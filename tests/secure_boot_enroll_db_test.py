import ctypes
import datetime
import hashlib
import io
import os
import struct
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from sonic_installer import secure_boot_db as db
from sonic_installer import secure_boot_enroll_db as enroll
from sonic_installer import secure_boot_lock


@pytest.fixture(scope="module")
def authorities():
    result = {}
    for authority in ("PK", "KEK", "rogue"):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, authority)])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime(2024, 1, 1))
            .not_valid_after(datetime.datetime(2099, 1, 1))
            .sign(key, hashes.SHA256())
        )
        result[authority] = key, cert
    return result


def _esl(cert):
    entry = b"\0" * 16 + cert.public_bytes(serialization.Encoding.DER)
    return db.EFI_CERT_X509_GUID.bytes_le + struct.pack("<III", 28 + len(entry), 0, len(entry)) + entry


def _der_content(data):
    return data[2 + (data[1] & 0x7f if data[1] & 0x80 else 0):]


def _signed_auth(authority, *, attributes=db.DB_ATTR_APPEND, bare=False):
    key, cert = authority
    payload = _esl(cert)
    header = db.EfiAuthVariable2()
    header.timestamp.year, header.timestamp.month, header.timestamp.day = 2026, 1, 1
    content = (
        "db".encode("utf-16-le") + db.EFI_IMAGE_SECURITY_DATABASE_GUID.bytes_le
        + struct.pack("<I", attributes) + bytes(header.timestamp) + payload
    )
    signature = (
        pkcs7.PKCS7SignatureBuilder().set_data(content).add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])
    )
    if bare:
        signature = _der_content(_der_content(signature)[len(db.PKCS7_SIGNED_DATA_OID):])
    header.auth_info.length = ctypes.sizeof(db.WinCertificateUefiGuid) + len(signature)
    header.auth_info.revision = db.WIN_CERT_REVISION_2_0
    header.auth_info.cert_type = db.WIN_CERT_TYPE_EFI_GUID
    header.auth_info.cert_type_guid[:] = db.EFI_CERT_TYPE_PKCS7_GUID.bytes_le
    return bytes(header) + signature + payload


def _fs_zip(auth, *, compression=zipfile.ZIP_STORED):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=compression) as archive:
        if auth is not None:
            archive.writestr("boot/DB.auth", auth)
    return data.getvalue()


def _create_installer(path, auth=b"DB.auth", *, fs_zip=None, include_fs=True, second_auth=None, tar_mode="w"):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode=tar_mode) as archive:
        if include_fs:
            members = [_fs_zip(auth) if fs_zip is None else fs_zip]
            if second_auth is not None:
                members.append(_fs_zip(second_auth))
            for data in members:
                info = tarfile.TarInfo("installer/fs.zip")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    path.write_bytes(b"#!/bin/sh\nexit_marker\n" + payload.getvalue() + b"appended CMS signature")


@pytest.fixture
def env(tmp_path, monkeypatch, authorities):
    monkeypatch.setattr(secure_boot_lock, "LOCK_FILE", tmp_path / "installer.lock")
    host, efivars = tmp_path / "host", tmp_path / "efivars"
    host.mkdir()
    efivars.mkdir()
    for name in ("PK", "KEK", "db"):
        data = _esl(authorities[name if name != "db" else "PK"][1])
        (efivars / f"{name}-{db.VARIABLE_GUIDS[name]}").write_bytes(b"\0" * 4 + data)
    monkeypatch.setenv("SONIC_HOST_PATH", str(host))
    monkeypatch.setenv("SONIC_EFIVARS_DIR", str(efivars))
    monkeypatch.delenv("SONIC_DB_AUTH_DIR", raising=False)
    monkeypatch.setattr(enroll.os.path, "ismount", lambda path: True)
    config = db.Config.from_env(auth_dir=host / "db-auth")
    state = {
        "config": config, "image": tmp_path / "sonic.bin", "commands": [], "updates": [],
        "mount_result": 0, "update_result": 0, "missing_tool": None,
    }
    real_run = subprocess.run

    def run(cmd, **kwargs):
        state["commands"].append(cmd)
        if cmd[0] == state["missing_tool"]:
            raise FileNotFoundError(2, "No such file or directory", cmd[0])
        if cmd[0] == "sig-list-to-certs":
            # Each fixture ESL contains exactly one X.509 signature.
            Path(f"{cmd[2]}-0.der").write_bytes(Path(cmd[1]).read_bytes()[44:])
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[0] == "efi-updatevar":
            assert secure_boot_lock.current_lock_fd() is not None
            data = Path(cmd[-2]).read_bytes()
            persisted = config.auth_dir / f"DB-{hashlib.sha256(data).hexdigest()}.auth"
            assert persisted.read_bytes() == data
            state["updates"].append(cmd)
            return subprocess.CompletedProcess(cmd, state["update_result"])
        if cmd[0] in ("mount", "chattr"):
            return subprocess.CompletedProcess(cmd, state["mount_result"] if cmd[0] == "mount" else 1, "", "denied")
        assert cmd[0] == "openssl", f"unexpected external command: {cmd}"
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(db.subprocess, "run", run)
    _create_installer(state["image"], _signed_auth(authorities["PK"]))
    return state


