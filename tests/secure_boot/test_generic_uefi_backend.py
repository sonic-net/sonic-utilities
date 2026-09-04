import io
import struct
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch, mock_open

from secure_boot import generic_uefi_backend as gb


def _signature_list(sig_size=20, header_size=0, entries=2, sig_type=b"\x11" * 16):
    payload = (b"\x22" * sig_size) * entries
    list_size = 28 + header_size + len(payload)
    return (
        sig_type
        + struct.pack("<III", list_size, header_size, sig_size)
        + (b"\x33" * header_size)
        + payload
    )


class TestSignatureCounting(unittest.TestCase):
    def test_single_list(self):
        self.assertEqual(gb._count_signature_entries(_signature_list(entries=3)), 3)

    def test_multiple_lists(self):
        payload = _signature_list(entries=2) + _signature_list(entries=1, sig_type=b"\x44" * 16)
        self.assertEqual(gb._count_signature_entries(payload), 3)

    def test_truncated_list_raises(self):
        with self.assertRaises(gb.BackendError):
            gb._count_signature_entries(b"\x00" * 10)

    def test_zero_signature_size_raises(self):
        bad = b"\x11" * 16 + struct.pack("<III", 28, 0, 0)
        with self.assertRaises(gb.BackendError):
            gb._count_signature_entries(bad)

    def test_signature_list_invalid_header_size(self):
        # SignatureHeaderSize pushes the entries start beyond the list end.
        bad = b"\x11" * 16 + struct.pack("<III", 28, 100, 20)
        with self.assertRaises(gb.BackendError):
            gb._count_signature_entries(bad)


class TestReadVariable(unittest.TestCase):
    def test_missing_variable_is_empty(self):
        with patch("os.path.exists", return_value=False):
            self.assertEqual(
                gb._read_variable("db"),
                {"state": "empty", "entry_count": 0, "data_length": 0},
            )

    def test_present_variable_counts_entries(self):
        payload = _signature_list(entries=2)
        content = b"\x06\x00\x00\x00" + payload  # 4-byte attr word + payload
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=content)):
            result = gb._read_variable("db")
        self.assertEqual(result["state"], "present")
        self.assertEqual(result["entry_count"], 2)
        self.assertEqual(result["data_length"], len(payload))

    def test_attr_only_is_empty(self):
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"\x06\x00\x00\x00")):
            self.assertEqual(gb._read_variable("db")["state"], "empty")

    def test_read_variable_invalid_attribute_only_length(self):
        # Fewer than 4 bytes cannot contain the efivarfs attribute word.
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"\x00\x00")):
            with self.assertRaises(gb.BackendError):
                gb._read_variable("db")


class TestMode(unittest.TestCase):
    def test_secure_boot_enabled(self):
        def raw(name):
            return {"SecureBoot": 1, "SetupMode": 0}[name]

        with patch.object(gb, "_read_raw_byte_variable", side_effect=raw):
            m = gb._mode()
        self.assertEqual(m["raw"], 1)
        self.assertEqual(m["name"], "Secure Boot Enabled")
        self.assertFalse(m["policy"]["vendor_store_write"])

    def test_setup_mode(self):
        def raw(name):
            return {"SecureBoot": 0, "SetupMode": 1}[name]

        with patch.object(gb, "_read_raw_byte_variable", side_effect=raw):
            self.assertEqual(gb._mode()["name"], "Setup Mode")

    def test_mode_unavailable_raises(self):
        with patch.object(gb, "_read_raw_byte_variable", return_value=None):
            with self.assertRaises(gb.BackendError):
                gb._mode()


class TestCommands(unittest.TestCase):
    def test_keys_uses_unified_suffix(self):
        with patch.object(gb, "_read_variable", return_value={"state": "empty", "entry_count": 0}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gb.cmd_keys()
        self.assertEqual(rc, 0)
        self.assertIn("PKUnified", buf.getvalue())
        self.assertNotIn("PKVendor", buf.getvalue())

    def test_key_rejects_vendor_store(self):
        with self.assertRaises(gb.BackendError):
            gb.cmd_key("db", "vendor")

    def test_key_rejects_customer_store(self):
        with self.assertRaises(gb.BackendError):
            gb.cmd_key("db", "customer")

    def test_key_unified_ok(self):
        with patch.object(gb, "_read_variable", return_value={"state": "present", "entry_count": 1}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gb.cmd_key("db", "unified")
        self.assertEqual(rc, 0)
        self.assertIn("dbUnified", buf.getvalue())


class TestMain(unittest.TestCase):
    def test_main_no_uefi_services(self):
        with patch.object(gb, "_uefi_available", return_value=False):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gb.main()
        self.assertEqual(rc, 1)
        self.assertIn("not available", buf.getvalue())

    def test_main_dispatches_keys(self):
        with patch.object(gb, "_uefi_available", return_value=True), \
             patch.object(gb.sys, "argv", ["x", "keys"]), \
             patch.object(gb, "_read_variable", return_value={"state": "empty", "entry_count": 0}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gb.main()
        self.assertEqual(rc, 0)
        self.assertIn("dbxUnified", buf.getvalue())

    def test_main_backend_error_is_json(self):
        with patch.object(gb, "_uefi_available", return_value=True), \
             patch.object(gb.sys, "argv", ["x", "key", "db", "--store", "vendor"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gb.main()
        self.assertEqual(rc, 1)
        self.assertIn("not supported", buf.getvalue())


class TestUpdate(unittest.TestCase):
    def test_update_requires_root(self):
        with patch("os.geteuid", return_value=1000):
            with self.assertRaises(gb.BackendError):
                gb._write_authenticated_variable("db", "/tmp/x.auth", "update")

    def test_update_empty_file_rejected(self):
        with patch("os.geteuid", return_value=0), \
             patch("builtins.open", mock_open(read_data=b"")):
            with self.assertRaises(gb.BackendError):
                gb._write_authenticated_variable("db", "/tmp/x.auth", "update")

    @staticmethod
    def _run_update(variable, operation, payload=b"authpayload"):
        written = {}
        m = mock_open(read_data=payload)

        def open_side_effect(path, mode="r", *args, **kwargs):
            handle = m(path, mode, *args, **kwargs)
            if "w" in mode:
                def _capture(data):
                    written["path"] = path
                    written["data"] = data
                handle.write.side_effect = _capture
            return handle

        with patch("os.geteuid", return_value=0), \
             patch("builtins.open", side_effect=open_side_effect):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gb._write_authenticated_variable(variable, "/tmp/x.auth", operation)
        return rc, buf.getvalue(), written

    def test_update_append_sets_attribute_and_writes(self):
        rc, out, written = self._run_update("db", "append")
        self.assertEqual(rc, 0)
        self.assertIn("success", out)
        attr = struct.unpack("<I", written["data"][:4])[0]
        self.assertTrue(attr & gb.EFI_VARIABLE_APPEND_WRITE)
        self.assertEqual(written["data"][4:], b"authpayload")

    def test_update_remove_does_not_set_append(self):
        rc, _, written = self._run_update("dbx", "remove")
        self.assertEqual(rc, 0)
        attr = struct.unpack("<I", written["data"][:4])[0]
        self.assertFalse(attr & gb.EFI_VARIABLE_APPEND_WRITE)

    def test_update_update_does_not_set_append(self):
        rc, _, written = self._run_update("db", "update")
        self.assertEqual(rc, 0)
        attr = struct.unpack("<I", written["data"][:4])[0]
        self.assertFalse(attr & gb.EFI_VARIABLE_APPEND_WRITE)


if __name__ == "__main__":
    unittest.main()
