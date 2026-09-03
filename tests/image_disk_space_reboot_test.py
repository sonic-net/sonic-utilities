# tests/image_disk_space_reboot_test.py

import json

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
