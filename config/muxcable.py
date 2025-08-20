import json
import os
import sys
import time

import click
import re
from natsort import natsorted
import utilities_common.cli as clicommon
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from swsscommon import swsscommon
from tabulate import tabulate
from utilities_common import platform_sfputil_helper
from utilities_common.general import get_optional_value_for_key_in_config_tbl 

platform_sfputil = None

REDIS_TIMEOUT_MSECS = 0
SELECT_TIMEOUT = 1000

# The empty namespace refers to linux host namespace.
EMPTY_NAMESPACE = ''


CONFIG_SUCCESSFUL = 0
CONFIG_FAIL = 1

VENDOR_NAME = "Credo"
VENDOR_MODEL_REGEX = re.compile(r"CAC\w{3}321P2P\w{2}MS")

# Helper functions


def db_connect(db_name, namespace=EMPTY_NAMESPACE):
    return swsscommon.DBConnector(db_name, REDIS_TIMEOUT_MSECS, True, namespace)


target_dict = { "NIC":"0",
                "TORA":"1",
                "TORB":"2",
                "LOCAL":"3"}

def parse_target(target):
    return target_dict.get(target, None)

def get_value_for_key_in_dict(mdict, port, key, table_name):
    value = mdict.get(key, None)
    if value is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table_name))
        sys.exit(CONFIG_FAIL)
    return value


def delete_all_keys_in_db_table(db_type, table_name):

    redis_db = {}
    table = {}
    table_keys = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        redis_db[asic_id] = db_connect(db_type, namespace)
        table[asic_id] = swsscommon.Table(redis_db[asic_id], table_name)
        table_keys[asic_id] = table[asic_id].getKeys()
        for key in table_keys[asic_id]:
            table[asic_id]._del(key)


def update_and_get_response_for_xcvr_cmd(cmd_name, rsp_name, exp_rsp, cmd_table_name, cmd_arg_table_name, rsp_table_name, port, cmd_timeout_secs, param_dict=None, arg=None):

    res_dict = {}
    state_db, appl_db = {}, {}
    firmware_rsp_tbl, firmware_rsp_tbl_keys = {}, {}
    firmware_rsp_sub_tbl = {}
    firmware_cmd_tbl, firmware_cmd_arg_tbl = {}, {}

    CMD_TIMEOUT_SECS = cmd_timeout_secs

    time_start = time.time()

    sel = swsscommon.Select()
    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        appl_db[asic_id] = db_connect("APPL_DB", namespace)
        firmware_cmd_tbl[asic_id] = swsscommon.Table(appl_db[asic_id], cmd_table_name)
        if cmd_arg_table_name is not None:
            firmware_cmd_arg_tbl[asic_id] = swsscommon.Table(appl_db[asic_id], cmd_arg_table_name)
        firmware_rsp_sub_tbl[asic_id] = swsscommon.SubscriberStateTable(state_db[asic_id], rsp_table_name)
        firmware_rsp_tbl[asic_id] = swsscommon.Table(state_db[asic_id], rsp_table_name)
        firmware_rsp_tbl_keys[asic_id] = firmware_rsp_tbl[asic_id].getKeys()
        for key in firmware_rsp_tbl_keys[asic_id]:
            firmware_rsp_tbl[asic_id]._del(key)
        sel.addSelectable(firmware_rsp_sub_tbl[asic_id])

    rc = CONFIG_FAIL
    res_dict[0] = CONFIG_FAIL
    res_dict[1] = 'unknown'

    logical_port_list = platform_sfputil_helper.get_logical_list()
    if port not in logical_port_list:
        click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
        res_dict[0] = rc
        return res_dict

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant perform firmware cmd".format(port))
            res_dict[0] = rc
            return res_dict

    if arg is None:
        cmd_arg = "null"
    else:
        cmd_arg = str(arg)

    if param_dict is not None:
        for key, value in param_dict.items():
            fvs = swsscommon.FieldValuePairs([(str(key), str(value))])
            firmware_cmd_arg_tbl[asic_index].set(port, fvs)

    fvs = swsscommon.FieldValuePairs([(cmd_name, cmd_arg)])
    firmware_cmd_tbl[asic_index].set(port, fvs)

    # Listen indefinitely for changes to the HW_MUX_CABLE_TABLE in the Application DB's
    while True:
        # Use timeout to prevent ignoring the signals we want to handle
        # in signal_handler() (e.g. SIGTERM for graceful shutdown)

        (state, selectableObj) = sel.select(SELECT_TIMEOUT)

        time_now = time.time()
        time_diff = time_now - time_start
        if time_diff >= CMD_TIMEOUT_SECS:
            return res_dict

        if state == swsscommon.Select.TIMEOUT:
            # Do not flood log when select times out
            continue
        if state != swsscommon.Select.OBJECT:
            click.echo("sel.select() did not  return swsscommon.Select.OBJECT for sonic_y_cable updates")
            continue

        # Get the redisselect object  from selectable object
        redisSelectObj = swsscommon.CastSelectableToRedisSelectObj(
            selectableObj)
        # Get the corresponding namespace from redisselect db connector object
        namespace = redisSelectObj.getDbConnector().getNamespace()
        asic_index = multi_asic.get_asic_index_from_namespace(namespace)

        (port_m, op_m, fvp_m) = firmware_rsp_sub_tbl[asic_index].pop()

        if not port_m:
            click.echo("Did not receive a port response {}".format(port))
            res_dict[1] = 'unknown'
            res_dict[0] = CONFIG_FAIL
            firmware_rsp_tbl[asic_index]._del(port)
            break

        if port_m != port:

            res_dict[1] = 'unknown'
            res_dict[0] = CONFIG_FAIL
            firmware_rsp_tbl[asic_index]._del(port)
            continue

        if fvp_m:

            fvp_dict = dict(fvp_m)
            if rsp_name in fvp_dict:
                # check if xcvrd got a probe command
                result = fvp_dict[rsp_name]

                if result == exp_rsp:
                    res_dict[1] = result
                    res_dict[0] = 0
                else:
                    res_dict[1] = result
                    res_dict[0] = CONFIG_FAIL

                firmware_rsp_tbl[asic_index]._del(port)
                break
            else:
                res_dict[1] = 'unknown'
                res_dict[0] = CONFIG_FAIL
                firmware_rsp_tbl[asic_index]._del(port)
                break
        else:
            res_dict[1] = 'unknown'
            res_dict[0] = CONFIG_FAIL
            firmware_rsp_tbl[asic_index]._del(port)
            break

    delete_all_keys_in_db_table("STATE_DB", rsp_table_name)

    return res_dict

