"""Regression tests for reboot rollback and image-installation safety."""

import os
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from sonic_installer.main import sonic_installer
from utilities_common import image_disk_space


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("validation", ["reboot", "image_install"])
def test_ssh_disk_space_check_has_total_timeout(monkeypatch, caplog, validation):
    def timeout_command(cmd, **kwargs):
        assert cmd[0] == "ssh"
        assert kwargs["timeout"] == 60
        assert kwargs["timeout"] == image_disk_space.SSH_DISK_CHECK_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    monkeypatch.setattr(image_disk_space.subprocess, "check_output", timeout_command)
    monkeypatch.setattr(image_disk_space, "is_running_on_dpu", lambda: False)
    threshold_getter = (
        "get_min_free_disk_in_gb_for_reboot" if validation == "reboot"
        else "get_min_free_disk_in_gb_for_image"
    )
    monkeypatch.setattr(image_disk_space, threshold_getter, lambda *args: 4)

    assert image_disk_space.get_remote_dpu_free_disk_in_bytes("dpu0") is None
    check = getattr(image_disk_space, f"check_remote_dpu_{validation}_free_disk_space")
    assert check("dpu0") is False
    assert "Failed to get free disk space from dpu0: Disk-space command timed out" in caplog.text
    assert "Unable to determine free disk space for dpu0" in caplog.text


@pytest.mark.parametrize("dhcp_state", ["enabled", "disabled"])
@pytest.mark.parametrize("reboot_status", [0, 9])
def test_smart_switch_final_reboot_preserves_dhcp_state(tmp_path, dhcp_state, reboot_status):
    """Run final dispatch with real DHCP helpers and a harmless reboot executable."""
    reboot_script = (REPO_ROOT / "scripts" / "reboot").read_text()
    marker = 'if [[ "${BLOCKING_MODE}" != "yes" ]]; then'
    branch = marker + reboot_script.rsplit(marker, 1)[1]
    branch = branch.replace("/sbin/reboot", '"$MOCK_REBOOT"')
    event_file = tmp_path / "dhcp-events"
    mock_reboot = tmp_path / "reboot"
    mock_reboot.write_text('#!/bin/sh\necho "reboot:$*" >> "$EVENT_FILE"\nexit "$REBOOT_STATUS"\n')
    mock_reboot.chmod(0o755)
    shell = r'''
source "$1/reboot_smartswitch_helper"
EXIT_SUCCESS=0
EXIT_ERROR=1
smartswitch=True
REBOOT_DPU=no
BLOCKING_MODE=no
REBOOT_FLAGS=-f
debug() { :; }
preflight_all_dpus() { return 0; }
get_num_dpus() { echo 0; }
sonic-db-cli() { echo "$DHCP_STATE"; }
config() { echo "$3" >> "$EVENT_FILE"; }
rollback() {
    local reboot_status=$1
    echo "trap:$reboot_status:$MIDPLANE_DHCP_CHANGE_ATTEMPTED" >> "$EVENT_FILE"
    restore_midplane_dhcp_on_failure "$reboot_status"
}
trap 'rollback $?' EXIT
prepare_smartswitch_reboot || exit "$EXIT_ERROR"
'''
    result = subprocess.run(
        ["bash", "-c", shell + branch, "test-reboot", str(REPO_ROOT / "scripts")],
        env={**os.environ, "EVENT_FILE": str(event_file), "MOCK_REBOOT": str(mock_reboot),
             "REBOOT_STATUS": str(reboot_status), "DHCP_STATE": dhcp_state},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == reboot_status, result.stderr
    changed = dhcp_state == "enabled"
    expected = ["disable"] if changed else []
    expected += ["reboot:-f", f"trap:{reboot_status}:{'yes' if changed else 'no'}"]
    if changed and reboot_status != 0:
        expected.append("enable")
    assert event_file.read_text().splitlines() == expected


@pytest.mark.parametrize("reboot_status", [0, 9])
def test_non_smart_switch_final_reboot_keeps_exec(tmp_path, reboot_status):
    reboot_script = (REPO_ROOT / "scripts" / "reboot").read_text()
    marker = 'if [[ "${BLOCKING_MODE}" != "yes" ]]; then'
    branch = marker + reboot_script.rsplit(marker, 1)[1]
    branch = branch.replace("/sbin/reboot", '"$MOCK_REBOOT"')
    event_file = tmp_path / "events"
    mock_reboot = tmp_path / "reboot"
    mock_reboot.write_text('#!/bin/sh\necho "reboot:$*" >> "$EVENT_FILE"\nexit "$REBOOT_STATUS"\n')
    mock_reboot.chmod(0o755)
    shell = r'''
smartswitch=False
REBOOT_DPU=no
BLOCKING_MODE=no
REBOOT_FLAGS=-f
trap 'echo trap >> "$EVENT_FILE"' EXIT
'''
    result = subprocess.run(
        ["bash", "-c", shell + branch],
        env={**os.environ, "EVENT_FILE": str(event_file), "MOCK_REBOOT": str(mock_reboot),
             "REBOOT_STATUS": str(reboot_status)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == reboot_status, result.stderr
    assert event_file.read_text().splitlines() == ["reboot:-f"]


def test_installer_disk_failure_aborts_before_side_effects():
    bootloader = Mock()
    bootloader.get_binary_image_version.return_value = "SONiC-OS-test"
    bootloader.get_installed_images.return_value = []

    with (
        patch("sonic_installer.main.get_bootloader", return_value=bootloader),
        patch("sonic_installer.main.check_image_install_free_disk_space", return_value=False) as check,
        patch("sonic_installer.main.SWAPAllocator") as swap,
        patch("sonic_installer.main.migrate_sonic_packages") as migrate,
        patch("sonic_installer.main.update_sonic_environment") as update_environment,
        patch("sonic_installer.main.run_command") as run_command,
    ):
        result = CliRunner().invoke(sonic_installer.commands["install"], ["sonic.bin", "-y"])
        assert result.exit_code != 0
        assert isinstance(result.exception, SystemExit)
        assert "Insufficient free disk space" in result.output
        check.assert_called_once_with()
        swap.assert_not_called()
        swap.return_value.__enter__.assert_not_called()
        migrate.assert_not_called()
        update_environment.assert_not_called()
        run_command.assert_not_called()
        bootloader.install_image.assert_not_called()
        bootloader.set_default_image.assert_not_called()
