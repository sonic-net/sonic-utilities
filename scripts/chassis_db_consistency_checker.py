#!/usr/bin/env python3

"""
chassis_db_consistency_checker

This script checks for synchronization of LAG (Link Aggregation Group) IDs
between the chassis_db and asic_db on VOQ chassis Linecard.
This script is intended to be run by Monit.
It will write an alerting message into syslog if it finds any mismatches in
LAG IDs between the chassis_db and asic_db.

It performs the following steps:
- Retrieves LAG IDs from the ASIC DBs (per namespace).
- Retrieves the SYSTEM_LAG_ID_TABLE from the chassis DB.
- Compares the LAG IDs in the chassis DB and ASIC DBs to identify mismatches.
- Reports any mismatched LAG keys per ASIC namespace.
- Exits with a non-zero status if mismatches are found.

Intended to be run on line cards (not on the supervisor) of a VOQ chassis
device.
Usage:
    python3 chassis_db_consistency_checker [--log-level LEVEL]

Arguments:
    --log-level LEVEL   Set the logging level (DEBUG, INFO, WARNING, ERROR,
                        CRITICAL). Default is WARNING.

"""

import subprocess
import json
import logging
import argparse
import sonic_py_common.multi_asic as multi_asic
import sonic_py_common.device_info as device_info
RC_OK = 0
RC_ERR = -1
RC_REDIS_ERR = -2


def run_redis_dump(cmd_args):
    """Run redis-dump with given command arguments and return parsed JSON output."""
    try:
        result = subprocess.run(cmd_args, capture_output=True, text=True)
        logging.debug(f"Command: {cmd_args} output: {result.stdout}")
        if result.returncode != 0:
            logging.error(f"Command failed: {result.stderr}")
            raise RuntimeError(f"Command failed: {result.stderr}")
        return json.loads(result.stdout)
    except Exception as e:
        logging.error(f"Error running redis-dump: {e}")
        return {}


def extract_lag_ids_from_asic_db(db_output, key_pattern, lag_id_field):
    """Extract LAG IDs from redis-dump output based on key pattern and field name."""
    lag_ids = set()
    for key, info in db_output.items():
        if key_pattern in key:
            lag_id = info.get('value', {}).get(lag_id_field, None)
            if lag_id is None:
                logging.error(f"{key} has bad lag_id")
            lag_ids.add(lag_id)
    logging.debug(f"Extracted LAG IDs from ASIC DB: {lag_ids}")
    return lag_ids


def extract_table_ids_from_chassis_db(table_output):
    """Extract IDs from a table output (dict of key: id)."""
    return set(table_output.values())


def get_lag_ids_asic_namespace(asic_netns):
    """Get LAG IDs from a specific ASIC namespace."""
    if asic_netns == multi_asic.DEFAULT_NAMESPACE:
        asic_cmd = ["redis-dump", "-d", "1", "-k", "*SAI_OBJECT_TYPE_LAG:*", "-y"]
    else:
        asic_cmd = [
            "sudo", "ip", "netns", "exec", asic_netns,
            "redis-dump", "-d", "1", "-k", "*SAI_OBJECT_TYPE_LAG:*", "-y"
        ]
    asic_db_output = run_redis_dump(asic_cmd)
    lag_id_ns = extract_lag_ids_from_asic_db(
        asic_db_output, "SAI_OBJECT_TYPE_LAG", "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID"
    )
    logging.debug(f"LAG IDs in ASIC namespace {asic_netns}: {lag_id_ns}")
    return lag_id_ns


def get_chassis_lag_db_table():
    """Fetch and return the SYSTEM_LAG_ID_TABLE from chassis_db."""
    chassis_db_cmd = [
        "redis-dump",
        "-H", "redis_chassis.server",
        "-p", "6380",
        "-d", "12",
        "-k", "SYSTEM_LAG_ID_TABLE",
        "-y"
    ]
    chassis_db_raw = run_redis_dump(chassis_db_cmd)
    chassis_db_table = chassis_db_raw.get('SYSTEM_LAG_ID_TABLE', {}).get('value', {})
    if not chassis_db_table:
        logging.error("No SYSTEM_LAG_ID_TABLE found in chassis_db")
        return {}
    return chassis_db_table


def compare_lag_ids(lag_ids_in_chassis_db, asic):
    lag_ids_in_asic_db = get_lag_ids_asic_namespace(asic)
    diff = lag_ids_in_chassis_db - lag_ids_in_asic_db
    if not diff:
        diff = lag_ids_in_asic_db - lag_ids_in_chassis_db
    return diff


def check_lag_id_sync():
    """Check if LAG IDs in chassis_db and asic_db are in sync."""

    rc = RC_OK
    diff_summary = {}
    chassis_db_lag_table = get_chassis_lag_db_table()
    if not chassis_db_lag_table:
        return RC_ERR, diff_summary
    lag_ids_in_chassis_db = extract_table_ids_from_chassis_db(chassis_db_lag_table)
    logging.debug(f"LAG IDs in chassis_db: {lag_ids_in_chassis_db}")

    asic_namespaces = multi_asic.get_namespace_list()

    for asic_namespace in asic_namespaces:
        diff = compare_lag_ids(lag_ids_in_chassis_db, asic_namespace)
        asic_name = "localhost" if asic_namespace == multi_asic.DEFAULT_NAMESPACE else asic_namespace
        # Convert set to list for JSON/logging friendliness
        diff_summary[asic_name] = sorted(list(diff))

    return rc, diff_summary


def main():
    parser = argparse.ArgumentParser(description="Check LAG ID sync between chassis_db and asic_db")
    parser.add_argument('--log-level', default='WARNING', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level')
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    if not device_info.is_voq_chassis():
        logging.info("Not a voq chassis device. Exiting.....")
        return RC_OK

    if device_info.is_supervisor():
        logging.info("Not supported on supervisor. Exiting....")
        return RC_OK

    rc, diff_summary = check_lag_id_sync()
    if rc != RC_OK:
        return rc

    mismatches_found = False
    for asic, mismatches in diff_summary.items():
        if mismatches:
            logging.critical(f"Mismatched LAG keys in {asic}: {mismatches}")
            mismatches_found = True

    if mismatches_found:
        logging.critical("Summary of mismatches:\n%s", json.dumps(diff_summary, indent=4))
        return RC_ERR
    else:
        logging.info("All ASICs are in sync with chassis_db")
        return RC_OK


if __name__ == "__main__":
    main()
