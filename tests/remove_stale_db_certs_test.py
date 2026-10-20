import datetime
import ctypes
import shutil
import stat
import sys
import struct
import uuid
from types import ModuleType
from unittest.mock import Mock, call

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from sonic_installer import secure_boot_db as prune

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
def bootloader(monkeypatch):
    module = ModuleType("sonic_installer.bootloader")
    module.get_bootloader = Mock()
    module.get_bootloader.return_value.get_installed_images.return_value = ["SONiC-OS-test"]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module.get_bootloader


@pytest.fixture
def env(tmp_path, monkeypatch, certs, bootloader):
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


@pytest.fixture
def safe_updates(env, monkeypatch):
    config = prune.Config.from_env()
    cert0, cert1 = env["certs"]
    _write_var(config.efivars_dir, "db", _esl(cert0, cert1, _make_cert("STALE")))
    (env["auth_dir"] / "DB-cert1.auth").write_bytes(_auth(_esl(cert1)))
    _write_executable(env["fake_bin"] / "openssl",
                      f'#!/bin/sh\n[ "$1" = x509 ] && exec "{REAL_OPENSSL}" "$@"\nexit 0\n')
    monkeypatch.setenv("FAIL_AUTH", "")
    db = config.efivars_dir / f"db-{prune.VARIABLE_GUIDS['db']}"
    payload_offset = ctypes.sizeof(prune.EfiAuthVariable2) + len(b"CMS!")
    _write_executable(env["fake_bin"] / "efi-updatevar", f"""#!{sys.executable}
import os, sys
from pathlib import Path
auth = Path(sys.argv[sys.argv.index("-f") + 1])
with Path({str(env["marker"])!r}).open("a") as log:
    log.write(auth.name + "\\n")
if auth.name == os.environ.get("FAIL_AUTH"):
    sys.exit(1)
db = Path({str(db)!r})
previous = db.read_bytes()[4:] if "-a" in sys.argv else b""
db.write_bytes(bytes(4) + previous + auth.read_bytes()[{payload_offset}:])
""")
    return config


def test_analyzed_plan_exposes_boot_chain_safety(env, tmp_path):
    config = prune.Config.from_env()
    plan = prune.analyze(config, tmp_path, images=["SONiC-OS-test"])
    assert plan.boot_critical_dir == config.sonic_os_dir
    assert set(plan.boot_critical_binaries) == {
        config.host_path / "image-test" / "boot" / "vmlinuz-test",
        config.sonic_os_dir / "shimx64.efi",
        config.esp_path / "BOOT" / "BOOTX64.EFI",
    }
    assert set(plan.records) == set(plan.boot_critical_binaries)
    assert plan.boot_critical_binaries_at_risk == 2
    assert plan.boot_chain_at_risk is True
    plan.boot_critical_binaries_at_risk = 0
    assert plan.boot_chain_at_risk is False


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


def test_plan_does_not_check_tool_availability(env, capsys, monkeypatch):
    def unexpected_tool_check(tool):
        pytest.fail(f"unexpected tool availability check: {tool}")

    monkeypatch.setattr(shutil, "which", unexpected_tool_check)
    code, out, err = _run(capsys, "--plan")
    assert code == 0, err
    assert "Plan only - no changes made." in out
    assert not env["marker"].exists()


@pytest.mark.parametrize("append", [False, True])
@pytest.mark.parametrize("chattr_status,update_status", [(0, 0), (1, 0), (0, 1)])
def test_update_db_calls_tools_directly(env, monkeypatch, append, chattr_status, update_status):
    config = prune.Config.from_env(None, None)
    auth = env["auth_dir"] / "DB-cert0.auth"
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        status = chattr_status if cmd[0] == "chattr" else update_status
        return prune.subprocess.CompletedProcess(cmd, status)

    def unexpected_tool_check(tool):
        pytest.fail(f"unexpected tool availability check: {tool}")

    monkeypatch.setattr(shutil, "which", unexpected_tool_check)
    monkeypatch.setattr(prune.subprocess, "run", run)
    assert prune.update_db(config, auth, append) == (update_status == 0)
    assert calls == [
        ["chattr", "-i", str(config.efivars_dir / f"db-{prune.VARIABLE_GUIDS['db']}")],
        ["efi-updatevar"] + (["-a"] if append else []) + ["-f", str(auth), "db"],
    ]


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


