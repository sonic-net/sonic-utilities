import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
REBOOT_SCRIPT = SCRIPTS_DIR / "reboot"
SMARTSWITCH_HELPER = SCRIPTS_DIR / "reboot_smartswitch_helper"
SWITCH_HOST_ENV = {
    "REBOOT_TEST_IS_DPU": "False",
    "REBOOT_TEST_IS_SWITCH_HOST": "True",
}


def _write_executable(path, body):
    path.write_text("#!/bin/bash\n{}\n".format(body))
    path.chmod(0o700)


def _build_reboot_sandbox(tmp_path, stop_after_precheck):
    """Build a PATH sandbox around a copied reboot script."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    device_dir = tmp_path / "device"
    platform_dir = device_dir / "test-platform"
    platform_dir.mkdir(parents=True)
    call_log = tmp_path / "calls.log"
    real_jq = shutil.which("jq")
    assert real_jq is not None, "jq is required by the reboot sandbox"
    real_timeout = shutil.which("timeout")
    assert real_timeout is not None, "timeout is required by the reboot sandbox"

    script = REBOOT_SCRIPT.read_text()
    replacements = {
        'DEVPATH="/usr/share/sonic/device"': 'DEVPATH="{}"'.format(device_dir),
        'declare -r WATCHDOG_UTIL="/usr/local/bin/watchdogutil"': (
            'declare -r WATCHDOG_UTIL="{}"'.format(bin_dir / "watchdogutil")
        ),
        'REBOOT_CAUSE_FILE="/host/reboot-cause/reboot-cause.txt"': (
            'REBOOT_CAUSE_FILE="{}"'.format(tmp_path / "reboot-cause.txt")
        ),
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
        'WARM_DIR="/host/warmboot"': 'WARM_DIR="{}"'.format(tmp_path / "warmboot"),
        "/sbin/kexec -u -a": "kexec -u -a",
        "/sbin/fstrim -av": "fstrim -av",
        "if test -f /usr/local/bin/ctrmgr_tools.py": "if false",
        'if [ -x ${DEVPATH}/${PLATFORM}/${PLAT_REBOOT} ]; then': (
            'echo "UNREACHABLE-OS-REBOOT" >> "$REBOOT_TEST_CALL_LOG"\n'
            'exit 99\n'
            'if [ -x ${DEVPATH}/${PLATFORM}/${PLAT_REBOOT} ]; then'
        ),
    }
    for old, new in replacements.items():
        assert script.count(old) == 1
        script = script.replace(old, new)

    if stop_after_precheck:
        old = "setup_reboot_variables\nreboot_pre_check\n"
        new = "setup_reboot_variables\nreboot_pre_check\nexit 0\n"
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
  *asic_type*) echo "${REBOOT_TEST_ASIC_TYPE:-broadcom}" ;;
  *DEVICE_METADATA.localhost.subtype*) echo "" ;;
  *asan*) echo no ;;
esac""",
    )
    _write_executable(
        bin_dir / "python3",
        """echo "python3 $*" >> "$REBOOT_TEST_CALL_LOG"
case "$*" in
  *get_num_dpus*) echo "${REBOOT_TEST_NUM_DPUS:-0}" ;;
  *is_dpu*) echo "${REBOOT_TEST_IS_DPU:-False}" ;;
  *is_switch_host*) echo "${REBOOT_TEST_IS_SWITCH_HOST:-False}" ;;
  *is_smartswitch*) echo "${REBOOT_TEST_IS_SMARTSWITCH:-False}" ;;
  *) echo False ;;
esac""",
    )
    _write_executable(
        bin_dir / "jq",
        '''echo "jq $*" >> "$REBOOT_TEST_CALL_LOG"
exec "$REBOOT_TEST_REAL_JQ" "$@"''',
    )
    _write_executable(
        bin_dir / "timeout",
        'echo "timeout $*" >> "$REBOOT_TEST_CALL_LOG"\n'
        'exec "$REBOOT_TEST_REAL_TIMEOUT" "$@"',
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
        platform_dir / "platform_update_reboot_cause",
        'echo "platform-update-reboot-cause" >> "$REBOOT_TEST_CALL_LOG"\n'
        'exit "${REBOOT_TEST_PLATFORM_CAUSE_RC:-0}"',
    )
    _write_executable(
        platform_dir / "pre_reboot_hook",
        '''echo "pre-reboot-hook marker=${SONIC_PRE_SHUTDOWN:-unset}" >> "$REBOOT_TEST_CALL_LOG"
case "${REBOOT_TEST_HOOK_MODE:-exit}" in
  exit)
    exit "${REBOOT_TEST_HOOK_RC:-0}"
    ;;
  sleep)
    /bin/sleep "${REBOOT_TEST_HOOK_SLEEP_SECS:-2}"
    ;;
  ignore-term)
    trap '' TERM
    (
      trap '' TERM
      exec /bin/sleep 60
    ) &
    hook_child=$!
    echo "$hook_child" > "$REBOOT_TEST_HOOK_CHILD_PID_FILE"
    wait "$hook_child"
    ;;
esac''',
    )
    (platform_dir / "asic.conf").write_text(
        'NUM_ASIC="${REBOOT_TEST_NUM_ASIC:-1}"\n'
    )
    _write_executable(
        bin_dir / "logger",
        "exit 0",
    )
    _write_executable(bin_dir / "logname", "echo root")
    for command in ("touch", "rm"):
        _write_executable(bin_dir / command, "exit 0")
    _write_executable(
        bin_dir / "systemctl",
        'echo "systemctl $*" >> "$REBOOT_TEST_CALL_LOG"\n'
        'exit "${REBOOT_TEST_SYSTEMCTL_RC:-0}"',
    )
    _write_executable(
        bin_dir / "docker",
        """echo "docker $*" >> "$REBOOT_TEST_CALL_LOG"
case "$1" in
  exec)
    if [[ -n "${REBOOT_TEST_SYNCD_FAIL_TARGET:-}" &&
          "$3" == "$REBOOT_TEST_SYNCD_FAIL_TARGET" ]]; then
        exit "${REBOOT_TEST_SYNCD_FAIL_RC:-7}"
    fi
    exit "${REBOOT_TEST_SYNCD_RC:-0}"
    ;;
  kill)
    exit "${REBOOT_TEST_PMON_KILL_RC:-0}"
    ;;
  inspect)
    if [[ "${REBOOT_TEST_PMON_INSPECT_RC:-0}" -ne 0 ]]; then
        exit "$REBOOT_TEST_PMON_INSPECT_RC"
    fi
    echo "${REBOOT_TEST_PMON_RUNNING:-false}"
    ;;
esac""",
    )
    _write_executable(
        bin_dir / "config",
        'echo "config $*" >> "$REBOOT_TEST_CALL_LOG"\nexit 0',
    )
    _write_executable(
        bin_dir / "kexec",
        'echo "kexec $*" >> "$REBOOT_TEST_CALL_LOG"\nexit 0',
    )
    _write_executable(
        bin_dir / "sync",
        'echo "sync" >> "$REBOOT_TEST_CALL_LOG"\n'
        'exit "${REBOOT_TEST_SYNC_RC:-0}"',
    )
    _write_executable(
        bin_dir / "fstrim",
        'echo "fstrim $*" >> "$REBOOT_TEST_CALL_LOG"\n'
        'exit "${REBOOT_TEST_FSTRIM_RC:-0}"',
    )
    _write_executable(
        bin_dir / "sleep",
        'echo "sleep $*" >> "$REBOOT_TEST_CALL_LOG"\nexit 0',
    )
    _write_executable(
        bin_dir / "watchdogutil",
        'echo "watchdogutil $*" >> "$REBOOT_TEST_CALL_LOG"\n'
        'printf "%s\\n" "${REBOOT_TEST_WATCHDOG_OUTPUT:-Watchdog armed for 180 seconds}"\n'
        'exit "${REBOOT_TEST_WATCHDOG_RC:-0}"',
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": "{}:{}".format(bin_dir, env["PATH"]),
            "REBOOT_TEST_ALLOW_NON_ROOT": "yes",
            "REBOOT_TEST_CALL_LOG": str(call_log),
            "REBOOT_TEST_HOOK_CHILD_PID_FILE": str(tmp_path / "hook-child.pid"),
            "REBOOT_TEST_REAL_JQ": real_jq,
            "REBOOT_TEST_REAL_TIMEOUT": real_timeout,
            "REBOOT_TEST_PLATFORM_JSON_PATH": str(platform_dir / "platform.json"),
            "REBOOT_TEST_PRECHECK_RC": "0",
        }
    )
    return test_reboot, call_log, env


