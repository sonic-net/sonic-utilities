#
# 'spanning-tree'  group ('config spanning-tree ...')
#

"""
- There will be mode check in each command to check if the mode is PVST or MST
- For PVST, priority can be set in global table but for MST,
  priority is associated with instance ID and will be set in the MST INSTANCE TABLE


***Existing PVST commands that are used for MST Commands***

    === config spanning_tree enable <pvst|mst> #enable pvst or mst
    === config spanning_tree disable <pvst|mst> #disable pvst or mst

    === config spanning_tree hello <value> #set hello time pvst or mst

    === config spanning_tree max_age <value> #set max age pvst or mst

    === config spanning_tree forward_delay <value> #set forward delay pvst or mst


    INTERFACE GROUP:
    config spanning_tree interface enable <ifname> #enable pvst or mst on interface
    config spanning_tree interface disable <ifname> #disable pvst or mst on interface

    config spanning_tree interface bpdu_guard enable <ifname>
    config spanning_tree interface bpdu_guard disable <ifname>

    config spanning_tree interface root_guard enable <ifname>
    config spanning_tree interface root_guard disable <ifname>

    config spanning_tree interface priority <ifname> <port-priority-value>

    config spanning_tree interface cost <ifname> <cost-value>


***NEW MST Commands***
    === config spanning_tree max_hops <value> (Not for PVST)

    MST GROUP:
    === config spanning_tree mst region-name <region-name>
    === config spanning_tree mst revision <number>

    config spanning_tree mst instance <instance-id> priority <bridge-priority-value>

    config spanning_tree mst instance <instance-id> vlan add <vlan-id>
    config spanning_tree mst instance <instance-id> vlan del <vlan-id>

    config spanning_tree mst instance <instance-id> interface <ifname> priority <port-priority-value>
    config spanning_tree mst instance <instance-id> interface <ifname> cost <cost-value>

    INTERFACE GROUP:
    config spanning_tree interface edge_port enable <ifname> #enable edge_port on interface for mst
    config spanning_tree interface edge_port disable <ifname> #disable edge_port on interface for mst

    config spanning_tree interface link_type point-to-point <interface_name>
    config spanning_tree interface link_type shared <interface_name>
    config spanning_tree interface link_type auto <interface_name>

"""

import click
import utilities_common.cli as clicommon
from natsort import natsorted
import logging

# MSTP parameters

MST_MIN_HOPS = 1
MST_MAX_HOPS = 40
MST_DEFAULT_HOPS = 20

MST_MIN_HELLO_TIME = 1
MST_MAX_HELLO_TIME = 10
MST_DEFAULT_HELLO_TIME = 2

MST_MIN_MAX_AGE = 6
MST_MAX_MAX_AGE = 40
MST_DEFAULT_MAX_AGE = 20

MST_MIN_REVISION = 0
MST_MAX_REVISION = 65535
MST_DEFAULT_REVISION = 0

MST_MIN_BRIDGE_PRIORITY = 0
MST_MAX_BRIDGE_PRIORITY = 61440
MST_DEFAULT_BRIDGE_PRIORITY = 32768

MST_MIN_PORT_PRIORITY = 0
MST_MAX_PORT_PRIORITY = 240
MST_DEFAULT_PORT_PRIORITY = 128

MST_MIN_FORWARD_DELAY = 4
MST_MAX_FORWARD_DELAY = 30
MST_DEFAULT_FORWARD_DELAY = 15

MST_MIN_ROOT_GUARD_TIMEOUT = 5
MST_MAX_ROOT_GUARD_TIMEOUT = 600
MST_DEFAULT_ROOT_GUARD_TIMEOUT = 30

MST_MIN_INSTANCES = 0
MST_MAX_INSTANCES = 63
MST_DEFAULT_INSTANCE = 0

MST_MIN_PORT_PATH_COST = 1
MST_MAX_PORT_PATH_COST = 200000000
MST_DEFAULT_PORT_PATH_COST = 1

MST_AUTO_LINK_TYPE = 'auto'
MST_P2P_LINK_TYPE = 'p2p'
MST_SHARED_LINK_TYPE = 'shared'

# STP parameters

STP_MIN_ROOT_GUARD_TIMEOUT = 5
STP_MAX_ROOT_GUARD_TIMEOUT = 600
STP_DEFAULT_ROOT_GUARD_TIMEOUT = 30

STP_MIN_FORWARD_DELAY = 4
STP_MAX_FORWARD_DELAY = 30
STP_DEFAULT_FORWARD_DELAY = 15

STP_MIN_HELLO_INTERVAL = 1
STP_MAX_HELLO_INTERVAL = 10
STP_DEFAULT_HELLO_INTERVAL = 2

STP_MIN_MAX_AGE = 6
STP_MAX_MAX_AGE = 40
STP_DEFAULT_MAX_AGE = 20

STP_MIN_BRIDGE_PRIORITY = 0
STP_MAX_BRIDGE_PRIORITY = 61440
STP_DEFAULT_BRIDGE_PRIORITY = 32768

PVST_MAX_INSTANCES = 255


def get_intf_list_in_vlan_member_table(config_db):
    """
    Get info from REDIS ConfigDB and create interface to vlan mapping
    """
    get_int_vlan_configdb_info = config_db.get_table('VLAN_MEMBER')
    int_list = []
    for key in get_int_vlan_configdb_info:
        interface = key[1]
        if interface not in int_list:
            int_list.append(interface)
    return int_list

##################################
# STP parameter validations
##################################


def is_valid_root_guard_timeout(ctx, root_guard_timeout):
    if root_guard_timeout not in range(STP_MIN_ROOT_GUARD_TIMEOUT, STP_MAX_ROOT_GUARD_TIMEOUT + 1):
        ctx.fail("STP root guard timeout must be in range 5-600")


def is_valid_forward_delay(ctx, forward_delay):
    if forward_delay not in range(STP_MIN_FORWARD_DELAY, STP_MAX_FORWARD_DELAY + 1):
        ctx.fail("STP forward delay value must be in range 4-30")


def is_valid_hello_interval(ctx, hello_interval):
    if hello_interval not in range(STP_MIN_HELLO_INTERVAL, STP_MAX_HELLO_INTERVAL + 1):
        ctx.fail("STP hello timer must be in range 1-10")


def is_valid_max_age(ctx, max_age):
    if max_age not in range(STP_MIN_MAX_AGE, STP_MAX_MAX_AGE + 1):
        ctx.fail("STP max age value must be in range 6-40")


def is_valid_bridge_priority(ctx, priority):
    if priority % 4096 != 0:
        ctx.fail("STP bridge priority must be multiple of 4096")
    if priority not in range(STP_MIN_BRIDGE_PRIORITY, STP_MAX_BRIDGE_PRIORITY + 1):
        ctx.fail("STP bridge priority must be in range 0-61440")


def validate_params(forward_delay, max_age, hello_time):
    if (2 * (int(forward_delay) - 1)) >= int(max_age) >= (2 * (int(hello_time) + 1)):
        return True
    else:
        return False


def is_valid_stp_vlan_parameters(ctx, db, vlan_name, param_type, new_value):
    stp_vlan_entry = db.get_entry('STP_VLAN', vlan_name)
    cfg_vlan_forward_delay = stp_vlan_entry.get("forward_delay")
    cfg_vlan_max_age = stp_vlan_entry.get("max_age")
    cfg_vlan_hello_time = stp_vlan_entry.get("hello_time")
    ret_val = False
    if param_type == "forward_delay":
        ret_val = validate_params(new_value, cfg_vlan_max_age, cfg_vlan_hello_time)
    elif param_type == "max_age":
        ret_val = validate_params(cfg_vlan_forward_delay, new_value, cfg_vlan_hello_time)
    elif param_type == "hello_time":
        ret_val = validate_params(cfg_vlan_forward_delay, cfg_vlan_max_age, new_value)

    if ret_val is not True:
        ctx.fail("2*(forward_delay-1) >= max_age >= 2*(hello_time +1 ) not met for VLAN")


