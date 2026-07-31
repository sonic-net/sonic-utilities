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
            image_disk_space.IMAGE_TYPE_COMMON,
            image_disk_space.SONIC_IMG_MIN_FREE_DISK_KEY,
            16,
        ),
        (
            image_disk_space.IMAGE_TYPE_DPU,
            image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY,
            14,
        ),
    ],
)
def test_get_min_free_disk_from_platform_json(
    tmp_path, image_type, key, value
):
    path = write_platform_json(tmp_path, {key: value})

    assert (
        image_disk_space.get_min_free_disk_in_gb(
            image_type,
            platform_json_path=path,
        )
        == value
    )


@pytest.mark.parametrize(
    "image_type",
    [
        image_disk_space.IMAGE_TYPE_COMMON,
        image_disk_space.IMAGE_TYPE_DPU,
    ],
)
def test_get_min_free_disk_missing_key_returns_none(
    tmp_path, image_type
):
    path = write_platform_json(tmp_path, {})

    assert (
        image_disk_space.get_min_free_disk_in_gb(
            image_type,
            platform_json_path=path,
        )
        is None
    )


@pytest.mark.parametrize("bad_value", [0, -1, "bad", None])
@pytest.mark.parametrize(
    "image_type,key",
    [
        (
            image_disk_space.IMAGE_TYPE_COMMON,
            image_disk_space.SONIC_IMG_MIN_FREE_DISK_KEY,
        ),
        (
            image_disk_space.IMAGE_TYPE_DPU,
            image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY,
        ),
    ],
)
def test_invalid_platform_json_value_returns_none(
    tmp_path,
    bad_value,
    image_type,
    key,
):
    path = write_platform_json(tmp_path, {key: bad_value})

    assert (
        image_disk_space.get_min_free_disk_in_gb(
            image_type,
            platform_json_path=path,
        )
        is None
    )


def test_missing_platform_json_returns_none():
    assert (
        image_disk_space.get_min_free_disk_in_gb(
            image_disk_space.IMAGE_TYPE_COMMON,
            platform_json_path="/bad/path/platform.json",
        )
        is None
    )


def test_invalid_platform_json_returns_none(tmp_path):
    path = tmp_path / "platform.json"
    path.write_text("{invalid-json")

    assert (
        image_disk_space.get_min_free_disk_in_gb(
            image_disk_space.IMAGE_TYPE_DPU,
            platform_json_path=str(path),
        )
        is None
    )


def test_get_min_free_disk_invalid_image_type():
    with pytest.raises(ValueError):
        image_disk_space.get_min_free_disk_in_gb("invalid")


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
        (False, image_disk_space.IMAGE_TYPE_COMMON),
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
        (image_disk_space.IMAGE_TYPE_COMMON, 20, True),
        (image_disk_space.IMAGE_TYPE_COMMON, 8, False),
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
            image_disk_space.SONIC_IMG_MIN_FREE_DISK_KEY: 12,
            image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY: 12,
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


def test_check_local_image_install_free_disk_space_auto_detects_common(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        image_disk_space,
        "get_local_image_type",
        lambda: image_disk_space.IMAGE_TYPE_COMMON,
    )

    def fake_get_threshold(image_type, platform_json_path):
        captured["image_type"] = image_type
        return 12

    monkeypatch.setattr(
        image_disk_space,
        "get_min_free_disk_in_gb",
        fake_get_threshold,
    )
    monkeypatch.setattr(
        image_disk_space,
        "get_free_disk_in_gb",
        lambda disk_path: 20,
    )

    assert image_disk_space.check_local_image_install_free_disk_space()
    assert captured["image_type"] == image_disk_space.IMAGE_TYPE_COMMON


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
        "get_min_free_disk_in_gb",
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
        ("Avail\n19327352832", 18 * GB),
        ("Available\n  26843545600\n", 25 * GB),
        ("Filesystem\n/dev/sda1\nAvail\n32212254720", 30 * GB),
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


def test_get_remote_dpu_free_disk_in_gb_success(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, "Avail\n19327352832"),
    )
    assert image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0") == 18