@pytest.fixture
def reboot_sandbox(tmp_path):
    """Stop the copied script immediately after its pre-checks."""
    return _build_reboot_sandbox(tmp_path, stop_after_precheck=True)


@pytest.fixture
def full_reboot_sandbox(tmp_path):
    """Run the copied script through its safe pre-shutdown exit."""
    return _build_reboot_sandbox(tmp_path, stop_after_precheck=False)


def _run_reboot(sandbox, arguments, **environment):
    test_reboot, call_log, env = sandbox
    env.update({key: str(value) for key, value in environment.items()})
    platform_data = {}
    platform_fields = {
        "REBOOT_TEST_HOOK_TIMEOUT": "pre_shutdown_hook_timeout_secs",
        "REBOOT_TEST_WATCHDOG_MIN": "pre_shutdown_min_watchdog_secs",
    }
    for env_name, field_name in platform_fields.items():
        raw_value = env.get(env_name, "missing")
        if raw_value == "missing":
            continue
        try:
            platform_data[field_name] = json.loads(raw_value)
        except json.JSONDecodeError:
            platform_data[field_name] = raw_value
    Path(env["REBOOT_TEST_PLATFORM_JSON_PATH"]).write_text(
        json.dumps(platform_data)
    )
    result = subprocess.run(
        [str(test_reboot)] + arguments,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    calls = call_log.read_text().splitlines()
    return result, calls


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


def test_non_switch_host_keeps_pre_shutdown_rejection(full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        REBOOT_TEST_IS_DPU="False",
        REBOOT_TEST_IS_SWITCH_HOST="False",
    )

    assert result.returncode == 1
    assert "'-p' option specified for a non-DPU" in result.stderr
    assert "systemctl disable pmon" not in calls
    assert not any(call.startswith("docker inspect") for call in calls)


def test_full_sandbox_blocks_any_os_reboot(full_reboot_sandbox):
    result, calls = _run_reboot(full_reboot_sandbox, [])

    assert result.returncode == 99
    assert "UNREACHABLE-OS-REBOOT" in calls
    assert "systemctl disable pmon" not in calls
    assert not any(call.startswith("docker inspect") for call in calls)


def test_switch_host_runs_existing_teardown_without_dpu_helper(
        full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV
    )

    assert result.returncode == 0
    assert not any("get_num_dpus" in call for call in calls)
    timeout_call = next(call for call in calls if call.startswith("timeout "))
    assert timeout_call.startswith("timeout --kill-after=10 60 ")
    assert timeout_call.endswith("/pre_reboot_hook")
    ordered_calls = [
        "docker exec -i syncd /usr/bin/syncd_request_shutdown --cold",
        "systemctl disable pmon",
        "systemctl stop pmon",
        "docker kill pmon",
        "docker inspect -f {{.State.Running}} pmon",
        "kexec -u -a",
        "sync",
        "fstrim -av",
        "platform-update-reboot-cause",
        timeout_call,
        "pre-reboot-hook marker=1",
        "watchdogutil arm",
    ]
    assert [calls.index(call) for call in ordered_calls] == sorted(
        calls.index(call) for call in ordered_calls
    )


def test_smartswitch_host_keeps_dhcp_gate_but_skips_dpu_legs(
        full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_IS_SMARTSWITCH="True"
    )

    assert result.returncode == 0
    assert "config dhcp_server ipv4 disable bridge-midplane" in calls
    assert not any("get_num_dpus" in call for call in calls)


@pytest.mark.parametrize(
    "syncd_failure_env",
    [
        {"REBOOT_TEST_SYNCD_RC": 7},
        {
            "REBOOT_TEST_NUM_ASIC": 2,
            "REBOOT_TEST_SYNCD_FAIL_TARGET": "syncd0",
        },
    ],
    ids=["single-asic", "multi-asic"],
)
def test_dpu_identity_wins_and_strict_failures_remain_best_effort(
        full_reboot_sandbox, syncd_failure_env):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        REBOOT_TEST_IS_DPU="True",
        REBOOT_TEST_IS_SWITCH_HOST="True",
        REBOOT_TEST_PMON_RUNNING="true",
        REBOOT_TEST_SYNC_RC=8,
        REBOOT_TEST_HOOK_RC=9,
        REBOOT_TEST_WATCHDOG_OUTPUT="Failed to arm watchdog",
        REBOOT_TEST_WATCHDOG_RC=5,
        **syncd_failure_env
    )

    assert result.returncode == 0
    assert any("get_num_dpus" in call for call in calls)
    assert not any(call.startswith("jq ") for call in calls)
    assert "systemctl stop pmon" in calls
    assert "docker kill pmon" in calls
    assert not any(call.startswith("docker inspect") for call in calls)
    assert "fstrim -av" in calls
    assert "pre-reboot-hook marker=unset" in calls
    assert not any(call.startswith("timeout ") for call in calls)
    assert "watchdogutil arm" in calls