def is_valid_stp_global_parameters(ctx, db, param_type, new_value):
    stp_global_entry = db.get_entry('STP', "GLOBAL")
    cfg_forward_delay = stp_global_entry.get("forward_delay")
    cfg_max_age = stp_global_entry.get("max_age")
    cfg_hello_time = stp_global_entry.get("hello_time")
    ret_val = False
    if param_type == "forward_delay":
        ret_val = validate_params(new_value, cfg_max_age, cfg_hello_time)
    elif param_type == "max_age":
        ret_val = validate_params(cfg_forward_delay, new_value, cfg_hello_time)
    elif param_type == "hello_time":
        ret_val = validate_params(cfg_forward_delay, cfg_max_age, new_value)

    if ret_val is not True:
        ctx.fail("2*(forward_delay-1) >= max_age >= 2*(hello_time +1 ) not met")


def get_max_stp_instances():
    return PVST_MAX_INSTANCES


def update_stp_vlan_parameter(ctx, db, param_type, new_value):
    stp_global_entry = db.get_entry('STP', "GLOBAL")

    allowed_params = {"priority", "max_age", "hello_time", "forward_delay"}
    if param_type not in allowed_params:
        ctx.fail("Invalid parameter")

    current_global_value = stp_global_entry.get("forward_delay")

    vlan_dict = db.get_table('STP_VLAN')
    for vlan in vlan_dict.keys():
        vlan_entry = db.get_entry('STP_VLAN', vlan)
        current_vlan_value = vlan_entry.get(param_type)
        if current_global_value == current_vlan_value:
            db.mod_entry('STP_VLAN', vlan, {param_type: new_value})

def check_if_vlan_exist_in_db(db, ctx, vid):
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)
    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))


def enable_stp_for_vlans(db):
    vlan_count = 0
    fvs = {'enabled': 'true',
           'forward_delay': get_global_stp_forward_delay(db),
           'hello_time': get_global_stp_hello_time(db),
           'max_age': get_global_stp_max_age(db),
           'priority': get_global_stp_priority(db)
           }
    vlan_dict = natsorted(db.get_table('VLAN'))
    max_stp_instances = get_max_stp_instances()
    for vlan_key in vlan_dict:
        if vlan_count >= max_stp_instances:
            logging.warning("Exceeded maximum STP configurable VLAN instances for {}".format(vlan_key))
            break
        db.set_entry('STP_VLAN', vlan_key, fvs)
        vlan_count += 1


def get_stp_enabled_vlan_count(db):
    count = 0
    stp_vlan_keys = db.get_table('STP_VLAN').keys()
    for key in stp_vlan_keys:
        if db.get_entry('STP_VLAN', key).get('enabled') == 'true':
            count += 1
    return count


def vlan_enable_stp(db, vlan_name):
    fvs = {'enabled': 'true',
           'forward_delay': get_global_stp_forward_delay(db),
           'hello_time': get_global_stp_hello_time(db),
           'max_age': get_global_stp_max_age(db),
           'priority': get_global_stp_priority(db)
           }
    if is_global_stp_enabled(db):
        if get_stp_enabled_vlan_count(db) < get_max_stp_instances():
            db.set_entry('STP_VLAN', vlan_name, fvs)
        else:
            logging.warning("Exceeded maximum STP configurable VLAN instances for {}".format(vlan_name))


def interface_enable_stp(db, interface_name):
    fvs = {'enabled': 'true',
           'root_guard': 'false',
           'bpdu_guard': 'false',
           'bpdu_guard_do_disable': 'false',
           'portfast': 'false',
           'uplink_fast': 'false'
           }
    if is_global_stp_enabled(db):
        db.set_entry('STP_PORT', interface_name, fvs)


def is_vlan_configured_interface(db, interface_name):
    intf_to_vlan_list = get_vlan_list_for_interface(db, interface_name)
    if intf_to_vlan_list:  # if empty
        return True
    else:
        return False


def is_interface_vlan_member(db, vlan_name, interface_name):
    ctx = click.get_current_context()
    key = vlan_name + '|' + interface_name
    entry = db.get_entry('VLAN_MEMBER', key)
    if len(entry) == 0:  # if empty
        ctx.fail("{} is not member of {}".format(interface_name, vlan_name))


def get_vlan_list_for_interface(db, interface_name):
    vlan_intf_info = db.get_table('VLAN_MEMBER')
    vlan_list = []
    for line in vlan_intf_info:
        if interface_name == line[1]:
            vlan_name = line[0]
            vlan_list.append(vlan_name)
    return vlan_list


def get_pc_member_port_list(db):
    pc_member_info = db.get_table('PORTCHANNEL_MEMBER')
    pc_member_port_list = []
    for line in pc_member_info:
        intf_name = line[1]
        pc_member_port_list.append(intf_name)
    return pc_member_port_list


def get_vlan_list_from_stp_vlan_intf_table(db, intf_name):
    stp_vlan_intf_info = db.get_table('STP_VLAN_PORT')
    vlan_list = []
    for line in stp_vlan_intf_info:
        if line[1] == intf_name:
            vlan_list.append(line[0])
    return vlan_list


def get_intf_list_from_stp_vlan_intf_table(db, vlan_name):
    stp_vlan_intf_info = db.get_table('STP_VLAN_PORT')
    intf_list = []
    for line in stp_vlan_intf_info:
        if line[0] == vlan_name:
            intf_list.append(line[1])
    return intf_list


def is_portchannel_member_port(db, interface_name):
    return interface_name in get_pc_member_port_list(db)


def enable_stp_for_interfaces(db):
    fvs = {'enabled': 'true',
           'root_guard': 'false',
           'bpdu_guard': 'false',
           'bpdu_guard_do_disable': 'false',
           'portfast': 'false',
           'uplink_fast': 'false'
           }
    port_dict = natsorted(db.get_table('PORT'))
    intf_list_in_vlan_member_table = get_intf_list_in_vlan_member_table(db)

    for port_key in port_dict:
        if port_key in intf_list_in_vlan_member_table:
            db.set_entry('STP_PORT', port_key, fvs)

    po_ch_dict = natsorted(db.get_table('PORTCHANNEL'))
    for po_ch_key in po_ch_dict:
        if po_ch_key in intf_list_in_vlan_member_table:
            db.set_entry('STP_PORT', po_ch_key, fvs)


def is_global_stp_enabled(db):
    stp_entry = db.get_entry('STP', "GLOBAL")
    mode = stp_entry.get("mode")
    if mode and mode != "none":
        return True
    else:
        return False


def check_if_global_stp_enabled(db, ctx):
    if not is_global_stp_enabled(db):
        ctx.fail("Global STP is not enabled - first configure STP mode")


def get_global_stp_mode(db):
    stp_entry = db.get_entry('STP', "GLOBAL")
    mode = stp_entry.get("mode")
    return mode


def get_global_stp_forward_delay(db):
    stp_entry = db.get_entry('STP', "GLOBAL")
    forward_delay = stp_entry.get("forward_delay")
    return forward_delay


def get_global_stp_hello_time(db):
    stp_entry = db.get_entry('STP', "GLOBAL")
    hello_time = stp_entry.get("hello_time")
    return hello_time


def get_global_stp_max_age(db):
    stp_entry = db.get_entry('STP', "GLOBAL")
    max_age = stp_entry.get("max_age")
    return max_age


