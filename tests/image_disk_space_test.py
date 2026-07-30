# tests/image_disk_space_test.py

import json
import subprocess

import pytest

from utilities_common import image_disk_space


GB = 1024 * 1024 * 1024


def write_platform_json(tmp_path, data):
    """Write platform data to a temporary platform.json file."""
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.mark.parametrize(
    "image_type,key,value",
    [
        (
            image_disk_space.IMAGE_TYPE_NPU,
            image_disk_space.NPU_MIN_FREE_DISK_KEY,
            16,
        ),
        (
            image_disk_space.IMAGE_TYPE_DPU,
            image_disk_space.DPU_MIN_FREE_DISK_KEY,
            14,
        ),
    ],
)
def test_get_min_free_disk_from_platform_json(
    tmp_path, image_type, key, value
):
    path = write_platform_json(tmp_path, {key: value})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_image(
            image_type,
            platform_json_path=path,
        )
        == value
    )


@pytest.mark.parametrize(
    "image_type,default_value",
    [
        (
            image_disk_space.IMAGE_TYPE_NPU,
            image_disk_space.MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE,
        ),
        (
            image_disk_space.IMAGE_TYPE_DPU,
            image_disk_space.MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE,
        ),
    ],
)
def test_get_min_free_disk_missing_key_uses_default(
    tmp_path, image_type, default_value
):
    path = write_platform_json(tmp_path, {})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_image(
            image_type,
            platform_json_path=path,
        )
        == default_value
    )


@pytest.mark.parametrize("bad_value", [0, -1, "bad", None])
@pytest.mark.parametrize(
    "image_type,key,default_value",
    [
        (
            image_disk_space.IMAGE_TYPE_NPU,
            image_disk_space.NPU_MIN_FREE_DISK_KEY,
            image_disk_space.MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE,
        ),
        (
            image_disk_space.IMAGE_TYPE_DPU,
            image_disk_space.DPU_MIN_FREE_DISK_KEY,
            image_disk_space.MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE,
        ),
    ],
)
def test_invalid_platform_json_value_uses_default(
    tmp_path,
    bad_value,
    image_type,
    key,
    default_value,
):
    path = write_platform_json(tmp_path, {key: bad_value})

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_image(
            image_type,
            platform_json_path=path,
        )
        == default_value
    )


def test_missing_platform_json_uses_default():
    assert (
        image_disk_space.get_min_free_disk_in_gb_for_image(
            image_disk_space.IMAGE_TYPE_NPU,
            platform_json_path="/bad/path/platform.json",
        )
        == image_disk_space.MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE
    )


def test_invalid_platform_json_uses_default(tmp_path):
    path = tmp_path / "platform.json"
    path.write_text("{invalid-json")

    assert (
        image_disk_space.get_min_free_disk_in_gb_for_image(
            image_disk_space.IMAGE_TYPE_DPU,
            platform_json_path=str(path),
        )
        == image_disk_space.MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE
    )


def test_get_min_free_disk_invalid_image_type():
    with pytest.raises(ValueError):
        image_disk_space.get_min_free_disk_in_gb_for_image("invalid")


def test_get_free_disk_in_gb_success(monkeypatch):
    class Usage:
        free = 20 * GB

    monkeypatch.setattr(
        image_disk_space.os.path,
        "exists",
        lambda path: True,
    )
    monkeypatch.setattr(
        image_disk_space.shutil,
        "disk_usage",
        lambda path: Usage,
    )

    assert image_disk_space.get_free_disk_in_gb("/host") == 20


def test_get_free_disk_in_gb_missing_path(monkeypatch):
    monkeypatch.setattr(
        image_disk_space.os.path,
        "exists",
        lambda path: False,
    )

    assert image_disk_space.get_free_disk_in_gb("/missing") is None