def test_switch_host_plain_reboot_remains_non_strict(
        full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        [],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_SYNCD_RC=7,
        REBOOT_TEST_PMON_RUNNING="true",
        REBOOT_TEST_SYNC_RC=8,
        REBOOT_TEST_HOOK_RC=9,
        REBOOT_TEST_WATCHDOG_OUTPUT="Failed to arm watchdog",
        REBOOT_TEST_WATCHDOG_RC=5
    )

    assert result.returncode == 99
    assert "UNREACHABLE-OS-REBOOT" in calls
    assert not any(call.startswith("jq ") for call in calls)
    assert "systemctl disable pmon" not in calls
    assert "systemctl stop pmon" in calls
    assert "docker kill pmon" in calls
    assert not any(call.startswith("docker inspect") for call in calls)
    assert "fstrim -av" in calls
    assert "pre-reboot-hook marker=unset" in calls
    assert not any(call.startswith("timeout ") for call in calls)
    assert "watchdogutil arm" in calls


def test_dpu_and_pre_shutdown_options_remain_mutually_exclusive(
        full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p", "-d", "DPU0"],
        **SWITCH_HOST_ENV
    )

    assert result.returncode == 1
    assert "'-p' option specified for a non-DPU" in result.stderr
    assert not any("get_num_dpus" in call for call in calls)
    assert "systemctl disable pmon" not in calls


