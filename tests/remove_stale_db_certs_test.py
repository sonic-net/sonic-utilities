import datetime
import ctypes
import importlib.util
import shutil
import stat
import sys
import struct
import uuid
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

SCRIPT = Path(__file__).parents[1] / "scripts" / "remove_stale_db_certs.py"
spec = importlib.util.spec_from_file_location("remove_stale_db_certs", SCRIPT)
prune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prune)

X509_GUID = prune.EFI_CERT_X509_GUID.bytes_le
OWNER_GUID = uuid.UUID(int=1).bytes_le
ESL_HEADER_SIZE = 28
REAL_OPENSSL = shutil.which("openssl")

# Stand-in for efitools' sig-list-to-certs: writes <prefix>-<n>.der for each X.509 entry.
FAKE_SIG_LIST_TO_CERTS = """#!%s
import struct, sys
data, prefix, count, pos = open(sys.argv[1], "rb").read(), sys.argv[2], 0, 0
while pos < len(data):
    list_size, header_size, sig_size = struct.unpack_from("<III", data, pos + 16)
    for entry in range(pos + 28 + header_size, pos + list_size, sig_size):
        open("%%s-%%d.der" %% (prefix, count), "wb").write(data[entry + 16:entry + sig_size])
        count += 1
    pos += list_size
"""


def _make_cert(common_name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    return (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2024, 1, 1)).not_valid_after(datetime.datetime(2099, 1, 1))
        .sign(key, hashes.SHA256())
    )


@pytest.fixture(scope="module")
def certs():
    return _make_cert("CERT0"), _make_cert("CERT1")


def _der(cert):
    return cert.public_bytes(serialization.Encoding.DER)


def _esl(*certs):
    out = b""
    for cert in certs:
        entry = OWNER_GUID + _der(cert)
        out += X509_GUID + struct.pack("<III", ESL_HEADER_SIZE + len(entry), 0, len(entry)) + entry
    return out


def _auth(payload=b"", signed=b"CMS!"):
    header = prune.EfiAuthVariable2()
    header.auth_info.length = ctypes.sizeof(prune.WinCertificateUefiGuid) + len(signed)
    return bytes(header) + signed + payload


def _write_executable(path, contents):
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_var(efivars, name, data):
    (efivars / f"{name}-{prune.VARIABLE_GUIDS[name]}").write_bytes(b"\0" * prune.EFIVAR_ATTR_SIZE + data)