def get_value_for_key_in_config_tbl(config_db, port, key, table):
    info_dict = {}
    info_dict = config_db.get_entry(table, port)
    if info_dict is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table))
        sys.exit(CONFIG_FAIL)

    value = get_value_for_key_in_dict(info_dict, port, key, table)

    return value

#
# 'muxcable' command ("config muxcable")
#


@click.group(name='muxcable', cls=clicommon.AliasedGroup)
def muxcable():
    """Show muxcable information"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(CONFIG_FAIL)

    global platform_sfputil
    # Load platform-specific sfputil class
    platform_sfputil_helper.load_platform_sfputil()

    # Load port info
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()

    platform_sfputil = platform_sfputil_helper.platform_sfputil


def lookup_statedb_and_update_configdb(db, per_npu_statedb, config_db, port, state_cfg_val, port_status_dict):

    muxcable_statedb_dict = per_npu_statedb.get_all(per_npu_statedb.STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
    configdb_state = get_value_for_key_in_config_tbl(config_db, port, "state", "MUX_CABLE")
    ipv4_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv4", "MUX_CABLE")
    ipv6_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv6", "MUX_CABLE")
    soc_ipv4_value = get_optional_value_for_key_in_config_tbl(config_db, port, "soc_ipv4", "MUX_CABLE")
    cable_type = get_optional_value_for_key_in_config_tbl(config_db, port, "cable_type", "MUX_CABLE")
    ctx = click.get_current_context()
    state = get_value_for_key_in_dict(muxcable_statedb_dict, port, "state", "MUX_CABLE_TABLE")

    port_name = platform_sfputil_helper.get_interface_alias(port, db)

    if str(state_cfg_val) == str(configdb_state):
        port_status_dict[port_name] = 'OK'
    else:
        if cable_type is not None or soc_ipv4_value is not None:
            try:
                config_db.set_entry("MUX_CABLE", port, {"state": state_cfg_val,
                                                        "server_ipv4": ipv4_value,
                                                        "server_ipv6": ipv6_value, 
                                                        "soc_ipv4":soc_ipv4_value, 
                                                        "cable_type": cable_type})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        else:
            try:
                config_db.set_entry("MUX_CABLE", port, {"state": state_cfg_val,
                                                        "server_ipv4": ipv4_value,
                                                        "server_ipv6": ipv6_value}) 
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        if (str(state_cfg_val) == 'active' and str(state) != 'active') or (str(state_cfg_val) == 'standby' and str(state) != 'standby'):
            port_status_dict[port_name] = 'INPROGRESS'
        else:
            port_status_dict[port_name] = 'OK'

def update_configdb_pck_loss_data(config_db, port, val):
    fvs = {}
    configdb_state = get_value_for_key_in_config_tbl(config_db, port, "state", "MUX_CABLE")
    fvs["state"] = configdb_state
    ipv4_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv4", "MUX_CABLE")
    fvs["server_ipv4"] = ipv4_value
    ipv6_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv6", "MUX_CABLE")
    fvs["server_ipv6"] = ipv6_value
    soc_ipv4_value = get_optional_value_for_key_in_config_tbl(config_db, port, "soc_ipv4", "MUX_CABLE")
    if soc_ipv4_value is not None:
        fvs["soc_ipv4"] = soc_ipv4_value
    cable_type = get_optional_value_for_key_in_config_tbl(config_db, port, "cable_type", "MUX_CABLE")
    if cable_type is not None:
        fvs["cable_type"] = cable_type
    prober_type_val = get_optional_value_for_key_in_config_tbl(config_db, port, "prober_type", "MUX_CABLE")
    if prober_type_val is not None:
        fvs["prober_type"] = prober_type_val

    fvs["pck_loss_data_reset"] = val
    try:
        config_db.set_entry("MUX_CABLE", port, fvs)
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


def update_configdb_prober_type(config_db, port, val):
    fvs = {}
    configdb_state = get_value_for_key_in_config_tbl(config_db, port, "state", "MUX_CABLE")
    fvs["state"] = configdb_state
    ipv4_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv4", "MUX_CABLE")
    fvs["server_ipv4"] = ipv4_value
    ipv6_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv6", "MUX_CABLE")
    fvs["server_ipv6"] = ipv6_value
    soc_ipv4_value = get_optional_value_for_key_in_config_tbl(config_db, port, "soc_ipv4", "MUX_CABLE")
    if soc_ipv4_value is not None:
        fvs["soc_ipv4"] = soc_ipv4_value
    cable_type = get_optional_value_for_key_in_config_tbl(config_db, port, "cable_type", "MUX_CABLE")
    if cable_type is not None:
        fvs["cable_type"] = cable_type
    pck_loss_data = get_optional_value_for_key_in_config_tbl(config_db, port, "pck_loss_data_reset", "MUX_CABLE")
    if pck_loss_data is not None:
        fvs["pck_loss_data_reset"] = pck_loss_data

    fvs["prober_type"] = val
    try:
        config_db.set_entry("MUX_CABLE", port, fvs)
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

# 'muxcable' command ("config muxcable mode <port|all> active|auto")
@muxcable.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["active", "auto", "manual", "standby", "detach"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL)
@clicommon.pass_db
def mode(db, state, port, json_output):
    """Config muxcable mode"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    port_table_keys = {}
    y_cable_asic_table_keys = {}
    per_npu_configdb = {}
    per_npu_statedb = {}
    mux_tbl_cfg_db = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        mux_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("MUX_CABLE")

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')

    if port is not None and port != "all":

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(CONFIG_FAIL)

        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            if logical_key in y_cable_asic_table_keys:
                port_status_dict = {}
                lookup_statedb_and_update_configdb(
                    db, per_npu_statedb[asic_index], per_npu_configdb[asic_index], port, state, port_status_dict)

                if json_output:
                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                else:
                    headers = ['port', 'state']
                    data = sorted([(k, v) for k, v in port_status_dict.items()])
                    click.echo(tabulate(data, headers=headers))

                sys.exit(CONFIG_SUCCESSFUL)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        port_status_dict = {}
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                logical_port = key.split("|")[1]
                lookup_statedb_and_update_configdb(
                    db, per_npu_statedb[asic_id], per_npu_configdb[asic_id], logical_port, state, port_status_dict)

            if json_output:
                click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
            else:
                data = sorted([(k, v) for k, v in port_status_dict.items()])

                headers = ['port', 'state']
                click.echo(tabulate(data, headers=headers))

        sys.exit(CONFIG_SUCCESSFUL)


