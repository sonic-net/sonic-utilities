import subprocess
import unittest
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from show.secure_boot import (
    secure_boot as show_secure_boot,
)
from config.secure_boot import (
    secure_boot as config_secure_boot,
)
from utilities_common.secure_boot import (
    run_backend,
    BackendError,
)

# Backwards-compatible aliases used throughout the tests.
ShowBackendError = BackendError
ConfigBackendError = BackendError

MODE = {
    "raw": 11,
    "hex": "0x000b",
    "name": "Generic Mode",
    "policy": {
        "vendor_store_write": True,
        "vendor_store_lock": True,
        "customer_store_write": False,
        "customer_store_lock": True,
    },
}
KEYS = {
    "PKVendor": {"state": "present", "entry_count": 1},
    "KEKVendor": {"state": "present", "entry_count": 2},
    "dbVendor": {"state": "present", "entry_count": 3},
    "dbxVendor": {"state": "empty", "entry_count": 0},
    "PKCustomer": {"state": "empty", "entry_count": 0},
    "KEKCustomer": {"state": "empty", "entry_count": 0},
    "dbCustomer": {"state": "empty", "entry_count": 0},
    "dbxCustomer": {"state": "empty", "entry_count": 0},
}
KEYS_UNIFIED = {
    "PKUnified": {"state": "present", "entry_count": 1},
    "KEKUnified": {"state": "present", "entry_count": 2},
    "dbUnified": {"state": "present", "entry_count": 3},
    "dbxUnified": {"state": "empty", "entry_count": 0},
}


