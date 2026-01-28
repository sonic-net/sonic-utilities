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
-- STATE_DB:
--   - MUX_CABLE_TABLE
-- ASIC_DB:
--   - ASIC_STATE (route entries, neighbor entries, nexthop entries)
--
-- KEYS - None
-- ARGV[1] - APPL_DB db index
-- ARGV[2] - APPL_DB separator
-- ARGV[3] - APPL_DB neighbor table name
-- ARGV[4] - APPL_DB mux cable table name
-- ARGV[5] - APPL_DB hardware mux cable table name
-- ARGV[6] - STATE_DB db index
-- ARGV[7] - STATE_DB separator
-- ARGV[8] - STATE_DB mux cable table name
-- ARGV[9] - ASIC_DB db index
-- ARGV[10] - ASIC_DB separator
-- ARGV[11] - ASIC_DB asic state table name

local APPL_DB                   = 0
local APPL_DB_SEPARATOR         = ':'
local neighbor_table_name       = 'NEIGH_TABLE'
local mux_state_table_name      = 'MUX_CABLE_TABLE'
local hw_mux_state_table_name   = 'HW_MUX_CABLE_TABLE'
local STATE_DB                  = 6
local STATE_DB_SEPARATOR        = '|'
local state_mux_cable_table_name = 'MUX_CABLE_TABLE'
local ASIC_DB                   = 1
local ASIC_DB_SEPARATOR         = ':'
local asic_state_table_name     = 'ASIC_STATE'
local asic_route_key_prefix     = 'SAI_OBJECT_TYPE_ROUTE_ENTRY'
local asic_neigh_key_prefix     = 'SAI_OBJECT_TYPE_NEIGHBOR_ENTRY'
local asic_fdb_key_prefix       = 'SAI_OBJECT_TYPE_FDB_ENTRY'

if table.getn(ARGV) == 10 then
    APPL_DB                 = ARGV[1]
    APPL_DB_SEPARATOR       = ARGV[2]
    neighbor_table_name     = ARGV[3]
    mux_state_table_name    = ARGV[4]
    hw_mux_state_table_name = ARGV[5]
    STATE_DB                = ARGV[6]
    STATE_DB_SEPARATOR      = ARGV[7]
    state_mux_cable_table_name = ARGV[8]
    ASIC_DB                 = ARGV[9]
    ASIC_DB_SEPARATOR       = ARGV[10]
    asic_state_table_name   = ARGV[11]
end

local neighbors             = {}
local mux_states            = {}
local hw_mux_states         = {}
local port_neighbor_modes   = {}
local asic_fdb              = {}
local asic_route_table      = {}
local asic_neighbor_table   = {}
local asic_nexthop_table    = {}

-- read from STATE_DB
redis.call('SELECT', STATE_DB)

-- read neighbor_mode for each port from MUX_CABLE_TABLE
local state_mux_cable_keys = redis.call('KEYS', state_mux_cable_table_name .. STATE_DB_SEPARATOR .. '*')
for i, state_mux_cable_key in ipairs(state_mux_cable_keys) do
    local port_name = string.sub(state_mux_cable_key, string.len(state_mux_cable_table_name .. STATE_DB_SEPARATOR) + 1)
    local mode = redis.call('HGET', state_mux_cable_key, 'neighbor_mode')
    if mode ~= nil then
        port_neighbor_modes[port_name] = mode
    end
end

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

-- read ASIC route table with nexthop information
local route_prefix = asic_state_table_name .. ASIC_DB_SEPARATOR .. asic_route_key_prefix
local route_entries = redis.call('KEYS', route_prefix .. '*')
for i, route_entry in ipairs(route_entries) do
    local route_details = string.sub(route_entry, string.len(route_prefix) + 2)
    local nexthop_id = redis.call('HGET', route_entry, 'SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID')
    local route_info = {}
    route_info['route_details'] = route_details
    route_info['nexthop_id'] = nexthop_id
    table.insert(asic_route_table, route_info)
