import concurrent.futures
from contextvars import copy_context
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import uuid

from generic_config_updater import reporting


class TestReporting(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        patcher = mock.patch.object(reporting, "REPORT_DIRECTORY", self.directory.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.report_id = str(uuid.uuid4())
        self.path = Path(self.directory.name) / f"gcu-apply.{self.report_id}.json"

    def read_report(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_disabled_reporting_does_not_create_files_or_translate_failure(self):
        error = ValueError("original")
        with mock.patch.object(reporting, "ErrorReport") as create:
            with self.assertRaises(ValueError) as caught:
                with reporting.report_session(), reporting.stage("input"):
                    reporting.remember_config({"key": "value"})
                    raise error
        self.assertIs(error, caught.exception)
        create.assert_not_called()
        self.assertEqual([], list(Path(self.directory.name).iterdir()))

    def test_success_is_published_atomically_with_no_actions_or_health_claims(self):
        replace = os.replace

        def publish(source, destination):
            self.assertFalse(self.path.exists())
            pending_text = Path(source).read_text(encoding="utf-8")
            self.assertTrue(pending_text.endswith("\n"))
            pending = json.loads(pending_text)
            self.assertEqual("0", pending["sonic_upgrade_summary"]["fault_code"])
            return replace(source, destination)

        with mock.patch.object(reporting.os, "replace", side_effect=publish):
            with reporting.report_session(self.report_id), reporting.stage("configdb_comparison"):
                self.assertFalse(self.path.exists())
        report = self.read_report()
        self.assertEqual(self.report_id, report["sonic_upgrade_summary"]["guid"])
        self.assertEqual([{"name": "configdb_comparison", "rc": "0"}],
                         report["sonic_upgrade_report"]["stages"])
        self.assertEqual([], report["sonic_upgrade_report"]["health_checks"])
        self.assertFalse(report["sonic_upgrade_actions"]["retriable"])
        self.assertFalse(report["sonic_upgrade_actions"]["isolate_on_failure"])
        self.assertFalse(self.path.with_suffix(".pending").exists())

    def test_failure_retains_original_exception_stage_and_redacts_values(self):
        secret = "synthetic-'credential'\\with\nescapes"
        error = ValueError(f"unknown field password: {json.dumps(secret)}")
        with self.assertRaises(ValueError) as caught:
            with reporting.report_session(self.report_id, failure_exit_code=2):
                reporting.remember_patch([{"path": "/AAA/key", "value": secret}])
                reporting.remember_config({"AAA": {"key": {"password": "old-credential"}}})
                with reporting.scope("localhost"), reporting.stage("sorting"):
                    raise error
        self.assertIs(error, caught.exception)
        report = self.read_report()
        self.assertEqual("2", report["sonic_upgrade_summary"]["fault_code"])
        self.assertEqual([{"name": "localhost.sorting", "rc": "2"}],
                         report["sonic_upgrade_report"]["stages"])
        message = report["sonic_upgrade_report"]["errors"][0]["message"]
        self.assertIn("unknown field password", message)
        self.assertIn("[redacted]", message)
        self.assertNotIn("credential", self.path.read_text())
        self.assertFalse(reporting.enabled())

    def test_unavailable_redaction_inputs_do_not_expose_exception_text(self):
        with self.assertRaises(RuntimeError):
            with reporting.report_session(self.report_id), reporting.stage("running_config"):
                raise RuntimeError("sensitive command output")
        self.assertNotIn("sensitive command output", self.path.read_text())
        self.assertIn("redaction inputs are unavailable", self.path.read_text())

    def test_redaction_budget_exhaustion_omits_diagnostic_without_changing_failure(self):
        with mock.patch.object(reporting, "MAX_REDACTION_BYTES", 8):
            with self.assertRaises(ValueError):
                with reporting.report_session(self.report_id):
                    reporting.remember_config({"key": "long-private-value"})
                    raise ValueError("long-private-value")
        self.assertNotIn("long-private-value", self.path.read_text())
        self.assertEqual("1", self.read_report()["sonic_upgrade_summary"]["fault_code"])

    def test_completed_id_cannot_be_reused(self):
        with reporting.report_session(self.report_id):
            pass
        original = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            with reporting.report_session(self.report_id):
                self.fail("An old report must not authorize another command")
        self.assertEqual(original, self.path.read_bytes())

    def test_pending_id_cannot_be_reused_concurrently(self):
        with reporting.report_session(self.report_id):
            with self.assertRaises(FileExistsError):
                with reporting.report_session(self.report_id):
                    self.fail("Only one owner may use this invocation ID")

    def test_completion_between_identity_check_and_reservation_blocks_reuse(self):
        first = reporting.ErrorReport(self.report_id, "apply", 1)
        open_reservation = os.open
        original = []

        def finish_before_reservation(path, flags, mode):
            first.publish(None)
            original.append(self.path.read_bytes())
            return open_reservation(path, flags, mode)

        operation = mock.Mock()
        with mock.patch.object(reporting.os, "open", side_effect=finish_before_reservation):
            with self.assertRaises(FileExistsError):
                with reporting.report_session(self.report_id):
                    operation()
        operation.assert_not_called()
        self.assertEqual(original[0], self.path.read_bytes())

    def test_precheck_and_application_reports_have_distinct_phase_identity(self):
        with reporting.report_session(self.report_id, "precheck"):
            pass
        with reporting.report_session(self.report_id):
            pass
        precheck = Path(self.directory.name) / f"gcu-precheck.{self.report_id}.json"
        self.assertEqual("gcu-precheck", json.loads(precheck.read_text())["sonic_upgrade_summary"]["script_name"])
        self.assertEqual("gcu-apply", self.read_report()["sonic_upgrade_summary"]["script_name"])

    def test_invalid_identifier_and_phase_cannot_reach_the_operation(self):
        for report_id, phase in (("../invalid", "apply"), (self.report_id, "../invalid")):
            with self.subTest(report_id=report_id, phase=phase):
                with self.assertRaises(ValueError):
                    with reporting.report_session(report_id, phase):
                        self.fail("Invalid report identity must fail before dispatch")

    def test_publication_failure_after_success_is_not_silently_successful(self):
        with mock.patch.object(reporting.os, "replace", side_effect=OSError("read only")):
            with self.assertRaisesRegex(RuntimeError, "reconcile configuration"):
                with reporting.report_session(self.report_id):
                    pass
        self.assertFalse(self.path.exists())
        self.assertTrue(self.path.with_suffix(".pending").exists())
        self.assertFalse(reporting.enabled())

    def test_publication_failure_does_not_replace_original_execution_failure(self):
        error = ValueError("original")
        with mock.patch.object(reporting.os, "replace", side_effect=OSError("read only")), \
                mock.patch.object(reporting.sys, "stderr", new_callable=io.StringIO) as stderr:
            with self.assertRaises(ValueError) as caught:
                with reporting.report_session(self.report_id):
                    raise error
        self.assertIs(error, caught.exception)
        self.assertIn("original command failure retained", stderr.getvalue())
        self.assertFalse(self.path.exists())

    def test_parallel_scopes_share_report_but_do_not_mix_stage_names(self):
        barrier = threading.Barrier(2)

        def run(scope):
            with reporting.scope(scope), reporting.stage("configdb_writes"):
                barrier.wait(timeout=5)

        with reporting.report_session(self.report_id):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(copy_context().run, run, scope)
                           for scope in ("asic0", "asic1")]
                for future in futures:
                    future.result()
        self.assertEqual(
            {"asic0.configdb_writes", "asic1.configdb_writes"},
            {stage["name"] for stage in self.read_report()["sonic_upgrade_report"]["stages"]},
        )

    def test_broken_diagnostic_stream_cannot_replace_the_original_failure(self):
        error = ValueError("original")
        stderr = mock.Mock()
        stderr.write.side_effect = OSError("closed stream")
        with mock.patch.object(reporting.os, "replace", side_effect=OSError("read only")), \
                mock.patch.object(reporting.sys, "stderr", stderr):
            with self.assertRaises(ValueError) as caught:
                with reporting.report_session(self.report_id):
                    raise error
        self.assertIs(error, caught.exception)
        self.assertFalse(reporting.enabled())
        self.assertFalse(self.path.exists())

    def test_truncated_observations_preserve_command_failure_and_report_the_limit(self):
        with mock.patch.object(reporting, "MAX_STAGES", 1), mock.patch.object(reporting, "MAX_ERRORS", 1):
            with self.assertRaises(ValueError):
                with reporting.report_session(self.report_id), reporting.stage("apply_patch"):
                    with reporting.stage("sorting"):
                        raise ValueError("synthetic validation failure")
        report = self.read_report()
        self.assertEqual("1", report["sonic_upgrade_summary"]["fault_code"])
        self.assertEqual([{"name": "apply_patch", "rc": "1"}], report["sonic_upgrade_report"]["stages"])
        self.assertEqual(["sorting", "report_limits"],
                         [entry["name"] for entry in report["sonic_upgrade_report"]["errors"]])

    def test_process_exit_and_click_interrupt_use_actual_exit_codes(self):
        for error, interrupt_code, expected in (
            (SystemExit(-1), 130, "255"),
            (KeyboardInterrupt(), 130, "130"),
            (KeyboardInterrupt(), 1, "1"),
        ):
            with self.subTest(error=type(error).__name__, interrupt_code=interrupt_code):
                report_id = str(uuid.uuid4())
                with self.assertRaises(type(error)):
                    with reporting.report_session(report_id, interrupt_exit_code=interrupt_code):
                        raise error
                path = Path(self.directory.name) / f"gcu-apply.{report_id}.json"
                self.assertEqual(expected, json.loads(path.read_text())["sonic_upgrade_summary"]["fault_code"])

    @unittest.skipUnless(os.name == "posix", "POSIX report permissions")
    def test_report_is_private_on_posix(self):
        with reporting.report_session(self.report_id):
            pass
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
