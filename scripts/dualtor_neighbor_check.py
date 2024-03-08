#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dualtor_neighbor_check.py

This tool is designed to verify that, for dualtor SONiC, the neighbors learnt from
mux ports should have correct neighbor/route entry in ASIC.
"""
import argparse
import enum
import functools
import ipaddress
import json
import logging
import shlex
import sys
import syslog
import subprocess
import tabulate

from natsort import natsorted

from swsscommon import swsscommon
from sonic_py_common import daemon_base
try:
    from swsssdk import port_util
except ImportError:
    from sonic_py_common import port_util


DB_READ_SCRIPT = """
-- this script is to read required tables from db:
-- APPL_DB:
--   - MUX_CABLE_TABLE
--   - HW_MUX_CABLE_TABLE
--   - NEIGH_TABLE
-- ASIC_DB:
--   - ASIC_STATE
--
-- KEYS - None
-- ARGV[1] - APPL_DB db index
-- ARGV[2] - APPL_DB separator
-- ARGV[3] - APPL_DB neighbor table name
-- ARGV[4] - APPL_DB mux cable table name
-- ARGV[5] - APPL_DB hardware mux cable table name
-- ARGV[6] - ASIC_DB db index
-- ARGV[7] - ASIC_DB separator
-- ARGV[8] - ASIC_DB asic state table name

local APPL_DB                   = 0
local APPL_DB_SEPARATOR         = ':'
local neighbor_table_name       = 'NEIGH_TABLE'
local mux_state_table_name      = 'MUX_CABLE_TABLE'
local hw_mux_state_table_name   = 'HW_MUX_CABLE_TABLE'
local ASIC_DB                   = 1
local ASIC_DB_SEPARATOR         = ':'
local asic_state_table_name     = 'ASIC_STATE'
local asic_route_key_prefix     = 'SAI_OBJECT_TYPE_ROUTE_ENTRY'
local asic_neigh_key_prefix     = 'SAI_OBJECT_TYPE_NEIGHBOR_ENTRY'
local asic_fdb_key_prefix       = 'SAI_OBJECT_TYPE_FDB_ENTRY'

if table.getn(ARGV) == 7 then
    APPL_DB                 = ARGV[1]
    APPL_DB_SEPARATOR       = ARGV[2]
    neighbor_table_name     = ARGV[3]
    mux_state_table_name    = ARGV[4]
    hw_mux_state_table_name = ARGV[5]
    ASIC_DB                 = ARGV[6]
    ASIC_DB_SEPARATOR       = ARGV[7]
    asic_state_table_name   = ARGV[8]
end

local neighbors             = {}
local mux_states            = {}
local hw_mux_states         = {}
local asic_fdb              = {}
local asic_route_table      = {}
local asic_neighbor_table   = {}

-- read from APPL_DB
redis.call('SELECT', APPL_DB)

-- read neighbors learnt from Vlan devices
local neighbor_table_vlan_prefix = neighbor_table_name .. APPL_DB_SEPARATOR .. 'Vlan'
local neighbor_keys = redis.call('KEYS', neighbor_table_vlan_prefix .. '*')
for i, neighbor_key in ipairs(neighbor_keys) do
    local second_separator_index = string.find(neighbor_key, APPL_DB_SEPARATOR, string.len(neighbor_table_vlan_prefix), true)
    if second_separator_index ~= nil then
        local neighbor_ip = string.sub(neighbor_key, second_separator_index + 1)
        local mac = string.lower(redis.call('HGET', neighbor_key, 'neigh'))
        neighbors[neighbor_ip] = mac
    end
end

-- read mux states
local mux_state_table_prefix = mux_state_table_name .. APPL_DB_SEPARATOR
local mux_cables = redis.call('KEYS', mux_state_table_prefix .. '*')
for i, mux_cable_key in ipairs(mux_cables) do
    local port_name = string.sub(mux_cable_key, string.len(mux_state_table_prefix) + 1)
    local mux_state = redis.call('HGET', mux_cable_key, 'state')
    if mux_state ~= nil then
        mux_states[port_name] = mux_state
    end
end

