"""
HWSKU Utilities

This module provides common utility functions for working with hardware SKUs (HWSKUs)
in SONiC. These utilities are shared across different CLI commands.
"""

import os
from sonic_py_common import device_info

# Constants
HOST_DEVICE_PATH = "/usr/share/sonic/device"


def get_available_hwskus():
    """
    Get list of available HWSKU names for the current platform

    Returns:
        List of available HWSKU names (directory names), or empty list if platform not found
    """
    platform = device_info.get_platform()
    if not platform:
        return []

    platform_path = os.path.join(HOST_DEVICE_PATH, platform)
    if not os.path.isdir(platform_path):
        return []

    hwskus = []
    try:
        for item in os.listdir(platform_path):
            # the lookup sonic-cfggen -k uses to find a HWSKU's ports
            if device_info.get_path_to_port_config_file(item) is not None:
                hwskus.append(item)
    except OSError:
        return []

    return hwskus
