#!/usr/bin/env python3

"""
SONiC Secure Boot backend selector.

This is the stable ``/usr/sbin/secure-boot-backend`` entry point used by the
``show secure-boot`` and ``config secure-boot`` CLI commands. It does not
implement any Secure Boot logic itself; it only selects the backend that does
and hands control to it unchanged.

Selection order:

1. Explicitly registered platform backend.
2. SONiC generic UEFI backend when standard UEFI variable services are
   available.
3. Report Secure Boot management unsupported.
"""

import json
import os
import sys

PLATFORM_BACKEND = "/usr/lib/sonic/secure-boot/platform-backend"
GENERIC_UEFI_BACKEND = "/usr/lib/sonic/secure-boot/generic-uefi-backend"

# Linux exposes UEFI runtime variables here when EFI variable services
# are available to the operating system.
EFIVARS_PATH = "/sys/firmware/efi/efivars"


def _error(message, rc=1):
    print(json.dumps({"error": message}))
    return rc


def _is_executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _uefi_services_available():
    return os.path.isdir(EFIVARS_PATH)


def _select_backend():
    """Return the Secure Boot backend executable per the HLD selection order."""

    # 1. Explicit platform override takes precedence.
    if _is_executable(PLATFORM_BACKEND):
        return PLATFORM_BACKEND

    # 2. Fall back to SONiC generic UEFI implementation.
    if _uefi_services_available() and _is_executable(GENERIC_UEFI_BACKEND):
        return GENERIC_UEFI_BACKEND

    # 3. Secure Boot management is unsupported.
    return None


def main():
    backend = _select_backend()

    if backend is None:
        return _error("Secure Boot management is not supported on this platform")

    try:
        # Replace the selector process so stdout/stderr/return code come
        # directly from the selected backend.
        os.execv(backend, [backend] + sys.argv[1:])
    except OSError as exc:
        return _error("failed to execute Secure Boot backend: {}".format(exc))


if __name__ == "__main__":
    sys.exit(main())
