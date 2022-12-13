
import json
import sys
import time

import click
import re
import utilities_common.cli as clicommon
from natsort import natsorted
from collections import OrderedDict
from operator import itemgetter
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from swsscommon import swsscommon
from tabulate import tabulate
from utilities_common import platform_sfputil_helper
from utilities_common.general import get_optional_value_for_key_in_config_tbl 

platform_sfputil = None

REDIS_TIMEOUT_MSECS = 0
SELECT_TIMEOUT = 1000
HWMODE_MUXDIRECTION_TIMEOUT = 0.1

# The empty namespace refers to linux host namespace.
EMPTY_NAMESPACE = ''

CONFIG_SUCCESSFUL = 0
CONFIG_FAIL = 1
EXIT_FAIL = 1
EXIT_SUCCESS = 0
STATUS_FAIL = 1
STATUS_SUCCESSFUL = 0

VENDOR_NAME = "Credo"
VENDOR_MODEL_REGEX = re.compile(r"CAC\w{3}321P2P\w{2}MS")


def db_connect(db_name, namespace=EMPTY_NAMESPACE):
    return swsscommon.DBConnector(db_name, REDIS_TIMEOUT_MSECS, True, namespace)


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

target_dict = { "NIC":"0",
                "TORA":"1",
                "TORB":"2",
                "LOCAL":"3"}

def parse_target(target):
    return target_dict.get(target, None)

def check_port_in_mux_cable_table(port):

    per_npu_configdb = {}
    mux_tbl_cfg_db = {}
    port_mux_tbl_keys = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # TO-DO replace the macros with correct swsscommon names
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=False, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        mux_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("MUX_CABLE")
        port_mux_tbl_keys[asic_id] = mux_tbl_cfg_db[asic_id].keys()

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)

    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant retrieve mux cable table entries".format(port))
            return False

    if port in port_mux_tbl_keys[asic_index]:
        return True
    return False



def get_per_port_firmware(port):

    state_db = {}
    mux_info_dict = {}
    mux_info_full_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        state_db[asic_id].connect(state_db[asic_id].STATE_DB)

    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)

    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant retrieve mux cable table entries".format(port))
            return False


    mux_info_full_dict[asic_index] = state_db[asic_index].get_all(
        state_db[asic_index].STATE_DB, 'MUX_CABLE_INFO|{}'.format(port))

    res_dir = {}
    res_dir = mux_info_full_dict[asic_index]
    mux_info_dict["version_nic_active"] = res_dir.get("version_nic_active", None)
    mux_info_dict["version_nic_inactive"] = res_dir.get("version_nic_inactive", None)
    mux_info_dict["version_nic_next"] = res_dir.get("version_nic_next", None)
    mux_info_dict["version_peer_active"] = res_dir.get("version_peer_active", None)
    mux_info_dict["version_peer_inactive"] = res_dir.get("version_peer_inactive", None)
    mux_info_dict["version_peer_next"] = res_dir.get("version_peer_next", None)
    mux_info_dict["version_self_active"] = res_dir.get("version_self_active", None)
    mux_info_dict["version_self_inactive"] = res_dir.get("version_self_inactive", None)
    mux_info_dict["version_self_next"] = res_dir.get("version_self_next", None)

    return mux_info_dict

def get_response_for_version(port, mux_info_dict):
    state_db = {}
    xcvrd_show_fw_res_tbl = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        xcvrd_show_fw_res_tbl[asic_id] = swsscommon.Table(state_db[asic_id], "XCVRD_SHOW_FW_RES")

    logical_port_list = platform_sfputil_helper.get_logical_list()
    if port not in logical_port_list:
        click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
        rc = EXIT_FAIL
        res_dict[1] = rc
        return mux_info_dict

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
            rc = CONFIG_FAIL
            res_dict[1] = rc
            return mux_info_dict

    (status, fvp) = xcvrd_show_fw_res_tbl[asic_index].get(port)
    res_dir = dict(fvp)
    mux_info_dict["version_nic_active"] = res_dir.get("version_nic_active", None)
    mux_info_dict["version_nic_inactive"] = res_dir.get("version_nic_inactive", None)
    mux_info_dict["version_nic_next"] = res_dir.get("version_nic_next", None)
    mux_info_dict["version_peer_active"] = res_dir.get("version_peer_active", None)
    mux_info_dict["version_peer_inactive"] = res_dir.get("version_peer_inactive", None)
    mux_info_dict["version_peer_next"] = res_dir.get("version_peer_next", None)
    mux_info_dict["version_self_active"] = res_dir.get("version_self_active", None)
    mux_info_dict["version_self_inactive"] = res_dir.get("version_self_inactive", None)
    mux_info_dict["version_self_next"] = res_dir.get("version_self_next", None)

    return mux_info_dict

def get_event_logs(port, res_dict, mux_info_dict):
    state_db = {}
    xcvrd_show_fw_res_tbl = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        xcvrd_show_fw_res_tbl[asic_id] = swsscommon.Table(state_db[asic_id], "XCVRD_EVENT_LOG_RES")

    logical_port_list = platform_sfputil_helper.get_logical_list()
    if port not in logical_port_list:
        click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
        rc = EXIT_FAIL
        res_dict[1] = rc
        return mux_info_dict

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
            rc = CONFIG_FAIL
            res_dict[1] = rc
            return mux_info_dict

    (status, fvp) = xcvrd_show_fw_res_tbl[asic_index].get(port)
    res_dir = dict(fvp)

    for key, value in res_dir.items():
        mux_info_dict[key] = value;

    return mux_info_dict

def get_result(port, res_dict, cmd ,result, table_name):
    state_db = {}
    xcvrd_show_fw_res_tbl = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        xcvrd_show_fw_res_tbl[asic_id] = swsscommon.Table(state_db[asic_id], table_name)

    logical_port_list = platform_sfputil_helper.get_logical_list()
    if port not in logical_port_list:
        click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
        rc = EXIT_FAIL
        res_dict[1] = rc
        return result

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
            rc = CONFIG_FAIL
            res_dict[1] = rc
            return result

    (status, fvp) = xcvrd_show_fw_res_tbl[asic_index].get(port)
    res_dir = dict(fvp)

    return res_dir