def test_direct_call_uses_supplied_images_without_querying_bootloader(env, monkeypatch, bootloader):
    monkeypatch.setattr(prune, "installed_images", Mock(side_effect=AssertionError("unexpected image discovery")))
    assert prune.prune_db_certificates(
        prune.Config.from_env(), images=["SONiC-OS-test"], plan_only=True,
    ) == 0
    assert not env["marker"].exists()
    bootloader.assert_not_called()


def test_direct_call_rejects_empty_image_list(env):
    with pytest.raises(prune.ScriptError, match="returned no installed images"):
        prune.prune_db_certificates(prune.Config.from_env(), images=[], auto=True)
    assert not env["marker"].exists()


def test_direct_call_rejects_conflicting_options(env):
    with pytest.raises(prune.ScriptError, match="--auto cannot be combined with --plan"):
        prune.prune_db_certificates(prune.Config.from_env(), plan_only=True, auto=True)
    assert not env["marker"].exists()


def test_auto_skips_when_no_certificates_are_stale(env, monkeypatch, capsys):
    plan = Mock(used=[Mock()], missing=[], boot_chain_at_risk=False, drop=[])
    monkeypatch.setattr(prune, "analyze", Mock(return_value=plan))
    apply = Mock()
    monkeypatch.setattr(prune, "apply_plan", apply)
    assert prune.prune_db_certificates(prune.Config.from_env(), auto=True) == 0
    assert "No stale db certificates" in capsys.readouterr().out
    apply.assert_not_called()
    assert not env["marker"].exists()


@pytest.mark.parametrize("verbose", [False, True])
def test_auto_validates_before_updates_and_keeps_default_output_concise(env, monkeypatch, capsys, verbose):
    config = prune.Config.from_env()
    auth = env["auth_dir"] / "DB-cert0.auth"
    kernel = config.host_path / "image-test" / "boot" / "vmlinuz-test"
    cert = config.auth_dir / "cert.pem"
    plan = Mock(
        used=[Mock()], missing=[], boot_chain_at_risk=False, drop=[Mock()],
        selected_auths=[auth], boot_critical_binaries=[kernel],
    )
    monkeypatch.setattr(prune, "analyze", Mock(return_value=plan))
    print_plan = Mock()
    monkeypatch.setattr(prune, "print_plan", print_plan)
    operations = Mock()
    operations.update.return_value = True
    operations.read.return_value = [Mock(pem=cert)]
    operations.verify.return_value = True
    monkeypatch.setattr(prune, "validate_updates", operations.validate)
    monkeypatch.setattr(prune, "update_db", operations.update)
    monkeypatch.setattr(prune, "read_efi_certificates", operations.read)
    monkeypatch.setattr(prune, "succeeds", operations.verify)
    assert prune.prune_db_certificates(config, auto=True, verbose=verbose) == 0
    assert [item[0] for item in operations.mock_calls] == ["validate", "update", "update", "read", "verify"]
    assert operations.update.call_args_list == [
        call(config, config.remove_all_auth, append=False), call(config, auth, append=True),
    ]
    out = capsys.readouterr().out
    assert "Pruning 1 stale" in out and "Done: db reset" in out
    assert ("verifies against the new db" in out) == verbose
    assert ("Reinstalling" in out) == verbose
    assert print_plan.call_count == int(verbose)


@pytest.mark.parametrize("error", [
    FileNotFoundError("sig-list-to-certs"), prune.subprocess.TimeoutExpired("openssl", 600),
])
def test_cli_reports_command_failures(env, monkeypatch, capsys, error):
    monkeypatch.setattr(prune, "analyze", Mock(side_effect=error))
    code, _, err = _run(capsys, "--plan")
    assert code == 2
    assert str(error) in err
    assert not env["marker"].exists()


def test_cli_passes_options_to_importable_api(tmp_path, monkeypatch):
    api = Mock(return_value=0)
    monkeypatch.setattr(prune, "prune_db_certificates", api)
    auth_dir, remove_all = tmp_path / "auth", tmp_path / "remove-all.auth"
    assert prune.main(["--auth-dir", str(auth_dir), "--remove-all", str(remove_all), "--commit", "-v"]) == 0
    api.assert_called_once()
    assert api.call_args.args[0].auth_dir == auth_dir
    assert api.call_args.args[0].remove_all_auth == remove_all
    assert api.call_args.kwargs == {"commit": True, "plan_only": False, "auto": False, "verbose": True}