def get_global_stp_priority(db):
    stp_entry = db.get_entry('STP', "GLOBAL")
    priority = stp_entry.get("priority")
    return priority


def get_bridge_mac_address(db):
    """Retrieve the bridge MAC address from the CONFIG_DB"""
    device_metadata = db.get_entry('DEVICE_METADATA', 'localhost')
    bridge_mac_address = device_metadata.get('mac')
    return bridge_mac_address


def enable_mst_instance0(db):
    mst_inst_fvs = {
        'bridge_priority': MST_DEFAULT_BRIDGE_PRIORITY
    }
    instance_id = 0
    db.set_entry('STP_MST_INST', f"MST_INSTANCE:INSTANCE{instance_id}", mst_inst_fvs)


def enable_mst_for_interfaces(db):
    fvs_port = {
        'edge_port': 'false',
        'link_type': MST_AUTO_LINK_TYPE,
        'enabled': 'true',
        'bpdu_guard': 'false',
        'bpdu_guard_do': 'false',
        'root_guard': 'false',
        'path_cost': MST_DEFAULT_PORT_PATH_COST,
        'priority': MST_DEFAULT_PORT_PRIORITY
        }

    fvs_mst_port = {
        'path_cost': MST_DEFAULT_PORT_PATH_COST,
        'priority': MST_DEFAULT_PORT_PRIORITY
        }

    port_dict = natsorted(db.get_table('PORT'))
    intf_list_in_vlan_member_table = get_intf_list_in_vlan_member_table(db)

    for port_key in port_dict:
        if port_key in intf_list_in_vlan_member_table:
            db.set_entry('STP_MST_PORT', f"MST_INSTANCE|0|{port_key}", fvs_mst_port)
            db.set_entry('STP_PORT', port_key, fvs_port)

    po_ch_dict = natsorted(db.get_table('PORTCHANNEL'))
    for po_ch_key in po_ch_dict:
        if po_ch_key in intf_list_in_vlan_member_table:
            db.set_entry('STP_MST_PORT', f"MST_INSTANCE|0|{po_ch_key}", fvs_mst_port)
            db.set_entry('STP_PORT', po_ch_key, fvs_port)


def disable_global_pvst(db):
    db.set_entry('STP', "GLOBAL", None)
    db.delete_table('STP_VLAN')
    db.delete_table('STP_PORT')
    db.delete_table('STP_VLAN_PORT')


def disable_global_mst(db):
    db.set_entry('STP', "GLOBAL", None)
    db.delete_table('STP_MST')
    db.delete_table('STP_MST_INST')
    db.delete_table('STP_MST_PORT')
    db.delete_table('STP_PORT')


@click.group()
@clicommon.pass_db
def spanning_tree(_db):
    """STP command line"""
    pass


###############################################
# STP Global commands implementation
###############################################

# cmd: STP enable
# Modifies & sets parameters in different tables for MST & PVST
# config spanning_tree enable <pvst|mst>
@spanning_tree.command('enable')
@click.argument('mode', metavar='<pvst|mst>', required=True, type=click.Choice(["pvst", "mst"]))
@clicommon.pass_db
def spanning_tree_enable(_db, mode):
    """enable STP """
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)

    if mode == "pvst" and current_mode == "pvst":
        ctx.fail("PVST is already configured")
    elif mode == "mst" and current_mode == "mst":
        ctx.fail("MST is already configured")
    elif mode == "pvst" and current_mode == "mst":
        ctx.fail("MSTP is already configured; please disable MST before enabling PVST")
    elif mode == "mst" and current_mode == "pvst":
        ctx.fail("PVST is already configured; please disable PVST before enabling MST")

    if mode == "pvst":
        fvs = {'mode': mode,
               'rootguard_timeout': STP_DEFAULT_ROOT_GUARD_TIMEOUT,
               'forward_delay': STP_DEFAULT_FORWARD_DELAY,
               'hello_time': STP_DEFAULT_HELLO_INTERVAL,
               'max_age': STP_DEFAULT_MAX_AGE,
               'priority': STP_DEFAULT_BRIDGE_PRIORITY
               }
        db.set_entry('STP', "GLOBAL", fvs)

        enable_stp_for_interfaces(db)
        enable_stp_for_vlans(db)  # Enable STP for VLAN by default

    elif mode == "mst":
        fvs = {'mode': mode
               }
        db.set_entry('STP', "GLOBAL", fvs)

        enable_mst_for_interfaces(db)
        enable_mst_instance0(db)


# cmd: STP disable
# config spanning_tree disable <pvst|mst> (Modify mode parameter for MST or PVST and Delete tables)
# Modify mode in STP GLOBAL table to None
# Delete tables STP_MST, STP_MST_INST, STP_MST_PORT, and STP_PORT
@spanning_tree.command('disable')
@click.argument('mode', metavar='<pvst|mst>', required=True, type=click.Choice(["pvst", "mst"]))
@clicommon.pass_db
def stp_disable(_db, mode):
    """disable STP """
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)

    if not current_mode or current_mode == "none":
        ctx.fail("STP is not configured")
    elif mode != current_mode and current_mode != "none":
        ctx.fail(f"{mode.upper()} is not currently configured mode")

    if mode == "pvst" and current_mode == "pvst":
        disable_global_pvst(db)
    elif mode == "mst" and current_mode == "mst":
        disable_global_mst(db)