def update_and_get_response_for_xcvr_cmd(cmd_name, rsp_name, exp_rsp, cmd_table_name, cmd_arg_table_name, rsp_table_name ,port, cmd_timeout_secs, param_dict= None, arg=None):

    res_dict = {}
    state_db, appl_db = {}, {}
    firmware_rsp_tbl, firmware_rsp_tbl_keys = {}, {}
    firmware_rsp_sub_tbl = {}
    firmware_cmd_tbl = {}
    firmware_cmd_arg_tbl = {}

    CMD_TIMEOUT_SECS = cmd_timeout_secs

    time_start = time.time()

    sel = swsscommon.Select()
    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        appl_db[asic_id] = db_connect("APPL_DB", namespace)
        firmware_cmd_tbl[asic_id] = swsscommon.Table(appl_db[asic_id], cmd_table_name)
        firmware_rsp_sub_tbl[asic_id] = swsscommon.SubscriberStateTable(state_db[asic_id], rsp_table_name)
        firmware_rsp_tbl[asic_id] = swsscommon.Table(state_db[asic_id], rsp_table_name)
        if cmd_arg_table_name is not None:
            firmware_cmd_arg_tbl[asic_id] = swsscommon.Table(appl_db[asic_id], cmd_arg_table_name)
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

                res_dict[1] = result
                res_dict[0] = 0
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


# 'muxcable' command ("show muxcable")
#


@click.group(name='muxcable', cls=clicommon.AliasedGroup)
def muxcable():
    """SONiC command line - 'show muxcable' command"""

    global platform_sfputil
    # Load platform-specific sfputil class
    platform_sfputil_helper.load_platform_sfputil()

    # Load port info
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()

    platform_sfputil = platform_sfputil_helper.platform_sfputil


def get_value_for_key_in_dict(mdict, port, key, table_name):
    value = mdict.get(key, None)
    if value is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table_name))
        sys.exit(STATUS_FAIL)

    return value


def get_value_for_key_in_config_tbl(config_db, port, key, table):
    info_dict = {}
    info_dict = config_db.get_entry(table, port)
    if info_dict is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table))
        sys.exit(STATUS_FAIL)

    value = get_value_for_key_in_dict(info_dict, port, key, table)

    return value


def get_switch_name(config_db):
    info_dict = {}
    info_dict = config_db.get_entry("DEVICE_METADATA", "localhost")
    #click.echo("{} ".format(info_dict))

    switch_name = get_value_for_key_in_dict(info_dict, "localhost", "peer_switch", "DEVICE_METADATA")
    if switch_name is not None:
        return switch_name
    else:
        click.echo("could not retreive switch name")
        sys.exit(STATUS_FAIL)


def create_json_dump_per_port_status(db, port_status_dict, muxcable_info_dict, muxcable_grpc_dict, muxcable_health_dict, muxcable_metrics_dict, asic_index, port):

    res_dict = {}
    status_value = get_value_for_key_in_dict(muxcable_info_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    port_name = platform_sfputil_helper.get_interface_alias(port, db)
    port_status_dict["MUX_CABLE"][port_name] = {}
    port_status_dict["MUX_CABLE"][port_name]["STATUS"] = status_value
    gRPC_value = get_value_for_key_in_dict(muxcable_grpc_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    port_status_dict["MUX_CABLE"][port_name]["SERVER_STATUS"] = gRPC_value
    health_value = get_value_for_key_in_dict(muxcable_health_dict[asic_index], port, "state", "MUX_LINKMGR_TABLE")
    port_status_dict["MUX_CABLE"][port_name]["HEALTH"] = health_value
    res_dict = get_hwmode_mux_direction_port(db, port)
    if res_dict[2] == "False":
        hwstatus = "absent"
    elif res_dict[1] == "not Y-Cable port":
        hwstatus = "not Y-Cable port"
    elif res_dict[1] == status_value:
        hwstatus = "consistent"
    else:
        hwstatus = "inconsistent"
    port_status_dict["MUX_CABLE"][port_name]["HWSTATUS"] = hwstatus

    last_switch_end_time = ""
    if "linkmgrd_switch_standby_end" in muxcable_metrics_dict[asic_index]:
        last_switch_end_time = muxcable_metrics_dict[asic_index].get("linkmgrd_switch_standby_end")
    elif "linkmgrd_switch_active_end" in muxcable_metrics_dict[asic_index]: 
        last_switch_end_time = muxcable_metrics_dict[asic_index].get("linkmgrd_switch_active_end")
    port_status_dict["MUX_CABLE"][port_name]["LAST_SWITCHOVER_TIME"] = last_switch_end_time

def create_table_dump_per_port_status(db, print_data, muxcable_info_dict, muxcable_grpc_dict, muxcable_health_dict, muxcable_metrics_dict, asic_index, port):

    print_port_data = []
    res_dict = {}

    res_dict = get_hwmode_mux_direction_port(db, port)
    status_value = get_value_for_key_in_dict(muxcable_info_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    #status_value = get_value_for_key_in_tbl(y_cable_asic_table, port, "status")
    gRPC_value = get_value_for_key_in_dict(muxcable_grpc_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    health_value = get_value_for_key_in_dict(muxcable_health_dict[asic_index], port, "state", "MUX_LINKMGR_TABLE")

    last_switch_end_time = ""
    if "linkmgrd_switch_standby_end" in muxcable_metrics_dict[asic_index]:
        last_switch_end_time = muxcable_metrics_dict[asic_index].get("linkmgrd_switch_standby_end")
    elif "linkmgrd_switch_active_end" in muxcable_metrics_dict[asic_index]: 
        last_switch_end_time = muxcable_metrics_dict[asic_index].get("linkmgrd_switch_active_end")

    port_name = platform_sfputil_helper.get_interface_alias(port, db)
    print_port_data.append(port_name)
    print_port_data.append(status_value)
    print_port_data.append(gRPC_value)
    print_port_data.append(health_value)
    if res_dict[2] == "False":
        hwstatus = "absent"
    elif res_dict[1] == "not Y-Cable port":
        hwstatus = "not Y-Cable port"
    elif res_dict[1] == status_value:
        hwstatus = "consistent"
    else:
        hwstatus = "inconsistent"
    print_port_data.append(hwstatus)
    print_port_data.append(last_switch_end_time)
    print_data.append(print_port_data)


def create_table_dump_per_port_config(db ,print_data, per_npu_configdb, asic_id, port, is_dualtor_active_active):

    port_list = []
    port_name = platform_sfputil_helper.get_interface_alias(port, db)
    port_list.append(port_name)
    state_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "state", "MUX_CABLE")
    port_list.append(state_value)
    ipv4_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv4", "MUX_CABLE")
    port_list.append(ipv4_value)
    ipv6_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv6", "MUX_CABLE")
    port_list.append(ipv6_value)
    cable_type = get_optional_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "cable_type", "MUX_CABLE")
    if cable_type is not None:
        port_list.append(cable_type)
    soc_ipv4_value = get_optional_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "soc_ipv4", "MUX_CABLE")
    if soc_ipv4_value is not None:
        port_list.append(soc_ipv4_value)
        is_dualtor_active_active[0] = True
    print_data.append(port_list)


def create_json_dump_per_port_config(db, port_status_dict, per_npu_configdb, asic_id, port):

    state_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "state", "MUX_CABLE")
    port_name = platform_sfputil_helper.get_interface_alias(port, db)
    port_status_dict["MUX_CABLE"]["PORTS"][port_name] = {"STATE": state_value}
    port_status_dict["MUX_CABLE"]["PORTS"][port_name]["SERVER"] = {}
    ipv4_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv4", "MUX_CABLE")
    port_status_dict["MUX_CABLE"]["PORTS"][port_name]["SERVER"]["IPv4"] = ipv4_value
    ipv6_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv6", "MUX_CABLE")
    port_status_dict["MUX_CABLE"]["PORTS"][port_name]["SERVER"]["IPv6"] = ipv6_value
    cable_type = get_optional_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "cable_type", "MUX_CABLE")
    if cable_type is not None:
        port_status_dict["MUX_CABLE"]["PORTS"][port_name]["SERVER"]["cable_type"] = cable_type
    soc_ipv4_value = get_optional_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "soc_ipv4", "MUX_CABLE")
    if soc_ipv4_value is not None:
        port_status_dict["MUX_CABLE"]["PORTS"][port_name]["SERVER"]["soc_ipv4"] = soc_ipv4_value