@pytest.mark.parametrize(
    "failure_env,expected_syncd_calls",
    [
        (
            {"REBOOT_TEST_SYNCD_RC": 7},
            ["docker exec -i syncd /usr/bin/syncd_request_shutdown --cold"],
        ),
        (
            {
                "REBOOT_TEST_NUM_ASIC": 2,
                "REBOOT_TEST_SYNCD_FAIL_TARGET": "syncd0",
            },
            [
                "docker exec -i syncd0 /usr/bin/syncd_request_shutdown --cold",
            ],
        ),
        (
            {
                "REBOOT_TEST_NUM_ASIC": 2,
                "REBOOT_TEST_SYNCD_FAIL_TARGET": "syncd1",
            },
            [
                "docker exec -i syncd0 /usr/bin/syncd_request_shutdown --cold",
                "docker exec -i syncd1 /usr/bin/syncd_request_shutdown --cold",
            ],
        ),
    ],
    ids=["single-asic", "multi-asic-first", "multi-asic-last"],
)
def test_strict_syncd_shutdown_failure_is_fatal(
        full_reboot_sandbox, failure_env, expected_syncd_calls):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        **failure_env
    )

    assert result.returncode != 0
    assert "PRE-SHUTDOWN FAILED: syncd shutdown request" in result.stdout
    assert [call for call in calls if call.startswith("docker exec -i syncd")] == (
        expected_syncd_calls
    )
    assert "systemctl disable pmon" not in calls


def test_strict_mellanox_path_keeps_existing_syncd_skip(full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_ASIC_TYPE="mellanox",
        REBOOT_TEST_SYNCD_RC=7
    )

    assert result.returncode == 0
    assert not any(call.startswith("docker exec -i syncd") for call in calls)
    assert any(call.startswith("docker inspect") for call in calls)


