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

DEFAULT_DISK_PATH = "/host"

IMAGE_TYPE_NPU = "npu"
IMAGE_TYPE_DPU = "dpu"

DEFAULT_SSH_OPTIONS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=no",
]


def get_default_platform_json_path() -> Optional[str]:
    """Return the platform.json path for the current platform."""
    if device_info is None:
        return None

    try:
        platform = device_info.get_platform()
    except Exception as error:
        logging.warning(
            "Failed to determine platform: %s",
            error,
        )
        return None

    if not platform:
        return None

    return f"/usr/share/sonic/device/{platform}/platform.json"


def _load_platform_json(
    platform_json_path: Optional[str] = None,
) -> Dict:
    if platform_json_path is None:
        platform_json_path = get_default_platform_json_path()

    if platform_json_path is None:
        logging.warning("Unable to determine platform.json path")
        return {}

    try:
        with open(platform_json_path, "r") as platform_json_file:
            return json.load(platform_json_file)
    except (OSError, ValueError, TypeError) as error:
        logging.warning(
            "Failed to read platform.json %s: %s",
            platform_json_path,
            error,
        )
        return {}


def _get_positive_int(
    data: Dict,
    key: str,
    default_value: int,
) -> int:
    try:
        value = data.get(key)
        if value is None:
            return default_value

        value = int(value)
        if value <= 0:
            logging.warning(
                "Invalid %s=%s, using default %s",
                key,
                value,
                default_value,
            )
            return default_value

        return value
    except (TypeError, ValueError) as error:
        logging.warning(
            "Failed to parse %s, using default %s: %s",
            key,
            default_value,
            error,
        )
        return default_value


def get_min_free_disk_in_gb_for_image(
    image_type: str,
    platform_json_path: Optional[str] = None,
) -> int:
    """
    Return the configured minimum free disk space for an image type.

    image_type:
        "npu" - NPU or regular switch image
        "dpu" - DPU image
    """
    platform_data = _load_platform_json(platform_json_path)

    if image_type == IMAGE_TYPE_NPU:
        return _get_positive_int(
            platform_data,
            NPU_MIN_FREE_DISK_KEY,
            MIN_FREE_DISK_IN_GB_FOR_NPU_IMAGE,
        )

    if image_type == IMAGE_TYPE_DPU:
        return _get_positive_int(
            platform_data,
            DPU_MIN_FREE_DISK_KEY,
            MIN_FREE_DISK_IN_GB_FOR_DPU_IMAGE,
        )

    raise ValueError("Unsupported image type: {}".format(image_type))


def get_free_disk_in_gb(
    path: str = DEFAULT_DISK_PATH,
) -> Optional[int]:
    if not os.path.exists(path):
        logging.warning("Disk path does not exist: %s", path)
        return None

    try:
        usage = shutil.disk_usage(path)
    except OSError as error:
        logging.warning(
            "Failed to get disk usage for %s: %s",
            path,
            error,
        )
        return None

    return usage.free // (1024 * 1024 * 1024)


def is_running_on_dpu() -> bool:
    """
    Return True when this utility is running on a DPU.
    """
    try:
        return bool(device_info and device_info.is_dpu())
    except Exception as error:
        logging.warning(
            "Failed to determine whether the system is a DPU: %s",
            error,
        )
        return False


def get_local_image_type() -> str:
    """
    Determine which image threshold applies to the local system.
    """
    if is_running_on_dpu():
        return IMAGE_TYPE_DPU

    return IMAGE_TYPE_NPU