def test_get_remote_dpu_free_disk_in_gb_floors_partial_gib(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (0, "Avail\n4294967295"),
    )
    assert image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0") == 3


def test_get_remote_dpu_free_disk_in_gb_custom_ssh_options(monkeypatch):
    captured = {}

    def fake_run_cmd(cmd):
        captured["cmd"] = cmd
        return 0, "Avail\n19327352832"

    monkeypatch.setattr(image_disk_space, "_run_cmd", fake_run_cmd)
    assert image_disk_space.get_remote_dpu_free_disk_in_gb(
        "DPU0", ssh_options=["-o", "ConnectTimeout=3"]
    ) == 18
    assert captured["cmd"] == [
        "ssh",
        "-o",
        "ConnectTimeout=3",
        "DPU0",
        "df",
        "-B1",
        "--output=avail",
        "/host",
    ]


def test_get_remote_dpu_free_disk_in_gb_command_failure(monkeypatch):
    monkeypatch.setattr(
        image_disk_space, "_run_cmd", lambda cmd: (1, "ssh failed")
    )
    assert image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0") is None


@pytest.mark.parametrize("output", ["", "Avail\nbad"])
def test_get_remote_dpu_free_disk_in_gb_parse_failure(monkeypatch, output):
    monkeypatch.setattr(
        image_disk_space, "_run_cmd", lambda cmd: (0, output)
    )
    assert image_disk_space.get_remote_dpu_free_disk_in_gb("DPU0") is None


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
        {image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY: 12},
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
        {image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY: 12},
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
        {image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY: 12},
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
        {image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY: 12},
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
        {image_disk_space.DPU_IMG_MIN_FREE_DISK_KEY: 12},
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
    assert captured["image_type"] == image_disk_space.IMAGE_TYPE_COMMON


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


# ---------------------------------------------------------------------------
# DPU reboot storage policy / retention (issue #28734)
# ---------------------------------------------------------------------------


DPU_STORAGE_POLICY = {
    "reboot": {
        "disk_path": "/",
        "min_free_disk_in_gb": 4,
    },
    "retention": {
        "paths": {
            "/var/dump": {
                "max_size_in_gb": 4,
                "min_files_to_keep": 1,
                "min_file_age_minutes": 10,
            },
        },
    },
}


def test_get_dpu_storage_policy_present(tmp_path):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: DPU_STORAGE_POLICY},
    )

    assert (
        image_disk_space.get_dpu_storage_policy(platform_json_path=path)
        == DPU_STORAGE_POLICY
    )


def test_get_dpu_storage_policy_absent(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert (
        image_disk_space.get_dpu_storage_policy(platform_json_path=path)
        is None
    )


def test_get_dpu_storage_policy_not_a_dict(tmp_path):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: "invalid"},
    )

    assert (
        image_disk_space.get_dpu_storage_policy(platform_json_path=path)
        is None
    )


def test_select_retention_files_under_max_keeps_all():
    now = 1000.0
    files = [
        {"path": "/var/dump/a", "size": 1 * GB, "mtime": now - 3600},
        {"path": "/var/dump/b", "size": 1 * GB, "mtime": now - 7200},
    ]
    path_policy = {
        "max_size_in_gb": 4,
        "min_files_to_keep": 1,
        "min_file_age_minutes": 10,
    }

    assert image_disk_space.select_retention_files_to_delete(
        files, path_policy, now=now
    ) == []


def test_select_retention_deletes_oldest_first_until_under_max():
    now = 10000.0
    files = [
        {"path": "/var/dump/new", "size": 3 * GB, "mtime": now - 3600},
        {"path": "/var/dump/old", "size": 3 * GB, "mtime": now - 7200},
        {"path": "/var/dump/older", "size": 3 * GB, "mtime": now - 10800},
    ]
    path_policy = {
        "max_size_in_gb": 4,
        "min_files_to_keep": 1,
        "min_file_age_minutes": 10,
    }

    # Total is 9GB, must drop to <= 4GB: remove the two oldest (older, old).
    assert image_disk_space.select_retention_files_to_delete(
        files, path_policy, now=now
    ) == ["/var/dump/older", "/var/dump/old"]


