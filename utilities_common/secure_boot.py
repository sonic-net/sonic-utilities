"""Shared helper for invoking the SONiC Secure Boot backend.

The CLI talks to a single stable entry point, ``/usr/sbin/secure-boot-backend``,
which is the SONiC Secure Boot backend selector. The selector chooses the
platform backend, the generic UEFI backend, or reports that Secure Boot
management is unsupported.

The contract between the CLI and the backend is:

    stdout -> JSON only
    stderr -> diagnostics
"""

import json
import subprocess

BACKEND = "/usr/sbin/secure-boot-backend"


class BackendError(RuntimeError):
    pass


def run_backend(args, timeout):
    """Run the Secure Boot backend and return its parsed JSON response.

    ``stdout`` is expected to carry JSON only; ``stderr`` carries diagnostics
    and is only surfaced when the backend fails without a JSON ``error`` field.
    """
    try:
        cp = subprocess.run(
            [BACKEND] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise BackendError("Secure Boot management is not supported on this platform")
    except subprocess.TimeoutExpired:
        raise BackendError("secure boot backend timed out")

    try:
        data = json.loads(cp.stdout or "{}")
    except json.JSONDecodeError:
        diagnostic = (cp.stderr or "").strip()
        if diagnostic:
            raise BackendError(diagnostic)
        raise BackendError("invalid backend response: {}".format((cp.stdout or "").strip()))

    if cp.returncode != 0 or "error" in data:
        message = data.get("error")
        if not message:
            message = (cp.stderr or "").strip()
        raise BackendError(message or "secure boot backend failed")

    return data