# cmd: STP global root guard timeout
# NOT VALID FOR MST
# config spanning_tree root_guard_timeout <5-600 seconds>
@spanning_tree.command('root_guard_timeout')
@click.argument('root_guard_timeout', metavar='<5-600 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_root_guard_timeout(_db, root_guard_timeout):
    """Configure STP global root guard timeout value"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "mst":
        ctx.fail("Root guard timeout not supported for MST")

    elif current_mode == "pvst":
        is_valid_root_guard_timeout(ctx, root_guard_timeout)
        db.mod_entry('STP', "GLOBAL", {'rootguard_timeout': root_guard_timeout})
    else:
        ctx.fail("Invalid STP mode configuration, no mode is enabled")


# cmd: STP global forward delay
# MST CONFIGURATION IN THE STP_MST GLOBAL TABLE
# config spanning_tree forward_delay <4-30 seconds>
@spanning_tree.command('forward_delay')
@click.argument('forward_delay', metavar='<4-30 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_forward_delay(_db, forward_delay):
    """Configure STP global forward delay"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        is_valid_forward_delay(ctx, forward_delay)
        is_valid_stp_global_parameters(ctx, db, "forward_delay", forward_delay)
        update_stp_vlan_parameter(ctx, db, "forward_delay", forward_delay)
        db.mod_entry('STP', "GLOBAL", {'forward_delay': forward_delay})

    elif current_mode == "mst":
        is_valid_forward_delay(ctx, forward_delay)
        db.mod_entry('STP_MST', "GLOBAL", {'forward_delay': forward_delay})

    else:
        ctx.fail("Invalid STP mode configuration, no mode is enabled")


# cmd: STP global hello interval
# MST CONFIGURATION IN THE STP_MST GLOBAL TABLE
# config spanning_tree hello <1-10 seconds>
@spanning_tree.command('hello')
@click.argument('hello_interval', metavar='<1-10 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_hello_interval(_db, hello_interval):
    """Configure STP global hello interval"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        is_valid_hello_interval(ctx, hello_interval)
        is_valid_stp_global_parameters(ctx, db, "hello_time", hello_interval)
        update_stp_vlan_parameter(ctx, db, "hello_time", hello_interval)
        db.mod_entry('STP', "GLOBAL", {'hello_time': hello_interval})

    elif current_mode == "mst":
        is_valid_hello_interval(ctx, hello_interval)
        db.mod_entry('STP_MST', "GLOBAL", {'hello_time': hello_interval})

    else:
        ctx.fail("Invalid STP mode configuration, no mode is enabled")


# cmd: STP global max age
# MST CONFIGURATION IN THE STP_MST GLOBAL TABLE
# config spanning_tree max_age <6-40 seconds>
@spanning_tree.command('max_age')
@click.argument('max_age', metavar='<6-40 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_max_age(_db, max_age):
    """Configure STP global max_age"""
    ctx = click.get_current_context()  # Ensure we are getting the correct context
    db = _db.cfgdb

    # Check if global STP is enabled
    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        # Validate max_age for PVST mode
        is_valid_max_age(ctx, max_age)
        is_valid_stp_global_parameters(ctx, db, "max_age", max_age)
        update_stp_vlan_parameter(ctx, db, "max_age", max_age)
        db.mod_entry('STP', "GLOBAL", {'max_age': max_age})

    elif current_mode == "mst":
        # Validate max_age for MST mode
        is_valid_max_age(ctx, max_age)
        db.mod_entry('STP_MST', "GLOBAL", {'max_age': max_age})

    else:
        # If the mode is invalid, fail with an error message
        ctx.fail("Invalid STP mode configuration, no mode is enabled")


# cmd: STP global max hop
# NO GLOBAL MAX HOP FOR PVST
# MST CONFIGURATION IN THE STP_MST GLOBAL TABLE
# config spanning_tree max_hops <6-40 seconds>
@spanning_tree.command('max_hops')
@click.argument('max_hops', metavar='<1-40>', required=True, type=int)
@clicommon.pass_db
def stp_global_max_hops(_db, max_hops):
    """Configure STP global max_hops"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        ctx.fail("Max hops not supported for PVST")

    elif current_mode == "mst":
        if max_hops not in range(MST_MIN_HOPS, MST_MAX_HOPS + 1):
            ctx.fail("STP max hops must be in range 1-40")
        db.mod_entry('STP_MST', "GLOBAL", {'max_hops': max_hops})
    else:
        ctx.fail("Invalid STP mode configured")


# Bridge priority cannot be set without Instance ID
# cmd: STP global bridge priority
# NOT SET FOR MST
# config spanning_tree priority <0-61440>
@spanning_tree.command('priority')
@click.argument('priority', metavar='<0-61440>', required=True, type=int)
@clicommon.pass_db
def stp_global_priority(_db, priority):
    """Configure STP global bridge priority"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        is_valid_bridge_priority(ctx, priority)
        update_stp_vlan_parameter(ctx, db, "priority", priority)
        db.mod_entry('STP', "GLOBAL", {'priority': priority})

    elif current_mode == "mst":
        ctx.fail("Bridge priority cannot be set for MST with this command without Instance ID")

    else:
        ctx.fail("Invalid STP mode configured")


# config spanning_tree mst
@spanning_tree.group()
def mst():
    """Configure MSTP region, instance, show, clear & debug commands"""
    pass


# MST REGION commands implementation
# cmd: MST region-name
# MST CONFIGURATION IN THE STP_MST GLOBAL TABLE
# config spanning_tree mst region-name <name>
@mst.command('region-name')
@click.argument('region_name', metavar='<name>', required=True)
@clicommon.pass_db
def stp_mst_region_name(_db, region_name):
    """Configure MSTP region name"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        ctx.fail("Configuration not supported for PVST")

    elif current_mode == "mst":
        if len(region_name) >= 32:
            ctx.fail("Region name must be less than 32 characters")

        db.mod_entry('STP_MST', "GLOBAL", {'name': region_name})


# cmd: MST Global revision number
# MST CONFIGURATION IN THE STP_MST GLOBAL TABLE
# config spanning_tree mst revision <0-65535>
@mst.command('revision')
@click.argument('revision', metavar='<0-65535>', required=True, type=int)
@clicommon.pass_db
def stp_global_revision(_db, revision):
    """Configure STP global revision number"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)

    current_mode = get_global_stp_mode(db)

    if current_mode == "pvst":
        ctx.fail("Configuration not supported for PVST")

    elif current_mode == "mst":
        # Valid revisions are inclusive: [MST_MIN_REVISION, MST_MAX_REVISION]
        if revision not in range(MST_MIN_REVISION, MST_MAX_REVISION + 1):
            ctx.fail("STP revision number must be in range 0-65535")

        db.mod_entry('STP_MST', "GLOBAL", {'revision': revision})
        # db.mod_entry('STP_MST', "STP_MST|GLOBAL", {'revision': revision})


###############################################
# STP VLAN commands implementation
###############################################

# config spanning_tree vlan
@spanning_tree.group('vlan')
@clicommon.pass_db
def spanning_tree_vlan(_db):
    """Configure STP for a VLAN"""
    pass


def is_stp_enabled_for_vlan(db, vlan_name):
    stp_entry = db.get_entry('STP_VLAN', vlan_name)
    stp_enabled = stp_entry.get("enabled")
    if stp_enabled == "true":
        return True
    else:
        return False


def check_if_stp_enabled_for_vlan(ctx, db, vlan_name):
    if not is_stp_enabled_for_vlan(db, vlan_name):
        ctx.fail("STP is not enabled for VLAN")


# Not for MST
# config spanning_tree vlan enable <vlan-id>
@spanning_tree_vlan.command('enable')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_enable(_db, vid):
    """Enable STP for a VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    current_mode = get_global_stp_mode(db)

    if current_mode == "mst":
        ctx.fail("Configuration not supported for MST")

    elif current_mode == "pvst":
        check_if_vlan_exist_in_db(db, ctx, vid)
        vlan_name = 'Vlan{}'.format(vid)
        if is_stp_enabled_for_vlan(db, vlan_name):
            ctx.fail("STP is already enabled for " + vlan_name)
        if get_stp_enabled_vlan_count(db) >= get_max_stp_instances():
            ctx.fail("Exceeded maximum STP configurable VLAN instances")
        check_if_global_stp_enabled(db, ctx)
        stp_vlan_entry = db.get_entry('STP_VLAN', vlan_name)
        if len(stp_vlan_entry) == 0:
            fvs = {'enabled': 'true',
                   'forward_delay': get_global_stp_forward_delay(db),
                   'hello_time': get_global_stp_hello_time(db),
                   'max_age': get_global_stp_max_age(db),
                   'priority': get_global_stp_priority(db)}
            db.set_entry('STP_VLAN', vlan_name, fvs)
        else:
            db.mod_entry('STP_VLAN', vlan_name, {'enabled': 'true'})
        # Refresh stp_vlan_intf entry for vlan
        for vlan, intf in db.get_table('STP_VLAN_PORT'):
            if vlan == vlan_name:
                vlan_intf_key = "{}|{}".format(vlan_name, intf)
                vlan_intf_entry = db.get_entry('STP_VLAN_PORT', vlan_intf_key)
                db.mod_entry('STP_VLAN_PORT', vlan_intf_key, vlan_intf_entry)


# Not for MST
# config spanning_tree vlan disable <vlan-id>
@spanning_tree_vlan.command('disable')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_disable(_db, vid):
    """Disable STP for a VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Configuration not supported for MST")

    elif current_mode == "pvst":
        check_if_vlan_exist_in_db(db, ctx, vid)
        vlan_name = 'Vlan{}'.format(vid)
        db.mod_entry('STP_VLAN', vlan_name, {'enabled': 'false'})


# not for MST
# config spanning_tree vlan forward_delay <vlan-id> <4-30 seconds>
@spanning_tree_vlan.command('forward_delay')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('forward_delay', metavar='<4-30 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_forward_delay(_db, vid, forward_delay):
    """Configure STP forward delay for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Configuration not supported for MST")
    elif current_mode == "pvst":
        check_if_vlan_exist_in_db(db, ctx, vid)
        vlan_name = 'Vlan{}'.format(vid)
        check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
        is_valid_forward_delay(ctx, forward_delay)
        is_valid_stp_vlan_parameters(ctx, db, vlan_name, "forward_delay", forward_delay)
        db.mod_entry('STP_VLAN', vlan_name, {'forward_delay': forward_delay})


# Not for MST
# config spanning_tree vlan hello <vlan-id> <1-10 seconds>
@spanning_tree_vlan.command('hello')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('hello_interval', metavar='<1-10 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_hello_interval(_db, vid, hello_interval):
    """Configure STP hello interval for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Configuration not supported for MST")
    elif current_mode == "pvst":
        check_if_vlan_exist_in_db(db, ctx, vid)
        vlan_name = 'Vlan{}'.format(vid)
        check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
        is_valid_hello_interval(ctx, hello_interval)
        is_valid_stp_vlan_parameters(ctx, db, vlan_name, "hello_time", hello_interval)
        db.mod_entry('STP_VLAN', vlan_name, {'hello_time': hello_interval})


# not for MST
# config spanning_tree vlan max_age <vlan-id> <6-40 seconds>
@spanning_tree_vlan.command('max_age')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('max_age', metavar='<6-40 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_max_age(_db, vid, max_age):
    """Configure STP max age for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Configuration not supported for MST")
    elif current_mode == "pvst":
        check_if_vlan_exist_in_db(db, ctx, vid)
        vlan_name = 'Vlan{}'.format(vid)
        check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
        is_valid_max_age(ctx, max_age)
        is_valid_stp_vlan_parameters(ctx, db, vlan_name, "max_age", max_age)
        db.mod_entry('STP_VLAN', vlan_name, {'max_age': max_age})


# not for MST
# config spanning_tree vlan priority <vlan-id> <0-61440>
@spanning_tree_vlan.command('priority')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('priority', metavar='<0-61440>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_priority(_db, vid, priority):
    """Configure STP bridge priority for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Configuration not supported for MST")
    elif current_mode == "pvst":
        check_if_vlan_exist_in_db(db, ctx, vid)
        vlan_name = 'Vlan{}'.format(vid)
        check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
        is_valid_bridge_priority(ctx, priority)
        db.mod_entry('STP_VLAN', vlan_name, {'priority': priority})


###############################################
# STP interface commands implementation
###############################################


def is_stp_enabled_for_interface(db, intf_name):
    stp_entry = db.get_entry('STP_PORT', intf_name)
    stp_enabled = stp_entry.get("enabled")
    if stp_enabled == "true":
        return True
    else:
        return False


def check_if_stp_enabled_for_interface(ctx, db, intf_name):
    if not is_stp_enabled_for_interface(db, intf_name):
        ctx.fail("STP is not enabled for interface {}".format(intf_name))


def check_if_interface_is_valid(ctx, db, interface_name):
    from config.main import interface_name_is_valid
    if interface_name_is_valid(db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")
    for key in db.get_table('INTERFACE'):
        if type(key) != tuple:
            continue
        if key[0] == interface_name:
            ctx.fail(" {} has ip address {} configured - It's not a L2 interface".format(interface_name, key[1]))
    if is_portchannel_member_port(db, interface_name):
        ctx.fail(" {} is a portchannel member port - STP can't be configured".format(interface_name))
    if not is_vlan_configured_interface(db, interface_name):
        ctx.fail(" {} has no VLAN configured - It's not a L2 interface".format(interface_name))


# config spanning_tree interface
@spanning_tree.group('interface')
@clicommon.pass_db
def spanning_tree_interface(_db):
    """Configure STP for interface"""
    pass


# STP interface port priority
STP_INTERFACE_MIN_PRIORITY = 0
STP_INTERFACE_MAX_PRIORITY = 240
STP_INTERFACE_DEFAULT_PRIORITY = 128


def is_valid_interface_priority(ctx, intf_priority):
    if intf_priority not in range(STP_INTERFACE_MIN_PRIORITY, STP_INTERFACE_MAX_PRIORITY + 1):
        ctx.fail("STP interface priority must be in range 0-240")


# STP interface port path cost
STP_INTERFACE_MIN_PATH_COST = 1
STP_INTERFACE_MAX_PATH_COST = 200000000


def is_valid_interface_path_cost(ctx, intf_path_cost):
    if intf_path_cost < STP_INTERFACE_MIN_PATH_COST or intf_path_cost > STP_INTERFACE_MAX_PATH_COST:
        ctx.fail("STP interface path cost must be in range 1-200000000")


# config spanning_tree interface cost <interface_name> <value: 1-200000000>
@spanning_tree_interface.command('cost')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('cost', metavar='<1-200000000>', required=True, type=int)
@clicommon.pass_db
def stp_interface_path_cost(_db, interface_name, cost):
    """Configure STP path cost for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    is_valid_interface_path_cost(ctx, cost)
    curr_intf_cost = db.get_entry('STP_PORT', interface_name).get('path_cost')
    db.mod_entry('STP_PORT', interface_name, {'path_cost': cost})
    # update interface path_cost in all stp_vlan_intf entries if entry exists
    for vlan, intf in db.get_table('STP_VLAN_PORT'):
        if intf == interface_name:
            vlan_intf_key = "{}|{}".format(vlan, interface_name)
            vlan_intf_entry = db.get_entry('STP_VLAN_PORT', vlan_intf_key)
            if len(vlan_intf_entry) != 0:
                vlan_intf_cost = vlan_intf_entry.get('path_cost')
                if curr_intf_cost == vlan_intf_cost:
                    db.mod_entry('STP_VLAN_PORT', vlan_intf_key, {'path_cost': cost})


# STP interface portfast
# config spanning_tree interface portfast
# Only for PVST
@spanning_tree_interface.group('portfast')
@clicommon.pass_db
def spanning_tree_interface_portfast(_db):
    """Configure STP portfast for interface"""
    pass


# config spanning_tree interface portfast enable <interface_name>
# MST CONFIGURATION IN THE STP_PORT TABLE
# It should the mode attribute in the STP global table
# If the mode is MST, then it should tell that the mode if MST, and not allow to configure portfast
@spanning_tree_interface_portfast.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_portfast_enable(_db, interface_name):
    """Enable STP portfast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Portfast is supported only for PVST mode")
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'portfast': 'true'})


# config spanning_tree interface portfast disable <interface_name>
# MST CONFIGURATION IN THE STP_PORT TABLE
# It should the mode attribute in the STP global table
# If the mode is MST, then it should tell that the mode if mst, and this cannot be done.
@spanning_tree_interface_portfast.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_portfast_disable(_db, interface_name):
    """Disable STP portfast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Portfast is supported only for PVST mode")
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'portfast': 'false'})


# config spanning_tree interface edge_port
# Only for MST

@spanning_tree_interface.group('edge_port')
@clicommon.pass_db
def spanning_tree_interface_edge_port(_db):
    """Configure STP edge_port for interface"""
    pass

# config spanning_tree interface edge_port enable <interface_name>
# This should check the mode attribute in the STP global table.
# If the mode is PVST, it should not allow configuring edge_port.


@spanning_tree_interface_edge_port.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_edge_port_enable(_db, interface_name):
    """Enable STP edge_port for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Check if STP is enabled globally
    check_if_global_stp_enabled(db, ctx)

    # Get the global STP mode
    current_mode = get_global_stp_mode(db)

    # Ensure mode is MSTP, otherwise fail
    if current_mode == "pvst":
        ctx.fail("edge_port configuration is not supported in PVST mode. This command is only allowed in MSTP mode.")

    # Validate the interface
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)

    # Enable edge_port for the interface
    db.mod_entry('STP_PORT', interface_name, {'edge_port': 'true'})

    click.echo(f"edge_port enabled on {interface_name} in MSTP mode.")


# config spanning_tree interface edge_port disable <interface_name>
# MST CONFIGURATION IN THE STP_PORT TABLE
# It should the mode attribute in the STP global table
# If the mode is PVST, then it should tell that the mode if PVST, and this cannot be done.


@spanning_tree_interface_edge_port.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_edge_port_disable(_db, interface_name):
    """Disable STP edge_port for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'edge_port': 'false'})