def test_select_retention_respects_min_files_to_keep():
    now = 10000.0
    files = [
        {"path": "/var/dump/a", "size": 3 * GB, "mtime": now - 3600},
        {"path": "/var/dump/b", "size": 3 * GB, "mtime": now - 7200},
    ]
    path_policy = {
        "max_size_in_gb": 1,
        "min_files_to_keep": 1,
        "min_file_age_minutes": 10,
    }

    # Would need to delete both to get under 1GB, but must keep at least one.
    assert image_disk_space.select_retention_files_to_delete(
        files, path_policy, now=now
    ) == ["/var/dump/b"]


def test_select_retention_respects_min_file_age():
    now = 10000.0
    files = [
        {"path": "/var/dump/recent", "size": 5 * GB, "mtime": now - 60},
        {"path": "/var/dump/old", "size": 5 * GB, "mtime": now - 7200},
    ]
    path_policy = {
        "max_size_in_gb": 1,
        "min_files_to_keep": 0,
        "min_file_age_minutes": 10,
    }

    # "recent" is younger than 10 minutes, so only "old" may be deleted.
    assert image_disk_space.select_retention_files_to_delete(
        files, path_policy, now=now
    ) == ["/var/dump/old"]


def test_select_retention_missing_max_size_is_noop():
    now = 10000.0
    files = [
        {"path": "/var/dump/a", "size": 5 * GB, "mtime": now - 7200},
    ]

    assert image_disk_space.select_retention_files_to_delete(
        files, {"min_files_to_keep": 0}, now=now
    ) == []


def test_list_remote_dir_files_parses_output(monkeypatch):
    def fake_run_cmd(cmd):
        assert cmd[0] == "ssh"
        assert cmd[1] == "DPU0"
        assert "find" in cmd[-1]
        return 0, (
            "1000.5 1073741824 /var/dump/a\n"
            "2000.0 2147483648 /var/dump/b"
        )

    monkeypatch.setattr(image_disk_space, "_run_cmd", fake_run_cmd)

    files = image_disk_space._list_remote_dir_files(
        "DPU0", "/var/dump", ["DPU0"]
    )

    assert files == [
        {"path": "/var/dump/a", "size": 1073741824, "mtime": 1000.5},
        {"path": "/var/dump/b", "size": 2147483648, "mtime": 2000.0},
    ]


def test_list_remote_dir_files_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(
        image_disk_space,
        "_run_cmd",
        lambda cmd: (1, "No such file or directory"),
    )

    assert image_disk_space._list_remote_dir_files(
        "DPU0", "/var/dump", ["DPU0"]
    ) == []


def test_delete_remote_files_empty_is_noop(monkeypatch):
    called = {"count": 0}

    def fake_run_cmd(cmd):
        called["count"] += 1
        return 0, ""

    monkeypatch.setattr(image_disk_space, "_run_cmd", fake_run_cmd)

    assert image_disk_space._delete_remote_files("DPU0", [], ["DPU0"])
    assert called["count"] == 0


def test_delete_remote_files_builds_rm_command(monkeypatch):
    captured = {}

    def fake_run_cmd(cmd):
        captured["cmd"] = cmd
        return 0, ""

    monkeypatch.setattr(image_disk_space, "_run_cmd", fake_run_cmd)

    assert image_disk_space._delete_remote_files(
        "DPU0", ["/var/dump/a", "/var/dump/b"], []
    )
    assert captured["cmd"] == [
        "ssh",
        "DPU0",
        "rm -f -- /var/dump/a /var/dump/b",
    ]


def test_recover_remote_dpu_disk_space_lists_selects_deletes(monkeypatch):
    deleted = {}

    monkeypatch.setattr(
        image_disk_space,
        "_list_remote_dir_files",
        lambda dpu_name, path, ssh_options: [
            {"path": path + "/a", "size": 5 * GB, "mtime": 1},
        ],
    )

    def fake_delete(dpu_name, file_paths, ssh_options):
        deleted[dpu_name] = file_paths
        return True

    monkeypatch.setattr(
        image_disk_space, "_delete_remote_files", fake_delete
    )

    image_disk_space.recover_remote_dpu_disk_space(
        "DPU0",
        {
            "paths": {
                "/var/dump": {
                    "max_size_in_gb": 1,
                    "min_files_to_keep": 0,
                    "min_file_age_minutes": 0,
                }
            }
        },
        ["DPU0"],
    )

    assert deleted == {"DPU0": ["/var/dump/a"]}


