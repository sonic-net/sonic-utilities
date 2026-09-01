import unittest
from unittest.mock import patch
from click.testing import CliRunner
from show.secure_boot import secure_boot as show_secure_boot
from config.secure_boot import secure_boot as config_secure_boot

MODE = {"raw": 11, "hex": "0x000b", "name": "Generic Mode", "policy": {"vendor_store_write": True, "vendor_store_lock": True, "customer_store_write": False, "customer_store_lock": True}}
KEYS = {"PKVendor":{"state":"present","certificate_count":1},"KEKVendor":{"state":"present","certificate_count":2},"dbVendor":{"state":"present","certificate_count":3},"dbxVendor":{"state":"empty","certificate_count":0},"PKCustomer":{"state":"empty","certificate_count":0},"KEKCustomer":{"state":"empty","certificate_count":0},"dbCustomer":{"state":"empty","certificate_count":0},"dbxCustomer":{"state":"empty","certificate_count":0}}

class TestShowSecureBoot(unittest.TestCase):
    @patch("show.secure_boot.run_backend")
    def test_show_mode(self, backend):
        backend.return_value = MODE
        r = CliRunner().invoke(show_secure_boot, ["mode"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("Generic Mode", r.output)

    @patch("show.secure_boot.run_backend")
    def test_show_status(self, backend):
        backend.return_value = {"mode": MODE, "keys": KEYS}
        r = CliRunner().invoke(show_secure_boot, ["status"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("PK", r.output)
        self.assertIn("present", r.output)

class TestConfigSecureBoot(unittest.TestCase):
    @patch("config.secure_boot.run_backend")
    def test_update(self, backend):
        backend.return_value = {"result":"success", "variable":"db", "operation":"append"}
        with CliRunner().isolated_filesystem():
            with open("db.auth", "w") as f: f.write("dummy")
            r = CliRunner().invoke(config_secure_boot, ["certificate","update","db","db.auth","--operation","append"])
        self.assertEqual(r.exit_code, 0)
        self.assertIn("submitted successfully", r.output)

    def test_mode_set_requires_yes(self):
        with CliRunner().isolated_filesystem():
            with open("ov.cms", "w") as f: f.write("dummy")
            r = CliRunner().invoke(config_secure_boot, ["mode","set","ov.cms"])
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("--yes", r.output)

if __name__ == "__main__":
    unittest.main()