@pytest.mark.parametrize(
    "failure_env,expected_message",
    [
        (
            {"REBOOT_TEST_PMON_RUNNING": "true"},
            "PRE-SHUTDOWN FAILED: pmon still running",
        ),
        (
            {"REBOOT_TEST_PMON_INSPECT_RC": 5},
            "PRE-SHUTDOWN FAILED: unable to verify pmon stopped",
        ),
    ],
    ids=["still-running", "inspect-error"],
)
def test_strict_pmon_postcondition_failure_is_fatal(
        full_reboot_sandbox, failure_env, expected_message):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        **failure_env
    )

    assert result.returncode != 0
    assert expected_message in result.stdout
    assert any(call.startswith("docker inspect") for call in calls)
    assert "kexec -u -a" not in calls


def test_strict_sync_failure_is_fatal(full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_SYNC_RC=6
    )

    assert result.returncode != 0
    assert "PRE-SHUTDOWN FAILED: sync" in result.stdout
    assert "kexec -u -a" in calls
    assert "fstrim -av" not in calls


@pytest.mark.parametrize(
    "hook_environment,expected_hook_rc",
    [
        ({"REBOOT_TEST_HOOK_RC": 1}, 1),
        (
            {
                "REBOOT_TEST_HOOK_MODE": "sleep",
                "REBOOT_TEST_HOOK_SLEEP_SECS": 3,
                "REBOOT_TEST_HOOK_TIMEOUT": 1,
            },
            124,
        ),
    ],
    ids=["non-zero", "term-timeout"],
)
def test_strict_hook_failure_is_fatal(
        full_reboot_sandbox, hook_environment, expected_hook_rc):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        **hook_environment
    )

    assert result.returncode != 0
    assert "PRE-SHUTDOWN FAILED: pre-reboot hook rc={}".format(
        expected_hook_rc
    ) in result.stdout
    assert "pre-reboot-hook marker=1" in calls
    assert any(call.startswith("timeout --kill-after=10 ") for call in calls)
    assert "watchdogutil arm" not in calls


def test_strict_hook_ignoring_term_is_killed_with_no_surviving_child(
        full_reboot_sandbox):
    child_pid_file = Path(
        full_reboot_sandbox[2]["REBOOT_TEST_HOOK_CHILD_PID_FILE"]
    )

    started = time.monotonic()
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_HOOK_MODE="ignore-term",
        REBOOT_TEST_HOOK_TIMEOUT=1
    )
    elapsed = time.monotonic() - started

    assert result.returncode != 0
    assert "PRE-SHUTDOWN FAILED: pre-reboot hook rc=137" in result.stdout
    assert "pre-reboot-hook marker=1" in calls
    assert 10.0 <= elapsed < 16.0
    child_proc = Path("/proc") / child_pid_file.read_text().strip()
    child_exit_deadline = time.monotonic() + 2
    while child_proc.exists() and time.monotonic() < child_exit_deadline:
        time.sleep(0.05)
    assert not child_proc.exists()
    assert "watchdogutil arm" not in calls


@pytest.mark.parametrize(
    "hook_timeout,expected_value",
    [
        ("0", "0"),
        ("-5", "-5"),
        ("1.5", "1.5"),
        ('"abc"', '"abc"'),
        ('"30s"', '"30s"'),
        ('"60"', '"60"'),
        ("false", "false"),
        ("null", "null"),
    ],
    ids=[
        "zero",
        "negative",
        "fractional",
        "nonnumeric-string",
        "suffixed-string",
        "numeric-string",
        "boolean",
        "null",
    ],
)
def test_strict_hook_timeout_rejects_invalid_values(
        full_reboot_sandbox, hook_timeout, expected_value):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_HOOK_TIMEOUT=hook_timeout
    )

    assert result.returncode != 0
    assert (
        "PRE-SHUTDOWN FAILED: invalid pre_shutdown_hook_timeout_secs "
        "'{}'".format(expected_value)
    ) in result.stdout
    assert not any(call.startswith("timeout ") for call in calls)
    assert "pre-reboot-hook marker=1" not in calls
    assert "watchdogutil arm" not in calls


def test_strict_hook_timeout_accepts_one_second_boundary(full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_HOOK_TIMEOUT=1
    )

    assert result.returncode == 0
    assert any(
        call.startswith("timeout --kill-after=10 1 ") for call in calls
    )
    assert "pre-reboot-hook marker=1" in calls
    assert "watchdogutil arm" in calls