@pytest.mark.parametrize("authority", ["PK", "KEK"])
@pytest.mark.parametrize("bare", [False, True])
def test_enrolls_authorized_append_updates(env, authorities, authority, bare):
    auth = _signed_auth(authorities[authority], bare=bare)
    _create_installer(env["image"], auth)
    assert enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert len(env["updates"]) == 1
    assert env["updates"][0][0:3] == ["efi-updatevar", "-a", "-f"]
    assert env["updates"][0][-1] == "db"
    assert any(cmd[0] == "chattr" for cmd in env["commands"])
    assert list(env["config"].auth_dir.glob("DB-*.auth"))[0].read_bytes() == auth
    assert not list(env["config"].host_path.glob(".secure_boot_enroll_db.*"))


@pytest.mark.parametrize("kind", [
    "unauthorized", "replace-only", "tampered", "empty-payload", "empty-signature", "truncated", "bad-length",
    "bad-revision", "bad-type", "bad-guid", "tampered-signature",
])
def test_rejects_invalid_auth_before_persistence_or_firmware_write(env, authorities, kind):
    auth = _signed_auth(
        authorities["rogue" if kind == "unauthorized" else "PK"],
        attributes=db.DB_ATTR_REPLACE if kind == "replace-only" else db.DB_ATTR_APPEND,
    )
    if kind == "tampered":
        auth = auth[:-1] + bytes([auth[-1] ^ 1])
    elif kind == "tampered-signature":
        header = db.EfiAuthVariable2.from_buffer_copy(auth)
        signature_end = ctypes.sizeof(db.EfiTime) + header.auth_info.length
        auth = auth[:signature_end - 1] + bytes([auth[signature_end - 1] ^ 1]) + auth[signature_end:]
    elif kind == "empty-payload":
        auth = auth[:-len(_esl(authorities["PK"][1]))]
    elif kind == "empty-signature":
        header = db.EfiAuthVariable2.from_buffer_copy(auth)
        header.auth_info.length = ctypes.sizeof(db.WinCertificateUefiGuid)
        auth = bytes(header) + _esl(authorities["PK"][1])
    elif kind in ("bad-revision", "bad-type", "bad-guid"):
        header = db.EfiAuthVariable2.from_buffer_copy(auth)
        if kind == "bad-revision":
            header.auth_info.revision = 0
        elif kind == "bad-type":
            header.auth_info.cert_type = 0
        else:
            header.auth_info.cert_type_guid[:] = db.EFI_CERT_X509_GUID.bytes_le
        auth = bytes(header) + auth[ctypes.sizeof(db.EfiAuthVariable2):]
    elif kind == "truncated":
        auth = auth[:20]
    elif kind == "bad-length":
        auth = auth[:16] + struct.pack("<I", len(auth) + 1) + auth[20:]
    _create_installer(env["image"], auth)
    with pytest.raises(db.ScriptError):
        enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert not env["updates"]
    assert not env["config"].auth_dir.exists()
    assert not list(env["config"].host_path.glob(".secure_boot_enroll_db.*"))


