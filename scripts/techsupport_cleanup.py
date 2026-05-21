"""
techsupport_cleanup script.
    This script is invoked by the generate_dump script for techsupport cleanup
    For more info, refer to the Event Driven TechSupport & CoreDump Mgmt HLD
"""
import os
import argparse
import syslog
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.auto_techsupport_helper import *


def clean_state_db_entries(removed_files, db):
    if not removed_files:
        return
    for file in removed_files:
        name = strip_ts_ext(file)
        db.delete(STATE_DB, TS_MAP + "|" + name)


def handle_techsupport_creation_event(dump_name, db):
    file_path = os.path.join(TS_DIR, dump_name)
    if not verify_recent_file_creation(file_path):
        return
    _ , num_bytes = get_stats(os.path.join(TS_DIR, TS_PTRN_GLOB))

    if db.get(CFG_DB, AUTO_TS, CFG_STATE) != "enabled":
        msg = "techsupport_cleanup is disabled. No cleanup is performed. current size occupied : {}"
        syslog.syslog(syslog.LOG_NOTICE, msg.format(pretty_size(num_bytes)))
        return

    max_ts = db.get(CFG_DB, AUTO_TS, CFG_MAX_TS)
    try:
        max_ts = float(max_ts)
    except ValueError:
        max_ts = 0.0

    if not max_ts:
        msg = "max-techsupport-limit argument is not set. No cleanup is performed, current size occupied: {}"
        syslog.syslog(syslog.LOG_NOTICE, msg.format(pretty_size(num_bytes)))
        return

    removed_files = cleanup_process(max_ts, TS_PTRN_GLOB, TS_DIR)
    clean_state_db_entries(removed_files, db)


def main():
    parser = argparse.ArgumentParser(description='Auto Techsupport Invocation and CoreDump Mgmt Script')
    parser.add_argument('name', type=str, help='TechSupport Dump Name')
    args = parser.parse_args()
    syslog.openlog(logoption=syslog.LOG_PID)
    db = SonicV2Connector(use_unix_socket_path=True)
    db.connect(CFG_DB)
    db.connect(STATE_DB)
    handle_techsupport_creation_event(args.name, db)


if __name__ == "__main__":
    main()
