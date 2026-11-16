"""Exercise installer error propagation with every firmware operation mocked."""
from contextlib import contextmanager, nullcontext
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from sonic_installer import main as installer
from sonic_installer import secure_boot_db as prune


@pytest.fixture
def reset_env(tmp_path, monkeypatch):
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    auths = [auth_dir / "first.auth", auth_dir / "second.auth"]
    for auth in auths:
        auth.write_bytes(b"inert mocked update")
    config = prune.Config(tmp_path, tmp_path, tmp_path, tmp_path, auth_dir, auth_dir / "remove-all.auth")
    cert = prune.DbCert(0, tmp_path / "signer.pem", "SIGNER", "signer", "2099")
    unknown = prune.DbCert(1, tmp_path / "unknown.pem", "OTHER", "unknown trust", "2099")
    kernel = tmp_path / "vmlinuz-test"
    plan = prune.Plan("enabled", [cert, unknown], tmp_path, {kernel: [cert]}, [kernel],
                      [cert], [unknown], {"SIGNER": auths[0]}, auths, [], 0)
    bootloader = Mock()
    bootloader.get_installed_images.side_effect = [["cur", "old"], ["cur"]]
    bootloader.get_current_image.return_value = "cur"
    bootloader.get_next_image.return_value = "cur"
    monkeypatch.setattr(installer, "get_bootloader", Mock(return_value=bootloader))
    monkeypatch.setattr(installer.log, "log", Mock())
    monkeypatch.setattr(prune.os, "geteuid", lambda: 0)
    monkeypatch.setattr(prune.Config, "from_env", Mock(return_value=config))
    monkeypatch.setattr(prune, "ensure_efivars", Mock())
    monkeypatch.setattr(prune, "secure_boot_state", Mock(return_value="enabled"))
    analyze = Mock(return_value=plan)
    validate = Mock()
    monkeypatch.setattr(prune, "analyze", analyze)
    monkeypatch.setattr(prune, "validate_updates", validate)
    monkeypatch.setattr(prune, "defer_cancellation", nullcontext)
    monkeypatch.setattr(prune, "read_efi_certificates", Mock(return_value=[cert]))
    monkeypatch.setattr(prune, "succeeds", Mock(return_value=True))
    monkeypatch.setattr(prune.subprocess, "run", Mock(side_effect=AssertionError("real subprocess forbidden")))
    monkeypatch.setattr(prune.subprocess, "Popen", Mock(side_effect=AssertionError("real subprocess forbidden")))
    return config, plan, bootloader, analyze, validate


def _invoke(command):
    args = ["remove", "-y", "old"] if command == "remove" else ["cleanup", "-y"]
    return CliRunner().invoke(installer.sonic_installer, args)


@pytest.mark.parametrize("command", ["remove", "cleanup"])
def test_automatic_removal_preserves_unknown_trust(reset_env, monkeypatch, command):
    _, _, bootloader, analyze, validate = reset_env
    update = Mock(side_effect=AssertionError("automatic firmware write forbidden"))
    monkeypatch.setattr(prune, "update_db", update)
    result = _invoke(command)
    assert result.exit_code == 0, (result.output, result.exception)
    bootloader.remove_image.assert_called_once_with("old")
    analyze.assert_called_once()
    validate.assert_not_called()
    update.assert_not_called()
    assert "cannot establish ownership" in result.output
    assert "db is unchanged" in result.output


@pytest.mark.parametrize("command", ["remove", "cleanup"])
@pytest.mark.parametrize("phase", [
    "validation", "cancellation-setup", "wipe-false", "wipe-error", "append", "readback", "verify",
])
def test_installer_distinguishes_preflight_from_attempted_updates(reset_env, monkeypatch, command, phase):
    config, plan, bootloader, _, validate = reset_env
    # Automatic mode now preserves db. Exercise its defensive error handling with
    # the real explicit-reset worker, so a future writer cannot hide mutation errors.
    reset = prune.prune_db_certificates

    def explicit_reset(config, *, images, auto):
        assert auto
        return reset(config, images=images, commit=True)

    monkeypatch.setattr(prune, "prune_db_certificates", explicit_reset)
    operations = []

    def update(config, auth, append):
        operations.append((auth, append))
        if not append and phase == "wipe-false":
            return False
        if not append and phase == "wipe-error":
            raise OSError("mock partial wipe error")
        if auth == plan.selected_auths[0] and phase == "append":
            raise OSError("mock append failure")
        return True

    monkeypatch.setattr(prune, "update_db", update)
    if phase == "validation":
        validate.side_effect = prune.ScriptError("mock invalid auth")
    elif phase == "cancellation-setup":
        @contextmanager
        def failed_setup():
            raise OSError("mock cancellation setup failure")
            yield

        monkeypatch.setattr(prune, "defer_cancellation", failed_setup)
    elif phase == "readback":
        monkeypatch.setattr(prune, "read_efi_certificates", Mock(side_effect=OSError("mock failed readback")))
    elif phase == "verify":
        monkeypatch.setattr(prune, "succeeds", Mock(return_value=False))
    result = _invoke(command)
    bootloader.remove_image.assert_called_once_with("old")
    if phase in ("validation", "cancellation-setup"):
        assert result.exit_code == 0, (result.output, result.exception)
        assert operations == []
        assert ("mock invalid auth" if phase == "validation" else "mock cancellation setup failure") in result.output
        assert "DO NOT REBOOT" not in result.output
    else:
        assert result.exit_code == 1, (result.output, result.exception)
        assert operations == [(config.remove_all_auth, False)] + [(a, True) for a in plan.selected_auths]
        assert "DO NOT REBOOT" in result.output
        assert "Error: Secure Boot db update failed" in result.output
        assert "Done:" not in result.output