def test_enrollment_holds_lock_during_authentication_and_persistence(env, monkeypatch):
    operations = []

    def checked(name, original):
        def wrapper(*args, **kwargs):
            assert secure_boot_lock.current_lock_fd() is not None
            operations.append(name)
            return original(*args, **kwargs)
        return wrapper

    monkeypatch.setattr(db, "build_trusted_pem", checked("authorities", db.build_trusted_pem))
    monkeypatch.setattr(db, "verify_db_auth", checked("verify", db.verify_db_auth))
    monkeypatch.setattr(enroll, "persist_auth", checked("persist", enroll.persist_auth))
    assert enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert operations == ["authorities", "verify", "persist"]
    assert secure_boot_lock.current_lock_fd() is None


def test_check_only_does_not_validate_or_access_firmware(env, monkeypatch):
    _create_installer(env["image"], b"not an authenticated update")

    def unexpected_firmware_access(*args):
        pytest.fail("check mode must not access firmware or authenticate the update")

    monkeypatch.setattr(enroll, "ensure_efivars", unexpected_firmware_access)
    monkeypatch.setattr(db, "parse_auth", unexpected_firmware_access)
    assert enroll.enroll_db_certificate(env["image"], check_only=True, config=env["config"])
    assert not env["commands"]
    assert not env["config"].auth_dir.exists()


@pytest.mark.parametrize("kind", ["missing-auth", "empty-auth", "missing-zip", "empty-zip"])
@pytest.mark.parametrize("check_only", [False, True])
def test_missing_optional_payload_is_a_noop_except_in_check_mode(env, kind, check_only):
    _create_installer(
        env["image"], None if kind == "missing-auth" else b"",
        include_fs=kind != "missing-zip", fs_zip=b"" if kind == "empty-zip" else None,
    )
    assert enroll.enroll_db_certificate(
        env["image"], check_only=check_only, config=env["config"],
    ) is not check_only
    assert not env["commands"]
    assert not env["config"].auth_dir.exists()


def test_accepts_compressed_outer_tar(env, authorities):
    _create_installer(env["image"], _signed_auth(authorities["KEK"]), tar_mode="w:gz")
    assert enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert len(env["updates"]) == 1


def test_reads_only_first_matching_fs_zip(env):
    _create_installer(env["image"], None, second_auth=b"ignored")
    assert not enroll.enroll_db_certificate(env["image"], check_only=True, config=env["config"])
    assert not env["commands"]


@pytest.mark.parametrize("kind", ["header", "tar", "zip", "zip-deflate"])
def test_malformed_installer_reports_an_error(env, capsys, kind):
    if kind == "header":
        env["image"].write_bytes(b"not an installer")
    elif kind == "tar":
        env["image"].write_bytes(b"#!/bin/sh\nexit_marker\nnot a tar archive")
    elif kind == "zip-deflate":
        data = bytearray(_fs_zip(b"bundled auth", compression=zipfile.ZIP_DEFLATED))
        data[30 + len("boot/DB.auth")] = 0xff
        _create_installer(env["image"], fs_zip=data)
    else:
        _create_installer(env["image"], fs_zip=b"not a zip archive")
    assert enroll.main([str(env["image"])]) == 1
    assert "ERROR:" in capsys.readouterr().out
    assert not env["commands"]
    assert not env["config"].auth_dir.exists()


@pytest.mark.parametrize("authority", ["PK", "KEK"])
def test_unreadable_authority_fails_before_persistence(env, authority):
    (env["config"].efivars_dir / f"{authority}-{db.VARIABLE_GUIDS[authority]}").unlink()
    with pytest.raises(db.ScriptError, match=f"failed to read the UEFI {authority}"):
        enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert not env["updates"]
    assert not env["config"].auth_dir.exists()


def test_requires_at_least_one_enrolled_authority_certificate(env):
    for name in ("PK", "KEK"):
        (env["config"].efivars_dir / f"{name}-{db.VARIABLE_GUIDS[name]}").write_bytes(b"\0" * 4)
    with pytest.raises(db.ScriptError, match="no enrolled PK or KEK"):
        enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert not env["updates"]
    assert not env["config"].auth_dir.exists()


