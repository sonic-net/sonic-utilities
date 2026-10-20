# tests/image_disk_space_reboot_test.py

import json
from pathlib import Path
import subprocess

import pytest

from utilities_common import image_disk_space


GB = 1024 * 1024 * 1024


def write_platform_json(tmp_path, data):
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.mark.parametrize(
    "device_type,key,value",
    [
        (
            image_disk_space.IMAGE_TYPE_SWITCH,
            image_disk_space.SWITCH_MIN_FREE_DISK_REBOOT_KEY,
            4,
        ),
        (
            image_disk_space.IMAGE_TYPE_DPU,
            image_disk_space.DPU_MIN_FREE_DISK_REBOOT_KEY,
            5,
        ),
    ],
)
def test_get_reboot_threshold(tmp_path, device_type, key, value):
    path = write_platform_json(tmp_path, {key: value})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_reboot(
            device_type,
            path,
        )
        == value
    )


@pytest.mark.parametrize(
    "device_type",
    [
        image_disk_space.IMAGE_TYPE_SWITCH,
        image_disk_space.IMAGE_TYPE_DPU,
    ],
)
def test_missing_reboot_threshold_disables_check(tmp_path, device_type):
    path = write_platform_json(tmp_path, {})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_reboot(
            device_type,
            path,
        )
        is None
    )


@pytest.mark.parametrize("value", [0, -1, "bad", None])
def test_invalid_reboot_threshold_skips_check(
    tmp_path,
    caplog,
    value,
):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.SWITCH_MIN_FREE_DISK_REBOOT_KEY: value,
        },
    )

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_reboot(
            image_disk_space.IMAGE_TYPE_SWITCH,
            path,
        )
        is None
    )
    assert "skipping the disk-space check" in caplog.text


@pytest.mark.parametrize(
    "available_gb,expected",
    [
        (8, True),
        (3, False),
        (None, False),
    ],
)
def test_check_local_reboot_free_disk_space(
    monkeypatch,
    tmp_path,
    available_gb,
    expected,
):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.SWITCH_MIN_FREE_DISK_REBOOT_KEY: 4,
        },
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_free_disk_in_gb",
        lambda disk_path: available_gb,
    )

    assert (
        image_disk_space.check_local_reboot_free_disk_space(
            device_type=image_disk_space.IMAGE_TYPE_SWITCH,
            platform_json_path=path,
        )
        is expected
    )


def test_local_reboot_without_policy_is_noop(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {})
    called = {"value": False}

    def get_free_disk(_):
        called["value"] = True
        return 0

    monkeypatch.setattr(
        image_disk_space,
        "get_free_disk_in_gb",
        get_free_disk,
    )

    assert image_disk_space.check_local_reboot_free_disk_space(
        platform_json_path=path,
    )
    assert not called["value"]


@pytest.mark.parametrize(
    "available_bytes,expected",
    [
        (4 * GB, True),
        (4 * GB - 1, False),
        (None, False),
    ],
)
def test_check_remote_dpu_reboot_free_disk_space(
    monkeypatch,
    tmp_path,
    available_bytes,
    expected,
):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.DPU_MIN_FREE_DISK_REBOOT_KEY: 4,
        },
    )
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_bytes",
        lambda *args, **kwargs: available_bytes,
    )

    assert (
        image_disk_space.check_remote_dpu_reboot_free_disk_space(
            "dpu0",
            platform_json_path=path,
        )
        is expected
    )


def test_remote_dpu_reboot_without_policy_is_noop(
    monkeypatch,
    tmp_path,
):
    path = write_platform_json(tmp_path, {})
    called = {"value": False}

    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )

    def get_remote(*args, **kwargs):
        called["value"] = True
        return 0

    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_bytes",
        get_remote,
    )

    assert image_disk_space.check_remote_dpu_reboot_free_disk_space(
        "dpu0",
        platform_json_path=path,
    )
    assert not called["value"]


def test_remote_dpu_reboot_rejected_on_dpu(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: True,
    )

    assert not image_disk_space.check_remote_dpu_reboot_free_disk_space(
        "dpu0"
    )


