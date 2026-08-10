#!/usr/bin/env python3

"""
chassis_db_consistency_checker

Checks synchronization of VOQ system LAG data between chassis_db and asic_db
on linecards:
- SYSTEM_LAG_ID_TABLE vs ASIC_DB SAI_OBJECT_TYPE_LAG aggregate IDs
- SYSTEM_LAG_MEMBER_TABLE vs ASIC_DB SAI_OBJECT_TYPE_LAG_MEMBER objects
  (including member status vs ingress/egress disable attributes)

Member status: chassis ``disabled`` is compared to ASIC ingress/egress disable
flags. SWSS may leave both flags ``false`` on SYSTEM ports even when chassis
lists the member as disabled; symmetric flags (both true or both false) are
treated as a match for ``disabled``. A chassis ``enabled`` member requires both
ASIC disable flags to be false.

Intended to run on line cards (not on the supervisor) of a VOQ chassis device.

Consumers (same checker logic; different invocation and output):

1. show CLI (``show chassis system-lag-consistency``) invokes this script with
   ``--json``. The show command parses the JSON, prints human-readable output,
   and always treats subprocess exit 0 as success (mismatches appear in the
   result payload, not the exit code).

2. Monit or manual runs invoke the script without ``--json``. On mismatch,
   CRITICAL messages are logged to syslog and the process exits with RC_ERR;
   on success it exits RC_OK. Full member checks run several redis-dump calls
   per ASIC namespace; size the Monit cycle accordingly on busy linecards.

Usage:
    python3 chassis_db_consistency_checker [--log-level LEVEL] [--lag-id-only] [--json]

Arguments:
    --log-level LEVEL   Set the logging level (DEBUG, INFO, WARNING, ERROR,
                        CRITICAL). Default is WARNING.
    --lag-id-only       Check SYSTEM_LAG_ID_TABLE only; skip lag member checks.
    --json              Output structured consistency result as JSON and exit 0.

"""

import subprocess
import json
import logging
import argparse
import sys
import sonic_py_common.multi_asic as multi_asic
import sonic_py_common.device_info as device_info

RC_OK = 0
RC_ERR = -1

# JSON result status values (used by show CLI and Monit logging).
STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_ERROR = "error"
STATUS_NOT_APPLICABLE = "not_applicable"

REASON_NOT_VOQ_CHASSIS = "Not a voq chassis device"
REASON_NOT_ON_SUPERVISOR = "Not supported on supervisor (VOQ chassis linecards only)"

CHASSIS_LAG_MEMBER_TABLE_PREFIX = "SYSTEM_LAG_MEMBER_TABLE|"


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
                continue
            lag_ids.add(str(lag_id))
    logging.debug(f"Extracted LAG IDs from ASIC DB: {lag_ids}")
    return lag_ids


def extract_table_ids_from_chassis_db(table_output):
    """Extract IDs from a table output (dict of key: id)."""
    return {str(lag_id) for lag_id in table_output.values() if lag_id is not None}


def run_redis_dump_asic_namespace(asic_netns, db_id, key_pattern):
    """Run redis-dump against a local ASIC redis instance (optionally in a netns)."""
    cmd = ["redis-dump", "-d", str(db_id), "-k", key_pattern, "-y"]
    if asic_netns != multi_asic.DEFAULT_NAMESPACE:
        cmd = ["sudo", "ip", "netns", "exec", asic_netns] + cmd
    return run_redis_dump(cmd)


def run_redis_dump_chassis_app(key_pattern):
    """Run redis-dump against CHASSIS_APP_DB on redis_chassis."""
    cmd = [
        "redis-dump",
        "-H", "redis_chassis.server",
        "-p", "6380",
        "-d", "12",
        "-k", key_pattern,
        "-y",
    ]
    return run_redis_dump(cmd)


def oid_from_asic_state_key(redis_key):
    if ":oid:" not in redis_key:
        return None
    return "oid:" + redis_key.rsplit(":oid:", 1)[1]


