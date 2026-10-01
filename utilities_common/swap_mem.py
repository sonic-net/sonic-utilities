# utilities_common/swap_mem.py

import logging
from typing import Optional

from utilities_common.image_disk_space import (
    get_optional_positive_int,
    load_platform_json,
)

MIN_SWAP_MEM_SIZE_KEY = "min_swap_mem_size_in_mb"
MIN_TOTAL_MEM_THRESHOLD_KEY = "min_total_mem_threshold_in_mb"

SWAP_CONFIG_CONTEXT = "SWAP configuration"


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
        SWAP_CONFIG_CONTEXT,
    )


def _resolve(
    key: str,
    requested: Optional[int],
    default: int,
    platform_json_path: Optional[str] = None,
) -> int:
    """Return the requested value, raised to the platform minimum if any.

    The value requested on the command line is used as-is, falling back to the
    built-in default when nothing was requested. Only the platform minimum can
    raise it, so behavior is unchanged for platforms that configure nothing.
    """
    resolved = requested if requested is not None else default

    platform_value = _get_platform_minimum(key, platform_json_path)
    if platform_value is not None:
        resolved = max(resolved, platform_value)

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

    A platform that needs more SWAP than the default declares a minimum in
    platform.json and gets it without the operator passing --swap-mem-size on
    every install. A larger value requested on the command line is still
    honored.
    """
    return _resolve(MIN_SWAP_MEM_SIZE_KEY, requested_size, default_size,
                    platform_json_path)


def resolve_total_mem_threshold(
    requested_threshold: Optional[int],
    default_threshold: int,
    platform_json_path: Optional[str] = None,
) -> int:
    """Return the total memory threshold to apply, in MiB.

    SWAP is set up when system total memory is below this threshold, or when
    available memory is below the separate available-memory threshold. On a
    platform whose total memory sits above the built-in default, the
    total-memory condition never contributes, so raising the threshold from
    platform.json lets such a platform opt in without the operator passing
    --total-mem-threshold on every install.
    """
    return _resolve(MIN_TOTAL_MEM_THRESHOLD_KEY, requested_threshold,
                    default_threshold, platform_json_path)