# STP interface root uplink_fast
# config spanning_tree interface uplink_fast
# Only for PVST
# It should also check if the mode is PVST, else not configure
@spanning_tree_interface.group('uplink_fast')
@clicommon.pass_db
def spanning_tree_interface_uplink_fast(_db):
    """Configure STP uplink fast for interface"""
    pass


# config spanning_tree interface uplink_fast enable <interface_name>
# Not for MST
@spanning_tree_interface_uplink_fast.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_uplink_fast_enable(_db, interface_name):
    """Enable STP uplink fast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Uplink fast is supported only for PVST mode")
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'uplink_fast': 'true'})


# config spanning_tree interface uplink_fast disable <interface_name>
# Not for MST
@spanning_tree_interface_uplink_fast.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_uplink_fast_disable(_db, interface_name):
    """Disable STP uplink fast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)
    if current_mode == "mst":
        ctx.fail("Uplink fast is supported only for PVST mode")
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'uplink_fast': 'false'})


# config spanning_tree interface link_type
@spanning_tree_interface.group('link_type')
@clicommon.pass_db
def spanning_tree_interface_link_type(_db):
    """Configure STP link type for interface"""
    pass

# config spanning_tree interface link_type point-to-point <interface_name>


@spanning_tree_interface_link_type.command('point-to-point')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_link_type_point_to_point(_db, interface_name):
    """Configure STP link type as point-to-point for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'link_type': 'point-to-point'})


# config spanning_tree interface link_type shared <interface_name>
@spanning_tree_interface_link_type.command('shared')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_link_type_shared(_db, interface_name):
    """Configure STP link type as shared for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'link_type': 'shared'})