@pytest.mark.parametrize(
    "output,expected",
    [
        ("Avail\n4294967296", 4 * GB),
        ("Avail\n4294967295", 4 * GB - 1),
        ("Filesystem\n/dev/mmcblk0p10\nAvail\n32212254720", 30 * GB),
    ],
)
def test_parse_df_available_bytes_success(output, expected):
    assert image_disk_space._parse_df_available_bytes(output) == expected


@pytest.mark.parametrize(
    "output",
    ["", "Avail", "Avail\nbad", "Avail\n-1", "Avail\n18.5"],
)
def test_parse_df_available_bytes_failure(output):
    assert image_disk_space._parse_df_available_bytes(output) is None


def test_get_remote_dpu_free_disk_in_bytes_command(monkeypatch):
    captured = {}

    def run_cmd(cmd):
        captured["cmd"] = cmd
        return 0, "Avail\n4294967296"

    monkeypatch.setattr(image_disk_space, "_run_cmd", run_cmd)

    assert (
        image_disk_space.get_remote_dpu_free_disk_in_bytes(
            "dpu0",
            disk_path="/host",
            ssh_options=["-o", "BatchMode=yes"],
        )
        == 4 * GB
    )
    assert "-B1" in captured["cmd"]
    assert "--output=avail" in captured["cmd"]


@pytest.mark.parametrize("dhcp_failure", ["none", "disable", "restore"])
@pytest.mark.parametrize(
    "disk_failure,worker_status,dhcp_state,offline,expected_code,expected_events",
    [
        (True, 0, "enabled", False, 1, ["check:dpu0", "check:dpu1"]),
        (False, 1, "enabled", False, 1,
         ["check:dpu0", "check:dpu1", "disable", "reboot:dpu0", "reboot:dpu1", "enable"]),
        (False, 1, "disabled", False, 1,
         ["check:dpu0", "check:dpu1", "reboot:dpu0", "reboot:dpu1"]),
        (False, 0, "disabled", False, 0,
         ["check:dpu0", "check:dpu1", "reboot:dpu0", "reboot:dpu1"]),
        (False, 0, "enabled", False, 0,
         ["check:dpu0", "check:dpu1", "disable", "reboot:dpu0", "reboot:dpu1"]),
        (False, 2, "enabled", True, 0,
         ["check:dpu0", "disable", "reboot:dpu0", "reboot:dpu1"]),
        (False, 0, "", False, 1, ["check:dpu0", "check:dpu1"]),
    ],
)
def test_smartswitch_reboot_preflight_and_dhcp(
    tmp_path, disk_failure, worker_status, dhcp_state, offline,
    expected_code, expected_events, dhcp_failure,
):
    if dhcp_failure == "disable" and "disable" in expected_events:
        expected_code = 1
        expected_events = expected_events[:expected_events.index("disable")] + ["disable", "enable"]
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    reboot_script = (scripts / "reboot").read_text()
    reboot_flow = reboot_script.split("# SmartSwitch NPU only:", 1)[1].split(
        "# On a smartswitch, complete the DPU reboot and exit", 1
    )[0]
    events = tmp_path / "events"
    shell = r'''
source "$1/reboot_smartswitch_helper"
EXIT_SUCCESS=0
EXIT_ERROR=1
REBOOT_DPU=no
PRE_SHUTDOWN=no
debug() { :; }
is_smartswitch() { echo True; }
is_dpu() { return 1; }
get_num_dpus() { echo 2; }
check_dpu_online() {
    if [[ "$offline" == True && "$1" == dpu1 ]]; then return 2; fi
    return 0
}
check_dpu_reboot_disk_space() {
    echo "check:$1" >> "$events"
    if [[ "$disk_failure" == True && "$1" == dpu1 ]]; then return 1; fi
    return 0
}
sonic-db-cli() { echo "$dhcp_state"; }
config() {
    echo "$3" >> "$events"
    if [[ "$dhcp_failure" == "$3" || ( "$dhcp_failure" == restore && "$3" == enable ) ]]; then
        return 1
    fi
    return 0
}
reboot_dpu() {
    echo "reboot:$1" >> "$events"
    if [[ "$1" == dpu1 ]]; then return "$worker_status"; fi
    return 0
}
'''
    result = subprocess.run(
        ["bash", "-c",
         'events=$2; disk_failure=$3; worker_status=$4; dhcp_state=$5; offline=$6; dhcp_failure=$7\n'
         + shell + reboot_flow + '\nexit 0\n',
         "reboot-test", str(scripts), str(events), str(disk_failure),
         str(worker_status), dhcp_state, str(offline), dhcp_failure],
        capture_output=True, text=True,
    )
    assert result.returncode == expected_code, result.stderr
    actual_events = events.read_text().splitlines()
    assert sorted(actual_events) == sorted(expected_events)
    if "disable" in actual_events:
        disable_index = actual_events.index("disable")
        assert all(event.startswith("check:") for event in actual_events[:disable_index])
        assert all(not event.startswith("check:") for event in actual_events[disable_index:])
    if "enable" in actual_events:
        assert actual_events[-1] == "enable"
        if dhcp_failure == "restore":
            assert "ERROR: Failed to restore dhcp_server on bridge-midplane" in result.stderr


