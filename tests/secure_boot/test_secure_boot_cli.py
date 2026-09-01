import subprocess
import unittest
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from show.secure_boot import (
    secure_boot as show_secure_boot,
    run_backend as show_run_backend,
    BackendError as ShowBackendError,
)
from config.secure_boot import (
    secure_boot as config_secure_boot,
    run_backend as config_run_backend,
    BackendError as ConfigBackendError,
)

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
    def test_show_key(self, backend):
        backend.return_value = {"dbCustomer": {"state": "present", "entry_count": 4}}
        r = CliRunner().invoke(show_secure_boot, ["key", "db", "--store", "customer"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("present", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_key_unified_store(self, backend):
        backend.return_value = {"dbUnified": {"state": "present", "entry_count": 5}}
        r = CliRunner().invoke(show_secure_boot, ["key", "db", "--store", "unified"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("unified", r.output)
        backend.assert_called_once_with("key", "db", "--store", "unified")

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
    def _cp(stdout, rc=0):
        cp = MagicMock()
        cp.stdout = stdout
        cp.returncode = rc
        return cp

    @patch("show.secure_boot.subprocess.run")
    def test_show_run_backend_success(self, run):
        run.return_value = self._cp('{"mode": "ok"}')
        self.assertEqual(show_run_backend("mode"), {"mode": "ok"})

    @patch("show.secure_boot.subprocess.run", side_effect=FileNotFoundError)
    def test_show_run_backend_not_installed(self, run):
        with self.assertRaises(ShowBackendError):
            show_run_backend("mode")

    @patch(
        "show.secure_boot.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1),
    )
    def test_show_run_backend_timeout(self, run):
        with self.assertRaises(ShowBackendError):
            show_run_backend("mode")

    @patch("show.secure_boot.subprocess.run")
    def test_show_run_backend_bad_json(self, run):
        run.return_value = self._cp("not json")
        with self.assertRaises(ShowBackendError):
            show_run_backend("mode")

    @patch("show.secure_boot.subprocess.run")
    def test_show_run_backend_error_field(self, run):
        run.return_value = self._cp('{"error": "nope"}', rc=1)
        with self.assertRaises(ShowBackendError):
            show_run_backend("mode")

    @patch("config.secure_boot.subprocess.run")
    def test_config_run_backend_success(self, run):
        run.return_value = self._cp('{"ok": true}')
        self.assertEqual(config_run_backend("update"), {"ok": True})

    @patch("config.secure_boot.subprocess.run", side_effect=FileNotFoundError)
    def test_config_run_backend_not_installed(self, run):
        with self.assertRaises(ConfigBackendError):
            config_run_backend("update")

    @patch(
        "config.secure_boot.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1),
    )
    def test_config_run_backend_timeout(self, run):
        with self.assertRaises(ConfigBackendError):
            config_run_backend("update")

    @patch("config.secure_boot.subprocess.run")
    def test_config_run_backend_bad_json(self, run):
        run.return_value = self._cp("not json")
        with self.assertRaises(ConfigBackendError):
            config_run_backend("update")

    @patch("config.secure_boot.subprocess.run")
    def test_config_run_backend_error_field(self, run):
        run.return_value = self._cp('{"error": "nope"}', rc=1)
        with self.assertRaises(ConfigBackendError):
            config_run_backend("update")


if __name__ == "__main__":
    unittest.main()