def _is_sai_bool_true(value):
    return str(value).lower() == "true"


def _asic_display_name(asic_namespace):
    if asic_namespace == multi_asic.DEFAULT_NAMESPACE:
        return "localhost"
    return asic_namespace


def bidirectional_set_diff(left, right):
    """Return items in left but not right, then items in right but not left."""
    missing_in_right = left - right
    extra_in_right = right - left
    return missing_in_right, extra_in_right


def format_bidirectional_diff(missing_in_right, extra_in_right):
    return {
        "missing_in_asic_db": sorted(missing_in_right),
        "extra_in_asic_db": sorted(extra_in_right),
    }


def bidirectional_diff_has_mismatch(diff):
    return diff["missing_in_asic_db"] or diff["extra_in_asic_db"]


def get_chassis_lag_db_table():
    """Fetch and return the SYSTEM_LAG_ID_TABLE from chassis_db."""
    chassis_db_raw = run_redis_dump_chassis_app("SYSTEM_LAG_ID_TABLE")
    chassis_db_table = chassis_db_raw.get('SYSTEM_LAG_ID_TABLE', {}).get('value', {})
    if not chassis_db_table:
        logging.error("No SYSTEM_LAG_ID_TABLE found in chassis_db")
        return {}
    return chassis_db_table


def get_chassis_lag_member_table():
    """Fetch and return the SYSTEM_LAG_MEMBER_TABLE from chassis_db."""
    chassis_db_raw = run_redis_dump_chassis_app("SYSTEM_LAG_MEMBER_TABLE*")
    return parse_chassis_lag_member_dump(chassis_db_raw)


def parse_chassis_lag_member_dump(dump_output):
    """Parse redis-dump output for SYSTEM_LAG_MEMBER_TABLE entries."""
    # redis-dump may return one SYSTEM_LAG_MEMBER_TABLE blob or per-member keys.
    member_table = {}
    single_table = dump_output.get("SYSTEM_LAG_MEMBER_TABLE", {}).get("value", {})
    if isinstance(single_table, dict):
        member_table.update(single_table)

    for redis_key, info in dump_output.items():
        if not redis_key.startswith(CHASSIS_LAG_MEMBER_TABLE_PREFIX):
            continue
        member_key = redis_key[len(CHASSIS_LAG_MEMBER_TABLE_PREFIX):]
        member_table[member_key] = info.get("value", {})
    return member_table


def parse_chassis_lag_members(member_table):
    """Return map of lag_member_key -> expected status from chassis table."""
    members = {}
    for member_key, fields in member_table.items():
        if not isinstance(fields, dict):
            members[member_key] = "enabled"
            continue
        status = fields.get("status", "enabled")
        members[member_key] = status if status else "enabled"
    return members


def build_lag_oid_to_alias(lag_db_output, lag_id_table):
    lag_id_to_alias = {str(lag_id): alias for alias, lag_id in lag_id_table.items() if lag_id is not None}
    lag_oid_to_alias = {}
    for key, info in lag_db_output.items():
        if "SAI_OBJECT_TYPE_LAG" not in key:
            continue
        lag_oid = oid_from_asic_state_key(key)
        aggregate_id = info.get("value", {}).get("SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID")
        if lag_oid and aggregate_id is not None and str(aggregate_id) in lag_id_to_alias:
            lag_oid_to_alias[lag_oid] = lag_id_to_alias[str(aggregate_id)]
    return lag_oid_to_alias


def build_lag_oid_to_aggregate_id(lag_db_output):
    """Map SAI LAG OID strings to SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID values."""
    lag_oid_to_aggregate_id = {}
    for key, info in lag_db_output.items():
        if "SAI_OBJECT_TYPE_LAG" not in key:
            continue
        lag_oid = oid_from_asic_state_key(key)
        aggregate_id = info.get("value", {}).get("SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID")
        if lag_oid and aggregate_id is not None:
            lag_oid_to_aggregate_id[lag_oid] = str(aggregate_id)
    return lag_oid_to_aggregate_id


