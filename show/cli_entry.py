"""Console entry for ``show``: run via the warm cli-daemon when available,
falling back to a cold Click import otherwise.

No special handling is needed for Tab completion here: the daemon's forked
child sees ``_SHOW_COMPLETE`` in the forwarded environment and behaves
exactly like a real command that happens to print completions.
"""

import sys


def main():
    from utilities_common.cli_server import try_run

    rc = try_run("show")
    if rc is not None:
        sys.exit(rc)

    from show.main import cli

    sys.exit(cli())