@pytest.mark.parametrize(
    "reboot_type,online_status,disk_status,expected_code,expected_events",
    [
        ("DPU", 0, 1, 1, ["check"]),
        ("DPU", 2, 0, 2, []),
        ("DPU", 0, 0, 0, ["check", "halt"]),
        ("SMARTSWITCH", 0, 1, 0, ["halt"]),
    ],
)
def test_dpu_worker_disk_check(
    reboot_type, online_status, disk_status, expected_code, expected_events,
):
    helper = Path(__file__).resolve().parents[1] / "scripts" / "reboot_smartswitch_helper"
    result = subprocess.run(
        ["bash", "-c", r'''
source "$1"
EXIT_SUCCESS=0
EXIT_ERROR=1
reboot_type=$2
online_status=$3
disk_status=$4
check_dpu_online() { return "$online_status"; }
check_dpu_reboot_disk_space() { echo check; return "$disk_status"; }
get_module_state_transition_flag() { return 1; }
set_module_state_transition_flag() { :; }
gnmi_reboot_dpu() { echo halt; exit 0; }
reboot_dpu dpu0 "$reboot_type"
''', "reboot-test", str(helper), reboot_type, str(online_status), str(disk_status)],
        capture_output=True, text=True,
    )
    assert result.returncode == expected_code, result.stderr
    assert result.stdout.splitlines() == expected_events


@pytest.mark.parametrize(
    "row,show_status,expected_status",
    [
        ("DPU0  DPU module  0  Online  up  serial  ready", 0, 0),
        ("  DPU0  DPU module  0  Offline  up  serial  ready", 0, 2),
        ("DPU0  DPU module  0  Online  up  serial  ready", 1, 1),
        ("", 1, 1),
        ("", 0, 1),
        ("DPU0  DPU module  0  Partial Online  up  serial  ready", 0, 1),
        ("DPU0  DPU module  0  Unknown  up  serial  ready", 0, 1),
        ("DPU0  DPU module  0  offline  up  serial  ready", 0, 1),
        ("DPU0 malformed output Online", 0, 1),
        ("DPU1  DPU module  1  Online  up  serial  ready", 0, 1),
    ],
)
def test_dpu_status_preflight(row, show_status, expected_status):
    helper = Path(__file__).resolve().parents[1] / "scripts" / "reboot_smartswitch_helper"
    result = subprocess.run(
        ["bash", "-c", r'''
source "$1"
EXIT_SUCCESS=0
EXIT_ERROR=1
mock_status_output=$2
show_status=$3
show() { printf '%s\n' "$mock_status_output"; return "$show_status"; }
check_dpu_reboot_disk_space() { echo check; }
check_dpu_online dpu0
printf 'status:%s\n' "$?"
preflight_all_dpus 1
''', "reboot-test", str(helper), row, str(show_status)],
        capture_output=True, text=True,
    )
    assert result.returncode == (1 if expected_status == 1 else 0), result.stderr
    expected_events = [f"status:{expected_status}"]
    if expected_status == 0:
        expected_events.append("check")
    assert result.stdout.splitlines() == expected_events