# config spanning_tree interface link_type auto <interface_name>
@spanning_tree_interface_link_type.command('auto')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_link_type_auto(_db, interface_name):
    """Configure STP link type as auto for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)
    if current_mode == "pvst":
        ctx.fail("Link type configuration is not supported in PVST mode")
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'link_type': 'auto'})


###############################################
# STP interface per VLAN commands implementation
###############################################

# config spanning_tree vlan interface
@spanning_tree_vlan.group('interface')
@clicommon.pass_db
def spanning_tree_vlan_interface(_db):
    """Configure STP parameters for interface per VLAN"""
    pass


# STP interface per vlan port priority
def is_valid_vlan_interface_priority(ctx, priority):
    if priority not in range(STP_INTERFACE_MIN_PRIORITY, STP_INTERFACE_MAX_PRIORITY + 1):
        ctx.fail("STP per vlan port priority must be in range 0-240")

# config spanning_tree vlan interface priority <Vlan> <interface_name> <value: 0-240>
@spanning_tree_vlan_interface.command('priority')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('priority', metavar='<0-240>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_interface_priority(_db, vid, interface_name, priority):
    """Configure STP per vlan port priority for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    vlan_name = 'Vlan{}'.format(vid)
    check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_vlan_exist_in_db(db, ctx, vid)
    is_interface_vlan_member(db, vlan_name, interface_name)
    is_valid_vlan_interface_priority(ctx, priority)
    vlan_interface = str(vlan_name) + "|" + interface_name
    db.mod_entry('STP_VLAN_PORT', vlan_interface, {'priority': priority})


# config spanning_tree vlan interface cost <Vlan> <interface_name> <value: 1-200000000>
@spanning_tree_vlan_interface.command('cost')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('cost', metavar='<1-200000000>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_interface_cost(_db, vid, interface_name, cost):
    """Configure STP per vlan path cost for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    vlan_name = 'Vlan{}'.format(vid)
    check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_vlan_exist_in_db(db, ctx, vid)
    is_interface_vlan_member(db, vlan_name, interface_name)
    is_valid_interface_path_cost(ctx, cost)
    vlan_interface = str(vlan_name) + "|" + interface_name
    db.mod_entry('STP_VLAN_PORT', vlan_interface, {'path_cost': cost})


# INTERFACE-LEVEL COMMANDS
# Command: config spanning_tree interface {enable} <ifname>
# Configure an interface for MSTP.


@spanning_tree_interface.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_enable(_db, interface_name):
    """Enable STP for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Check and display the current STP mode
    stp_global_entry = db.get_entry('STP_GLOBAL', 'GLOBAL')
    current_mode = stp_global_entry.get('mode', 'none')
    click.echo(f"Current STP mode: {current_mode}")
    if current_mode == "none":
        ctx.fail("Global STP is not enabled - first configure STP mode")

    check_if_global_stp_enabled(db, ctx)
    if is_stp_enabled_for_interface(db, interface_name):
        ctx.fail(f"STP is already enabled for {interface_name}")
    check_if_interface_is_valid(ctx, db, interface_name)

    # Set the common attributes
    fvs = {
        'enabled': 'true',
        'root_guard': 'false',
        'bpdu_guard': 'false',
        'bpdu_guard_do_disable': 'false'
    }

    # Add mode-specific attributes
    if current_mode == 'mstp':
        fvs.update({
            'edge_port': 'false',
            'link_type': 'auto',
            'portfast': 'false',
            'uplink_fast': 'false'
        })
    elif current_mode == 'pvst':
        fvs.update({
            'portfast': 'false',
            'uplink_fast': 'false'
        })
    else:
        click.echo("No STP mode selected. Please select a mode first.")
        return

    fvs = {'enabled': 'true'}
    db.set_entry('STP_PORT', interface_name, fvs)
    click.echo(f"Mode {current_mode} is enabled for interface {interface_name}")


# Command: config spanning_tree interface {disable} <ifname>
# Configure an interface for MSTP.
@spanning_tree_interface.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_disable(_db, interface_name):
    """Disable STP for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Check and display the current STP mode
    stp_global_entry = db.get_entry('STP_GLOBAL', 'GLOBAL')
    current_mode = stp_global_entry.get('mode', 'none')
    click.echo(f"Current STP mode: {current_mode}")

    check_if_global_stp_enabled(db, ctx)
    check_if_interface_is_valid(ctx, db, interface_name)

    # Clear all entries for the interface except the disable attribute
    if current_mode in ['mstp', 'pvst']:
        db.set_entry('STP_PORT', interface_name, {'enabled': 'false'})
        click.echo(f"STP mode {current_mode} is disabled for {interface_name}")
    else:
        click.echo("No STP mode selected. Please select a mode first.")


# config spanning_tree interface edge_port {enable|disable} <ifname>
# This command allow enabling or disabling of edge port on an interface.
@spanning_tree_interface.command('edge_port')
@click.argument('state', metavar='<enable|disable>', required=True, type=click.Choice(['enable', 'disable']))
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def mstp_interface_edge_port(_db, state, interface_name):
    """Enable/Disable edge port on interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    current_mode = get_global_stp_mode(db)
    if current_mode != "mst":
        ctx.fail("edge_port is supported for MSTP only")
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'edge_port': 'true' if state == 'enable' else 'false'})


# config spanning_tree interface bpdu_guard {enable|disable} <ifname>
# STP interface bpdu guard
# config spanning_tree interface bpdu_guard

