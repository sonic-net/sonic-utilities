# utilities_common/image_disk_space.py

import json
import logging
import os
import shlex
import shutil
import subprocess
import time
from typing import Dict, List, Optional, Tuple, Union

try:
    from sonic_py_common import device_info
except ImportError:
    device_info = None


# Minimum free disk (in GB) is read from platform.json. Common and DPU images
# have independent thresholds and may be configured at the same time. When the
# relevant key is absent the install check is skipped, so platforms that do not
# opt in are unaffected.
SONIC_IMG_MIN_FREE_DISK_KEY = "min_free_disk_in_gb_for_image"
DPU_IMG_MIN_FREE_DISK_KEY = "min_free_disk_in_gb_for_dpu_image"

# Optional DPU storage policy used by the smart-switch reboot flow. When
# platform.json defines "dpu_storage_policy" the DPU free disk space is
# validated before a reboot and, if a retention policy is configured, space is
# recovered automatically. Platforms that do not define the policy keep their
# existing behavior.
DPU_STORAGE_POLICY_KEY = "dpu_storage_policy"

DEFAULT_DISK_PATH = "/host"

IMAGE_TYPE_COMMON = "common"
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


def _get_optional_positive_int(
    data: Dict,
    key: str,
) -> Optional[int]:
    """
    Return a positive integer for key, or None when the key is absent or
    invalid. A None result tells callers to skip the disk-space check.
    """
    value = data.get(key)
    if value is None:
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        logging.warning("Invalid value for %s: %r", key, value)
        return None

    if value <= 0:
        logging.warning("Non-positive value for %s: %s", key, value)
        return None

    return value