def test_get_free_disk_in_gb_disk_usage_failure(monkeypatch):
    def raise_error(path):
        raise OSError("disk usage failed")

    monkeypatch.setattr(
        image_disk_space.os.path,
        "exists",
        lambda path: True,
    )
    monkeypatch.setattr(
        image_disk_space.shutil,
        "disk_usage",
        raise_error,
    )

    assert image_disk_space.get_free_disk_in_gb("/host") is None


def test_is_running_on_dpu_true(monkeypatch):
    class DeviceInfo:
        @staticmethod
        def is_dpu():
            return True

    monkeypatch.setattr(image_disk_space, "device_info", DeviceInfo)

    assert image_disk_space.is_running_on_dpu()


def test_is_running_on_dpu_false(monkeypatch):
    class DeviceInfo:
        @staticmethod
        def is_dpu():
            return False

    monkeypatch.setattr(image_disk_space, "device_info", DeviceInfo)

    assert not image_disk_space.is_running_on_dpu()


def test_is_running_on_dpu_false_when_device_info_missing(monkeypatch):
    monkeypatch.setattr(image_disk_space, "device_info", None)

    assert not image_disk_space.is_running_on_dpu()


def test_is_running_on_dpu_exception(monkeypatch):
    class DeviceInfo:
        @staticmethod
        def is_dpu():
            raise RuntimeError("failed")

    monkeypatch.setattr(image_disk_space, "device_info", DeviceInfo)

    assert not image_disk_space.is_running_on_dpu()


@pytest.mark.parametrize(
    "running_on_dpu,expected_type",
    [
        (False, image_disk_space.IMAGE_TYPE_NPU),
        (True, image_disk_space.IMAGE_TYPE_DPU),
    ],
)
def test_get_local_image_type(
    monkeypatch, running_on_dpu, expected_type
):
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: running_on_dpu,
    )

    assert image_disk_space.get_local_image_type() == expected_type


@pytest.mark.parametrize(
    "image_type,available_gb,expected",
    [
        (image_disk_space.IMAGE_TYPE_NPU, 20, True),
        (image_disk_space.IMAGE_TYPE_NPU, 8, False),
        (image_disk_space.IMAGE_TYPE_DPU, 20, True),
        (image_disk_space.IMAGE_TYPE_DPU, 8, False),
        (image_disk_space.IMAGE_TYPE_DPU, None, False),
    ],
)
def test_check_local_image_install_free_disk_space(
    monkeypatch,
    tmp_path,
    image_type,
    available_gb,
    expected,
):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.NPU_MIN_FREE_DISK_KEY: 12,
            image_disk_space.DPU_MIN_FREE_DISK_KEY: 12,
        },
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_free_disk_in_gb",
        lambda disk_path: available_gb,
    )

    result = image_disk_space.check_local_image_install_free_disk_space(
        image_type=image_type,
        disk_path="/host",
        platform_json_path=path,
    )

    assert result is expected


def test_check_local_image_install_free_disk_space_auto_detects_npu(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        image_disk_space,
        "get_local_image_type",
        lambda: image_disk_space.IMAGE_TYPE_NPU,
    )

    def fake_get_threshold(image_type, platform_json_path):
        captured["image_type"] = image_type
        return 12

    monkeypatch.setattr(
        image_disk_space,
        "get_min_free_disk_in_gb_for_image",
        fake_get_threshold,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_free_disk_in_gb",
        lambda disk_path: 20,
    )

    assert image_disk_space.check_local_image_install_free_disk_space()
    assert captured["image_type"] == image_disk_space.IMAGE_TYPE_NPU


def test_check_local_image_install_free_disk_space_auto_detects_dpu(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        image_disk_space,
        "get_local_image_type",
        lambda: image_disk_space.IMAGE_TYPE_DPU,
    )

    def fake_get_threshold(image_type, platform_json_path):
        captured["image_type"] = image_type
        return 12

    monkeypatch.setattr(
        image_disk_space,
        "get_min_free_disk_in_gb_for_image",
        fake_get_threshold,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_free_disk_in_gb",
        lambda disk_path: 20,
    )

    assert image_disk_space.check_local_image_install_free_disk_space()
    assert captured["image_type"] == image_disk_space.IMAGE_TYPE_DPU