@pytest.fixture
def env(tmp_path, monkeypatch, certs):
    """A fake device: cert0 signs shim, cert1 signs the kernel and fallback loader; only cert0
    has a reinstall .auth, so the kernel and fallback loader are at risk."""
    cert0, cert1 = certs
    host, esp = tmp_path / "host", tmp_path / "esp" / "EFI"
    efivars, auth_dir = tmp_path / "efivars", tmp_path / "db-auth"
    fake_bin, signers = tmp_path / "bin", tmp_path / "signers"
    for d in (host / "image-test" / "boot", esp / "SONiC-OS", esp / "BOOT", efivars, auth_dir, fake_bin, signers):
        d.mkdir(parents=True)

    kernel = host / "image-test" / "boot" / "vmlinuz-test"
    shim = esp / "SONiC-OS" / "shimx64.efi"
    fallback = esp / "BOOT" / "BOOTX64.EFI"
    for binary in (kernel, shim, fallback):
        binary.write_text("binary")
    for binary, cert in ((shim, cert0), (kernel, cert1), (fallback, cert1)):
        (signers / binary.name).write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    _write_var(efivars, "db", _esl(cert0, cert1))
    _write_var(efivars, "KEK", _esl(cert0))
    (auth_dir / "DB-cert0.auth").write_bytes(_auth(_esl(cert0)))
    (auth_dir / "remove-all-db.auth").write_bytes(_auth())

    marker = tmp_path / "efi-updatevar-called"
    _write_executable(fake_bin / "sonic-installer", "#!/bin/sh\nprintf 'Current: SONiC-OS-test\\n"
                      "Next: SONiC-OS-test\\nAvailable:\\nSONiC-OS-test\\n'\n")
    _write_executable(fake_bin / "sbverify", f"""#!/bin/sh
if [ "$1" = "--list" ]; then
    [ "$(basename "$2")" != "$UNINSPECTABLE_BINARY" ]
    exit
fi
name="$(basename "$3")"
[ "$name" != "$UNSIGNED_BINARY" ] && cmp -s "$2" "{signers}/$name"
""")
    # The fake openssl rejects reinstall-* updates, as for a replace-only (non-append) .auth.
    _write_executable(fake_bin / "openssl", f'#!/bin/sh\n[ "$1" = x509 ] && exec "{REAL_OPENSSL}" "$@"\n'
                      'case "$*" in *reinstall-*) exit 1;; esac\nexit 0\n')
    _write_executable(fake_bin / "sig-list-to-certs", FAKE_SIG_LIST_TO_CERTS % sys.executable)
    _write_executable(fake_bin / "efi-updatevar", f'#!/bin/sh\nprintf called > "{marker}"\n')

    monkeypatch.setenv("PATH", f"{fake_bin}:/usr/bin:/bin")
    monkeypatch.setenv("SONIC_HOST_PATH", str(host))
    monkeypatch.setenv("SONIC_ESP_PATH", str(esp))
    monkeypatch.setenv("SONIC_OS_DIR", str(esp / "SONiC-OS"))
    monkeypatch.setenv("SONIC_EFIVARS_DIR", str(efivars))
    monkeypatch.setenv("SONIC_DB_AUTH_DIR", str(auth_dir))
    monkeypatch.setenv("UNSIGNED_BINARY", "-none-")
    monkeypatch.setenv("UNINSPECTABLE_BINARY", "-none-")
    monkeypatch.setattr(prune.os, "geteuid", lambda: 0)
    return {"marker": marker, "esp": esp, "auth_dir": auth_dir, "fake_bin": fake_bin, "certs": certs}


def _run(capsys, *argv):
    try:
        code = prune.main(list(argv))
    except SystemExit as e:
        code = e.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_plan_marks_installed_kernel_and_fallback_loader_as_essential(env, capsys):
    code, out, err = _run(capsys, "--plan")
    assert code == 0, err
    assert "essential_missing=2" in out
    assert "boot-chain binary would lose all db signers" in err
    assert "vmlinuz-test" in err and "BOOTX64.EFI" in err

    code, _, err = _run(capsys, "--commit")
    assert code == 2
    assert "Refusing to touch db" in err
    assert not env["marker"].exists()


def test_commit_rejects_remove_all_auth_with_nonempty_payload(env, capsys, monkeypatch):
    cert0, _ = env["certs"]
    (env["auth_dir"] / "remove-all-db.auth").write_bytes(_auth(_esl(cert0)))
    monkeypatch.setattr(prune, "check_boot_chain", lambda *a: 0)

    code, _, err = _run(capsys, "--commit")
    assert code == 2
    assert "remove-all .auth must contain an empty signature-list payload" in err
    assert not env["marker"].exists()


def test_commit_rejects_replace_only_reinstall_auth_before_db_update(env, capsys, monkeypatch):
    monkeypatch.setattr(prune, "check_boot_chain", lambda *a: 0)
    code, _, err = _run(capsys, "--commit")
    assert code == 2
    assert "not an authorized db append update" in err
    assert not env["marker"].exists()


def test_binary_without_any_db_signer_is_essential_and_blocks_commit(env, capsys, monkeypatch):
    monkeypatch.setenv("UNSIGNED_BINARY", "shimx64.efi")
    code, out, err = _run(capsys, "--plan")
    assert code == 0, err
    assert "essential_missing=3" in out
    assert "not signed by any db certificate" in err
    assert "shimx64.efi" in err

    code, _, _ = _run(capsys, "--commit")
    assert code == 2
    assert not env["marker"].exists()