def test_installed_images_uses_bootloader_without_subprocesses(bootloader, monkeypatch):
    images = ["SONiC-OS-z", "SONiC-OS-a"]
    bootloader.return_value.get_installed_images.return_value = images
    monkeypatch.setattr(prune, "run", Mock(side_effect=AssertionError("unexpected subprocess")))
    assert prune.installed_images() is images
    bootloader.assert_called_once_with()
    bootloader.return_value.get_installed_images.assert_called_once_with()


@pytest.mark.parametrize("mode", ["--plan", "--commit", "--auto"])
@pytest.mark.parametrize("failure", ["detect", "query", "empty"])
def test_cli_refuses_pruning_when_bootloader_image_discovery_fails(env, bootloader, capsys, mode, failure):
    if failure == "detect":
        bootloader.side_effect = RuntimeError("Bootloader could not be detected")
        message = "Bootloader could not be detected"
    elif failure == "query":
        bootloader.return_value.get_installed_images.side_effect = OSError("unreadable boot config")
        message = "unreadable boot config"
    else:
        bootloader.return_value.get_installed_images.return_value = []
        message = "bootloader returned no installed images"
    code, _, err = _run(capsys, mode)
    assert code == 2
    assert message in err
    assert "refusing to prune" in err
    assert not env["marker"].exists()


def test_read_commands_are_bounded_but_firmware_writes_are_not(env, monkeypatch):
    run = Mock(return_value=prune.subprocess.CompletedProcess(["openssl"], 0))
    monkeypatch.setattr(prune.subprocess, "run", run)
    prune.run(["openssl"], stdin=prune.subprocess.DEVNULL)
    run.assert_called_once_with(
        ["openssl"], capture_output=True, text=True, timeout=prune.COMMAND_TIMEOUT_SECS,
        stdin=prune.subprocess.DEVNULL,
    )
    run.reset_mock()
    auth = env["auth_dir"] / "DB-cert0.auth"
    assert prune.update_db(prune.Config.from_env(), auth, append=True)
    run.assert_called_with(["efi-updatevar", "-a", "-f", str(auth), "db"])


@pytest.mark.parametrize("mode", ["--commit", "--auto"])
def test_safe_pruning_restores_all_signers_before_success(env, safe_updates, capsys, mode):
    code, out, err = _run(capsys, mode)
    assert code == 0, err
    assert env["marker"].read_text().splitlines() == [
        "remove-all-db.auth", "DB-cert0.auth", "DB-cert1.auth",
    ]
    assert prune.read_efi_variable(safe_updates, "db") == _esl(*env["certs"])
    assert "Done: db reset to 2 image-signing certificate(s)" in out
    assert "DO NOT REBOOT" not in err


@pytest.mark.parametrize("mode", ["--commit", "--auto"])
def test_failed_append_restores_other_signers_and_warns_against_reboot(env, safe_updates, monkeypatch, capsys, mode):
    monkeypatch.setenv("FAIL_AUTH", "DB-cert0.auth")
    code, out, err = _run(capsys, mode)
    assert code == 2
    assert env["marker"].read_text().splitlines() == [
        "remove-all-db.auth", "DB-cert0.auth", "DB-cert1.auth",
    ]
    assert prune.read_efi_variable(safe_updates, "db") == _esl(env["certs"][1])
    assert "failed to append" in err and "DO NOT REBOOT" in err
    assert "Done:" not in out


@pytest.mark.parametrize("error", [OSError("cannot start writer"), prune.subprocess.TimeoutExpired("writer", 600)])
def test_append_exception_does_not_abandon_other_reinstalls(env, safe_updates, monkeypatch, capsys, error):
    update = prune.update_db

    def fail_first_append(config, auth, append):
        if auth.name == "DB-cert0.auth":
            raise error
        return update(config, auth, append)

    monkeypatch.setattr(prune, "update_db", fail_first_append)
    code, out, err = _run(capsys, "--auto")
    assert code == 2
    assert prune.read_efi_variable(safe_updates, "db") == _esl(env["certs"][1])
    assert str(error) in err and "DO NOT REBOOT" in err
    assert "Done:" not in out


