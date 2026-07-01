# utilities_common/image_disk_space.py

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple, Union

try:
    from sonic_py_common import device_info
except ImportError:
    device_info = None


MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE = 12
MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE = 12

NPU_MIN_FREE_DISK_KEY = "min_free_disk_in_gb_for_npu_image"
DPU_MIN_FREE_DISK_KEY = "min_free_disk_in_gb_for_dpu_image"

DEFAULT_PLATFORM_JSON = "/usr/share/sonic/platform/platform.json"
DEFAULT_DISK_PATH = "/host"

DEFAULT_SSH_OPTIONS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=no",
]


def _load_platform_json(platform_json_path: str = DEFAULT_PLATFORM_JSON) -> Dict:
    try:
        with open(platform_json_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.warning("Failed to read platform.json %s: %s", platform_json_path, e)
        return {}


def _get_positive_int(data: Dict, key: str, default_value: int) -> int:
    try:
        value = data.get(key)
        if value is None:
            return default_value

        value = int(value)
        if value <= 0:
            logging.warning("Invalid %s=%s, using default %s", key, value, default_value)
            return default_value

        return value
    except Exception as e:
        logging.warning("Failed to parse %s, using default %s: %s", key, default_value, e)
        return default_value


def get_min_free_disk_in_gb_for_npu_image(
    platform_json_path: str = DEFAULT_PLATFORM_JSON
) -> int:
    return _get_positive_int(
        _load_platform_json(platform_json_path),
        NPU_MIN_FREE_DISK_KEY,
        MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE,
    )


def get_min_free_disk_in_gb_for_dpu_image(
    platform_json_path: str = DEFAULT_PLATFORM_JSON
) -> int:
    return _get_positive_int(
        _load_platform_json(platform_json_path),
        DPU_MIN_FREE_DISK_KEY,
        MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE,
    )


def get_free_disk_in_gb(path: str = DEFAULT_DISK_PATH) -> Optional[int]:
    if not os.path.exists(path):
        logging.warning("Disk path does not exist: %s", path)
        return None

    usage = shutil.disk_usage(path)
    return usage.free // (1024 * 1024 * 1024)


def check_npu_image_install_free_disk_space(
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: str = DEFAULT_PLATFORM_JSON,
) -> bool:
    required_gb = get_min_free_disk_in_gb_for_npu_image(platform_json_path)
    available_gb = get_free_disk_in_gb(disk_path)

    if available_gb is None or available_gb < required_gb:
        logging.error(
            "Insufficient NPU disk space: available=%sGB required=%sGB path=%s",
            available_gb,
            required_gb,
            disk_path,
        )
        return False

    return True


def _run_cmd(cmd: List[str]) -> Tuple[int, str]:
    try:
        output = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        return 0, output.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()


def _parse_df_available_gb(output: str) -> Optional[int]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    value = lines[-1]
    match = re.search(r"(\d+)", value)
    if not match:
        return None

    return int(match.group(1))


def get_dpu_free_disk_in_gb(
    dpu_name: str,
    disk_path: str = DEFAULT_DISK_PATH,
    ssh_options: Optional[List[str]] = None,
) -> Optional[int]:
    ssh_options = ssh_options if ssh_options is not None else DEFAULT_SSH_OPTIONS

    cmd = [
        "ssh",
        *ssh_options,
        dpu_name,
        "df",
        "-BG",
        "--output=avail",
        disk_path,
    ]

    rc, output = _run_cmd(cmd)
    if rc != 0:
        logging.warning("Failed to get free disk space from %s: %s", dpu_name, output)
        return None

    available_gb = _parse_df_available_gb(output)
    if available_gb is None:
        logging.warning("Failed to parse disk space from %s output=%s", dpu_name, output)

    return available_gb


def check_dpu_image_install_free_disk_space(
    dpu_names: Union[str, List[str]],
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: str = DEFAULT_PLATFORM_JSON,
    ssh_options: Optional[List[str]] = None,
) -> bool:
    if isinstance(dpu_names, str):
        dpu_names = [dpu_names]

    required_gb = get_min_free_disk_in_gb_for_dpu_image(platform_json_path)

    for dpu_name in dpu_names:
        available_gb = get_dpu_free_disk_in_gb(dpu_name, disk_path, ssh_options)

        if available_gb is None or available_gb < required_gb:
            logging.error(
                "Insufficient DPU disk space: dpu=%s available=%sGB required=%sGB path=%s",
                dpu_name,
                available_gb,
                required_gb,
                disk_path,
            )
            return False

    return True


def check_image_install_free_disk_space(
    target: str = "npu",
    dpu_names: Optional[Union[str, List[str]]] = None,
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: str = DEFAULT_PLATFORM_JSON,
    ssh_options: Optional[List[str]] = None,
) -> bool:
    target = target.lower()

    if target == "npu":
        return check_npu_image_install_free_disk_space(disk_path, platform_json_path)

    if target == "dpu":
        if not dpu_names:
            logging.error("DPU image disk-space check requires dpu_names")
            return False

        return check_dpu_image_install_free_disk_space(
            dpu_names,
            disk_path,
            platform_json_path,
            ssh_options,
        )

    logging.error("Unsupported image install target: %s", target)
    return False


def is_smartswitch() -> bool:
    try:
        return bool(device_info and device_info.is_smartswitch())
    except Exception as e:
        logging.warning("Failed to determine smartswitch platform: %s", e)
        return False