def get_min_free_disk_in_gb(
    image_type: str,
    platform_json_path: Optional[str] = None,
) -> Optional[int]:
    """
    Return the configured minimum free disk space (in GB) for an image type,
    or None when platform.json does not define the corresponding key (in which
    case the install check is skipped).

    image_type:
        "common" - local/common image threshold
        "dpu"    - DPU image threshold
    """
    platform_data = _load_platform_json(platform_json_path)

    if image_type == IMAGE_TYPE_COMMON:
        return _get_optional_positive_int(
            platform_data, SONIC_IMG_MIN_FREE_DISK_KEY
        )

    if image_type == IMAGE_TYPE_DPU:
        return _get_optional_positive_int(
            platform_data, DPU_IMG_MIN_FREE_DISK_KEY
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

    return IMAGE_TYPE_COMMON


def check_local_image_install_free_disk_space(
    image_type: Optional[str] = None,
    disk_path: str = DEFAULT_DISK_PATH,
    platform_json_path: Optional[str] = None,
) -> bool:
    """
    Check free disk space on the system where this function is running.

    When image_type is omitted it is auto-detected (DPU vs. common). The check
    is skipped (returns True) when platform.json does not configure the
    corresponding threshold.
    """
    resolved_image_type = image_type or get_local_image_type()

    try:
        required_gb = get_min_free_disk_in_gb(
            resolved_image_type,
            platform_json_path,
        )
    except ValueError as error:
        logging.error("%s", error)
        return False

    if required_gb is None:
        logging.info(
            "No min free disk configured for %s image; skipping install check",
            resolved_image_type,
        )
        return True

    available_gb = get_free_disk_in_gb(disk_path)

    if available_gb is None:
        logging.error(
            "Unable to determine local free disk space: path=%s",
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


def _parse_df_available_bytes(output: str) -> Optional[int]:
    """Parse the available-byte value from ``df -B1 --output=avail``."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    try:
        available_bytes = int(lines[-1])
    except ValueError:
        return None

    return available_bytes if available_bytes >= 0 else None


def get_remote_dpu_free_disk_in_gb(
    dpu_name: str,
    disk_path: str = DEFAULT_DISK_PATH,
    ssh_options: Optional[List[str]] = None,
) -> Optional[int]:
    """Get remote DPU free space, flooring exact bytes to whole GiB."""
    resolved_ssh_options = (
        ssh_options if ssh_options is not None else DEFAULT_SSH_OPTIONS
    )
    command = [
        "ssh",
        *resolved_ssh_options,
        dpu_name,
        "df",
        "-B1",
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

    available_bytes = _parse_df_available_bytes(output)
    if available_bytes is None:
        logging.warning(
            "Failed to parse disk space from %s: %s",
            dpu_name,
            output,
        )
        return None

    return available_bytes // (1024 ** 3)


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

    required_gb = get_min_free_disk_in_gb(
        IMAGE_TYPE_DPU,
        platform_json_path,
    )

    if required_gb is None:
        logging.info(
            "%s is not configured; skipping remote DPU check",
            DPU_IMG_MIN_FREE_DISK_KEY,
        )
        return True

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
        Checks the local DPU.

    Running on a switch without dpu_names:
        Checks the local system.

    Running on a switch with dpu_names:
        Checks the specified remote DPUs.
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
        image_type=IMAGE_TYPE_COMMON,
        disk_path=disk_path,
        platform_json_path=platform_json_path,
    )


def get_dpu_storage_policy(
    platform_json_path: Optional[str] = None,
) -> Optional[Dict]:
    """
    Return the "dpu_storage_policy" object from platform.json, or None when it
    is not defined. A None result tells callers to skip the reboot disk-space
    check so platforms without the policy are unaffected.
    """
    platform_data = _load_platform_json(platform_json_path)
    policy = platform_data.get(DPU_STORAGE_POLICY_KEY)
    if isinstance(policy, dict):
        return policy
    return None


def select_retention_files_to_delete(
    files: List[Dict],
    path_policy: Dict,
    now: Optional[float] = None,
) -> List[str]:
    """
    Decide which files to delete from a single retention path.

    files:
        list of {"path": str, "size": int (bytes), "mtime": float (epoch)}
    path_policy:
        {
            "max_size_in_gb": int,       # target maximum total size for path
            "min_files_to_keep": int,    # never delete below this many files
            "min_file_age_minutes": int, # only delete files older than this
        }

    Oldest eligible files are removed first until the total size is at or below
    max_size_in_gb, while always keeping at least min_files_to_keep files and
    never deleting files younger than min_file_age_minutes.
    """
    max_size_in_gb = _get_optional_positive_int(path_policy, "max_size_in_gb")
    if max_size_in_gb is None:
        return []

    if now is None:
        now = time.time()

    try:
        min_files_to_keep = max(int(path_policy.get("min_files_to_keep", 0)), 0)
    except (TypeError, ValueError):
        min_files_to_keep = 0

    try:
        min_file_age_minutes = max(
            int(path_policy.get("min_file_age_minutes", 0)), 0
        )
    except (TypeError, ValueError):
        min_file_age_minutes = 0

    age_cutoff = now - (min_file_age_minutes * 60)
    max_size_bytes = max_size_in_gb * (1024 ** 3)

    total_size = sum(int(entry.get("size", 0)) for entry in files)
    remaining = len(files)

    # Oldest files first.
    ordered = sorted(files, key=lambda entry: entry.get("mtime", 0))

    to_delete = []
    for entry in ordered:
        if total_size <= max_size_bytes:
            break
        if remaining <= min_files_to_keep:
            break
        if entry.get("mtime", 0) > age_cutoff:
            # File is newer than the minimum age; do not delete it.
            continue

        to_delete.append(entry["path"])
        total_size -= int(entry.get("size", 0))
        remaining -= 1

    return to_delete


def _list_remote_dir_files(
    dpu_name: str,
    path: str,
    ssh_options: List[str],
) -> List[Dict]:
    """
    List regular files under a directory on a remote DPU.

    Returns a list of {"path", "size", "mtime"} entries. A missing directory or
    a listing failure yields an empty list.
    """
    remote_cmd = "find {} -type f -printf '%T@ %s %p\\n'".format(
        shlex.quote(path)
    )
    return_code, output = _run_cmd(
        ["ssh", *ssh_options, dpu_name, remote_cmd]
    )
    if return_code != 0:
        logging.info(
            "Unable to list %s on %s (it may not exist): %s",
            path,
            dpu_name,
            output,
        )
        return []

    files = []
    for line in output.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) != 3:
            continue
        mtime_str, size_str, file_path = parts
        try:
            files.append(
                {
                    "path": file_path,
                    "size": int(size_str),
                    "mtime": float(mtime_str),
                }
            )
        except ValueError:
            continue
    return files


def _delete_remote_files(
    dpu_name: str,
    file_paths: List[str],
    ssh_options: List[str],
) -> bool:
    """Delete the given files on a remote DPU. Returns True on success."""
    if not file_paths:
        return True

    quoted = " ".join(shlex.quote(file_path) for file_path in file_paths)
    remote_cmd = "rm -f -- {}".format(quoted)
    return_code, output = _run_cmd(
        ["ssh", *ssh_options, dpu_name, remote_cmd]
    )
    if return_code != 0:
        logging.warning(
            "Failed to delete files on %s: %s",
            dpu_name,
            output,
        )
        return False
    return True


def recover_remote_dpu_disk_space(
    dpu_name: str,
    retention_policy: Dict,
    ssh_options: List[str],
) -> None:
    """
    Apply the retention policy on a remote DPU to free disk space.

    Each configured path is trimmed independently; a failure for one path does
    not prevent the remaining paths from being processed.
    """
    paths = retention_policy.get("paths")
    if not isinstance(paths, dict):
        return

    for path, path_policy in paths.items():
        if not isinstance(path_policy, dict):
            continue

        files = _list_remote_dir_files(dpu_name, path, ssh_options)
        if not files:
            continue

        to_delete = select_retention_files_to_delete(files, path_policy)
        if not to_delete:
            continue

        logging.info(
            "Applying retention on %s:%s, removing %d file(s)",
            dpu_name,
            path,
            len(to_delete),
        )
        _delete_remote_files(dpu_name, to_delete, ssh_options)


def ensure_remote_dpu_disk_space_for_operation(
    dpu_name: str,
    operation: str,
    platform_json_path: Optional[str] = None,
    ssh_options: Optional[List[str]] = None,
) -> bool:
    """Validate and, when configured, recover DPU space for an operation."""
    policy = get_dpu_storage_policy(platform_json_path)
    if not policy:
        logging.info(
            "dpu_storage_policy is not configured; skipping %s disk-space "
            "check for %s",
            operation,
            dpu_name,
        )
        return True

    operation_policy = policy.get(operation)
    if operation_policy is None:
        logging.info(
            "dpu_storage_policy.%s is not configured; skipping disk-space "
            "check for %s",
            operation,
            dpu_name,
        )
        return True
    if not isinstance(operation_policy, dict):
        logging.error("dpu_storage_policy.%s must be an object", operation)
        return False

    threshold_key = "min_free_disk_in_gb"
    if threshold_key not in operation_policy:
        logging.info(
            "dpu_storage_policy.%s.%s is not configured; skipping disk-space "
            "check for %s",
            operation,
            threshold_key,
            dpu_name,
        )
        return True

    required_gb = _get_optional_positive_int(operation_policy, threshold_key)
    if required_gb is None:
        logging.error(
            "Invalid dpu_storage_policy.%s.%s",
            operation,
            threshold_key,
        )
        return False

    disk_path = operation_policy.get("disk_path", DEFAULT_DISK_PATH)
    if not isinstance(disk_path, str) or not disk_path:
        logging.error("Invalid dpu_storage_policy.%s.disk_path", operation)
        return False

    resolved_ssh_options = (
        ssh_options if ssh_options is not None else DEFAULT_SSH_OPTIONS
    )
    available_gb = get_remote_dpu_free_disk_in_gb(
        dpu_name, disk_path, resolved_ssh_options
    )
    if available_gb is not None and available_gb >= required_gb:
        return True

    retention_policy = policy.get("retention")
    if isinstance(retention_policy, dict):
        logging.info(
            "Insufficient free disk on %s before %s "
            "(available=%sGB required=%sGB); applying retention policy",
            dpu_name,
            operation,
            available_gb,
            required_gb,
        )
        recover_remote_dpu_disk_space(
            dpu_name, retention_policy, resolved_ssh_options
        )
        available_gb = get_remote_dpu_free_disk_in_gb(
            dpu_name, disk_path, resolved_ssh_options
        )

    if available_gb is None:
        logging.error("Unable to determine free disk space on %s", dpu_name)
        return False
    if available_gb < required_gb:
        logging.error(
            "Insufficient free disk on %s after retention: "
            "available=%sGB required=%sGB path=%s operation=%s",
            dpu_name,
            available_gb,
            required_gb,
            disk_path,
            operation,
        )
        return False

    return True


def ensure_remote_dpu_reboot_disk_space(
    dpu_name: str,
    platform_json_path: Optional[str] = None,
    ssh_options: Optional[List[str]] = None,
) -> bool:
    """Compatibility wrapper for the reboot disk-space policy."""
    return ensure_remote_dpu_disk_space_for_operation(
        dpu_name=dpu_name,
        operation="reboot",
        platform_json_path=platform_json_path,
        ssh_options=ssh_options,
    )