def get_tunnel_route_per_port(db, port_tunnel_route, per_npu_configdb, per_npu_appl_db, asic_id, port):

    mux_cfg_dict = per_npu_configdb[asic_id].get_all(
    per_npu_configdb[asic_id].CONFIG_DB, 'MUX_CABLE|{}'.format(port))
    dest_names = ["server_ipv4", "server_ipv6", "soc_ipv4"]

    for name in dest_names:
        dest_address = mux_cfg_dict.get(name, None)

        if dest_address is not None:
            kernel_route_keys = per_npu_appl_db[asic_id].keys(
                per_npu_appl_db[asic_id].APPL_DB, 'TUNNEL_ROUTE_TABLE:*{}'.format(dest_address))
            if_kernel_tunnel_route_programed = kernel_route_keys is not None and len(kernel_route_keys)

            asic_route_keys = per_npu_asic_db[asic_id].keys(
                per_npu_asic_db[asic_id].ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:*{}*'.format(dest_address))
            if_asic_tunnel_route_programed = asic_route_keys is not None and len(asic_route_keys)

            if if_kernel_tunnel_route_programed or if_asic_tunnel_route_programed:
                port_tunnel_route["TUNNEL_ROUTE"][port] = port_tunnel_route["TUNNEL_ROUTE"].get(port, {})
                port_tunnel_route["TUNNEL_ROUTE"][port][name] = {}
                port_tunnel_route["TUNNEL_ROUTE"][port][name]['DEST'] = dest_address

                port_tunnel_route["TUNNEL_ROUTE"][port][name]['kernel'] = if_kernel_tunnel_route_programed
                port_tunnel_route["TUNNEL_ROUTE"][port][name]['asic'] = if_asic_tunnel_route_programed

def create_json_dump_per_port_tunnel_route(db, port_tunnel_route, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_id, port):

    get_tunnel_route_per_port(db, port_tunnel_route, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_id, port)

def create_table_dump_per_port_tunnel_route(db, print_data, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_id, port):

    port_tunnel_route = {}
    port_tunnel_route["TUNNEL_ROUTE"] = {}
    get_tunnel_route_per_port(db, port_tunnel_route, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_id, port)

    for port, route in port_tunnel_route["TUNNEL_ROUTE"].items():
        for dest_name, values in route.items():
            print_line = []
            print_line.append(port)
            print_line.append(dest_name)
            print_line.append(values['DEST'])
            print_line.append('added' if values['asic'] else '-')
            print_line.append('added' if values['kernel'] else '-')
            print_data.append(print_line)

@muxcable.command()
@click.argument('port', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def status(db, port, json_output):
    """Show muxcable status information"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    port_table_keys = {}
    appl_db_muxcable_tbl_keys = {}
    port_health_table_keys = {}
    port_metrics_table_keys = {}
    per_npu_statedb = {}
    per_npu_appl_db = {}
    muxcable_info_dict = {}
    muxcable_grpc_dict = {}
    muxcable_health_dict = {}
    muxcable_metrics_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        per_npu_appl_db[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_appl_db[asic_id].connect(per_npu_appl_db[asic_id].APPL_DB)

        appl_db_muxcable_tbl_keys[asic_id] = per_npu_appl_db[asic_id].keys(
            per_npu_appl_db[asic_id].APPL_DB, 'MUX_CABLE_TABLE:*')
        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')
        port_health_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_LINKMGR_TABLE|*')
        port_metrics_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_METRICS_TABLE|*')

    if port is not None:
        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                port_name = platform_sfputil_helper.get_interface_alias(port, db)
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port_name))
                sys.exit(STATUS_FAIL)

        muxcable_info_dict[asic_index] = per_npu_appl_db[asic_index].get_all(
            per_npu_appl_db[asic_index].APPL_DB, 'MUX_CABLE_TABLE:{}'.format(port))
        muxcable_grpc_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
        muxcable_health_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_LINKMGR_TABLE|{}'.format(port))
        muxcable_metrics_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_METRICS_TABLE|{}'.format(port))

        if muxcable_info_dict[asic_index] is not None:
            logical_key = "MUX_CABLE_TABLE:{}".format(port)
            logical_health_key = "MUX_LINKMGR_TABLE|{}".format(port)
            logical_metrics_key = "MUX_METRICS_TABLE|{}".format(port)
            if logical_key in appl_db_muxcable_tbl_keys[asic_index] and logical_health_key in port_health_table_keys[asic_index]:
                
                if logical_metrics_key not in port_metrics_table_keys[asic_index]: 
                    muxcable_metrics_dict[asic_index] = {}

                if json_output:
                    port_status_dict = {}
                    port_status_dict["MUX_CABLE"] = {}

                    create_json_dump_per_port_status(db, port_status_dict, muxcable_info_dict, muxcable_grpc_dict,
                                                     muxcable_health_dict, muxcable_metrics_dict, asic_index, port)

                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                    sys.exit(STATUS_SUCCESSFUL)
                else:
                    print_data = []

                    create_table_dump_per_port_status(db, print_data, muxcable_info_dict, muxcable_grpc_dict,
                                                      muxcable_health_dict, muxcable_metrics_dict, asic_index, port)

                    headers = ['PORT', 'STATUS', 'SERVER_STATUS', 'HEALTH', 'HWSTATUS', 'LAST_SWITCHOVER_TIME']

                    click.echo(tabulate(print_data, headers=headers))
                    sys.exit(STATUS_SUCCESSFUL)
            else:
                port_name = platform_sfputil_helper.get_interface_alias(port, db)
                click.echo("this is not a valid port present on mux_cable".format(port_name))
                sys.exit(STATUS_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(STATUS_FAIL)

    else:

        if json_output:
            port_status_dict = {}
            port_status_dict["MUX_CABLE"] = {}
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in natsorted(appl_db_muxcable_tbl_keys[asic_id]):
                    port = key.split(":")[1]
                    muxcable_info_dict[asic_id] = per_npu_appl_db[asic_id].get_all(
                        per_npu_appl_db[asic_id].APPL_DB, 'MUX_CABLE_TABLE:{}'.format(port))
                    muxcable_grpc_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
                    muxcable_health_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_LINKMGR_TABLE|{}'.format(port))
                    muxcable_metrics_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_METRICS_TABLE|{}'.format(port))
                    if not muxcable_metrics_dict[asic_id]: 
                        muxcable_metrics_dict[asic_id] = {}
                    create_json_dump_per_port_status(db, port_status_dict, muxcable_info_dict, muxcable_grpc_dict,
                                                     muxcable_health_dict, muxcable_metrics_dict, asic_id, port)

            click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
        else:
            print_data = []
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in natsorted(appl_db_muxcable_tbl_keys[asic_id]):
                    port = key.split(":")[1]
                    muxcable_info_dict[asic_id] = per_npu_appl_db[asic_id].get_all(
                        per_npu_appl_db[asic_id].APPL_DB, 'MUX_CABLE_TABLE:{}'.format(port))
                    muxcable_health_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_LINKMGR_TABLE|{}'.format(port))
                    muxcable_grpc_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
                    muxcable_metrics_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_METRICS_TABLE|{}'.format(port))
                    if not muxcable_metrics_dict[asic_id]: 
                        muxcable_metrics_dict[asic_id] = {}
                    create_table_dump_per_port_status(db, print_data, muxcable_info_dict, muxcable_grpc_dict,
                                                      muxcable_health_dict, muxcable_metrics_dict, asic_id, port)

            headers = ['PORT', 'STATUS', 'SERVER_STATUS', 'HEALTH', 'HWSTATUS', 'LAST_SWITCHOVER_TIME']
            click.echo(tabulate(print_data, headers=headers))

        sys.exit(STATUS_SUCCESSFUL)


@muxcable.command()
@click.argument('port', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def config(db, port, json_output):
    """Show muxcable config information"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    port_mux_tbl_keys = {}
    asic_start_idx = None
    per_npu_configdb = {}
    mux_tbl_cfg_db = {}
    peer_switch_tbl_cfg_db = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        if asic_start_idx is None:
            asic_start_idx = asic_id
        # TO-DO replace the macros with correct swsscommon names
        #config_db[asic_id] = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MSECS, True, namespace)
        #mux_tbl_cfg_db[asic_id] = swsscommon.Table(config_db[asic_id], swsscommon.CFG_MUX_CABLE_TABLE_NAME)
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=False, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        mux_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("MUX_CABLE")
        peer_switch_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("PEER_SWITCH")
        #peer_switch_tbl_cfg_db[asic_id] = swsscommon.Table(config_db[asic_id], swsscommon.CFG_PEER_SWITCH_TABLE_NAME)
        port_mux_tbl_keys[asic_id] = mux_tbl_cfg_db[asic_id].keys()

    if port is not None:
        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                port_name = platform_sfputil_helper.get_interface_alias(port, db)
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port_name))
                sys.exit(CONFIG_FAIL)

        port_status_dict = {}
        port_status_dict["MUX_CABLE"] = {}
        port_status_dict["MUX_CABLE"]["PEER_TOR"] = {}
        peer_switch_value = None

        switch_name = get_switch_name(per_npu_configdb[asic_start_idx])
        if asic_start_idx is not None:
            peer_switch_value = get_value_for_key_in_config_tbl(
                per_npu_configdb[asic_start_idx], switch_name, "address_ipv4", "PEER_SWITCH")
            port_status_dict["MUX_CABLE"]["PEER_TOR"] = peer_switch_value
        if port_mux_tbl_keys[asic_id] is not None:
            if port in port_mux_tbl_keys[asic_id]:

                if json_output:

                    port_status_dict["MUX_CABLE"] = {}
                    port_status_dict["MUX_CABLE"]["PORTS"] = {}
                    create_json_dump_per_port_config(db, port_status_dict, per_npu_configdb, asic_id, port)

                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                    sys.exit(CONFIG_SUCCESSFUL)
                else:
                    print_data = []
                    print_peer_tor = []
                    is_dualtor_active_active = [False]


                    create_table_dump_per_port_config(db, print_data, per_npu_configdb, asic_id, port, is_dualtor_active_active)

                    headers = ['SWITCH_NAME', 'PEER_TOR']
                    peer_tor_data = []
                    peer_tor_data.append(switch_name)
                    peer_tor_data.append(peer_switch_value)
                    print_peer_tor.append(peer_tor_data)
                    click.echo(tabulate(print_peer_tor, headers=headers))
                    if is_dualtor_active_active[0]:
                        headers = ['port', 'state', 'ipv4', 'ipv6', 'cable_type', 'soc_ipv4']
                    else:
                        headers = ['port', 'state', 'ipv4', 'ipv6']
                    click.echo(tabulate(print_data, headers=headers))

                    sys.exit(CONFIG_SUCCESSFUL)

            else:
                port_name = platform_sfputil_helper.get_interface_alias(port, db)
                click.echo("this is not a valid port present on mux_cable".format(port_name))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    else:

        port_status_dict = {}
        port_status_dict["MUX_CABLE"] = {}
        port_status_dict["MUX_CABLE"]["PEER_TOR"] = {}
        peer_switch_value = None

        switch_name = get_switch_name(per_npu_configdb[asic_start_idx])
        if asic_start_idx is not None:
            peer_switch_value = get_value_for_key_in_config_tbl(
                per_npu_configdb[asic_start_idx], switch_name, "address_ipv4", "PEER_SWITCH")
            port_status_dict["MUX_CABLE"]["PEER_TOR"] = peer_switch_value
        if json_output:
            port_status_dict["MUX_CABLE"]["PORTS"] = {}
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for port in natsorted(port_mux_tbl_keys[asic_id]):
                    create_json_dump_per_port_config(db, port_status_dict, per_npu_configdb, asic_id, port)

            click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
        else:
            print_data = []
            print_peer_tor = []
            is_dualtor_active_active = [False]

            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for port in natsorted(port_mux_tbl_keys[asic_id]):
                    create_table_dump_per_port_config(db, print_data, per_npu_configdb, asic_id, port, is_dualtor_active_active)

            headers = ['SWITCH_NAME', 'PEER_TOR']
            peer_tor_data = []
            peer_tor_data.append(switch_name)
            peer_tor_data.append(peer_switch_value)
            print_peer_tor.append(peer_tor_data)
            click.echo(tabulate(print_peer_tor, headers=headers))
            if is_dualtor_active_active[0]:
                headers = ['port', 'state', 'ipv4', 'ipv6', 'cable_type', 'soc_ipv4']
            else:
                headers = ['port', 'state', 'ipv4', 'ipv6']
            click.echo(tabulate(print_data, headers=headers))

        sys.exit(CONFIG_SUCCESSFUL)


