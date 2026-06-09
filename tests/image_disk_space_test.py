# tests/image_disk_space_test.py

import json
import subprocess

import pytest

from utilities_common import image_disk_space


GB = 1024 * 1024 * 1024


def write_platform_json(tmp_path, data):
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_get_min_free_disk_npu_from_platform_json(tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_npu_image": 16
    })

    assert image_disk_space.get_min_free_disk_in_gb_for_npu_image(path) == 16


def test_get_min_free_disk_dpu_from_platform_json(tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 14
    })

    assert image_disk_space.get_min_free_disk_in_gb_for_dpu_image(path) == 14


def test_get_min_free_disk_npu_missing_key_uses_default(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_npu_image(path) ==
        image_disk_space.MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE
    )


def test_get_min_free_disk_dpu_missing_key_uses_default(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_dpu_image(path) ==
        image_disk_space.MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE
    )


@pytest.mark.parametrize("bad_value", [0, -1, "bad"])
def test_invalid_npu_platform_json_value_uses_default(tmp_path, bad_value):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_npu_image": bad_value
    })

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_npu_image(path) ==
        image_disk_space.MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE
    )


@pytest.mark.parametrize("bad_value", [0, -1, "bad"])
def test_invalid_dpu_platform_json_value_uses_default(tmp_path, bad_value):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": bad_value
    })

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_dpu_image(path) ==
        image_disk_space.MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE
    )


def test_missing_platform_json_uses_default():
    assert (
        image_disk_space.get_min_free_disk_in_gb_for_npu_image(
            "/bad/path/platform.json"
        ) == image_disk_space.MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE
    )


def test_get_free_disk_in_gb_success(monkeypatch):
    class Usage:
        free = 20 * GB

    monkeypatch.setattr(image_disk_space.os.path, "exists", lambda path: True)
    monkeypatch.setattr(image_disk_space.shutil, "disk_usage", lambda path: Usage)

    assert image_disk_space.get_free_disk_in_gb("/host") == 20


def test_get_free_disk_in_gb_missing_path(monkeypatch):
    monkeypatch.setattr(image_disk_space.os.path, "exists", lambda path: False)

    assert image_disk_space.get_free_disk_in_gb("/missing") is None


def test_check_npu_image_install_free_disk_space_success(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_npu_image": 12
    })

    monkeypatch.setattr(image_disk_space, "get_free_disk_in_gb", lambda disk_path: 20)

    assert image_disk_space.check_npu_image_install_free_disk_space(
        disk_path="/host",
        platform_json_path=path
    )


def test_check_npu_image_install_free_disk_space_failure(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_npu_image": 12
    })

    monkeypatch.setattr(image_disk_space, "get_free_disk_in_gb", lambda disk_path: 8)

    assert not image_disk_space.check_npu_image_install_free_disk_space(
        disk_path="/host",
        platform_json_path=path
    )


def test_check_npu_image_install_free_disk_space_unable_to_check(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_npu_image": 12
    })

    monkeypatch.setattr(image_disk_space, "get_free_disk_in_gb", lambda disk_path: None)

    assert not image_disk_space.check_npu_image_install_free_disk_space(
        disk_path="/host",
        platform_json_path=path
    )


def test_run_cmd_success(monkeypatch):
    monkeypatch.setattr(
        image_disk_space.subprocess,
        "check_output",
        lambda *args, **kwargs: "Avail\n20G\n"
    )

    rc, output = image_disk_space._run_cmd(["dummy"])

    assert rc == 0
    assert output == "Avail\n20G"


def test_run_cmd_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "cmd", output="error")

    monkeypatch.setattr(image_disk_space.subprocess, "check_output", raise_error)

    rc, output = image_disk_space._run_cmd(["dummy"])

    assert rc == 1
    assert output == "error"


@pytest.mark.parametrize(
    "output,expected",
    [
        ("Avail\n18G", 18),
        ("Avail\n18", 18),
        ("Available\n  25G\n", 25),
        ("Filesystem\n/dev/sda1\nAvail\n30G", 30),
    ]
)
def test_parse_df_available_gb_success(output, expected):
    assert image_disk_space._parse_df_available_gb(output) == expected


@pytest.mark.parametrize("output", ["", "Avail", "Avail\nbad"])
def test_parse_df_available_gb_failure(output):
    assert image_disk_space._parse_df_available_gb(output) is None


def test_get_dpu_free_disk_in_gb_success(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, "Avail\n18G")
    )

    assert image_disk_space.get_dpu_free_disk_in_gb("DPU0") == 18


def test_get_dpu_free_disk_in_gb_with_custom_ssh_options(monkeypatch):
    captured_cmd = {}

    def fake_run_cmd(cmd):
        captured_cmd["cmd"] = cmd
        return 0, "Avail\n18G"

    monkeypatch.setattr(image_disk_space, "_run_cmd", fake_run_cmd)

    assert image_disk_space.get_dpu_free_disk_in_gb(
        "DPU0",
        ssh_options=["-o", "ConnectTimeout=3"]
    ) == 18

    assert captured_cmd["cmd"] == [
        "ssh",
        "-o", "ConnectTimeout=3",
        "DPU0",
        "df", "-BG", "--output=avail", "/host"
    ]