end

-- read ASIC neigh table
local neighbor_prefix = asic_state_table_name .. ASIC_DB_SEPARATOR .. asic_neigh_key_prefix
local neighbor_entries = redis.call('KEYS', neighbor_prefix .. '*')
for i, neighbor_entry in ipairs(neighbor_entries) do
    local neighbor_details = string.sub(neighbor_entry, string.len(neighbor_prefix) + 2)
    table.insert(asic_neighbor_table, neighbor_details)
end

-- read ASIC nexthop table
local nexthop_prefix = asic_state_table_name .. ASIC_DB_SEPARATOR .. 'SAI_OBJECT_TYPE_NEXT_HOP:'
local nexthop_entries = redis.call('KEYS', nexthop_prefix .. '*')
for i, nexthop_entry in ipairs(nexthop_entries) do
    local nexthop_id = string.sub(nexthop_entry, string.len(nexthop_prefix) + 1)
    local nexthop_type = redis.call('HGET', nexthop_entry, 'SAI_NEXT_HOP_ATTR_TYPE')
    local nexthop_info = {}
    nexthop_info['nexthop_id'] = nexthop_id
    nexthop_info['nexthop_type'] = nexthop_type

    -- Get tunnel ID if it's a tunnel nexthop
    if nexthop_type == 'SAI_NEXT_HOP_TYPE_TUNNEL_ENCAP' then
        nexthop_info['tunnel_id'] = redis.call('HGET', nexthop_entry, 'SAI_NEXT_HOP_ATTR_TUNNEL_ID')
    end

    asic_nexthop_table[nexthop_id] = nexthop_info
end

local result = {}
result['neighbors']         = neighbors
result['mux_states']        = mux_states
result['hw_mux_states']     = hw_mux_states
result['port_neighbor_modes'] = port_neighbor_modes
result['asic_fdb']          = asic_fdb
result['asic_route_table']  = asic_route_table
result['asic_neigh_table']  = asic_neighbor_table
result['asic_nexthop_table'] = asic_nexthop_table