@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def berinfo(db, port, target, json_output):
    """Show muxcable BER (bit error rate) information"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

    if port is not None:

        res_dict = {}
        result = {}
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target


        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_ber", "status", "True", "XCVRD_GET_BER_CMD", "XCVRD_GET_BER_CMD_ARG", "XCVRD_GET_BER_RSP", port, 10, param_dict, "ber")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_BER_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))

    else:
        click.echo("Did not get a valid Port for ber value".format(port))
        sys.exit(CONFIG_FAIL)


@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def eyeinfo(db, port, target, json_output):
    """Show muxcable eye information in mv"""

    port = platform_sfputil_helper.get_interface_alias(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

    if port is not None:

        res_dict = {}
        result = {}
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target


        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_ber", "status", "True", "XCVRD_GET_BER_CMD", "XCVRD_GET_BER_CMD_ARG", "XCVRD_GET_BER_RSP", port, 10, param_dict, "eye")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_BER_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")
        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))

    else:
        click.echo("Did not get a valid Port for ber value".format(port))
        sys.exit(CONFIG_FAIL)


@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def fecstatistics(db, port, target, json_output):
    """Show muxcable fec layer statistics information, target NIC TORA TORB"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

    if port is not None:

        res_dict = {}
        result = {}
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target


        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_ber", "status", "True", "XCVRD_GET_BER_CMD", "XCVRD_GET_BER_CMD_ARG", "XCVRD_GET_BER_RSP", port, 10, param_dict, "fec_stats")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_BER_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")
        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))

    else:
        click.echo("Did not get a valid Port for ber value".format(port))
        sys.exit(CONFIG_FAIL)


