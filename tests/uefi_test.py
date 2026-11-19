import os
import struct
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from unittest import mock

import click
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

from utilities_common import uefi as uefi_lib  # noqa: E402
from utilities_common import uefi_parser  # noqa: E402
from show.uefi import security as show_security  # noqa: E402
from show.uefi import attach as attach_show  # noqa: E402
from config.uefi import security as config_security  # noqa: E402
from config.uefi import attach as attach_config  # noqa: E402


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

    def test_guid_to_str_short_and_efi_time_short(self):
        assert uefi_parser.guid_to_str(b"abcd") == b"abcd".hex()
        assert "<short>" in uefi_parser._efi_time(b"\x00\x01")

    def test_extract_esl_invalid_dwlength(self):
        efi_time = b"\x00" * 16
        win = struct.pack("<IHH", 10, 0x0200, 0x0EF1) + uefi_parser.GUID_PKCS7
        try:
            uefi_parser.extract_esl(efi_time + win)
            assert False, "expected UefiError"
        except uefi_lib.UefiError as exc:
            assert "dwLength" in str(exc)

    def test_entries_from_bytes_none_and_truncated_list(self):
        assert uefi_parser.entries_from_bytes(None) == []
        truncated = uefi_parser.GUID_SHA256 + struct.pack("<III", 8, 0, 48)
        assert uefi_parser.entries_from_bytes(truncated) == []

    def test_entry_label_hash_and_unknown(self):
        owner = b"\x11" * 16
        label = uefi_parser._entry_label("SHA256", b"\xab" * 32, owner)
        assert label.startswith("SHA256 ")
        unknown = uefi_parser._entry_label("Unknown", b"\x00", owner)
        assert "owner=" in unknown

    def test_x509_field_openssl_missing_and_fail(self):
        with mock.patch("utilities_common.uefi_parser.subprocess.run",
                        side_effect=OSError("no openssl")):
            assert uefi_parser.x509_field(b"cert", "-subject") is None
        failed = mock.Mock(returncode=1, stdout=b"", stderr=b"bad")
        with mock.patch("utilities_common.uefi_parser.subprocess.run",
                        return_value=failed):
            assert uefi_parser.x509_field(b"cert", "-subject") is None

    def test_x509_dates_parse_and_skip_bad_lines(self):
        raw = (
            "notBefore=Jan  1 00:00:00 2020 GMT\n"
            "garbage\n"
            "notAfter=not-a-date\n"
            "notAfter=Jan  1 00:00:00 2030 GMT\n"
        )
        with mock.patch("utilities_common.uefi_parser.x509_field", return_value=raw):
            before, after = uefi_parser.x509_dates(b"cert")
        assert before.year == 2020
        assert after.year == 2030
        with mock.patch("utilities_common.uefi_parser.x509_field", return_value=""):
            assert uefi_parser.x509_dates(b"cert") == (None, None)

    def test_scan_oids_skips_invalid_length(self):
        assert uefi_parser.scan_oids(b"\x06\x00") == []
        assert uefi_parser.scan_oids(b"\x06\x80abc") == []

    def test_x509_summary_openssl_paths(self):
        with mock.patch("utilities_common.uefi_parser.subprocess.run",
                        side_effect=OSError("missing")):
            lines = uefi_parser._x509_summary(b"cert")
        assert any("openssl not available" in line for line in lines)
        failed = mock.Mock(returncode=1, stdout=b"", stderr=b"pqc")
        with mock.patch("utilities_common.uefi_parser.subprocess.run",
                        return_value=failed):
            lines = uefi_parser._x509_summary(b"cert")
        assert any("could not decode" in line for line in lines)
        ok = mock.Mock(
            returncode=0,
            stdout=b"        Subject: CN=Owner\n        Not After: 2030\n"
                   b"        Signature Algorithm: sha256WithRSAEncryption\n",
            stderr=b"")
        with mock.patch("utilities_common.uefi_parser.subprocess.run",
                        return_value=ok):
            lines = uefi_parser._x509_summary(b"cert")
        assert any("Subject:" in line for line in lines)
        assert any("Signature Algorithm:" in line for line in lines)

    def test_hash_lines_sha512_and_unknown(self):
        sha512 = uefi_parser._hash_lines("SHA512", b"\x55" * 64)
        assert sha512[0].endswith(("55" * 64))
        other = uefi_parser._hash_lines("RSA2048", b"\x01\x02")
        assert "0102" in other[0]

    def test_format_payload_invalid_auth2_and_sha512(self):
        efi_time = struct.pack("<HBBBBB", 2026, 1, 1, 0, 0, 0) + b"\x00" * 9
        short = efi_time + struct.pack("<IHH", 10, 0x0200, 0x0EF1) + uefi_parser.GUID_PKCS7
        fd, path = tempfile.mkstemp(suffix=".auth")
        os.write(fd, short)
        os.close(fd)
        try:
            try:
                uefi_parser.format_payload(path)
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "dwLength" in str(exc)
        finally:
            os.unlink(path)

        huge = efi_time + struct.pack("<IHH", 5000, 0x0200, 0x0EF1) + uefi_parser.GUID_PKCS7
        fd, path = tempfile.mkstemp(suffix=".auth")
        os.write(fd, huge)
        os.close(fd)
        try:
            try:
                uefi_parser.format_payload(path)
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "PKCS#7" in str(exc)
        finally:
            os.unlink(path)

        path = _write_raw_esl(uefi_parser.GUID_SHA512, b"\x66" * 64)
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "SHA512" in out
        assert "66" * 16 in out

    def test_format_payload_x509_and_invalid_esl_list(self):
        path = _write_raw_esl(uefi_parser.GUID_X509, b"not-a-real-cert")
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "X509" in out

        fd, path = tempfile.mkstemp(suffix=".esl")
        os.write(fd, uefi_parser.GUID_SHA256 + struct.pack("<III", 8, 0, 48) + b"\x00" * 8)
        os.close(fd)
        try:
            out = uefi_parser.format_payload(path)
        finally:
            os.unlink(path)
        assert "ERROR: invalid ESL list" in out