local hw_mux_state_table_prefix = hw_mux_state_table_name .. APPL_DB_SEPARATOR
local hw_mux_cables = redis.call('KEYS', hw_mux_state_table_prefix .. '*')
for i, hw_mux_cable_key in ipairs(hw_mux_cables) do
    local port_name = string.sub(hw_mux_cable_key, string.len(hw_mux_state_table_prefix) + 1)
    local mux_state = redis.call('HGET', hw_mux_cable_key, 'state')
    if mux_state ~= nil then
        hw_mux_states[port_name] = mux_state
    end
end

-- read from ASIC_DB
redis.call('SELECT', ASIC_DB)

-- read ASIC fdb entries
local fdb_prefix = asic_state_table_name .. ASIC_DB_SEPARATOR .. asic_fdb_key_prefix
local fdb_entries = redis.call('KEYS', fdb_prefix .. '*')
for i, fdb_entry in ipairs(fdb_entries) do
    local bridge_port_id = redis.call('HGET', fdb_entry, 'SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID')
    local fdb_details = cjson.decode(string.sub(fdb_entry, string.len(fdb_prefix) + 2))
    local mac = string.lower(fdb_details['mac'])
    asic_fdb[mac] = bridge_port_id
end

-- read ASIC route table
local route_prefix = asic_state_table_name .. ASIC_DB_SEPARATOR .. asic_route_key_prefix
local route_entries = redis.call('KEYS', route_prefix .. '*')
for i, route_entry in ipairs(route_entries) do
    local route_details = string.sub(route_entry, string.len(route_prefix) + 2)
    table.insert(asic_route_table, route_details)
end

-- read ASIC neigh table
local neighbor_prefix = asic_state_table_name .. ASIC_DB_SEPARATOR .. asic_neigh_key_prefix
local neighbor_entries = redis.call('KEYS', neighbor_prefix .. '*')
for i, neighbor_entry in ipairs(neighbor_entries) do
    local neighbor_details = string.sub(neighbor_entry, string.len(neighbor_prefix) + 2)
    table.insert(asic_neighbor_table, neighbor_details)
end

local result = {}
result['neighbors']         = neighbors
result['mux_states']        = mux_states
result['hw_mux_states']     = hw_mux_states
result['asic_fdb']          = asic_fdb
result['asic_route_table']  = asic_route_table
result['asic_neigh_table']  = asic_neighbor_table

