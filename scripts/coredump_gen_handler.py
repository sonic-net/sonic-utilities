"""
coredump_gen_handler script.
    This script is invoked by the coredump-compress script
    for auto techsupport invocation and cleanup core dumps.
    For more info, refer to the Event Driven TechSupport & CoreDump Mgmt HLD
"""
import os
import argparse
import syslog
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.auto_techsupport_helper import *


def handle_coredump_cleanup(dump_name, db):
    _, num_bytes = get_stats(os.path.join(CORE_DUMP_DIR, CORE_DUMP_PTRN))

    if db.get(CFG_DB, AUTO_TS, CFG_STATE) != "enabled":
        msg = "coredump_cleanup is disabled. No cleanup is performed. current size occupied : {}"
        syslog.syslog(syslog.LOG_NOTICE, msg.format(pretty_size(num_bytes)))
        return

    core_usage = db.get(CFG_DB, AUTO_TS, CFG_CORE_USAGE)
    try:
        core_usage = float(core_usage)
    except ValueError:
        core_usage = 0.0

    if not core_usage:
        msg = "core-usage argument is not set. No cleanup is performed, current size occupied: {}"
        syslog.syslog(syslog.LOG_NOTICE, msg.format(pretty_size(num_bytes)))
        return

    cleanup_process(core_usage, CORE_DUMP_PTRN, CORE_DUMP_DIR)


class CriticalProcCoreDumpHandle():
    """
    Class to handle coredump creation event for critical processes
    """

    def __init__(self, core_name, container_name, db):
        self.core_name = core_name
        self.container = container_name
        self.db = db

    def handle_core_dump_creation_event(self):
        if self.db.get(CFG_DB, AUTO_TS, CFG_STATE) != "enabled":
            syslog.syslog(syslog.LOG_NOTICE, "auto_invoke_ts is disabled. No cleanup is performed: core {}".format(self.core_name))
            return

        # Config made for the defaul instance applies to all the masic instances
        self.container = trim_masic_suffix(self.container)

        FEATURE_KEY = FEATURE.format(self.container)
        if self.db.get(CFG_DB, FEATURE_KEY, CFG_STATE) != "enabled":
            msg = "auto-techsupport feature for {} is not enabled. Techsupport Invocation is skipped. core: {}"
            syslog.syslog(syslog.LOG_NOTICE, msg.format(self.container, self.core_name))
            return

        invoke_ts_command_rate_limited(self.db, EVENT_TYPE_CORE, {CORE_DUMP: self.core_name}, self.container)


def main():
    parser = argparse.ArgumentParser(description='Auto Techsupport Invocation and CoreDump Mgmt Script')
    parser.add_argument('name', type=str, help='Core Dump Name')
    parser.add_argument('container', type=str, help='Container Name')
    args = parser.parse_args()
    syslog.openlog(logoption=syslog.LOG_PID)
    db = SonicV2Connector(use_unix_socket_path=True)
    db.connect(CFG_DB)
    db.connect(STATE_DB)
    file_path = os.path.join(CORE_DUMP_DIR, args.name)
    if not verify_recent_file_creation(file_path):
        syslog.syslog(syslog.LOG_INFO, "Spurious Invocation. {} is not created within last {} sec".format(file_path, TIME_BUF))
        return
    cls = CriticalProcCoreDumpHandle(args.name, args.container, db)
    cls.handle_core_dump_creation_event()
    handle_coredump_cleanup(args.name, db)


if __name__ == "__main__":
    main()