def normalize_member_port_alias(lag_alias, port_alias):
    """Expand short port aliases (Ethernet0) to chassis system-port format."""
    # Chassis member keys use slot|core|port; COUNTERS maps may return short Ethernet aliases.
    if "|" in port_alias:
        return port_alias
    lag_parts = lag_alias.split("|")
    if len(lag_parts) >= 2:
        return f"{lag_parts[0]}|{lag_parts[1]}|{port_alias}"
    return port_alias


def build_port_oid_to_alias(asic_netns):
    """Map SAI port OID strings to port/system-port aliases via COUNTERS maps."""
    # ASIC_STATE_DB stores OIDs; COUNTERS_DB name maps provide alias <-> OID lookup.
    oid_to_alias = {}
    for map_name in ("COUNTERS_SYSTEM_PORT_NAME_MAP", "COUNTERS_PORT_NAME_MAP"):
        raw = run_redis_dump_asic_namespace(asic_netns, 2, map_name)
        name_map = raw.get(map_name, {}).get("value", {})
        for alias, oid in name_map.items():
            if oid:
                oid_to_alias[oid] = alias
    return oid_to_alias


def build_valid_port_oids(port_db_output):
    valid_port_oids = set()
    for key in port_db_output:
        if "SAI_OBJECT_TYPE_PORT" not in key and "SAI_OBJECT_TYPE_SYSTEM_PORT" not in key:
            continue
        port_oid = oid_from_asic_state_key(key)
        if port_oid:
            valid_port_oids.add(port_oid)
    return valid_port_oids


def extract_asic_lag_members(
    lag_member_db_output,
    lag_oid_to_alias,
    oid_to_alias,
    valid_port_oids,
    lag_oid_to_aggregate_id=None,
):
    """Return lag member map keyed by chassis member key."""
    members = {}
    unresolved = []
    invalid_port_id = []
    incomplete_attrs = []
    lag_oid_to_aggregate_id = lag_oid_to_aggregate_id or {}

    for key, info in lag_member_db_output.items():
        if "SAI_OBJECT_TYPE_LAG_MEMBER" not in key:
            continue
        value = info.get("value", {})
        lag_oid = value.get("SAI_LAG_MEMBER_ATTR_LAG_ID")
        port_oid = value.get("SAI_LAG_MEMBER_ATTR_PORT_ID")
        if lag_oid is None or port_oid is None:
            incomplete_attrs.append({
                "lag_member_oid": oid_from_asic_state_key(key) or key,
                "lag_oid": lag_oid,
                "port_oid": port_oid,
            })
            logging.error("%s has incomplete lag member attributes", key)
            continue

        lag_alias = lag_oid_to_alias.get(lag_oid)
        port_alias = oid_to_alias.get(port_oid)
        if not lag_alias or not port_alias:
            # OID present in ASIC_DB but not mappable to a chassis lag:port key.
            unresolved.append({
                "lag_oid": lag_oid,
                "port_oid": port_oid,
                "system_port_aggregate_id": lag_oid_to_aggregate_id.get(lag_oid),
            })
            continue

        port_alias = normalize_member_port_alias(lag_alias, port_alias)
        # Member key matches chassis_db: lag_alias:slot|core|port_alias
        member_key = f"{lag_alias}:{port_alias}"
        if port_oid not in valid_port_oids:
            invalid_port_id.append({
                "member": member_key,
                "port_id": port_oid,
            })
            continue

        members[member_key] = {
            "ingress_disable": value.get("SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE", "false"),
            "egress_disable": value.get("SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE", "false"),
            "port_id": port_oid,
        }

    return members, unresolved, invalid_port_id, incomplete_attrs