return redis.status_reply(cjson.encode(result))
"""

DB_READ_SCRIPT_CONFIG_DB_KEY = "_DUALTOR_NEIGHBOR_CHECK_SCRIPT_SHA1"
ZERO_MAC = "00:00:00:00:00:00"
NEIGHBOR_ATTRIBUTES = ["NEIGHBOR", "MAC", "PORT", "MUX_STATE", "IN_MUX_TOGGLE", "NEIGHBOR_IN_ASIC", "TUNNEL_IN_ASIC", "HWSTATUS"]
NOT_AVAILABLE = "N/A"


class LogOutput(enum.Enum):
    """Enum to represent log output."""
    SYSLOG = "SYSLOG"
    STDOUT = "STDOUT"

    def __str__(self):
        return self.value


class SyslogLevel(enum.IntEnum):
    """Enum to represent syslog level."""
    ERROR = 3
    NOTICE = 5
    INFO = 6
    DEBUG = 7

    def __str__(self):
        return self.name


SYSLOG_LEVEL = SyslogLevel.INFO
WRITE_LOG_ERROR = None
WRITE_LOG_WARN = None
WRITE_LOG_INFO = None
WRITE_LOG_DEBUG = None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify neighbors state is consistent with mux state."
    )
    parser.add_argument(
        "-o",
        "--log-output",
        type=LogOutput,
        choices=list(LogOutput),
        default=LogOutput.STDOUT,
        help="log output"
    )
    parser.add_argument(
        "-s",
        "--syslog-level",
        choices=["ERROR", "NOTICE", "INFO", "DEBUG"],
        default=None,
        help="syslog level"
    )
    parser.add_argument(
        "-l",
        "--log-level",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        default=None,
        help="stdout log level"
    )
    args = parser.parse_args()

    if args.log_output == LogOutput.STDOUT:
        if args.log_level is None:
            args.log_level = logging.WARNING
        else:
            args.log_level = logging.getLevelName(args.log_level)

        if args.syslog_level is not None:
            parser.error("Received syslog level with log output to stdout.")
    if args.log_output == LogOutput.SYSLOG:
        if args.syslog_level is None:
            args.syslog_level = SyslogLevel.NOTICE
        else:
            args.syslog_level = SyslogLevel[args.syslog_level]

        if args.log_level is not None:
            parser.error("Received stdout log level with log output to syslog.")

    return args


def write_syslog(level, message, *args):
    if level > SYSLOG_LEVEL:
        return
    if args:
        message %= args
    if level == SyslogLevel.ERROR:
        syslog.syslog(syslog.LOG_ERR, message)
    elif level == SyslogLevel.NOTICE:
        syslog.syslog(syslog.LOG_NOTICE, message)
    elif level == SyslogLevel.INFO:
        syslog.syslog(syslog.LOG_INFO, message)
    elif level == SyslogLevel.DEBUG:
        syslog.syslog(syslog.LOG_DEBUG, message)
    else:
        syslog.syslog(syslog.LOG_DEBUG, message)


def config_logging(args):
    """Configures logging based on arguments."""
    global SYSLOG_LEVEL
    global WRITE_LOG_ERROR
    global WRITE_LOG_WARN
    global WRITE_LOG_INFO
    global WRITE_LOG_DEBUG
    if args.log_output == LogOutput.STDOUT:
        logging.basicConfig(
            stream=sys.stdout,
            level=args.log_level,
            format="%(message)s"
        )
        WRITE_LOG_ERROR = logging.error
        WRITE_LOG_WARN = logging.warning
        WRITE_LOG_INFO = logging.info
        WRITE_LOG_DEBUG = logging.debug
    elif args.log_output == LogOutput.SYSLOG:
        SYSLOG_LEVEL = args.syslog_level
        WRITE_LOG_ERROR = functools.partial(write_syslog, SyslogLevel.ERROR)
        WRITE_LOG_WARN = functools.partial(write_syslog, SyslogLevel.NOTICE)
        WRITE_LOG_INFO = functools.partial(write_syslog, SyslogLevel.INFO)
        WRITE_LOG_DEBUG = functools.partial(write_syslog, SyslogLevel.DEBUG)


def run_command(cmd):
    """Runs a command and returns its output."""
    WRITE_LOG_DEBUG("Running command: %s", cmd)
    try:
        p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output, _) = p.communicate()
    except Exception as details:
        raise RuntimeError("Failed to run command: %s", details)
    WRITE_LOG_DEBUG("Command output: %s", output)
    WRITE_LOG_DEBUG("Command return code: %s", p.returncode)
    if p.returncode != 0:
        raise RuntimeError("Command failed with return code %s: %s" % (p.returncode, output))
    return output.decode()


def redis_cli(redis_cmd):
    """Call a redis command with return error check."""
    run_cmd = "sudo redis-cli %s" % redis_cmd
    result = run_command(run_cmd).strip()
    if "error" in result or "ERR" in result:
        raise RuntimeError("Redis command '%s' failed: %s" % (redis_cmd, result))
    return result


def read_tables_from_db(appl_db):
    """Reads required tables from db."""
    # NOTE: let's cache the db read script sha1 in APPL_DB under
    # key "_DUALTOR_NEIGHBOR_CHECK_SCRIPT_SHA1"
    db_read_script_sha1 = appl_db.get(DB_READ_SCRIPT_CONFIG_DB_KEY)
    if not db_read_script_sha1:
        redis_load_cmd = "SCRIPT LOAD \"%s\"" % DB_READ_SCRIPT
        db_read_script_sha1 = redis_cli(redis_load_cmd).strip()
        WRITE_LOG_INFO("loaded script sha1: %s", db_read_script_sha1)
        appl_db.set(DB_READ_SCRIPT_CONFIG_DB_KEY, db_read_script_sha1)

    redis_run_cmd = "EVALSHA %s 0" % db_read_script_sha1
    result = redis_cli(redis_run_cmd).strip()
    tables = json.loads(result)

    neighbors = tables["neighbors"]
    mux_states = tables["mux_states"]
    hw_mux_states = tables["hw_mux_states"]
    asic_fdb = {k: v.lstrip("oid:0x") for k, v in tables["asic_fdb"].items()}
    asic_route_table = tables["asic_route_table"]
    asic_neigh_table = tables["asic_neigh_table"]
    WRITE_LOG_DEBUG("neighbors: %s", json.dumps(neighbors, indent=4))
    WRITE_LOG_DEBUG("mux states: %s", json.dumps(mux_states, indent=4))
    WRITE_LOG_DEBUG("hw mux states: %s", json.dumps(hw_mux_states, indent=4))
    WRITE_LOG_DEBUG("ASIC FDB: %s", json.dumps(asic_fdb, indent=4))
    WRITE_LOG_DEBUG("ASIC route table: %s", json.dumps(asic_route_table, indent=4))
    WRITE_LOG_DEBUG("ASIC neigh table: %s", json.dumps(asic_neigh_table, indent=4))
    return neighbors, mux_states, hw_mux_states, asic_fdb, asic_route_table, asic_neigh_table


def get_if_br_oid_to_port_name_map():
    """Return port bridge oid to port name map."""
    db = swsscommon.SonicV2Connector(host="127.0.0.1")
    try:
        port_name_map = port_util.get_interface_oid_map(db)[1]
    except IndexError:
        port_name_map = {}
    if_br_oid_map = port_util.get_bridge_port_map(db)
    if_br_oid_to_port_name_map = {}
    for if_br_oid, if_oid in if_br_oid_map.items():
        if if_oid in port_name_map:
            if_br_oid_to_port_name_map[if_br_oid] = port_name_map[if_oid]
    return if_br_oid_to_port_name_map


def is_dualtor(config_db):
    """Check if it is a dualtor device."""
    device_metadata = config_db.get_table('DEVICE_METADATA')
    return ("localhost" in device_metadata and
            "subtype" in device_metadata['localhost'] and
            device_metadata['localhost']['subtype'].lower() == 'dualtor')


def get_mux_cable_config(config_db):
    """Return mux cable config from CONFIG_DB."""
    return config_db.get_table("MUX_CABLE")


def get_mux_server_to_port_map(mux_cables):
    """Return mux server ip to port name map."""
    mux_server_to_port_map = {}
    for port, mux_details in mux_cables.items():
        if "server_ipv4" in mux_details:
            server_ipv4 = str(ipaddress.ip_interface(mux_details["server_ipv4"]).ip)
            mux_server_to_port_map[server_ipv4] = port
        if "server_ipv6" in mux_details:
            server_ipv6 = str(ipaddress.ip_interface(mux_details["server_ipv6"]).ip)
            mux_server_to_port_map[server_ipv6] = port
    return mux_server_to_port_map


def get_mac_to_port_name_map(asic_fdb, if_oid_to_port_name_map):
    """Return mac to port name map."""
    mac_to_port_name_map = {}
    for mac, port_br_oid in asic_fdb.items():
        if port_br_oid in if_oid_to_port_name_map:
            mac_to_port_name_map[mac] = if_oid_to_port_name_map[port_br_oid]
    return mac_to_port_name_map


def check_neighbor_consistency(neighbors, mux_states, hw_mux_states, mac_to_port_name_map,
                               asic_route_table, asic_neigh_table, mux_server_to_port_map):
    """Checks if neighbors are consistent with mux states."""

    asic_route_destinations = set(json.loads(_)["dest"].split("/")[0] for _ in asic_route_table)
    asic_neighs = set(json.loads(_)["ip"] for _ in asic_neigh_table)

    check_results = []
    for neighbor_ip in natsorted(list(neighbors.keys())):
        mac = neighbors[neighbor_ip]
        check_result = {attr: NOT_AVAILABLE for attr in NEIGHBOR_ATTRIBUTES}
        check_result["NEIGHBOR"] = neighbor_ip
        check_result["MAC"] = mac

        is_zero_mac = (mac == ZERO_MAC)
        if mac not in mac_to_port_name_map and not is_zero_mac:
            check_results.append(check_result)
            continue

        check_result["NEIGHBOR_IN_ASIC"] = neighbor_ip in asic_neighs
        check_result["TUNNEL_IN_ASIC"] = neighbor_ip in asic_route_destinations
        if is_zero_mac:
            # NOTE: for zero-mac neighbors, two situations:
            # 1. new neighbor just learnt, no neighbor entry in ASIC, tunnel route present in ASIC.
            # 2. neighbor expired, neighbor entry still present in ASIC, no tunnel route in ASIC.
            check_result["HWSTATUS"] = check_result["NEIGHBOR_IN_ASIC"] or check_result["TUNNEL_IN_ASIC"]
        else:
            port_name = mac_to_port_name_map[mac]
            # NOTE: mux server ips are always fixed to the mux port
            if neighbor_ip in mux_server_to_port_map:
                port_name = mux_server_to_port_map[neighbor_ip]
            mux_state = mux_states[port_name]
            hw_mux_state = hw_mux_states[port_name]
            check_result["PORT"] = port_name
            check_result["MUX_STATE"] = mux_state
            check_result["IN_MUX_TOGGLE"] = mux_state != hw_mux_state

            if mux_state == "active":
                check_result["HWSTATUS"] = (check_result["NEIGHBOR_IN_ASIC"] and (not check_result["TUNNEL_IN_ASIC"]))
            elif mux_state == "standby":
                check_result["HWSTATUS"] = ((not check_result["NEIGHBOR_IN_ASIC"]) and check_result["TUNNEL_IN_ASIC"])
            else:
                # skip as unknown mux state
                continue

        check_results.append(check_result)

    return check_results


def parse_check_results(check_results):
    """Parse the check results to see if there are neighbors that are inconsistent with mux state."""
    failed_neighbors = []
    bool_to_yes_no = ("no", "yes")
    bool_to_consistency = ("inconsistent", "consistent")
    for check_result in check_results:
        port = check_result["PORT"]
        is_zero_mac = check_result["MAC"] == ZERO_MAC
        if port == NOT_AVAILABLE and not is_zero_mac:
            continue
        in_toggle = check_result["IN_MUX_TOGGLE"]
        hwstatus = check_result["HWSTATUS"]
        if not is_zero_mac:
            check_result["IN_MUX_TOGGLE"] = bool_to_yes_no[in_toggle]
        check_result["NEIGHBOR_IN_ASIC"] = bool_to_yes_no[check_result["NEIGHBOR_IN_ASIC"]]
        check_result["TUNNEL_IN_ASIC"] = bool_to_yes_no[check_result["TUNNEL_IN_ASIC"]]
        check_result["HWSTATUS"] = bool_to_consistency[hwstatus]
        if (not hwstatus):
            if is_zero_mac:
                failed_neighbors.append(check_result)
            elif not in_toggle:
                failed_neighbors.append(check_result)

    output_lines = tabulate.tabulate(
        [[check_result[attr] for attr in NEIGHBOR_ATTRIBUTES] for check_result in check_results],
        headers=NEIGHBOR_ATTRIBUTES,
        tablefmt="simple"
    )
    for output_line in output_lines.split("\n"):
        WRITE_LOG_WARN(output_line)

    if failed_neighbors:
        WRITE_LOG_ERROR("Found neighbors that are inconsistent with mux states: %s", [_["NEIGHBOR"] for _ in failed_neighbors])
        err_output_lines = tabulate.tabulate(
            [[neighbor[attr] for attr in NEIGHBOR_ATTRIBUTES] for neighbor in failed_neighbors],
            headers=NEIGHBOR_ATTRIBUTES,
            tablefmt="simple"
        )
        for output_line in err_output_lines.split("\n"):
            WRITE_LOG_ERROR(output_line)
        return False
    return True


if __name__ == "__main__":
    args = parse_args()
    config_logging(args)

    config_db = swsscommon.ConfigDBConnector(use_unix_socket_path=False)
    config_db.connect()
    appl_db = daemon_base.db_connect("APPL_DB")

    mux_cables = get_mux_cable_config(config_db)

    if not is_dualtor(config_db) or not mux_cables:
        WRITE_LOG_DEBUG("Not a valid dualtor setup, skip the check.")
        sys.exit(0)

    mux_server_to_port_map = get_mux_server_to_port_map(mux_cables)
    if_oid_to_port_name_map = get_if_br_oid_to_port_name_map()
    neighbors, mux_states, hw_mux_states, asic_fdb, asic_route_table, asic_neigh_table = read_tables_from_db(appl_db)
    mac_to_port_name_map = get_mac_to_port_name_map(asic_fdb, if_oid_to_port_name_map)

    check_results = check_neighbor_consistency(
        neighbors,
        mux_states,
        hw_mux_states,
        mac_to_port_name_map,
        asic_route_table,
        asic_neigh_table,
        mux_server_to_port_map
    )
    res = parse_check_results(check_results)
    sys.exit(0 if res else 1)
