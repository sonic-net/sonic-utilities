import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
REBOOT_SCRIPT = SCRIPTS_DIR / "reboot"
SMARTSWITCH_HELPER = SCRIPTS_DIR / "reboot_smartswitch_helper"


def _write_executable(path, body):
    path.write_text("#!/bin/bash\n{}\n".format(body))
    path.chmod(0o700)


@pytest.fixture
def reboot_sandbox(tmp_path):
    """Build a PATH sandbox that stops the copied script after its pre-checks."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    device_dir = tmp_path / "device"
    platform_dir = device_dir / "test-platform"
    platform_dir.mkdir(parents=True)
    call_log = tmp_path / "calls.log"

    script = REBOOT_SCRIPT.read_text()
    replacements = {
        'DEVPATH="/usr/share/sonic/device"': 'DEVPATH="{}"'.format(device_dir),
        "VMCORE_FILE=/proc/vmcore": "VMCORE_FILE={}".format(tmp_path / "no-vmcore"),
        'FIRMWARE_AU_STATUS_DIR="/tmp/firmwareupdate"': (
            'FIRMWARE_AU_STATUS_DIR="{}"'.format(tmp_path / "firmwareupdate")
        ),
        'REBOOT_CONFIG_FILE="/etc/sonic/reboot.conf"': (
            'REBOOT_CONFIG_FILE="{}"'.format(tmp_path / "reboot.conf")
        ),
        'if [[ "$EUID" -ne 0 ]]; then': (
            'if [[ "$EUID" -ne 0 && "${REBOOT_TEST_ALLOW_NON_ROOT}" != "yes" ]]; then'
        ),
        "setup_reboot_variables\nreboot_pre_check\n": (
            "setup_reboot_variables\n"
            "reboot_pre_check\n"
            "exit 0\n"
        ),
    }
    for old, new in replacements.items():
        assert script.count(old) == 1
        script = script.replace(old, new)

    test_reboot = bin_dir / "reboot-under-test"
    test_reboot.write_text(script)
    test_reboot.chmod(0o700)
    shutil.copy2(SMARTSWITCH_HELPER, bin_dir / SMARTSWITCH_HELPER.name)

    _write_executable(
        bin_dir / "sonic-cfggen",
        """case "$*" in
  *DEVICE_METADATA.localhost.platform*) echo test-platform ;;
esac""",
    )
    _write_executable(
        bin_dir / "python3",
        """case "$*" in
  *get_num_dpus*) echo 0 ;;
  *is_dpu*) echo "${REBOOT_TEST_IS_DPU:-False}" ;;
  *) echo False ;;
esac""",
    )
    _write_executable(
        bin_dir / "sonic-installer",
        """case "$1" in
  list)
    echo "sonic-installer list" >> "$REBOOT_TEST_CALL_LOG"
    echo "Next: SONiC-OS-test"
    ;;
  verify-next-image)
    echo "sonic-installer verify-next-image" >> "$REBOOT_TEST_CALL_LOG"
    echo "${REBOOT_TEST_VERIFY_MESSAGE:-}"
    exit "${REBOOT_TEST_VERIFY_RC:-0}"
    ;;
esac""",
    )
    _write_executable(
        platform_dir / "platform_reboot_pre_check",
        'echo "platform-pre-check" >> "$REBOOT_TEST_CALL_LOG"\n'
        'exit "$REBOOT_TEST_PRECHECK_RC"',
    )
    _write_executable(
        bin_dir / "logger",
        "exit 0",
    )
    _write_executable(bin_dir / "logname", "echo root")
    for command in ("touch", "rm"):
        _write_executable(bin_dir / command, "exit 0")

    env = os.environ.copy()
    env.update(
        {
            "PATH": "{}:{}".format(bin_dir, env["PATH"]),
            "REBOOT_TEST_ALLOW_NON_ROOT": "yes",
            "REBOOT_TEST_CALL_LOG": str(call_log),
        }
    )
    return test_reboot, call_log, env


@pytest.mark.parametrize(
    "arguments,is_dpu",
    [([], False), (["-p"], True)],
    ids=["plain-reboot", "dpu-pre-shutdown"],
)
def test_platform_pre_check_failure_propagates_original_rc(
        reboot_sandbox, arguments, is_dpu):
    test_reboot, call_log, env = reboot_sandbox
    env["REBOOT_TEST_IS_DPU"] = str(is_dpu)
    env["REBOOT_TEST_PRECHECK_RC"] = "3"

    result = subprocess.run(
        [str(test_reboot)] + arguments,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    calls = call_log.read_text().splitlines()
    assert result.returncode == 3
    assert "Platform reboot pre-check failed: rc=3" in result.stdout
    assert "platform-pre-check" in calls
    assert "sonic-installer verify-next-image" not in calls


@pytest.mark.parametrize(
    "arguments,is_dpu",
    [([], False), (["-p"], True)],
    ids=["plain-reboot", "dpu-pre-shutdown"],
)
def test_next_image_verification_failure_uses_existing_exit_code(
        reboot_sandbox, arguments, is_dpu):
    test_reboot, call_log, env = reboot_sandbox
    env["REBOOT_TEST_IS_DPU"] = str(is_dpu)
    env["REBOOT_TEST_PRECHECK_RC"] = "0"
    env["REBOOT_TEST_VERIFY_RC"] = "7"
    env["REBOOT_TEST_VERIFY_MESSAGE"] = "next image validation failed"

    result = subprocess.run(
        [str(test_reboot)] + arguments,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    calls = call_log.read_text().splitlines()
    assert result.returncode == 21
    assert (
        "Failed to verify next image: next image validation failed" in result.stdout
    )
    assert calls.index("platform-pre-check") < calls.index(
        "sonic-installer verify-next-image"
    )


@pytest.mark.parametrize(
    "arguments,is_dpu",
    [([], False), (["-p"], True)],
    ids=["plain-reboot", "dpu-pre-shutdown"],
)
def test_platform_pre_check_success_keeps_existing_flow(
        reboot_sandbox, arguments, is_dpu):
    test_reboot, call_log, env = reboot_sandbox
    env["REBOOT_TEST_IS_DPU"] = str(is_dpu)
    env["REBOOT_TEST_PRECHECK_RC"] = "0"

    result = subprocess.run(
        [str(test_reboot)] + arguments,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    calls = call_log.read_text().splitlines()
    assert result.returncode == 0
    assert calls.index("platform-pre-check") < calls.index(
        "sonic-installer verify-next-image"
    )