@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('target', metavar='<target> NIC TORA TORB LOCAL', required=True, default=None, type=click.Choice(["NIC", "TORA", "TORB", "LOCAL"]))
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def pcsstatistics(db, port, target, json_output):
    """Show muxcable pcs layer statistics information"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

    if port is not None:

        res_dict = {}
        result = {}
        param_dict = {}
        target = parse_target(target)
        param_dict["target"] = target


        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_ber", "status", "True", "XCVRD_GET_BER_CMD", "XCVRD_GET_BER_CMD_ARG", "XCVRD_GET_BER_RSP", port, 10, param_dict, "pcs_stats")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_BER_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")
        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))

    else:
        click.echo("Did not get a valid Port for pcs statistics".format(port))
        sys.exit(CONFIG_FAIL)

@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('option', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def debugdumpregisters(db, port, option, json_output):
    """Show muxcable debug deump registers information, preagreed by vendors"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

    if port is not None:

        res_dict = {}
        result = {}
        param_dict = {}
        param_dict["option"] = option


        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_ber", "status", "True", "XCVRD_GET_BER_CMD", "XCVRD_GET_BER_CMD_ARG", "XCVRD_GET_BER_RSP", port, 100, param_dict, "debug_dump")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_BER_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD_ARG")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")
        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))
    else:
        click.echo("Did not get a valid Port for debug dump registers".format(port))
        sys.exit(CONFIG_FAIL)

@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def alivecablestatus(db, port, json_output):
    """Show muxcable alive information """

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

    if port is not None:

        res_dict = {}
        result = {}


        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_ber", "status", "True", "XCVRD_GET_BER_CMD", None, "XCVRD_GET_BER_RSP", port, 10, None, "cable_alive")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_BER_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_BER_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_BER_RES")

        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))
    else:
        click.echo("Did not get a valid Port for cable alive status".format(port))
        sys.exit(CONFIG_FAIL)

@muxcable.command()
@click.argument('port', required=True, default=None)
@clicommon.pass_db
def cableinfo(db, port):
    """Show muxcable cable information"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    if platform_sfputil is not None:
        physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

    if not isinstance(physical_port_list, list):
        click.echo("ERR: Unable to get a port on muxcable port")
        sys.exit(EXIT_FAIL)
        if len(physical_port_list) != 1:
            click.echo("ERR: Unable to get a single port on muxcable")
            sys.exit(EXIT_FAIL)

    physical_port = physical_port_list[0]
    import sonic_y_cable.y_cable
    part_num = sonic_y_cable.y_cable.get_part_number(physical_port)
    if part_num == False or part_num == -1:
        click.echo("ERR: Unable to get cable info part number")
        sys.exit(EXIT_FAIL)
    vendor = sonic_y_cable.y_cable.get_vendor(physical_port)
    if vendor == False or vendor == -1:
        click.echo("ERR: Unable to get cable info vendor name")
        sys.exit(EXIT_FAIL)
    headers = ['Vendor', 'Model']

    body = [[vendor, part_num]]
    click.echo(tabulate(body, headers=headers))



def get_hwmode_mux_direction_port(db, port):


    delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_DIR_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RES")

    res_dict = {}
    res_dict[0] = CONFIG_FAIL
    res_dict[1] = "unknown"
    res_dict[2] = "unknown"
    result = {}
    if port is not None:

        res_dict = update_and_get_response_for_xcvr_cmd(
            "state", "state", "True", "XCVRD_SHOW_HWMODE_DIR_CMD", "XCVRD_SHOW_HWMODE_DIR_RES", "XCVRD_SHOW_HWMODE_DIR_RSP", port, HWMODE_MUXDIRECTION_TIMEOUT, None, "probe")

        result = get_result(port, res_dict, "muxdirection" , result, "XCVRD_SHOW_HWMODE_DIR_RES")

        res_dict[2] = result.get("presence","unknown")

    return res_dict


@muxcable.group(cls=clicommon.AbbreviationGroup)
def hwmode():
    """Shows the muxcable hardware information directly"""
    pass


@hwmode.command()
@click.argument('port', metavar='<port_name>', required=False, default=None)
@clicommon.pass_db
def muxdirection(db, port):
    """Shows the current direction of the muxcable {active/standy}"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_DIR_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RES")

    if port is not None:

        if check_port_in_mux_cable_table(port) == False:
            click.echo("Not Y-cable port")
            return CONFIG_FAIL

        res_dict = get_hwmode_mux_direction_port(db, port)

        body = []
        temp_list = []
        headers = ['Port', 'Direction', 'Presence']
        port = platform_sfputil_helper.get_interface_alias(port, db)
        temp_list.append(port)
        temp_list.append(res_dict[1])
        temp_list.append(res_dict[2])
        body.append(temp_list)

        rc = res_dict[0]
        click.echo(tabulate(body, headers=headers))

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_DIR_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RES")

        return rc

    else:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True
        body = []

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            if not check_port_in_mux_cable_table(port):
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

            temp_list = []

            res_dict = get_hwmode_mux_direction_port(db, port)

            port = platform_sfputil_helper.get_interface_alias(port, db)
            temp_list.append(port)
            temp_list.append(res_dict[1])
            temp_list.append(res_dict[2])
            body.append(temp_list)
            rc = res_dict[0]
            if rc != 0:
                rc_exit = False

        headers = ['Port', 'Direction', 'Presence']

        click.echo(tabulate(body, headers=headers))

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_DIR_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_DIR_RES")
        if rc_exit == False:
            sys.exit(EXIT_FAIL)


