from unittest.mock import call

import pytest

from sonic_installer import secure_boot_db as db
from sonic_installer import secure_boot_keys as keys
from sonic_installer import secure_boot_lock


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(secure_boot_lock, "LOCK_FILE", tmp_path / "installer.lock")
    efivars = tmp_path / "efivars"
    efivars.mkdir()
    for name in ("KEK", "PK"):
        (efivars / f"{name}-{db.EFI_GLOBAL_VARIABLE_GUID}").write_bytes(b"\0" * 4)
    auth = tmp_path / "update.auth"
    auth.write_bytes(b"signed authenticated update")
    monkeypatch.setenv("SONIC_EFIVARS_DIR", str(efivars))
    monkeypatch.setattr(keys.os.path, "ismount", lambda path: True)
    state = {
        "config": db.Config.from_env(), "auth": auth, "calls": [],
        "status": {"mount": 0, "chattr": 0, "efi-updatevar": 0},
        "failed_tool": None, "error": None,
    }

    def run(cmd, **kwargs):
        assert secure_boot_lock.current_lock_fd() is not None
        assert cmd[0] in state["status"], f"unexpected external command: {cmd}"
        assert kwargs["timeout"] == 600
        state["calls"].append(call(cmd, **kwargs))
        if cmd[0] == state["failed_tool"]:
            raise state["error"]
        return keys.subprocess.CompletedProcess(cmd, state["status"][cmd[0]], "", "denied")

    monkeypatch.setattr(keys.subprocess, "run", run)
    return state


def _run(capsys, *args):
    try:
        code = keys.main(list(args))
    except SystemExit as e:
        code = e.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize("variable", ["KEK", "PK"])
def test_updates_key_directly_without_appending(env, capsys, variable):
    config = env["config"]
    assert keys.update_secure_boot_key(variable, env["auth"], config=config) is None
    assert env["calls"] == [
        call(
            ["chattr", "-i", str(config.efivars_dir / f"{variable}-{db.EFI_GLOBAL_VARIABLE_GUID}")],
            capture_output=True, text=True, timeout=600,
        ),
        call(["efi-updatevar", "-f", str(env["auth"]), variable], timeout=600),
    ]
    assert f"secure_boot_enroll_key: {variable} updated" in capsys.readouterr().out


def test_new_key_variable_does_not_need_immutable_flag_cleared(env):
    config = env["config"]
    (config.efivars_dir / f"PK-{db.EFI_GLOBAL_VARIABLE_GUID}").unlink()
    keys.update_secure_boot_key("PK", env["auth"], config=config)
    assert env["calls"] == [call(["efi-updatevar", "-f", str(env["auth"]), "PK"], timeout=600)]


@pytest.mark.parametrize("failure", ["nonzero-status", "missing-tool"])
def test_clearing_immutable_flag_remains_best_effort(env, failure):
    if failure == "nonzero-status":
        env["status"]["chattr"] = 1
    else:
        env["failed_tool"] = "chattr"
        env["error"] = FileNotFoundError("chattr")
    keys.update_secure_boot_key("KEK", env["auth"], config=env["config"])
    assert env["calls"][-1] == call(["efi-updatevar", "-f", str(env["auth"]), "KEK"], timeout=600)


def test_mounts_efivarfs_when_necessary(env, monkeypatch):
    monkeypatch.setattr(keys.os.path, "ismount", lambda path: False)
    keys.update_secure_boot_key("KEK", env["auth"], config=env["config"])
    assert env["calls"][0] == call(
        ["mount", "-t", "efivarfs", "efivarfs", str(env["config"].efivars_dir)],
        capture_output=True, text=True, timeout=600,
    )
    assert env["calls"][-1] == call(["efi-updatevar", "-f", str(env["auth"]), "KEK"], timeout=600)


def test_mount_failure_is_reported_before_any_key_update(env, monkeypatch, capsys):
    monkeypatch.setattr(keys.os.path, "ismount", lambda path: False)
    env["status"]["mount"] = 1
    code, out, _ = _run(capsys, "PK", str(env["auth"]))
    assert code == 1
    assert "failed to mount efivarfs" in out
    assert len(env["calls"]) == 1


@pytest.mark.parametrize("variable", ["db", "pk", "", "../PK"])
def test_api_rejects_unsupported_variables_before_running_commands(env, variable):
    with pytest.raises(keys.PreconditionError, match="unsupported variable"):
        keys.update_secure_boot_key(variable, env["auth"], config=env["config"])
    assert not env["calls"]


@pytest.mark.parametrize("args", [[], ["KEK"], ["db", "update.auth"]])
def test_cli_argument_errors_keep_exit_code_two(env, capsys, args):
    code, _, err = _run(capsys, *args)
    assert code == 2
    assert "usage:" in err
    assert not env["calls"]


@pytest.mark.parametrize("auth", ["missing.auth", "."])
def test_missing_or_nonfile_auth_keeps_exit_code_two(env, capsys, auth):
    code, out, _ = _run(capsys, "KEK", str(env["auth"].parent / auth))
    assert code == 2
    assert "auth file" in out and "not found" in out
    assert not env["calls"]


def test_unavailable_efivars_keeps_exit_code_two(env, monkeypatch, capsys):
    monkeypatch.setenv("SONIC_EFIVARS_DIR", str(env["auth"].parent / "missing-efivars"))
    code, out, _ = _run(capsys, "KEK", str(env["auth"]))
    assert code == 2
    assert "efivars not available" in out
    assert not env["calls"]


@pytest.mark.parametrize("variable", ["KEK", "PK"])
def test_firmware_rejection_keeps_exit_code_one(env, capsys, variable):
    env["status"]["efi-updatevar"] = 1
    code, out, _ = _run(capsys, variable, str(env["auth"]))
    assert code == 1
    assert f"failed to update {variable}" in out
    assert f"{variable} updated" not in out


@pytest.mark.parametrize("tool", ["mount", "efi-updatevar"])
@pytest.mark.parametrize("error", [
    FileNotFoundError("missing utility"),
    keys.subprocess.TimeoutExpired("firmware operation", 600),
])
def test_execution_failures_and_timeouts_are_reported(env, monkeypatch, capsys, tool, error):
    env["failed_tool"], env["error"] = tool, error
    monkeypatch.setattr(keys.os.path, "ismount", lambda path: tool != "mount")
    code, out, _ = _run(capsys, "PK", str(env["auth"]))
    assert code == 1
    assert f"ERROR: {error}" in out
    assert "PK updated" not in out
    if tool == "mount":
        assert len(env["calls"]) == 1


def test_direct_api_propagates_firmware_timeout(env):
    env["failed_tool"] = "efi-updatevar"
    env["error"] = keys.subprocess.TimeoutExpired("efi-updatevar", 600)
    with pytest.raises(keys.subprocess.TimeoutExpired):
        keys.update_secure_boot_key("PK", env["auth"], config=env["config"])


@pytest.mark.parametrize("variable", ["KEK", "PK"])
def test_cli_success_keeps_exit_code_zero(env, capsys, variable):
    code, out, _ = _run(capsys, variable, str(env["auth"]))
    assert code == 0
    assert f"{variable} updated" in out
    assert env["calls"][-1] == call(["efi-updatevar", "-f", str(env["auth"]), variable], timeout=600)
