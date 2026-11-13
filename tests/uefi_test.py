import os
import struct
import sys
import tempfile
from unittest import mock

import click
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

from utilities_common import uefi as uefi_lib
from utilities_common import uefi_parser
from show.uefi import security as show_security
from show.uefi import attach as attach_show
from config.uefi import security as config_security
from config.uefi import attach as attach_config


EFI_READVAR_ALL = """\
Variable PK, length 1234
PK: list 0, type X509
    subject=CN=Owner PK
Variable KEK, length 2345
KEK: list 0, type X509
    subject=CN=Owner KEK1
"""


def _completed(stdout=b"", stderr=b"", returncode=0):
    result = mock.Mock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def _write_empty_auth2():
    """40-byte unsigned AUTH2 (dwLength 24, empty ESL)."""
    efi_time = struct.pack("<HBBBBB", 2026, 11, 12, 0, 0, 0) + b"\x00" * 9
    win = struct.pack("<IHH", 24, 0x0200, 0x0EF1) + uefi_parser.GUID_PKCS7
    fd, path = tempfile.mkstemp(suffix=".auth")
    os.write(fd, efi_time + win)
    os.close(fd)
    return path


def _write_raw_esl(sig_guid=None, payload=None, suffix=".esl"):
    if sig_guid is None:
        sig_guid = uefi_parser.GUID_SHA256
    if payload is None:
        payload = b"\x22" * 32
    owner = b"\x11" * 16
    sig_size = 16 + len(payload)
    list_size = 28 + sig_size
    esl = sig_guid + struct.pack("<III", list_size, 0, sig_size) + owner + payload
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, esl)
    os.close(fd)
    return path


def _write_auth2_with_pkcs7(pkcs7):
    efi_time = struct.pack("<HBBBBB", 2026, 11, 12, 0, 0, 0) + b"\x00" * 9
    dwlen = 24 + len(pkcs7)
    win = struct.pack("<IHH", dwlen, 0x0200, 0x0EF1) + uefi_parser.GUID_PKCS7
    fd, path = tempfile.mkstemp(suffix=".auth")
    os.write(fd, efi_time + win + pkcs7)
    os.close(fd)
    return path