def member_disable_matches_status(ingress_disable, egress_disable, expected_status):
    """Return True when ASIC disable flags match the chassis member status.

    For ``enabled``, both ingress and egress disable must be false.

    For ``disabled``, SWSS may omit disable attrs on SYSTEM ports (both false
    while chassis still lists disabled). Symmetric flags (both true or both
    false) are treated as a match. Mismatched flags (one true, one false) are not
    a match.
    """
    ingress_disabled = _is_sai_bool_true(ingress_disable)
    egress_disabled = _is_sai_bool_true(egress_disable)
    if expected_status == "disabled":
        return ingress_disabled == egress_disabled
    return not ingress_disabled and not egress_disabled


def find_member_status_mismatches(chassis_members, asic_members):
    mismatches = []
    for member_key in chassis_members.keys() & asic_members.keys():
        expected_status = chassis_members[member_key]
        asic_info = asic_members[member_key]
        ingress_disable = asic_info["ingress_disable"]
        egress_disable = asic_info["egress_disable"]
        if member_disable_matches_status(ingress_disable, egress_disable, expected_status):
            continue
        mismatches.append({
            "member": member_key,
            "chassis_status": expected_status,
            "ingress_disable": ingress_disable,
            "egress_disable": egress_disable,
        })
    return mismatches


def member_diff_has_mismatch(member_result):
    return (
        member_result["missing_in_asic_db"]
        or member_result["extra_in_asic_db"]
        or member_result["status_mismatch"]
        or member_result["invalid_port_id"]
        or member_result["unresolved"]
        or member_result["incomplete_attrs"]
    )


def _empty_lag_members_result():
    return {
        "member_count": 0,
        "missing_in_asic_db": [],
        "extra_in_asic_db": [],
        "status_mismatch": [],
        "invalid_port_id": [],
        "unresolved": [],
        "incomplete_attrs": [],
    }


def check_asic_namespace(
    asic_namespace,
    lag_ids_in_chassis_db,
    lag_id_table,
    chassis_members=None,
    check_members=True,
):
    """Check lag ID and optionally lag member consistency for one ASIC namespace."""
    lag_db_output = run_redis_dump_asic_namespace(asic_namespace, 1, "*SAI_OBJECT_TYPE_LAG:*")
    lag_ids_in_asic_db = extract_lag_ids_from_asic_db(
        lag_db_output, "SAI_OBJECT_TYPE_LAG", "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID"
    )
    lag_id_missing, lag_id_extra = bidirectional_set_diff(lag_ids_in_chassis_db, lag_ids_in_asic_db)

    lag_ids_result = {
        "lag_id_count": len(lag_ids_in_asic_db),
        **format_bidirectional_diff(lag_id_missing, lag_id_extra),
    }
    # --lag-id-only / Monit lagIdCheck: skip member redis dumps and comparisons.
    if not check_members:
        return {"lag_ids": lag_ids_result}

    chassis_members = chassis_members or {}
    lag_member_db_output = run_redis_dump_asic_namespace(
        asic_namespace, 1, "*SAI_OBJECT_TYPE_LAG_MEMBER:*"
    )
    port_db_output = run_redis_dump_asic_namespace(asic_namespace, 1, "*SAI_OBJECT_TYPE_PORT:*")
    system_port_db_output = run_redis_dump_asic_namespace(
        asic_namespace, 1, "*SAI_OBJECT_TYPE_SYSTEM_PORT:*"
    )

    lag_oid_to_alias = build_lag_oid_to_alias(lag_db_output, lag_id_table)
    lag_oid_to_aggregate_id = build_lag_oid_to_aggregate_id(lag_db_output)
    oid_to_alias = build_port_oid_to_alias(asic_namespace)
    valid_port_oids = build_valid_port_oids(port_db_output)
    valid_port_oids.update(build_valid_port_oids(system_port_db_output))

    asic_members, unresolved, invalid_port_id, incomplete_attrs = extract_asic_lag_members(
        lag_member_db_output,
        lag_oid_to_alias,
        oid_to_alias,
        valid_port_oids,
        lag_oid_to_aggregate_id,
    )
    member_missing, member_extra = bidirectional_set_diff(
        set(chassis_members.keys()), set(asic_members.keys())
    )
    # Invalid PORT_ID is reported separately; do not also count those keys as missing/extra.
    invalid_member_keys = {item["member"] for item in invalid_port_id}
    member_missing -= invalid_member_keys
    member_extra -= invalid_member_keys
    status_mismatch = find_member_status_mismatches(chassis_members, asic_members)

    return {
        "lag_ids": lag_ids_result,
        "lag_members": {
            "member_count": len(asic_members),
            **format_bidirectional_diff(member_missing, member_extra),
            "status_mismatch": status_mismatch,
            "invalid_port_id": invalid_port_id,
            "unresolved": unresolved,
            "incomplete_attrs": incomplete_attrs,
        },
    }


