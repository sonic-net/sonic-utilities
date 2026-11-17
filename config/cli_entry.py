"""Console entry for ``config``: run via the warm cli-daemon when available,
falling back to a cold Click import otherwise.

No special handling is needed for Tab completion here: the daemon's forked
child sees ``_CONFIG_COMPLETE`` in the forwarded environment and behaves
exactly like a real command that happens to print completions.
"""

import sys


def main():
    from utilities_common.cli_server import try_run

    rc = try_run("config")
    if rc is not None:
        sys.exit(rc)

    from config.main import config

    sys.exit(config())