def test_ensure_reboot_disk_space_no_policy_is_skipped(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )


def test_ensure_reboot_disk_space_no_reboot_section_is_skipped(tmp_path):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: {"retention": {}}},
    )

    assert image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )


def test_ensure_reboot_disk_space_sufficient_no_retention(
    monkeypatch, tmp_path
):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: DPU_STORAGE_POLICY},
    )
    recovered = {"called": False}

    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options: 10,
    )
    monkeypatch.setattr(
        image_disk_space,
        "recover_remote_dpu_disk_space",
        lambda *args, **kwargs: recovered.__setitem__("called", True),
    )

    assert image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )
    assert recovered["called"] is False


def test_ensure_reboot_disk_space_recovers_then_succeeds(
    monkeypatch, tmp_path
):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: DPU_STORAGE_POLICY},
    )
    free_values = iter([2, 8])

    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options: next(free_values),
    )
    recovered = {"called": False}
    monkeypatch.setattr(
        image_disk_space,
        "recover_remote_dpu_disk_space",
        lambda *args, **kwargs: recovered.__setitem__("called", True),
    )

    assert image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )
    assert recovered["called"] is True


def test_ensure_reboot_disk_space_still_insufficient_fails(
    monkeypatch, tmp_path
):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: DPU_STORAGE_POLICY},
    )

    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options: 2,
    )
    monkeypatch.setattr(
        image_disk_space,
        "recover_remote_dpu_disk_space",
        lambda *args, **kwargs: None,
    )

    assert not image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )


def test_ensure_reboot_disk_space_undeterminable_fails(
    monkeypatch, tmp_path
):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.DPU_STORAGE_POLICY_KEY: {
                "reboot": {"disk_path": "/", "min_free_disk_in_gb": 4}
            }
        },
    )

    monkeypatch.setattr(
        image_disk_space,
        "get_remote_dpu_free_disk_in_gb",
        lambda dpu_name, disk_path, ssh_options: None,
    )

    assert not image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )


@pytest.mark.parametrize("bad_value", [0, -1, "4GB", None])
def test_ensure_reboot_disk_space_invalid_threshold_fails(tmp_path, bad_value):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.DPU_STORAGE_POLICY_KEY: {
                "reboot": {"min_free_disk_in_gb": bad_value}
            }
        },
    )
    assert not image_disk_space.ensure_remote_dpu_reboot_disk_space(
        "DPU0", platform_json_path=path
    )


def test_ensure_operation_uses_requested_policy(monkeypatch, tmp_path):
    path = write_platform_json(
        tmp_path,
        {
            image_disk_space.DPU_STORAGE_POLICY_KEY: {
                "reboot": {"disk_path": "/reboot", "min_free_disk_in_gb": 4},
                "upgrade": {"disk_path": "/upgrade", "min_free_disk_in_gb": 9},
            }
        },
    )
    captured = {}

    def fake_free(dpu_name, disk_path, ssh_options):
        captured["disk_path"] = disk_path
        return 10

    monkeypatch.setattr(
        image_disk_space, "get_remote_dpu_free_disk_in_gb", fake_free
    )
    assert image_disk_space.ensure_remote_dpu_disk_space_for_operation(
        "DPU0", "upgrade", platform_json_path=path
    )
    assert captured["disk_path"] == "/upgrade"


def test_ensure_operation_invalid_section_fails(tmp_path):
    path = write_platform_json(
        tmp_path,
        {image_disk_space.DPU_STORAGE_POLICY_KEY: {"reboot": "invalid"}},
    )
    assert not image_disk_space.ensure_remote_dpu_disk_space_for_operation(
        "DPU0", "reboot", platform_json_path=path
    )