@hwmode.command()
@click.argument('port', metavar='<port_name>', required=False, default=None)
@clicommon.pass_db
def switchmode(db, port):
    """Shows the current switching mode of the muxcable {auto/manual}"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_SWMODE_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_SWMODE_RSP")

    if port is not None:

        if check_port_in_mux_cable_table(port) == False:
            click.echo("Not Y-cable port")
            return CONFIG_FAIL

        res_dict = {}
        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd(
            "state", "state", "True", "XCVRD_SHOW_HWMODE_SWMODE_CMD", None, "XCVRD_SHOW_HWMODE_SWMODE_RSP", port, 1, None, "probe")

        body = []
        temp_list = []
        headers = ['Port', 'Switching']
        port = platform_sfputil_helper.get_interface_alias(port, db)
        temp_list.append(port)
        temp_list.append(res_dict[1])
        body.append(temp_list)

        rc = res_dict[0]
        click.echo(tabulate(body, headers=headers))

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_SWMODE_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_SWMODE_RSP")

        return rc

    else:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True
        body = []

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            if not check_port_in_mux_cable_table(port):
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

            temp_list = []
            res_dict = {}
            res_dict[0] = CONFIG_FAIL
            res_dict[1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd(
                "state", "state", "True", "XCVRD_SHOW_HWMODE_SWMODE_CMD", None, "XCVRD_SHOW_HWMODE_SWMODE_RSP", port, 1, None, "probe")
            port = platform_sfputil_helper.get_interface_alias(port, db)
            temp_list.append(port)
            temp_list.append(res_dict[1])
            rc = res_dict[1]
            if rc != 0:
                rc_exit = False
            body.append(temp_list)

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_HWMODE_SWMODE_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_HWMODE_SWMODE_RSP")

        headers = ['Port', 'Switching']

        click.echo(tabulate(body, headers=headers))
        if rc_exit == False:
            sys.exit(EXIT_FAIL)



def get_single_port_firmware_version(port, res_dict, mux_info_dict):

    state_db, appl_db = {}, {}
    xcvrd_show_fw_rsp_sts_tbl_keys = {}
    xcvrd_show_fw_rsp_sts_tbl = {}
    xcvrd_show_fw_rsp_tbl = {}
    xcvrd_show_fw_cmd_tbl, xcvrd_show_fw_res_tbl = {}, {}

    sel = swsscommon.Select()
    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        appl_db[asic_id] = db_connect("APPL_DB", namespace)
        xcvrd_show_fw_cmd_tbl[asic_id] = swsscommon.Table(appl_db[asic_id], "XCVRD_SHOW_FW_CMD")
        xcvrd_show_fw_rsp_tbl[asic_id] = swsscommon.SubscriberStateTable(state_db[asic_id], "XCVRD_SHOW_FW_RSP")
        xcvrd_show_fw_rsp_sts_tbl[asic_id] = swsscommon.Table(state_db[asic_id], "XCVRD_SHOW_FW_RSP")
        xcvrd_show_fw_res_tbl[asic_id] = swsscommon.Table(state_db[asic_id], "XCVRD_SHOW_FW_RES")
        xcvrd_show_fw_rsp_sts_tbl_keys[asic_id] = xcvrd_show_fw_rsp_sts_tbl[asic_id].getKeys()
        for key in xcvrd_show_fw_rsp_sts_tbl_keys[asic_id]:
            xcvrd_show_fw_rsp_sts_tbl[asic_id]._del(key)
        sel.addSelectable(xcvrd_show_fw_rsp_tbl[asic_id])

    rc = 0
    res_dict[0] = 'unknown'

    logical_port_list = platform_sfputil_helper.get_logical_list()
    if port not in logical_port_list:
        click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
        rc = EXIT_FAIL
        res_dict[1] = rc
        return

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
            rc = CONFIG_FAIL
            res_dict[1] = rc
            return

    fvs = swsscommon.FieldValuePairs([('firmware_version', 'probe')])
    xcvrd_show_fw_cmd_tbl[asic_index].set(port, fvs)

    # Listen indefinitely for changes to the HW_MUX_CABLE_TABLE in the Application DB's
    while True:
        # Use timeout to prevent ignoring the signals we want to handle
        # in signal_handler() (e.g. SIGTERM for graceful shutdown)

        (state, selectableObj) = sel.select(SELECT_TIMEOUT)

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

        (port_m, op_m, fvp_m) = xcvrd_show_fw_rsp_tbl[asic_index].pop()

        if not port_m:
            click.echo("Did not receive a port response {}".format(port))
            res_dict[0] = 'False'
            res_dict[1] = EXIT_FAIL
            xcvrd_show_fw_rsp_sts_tbl[asic_index]._del(port)
            break

        if port_m != port:

            res_dict[0] = 'False'
            res_dict[1] = EXIT_FAIL
            xcvrd_show_fw_rsp_sts_tbl[asic_index]._del(port)
            continue

        if fvp_m:

            fvp_dict = dict(fvp_m)
            if "status" in fvp_dict:
                # check if xcvrd got a probe command
                state = fvp_dict["status"]

                res_dict[0] = state
                res_dict[1] = EXIT_FAIL
                xcvrd_show_fw_rsp_sts_tbl[asic_index]._del(port)
                (status, fvp) = xcvrd_show_fw_res_tbl[asic_index].get(port)
                res_dir = dict(fvp)
                mux_info_dict["version_nic_active"] = res_dir.get("version_nic_active", None)
                mux_info_dict["version_nic_inactive"] = res_dir.get("version_nic_inactive", None)
                mux_info_dict["version_nic_next"] = res_dir.get("version_nic_next", None)
                mux_info_dict["version_peer_active"] = res_dir.get("version_peer_active", None)
                mux_info_dict["version_peer_inactive"] = res_dir.get("version_peer_inactive", None)
                mux_info_dict["version_peer_next"] = res_dir.get("version_peer_next", None)
                mux_info_dict["version_self_active"] = res_dir.get("version_self_active", None)
                mux_info_dict["version_self_inactive"] = res_dir.get("version_self_inactive", None)
                mux_info_dict["version_self_next"] = res_dir.get("version_self_next", None)
                break
            else:
                res_dict[0] = 'False'
                res_dict[1] = EXIT_FAIL
                xcvrd_show_fw_rsp_sts_tbl[asic_index]._del(port)
                break
        else:
            res_dict[0] = 'False'
            res_dict[1] = EXIT_FAIL
            xcvrd_show_fw_rsp_sts_tbl[asic_index]._del(port)
            break


    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_FW_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_FW_RES")

    return


@muxcable.group(cls=clicommon.AbbreviationGroup)
def firmware():
    """Show muxcable firmware command"""
    pass


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--active', 'active', required=False, is_flag=True, type=click.BOOL, help="display the firmware version of only active bank within MCU's")
@clicommon.pass_db
def version(db, port, active):
    """Show muxcable firmware version"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_SHOW_FW_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_FW_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_FW_RES")

    if port is not None and port != "all":

        res_dict = {}
        mux_info_dict, mux_info_active_dict = {}, {}

        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"
        mux_info_dict["version_nic_active"] = "N/A"
        mux_info_dict["version_nic_inactive"] = "N/A"
        mux_info_dict["version_nic_next"] = "N/A"
        mux_info_dict["version_peer_active"] = "N/A"
        mux_info_dict["version_peer_inactive"] = "N/A"
        mux_info_dict["version_peer_next"] = "N/A"
        mux_info_dict["version_self_active"] = "N/A"
        mux_info_dict["version_self_inactive"] = "N/A"
        mux_info_dict["version_self_next"] = "N/A"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "firmware_version", "status", "True", "XCVRD_SHOW_FW_CMD", None, "XCVRD_SHOW_FW_RSP", port, 20, None, "probe")

        if res_dict[1] == "True":
            mux_info_dict = get_response_for_version(port, mux_info_dict)

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_FW_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_SHOW_FW_RES")

        if active is True:
            for key in mux_info_dict:
                if key.endswith("_active"):
                    mux_info_active_dict[key] = mux_info_dict[key]
            click.echo("{}".format(json.dumps(mux_info_active_dict, indent=4)))
        else:
            click.echo("{}".format(json.dumps(mux_info_dict, indent=4)))

    elif port == "all" and port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            if not check_port_in_mux_cable_table(port):
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


            port = platform_sfputil_helper.get_interface_alias(port, db)
            
            mux_info_dict = get_per_port_firmware(port)
            if not isinstance(mux_info_dict, dict):
                mux_info_dict = {}
                rc_exit = False
             
            mux_info = {}
            mux_info_active_dict = {}
            if active is True:
                for key in mux_info_dict:
                    if key.endswith("_active"):
                        mux_info_active_dict[key] = mux_info_dict[key]
                mux_info[port] = mux_info_active_dict
                click.echo("{}".format(json.dumps(mux_info, indent=4)))
            else:
                mux_info[port] = mux_info_dict
                click.echo("{}".format(json.dumps(mux_info, indent=4)))
            
            if rc_exit == False:
                sys.exit(EXIT_FAIL)

        sys.exit(CONFIG_SUCCESSFUL)

    else:
        port_name = platform_sfputil_helper.get_interface_name(port, db)
        click.echo("Did not get a valid Port for mux firmware version".format(port_name))
        sys.exit(CONFIG_FAIL)