@pytest.mark.parametrize("error", [
    OSError("cannot read updated db"), prune.subprocess.TimeoutExpired("verification", 600),
    KeyboardInterrupt(), SystemExit(143), RuntimeError("unexpected verification failure"),
])
def test_post_write_failure_preserves_error_and_warns_against_reboot(
        env, safe_updates, monkeypatch, capsys, error):
    read = prune.read_efi_certificates

    def fail_readback(*args, **kwargs):
        if args[2:] == ("db", "new-db"):
            raise error
        return read(*args, **kwargs)

    monkeypatch.setattr(prune, "read_efi_certificates", fail_readback)
    with pytest.raises(type(error)) as caught:
        prune.prune_db_certificates(safe_updates, auto=True)
    assert caught.value is error
    assert prune.read_efi_variable(safe_updates, "db") == _esl(*env["certs"])
    captured = capsys.readouterr()
    assert "DO NOT REBOOT" in captured.err
    assert "Done:" not in captured.out


@pytest.mark.parametrize("append", [False, True])
def test_firmware_write_outlives_read_command_deadline(env, monkeypatch, append):
    _write_executable(env["fake_bin"] / "efi-updatevar", f"""#!{sys.executable}
import time
from pathlib import Path
time.sleep(0.15)
Path({str(env["marker"])!r}).write_text("completed")
""")
    monkeypatch.setattr(prune, "COMMAND_TIMEOUT_SECS", 0.03)
    monkeypatch.setattr(prune, "succeeds", Mock(return_value=True))
    assert prune.update_db(prune.Config.from_env(), env["auth_dir"] / "DB-cert0.auth", append)
    assert env["marker"].read_text() == "completed"


@pytest.mark.parametrize("append", [False, True])
def test_chattr_timeout_does_not_prevent_firmware_update(env, monkeypatch, capsys, append):
    monkeypatch.setattr(prune, "succeeds", Mock(side_effect=prune.subprocess.TimeoutExpired("chattr", 600)))
    run = Mock(return_value=prune.subprocess.CompletedProcess(["efi-updatevar"], 0))
    monkeypatch.setattr(prune.subprocess, "run", run)
    assert prune.update_db(prune.Config.from_env(), env["auth_dir"] / "DB-cert0.auth", append)
    assert "timeout" not in run.call_args.kwargs
    assert "attempting the firmware update" in capsys.readouterr().err


def test_validation_timeout_does_not_warn_of_firmware_changes(env, safe_updates, monkeypatch, capsys):
    monkeypatch.setattr(prune, "validate_updates", Mock(side_effect=prune.subprocess.TimeoutExpired("openssl", 600)))
    code, _, err = _run(capsys, "--auto")
    assert code == 2
    assert "timed out" in err
    assert "DO NOT REBOOT" not in err
    assert not env["marker"].exists()


def test_sigterm_during_updates_warns_and_restores_signal_handler(env, safe_updates, monkeypatch, capsys):
    monkeypatch.setattr(prune.signal, "getsignal", Mock(return_value=prune.signal.SIG_DFL))
    handler = Mock()
    monkeypatch.setattr(prune.signal, "signal", handler)
    update = prune.update_db

    def terminate_after_wipe(config, auth, append):
        result = update(config, auth, append)
        handler.call_args.args[1](prune.signal.SIGTERM, None)
        return result

    monkeypatch.setattr(prune, "update_db", terminate_after_wipe)
    with pytest.raises(SystemExit) as error:
        prune.prune_db_certificates(safe_updates, auto=True)
    assert error.value.code == 143
    assert prune.read_efi_variable(safe_updates, "db") == b""
    assert "DO NOT REBOOT" in capsys.readouterr().err
    assert handler.call_count == 2
    handler.assert_called_with(prune.signal.SIGTERM, prune.signal.SIG_DFL)


def test_pruning_preserves_existing_signal_handler(safe_updates, monkeypatch):
    monkeypatch.setattr(prune.signal, "getsignal", Mock(return_value=prune.signal.SIG_IGN))
    handler = Mock()
    monkeypatch.setattr(prune.signal, "signal", handler)
    assert prune.prune_db_certificates(safe_updates, auto=True) == 0
    handler.assert_not_called()


def test_pruning_can_run_outside_the_main_thread(safe_updates, monkeypatch):
    monkeypatch.setattr(prune.threading, "current_thread", Mock(return_value=object()))
    handler = Mock()
    monkeypatch.setattr(prune.signal, "signal", handler)
    assert prune.prune_db_certificates(safe_updates, auto=True) == 0
    handler.assert_not_called()