@pytest.mark.parametrize(
    "watchdog_minimum,expected_value",
    [
        ("-1", "-1"),
        ('"abc"', '"abc"'),
        ('"0140"', '"0140"'),
        ('"140"', '"140"'),
        ("false", "false"),
        ("null", "null"),
    ],
    ids=[
        "negative",
        "nonnumeric-string",
        "leading-zero-string",
        "numeric-string",
        "boolean",
        "null",
    ],
)
def test_strict_watchdog_minimum_rejects_invalid_values(
        full_reboot_sandbox, watchdog_minimum, expected_value):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_WATCHDOG_MIN=watchdog_minimum
    )

    assert result.returncode != 0
    assert (
        "PRE-SHUTDOWN FAILED: invalid pre_shutdown_min_watchdog_secs "
        "'{}'".format(expected_value)
    ) in result.stdout
    assert "pre-reboot-hook marker=1" in calls
    assert "watchdogutil arm" not in calls


@pytest.mark.parametrize(
    "watchdog_output",
    [
        "Failed to arm watchdog",
        "Watchdog armed for 010 seconds",
        "Watchdog armed for 180 seconds trailing",
        "Armed watchdog for 180 seconds",
    ],
    ids=[
        "failure-sentence",
        "leading-zero",
        "trailing-garbage",
        "different-sentence",
    ],
)
def test_strict_watchdog_rejects_unproved_output(
        full_reboot_sandbox, watchdog_output):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_WATCHDOG_OUTPUT=watchdog_output
    )

    assert result.returncode != 0
    assert "PRE-SHUTDOWN FAILED: watchdog arm/readback" in result.stdout
    assert "watchdogutil arm" in calls


def test_strict_watchdog_rejects_readback_below_minimum(full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_WATCHDOG_MIN=140,
        REBOOT_TEST_WATCHDOG_OUTPUT="Watchdog armed for 100 seconds"
    )

    assert result.returncode != 0
    assert (
        "PRE-SHUTDOWN FAILED: watchdog readback 100s below required 140s"
        in result.stdout
    )
    assert "watchdogutil arm" in calls


def test_strict_watchdog_compares_above_int64_without_overflow(
        full_reboot_sandbox):
    watchdog_minimum = "9223372036854776000"
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_WATCHDOG_MIN=watchdog_minimum,
        REBOOT_TEST_WATCHDOG_OUTPUT="Watchdog armed for 100 seconds"
    )

    assert result.returncode != 0
    assert (
        "PRE-SHUTDOWN FAILED: watchdog readback 100s below required {}s".format(
            watchdog_minimum
        ) in result.stdout
    )
    assert "watchdogutil arm" in calls


@pytest.mark.parametrize(
    "watchdog_minimum,watchdog_seconds",
    [("0", 1), ("140", 200)],
    ids=["zero-minimum", "above-minimum"],
)
def test_strict_watchdog_accepts_proved_readback(
        full_reboot_sandbox, watchdog_minimum, watchdog_seconds):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-v", "-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_WATCHDOG_MIN=watchdog_minimum,
        REBOOT_TEST_WATCHDOG_OUTPUT=(
            "Watchdog armed for {} seconds".format(watchdog_seconds)
        )
    )

    assert result.returncode == 0
    assert "watchdog armed: {}s (required minimum {}s)".format(
        watchdog_seconds, watchdog_minimum
    ) in result.stdout
    assert "watchdogutil arm" in calls


def test_strict_watchdog_requires_executable_utility(full_reboot_sandbox):
    watchdog_path = full_reboot_sandbox[0].parent / "watchdogutil"
    watchdog_path.unlink()

    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV
    )

    assert result.returncode != 0
    assert "PRE-SHUTDOWN FAILED: watchdog utility unavailable" in result.stdout
    assert "watchdogutil arm" not in calls


def test_strict_path_retains_named_best_effort_steps(full_reboot_sandbox):
    result, calls = _run_reboot(
        full_reboot_sandbox,
        ["-p"],
        **SWITCH_HOST_ENV,
        REBOOT_TEST_FSTRIM_RC=9,
        REBOOT_TEST_PLATFORM_CAUSE_RC=8
    )

    assert result.returncode == 0
    assert "kexec -u -a" in calls
    assert "fstrim -av" in calls
    assert "platform-update-reboot-cause" in calls