def test_pruning_does_not_inherit_enrollments_pk_authority(env, tmp_path, authorities):
    trusted = db.build_trusted_pem(env["config"], tmp_path)
    assert not db.verify_db_auth(
        db.parse_auth(_signed_auth(authorities["PK"])), db.DB_ATTR_APPEND, True, trusted, tmp_path / "prune",
    )


def test_reuses_identical_persisted_update_without_overwriting(env, capsys):
    assert enroll.main([str(env["image"])]) == 0
    persisted = next(env["config"].auth_dir.glob("DB-*.auth"))
    os.utime(persisted, (1, 1))
    assert enroll.main([str(env["image"])]) == 0
    assert persisted.stat().st_mtime == 1
    assert "not copying" in capsys.readouterr().out


def test_persistence_collision_prevents_firmware_write(env, authorities):
    auth = _signed_auth(authorities["PK"])
    _create_installer(env["image"], auth)
    env["config"].auth_dir.mkdir()
    persisted = env["config"].auth_dir / f"DB-{hashlib.sha256(auth).hexdigest()}.auth"
    persisted.write_bytes(b"different")
    with pytest.raises(db.ScriptError, match="different content"):
        enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert persisted.read_bytes() == b"different"
    assert not env["updates"]


def test_persistence_failure_prevents_firmware_write(env):
    env["config"].auth_dir.write_bytes(b"not a directory")
    with pytest.raises(OSError):
        enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert not env["updates"]


def test_mounts_efivarfs_when_not_already_mounted(env, monkeypatch):
    monkeypatch.setattr(enroll.os.path, "ismount", lambda path: False)
    assert enroll.enroll_db_certificate(env["image"], config=env["config"])
    assert env["commands"][0] == ["mount", "-t", "efivarfs", "efivarfs", str(env["config"].efivars_dir)]


def test_mount_failure_is_reported_without_persistence(env, monkeypatch, capsys):
    monkeypatch.setattr(enroll.os.path, "ismount", lambda path: False)
    env["mount_result"] = 1
    assert enroll.main([str(env["image"])]) == 1
    assert "failed to mount efivarfs" in capsys.readouterr().out
    assert not env["config"].auth_dir.exists()
    assert not env["updates"]


def test_unavailable_efivars_is_reported(env, capsys, monkeypatch):
    monkeypatch.setenv("SONIC_EFIVARS_DIR", str(env["config"].efivars_dir / "missing"))
    assert enroll.main([str(env["image"])]) == 1
    assert "efivars not available" in capsys.readouterr().out
    assert not env["commands"]


def test_firmware_failure_is_reported_and_authorized_update_is_retained(env, capsys):
    env["update_result"] = 1
    assert enroll.main([str(env["image"])]) == 1
    assert "failed to enroll db certificate" in capsys.readouterr().out
    assert len(list(env["config"].auth_dir.glob("DB-*.auth"))) == 1


@pytest.mark.parametrize("tool", ["sig-list-to-certs", "openssl", "efi-updatevar"])
def test_missing_utility_reports_execution_failure(env, capsys, tool):
    env["missing_tool"] = tool
    assert enroll.main([str(env["image"])]) == 1
    assert tool in capsys.readouterr().out
    assert not env["updates"]


def test_cli_check_and_host_relative_auth_default(env):
    assert enroll.main(["--check", str(env["image"])]) == 0
    assert not env["config"].auth_dir.exists()
    assert enroll.main([str(env["image"])]) == 0
    assert env["config"].auth_dir.parent == env["config"].host_path
    assert len(list(env["config"].auth_dir.glob("DB-*.auth"))) == 1


def test_explicit_auth_directory_override(env, monkeypatch, tmp_path):
    env["config"].auth_dir = tmp_path / "custom-auth"
    monkeypatch.setenv("SONIC_DB_AUTH_DIR", str(env["config"].auth_dir))
    assert enroll.main([str(env["image"])]) == 0
    assert len(list(env["config"].auth_dir.glob("DB-*.auth"))) == 1


def test_missing_image_reports_an_error(env, capsys):
    assert enroll.main([str(env["image"].with_name("missing"))]) == 1
    assert "not found" in capsys.readouterr().out
    assert not env["commands"]