return redis.status_reply(cjson.encode(result))
"""

DB_READ_SCRIPT_CONFIG_DB_KEY = "_DUALTOR_NEIGHBOR_CHECK_SCRIPT_SHA1"
ZERO_MAC = "00:00:00:00:00:00"
NEIGHBOR_ATTRIBUTES_HOST_ROUTE = ["NEIGHBOR", "MAC", "PORT", "MUX_STATE", "IN_MUX_TOGGLE", "NEIGHBOR_IN_ASIC", "TUNNEL_IN_ASIC", "HWSTATUS"]
NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE = ["NEIGHBOR", "MAC", "PORT", "MUX_STATE", "IN_MUX_TOGGLE", "NEIGHBOR_IN_ASIC", "PREFIX_ROUTE", "NEXTHOP_TYPE", "HWSTATUS"]
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
    def _load_script():
        redis_load_cmd = "SCRIPT LOAD \"%s\"" % DB_READ_SCRIPT
        db_read_script_sha1 = redis_cli(redis_load_cmd).strip()
        WRITE_LOG_INFO("loaded script sha1: %s", db_read_script_sha1)
        appl_db.set(DB_READ_SCRIPT_CONFIG_DB_KEY, db_read_script_sha1)
        return db_read_script_sha1

    def _is_script_existed(script_sha1):
        redis_script_exists_cmd = "SCRIPT EXISTS %s" % script_sha1
        cmd_output = redis_cli(redis_script_exists_cmd).strip()
        return "1" in cmd_output

    db_read_script_sha1 = appl_db.get(DB_READ_SCRIPT_CONFIG_DB_KEY)
    if ((not db_read_script_sha1) or (not _is_script_existed(db_read_script_sha1))):
        db_read_script_sha1 = _load_script()

    redis_run_cmd = "EVALSHA %s 0" % db_read_script_sha1
    result = redis_cli(redis_run_cmd).strip()
    tables = json.loads(result)

    neighbors = tables["neighbors"]
    mux_states = tables["mux_states"]
    hw_mux_states = tables["hw_mux_states"]
    port_neighbor_modes = tables.get("port_neighbor_modes", {})
    asic_fdb = {k: v.lstrip("oid:0x") for k, v in tables["asic_fdb"].items()}
    asic_route_table = tables["asic_route_table"]
    asic_neigh_table = tables["asic_neigh_table"]
    asic_nexthop_table = tables["asic_nexthop_table"]
    WRITE_LOG_DEBUG("neighbors: %s", json.dumps(neighbors, indent=4))
    WRITE_LOG_DEBUG("mux states: %s", json.dumps(mux_states, indent=4))
    WRITE_LOG_DEBUG("hw mux states: %s", json.dumps(hw_mux_states, indent=4))
    WRITE_LOG_DEBUG("port_neighbor_modes: %s", json.dumps(port_neighbor_modes, indent=4))
    WRITE_LOG_DEBUG("ASIC FDB: %s", json.dumps(asic_fdb, indent=4))
    WRITE_LOG_DEBUG("ASIC route table: %s", json.dumps(asic_route_table, indent=4))
    WRITE_LOG_DEBUG("ASIC neigh table: %s", json.dumps(asic_neigh_table, indent=4))
    WRITE_LOG_DEBUG("ASIC nexthop table: %s", json.dumps(asic_nexthop_table, indent=4))
    return neighbors, mux_states, hw_mux_states, port_neighbor_modes, asic_fdb, asic_route_table, asic_neigh_table, asic_nexthop_table


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
                               asic_route_table, asic_neigh_table, asic_nexthop_table,
                               mux_server_to_port_map, port_neighbor_modes):
    """Checks if neighbors are consistent with mux states."""

    # Parse route table to get route destinations and their nexthop types
    route_to_nexthop_map = {}
    asic_route_destinations = set()

    for route_info in asic_route_table:
        route_details = json.loads(route_info["route_details"])
        route_dest = route_details["dest"].split("/")[0]
        asic_route_destinations.add(route_dest)

        nexthop_id = route_info["nexthop_id"]

        nexthop_type = NOT_AVAILABLE
        if nexthop_id in asic_nexthop_table:
            nexthop_info = asic_nexthop_table[nexthop_id]
            if nexthop_info["nexthop_type"] == "SAI_NEXT_HOP_TYPE_TUNNEL_ENCAP":
                nexthop_type = "TUNNEL"
            elif nexthop_info["nexthop_type"] == "SAI_NEXT_HOP_TYPE_IP":
                nexthop_type = "NEIGHBOR"
            else:
                nexthop_type = nexthop_info["nexthop_type"]

        route_to_nexthop_map[route_dest] = nexthop_type

    asic_neighs = set(json.loads(_)["ip"] for _ in asic_neigh_table)

    check_results = []

    for neighbor_ip in natsorted(list(neighbors.keys())):
        mac = neighbors[neighbor_ip]

        is_zero_mac = (mac == ZERO_MAC)

        # Determine port and neighbor_mode for this neighbor
        port_name = None
        neighbor_mode = None

        if not is_zero_mac and mac in mac_to_port_name_map:
            port_name = mac_to_port_name_map[mac]
            # NOTE: mux server ips are always fixed to the mux port
            if neighbor_ip in mux_server_to_port_map:
                port_name = mux_server_to_port_map[neighbor_ip]
            # Get neighbor_mode for this port
            neighbor_mode = port_neighbor_modes.get(port_name, None)

            # Skip this neighbor if neighbor_mode is not set for the port
            if neighbor_mode is None or neighbor_mode == False:
                WRITE_LOG_WARN("neighbor %s on port %s: neighbor_mode not configured in STATE_DB MUX_CABLE_TABLE",
                              neighbor_ip, port_name)
                continue


        # Determine which attributes to use based on neighbor_mode
        if neighbor_mode == "prefix-route":
            neighbor_attrs = NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE
        elif neighbor_mode == "host-route":
            neighbor_attrs = NEIGHBOR_ATTRIBUTES_HOST_ROUTE
        else:
            # For zero-mac neighbors or neighbors without port, skip them
            WRITE_LOG_DEBUG("Skipping neighbor %s: unable to determine neighbor_mode (mac=%s, port=%s, mode=%s)",
                           neighbor_ip, mac, port_name if port_name else "N/A", neighbor_mode)
            continue

        check_result = {attr: NOT_AVAILABLE for attr in neighbor_attrs}
        check_result["NEIGHBOR"] = neighbor_ip
        check_result["MAC"] = mac
        check_result["_NEIGHBOR_MODE"] = neighbor_mode  # Internal field for grouping

        if mac not in mac_to_port_name_map and not is_zero_mac:
            check_results.append(check_result)
            continue

        check_result["NEIGHBOR_IN_ASIC"] = neighbor_ip in asic_neighs

        if neighbor_mode == "prefix-route":
            check_result["PREFIX_ROUTE"] = neighbor_ip in asic_route_destinations
            check_result["NEXTHOP_TYPE"] = route_to_nexthop_map.get(neighbor_ip, NOT_AVAILABLE)
        else:
            check_result["TUNNEL_IN_ASIC"] = neighbor_ip in asic_route_destinations

        if is_zero_mac:
            # NOTE: for zero-mac neighbors, two situations:
            # 1. new neighbor just learnt, no neighbor entry in ASIC, tunnel route present in ASIC.
            # 2. neighbor expired, neighbor entry still present in ASIC, no tunnel route in ASIC.
            if neighbor_mode == "prefix-route":
                check_result["HWSTATUS"] = check_result["NEIGHBOR_IN_ASIC"] or check_result["PREFIX_ROUTE"]
            else:
                check_result["HWSTATUS"] = check_result["NEIGHBOR_IN_ASIC"] or check_result["TUNNEL_IN_ASIC"]
        else:
            if port_name and port_name in mux_states:
                mux_state = mux_states[port_name]
                hw_mux_state = hw_mux_states[port_name]
                check_result["PORT"] = port_name
                check_result["MUX_STATE"] = mux_state
                check_result["IN_MUX_TOGGLE"] = mux_state != hw_mux_state

                if neighbor_mode == "prefix-route":
                    if mux_state == "active":
                        # For active mux state, neighbor should be in ASIC and route should point to neighbor nexthop
                        expected_nexthop = "NEIGHBOR"
                        check_result["HWSTATUS"] = (check_result["NEIGHBOR_IN_ASIC"] and
                                                    check_result["PREFIX_ROUTE"] and
                                                    check_result["NEXTHOP_TYPE"] == expected_nexthop)
                    elif mux_state == "standby":
                        # For standby mux state, route should point to tunnel nexthop
                        expected_nexthop = "TUNNEL"
                        check_result["HWSTATUS"] = (check_result["PREFIX_ROUTE"] and
                                                    check_result["NEXTHOP_TYPE"] == expected_nexthop)
                    else:
                        # skip as unknown mux state
                        continue
                else:
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

    # Group check results by neighbor_mode
    prefix_route_results = []
    host_route_results = []

    for check_result in check_results:
        port = check_result["PORT"]
        is_zero_mac = check_result["MAC"] == ZERO_MAC
        neighbor_mode = check_result.get("_NEIGHBOR_MODE", "host-route")

        if port == NOT_AVAILABLE and not is_zero_mac:
            continue

        in_toggle = check_result["IN_MUX_TOGGLE"]
        hwstatus = check_result["HWSTATUS"]
        if not is_zero_mac:
            check_result["IN_MUX_TOGGLE"] = bool_to_yes_no[in_toggle]
        check_result["NEIGHBOR_IN_ASIC"] = bool_to_yes_no[check_result["NEIGHBOR_IN_ASIC"]]

        if neighbor_mode == "prefix-route":
            check_result["PREFIX_ROUTE"] = bool_to_yes_no[check_result["PREFIX_ROUTE"]]
            prefix_route_results.append(check_result)
        else:
            check_result["TUNNEL_IN_ASIC"] = bool_to_yes_no[check_result["TUNNEL_IN_ASIC"]]
            host_route_results.append(check_result)

        check_result["HWSTATUS"] = bool_to_consistency[hwstatus]
        if (not hwstatus):
            if is_zero_mac:
                failed_neighbors.append(check_result)
            elif not in_toggle:
                failed_neighbors.append(check_result)

    # Display prefix-route neighbors if any
    if prefix_route_results:
        WRITE_LOG_WARN("=" * 80)
        WRITE_LOG_WARN("Neighbors in PREFIX-ROUTE mode:")
        WRITE_LOG_WARN("=" * 80)
        output_lines = tabulate.tabulate(
            [[result[attr] for attr in NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE] for result in prefix_route_results],
            headers=NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE,
            tablefmt="simple"
        )
        for output_line in output_lines.split("\n"):
            WRITE_LOG_WARN(output_line)
        WRITE_LOG_WARN("")

    # Display host-route neighbors if any
    if host_route_results:
        WRITE_LOG_WARN("=" * 80)
        WRITE_LOG_WARN("Neighbors in HOST-ROUTE mode:")
        WRITE_LOG_WARN("=" * 80)
        output_lines = tabulate.tabulate(
            [[result[attr] for attr in NEIGHBOR_ATTRIBUTES_HOST_ROUTE] for result in host_route_results],
            headers=NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        )
        for output_line in output_lines.split("\n"):
            WRITE_LOG_WARN(output_line)
        WRITE_LOG_WARN("")

    if failed_neighbors:
        WRITE_LOG_ERROR("Found neighbors that are inconsistent with mux states: %s", [_["NEIGHBOR"] for _ in failed_neighbors])

        # Group failed neighbors by mode for error output
        failed_prefix = [n for n in failed_neighbors if n.get("_NEIGHBOR_MODE") == "prefix-route"]
        failed_host = [n for n in failed_neighbors if n.get("_NEIGHBOR_MODE") != "prefix-route"]

        if failed_prefix:
            WRITE_LOG_ERROR("Failed PREFIX-ROUTE neighbors:")
            err_output_lines = tabulate.tabulate(
                [[neighbor[attr] for attr in NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE] for neighbor in failed_prefix],
                headers=NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE,
                tablefmt="simple"
            )
            for output_line in err_output_lines.split("\n"):
                WRITE_LOG_ERROR(output_line)

        if failed_host:
            WRITE_LOG_ERROR("Failed HOST-ROUTE neighbors:")
            err_output_lines = tabulate.tabulate(
                [[neighbor[attr] for attr in NEIGHBOR_ATTRIBUTES_HOST_ROUTE] for neighbor in failed_host],
                headers=NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
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
    neighbors, mux_states, hw_mux_states, port_neighbor_modes, asic_fdb, asic_route_table, asic_neigh_table, \
        asic_nexthop_table = read_tables_from_db(appl_db)
    mac_to_port_name_map = get_mac_to_port_name_map(asic_fdb, if_oid_to_port_name_map)

    check_results = check_neighbor_consistency(
        neighbors,
        mux_states,
        hw_mux_states,
        mac_to_port_name_map,
        asic_route_table,
        asic_neigh_table,
        asic_nexthop_table,
        mux_server_to_port_map,
        port_neighbor_modes
    )
    res = parse_check_results(check_results)
    sys.exit(0 if res else 1)