# STP interface bpdu guard
@spanning_tree_interface.group(name='bpdu-guard')
@clicommon.pass_db
def spanning_tree_interface_bpdu_guard(_db):
    """Configure STP bpdu guard for interface"""
    pass


@spanning_tree_interface_bpdu_guard.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('-s', '--shutdown', is_flag=True)
@clicommon.pass_db
def stp_interface_bpdu_guard_enable(_db, interface_name, shutdown):
    """Enable STP bpdu guard for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_interface_is_valid(ctx, db, interface_name)
    stp_mode = get_global_stp_mode(db)
    fvs = {'bpdu_guard': 'true'}
    if shutdown:
        fvs['bpdu_guard_do_disable'] = 'true'
    else:
        fvs['bpdu_guard_do_disable'] = 'false'

    if stp_mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif stp_mode == "mstp":
        fvs.update({'edge_port': 'false', 'link_type': 'auto'})

    db.mod_entry('STP_PORT', interface_name, fvs)


@spanning_tree_interface_bpdu_guard.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_bpdu_guard_disable(_db, interface_name):
    """Disable STP bpdu guard for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_interface_is_valid(ctx, db, interface_name)
    stp_mode = get_global_stp_mode(db)
    fvs = {'bpdu_guard': 'false', 'bpdu_guard_do_disable': 'false'}

    if stp_mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif stp_mode == "mstp":
        fvs.update({'edge_port': 'false', 'link_type': 'auto'})

    db.mod_entry('STP_PORT', interface_name, fvs)


# config spanning_tree interface root_guard {enable|disable} <ifname>
# This command allow enabling or disabling of root_guard on an interface.
# STP interface root guard
@spanning_tree_interface.group('root_guard')
@clicommon.pass_db
def spanning_tree_interface_root_guard(_db):
    """Configure STP root guard for interface"""
    pass


@spanning_tree_interface_root_guard.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_root_guard_enable(_db, interface_name):
    """Enable STP root guard for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_interface_is_valid(ctx, db, interface_name)

    stp_mode = get_global_stp_mode(db)
    fvs = {'root_guard': 'true'}

    # Add mode-specific attributes
    if stp_mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif stp_mode == "mstp":
        fvs.update({'edge_port': 'false', 'link_type': 'auto'})

    db.mod_entry('STP_PORT', interface_name, fvs)


@spanning_tree_interface.group('root-guard')
def spanning_tree_interface_root_guard():
    """Root guard subcommands under interface"""
    pass


@spanning_tree_interface_root_guard.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_root_guard_disable(_db, interface_name):
    """Disable STP root guard for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_interface_is_valid(ctx, db, interface_name)

    stp_mode = get_global_stp_mode(db)
    fvs = {'root_guard': 'false'}

    # Add mode-specific attributes
    if stp_mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif stp_mode == "mstp":
        fvs.update({'edge_port': 'false', 'link_type': 'auto'})

    db.mod_entry('STP_PORT', interface_name, fvs)


# config spanning_tree interface priority <ifname> <port_priority-value>
# Specify configuring the port level priority for root bridge in seconds.
# Default: 128, range 0-240
# STP interface priority
@spanning_tree_interface.command('priority')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('priority_value', metavar='<0-240>', required=True, type=int)
@clicommon.pass_db
def stp_interface_priority(_db, interface_name, priority_value):
    """Configure STP port priority for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Validate if STP is enabled globally
    check_if_global_stp_enabled(db, ctx)

    # Validate if STP is enabled for the given interface
    check_if_stp_enabled_for_interface(ctx, db, interface_name)

    # Ensure interface is valid
    check_if_interface_is_valid(ctx, db, interface_name)

    # Validate the priority range
    if priority_value < 0 or priority_value > 240:
        ctx.fail("STP interface priority must be in range 0-240")

    # Fetch STP mode (PVST or MSTP)
    stp_mode = get_global_stp_mode(db)

    # Constructing field values to be updated in STP_PORT table
    fvs = {'priority': str(priority_value)}

    if stp_mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif stp_mode == "mstp":
        fvs.update({'edge_port': 'false', 'link_type': 'auto'})

    # Update the database entry
    db.mod_entry('STP_PORT', interface_name, fvs)


# config spanning_tree interface cost <ifname> <cost-value>

# Specify configuring the port level priority for root bridge in seconds.
# Default: 0, range 1-200000000
# STP interface port cost
STP_INTERFACE_MIN_COST = 1
STP_INTERFACE_MAX_COST = 200000000
STP_INTERFACE_DEFAULT_COST = 0


def is_valid_interface_cost(ctx, cost):
    """Validate if the provided cost is within the valid range"""
    if cost < STP_INTERFACE_MIN_COST or cost > STP_INTERFACE_MAX_COST:
        ctx.fail("STP interface path cost must be in range 1-200000000")


# config spanning_tree interface cost <ifname> <cost-value>
@spanning_tree_interface.command('cost')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('cost', metavar='<1-200000000>', required=True, type=int)
@clicommon.pass_db
def stp_interface_cost(_db, interface_name, cost):
    """Configure STP port cost for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    check_if_global_stp_enabled(db, ctx)
    check_if_interface_is_valid(ctx, db, interface_name)
    is_valid_interface_cost(ctx, cost)

    stp_intf_entry = db.get_entry('STP_PORT', interface_name)
    mode = get_global_stp_mode(db)

    fvs = {'path_cost': cost}

    # Add additional attributes based on STP mode
    if mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif mode == "mst":
        fvs.update({'edge_port': 'false', 'link_type': 'auto'})

    if len(stp_intf_entry) == 0:
        db.set_entry('STP_PORT', interface_name, fvs)
    else:
        db.mod_entry('STP_PORT', interface_name, {'path_cost': cost})


# config spanning_tree interface link-type {P2P|Shared-Lan|Auto} <ifname>
# Specify configuring the interface at different link types.
# Default : Auto
# STP interface link-type
@spanning_tree_interface.group('link-type')
@clicommon.pass_db
def spanning_tree_interface_link_type(_db):
    """Configure STP link type for interface"""
    pass


