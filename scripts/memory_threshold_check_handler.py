#!/usr/bin/env python3

import sys
import os
import syslog
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.auto_techsupport_helper import *

# Exit codes
EXIT_SUCCESS = 0  # Success
EXIT_FAILURE = 1  # General failure occurred, no techsupport is invoked

def main():
    output = os.environ.get("MONIT_DESCRIPTION")
    syslog.openlog(logoption=syslog.LOG_PID)
    db = SonicV2Connector(use_unix_socket_path=True)
    db.connect(CFG_DB)
    db.connect(STATE_DB)
    if not output:
        syslog.syslog(
            syslog.LOG_ERR,
            "Expected to get output from environment variable MONIT_DESCRIPTION"
        )
        return EXIT_FAILURE
    if "--" not in output:
        syslog.syslog(syslog.LOG_ERR, "Unexpected value in environment variable MONIT_DESCRIPTION")
        return EXIT_FAILURE

    monit_output = output.split("--")[1].strip()
    # If the output of memory_threshold_check is empty
    # that means that memory threshold check failed for the host.
    # In this case monit inserts "no output" string in MONIT_DESCRIPTION
    if monit_output == "no output":
        container = None
    else:
        container = monit_output
    invoke_ts_command_rate_limited(db, EVENT_TYPE_MEMORY, container)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