def test_check_local_image_install_free_disk_space_invalid_type():
    assert not image_disk_space.check_local_image_install_free_disk_space(
        image_type="invalid"
    )


def test_run_cmd_success(monkeypatch):
    monkeypatch.setattr(
        image_disk_space.subprocess,
        "check_output",
        lambda *args, **kwargs: "Avail\n20G\n",
    )

    rc, output = image_disk_space._run_cmd(["dummy"])

    assert rc == 0
    assert output == "Avail\n20G"


def test_run_cmd_called_process_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise subprocess.CalledProcessError(
            1,
            "cmd",
            output="error",
        )

    monkeypatch.setattr(
        image_disk_space.subprocess,
        "check_output",
        raise_error,
    )

    rc, output = image_disk_space._run_cmd(["dummy"])

    assert rc == 1
    assert output == "error"


def test_run_cmd_os_error(monkeypatch):
    def raise_error(*args, **kwargs):
        raise OSError("command unavailable")

    monkeypatch.setattr(
        image_disk_space.subprocess,
        "check_output",
        raise_error,
    )

    rc, output = image_disk_space._run_cmd(["dummy"])

    assert rc == 1
    assert output == "command unavailable"


@pytest.mark.parametrize(
    "output,expected",
    [
        ("Avail\n18G", 18),
        ("Avail\n18", 18),
        ("Available\n  25G\n", 25),
        ("Filesystem\n/dev/sda1\nAvail\n30G", 30),
    ],
)
def test_parse_df_available_gb_success(output, expected):
    assert image_disk_space._parse_df_available_gb(output) == expected


@pytest.mark.parametrize(
    "output",
    [
        "",
        "Avail",
        "Avail\nbad",
        "Avail\n18GB",
        "Avail\n18.5G",
    ],
)
def test_parse_df_available_gb_failure(output):
    assert image_disk_space._parse_df_available_gb(output) is None


def test_get_remote_dpu_free_disk_in_gb_success(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, "Avail\n18G"),
    )

    assert (
        image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0")
        == 18
    )


def test_get_remote_dpu_free_disk_in_gb_custom_ssh_options(
    monkeypatch,
):
    captured = {}

    def fake_run_cmd(cmd):
        captured["cmd"] = cmd
        return 0, "Avail\n18G"

    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        fake_run_cmd,
    )

    assert (
        image_disk_space.get_remote_dpu_free_disk_in_gb(
            "DPU0",
            ssh_options=["-o", "ConnectTimeout=3"],
        )
        == 18
    )
    assert captured["cmd"] == [
        "ssh",
        "-o",
        "ConnectTimeout=3",
        "DPU0",
        "df",
        "-BG",
        "--output=avail",
        "/host",
    ]


def test_get_remote_dpu_free_disk_in_gb_command_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (1, "ssh failed"),
    )

    assert (
        image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0")
        is None
    )


@pytest.mark.parametrize("output", ["", "Avail\nbad"])
def test_get_remote_dpu_free_disk_in_gb_parse_failure(
    monkeypatch, output
):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, output),
    )

    assert (
        image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0")
        is None
    )


def test_remote_dpu_check_rejected_when_running_on_dpu(
    monkeypatch,
):
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: True,
    )

    assert not (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space("DPU0")
    )


def test_remote_dpu_check_requires_name(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )

    assert not (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space([])
    )


def test_remote_dpu_check_single_success(monkeypatch, tmp_path):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_MIN_FREE_DISK_KEY: 12},
    )
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: 20,
    )

    assert (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space(
            "DPU0",
            disk_path="/host",
            platform_json_path=path,
        )
    )