@spanning_tree_interface_link_type.command('set')
@click.argument(
    'link_type',
    metavar='<P2P|Shared-Lan|Auto>',
    required=True,
    type=click.Choice(["P2P", "Shared-Lan", "Auto"], case_sensitive=False)
)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_link_type_set(_db, link_type, interface_name):
    """Configure STP link type for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Ensure STP is enabled for the interface
    check_if_stp_enabled_for_interface(ctx, db, interface_name)

    # Validate interface
    check_if_interface_is_valid(ctx, db, interface_name)

    # Determine STP mode
    stp_mode = get_global_stp_mode(db)

    # Map link type options
    link_type_mapping = {
        "P2P": "p2p",
        "Shared-Lan": "shared",
        "Auto": "auto"
    }

    # Set appropriate link type
    fvs = {'link_type': link_type_mapping[link_type]}

    # Add PVST or MST-specific attributes
    if stp_mode == "pvst":
        fvs.update({'portfast': 'false', 'uplink_fast': 'false'})
    elif stp_mode == "mst":
        fvs.update({'edge_port': 'false'})

    db.mod_entry('STP_PORT', interface_name, fvs)


# INSTANCE INTERFACE LEVEL COMMANDS

# first instance-interface command
# config spanning_tree mst instance <instance-id> interface <ifname> priority <priority-value>

# Configure priority of an interface for an instance.
# priority-value: Default: 128, range: 0-240
# Supported Instances : 64

@mst.group('instance')
def mst_instance():
    """Configure MSTP instance settings"""
    pass


@mst_instance.group('interface')
def mst_instance_interface():
    """Configure MSTP instance interface settings"""
    pass


@mst_instance_interface.command('priority')
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('priority', metavar='<0-240>', required=True, type=int)
@clicommon.pass_db
def mst_instance_interface_priority(_db, instance_id, interface_name, priority):
    """Configure priority of an interface for an MST instance"""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Validate instance_id
    if instance_id < 0 or instance_id >= MST_MAX_INSTANCES:
        ctx.fail(f"Instance ID must be in range 0-{MST_MAX_INSTANCES-1}")

    # Validate priority value
    if priority < MST_MIN_PORT_PRIORITY or priority > MST_MAX_PORT_PRIORITY:
        ctx.fail(f"Priority value must be in range {MST_MIN_PORT_PRIORITY}-{MST_MAX_PORT_PRIORITY}")

    # Validate if the interface is valid
    check_if_interface_is_valid(ctx, db, interface_name)

    # Construct the key and field-value dictionary
    mst_instance_interface_key = f"MST_INSTANCE|{instance_id}|{interface_name}"
    fvs = {'priority': str(priority)}

    # Update the database entry
    db.mod_entry('STP_MST_PORT', mst_instance_interface_key, fvs)
    click.echo(f"Priority {priority} set for interface {interface_name} in MST instance {instance_id}")


# config spanning_tree mst instance <instance-id> interface <ifname> cost <cost-value>

# second instance-interface command
# Configure path cost of an interface for an instance.
# cost-value: Range: 1-200000000

@mst_instance_interface.command('cost')
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('cost', metavar='<1-200000000>', required=True, type=int)
@clicommon.pass_db
def mst_instance_interface_cost(_db, instance_id, interface_name, cost):
    """Configure path cost of an interface for an MST instance."""
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Validate MST mode
    mode = get_global_stp_mode(db)
    if mode != "mst":
        ctx.fail("Configuration not supported for PVST")

    # Validate instance_id range
    if not (0 <= instance_id < MST_MAX_INSTANCES):
        ctx.fail(f"Instance ID must be in range 0-{MST_MAX_INSTANCES - 1}")

    # Validate cost range
    if not (MST_MIN_PORT_PATH_COST <= cost <= MST_MAX_PORT_PATH_COST):
        ctx.fail(f"Path cost must be in range {MST_MIN_PORT_PATH_COST}-{MST_MAX_PORT_PATH_COST}")

    # Validate interface name
    check_if_interface_is_valid(ctx, db, interface_name)

    # Prepare key and value for database update
    mst_instance_interface_key = f"MST_INSTANCE|{instance_id}|{interface_name}"
    fvs = {'path_cost': str(cost)}

    # Update database entry
    db.mod_entry('STP_MST_PORT', mst_instance_interface_key, fvs)
    click.echo(f"Path cost {cost} set for interface {interface_name} in MST instance {instance_id}")


# Add under mst_instance group in stp.py
@mst_instance.command('priority')
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.argument('priority_value', metavar='<0-61440>', required=True, type=int)
@clicommon.pass_db
def mst_instance_priority(_db, instance_id, priority_value):
    """
    Configure bridge priority for an MST instance.
    """
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Validate instance_id range
    if not (0 <= instance_id < MST_MAX_INSTANCES):
        ctx.fail(f"Instance ID must be in range 0-{MST_MAX_INSTANCES - 1}")

    # Check if instance exists
    instance_key = f"MST_INSTANCE|{instance_id}"
    if not db.get_entry('STP_MST_INST', instance_key):
        ctx.fail(f"MST instance {instance_id} does not exist. Please create it first.")

    # Validate priority: must be multiple of 4096 and within range
    if priority_value % 4096 != 0 or not (MST_MIN_BRIDGE_PRIORITY <= priority_value <= MST_MAX_BRIDGE_PRIORITY):
        ctx.fail(
            f"Priority must be a multiple of 4096 and between "
            f"{MST_MIN_BRIDGE_PRIORITY}-{MST_MAX_BRIDGE_PRIORITY}."
        )

    # Update the instance priority
    db.mod_entry('STP_MST_INST', instance_key, {'bridge_priority': str(priority_value)})
    click.echo(f"Bridge priority set to {priority_value} for MST instance {instance_id}.")


@mst_instance.group('vlan')
def mst_instance_vlan():
    """VLAN to instance mapping for MST."""
    pass


@mst_instance_vlan.command('add')
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.argument('vlan_id', metavar='<vlan-id>', required=True, type=int)
@clicommon.pass_db
def mst_instance_vlan_add(_db, instance_id, vlan_id):
    """
    Map a VLAN to an MST instance.
    """
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Validate instance_id range
    if not (0 < instance_id < MST_MAX_INSTANCES):
        ctx.fail(f"Instance ID must be in range 0-{MST_MAX_INSTANCES - 1}")
    # Disallow VLAN configuration for MST instance 0
    if instance_id == 0:
        ctx.fail("VLAN configuration for MST instance 0 is not allowed.")

    # Check if instance exists
    instance_key = f"MST_INSTANCE|{instance_id}"
    if not db.get_entry('STP_MST_INST', instance_key):
        ctx.fail(f"MST instance {instance_id} does not exist. Please create it first.")

    # Validate VLAN ID range
    if not (1 <= vlan_id <= 4094):
        ctx.fail("VLAN ID must be in range 1-4094.")

    # Check if VLAN exists
    vlan_key = f"Vlan{vlan_id}"
    if not db.get_entry('VLAN', vlan_key):
        ctx.fail(f"VLAN {vlan_id} does not exist.")

    # Update VLAN list in MST instance
    instance_entry = db.get_entry('STP_MST_INST', instance_key)
    vlan_list = instance_entry.get('vlan_list', "")
    vlans = set(vlan_list.split(',')) if vlan_list else set()

    if str(vlan_id) in vlans:
        ctx.fail(f"VLAN {vlan_id} is already mapped to MST instance {instance_id}.")

    vlans.add(str(vlan_id))
    updated_vlan_list = ",".join(sorted(vlans, key=int))
    db.mod_entry('STP_MST_INST', instance_key, {'vlan_list': updated_vlan_list})

    click.echo(f"VLAN {vlan_id} added to MST instance {instance_id}.")


mst.add_command(mst_instance, "instance")
spanning_tree.add_command(mst, "mst")


@mst_instance_vlan.command('del')
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.argument('vlan_id', metavar='<vlan-id>', required=True, type=int)
@clicommon.pass_db
def mst_instance_vlan_del(_db, instance_id, vlan_id):
    """
    Remove a VLAN from an MST instance.
    """
    ctx = click.get_current_context()
    db = _db.cfgdb

    # Validate instance_id range
    if not (0 <= instance_id < MST_MAX_INSTANCES):
        ctx.fail(f"Instance ID must be in range 0-{MST_MAX_INSTANCES - 1}")

    # Disallow VLAN delete from MST instance 0
    if instance_id == 0:
        ctx.fail("VLAN delete from MST instance 0 is not allowed.")

    # Check if instance exists
    instance_key = f"MST_INSTANCE|{instance_id}"
    instance_entry = db.get_entry('STP_MST_INST', instance_key)
    if not instance_entry:
        ctx.fail(f"MST instance {instance_id} does not exist.")

    vlan_list = instance_entry.get('vlan_list', "")
    vlans = set(vlan_list.split(',')) if vlan_list else set()

    if str(vlan_id) not in vlans:
        ctx.fail(f"VLAN {vlan_id} is not mapped to MST instance {instance_id}.")

    vlans.remove(str(vlan_id))
    updated_vlan_list = ",".join(sorted(vlans, key=int))
    db.mod_entry('STP_MST_INST', instance_key, {'vlan_list': updated_vlan_list})

    click.echo(f"VLAN {vlan_id} removed from MST instance {instance_id}.")