@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def metrics(db, port, json_output):
    """Show muxcable metrics <port>"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    metrics_table_keys = {}
    per_npu_statedb = {}
    metrics_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_statedb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        metrics_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_METRICS_TABLE|*')

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        if port not in logical_port_list:
            port_name = platform_sfputil_helper.get_interface_alias(port, db)
            click.echo(("ERR: Not a valid logical port for muxcable firmware {}".format(port_name)))
            sys.exit(CONFIG_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
            if asic_index is None:
                # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
                # is fully mocked
                import sonic_platform_base.sonic_sfp.sfputilhelper
                asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
                if asic_index is None:
                    port_name = platform_sfputil_helper.get_interface_alias(port, db)
                    click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port_name))

        metrics_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_METRICS_TABLE|{}'.format(port))

        ordered_dict = OrderedDict(sorted(metrics_dict[asic_index].items(), key=itemgetter(1)))
        if json_output:
            click.echo("{}".format(json.dumps(ordered_dict, indent=4)))
        else:
            print_data = []
            for key, val in ordered_dict.items():
                print_port_data = []
                port = platform_sfputil_helper.get_interface_alias(port, db)
                print_port_data.append(port)
                print_port_data.append(key)
                print_port_data.append(val)
                print_data.append(print_port_data)

            headers = ['PORT', 'EVENT', 'TIME']

            click.echo(tabulate(print_data, headers=headers))

@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def event_log(db, port, json_output):
    """Show muxcable event log <port>"""

    click.confirm(('Muxcable at port {} will retreive cable logs from MCU, Caution: approx wait time could be ~2 minutes Continue?'.format(port)), abort=True)
    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_EVENT_LOG_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_EVENT_LOG_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_EVENT_LOG_RES")

    if port is not None:

        res_dict = {}
        result = {}
        mux_info_dict = {}

        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "show_event", "status", "True", "XCVRD_EVENT_LOG_CMD", None, "XCVRD_EVENT_LOG_RSP", port, 1000, None, "probe")

        if res_dict[1] == "True":
            result = get_event_logs(port, res_dict, mux_info_dict)


        delete_all_keys_in_db_table("STATE_DB", "XCVRD_EVENT_LOG_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_EVENT_LOG_RES")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_EVENT_LOG_CMD")
        port = platform_sfputil_helper.get_interface_alias(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))
    else:
        click.echo("Did not get a valid Port for event log".format(port))
        sys.exit(CONFIG_FAIL)

@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def get_fec_anlt_speed(db, port, json_output):
    """Show muxcable configurations for fec anlt speed <port>"""

    port = platform_sfputil_helper.get_interface_name(port, db)
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_FEC_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_FEC_RSP")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_FEC_RES")

    if port is not None:

        res_dict = {}
        result = {}

        res_dict[0] = CONFIG_FAIL
        res_dict[1] = "unknown"

        res_dict = update_and_get_response_for_xcvr_cmd(
            "get_fec", "status", "True", "XCVRD_GET_FEC_CMD", None, "XCVRD_GET_FEC_RSP", port, 10, None, "probe")

        if res_dict[1] == "True":
            result = get_result(port, res_dict, "fec" , result, "XCVRD_GET_FEC_RES")


        delete_all_keys_in_db_table("APPL_DB", "XCVRD_GET_FEC_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_FEC_RSP")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_GET_FEC_RES")
        port = platform_sfputil_helper.get_interface_name(port, db)

        if json_output:
            click.echo("{}".format(json.dumps(result, indent=4)))
        else:
            headers = ['PORT', 'ATTR', 'VALUE']
            res = [[port]+[key] + [val] for key, val in result.items()]
            click.echo(tabulate(res, headers=headers))
    else:
        click.echo("Did not get a valid Port for fec value speed anlt".format(port))
        sys.exit(CONFIG_FAIL)

@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def packetloss(db, port, json_output):
    """show muxcable packetloss <port>"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    pckloss_table_keys = {}
    per_npu_statedb = {}
    pckloss_dict = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)

        per_npu_statedb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        pckloss_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'LINK_PROBE_STATS|*')

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        if port not in logical_port_list:
            port_name = platform_sfputil_helper.get_interface_alias(port, db)
            click.echo(("ERR: Not a valid logical port for muxcable firmware {}".format(port_name)))
            sys.exit(CONFIG_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
            if asic_index is None:
                # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
                # is fully mocked
                import sonic_platform_base.sonic_sfp.sfputilhelper
                asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
                if asic_index is None:
                    port_name = platform_sfputil_helper.get_interface_alias(port, db)
                    click.echo("Got invalid asic index for port {}, cant retreive pck loss info".format(port_name))

        pckloss_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'LINK_PROBE_STATS|{}'.format(port))

        ordered_dict = OrderedDict(sorted(pckloss_dict[asic_index].items(), key=itemgetter(1)))
        if json_output:
            click.echo("{}".format(json.dumps(ordered_dict, indent=4)))
        else:
            print_count = []
            print_event = []
            for key, val in ordered_dict.items():
                print_port_data = []
                port = platform_sfputil_helper.get_interface_alias(port, db)
                print_port_data.append(port)
                print_port_data.append(key)
                print_port_data.append(val)
                if "count" in key: 
                    print_count.append(print_port_data)
                else:
                    print_event.append(print_port_data)

            count_headers = ['PORT', 'COUNT', 'VALUE']
            event_headers = ['PORT', 'EVENT', 'TIME']

            click.echo(tabulate(print_count, headers=count_headers))
            click.echo(tabulate(print_event, headers=event_headers))