def check_local_image_install_free_disk_space(
    image_type: Optional[str] = None,
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: Optional[str] = None,
) -> bool:
    """
    Check free disk space on the system where this function is running.

    When image_type is omitted, the function automatically determines
    whether it is running on an NPU/regular switch or on a DPU.
    """
    resolved_image_type = image_type or get_local_image_type()

    try:
        required_gb = get_min_free_disk_in_gb_for_image(
            resolved_image_type,
            platform_json_path,
        )
    except ValueError as error:
        logging.error("%s", error)
        return False

    available_gb = get_free_disk_in_gb(disk_path)

    if available_gb is None:
        logging.error(
            "Unable to determine local free disk space: "
            "image_type=%s path=%s",
            resolved_image_type,
            disk_path,
        )
        return False

    if available_gb < required_gb:
        logging.error(
            "Insufficient local disk space: "
            "image_type=%s available=%sGB required=%sGB path=%s",
            resolved_image_type,
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
    except subprocess.CalledProcessError as error:
        output = error.output or ""
        return error.returncode, output.strip()
    except OSError as error:
        return 1, str(error)


def _parse_df_available_gb(output: str) -> Optional[int]:
    """
    Parse output from:

        df -BG --output=avail <path>

    Expected output resembles:

        Avail
          18G
    """
    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    if len(lines) < 2:
        return None

    match = re.fullmatch(r"(\d+)G?", lines[-1])
    if not match:
        return None

    return int(match.group(1))


def get_remote_dpu_free_disk_in_gb(
    dpu_name: str,
    disk_path: str = DEFAULT_DISK_PATH,
    ssh_options: Optional[List[str]] = None,
) -> Optional[int]:
    """
    Get free disk space from a DPU reachable over SSH.
    """
    resolved_ssh_options = (
        ssh_options
        if ssh_options is not None
        else DEFAULT_SSH_OPTIONS
    )

    command = [
        "ssh",
        *resolved_ssh_options,
        dpu_name,
        "df",
        "-BG",
        "--output=avail",
        disk_path,
    ]

    return_code, output = _run_cmd(command)
    if return_code != 0:
        logging.warning(
            "Failed to get free disk space from %s: %s",
            dpu_name,
            output,
        )
        return None

    available_gb = _parse_df_available_gb(output)
    if available_gb is None:
        logging.warning(
            "Failed to parse disk space from %s: %s",
            dpu_name,
            output,
        )

    return available_gb


def check_remote_dpu_image_install_free_disk_space(
    dpu_names: Union[str, List[str]],
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: Optional[str] = None,
    ssh_options: Optional[List[str]] = None,
) -> bool:
    """
    Check one or more remote DPUs from an NPU.

    The complete check fails if any DPU has insufficient disk space or
    if the free disk space cannot be determined for any DPU.
    """
    if is_running_on_dpu():
        logging.error(
            "Remote DPU disk-space checks must be initiated from an NPU"
        )
        return False

    if isinstance(dpu_names, str):
        resolved_dpu_names = [dpu_names]
    else:
        resolved_dpu_names = dpu_names

    if not resolved_dpu_names:
        logging.error(
            "Remote DPU disk-space check requires at least one DPU name"
        )
        return False

    required_gb = get_min_free_disk_in_gb_for_image(
        IMAGE_TYPE_DPU,
        platform_json_path,
    )

    for dpu_name in resolved_dpu_names:
        available_gb = get_remote_dpu_free_disk_in_gb(
            dpu_name,
            disk_path,
            ssh_options,
        )

        if available_gb is None:
            logging.error(
                "Unable to determine free disk space for %s",
                dpu_name,
            )
            return False

        if available_gb < required_gb:
            logging.error(
                "Insufficient remote DPU disk space: "
                "dpu=%s available=%sGB required=%sGB path=%s",
                dpu_name,
                available_gb,
                required_gb,
                disk_path,
            )
            return False

    return True


def check_image_install_free_disk_space(
    dpu_names: Optional[Union[str, List[str]]] = None,
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: Optional[str] = None,
    ssh_options: Optional[List[str]] = None,
) -> bool:
    """
    Smart image-installation disk-space validation entry point.

    Behavior:

    Running on a DPU:
        Checks the local DPU using the DPU image threshold.

    Running on an NPU or regular switch without dpu_names:
        Checks the local system using the NPU image threshold.

    Running on an NPU with dpu_names:
        Checks the specified remote DPUs using the DPU image threshold.
    """
    if is_running_on_dpu():
        if dpu_names:
            logging.error(
                "dpu_names must not be supplied when running locally on a DPU"
            )
            return False

        return check_local_image_install_free_disk_space(
            image_type=IMAGE_TYPE_DPU,
            disk_path=disk_path,
            platform_json_path=platform_json_path,
        )

    if dpu_names:
        return check_remote_dpu_image_install_free_disk_space(
            dpu_names=dpu_names,
            disk_path=disk_path,
            platform_json_path=platform_json_path,
            ssh_options=ssh_options,
        )

    return check_local_image_install_free_disk_space(
        image_type=IMAGE_TYPE_NPU,
        disk_path=disk_path,
        platform_json_path=platform_json_path,
    )