def _not_applicable_result(reason, lag_id_only=False):
    return {
        "status": STATUS_NOT_APPLICABLE,
        "reason": reason,
        "lag_id_only": lag_id_only,
        "chassis_lag_id_count": 0,
        "chassis_lag_member_count": 0,
        "asics": {},
    }


def get_system_lag_consistency_result(check_members=True):
    """Return structured system LAG consistency result for CLI or automation."""
    # Internal flag is check_members; JSON/CLI surface the inverse as lag_id_only.
    lag_id_only = not check_members

    if not device_info.is_voq_chassis():
        return _not_applicable_result(REASON_NOT_VOQ_CHASSIS, lag_id_only=lag_id_only)

    if device_info.is_supervisor():
        return _not_applicable_result(REASON_NOT_ON_SUPERVISOR, lag_id_only=lag_id_only)

    chassis_db_lag_table = get_chassis_lag_db_table()
    if not chassis_db_lag_table:
        return {
            "status": STATUS_ERROR,
            "reason": "No SYSTEM_LAG_ID_TABLE found in chassis_db",
            "lag_id_only": lag_id_only,
            "chassis_lag_id_count": 0,
            "chassis_lag_member_count": 0,
            "asics": {},
        }

    chassis_members = {}
    if check_members:
        chassis_members = parse_chassis_lag_members(get_chassis_lag_member_table())
    lag_ids_in_chassis_db = extract_table_ids_from_chassis_db(chassis_db_lag_table)
    logging.debug(f"LAG IDs in chassis_db: {lag_ids_in_chassis_db}")
    logging.debug(f"LAG members in chassis_db: {chassis_members}")

    asics = {}
    for asic_namespace in multi_asic.get_namespace_list():
        asic_name = _asic_display_name(asic_namespace)
        asics[asic_name] = check_asic_namespace(
            asic_namespace,
            lag_ids_in_chassis_db,
            chassis_db_lag_table,
            chassis_members,
            check_members=check_members,
        )

    any_mismatch = any(
        bidirectional_diff_has_mismatch(asic_info["lag_ids"])
        or (check_members and member_diff_has_mismatch(asic_info["lag_members"]))
        for asic_info in asics.values()
    )

    return {
        "status": STATUS_FAILED if any_mismatch else STATUS_OK,
        "lag_id_only": lag_id_only,
        "chassis_lag_id_count": len(lag_ids_in_chassis_db),
        "chassis_lag_member_count": len(chassis_members),
        "asics": asics,
    }


def get_lag_id_consistency_result():
    """Return LAG ID consistency result without lag member checks."""
    # Convenience entry for lag-id-only callers (e.g. future Monit lagIdCheck).
    return get_system_lag_consistency_result(check_members=False)