# 'muxcable' command ("config muxcable probertype hardware/software <port|all>")
@muxcable.command()
@click.argument('probertype', metavar='<operation_status>', required=True, type=click.Choice(["hardware", "software"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def probertype(db, probertype, port):
    """Config muxcable probertype"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    port_table_keys = {}
    y_cable_asic_table_keys = {}
    per_npu_configdb = {}
    per_npu_statedb = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')

    if port is not None and port != "all":

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(CONFIG_FAIL)

        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            if logical_key in y_cable_asic_table_keys:
                update_configdb_prober_type(per_npu_configdb[asic_index], port, probertype)
                sys.exit(CONFIG_SUCCESSFUL)
            else:
                click.echo("this is not a valid port {} present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic asic-{} table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                logical_port = key.split("|")[1]
                update_configdb_prober_type(per_npu_configdb[asic_id], logical_port, probertype)

        sys.exit(CONFIG_SUCCESSFUL)


# 'muxcable' command ("config muxcable kill-radv <enable|disable> ")
@muxcable.command(short_help="Kill radv service when it is meant to be stopped, so no good-bye packet is sent for ceasing To Be an Advertising Interface")
@click.argument('knob', metavar='<feature_knob>', required=True, type=click.Choice(["enable", "disable"]))
@clicommon.pass_db
def kill_radv(db, knob):
    """config muxcable kill radv"""

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()

        mux_lmgrd_cfg_tbl = config_db.get_table("MUX_LINKMGR")
        config_db.mod_entry("MUX_LINKMGR", "SERVICE_MGMT", {"kill_radv": "True" if knob == "enable" else "False"})

# 'muxcable' command ("config muxcable packetloss reset <port|all>")
@muxcable.command()
@click.argument('action', metavar='<action_name>', required=True, type=click.Choice(["reset"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def packetloss(db, action, port):
    """config muxcable packetloss reset"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    port_table_keys = {}
    mux_cable_table_keys = {}
    pck_loss_table_keys = {}
    per_npu_configdb = {}
    per_npu_statedb = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        per_npu_statedb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'LINK_PROBE_STATS|*')
        mux_cable_table_keys[asic_id] = per_npu_configdb[asic_id].get_table("MUX_CABLE").keys() # keys here are port names
    if port is not None and port != "all":

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(CONFIG_FAIL)

        if per_npu_statedb[asic_index] is not None:
            pck_loss_table_keys = port_table_keys[asic_index]
            logical_key = "LINK_PROBE_STATS|{}".format(port)
            if logical_key in pck_loss_table_keys:
                update_configdb_pck_loss_data(per_npu_configdb[asic_index], port, "reset")
                sys.exit(CONFIG_SUCCESSFUL)
            else:
                click.echo("this is not a valid port present on pck_loss_stats".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                logical_port = key.split("|")[1]
                if logical_port in mux_cable_table_keys[asic_id]:
                    update_configdb_pck_loss_data(per_npu_configdb[asic_id], logical_port, "reset")

        sys.exit(CONFIG_SUCCESSFUL)

@muxcable.group(cls=clicommon.AbbreviationGroup)
def prbs():
    """Enable/disable PRBS mode on a port"""
    pass


@prbs.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.argument('mode_value', required=True, default=None, type=click.INT)
@click.argument('lane_mask', required=True, default=None, type=click.INT)
@click.argument('prbs_direction', metavar='<PRBS_DIRECTION> PRBS_DIRECTION_BOTH = 0 PRBS_DIRECTION_GENERATOR = 1 PRBS_DIRECTION_CHECKER = 2', required=False, default="0", type=click.Choice(["0", "1", "2"]))
@clicommon.pass_db
def enable(db, port, target, mode_value, lane_mask, prbs_direction):
    """Enable PRBS mode on a port args port target mode_value lane_mask prbs_direction
       example sudo config mux prbs enable Ethernet48 0 3 3 0
    """

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

    if port is not None:
        click.confirm(('Muxcable at port {} will be changed to PRBS mode {} state; disable traffic Continue?'.format(
            port, mode_value)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target
        param_dict["mode_value"] = mode_value
        param_dict["lane_mask"] = lane_mask
        param_dict["direction"] = prbs_direction

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_prbs", "status", "True", "XCVRD_CONFIG_PRBS_CMD", "XCVRD_CONFIG_PRBS_CMD_ARG", "XCVRD_CONFIG_PRBS_RSP", port, 30, param_dict, "enable")

        rc = res_dict[0]

        port = platform_sfputil_helper.get_interface_alias(port, db)
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

        if rc == 0:
            click.echo("Success in PRBS mode port {} to {}".format(port, mode_value))
        else:
            click.echo("ERR: Unable to set PRBS mode port {} to {}".format(port, mode_value))
            sys.exit(CONFIG_FAIL)


@prbs.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.argument('prbs_direction',  metavar='<PRBS_DIRECTION> PRBS_DIRECTION_BOTH = 0 PRBS_DIRECTION_GENERATOR = 1 PRBS_DIRECTION_CHECKER = 2', required=False, default="0", type=click.Choice(["0", "1", "2"]))
@clicommon.pass_db
def disable(db, port, target, prbs_direction):
    """Disable PRBS mode on a port
       example sudo config mux prbs disable Ethernet48 0
    """
    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

    if port is not None:
        click.confirm(('Muxcable at port {} will be changed to disable PRBS mode {} target; disable traffic Continue?'.format(
            port, target)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target
        param_dict["direction"] = prbs_direction

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_prbs", "status", "True", "XCVRD_CONFIG_PRBS_CMD", "XCVRD_CONFIG_PRBS_CMD_ARG", "XCVRD_CONFIG_PRBS_RSP", port, 30, param_dict, "disable")

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)
        if rc == 0:
            click.echo("Success in disable PRBS mode port {} on target {}".format(port, target))
        else:
            click.echo("ERR: Unable to disable PRBS mode port {} on target {}".format(port, target))
            sys.exit(CONFIG_FAIL)


@muxcable.group(cls=clicommon.AbbreviationGroup)
def loopback():
    """Enable/disable loopback mode on a port"""
    pass


@loopback.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.argument('lane_mask', required=True, default=None, type=click.INT)
@click.argument('mode_value', required=False, metavar='<Loop mode> 1 LOOPBACK_MODE_NEAR_END 2 LOOPBACK_MODE_FAR_END', default="1", type=click.Choice(["1", "2"]))
@clicommon.pass_db
def enable(db, port, target, lane_mask, mode_value):
    """Enable loopback mode on a port args port target lane_map mode_value"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_LOOP_RSP")

    if port is not None:
        click.confirm(('Muxcable at port {} will be changed to LOOP mode {} state; disable traffic Continue?'.format(
            port, mode_value)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target
        param_dict["mode_value"] = mode_value
        param_dict["lane_mask"] = lane_mask

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_loop", "status", "True", "XCVRD_CONFIG_LOOP_CMD", "XCVRD_CONFIG_LOOP_CMD_ARG", "XCVRD_CONFIG_LOOP_RSP", port, 30, param_dict, "enable")

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_LOOP_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)
        if rc == 0:
            click.echo("Success in LOOP mode port {} to {}".format(port, mode_value))
        else:
            click.echo("ERR: Unable to set LOOP mode port {} to {}".format(port, mode_value))
            sys.exit(CONFIG_FAIL)


@loopback.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@clicommon.pass_db
def disable(db, port, target):
    """Disable loopback mode on a port"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_LOOP_RSP")

    if port is not None:
        click.confirm(('Muxcable at port {} will be changed to disable LOOP mode {} state; disable traffic Continue?'.format(
            port, target)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_loop", "status", "True", "XCVRD_CONFIG_LOOP_CMD", "XCVRD_CONFIG_LOOP_CMD_ARG", "XCVRD_CONFIG_LOOP_RSP", port, 30, param_dict, "disable")

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_LOOP_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_LOOP_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)
        if rc == 0:
            click.echo("Success in disable LOOP mode port {} to {}".format(port, target))
        else:
            click.echo("ERR: Unable to set disable LOOP mode port {} to {}".format(port, target))
            sys.exit(CONFIG_FAIL)


@muxcable.group(cls=clicommon.AbbreviationGroup)
def hwmode():
    """Configure muxcable hardware directly"""
    pass


@hwmode.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["active", "standby"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def state(db, state, port):
    """Configure the muxcable mux state {active/standby}"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_DIR_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_DIR_RSP")

    if port is not None and port != "all":
        click.confirm(('Muxcable at port {} will be changed to {} state. Continue?'.format(port, state)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd(
            "config", "result", "True", "XCVRD_CONFIG_HWMODE_DIR_CMD", None, "XCVRD_CONFIG_HWMODE_DIR_RSP", port, 1, None, state)

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_DIR_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_DIR_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if rc == 0:
            click.echo("Success in toggling port {} to {}".format(port, state))
        else:
            click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
            sys.exit(CONFIG_FAIL)

    elif port == "all":
        click.confirm(('Muxcable at all ports will be changed to {} state. Continue?'.format(state)), abort=True)

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = 0

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            res_dict = {}
            res_dict[0] = CONFIG_FAIL
            res_dict[1] = 'unknown'

            res_dict = update_and_get_response_for_xcvr_cmd(
                "config", "result", "True", "XCVRD_CONFIG_HWMODE_DIR_CMD", None, "XCVRD_CONFIG_HWMODE_DIR_RSP", port, 1, None, state)

            rc = res_dict[0]

            delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_DIR_CMD")
            delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_DIR_RSP")

            port = platform_sfputil_helper.get_interface_alias(port, db)

            if rc == 0:
                click.echo("Success in toggling port {} to {}".format(port, state))
            else:
                click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@hwmode.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["auto", "manual"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def setswitchmode(db, state, port):
    """Configure the muxcable mux switching mode {auto/manual}"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_SWMODE_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_SWMODE_RSP")

    if port is not None and port != "all":
        click.confirm(('Muxcable at port {} will be changed to {} switching mode. Continue?'.format(port, state)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd(
            "config", "result", "True", "XCVRD_CONFIG_HWMODE_SWMODE_CMD", None, "XCVRD_CONFIG_HWMODE_SWMODE_RSP", port, 1, None, state)

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_SWMODE_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_SWMODE_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if rc == 0:
            click.echo("Success in switch muxcable mode port {} to {}".format(port, state))
        else:
            click.echo("ERR: Unable to switch muxcable mode port {} to {}".format(port, state))
            sys.exit(CONFIG_FAIL)

    elif port == "all":
        click.confirm(('Muxcable at all ports will be changed to {} switching mode. Continue?'.format(state)), abort=True)

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = 0

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            res_dict = {}
            res_dict[0] = CONFIG_FAIL
            res_dict[1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd(
                "config", "result", "True", "XCVRD_CONFIG_HWMODE_SWMODE_CMD", None, "XCVRD_CONFIG_HWMODE_SWMODE_RSP", port, 1, None, state)

            rc = res_dict[0]

            delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_SWMODE_CMD")
            delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_SWMODE_RSP")

            port = platform_sfputil_helper.get_interface_alias(port, db)

            if rc == 0:
                click.echo("Success in toggling port {} to {}".format(port, state))
            else:
                click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@muxcable.group(cls=clicommon.AbbreviationGroup)
def firmware():
    """Configure muxcable firmware command"""
    pass


@firmware.command()
@click.argument('fwfile', metavar='<firmware_file>', required=True)
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def download(db, fwfile, port):
    """Config muxcable firmware download"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")

    if port is not None and port != "all":

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd(
            "download_firmware", "status", "0", "XCVRD_DOWN_FW_CMD", None, "XCVRD_DOWN_FW_RSP", port, 1000, None, fwfile)

        rc = res_dict[0]

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if rc == 0:
            click.echo("Success in downloading firmware port {} {}".format(port, fwfile))
        else:
            click.echo("ERR: Unable to download firmware port {} {}".format(port, fwfile))
            sys.exit(CONFIG_FAIL)

    elif port == "all":
        click.confirm(('Muxcable at all ports will be changed to {} switching mode. Continue?'.format(state)), abort=True)

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            res_dict = {}

            res_dict[0] = CONFIG_FAIL
            res_dict[1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd(
                "download_firmware", "status", "0", "XCVRD_DOWN_FW_CMD", "XCVRD_DOWN_FW_RSP", port, 1000, fwfile)

            rc = res_dict[0]

            delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")

            port = platform_sfputil_helper.get_interface_alias(port, db)

            if rc == 0:
                click.echo("Success in downloading firmware port {} {}".format(port, fwfile))
            else:
                click.echo("ERR: Unable to download firmware port {} {}".format(port, fwfile))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('fwfile', metavar='<firmware_file>', required=False, default=None)
@click.option('--nonhitless', 'nonhitless', required=False, is_flag=True, type=click.BOOL)
@clicommon.pass_db
def activate(db, port, fwfile, nonhitless):
    """Config muxcable firmware activate"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("STATE_DB", "XCVRD_ACTI_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD_ARG")

    if port is not None and port != "all":

        res_dict = {}
        param_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        if nonhitless:
            param_dict["hitless"] = "1"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "activate_firmware", "status", "0", "XCVRD_ACTI_FW_CMD", "XCVRD_ACTI_FW_CMD_ARG", "XCVRD_ACTI_FW_RSP", port, 60, param_dict, fwfile)

        rc = res_dict[0]

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_ACTI_FW_RSP")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD")

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if rc == 0:
            click.echo("Success in activate firmware port {} fwfile {}".format(port, fwfile))
        else:
            click.echo("ERR: Unable to activate firmware port {} fwfile {}".format(port, fwfile))
            sys.exit(CONFIG_FAIL)

    elif port == "all":

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            res_dict = {}

            res_dict[0] = CONFIG_FAIL
            res_dict[1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd(
                "activate_firmware", "status", "0", "XCVRD_ACTI_FW_CMD", None, "XCVRD_ACTI_FW_RSP", port, 60, None, fwfile)

            delete_all_keys_in_db_table("STATE_DB", "XCVRD_ACTI_FW_RSP")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD_ARG")

            rc = res_dict[0]

            port = platform_sfputil_helper.get_interface_alias(port, db)

            if rc == 0:
                click.echo("Success in activate firmware port {} fwfile {}".format(port, fwfile))
            else:
                click.echo("ERR: Unable to activate firmware port {} fwfile {}".format(port, fwfile))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('fwfile', metavar='<firmware_file>', required=False, default=None)
@clicommon.pass_db
def rollback(db, port, fwfile):
    """Config muxcable firmware rollback"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("STATE_DB", "XCVRD_ROLL_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_ROLL_FW_CMD")

    if port is not None and port != "all":

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd(
            "rollback_firmware", "status", "0", "XCVRD_ROLL_FW_CMD", None, "XCVRD_ROLL_FW_RSP", port, 60, None, fwfile)

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_ROLL_FW_RSP")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_ROLL_FW_CMD")

        rc = res_dict[0]

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if rc == 0:
            click.echo("Success in rollback firmware port {} fwfile {}".format(port, fwfile))
        else:
            click.echo("ERR: Unable to rollback firmware port {} fwfile {}".format(port, fwfile))
            sys.exit(CONFIG_FAIL)

    elif port == "all":

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            res_dict = {}

            res_dict[0] = CONFIG_FAIL
            res_dict[1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd(
                "rollback_firmware", "status", "0", "XCVRD_ROLL_FW_CMD", None, "XCVRD_ROLL_FW_RSP", port, 60, None, fwfile)

            delete_all_keys_in_db_table("STATE_DB", "XCVRD_ROLL_FW_RSP")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_ROLL_FW_CMD")

            rc = res_dict[0]

            port = platform_sfputil_helper.get_interface_alias(port, db)

            if rc == 0:
                click.echo("Success in rollback firmware port {} fwfile {}".format(port, fwfile))
            else:
                click.echo("ERR: Unable to rollback firmware port {} fwfile {}".format(port, fwfile))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@muxcable.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@clicommon.pass_db
def reset(db, port, target):
    """reset a target on the cable NIC TORA TORB Local """

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

    if port is not None:
        click.confirm(('Muxcable at port {} will be reset; CAUTION: disable traffic Continue?'.format(port)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_prbs", "status", "True", "XCVRD_CONFIG_PRBS_CMD", "XCVRD_CONFIG_PRBS_CMD_ARG", "XCVRD_CONFIG_PRBS_RSP", port, 30, param_dict, "reset")

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)
        if rc == 0:
            click.echo("Success in reset port {}".format(port))
        else:
            click.echo("ERR: Unable to reset port {}".format(port))
            sys.exit(CONFIG_FAIL)


@muxcable.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.argument('mode', required=True, metavar='<mode> 0 disable 1 enable',  default=True, type=click.Choice(["0", "1"]))
@clicommon.pass_db
def set_anlt(db, port, target, mode):
    """Enable anlt mode on a port args port <target> NIC TORA TORB LOCAL enable/disable 1/0"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

    if port is not None:
        click.confirm(
            ('Muxcable at port {} will be changed to enable/disable anlt mode {} state; disable traffic Continue?'.format(port, mode)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target
        param_dict["mode"] = mode

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_prbs", "status", "True", "XCVRD_CONFIG_PRBS_CMD", "XCVRD_CONFIG_PRBS_CMD_ARG", "XCVRD_CONFIG_PRBS_RSP", port, 30, param_dict, "anlt")

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)
        if rc == 0:
            click.echo("Success in anlt enable/disable port {} to {}".format(port, mode))
        else:
            click.echo("ERR: Unable to set anlt enable/disable port {} to {}".format(port, mode))
            sys.exit(CONFIG_FAIL)

@muxcable.command()
@click.argument('port', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.argument('mode', required=True, metavar='<mode> FEC_MODE_NONE 0 FEC_MODE_RS 1 FEC_MODE_FC 2',  default=True, type=click.Choice(["0", "1", "2"]))
@clicommon.pass_db
def set_fec(db, port, target, mode):
    """Enable fec mode on a port args port <target>  NIC TORA TORB LOCAL <mode_value> FEC_MODE_NONE 0 FEC_MODE_RS 1 FEC_MODE_FC 2 """

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

    if port is not None:
        click.confirm(
            ('Muxcable at port {} will be changed to enable/disable fec mode {} state; disable traffic Continue?'.format(port, mode)), abort=True)

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target
        param_dict["mode"] = mode

        res_dict = update_and_get_response_for_xcvr_cmd(
            "config_prbs", "status", "True", "XCVRD_CONFIG_PRBS_CMD", "XCVRD_CONFIG_PRBS_CMD_ARG", "XCVRD_CONFIG_PRBS_RSP", port, 30, param_dict, "fec")

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_PRBS_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_PRBS_RSP")

        port = platform_sfputil_helper.get_interface_alias(port, db)
        if rc == 0:
            click.echo("Success in fec enable/disable port {} to {}".format(port, mode))
        else:
            click.echo("ERR: Unable to set fec enable/disable port {} to {}".format(port, mode))
            sys.exit(CONFIG_FAIL)

def update_configdb_ycable_telemetry_data(config_db, key, val):
    log_verbosity = get_value_for_key_in_config_tbl(config_db, key, "log_verbosity", "XCVRD_LOG")

    config_db.set_entry("XCVRD_LOG", key, {"log_verbosity": log_verbosity,
                                                "disable_telemetry": val})
    return 0

@muxcable.command()
@click.argument('state', metavar='<enable/disable telemetry>', required=True, type=click.Choice(["enable", "disable"]))
@clicommon.pass_db
def telemetry(db, state):
    """Enable/Disable Telemetry for ycabled """

    per_npu_configdb = {}
    xcvrd_log_cfg_db_tbl = {}

    if state == 'enable':
        val = 'False'
    elif state == 'disable':
        val = 'True'


    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        per_npu_configdb[asic_id].connect()

        xcvrd_log_cfg_db_tbl[asic_id] = per_npu_configdb[asic_id].get_table("XCVRD_LOG")

    asic_index = multi_asic.get_asic_index_from_namespace(EMPTY_NAMESPACE)
    rc = update_configdb_ycable_telemetry_data(per_npu_configdb[asic_index], "Y_CABLE", val)


    if rc == 0:
        click.echo("Success in ycabled telemetry state to {}".format(state))
    else:
        click.echo("ERR: Unable to set ycabled telemetry state to {}".format(state))
        sys.exit(CONFIG_FAIL)


# 'muxcable' command ("config muxcable reset-heartbeat-suspend <port|all>")
@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def reset_heartbeat_suspend(db, port):
    """Reset the mux port heartbeat suspend."""

    if port is None:
        click.echo("no port provided")
        sys.exit(CONFIG_FAIL)

    port = platform_sfputil_helper.get_interface_name(port, db)
    asic_index = multi_asic.get_asic_index_from_namespace(EMPTY_NAMESPACE)
    config_dbs = {}
    mux_linkmgrd_tables = {}
    mux_config_tables = {}

    # Getting all front asic namespace and correspding config DB connector
    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_index = multi_asic.get_asic_index_from_namespace(namespace)
        config_dbs[asic_index] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_dbs[asic_index].connect()
        mux_linkmgrd_tables[asic_index] = config_dbs[asic_index].get_table("MUX_LINKMGR")
        mux_config_tables[asic_index] = config_dbs[asic_index].get_table("MUX_CABLE")

    mux_ports = []
    if port == "all":
        for asic_index, mux_config_table in mux_config_tables.items():
            config_db = config_dbs[asic_index]
            mux_linkmgrd_table = mux_linkmgrd_tables[asic_index]
            mux_ports = [p for p, c in mux_config_table.items()
                         if c.get("cable_type", "active-standby") == "active-standby"]
            if mux_ports:
                # trigger one-shot heartbeat suspend reset
                config_db.mod_entry("MUX_LINKMGR", "LINK_PROBER", {"reset_suspend_timer": ",".join(mux_ports)})
                # restore config db to the original
                config_db.set_entry("MUX_LINKMGR", "LINK_PROBER", mux_linkmgrd_table.get("LINK_PROBER", None))
    else:
        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, can't reset heartbeat suspend".format(port))
                sys.exit(CONFIG_FAIL)
        if asic_index in config_dbs:
            config_db = config_dbs[asic_index]
            mux_linkmgrd_table = mux_linkmgrd_tables[asic_index]
            mux_config_table = mux_config_tables[asic_index]
            if port not in mux_config_table:
                click.echo("Got invalid port {}, can't reset heartbeat suspend'".format(port))
                sys.exit(CONFIG_FAIL)
            elif mux_config_table[port].get("cable_type", "active-standby") != "active-standby":
                click.echo(
                    "Got invalid port {}, can't reset heartbeat suspend on active-active mux port".format(port)
                )
                sys.exit(CONFIG_FAIL)
            mux_ports.append(port)
            # trigger one-shot heartbeat suspend reset
            config_db.mod_entry("MUX_LINKMGR", "LINK_PROBER", {"reset_suspend_timer": port})
            # restore config db to the original
            config_db.set_entry("MUX_LINKMGR", "LINK_PROBER", mux_linkmgrd_table.get("LINK_PROBER", None))
        else:
            click.echo("Got invalid asic index for port {}, can't reset heartbeat suspend'".format(port))
            sys.exit(CONFIG_FAIL)

    if not mux_ports:
        click.echo("No mux ports found to reset heartbeat suspend")
        sys.exit(CONFIG_FAIL)

    mux_ports = natsorted(mux_ports)
    click.echo("Success in resetting heartbeat suspend for mux ports: {}".format(", ".join(mux_ports)))