class TestShowSecureBoot(unittest.TestCase):
    @patch("show.secure_boot.run_backend")
    def test_show_mode(self, backend):
        backend.return_value = MODE
        r = CliRunner().invoke(show_secure_boot, ["mode"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("Generic Mode", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_mode_backend_error(self, backend):
        backend.side_effect = ShowBackendError("boom")
        r = CliRunner().invoke(show_secure_boot, ["mode"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("boom", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_status(self, backend):
        backend.return_value = {"mode": MODE, "keys": KEYS}
        r = CliRunner().invoke(show_secure_boot, ["status"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("PK", r.output)
        self.assertIn("present", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_status_backend_error(self, backend):
        backend.side_effect = ShowBackendError("boom")
        r = CliRunner().invoke(show_secure_boot, ["status"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("boom", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_status_unified(self, backend):
        backend.return_value = {"mode": MODE, "keys": KEYS_UNIFIED}
        r = CliRunner().invoke(show_secure_boot, ["status"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("PK", r.output)
        self.assertIn("present", r.output)
        # Unified rendering must not show vendor/customer columns.
        self.assertNotIn("Vendor State", r.output)
        self.assertNotIn("Customer State", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_keys(self, backend):
        backend.return_value = KEYS
        r = CliRunner().invoke(show_secure_boot, ["keys"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("vendor", r.output)
        self.assertIn("customer", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_keys_backend_error(self, backend):
        backend.side_effect = ShowBackendError("boom")
        r = CliRunner().invoke(show_secure_boot, ["keys"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("boom", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_keys_unified(self, backend):
        backend.return_value = KEYS_UNIFIED
        r = CliRunner().invoke(show_secure_boot, ["keys"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("unified", r.output)
        self.assertNotIn("vendor", r.output)
        self.assertNotIn("customer", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_key(self, backend):
        backend.return_value = {"dbCustomer": {"state": "present", "entry_count": 4}}
        r = CliRunner().invoke(show_secure_boot, ["key", "db", "--store", "customer"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("present", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_key_without_store(self, backend):
        backend.return_value = {"dbUnified": {"state": "present", "entry_count": 3}}
        r = CliRunner().invoke(show_secure_boot, ["key", "db"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("unified", r.output)
        backend.assert_called_once_with(("key", "db"), 180)

    @patch("show.secure_boot.run_backend")
    def test_show_key_unified_store(self, backend):
        backend.return_value = {"dbUnified": {"state": "present", "entry_count": 5}}
        r = CliRunner().invoke(show_secure_boot, ["key", "db", "--store", "unified"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("unified", r.output)
        backend.assert_called_once_with(("key", "db", "--store", "unified"), 180)

    @patch("show.secure_boot.run_backend")
    def test_show_key_empty_response(self, backend):
        backend.return_value = {}
        r = CliRunner().invoke(show_secure_boot, ["key", "db"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("invalid empty backend response", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_key_backend_error(self, backend):
        backend.side_effect = ShowBackendError("boom")
        r = CliRunner().invoke(show_secure_boot, ["key", "db"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("boom", r.output)


class TestConfigSecureBoot(unittest.TestCase):
    @patch("config.secure_boot.run_backend")
    def test_update(self, backend):
        backend.return_value = {"result": "success", "variable": "db", "operation": "append"}
        with CliRunner().isolated_filesystem():
            with open("db.auth", "w") as f:
                f.write("dummy")
            r = CliRunner().invoke(
                config_secure_boot,
                ["certificate", "update", "db", "db.auth", "--operation", "append"],
            )
        self.assertEqual(r.exit_code, 0)
        self.assertIn("submitted successfully", r.output)

    @patch("config.secure_boot.run_backend")
    def test_update_backend_error(self, backend):
        backend.side_effect = ConfigBackendError("boom")
        with CliRunner().isolated_filesystem():
            with open("db.auth", "w") as f:
                f.write("dummy")
            r = CliRunner().invoke(config_secure_boot, ["certificate", "update", "db", "db.auth"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("boom", r.output)


class TestRunBackend(unittest.TestCase):
    @staticmethod
    def _cp(stdout, rc=0, stderr=""):
        cp = MagicMock()
        cp.stdout = stdout
        cp.stderr = stderr
        cp.returncode = rc
        return cp

    @patch("utilities_common.secure_boot.subprocess.run")
    def test_run_backend_success(self, run):
        run.return_value = self._cp('{"mode": "ok"}')
        self.assertEqual(run_backend(("mode",), 180), {"mode": "ok"})

    @patch("utilities_common.secure_boot.subprocess.run", side_effect=FileNotFoundError)
    def test_run_backend_not_installed(self, run):
        with self.assertRaises(BackendError):
            run_backend(("mode",), 180)

    @patch(
        "utilities_common.secure_boot.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1),
    )
    def test_run_backend_timeout(self, run):
        with self.assertRaises(BackendError):
            run_backend(("mode",), 180)

    @patch("utilities_common.secure_boot.subprocess.run")
    def test_run_backend_bad_json(self, run):
        run.return_value = self._cp("not json")
        with self.assertRaises(BackendError):
            run_backend(("mode",), 180)

    @patch("utilities_common.secure_boot.subprocess.run")
    def test_run_backend_bad_json_surfaces_stderr(self, run):
        # Malformed stdout on a failed backend must not hide the stderr
        # diagnostic.
        run.return_value = self._cp("garbage", rc=1, stderr="useful platform error\n")
        with self.assertRaises(BackendError) as ctx:
            run_backend(("mode",), 180)
        self.assertIn("useful platform error", str(ctx.exception))

    @patch("utilities_common.secure_boot.subprocess.run")
    def test_run_backend_error_field(self, run):
        run.return_value = self._cp('{"error": "nope"}', rc=1)
        with self.assertRaises(BackendError) as ctx:
            run_backend(("mode",), 180)
        self.assertIn("nope", str(ctx.exception))

    @patch("utilities_common.secure_boot.subprocess.run")
    def test_run_backend_stderr_fallback(self, run):
        # Non-zero return code with valid JSON and no "error" field falls
        # back to the stderr diagnostic.
        run.return_value = self._cp("{}", rc=1, stderr="backend diagnostic\n")
        with self.assertRaises(BackendError) as ctx:
            run_backend(("update",), 300)
        self.assertIn("backend diagnostic", str(ctx.exception))

    @patch("utilities_common.secure_boot.subprocess.run")
    def test_run_backend_failure_default_message(self, run):
        # Non-zero return code with no error field and no stderr.
        run.return_value = self._cp("{}", rc=1, stderr="")
        with self.assertRaises(BackendError) as ctx:
            run_backend(("update",), 300)
        self.assertIn("secure boot backend failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