class TestUefiLib(object):
    def test_normalize_var(self):
        assert uefi_lib.normalize_var("PK") == "pk"
        assert uefi_lib.uefi_name("dbx") == "dbx"
        try:
            uefi_lib.normalize_var("dbt")
            assert False, "expected UefiError"
        except uefi_lib.UefiError as exc:
            assert "dbt" in str(exc)

    def test_format_status(self):
        out = uefi_lib.format_status(1, 0)
        assert "SetupMode: 1 (Setup Mode)" in out
        assert "SecureBoot: 0 (not enforcing)" in out
        out = uefi_lib.format_status(0, 1)
        assert "SetupMode: 0 (User Mode)" in out
        assert "SecureBoot: 1 (enforcing)" in out

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_read_variables_all(self, mock_run, _mount, _isdir):
        mock_run.return_value = _completed(EFI_READVAR_ALL.encode())
        out = uefi_lib.read_variables(None)
        mock_run.assert_called_once_with(
            ["efi-readvar"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)
        assert "Variable PK" in out

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_read_variables_pk(self, mock_run, _mount, _isdir):
        mock_run.return_value = _completed(b"Variable PK, length 10\n")
        uefi_lib.read_variables("pk")
        mock_run.assert_called_once_with(
            ["efi-readvar", "-v", "PK"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_enroll_kek_esl(self, mock_run, _chattr, _isfile, _mount, _isdir):
        mock_run.return_value = _completed()
        uefi_lib.enroll("kek", "/tmp/KEK.esl")
        mock_run.assert_called_once_with(
            ["efi-updatevar", "-e", "-f", "/tmp/KEK.esl", "KEK"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_enroll_pk_auth2(self, mock_run, _chattr, _isfile, _mount, _isdir):
        mock_run.return_value = _completed()
        uefi_lib.enroll("pk", "/tmp/PK.auth")
        mock_run.assert_called_once_with(
            ["efi-updatevar", "-f", "/tmp/PK.auth", "PK"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_append_auth2(self, mock_run, _chattr, _isfile, _mount, _isdir):
        mock_run.return_value = _completed()
        uefi_lib.append("db", "/tmp/db.append.auth")
        mock_run.assert_called_once_with(
            ["efi-updatevar", "-a", "-f", "/tmp/db.append.auth", "db"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_update_auth2(self, mock_run, _chattr, _isfile, _mount, _isdir):
        mock_run.return_value = _completed()
        uefi_lib.update("db", "/tmp/db.auth")
        mock_run.assert_called_once_with(
            ["efi-updatevar", "-f", "/tmp/db.auth", "db"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_unclaim(self, mock_run, _chattr, _isfile, _mount, _isdir):
        mock_run.return_value = _completed()
        uefi_lib.unclaim("/tmp/PK.empty.auth")
        mock_run.assert_called_once_with(
            ["efi-updatevar", "-f", "/tmp/PK.empty.auth", "PK"],
            stdout=mock.ANY, stderr=mock.ANY, check=False)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_firmware_reject_is_not_retried(self, mock_run, _mount, _isdir):
        mock_run.return_value = _completed(
            stderr=b"Failed to update PK: Operation not permitted",
            returncode=1)
        with mock.patch("utilities_common.uefi.os.path.isfile", return_value=True):
            with mock.patch("utilities_common.uefi.clear_immutable"):
                try:
                    uefi_lib.update("pk", "/tmp/PK.empty.auth")
                    assert False, "expected UefiError"
                except uefi_lib.UefiError as exc:
                    assert "Operation not permitted" in str(exc)
        assert mock_run.call_count == 1

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_append_firmware_reject_is_not_retried_as_update(
            self, mock_run, _mount, _isdir):
        mock_run.return_value = _completed(
            stderr=b"Failed to update db: Operation not permitted",
            returncode=1)
        with mock.patch("utilities_common.uefi.os.path.isfile", return_value=True):
            with mock.patch("utilities_common.uefi.clear_immutable"):
                try:
                    uefi_lib.append("db", "/tmp/db.append.auth")
                    assert False, "expected UefiError"
                except uefi_lib.UefiError as exc:
                    assert "Operation not permitted" in str(exc)
        assert mock_run.call_count == 1
        assert mock_run.call_args[0][0] == [
            "efi-updatevar", "-a", "-f", "/tmp/db.append.auth", "db"]


class TestShowPlatformUefi(object):
    def test_commands_registered(self):
        @click.group()
        def platform():
            pass

        attach_show(platform)
        uefi = platform.commands["security"].commands["uefi"]
        assert "status" in uefi.commands
        assert "variables" in uefi.commands
        assert "inspect" in uefi.commands
        assert "compare" in uefi.commands
        assert "health" in uefi.commands

    def test_wired_in_show_platform(self):
        src = open(os.path.join(modules_path, "show/platform.py")).read()
        assert "show_uefi.attach(platform)" in src

    @mock.patch("utilities_common.uefi.read_status", return_value=(1, 0))
    def test_status(self, _status):
        result = CliRunner().invoke(show_security.commands["uefi"].commands["status"])
        assert result.exit_code == 0
        assert "SetupMode: 1 (Setup Mode)" in result.output
        assert "SecureBoot: 0 (not enforcing)" in result.output

    @mock.patch("utilities_common.uefi.read_variables", return_value=EFI_READVAR_ALL)
    def test_variables_all(self, mock_read):
        result = CliRunner().invoke(
            show_security.commands["uefi"].commands["variables"], ["all"])
        assert result.exit_code == 0
        mock_read.assert_called_once_with(None)
        assert "Variable PK" in result.output

    @mock.patch("utilities_common.uefi.read_variables", return_value="Variable PK\n")
    def test_variables_pk(self, mock_read):
        result = CliRunner().invoke(
            show_security.commands["uefi"].commands["variables"], ["pk"])
        assert result.exit_code == 0
        mock_read.assert_called_once_with("pk")

    def test_inspect_empty_auth2(self):
        path = _write_empty_auth2()
        try:
            result = CliRunner().invoke(
                show_security.commands["uefi"].commands["inspect"], [path])
            assert result.exit_code == 0, result.output
            assert "Type: AUTH2" in result.output
            assert "PKCS#7: empty" in result.output
            assert "ESL: empty" in result.output
        finally:
            os.unlink(path)

    @mock.patch("utilities_common.uefi.format_compare", return_value="Variable: db\n")
    def test_compare(self, mock_cmp):
        path = _write_raw_esl()
        try:
            result = CliRunner().invoke(
                show_security.commands["uefi"].commands["compare"], ["db", path])
            assert result.exit_code == 0, result.output
            mock_cmp.assert_called_once_with("db", path)
            assert "Variable: db" in result.output
        finally:
            os.unlink(path)

    @mock.patch("utilities_common.uefi.format_health",
                return_value="SetupMode: 1 (Setup Mode)\nFindings:\n  INFO: Setup Mode\n")
    def test_health(self, _health):
        result = CliRunner().invoke(show_security.commands["uefi"].commands["health"])
        assert result.exit_code == 0, result.output
        assert "Setup Mode" in result.output


class TestConfigPlatformUefi(object):
    def test_commands_registered(self):
        @click.group()
        def platform():
            pass

        attach_config(platform)
        uefi = platform.commands["security"].commands["uefi"]
        assert "enroll" in uefi.commands
        assert "append" in uefi.commands
        assert "update" in uefi.commands
        assert "unclaim" in uefi.commands
        assert "remove" not in uefi.commands
        assert "revoke" not in uefi.commands

    def test_wired_in_config_platform(self):
        src = open(os.path.join(modules_path, "config/main.py")).read()
        assert "uefi_cli.attach(platform)" in src

    @mock.patch("utilities_common.uefi.enroll")
    def test_enroll(self, mock_enroll):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["enroll"],
            ["-y", "kek", "/tmp/KEK.esl"])
        assert result.exit_code == 0, result.output
        mock_enroll.assert_called_once_with("kek", "/tmp/KEK.esl")

    @mock.patch("utilities_common.uefi.append")
    def test_append(self, mock_append):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["append"],
            ["-y", "db", "/tmp/db.append.auth"])
        assert result.exit_code == 0, result.output
        mock_append.assert_called_once_with("db", "/tmp/db.append.auth")

    @mock.patch("utilities_common.uefi.update")
    def test_update(self, mock_update):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["update"],
            ["-y", "db", "/tmp/db.auth"])
        assert result.exit_code == 0, result.output
        mock_update.assert_called_once_with("db", "/tmp/db.auth")

    @mock.patch("utilities_common.uefi.unclaim")
    def test_unclaim(self, mock_unclaim):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["unclaim"],
            ["-y", "PK.empty.auth"])
        assert result.exit_code == 0, result.output
        mock_unclaim.assert_called_once_with("PK.empty.auth")

    @mock.patch("utilities_common.uefi.enroll",
                side_effect=uefi_lib.UefiError("Failed to update PK: Operation not permitted"))
    def test_enroll_firmware_reject(self, _enroll):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["enroll"],
            ["-y", "pk", "/tmp/PK.auth"])
        assert result.exit_code == 1
        assert "Operation not permitted" in result.output
        assert result.output.count("Operation not permitted") == 1

    @mock.patch("utilities_common.uefi.unclaim")
    def test_unclaim_aborts_without_yes(self, mock_unclaim):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["unclaim"],
            ["PK.empty.auth"],
            input="n\n")
        assert result.exit_code != 0
        mock_unclaim.assert_not_called()

    @mock.patch("utilities_common.uefi.get_backend")
    def test_non_uefi_error(self, mock_backend):
        mock_backend.side_effect = uefi_lib.UefiError(uefi_lib.NOT_AVAILABLE)
        result = CliRunner().invoke(show_security.commands["uefi"].commands["status"])
        assert result.exit_code == 1
        assert "not available on this platform" in result.output


class TestUefiParser(object):
    def test_empty_auth2(self):
        path = _write_empty_auth2()
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "Type: AUTH2" in out
        assert "Time Stamp: 2026-11-12 00:00:00" in out
        assert "PKCS#7: empty" in out
        assert "ESL: empty" in out
        assert "unclaim" in out

    def test_raw_esl_sha256(self):
        path = _write_raw_esl()
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "Type: ESL" in out
        assert "SHA256" in out
        assert "Owner GUID : 11111111-1111-1111-1111-111111111111" in out
        assert "Hash: " + ("22" * 32) in out

    def test_raw_esl_sha384(self):
        path = _write_raw_esl(uefi_parser.GUID_SHA384, b"\x33" * 48)
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "SHA384" in out
        assert "Hash: " + ("33" * 48) in out

    def test_auth2_sha384_pkcs7_oid(self):
        # SHA-384 digest OID in PKCS#7 (RSA-4096 / SHA-384 platforms).
        pkcs7 = b"\x30\x0b" + b"\x06\x09" + bytes.fromhex("608648016503040202")
        path = _write_auth2_with_pkcs7(pkcs7)
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "Type: AUTH2" in out
        assert "SHA-384" in out

    def test_auth2_pqc_mldsa_oid(self):
        # ML-DSA-65 OID; openssl may not decode, inspect must still succeed.
        pkcs7 = b"\x30\x0b" + b"\x06\x09" + bytes.fromhex("608648016503040312")
        path = _write_auth2_with_pkcs7(pkcs7)
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "Type: AUTH2" in out
        assert "ML-DSA-65" in out

    def test_unknown_esl_type_does_not_fail(self):
        path = _write_raw_esl(b"\xab" * 16, b"\x06\x09" + bytes.fromhex("608648016503040311"))
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "Unknown" in out
        assert "Type GUID:" in out
        assert "ML-DSA-44" in out

    def test_compare_file_vs_store(self):
        store = _write_raw_esl(payload=b"\x22" * 32)
        incoming = _write_raw_esl(payload=b"\x44" * 32)
        try:
            with open(store, "rb") as handle:
                current = handle.read()
            backend = mock.Mock()
            backend.export_esl.return_value = current
            with mock.patch("utilities_common.uefi.get_backend", return_value=backend):
                out = uefi_lib.format_compare("db", incoming)
            assert "Current store: 1 entries" in out
            assert "AUTH2/ESL file: 1 entries" in out
            assert "In file, not in store" in out
            assert "In store, not in file" in out
            assert "(none)" in out.split("In both")[1].split("In file")[0]
        finally:
            os.unlink(store)
            os.unlink(incoming)

    def test_health_setup_mode_info(self):
        backend = mock.Mock()
        backend.get_status.return_value = (1, 0)
        backend.export_esl.return_value = b""
        with mock.patch("utilities_common.uefi.get_backend", return_value=backend):
            out = uefi_lib.format_health()
        assert "SetupMode: 1 (Setup Mode)" in out
        assert "INFO: Setup Mode" in out

    def test_missing_file(self):
        try:
            uefi_parser.format_payload("/no/such/file.auth")
            assert False, "expected UefiError"
        except uefi_lib.UefiError as exc:
            assert "File not found" in str(exc)