def test_get_dpu_free_disk_in_gb_command_failure(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (1, "ssh failed")
    )

    assert image_disk_space.get_dpu_free_disk_in_gb("DPU0") is None


def test_get_dpu_free_disk_in_gb_parse_failure(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, "Avail\nbad")
    )

    assert image_disk_space.get_dpu_free_disk_in_gb("DPU0") is None


def test_get_dpu_free_disk_in_gb_empty_output(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, "")
    )

    assert image_disk_space.get_dpu_free_disk_in_gb("DPU0") is None


def test_check_dpu_image_install_free_disk_space_single_success(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 12
    })

    monkeypatch.setattr(
        image_disk_space,
        "get_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: 20
    )

    assert image_disk_space.check_dpu_image_install_free_disk_space(
        "DPU0",
        disk_path="/host",
        platform_json_path=path
    )


def test_check_dpu_image_install_free_disk_space_multi_success(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 12
    })

    free_space = {
        "DPU0": 20,
        "DPU1": 18,
        "DPU2": 16,
    }

    monkeypatch.setattr(
        image_disk_space,
        "get_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: free_space[dpu_name]
    )

    assert image_disk_space.check_dpu_image_install_free_disk_space(
        ["DPU0", "DPU1", "DPU2"],
        disk_path="/host",
        platform_json_path=path
    )


def test_check_dpu_image_install_free_disk_space_failure(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 12
    })

    monkeypatch.setattr(
        image_disk_space,
        "get_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: 8
    )

    assert not image_disk_space.check_dpu_image_install_free_disk_space(
        ["DPU0"],
        disk_path="/host",
        platform_json_path=path
    )


def test_check_dpu_image_install_free_disk_space_unable_to_check(monkeypatch, tmp_path):
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 12
    })

    monkeypatch.setattr(
        image_disk_space,
        "get_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: None
    )

    assert not image_disk_space.check_dpu_image_install_free_disk_space(
        ["DPU0"],
        disk_path="/host",
        platform_json_path=path
    )


def test_check_dpu_image_install_free_disk_space_mixed_results_fail(monkeypatch, tmp_path):
    """
    If any DPU has less than the required free disk space,
    the whole batch check must fail.
    """
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 12
    })

    free_space = {
        "DPU0": 20,
        "DPU1": 8,
        "DPU2": 18,
    }

    monkeypatch.setattr(
        image_disk_space,
        "get_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: free_space[dpu_name]
    )

    assert not image_disk_space.check_dpu_image_install_free_disk_space(
        ["DPU0", "DPU1", "DPU2"],
        disk_path="/host",
        platform_json_path=path
    )


def test_check_dpu_image_install_free_disk_space_stops_on_first_failure(monkeypatch, tmp_path):
    """
    Verify that the function fails fast once a DPU below threshold is found.
    """
    path = write_platform_json(tmp_path, {
        "min_free_disk_in_gb_for_dpu_image": 12
    })

    checked_dpus = []

    def fake_get_dpu_free_disk_in_gb(dpu_name, disk_path, ssh_options=None):
        checked_dpus.append(dpu_name)
        return {
            "DPU0": 20,
            "DPU1": 8,
            "DPU2": 20,
        }[dpu_name]

    monkeypatch.setattr(
        image_disk_space,
        "get_dpu_free_disk_in_gb",
        fake_get_dpu_free_disk_in_gb
    )

    assert not image_disk_space.check_dpu_image_install_free_disk_space(
        ["DPU0", "DPU1", "DPU2"],
        disk_path="/host",
        platform_json_path=path
    )

    assert checked_dpus == ["DPU0", "DPU1"]


def test_check_image_install_free_disk_space_npu(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "check_npu_image_install_free_disk_space",
        lambda disk_path, platform_json_path: True
    )

    assert image_disk_space.check_image_install_free_disk_space(target="npu")


def test_check_image_install_free_disk_space_dpu(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "check_dpu_image_install_free_disk_space",
        lambda dpu_names, disk_path, platform_json_path, ssh_options=None: True
    )

    assert image_disk_space.check_image_install_free_disk_space(
        target="dpu",
        dpu_names=["DPU0"]
    )


def test_check_image_install_free_disk_space_dpu_without_dpu_names():
    assert not image_disk_space.check_image_install_free_disk_space(target="dpu")


def test_check_image_install_free_disk_space_invalid_target():
    assert not image_disk_space.check_image_install_free_disk_space(target="bad")


def test_is_smartswitch_true(monkeypatch):
    class DeviceInfo:
        @staticmethod
        def is_smartswitch():
            return True

    monkeypatch.setattr(image_disk_space, "device_info", DeviceInfo)

    assert image_disk_space.is_smartswitch()


def test_is_smartswitch_false_when_device_info_missing(monkeypatch):
    monkeypatch.setattr(image_disk_space, "device_info", None)

    assert not image_disk_space.is_smartswitch()


def test_is_smartswitch_exception(monkeypatch):
    class DeviceInfo:
        @staticmethod
        def is_smartswitch():
            raise RuntimeError("failed")

    monkeypatch.setattr(image_disk_space, "device_info", DeviceInfo)

    assert not image_disk_space.is_smartswitch()