@muxcable.command()
@click.argument('port', metavar='<port_name>', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def tunnel_route(db, port, json_output):
    """show muxcable tunnel-route <port_name>"""

    port = platform_sfputil_helper.get_interface_name(port, db)

    per_npu_appl_db = {}
    per_npu_asic_db = {}
    per_npu_configdb = {}
    mux_tbl_keys = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)

        per_npu_appl_db[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_appl_db[asic_id].connect(per_npu_appl_db[asic_id].APPL_DB)

        per_npu_asic_db[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_asic_db[asic_id].connect(per_npu_asic_db[asic_id].ASIC_DB)

        per_npu_configdb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_configdb[asic_id].connect(per_npu_configdb[asic_id].CONFIG_DB) 

        mux_tbl_keys[asic_id] = per_npu_configdb[asic_id].keys(
            per_npu_configdb[asic_id].CONFIG_DB, "MUX_CABLE|*")

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        if port not in logical_port_list:
            port_name = platform_sfputil_helper.get_interface_alias(port, db)
            click.echo(("ERR: Not a valid logical port for dualtor firmware {}".format(port_name)))
            sys.exit(CONFIG_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                port_name = platform_sfputil_helper.get_interface_alias(port, db)
                click.echo("Got invalid asic index for port {}, cant retreive tunnel route info".format(port_name))
                sys.exit(STATUS_FAIL)
        
        if mux_tbl_keys[asic_index] is not None and "MUX_CABLE|{}".format(port) in mux_tbl_keys[asic_index]:
            if json_output:
                port_tunnel_route = {}
                port_tunnel_route["TUNNEL_ROUTE"] = {}

                create_json_dump_per_port_tunnel_route(db, port_tunnel_route, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_index, port)

                click.echo("{}".format(json.dumps(port_tunnel_route, indent=4)))

            else:
                print_data = []

                create_table_dump_per_port_tunnel_route(db, print_data, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_index, port)

                headers = ['PORT', 'DEST_TYPE', 'DEST_ADDRESS']

                click.echo(tabulate(print_data, headers=headers))
        else:
            click.echo("this is not a valid port present on dualToR".format(port))
            sys.exit(STATUS_FAIL)
    
    else:
        if json_output:
            port_tunnel_route = {}
            port_tunnel_route["TUNNEL_ROUTE"] = {}
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in natsorted(mux_tbl_keys[asic_id]):
                    port = key.split("|")[1]

                    create_json_dump_per_port_tunnel_route(db, port_tunnel_route, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_id, port)
            
            click.echo("{}".format(json.dumps(port_tunnel_route, indent=4)))
        else:
            print_data = []

            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in natsorted(mux_tbl_keys[asic_id]):
                    port = key.split("|")[1]
            
                    create_table_dump_per_port_tunnel_route(db, print_data, per_npu_configdb, per_npu_appl_db, per_npu_asic_db, asic_id, port)

            headers = ['PORT', 'DEST_TYPE', 'DEST_ADDRESS']

            click.echo(tabulate(print_data, headers=headers))

    sys.exit(STATUS_SUCCESSFUL)
