"""Helpers shared by HFT CLI modules."""

from sonic_py_common import device_info

SUPPORTED_PLATFORMS = (
    'x86_64-nvidia_sn5640-r0',
    'x86_64-kvm_x86_64-r0',
    'x86_64-arista_7060x6_64pe_b',
)


def is_supported_platform(platform_name=None):
    """Return True when the current platform supports HFT commands."""
    target_platform = platform_name
    if target_platform is None:
        try:
            target_platform = device_info.get_platform()
        except Exception:
            return False
    return target_platform in SUPPORTED_PLATFORMS
