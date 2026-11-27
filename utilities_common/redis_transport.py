"""Explicit transport setting for command-line Redis readers."""

import os


def cli_uses_unix_socket():
    """Read the transport supplied by the CLI environment, defaulting to TCP."""
    transport = os.environ.get("SONIC_REDIS_TRANSPORT", "tcp")
    if transport not in ("tcp", "unix"):
        raise ValueError("SONIC_REDIS_TRANSPORT must be tcp or unix")
    return transport == "unix"