class TestUefiErrorPaths(object):
    def test_normalize_var_none(self):
        assert uefi_lib.normalize_var(None) is None

    def test_audit_falls_back_to_syslog_then_swallows(self):
        with mock.patch.dict(sys.modules, {"config.utils": None}):
            with mock.patch("syslog.openlog"), mock.patch("syslog.syslog"):
                uefi_lib.audit_notice("n")
                uefi_lib.audit_error("e")
            with mock.patch.dict(sys.modules, {"syslog": None}):
                uefi_lib.audit_notice("n")

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run",
                side_effect=OSError("No such file or directory"))
    def test_run_oserror_install_efitools(self, _run, _chattr, _isfile, _mount, _isdir):
        try:
            uefi_lib.enroll("kek", "/tmp/KEK.esl")
            assert False, "expected UefiError"
        except uefi_lib.UefiError as exc:
            assert "Install efitools" in str(exc)

    @mock.patch("utilities_common.uefi.os.path.isdir", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.ismount", return_value=True)
    @mock.patch("utilities_common.uefi.os.path.isfile", return_value=True)
    @mock.patch("utilities_common.uefi.clear_immutable")
    @mock.patch("utilities_common.uefi.subprocess.run")
    def test_run_writes_stdout_when_not_capturing(
            self, mock_run, _chattr, _isfile, _mount, _isdir):
        mock_run.return_value = _completed(stdout=b"updated\n")
        uefi_lib.enroll("kek", "/tmp/KEK.esl")

    def test_clear_immutable_missing_and_chattr_errors(self):
        uefi_lib.clear_immutable("/no/such/efivar")
        with mock.patch("utilities_common.uefi.os.path.exists", return_value=True):
            with mock.patch("utilities_common.uefi.subprocess.call",
                            side_effect=OSError("no chattr")):
                uefi_lib.clear_immutable("/sys/firmware/efi/efivars/PK")
            with mock.patch("utilities_common.uefi.subprocess.call", return_value=0) as call:
                uefi_lib.clear_immutable("/sys/firmware/efi/efivars/PK")
                call.assert_called_once()

    def test_backend_ensure_mount_and_unavailable(self):
        backend = uefi_lib.EfitoolsBackend()
        with mock.patch.object(backend, "available", return_value=False):
            try:
                backend.ensure()
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "not available" in str(exc)
        with mock.patch("utilities_common.uefi.os.path.isdir", return_value=True):
            with mock.patch("utilities_common.uefi.os.path.ismount", return_value=False):
                with mock.patch("utilities_common.uefi.os.makedirs"):
                    with mock.patch("utilities_common.uefi.subprocess.check_call") as mount:
                        backend.ensure()
                        mount.assert_called_once()
                    with mock.patch("utilities_common.uefi.subprocess.check_call",
                                    side_effect=OSError("mount failed")):
                        try:
                            backend.ensure()
                            assert False, "expected UefiError"
                        except uefi_lib.UefiError as exc:
                            assert "efivarfs" in str(exc)

    def test_export_esl_missing_short_and_payload(self):
        backend = uefi_lib.EfitoolsBackend()
        with mock.patch.object(backend, "ensure"):
            with mock.patch("utilities_common.uefi.os.path.exists", return_value=False):
                assert backend.export_esl("pk") == b""
            with mock.patch("utilities_common.uefi.os.path.exists", return_value=True):
                with mock.patch("builtins.open", mock.mock_open(read_data=b"attr")):
                    assert backend.export_esl("pk") == b""
                with mock.patch("builtins.open",
                                mock.mock_open(read_data=b"attr" + b"esl-bytes")):
                    assert backend.export_esl("pk") == b"esl-bytes"

    def test_enroll_and_append_missing_file(self):
        backend = uefi_lib.EfitoolsBackend()
        with mock.patch.object(backend, "ensure"):
            with mock.patch("utilities_common.uefi.os.path.isfile", return_value=False):
                try:
                    backend.enroll("kek", "/no/KEK.esl")
                    assert False, "expected UefiError"
                except uefi_lib.UefiError as exc:
                    assert "File not found" in str(exc)
                try:
                    backend.append("db", "/no/db.auth")
                    assert False, "expected UefiError"
                except uefi_lib.UefiError as exc:
                    assert "File not found" in str(exc)

    def test_get_backend_platform_and_fallback(self):
        class Plat(object):
            def available(self):
                return True

        class Unavail(object):
            def available(self):
                return False

        class NoFlag(object):
            pass

        plat_mod = mock.Mock(UefiBackend=Plat)
        with mock.patch.dict(sys.modules, {
                "sonic_platform": mock.Mock(),
                "sonic_platform.uefi": plat_mod}):
            assert isinstance(uefi_lib.get_backend(), Plat)

        plat_mod.UefiBackend = Unavail
        with mock.patch.dict(sys.modules, {
                "sonic_platform": mock.Mock(),
                "sonic_platform.uefi": plat_mod}):
            try:
                uefi_lib.get_backend()
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "not available" in str(exc)

        plat_mod.UefiBackend = NoFlag
        with mock.patch.dict(sys.modules, {
                "sonic_platform": mock.Mock(),
                "sonic_platform.uefi": plat_mod}):
            assert isinstance(uefi_lib.get_backend(), NoFlag)

        with mock.patch("utilities_common.uefi.os.path.isdir", return_value=False):
            try:
                uefi_lib.get_backend()
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "not available" in str(exc)

    def test_read_flag_errors_and_value(self):
        with mock.patch("builtins.open", side_effect=OSError("denied")):
            try:
                uefi_lib._read_flag("/sys/x", "SetupMode")
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "Cannot read SetupMode" in str(exc)
        with mock.patch("builtins.open", mock.mock_open(read_data=b"1234")):
            try:
                uefi_lib._read_flag("/sys/x", "SetupMode")
                assert False, "expected UefiError"
            except uefi_lib.UefiError as exc:
                assert "truncated" in str(exc)
        with mock.patch("builtins.open", mock.mock_open(read_data=b"attr\x01")):
            assert uefi_lib._read_flag("/sys/x", "SetupMode") == 1

    def test_format_compare_overlap_and_empty_file(self):
        shared = _write_raw_esl(payload=b"\x22" * 32)
        empty = _write_empty_auth2()
        try:
            with open(shared, "rb") as handle:
                current = handle.read()
            backend = mock.Mock()
            backend.export_esl.return_value = current
            with mock.patch("utilities_common.uefi.get_backend", return_value=backend):
                both = uefi_lib.format_compare("db", shared)
                cleared = uefi_lib.format_compare("pk", empty)
            assert "In both (unchanged):" in both
            assert "(none)" in both.split("In file, not in store")[1]
            assert "File ESL is empty" in cleared
        finally:
            os.unlink(shared)
            os.unlink(empty)

    def test_format_health_expiry_overlap_and_user_mode(self):
        now = datetime.now(timezone.utc)
        expired = {"type": "X509", "label": "old", "digest": "aa", "payload": b"old"}
        soon = {"type": "X509", "label": "soon", "digest": "bb", "payload": b"soon"}
        ok = {"type": "X509", "label": "ok", "digest": "cc", "payload": b"ok"}
        hashed = {"type": "SHA256", "label": "h", "digest": "aa", "payload": b"h"}
        unknown = {"type": "X509", "label": "unk", "digest": "dd", "payload": b"unk"}

        def dates(payload):
            if payload == b"old":
                return now - timedelta(days=400), now - timedelta(days=1)
            if payload == b"soon":
                return now - timedelta(days=10), now + timedelta(days=7)
            if payload == b"ok":
                return now - timedelta(days=10), now + timedelta(days=400)
            return None, None

        backend = mock.Mock()
        backend.get_status.return_value = (0, 1)
        backend.export_esl.side_effect = lambda var: var.encode()

        def entries(data):
            return {
                b"pk": [ok],
                b"kek": [],
                b"db": [expired, soon, ok, hashed],
                b"dbx": [hashed, unknown],
            }.get(data, [])

        with mock.patch("utilities_common.uefi.get_backend", return_value=backend):
            with mock.patch("utilities_common.uefi_parser.entries_from_bytes",
                            side_effect=entries):
                with mock.patch("utilities_common.uefi_parser.x509_dates",
                                side_effect=dates):
                    out = uefi_lib.format_health()
        assert "EXPIRED" in out
        assert "expiring" in out
        assert "not_after=" in out
        assert "validity=unknown" in out
        assert "both db and dbx" in out

        empty = mock.Mock()
        empty.get_status.return_value = (0, 1)
        empty.export_esl.return_value = b""
        with mock.patch("utilities_common.uefi.get_backend", return_value=empty):
            out = uefi_lib.format_health()
        assert "User Mode but PK is empty" in out
        assert "User Mode but db is empty" in out
        assert "Findings:" in out


class TestShowConfigFailPaths(object):
    @mock.patch("utilities_common.uefi.read_status", return_value=(1, 0))
    def test_show_through_parent_groups(self, _status):
        result = CliRunner().invoke(show_security, ["uefi", "status"])
        assert result.exit_code == 0, result.output
        assert "Setup Mode" in result.output

    @mock.patch("utilities_common.uefi.enroll")
    def test_config_through_parent_groups(self, mock_enroll):
        result = CliRunner().invoke(
            config_security, ["uefi", "enroll", "-y", "kek", "/tmp/KEK.esl"])
        assert result.exit_code == 0, result.output
        mock_enroll.assert_called_once_with("kek", "/tmp/KEK.esl")

    @mock.patch("utilities_common.uefi.read_variables",
                side_effect=uefi_lib.UefiError("read failed"))
    def test_show_variables_error(self, _read):
        result = CliRunner().invoke(
            show_security.commands["uefi"].commands["variables"], ["all"])
        assert result.exit_code == 1
        assert "read failed" in result.output

    def test_show_inspect_compare_health_errors(self):
        path = _write_raw_esl()
        try:
            with mock.patch("utilities_common.uefi_parser.format_payload",
                            side_effect=uefi_lib.UefiError("bad inspect")):
                result = CliRunner().invoke(
                    show_security.commands["uefi"].commands["inspect"], [path])
                assert result.exit_code == 1
                assert "bad inspect" in result.output
            with mock.patch("utilities_common.uefi.format_compare",
                            side_effect=uefi_lib.UefiError("bad compare")):
                result = CliRunner().invoke(
                    show_security.commands["uefi"].commands["compare"], ["db", path])
                assert result.exit_code == 1
                assert "bad compare" in result.output
        finally:
            os.unlink(path)
        with mock.patch("utilities_common.uefi.format_health",
                        side_effect=uefi_lib.UefiError("bad health")):
            result = CliRunner().invoke(
                show_security.commands["uefi"].commands["health"])
            assert result.exit_code == 1
            assert "bad health" in result.output

    @mock.patch("utilities_common.uefi.append",
                side_effect=uefi_lib.UefiError("append failed"))
    def test_config_append_error(self, _append):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["append"],
            ["-y", "db", "/tmp/db.append.auth"])
        assert result.exit_code == 1
        assert "append failed" in result.output

    @mock.patch("utilities_common.uefi.update",
                side_effect=uefi_lib.UefiError("update failed"))
    def test_config_update_error(self, _update):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["update"],
            ["-y", "db", "/tmp/db.auth"])
        assert result.exit_code == 1
        assert "update failed" in result.output

    @mock.patch("utilities_common.uefi.unclaim",
                side_effect=uefi_lib.UefiError("unclaim failed"))
    def test_config_unclaim_error(self, _unclaim):
        result = CliRunner().invoke(
            config_security.commands["uefi"].commands["unclaim"],
            ["-y", "PK.empty.auth"])
        assert result.exit_code == 1
        assert "unclaim failed" in result.output