def test_remote_dpu_check_multi_success(monkeypatch, tmp_path):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_MIN_FREE_DISK_KEY: 12},
    )
    free_space = {
        "DPU0": 20,
        "DPU1": 18,
        "DPU2": 16,
    }
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: (
            free_space[dpu_name]
        ),
    )

    assert (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space(
            ["DPU0", "DPU1", "DPU2"],
            disk_path="/host",
            platform_json_path=path,
        )
    )


@pytest.mark.parametrize("available_gb", [8, None])
def test_remote_dpu_check_failure(
    monkeypatch, tmp_path, available_gb
):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_MIN_FREE_DISK_KEY: 12},
    )
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: available_gb,
    )

    assert not (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space(
            ["DPU0"],
            disk_path="/host",
            platform_json_path=path,
        )
    )


def test_remote_dpu_check_mixed_results_fail(
    monkeypatch, tmp_path
):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_MIN_FREE_DISK_KEY: 12},
    )
    free_space = {
        "DPU0": 20,
        "DPU1": 8,
        "DPU2": 18,
    }
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options=None: (
            free_space[dpu_name]
        ),
    )

    assert not (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space(
            ["DPU0", "DPU1", "DPU2"],
            disk_path="/host",
            platform_json_path=path,
        )
    )


def test_remote_dpu_check_stops_on_first_failure(
    monkeypatch, tmp_path
):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_MIN_FREE_DISK_KEY: 12},
    )
    checked_dpus = []

    def fake_get_remote_disk(
        dpu_name,
        disk_path,
        ssh_options=None,
    ):
        checked_dpus.append(dpu_name)
        return {
            "DPU0": 20,
            "DPU1": 8,
            "DPU2": 20,
        }[dpu_name]

    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        fake_get_remote_disk,
    )

    assert not (
        image_disk_space
        .check_remote_dpu_image_install_free_disk_space(
            ["DPU0", "DPU1", "DPU2"],
            disk_path="/host",
            platform_json_path=path,
        )
    )
    assert checked_dpus == ["DPU0", "DPU1"]


def test_smart_check_local_npu(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )

    def fake_local_check(
        image_type=None,
        disk_path=image_disk_space.DEFAULT_DISK_PATH,
        platform_json_path=None,
    ):
        captured["image_type"] = image_type
        return True

    monkeypatch.setattr(
        image_disk_space,
        "check_local_image_install_free_disk_space",
        fake_local_check,
    )

    assert image_disk_space.check_image_install_free_disk_space()
    assert captured["image_type"] == image_disk_space.IMAGE_TYPE_NPU


def test_smart_check_local_dpu(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: True,
    )

    def fake_local_check(
        image_type=None,
        disk_path=image_disk_space.DEFAULT_DISK_PATH,
        platform_json_path=None,
    ):
        captured["image_type"] = image_type
        return True

    monkeypatch.setattr(
        image_disk_space,
        "check_local_image_install_free_disk_space",
        fake_local_check,
    )

    assert image_disk_space.check_image_install_free_disk_space()
    assert captured["image_type"] == image_disk_space.IMAGE_TYPE_DPU


def test_smart_check_remote_dpus_from_npu(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: False,
    )

    def fake_remote_check(
        dpu_names,
        disk_path=image_disk_space.DEFAULT_DISK_PATH,
        platform_json_path=None,
        ssh_options=None,
    ):
        captured["dpu_names"] = dpu_names
        return True

    monkeypatch.setattr(
        image_disk_space,
        "check_remote_dpu_image_install_free_disk_space",
        fake_remote_check,
    )

    assert image_disk_space.check_image_install_free_disk_space(
        dpu_names=["DPU0", "DPU1"]
    )
    assert captured["dpu_names"] == ["DPU0", "DPU1"]


def test_smart_check_rejects_dpu_names_on_dpu(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "is_running_on_dpu",
        lambda: True,
    )

    assert not image_disk_space.check_image_install_free_disk_space(
        dpu_names=["DPU0"]
    )
