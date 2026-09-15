# utilities_common/swap_mem.py

import logging
from typing import Optional

from utilities_common.image_disk_space import (
    get_optional_positive_int,
    load_platform_json,
)

MIN_SWAP_MEM_SIZE_KEY = "min_swap_mem_size_in_mb"
MIN_TOTAL_MEM_THRESHOLD_KEY = "min_total_mem_threshold_in_mb"


def _get_platform_minimum(
    key: str,
    platform_json_path: Optional[str] = None,
) -> Optional[int]:
    """Return an optional platform minimum, in MiB.

    A missing or invalid key leaves the value unchanged, preserving the
    existing behavior.
    """
    return get_optional_positive_int(
        load_platform_json(platform_json_path),
        key,
    )


def _resolve(
    key: str,
    requested: Optional[int],
    default: int,
    platform_json_path: Optional[str] = None,
) -> int:
    """Return the largest of the requested, platform and default values."""
    candidates = [default]

    if requested is not None:
        candidates.append(requested)

    platform_value = _get_platform_minimum(key, platform_json_path)
    if platform_value is not None:
        candidates.append(platform_value)

    resolved = max(candidates)

    logging.debug(
        "Resolved %s to %s MiB from requested=%s platform=%s default=%s",
        key,
        resolved,
        requested,
        platform_value,
        default,
    )

    return resolved


def get_min_swap_mem_size_in_mb(
    platform_json_path: Optional[str] = None,
) -> Optional[int]:
    """Return the optional platform minimum SWAP size, in MiB."""
    return _get_platform_minimum(MIN_SWAP_MEM_SIZE_KEY, platform_json_path)


def get_min_total_mem_threshold_in_mb(
    platform_json_path: Optional[str] = None,
) -> Optional[int]:
    """Return the optional platform minimum total memory threshold, in MiB."""
    return _get_platform_minimum(MIN_TOTAL_MEM_THRESHOLD_KEY,
                                 platform_json_path)


def resolve_swap_mem_size(
    requested_size: Optional[int],
    default_size: int,
    platform_json_path: Optional[str] = None,
) -> int:
    """Return the SWAP size to allocate, in MiB.

    The size requested on the command line, the platform minimum from
    platform.json and the built-in default are compared, and the largest is
    used. A platform that needs more SWAP than the default therefore gets it
    without the operator passing --swap-mem-size on every install, while an
    operator asking for more than the platform minimum is still honored.
    """
    return _resolve(MIN_SWAP_MEM_SIZE_KEY, requested_size, default_size,
                    platform_json_path)


def resolve_total_mem_threshold(
    requested_threshold: Optional[int],
    default_threshold: int,
    platform_json_path: Optional[str] = None,
) -> int:
    """Return the total memory threshold to apply, in MiB.

    SWAP is only set up when system total memory is below this threshold, so a
    platform whose memory sits above the built-in default would never get a
    swapfile. Raising the threshold from platform.json lets such a platform opt
    in without the operator passing --total-mem-threshold on every install.
    """
    return _resolve(MIN_TOTAL_MEM_THRESHOLD_KEY, requested_threshold,
                    default_threshold, platform_json_path)