def _log_consistency_result(result):
    """Log consistency result for Monit and return exit code."""
    # Default invocation path: syslog CRITICAL on mismatch, RC_ERR for Monit.
    if result["status"] == STATUS_NOT_APPLICABLE:
        if result["reason"] == REASON_NOT_VOQ_CHASSIS:
            logging.info("Not a voq chassis device. Exiting.....")
        else:
            logging.info("Not supported on supervisor. Exiting....")
        return RC_OK

    if result["status"] == STATUS_ERROR:
        logging.error(result["reason"])
        return RC_ERR

    lag_id_only = result.get("lag_id_only", False)
    mismatches_found = False
    lag_id_summary = {}
    lag_member_summary = {}

    for asic, asic_info in result["asics"].items():
        lag_ids = asic_info["lag_ids"]
        lag_members = asic_info.get("lag_members", _empty_lag_members_result())
        lag_id_summary[asic] = lag_ids
        if not lag_id_only:
            lag_member_summary[asic] = lag_members

        lag_id_mismatch = bidirectional_diff_has_mismatch(lag_ids)
        member_mismatch = not lag_id_only and member_diff_has_mismatch(lag_members)
        if not lag_id_mismatch and not member_mismatch:
            continue

        mismatches_found = True
        missing_in_asic = lag_ids["missing_in_asic_db"]
        extra_in_asic = lag_ids["extra_in_asic_db"]
        if missing_in_asic:
            logging.critical(
                "LAG IDs in chassis_db missing in %s ASIC_DB: %s", asic, missing_in_asic
            )
        if extra_in_asic:
            logging.critical(
                "LAG IDs in %s ASIC_DB missing from chassis_db: %s", asic, extra_in_asic
            )

        if not lag_id_only:
            member_missing = lag_members["missing_in_asic_db"]
            member_extra = lag_members["extra_in_asic_db"]
            if member_missing:
                logging.critical(
                    "LAG members in chassis_db missing in %s ASIC_DB: %s", asic, member_missing
                )
            if member_extra:
                logging.critical(
                    "LAG members in %s ASIC_DB missing from chassis_db: %s", asic, member_extra
                )
            for item in lag_members["status_mismatch"]:
                logging.critical("LAG member status mismatch in %s: %s", asic, item)
            for item in lag_members["invalid_port_id"]:
                logging.critical("LAG member invalid PORT_ID in %s: %s", asic, item)
            for item in lag_members["unresolved"]:
                logging.critical(
                    "LAG member could not be resolved to chassis key in %s: %s", asic, item
                )
            for item in lag_members["incomplete_attrs"]:
                logging.critical(
                    "LAG member with incomplete attributes in %s: %s", asic, item
                )

    if mismatches_found:
        summary = {"lag_ids": lag_id_summary}
        if not lag_id_only:
            summary["lag_members"] = lag_member_summary
        logging.critical(
            "Summary of mismatches:\n%s",
            json.dumps(summary, indent=4),
        )
        return RC_ERR

    logging.info("All ASICs are in sync with chassis_db")
    return RC_OK


def main():
    parser = argparse.ArgumentParser(
        description="Check VOQ system LAG sync between chassis_db and asic_db"
    )
    parser.add_argument('--log-level', default='WARNING', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level')
    parser.add_argument('--lag-id-only', action='store_true',
                        help='Check SYSTEM_LAG_ID_TABLE only; skip lag member checks')
    parser.add_argument('--json', action='store_true',
                        help='Output structured consistency result as JSON and exit 0')
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    # CLI --lag-id-only maps to skipping member checks inside get_system_lag_consistency_result().
    check_members = not args.lag_id_only
    result = get_system_lag_consistency_result(check_members=check_members)

    # show chassis system-lag-consistency: JSON payload, always exit 0; show prints text.
    if args.json:
        print(json.dumps(result, indent=2))
        return RC_OK

    # Monit / manual: syslog + non-zero exit on mismatch.
    return _log_consistency_result(result)


if __name__ == "__main__":
    sys.exit(main())