def test_plan_discovers_efi_binaries_case_insensitively(env, capsys):
    (env["esp"] / "SONiC-OS" / "shimx64.efi").rename(env["esp"] / "SONiC-OS" / "ShimX64.EFI")
    (env["esp"] / "BOOT" / "grubnetx64.EFI").write_text("netboot")
    (env["esp"] / "SONiC-OS" / "mmx64.efi").write_text("mokmanager")

    code, out, err = _run(capsys, "--plan")
    assert code == 0, err
    # The fake sbverify only knows the lowercase name, so the renamed shim is reported as unsigned;
    # that it is reported at all shows it was discovered.
    assert "ShimX64.EFI" in err
    assert "grubnetx64" not in out + err and "mmx64" not in out + err


def test_plan_fails_closed_when_no_boot_loader_is_found(env, capsys):
    (env["esp"] / "SONiC-OS" / "shimx64.efi").unlink()
    code, _, err = _run(capsys, "--plan")
    assert code != 0
    assert "no boot loader found" in err
    assert not env["marker"].exists()


def test_uninspectable_kernel_is_reported_distinctly_and_blocks_commit(env, capsys, monkeypatch):
    monkeypatch.setenv("UNSIGNED_BINARY", "vmlinuz-test")
    monkeypatch.setenv("UNINSPECTABLE_BINARY", "vmlinuz-test")
    code, out, err = _run(capsys, "--plan")
    assert code == 0, err
    assert "essential_missing=2" in out
    assert "cannot inspect boot-chain binary" in err
    assert "vmlinuz-test" in err

    code, _, _ = _run(capsys, "--commit")
    assert code == 2
    assert not env["marker"].exists()


def test_plan_fails_closed_when_sonic_installer_lists_no_images(env, capsys):
    _write_executable(env["fake_bin"] / "sonic-installer", "#!/bin/sh\nexit 0\n")
    code, _, err = _run(capsys, "--plan")
    assert code != 0
    assert "returned no installed images" in err
    assert not env["marker"].exists()


def test_auto_skips_unsafe_plan_without_touching_db(env, capsys):
    code, _, err = _run(capsys, "--auto")
    assert code == 0, err
    assert "prune skipped (unsafe plan" in err
    assert not env["marker"].exists()


def test_auto_rejects_conflicting_options(env, capsys):
    code, _, err = _run(capsys, "--auto", "--plan")
    assert code == 2
    assert "--auto cannot be combined" in err


def test_allow_essential_missing_option_is_not_supported(env, capsys):
    code, _, err = _run(capsys, "--commit", "--allow-essential-missing")
    assert code == 2
    assert "unrecognized arguments: --allow-essential-missing" in err
    assert not env["marker"].exists()


def test_commit_refuses_when_boot_chain_binary_would_lose_its_signer(env, capsys):
    code, _, err = _run(capsys, "--commit")
    assert code == 2
    assert "a boot-chain binary would lose every db signer" in err
    assert not env["marker"].exists()


def test_esl_roundtrip_and_auth_parsing(env, tmp_path):
    cert0, cert1 = env["certs"]
    parsed = prune.load_certificates(_esl(cert0, cert1), tmp_path, "db")
    assert [c.fingerprint for c in parsed] == [cert.fingerprint(hashes.SHA256()).hex(":").upper()
                                               for cert in (cert0, cert1)]
    assert parsed[0].subject == "CN=CERT0" and parsed[0].expires.endswith("2099 GMT")
    assert prune.load_certificates(b"", tmp_path, "empty") == []
    update = prune.parse_auth(_auth(_esl(cert0)))
    assert update.signed_data == b"CMS!"
    assert update.payload == _esl(cert0)
    with pytest.raises(prune.ScriptError):
        prune.parse_auth(b"\0" * 10)


def test_pkcs7_wrapping_detection():
    wrapped = prune.der(prune.DER_SEQUENCE, prune.PKCS7_SIGNED_DATA_OID + b"\xa0\x00")
    assert prune.is_pkcs7_content_info(wrapped)
    assert not prune.is_pkcs7_content_info(prune.der(prune.DER_SEQUENCE, b"\x02\x01\x01"))
    assert prune.der(0x04, b"x" * 300)[:4] == b"\x04\x82\x01\x2c"
