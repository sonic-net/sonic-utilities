
#
# 'spanning-tree' group ('config  spanning-tree ...')
#

import click
import utilities_common.cli as clicommon
from natsort import natsorted
import logging

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
    if mode:
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


@click.group()
@clicommon.pass_db
def spanning_tree(_db):
    """STP command line"""
    pass


###############################################
# STP Global commands implementation
###############################################

# cmd: STP enable
@spanning_tree.command('enable')
@click.argument('mode', metavar='<pvst>', required=True, type=click.Choice(["pvst"]))
@clicommon.pass_db
def spanning_tree_enable(_db, mode):
    """enable STP """
    ctx = click.get_current_context()
    db = _db.cfgdb
    if mode == "pvst" and get_global_stp_mode(db) == "pvst":
        ctx.fail("PVST is already configured")
    fvs = {'mode': mode,
           'rootguard_timeout': STP_DEFAULT_ROOT_GUARD_TIMEOUT,
           'forward_delay': STP_DEFAULT_FORWARD_DELAY,
           'hello_time': STP_DEFAULT_HELLO_INTERVAL,
           'max_age': STP_DEFAULT_MAX_AGE,
           'priority': STP_DEFAULT_BRIDGE_PRIORITY
           }
    db.set_entry('STP', "GLOBAL", fvs)
    # Enable STP for VLAN by default
    enable_stp_for_interfaces(db)
    enable_stp_for_vlans(db)


# cmd: STP disable
@spanning_tree.command('disable')
@click.argument('mode', metavar='<pvst>', required=True, type=click.Choice(["pvst"]))
@clicommon.pass_db
def stp_disable(_db, mode):
    """disable STP """
    db = _db.cfgdb
    db.set_entry('STP', "GLOBAL", None)
    # Disable STP for all VLANs and interfaces
    db.delete_table('STP_VLAN')
    db.delete_table('STP_PORT')
    db.delete_table('STP_VLAN_PORT')
    if get_global_stp_mode(db) == "pvst":
        print("Error PVST disable failed")


# cmd: STP global root guard timeout
@spanning_tree.command('root_guard_timeout')
@click.argument('root_guard_timeout', metavar='<5-600 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_root_guard_timeout(_db, root_guard_timeout):
    """Configure STP global root guard timeout value"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    is_valid_root_guard_timeout(ctx, root_guard_timeout)
    db.mod_entry('STP', "GLOBAL", {'rootguard_timeout': root_guard_timeout})


# cmd: STP global forward delay
@spanning_tree.command('forward_delay')
@click.argument('forward_delay', metavar='<4-30 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_forward_delay(_db, forward_delay):
    """Configure STP global forward delay"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    is_valid_forward_delay(ctx, forward_delay)
    is_valid_stp_global_parameters(ctx, db, "forward_delay", forward_delay)
    update_stp_vlan_parameter(ctx, db, "forward_delay", forward_delay)
    db.mod_entry('STP', "GLOBAL", {'forward_delay': forward_delay})


# cmd: STP global hello interval
@spanning_tree.command('hello')
@click.argument('hello_interval', metavar='<1-10 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_hello_interval(_db, hello_interval):
    """Configure STP global hello interval"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    is_valid_hello_interval(ctx, hello_interval)
    is_valid_stp_global_parameters(ctx, db, "hello_time", hello_interval)
    update_stp_vlan_parameter(ctx, db, "hello_time", hello_interval)
    db.mod_entry('STP', "GLOBAL", {'hello_time': hello_interval})


# cmd: STP global max age
@spanning_tree.command('max_age')
@click.argument('max_age', metavar='<6-40 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_global_max_age(_db, max_age):
    """Configure STP global max_age"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    is_valid_max_age(ctx, max_age)
    is_valid_stp_global_parameters(ctx, db, "max_age", max_age)
    update_stp_vlan_parameter(ctx, db, "max_age", max_age)
    db.mod_entry('STP', "GLOBAL", {'max_age': max_age})


# cmd: STP global bridge priority
@spanning_tree.command('priority')
@click.argument('priority', metavar='<0-61440>', required=True, type=int)
@clicommon.pass_db
def stp_global_priority(_db, priority):
    """Configure STP global bridge priority"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    is_valid_bridge_priority(ctx, priority)
    update_stp_vlan_parameter(ctx, db, "priority", priority)
    db.mod_entry('STP', "GLOBAL", {'priority': priority})


###############################################
# STP VLAN commands implementation
###############################################
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


@spanning_tree_vlan.command('enable')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_enable(_db, vid):
    """Enable STP for a VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_vlan_exist_in_db(db, ctx, vid)
    vlan_name = 'Vlan{}'.format(vid)
    if is_stp_enabled_for_vlan(db, vlan_name):
        ctx.fail("STP is already enabled for " + vlan_name)
    if get_stp_enabled_vlan_count(db) >= get_max_stp_instances():
        ctx.fail("Exceeded maximum STP configurable VLAN instances")
    check_if_global_stp_enabled(db, ctx)
    # when enabled for first time, create VLAN entry with
    # global values - else update only VLAN STP state
    stp_vlan_entry = db.get_entry('STP_VLAN', vlan_name)
    if len(stp_vlan_entry) == 0:
        fvs = {'enabled': 'true',
               'forward_delay': get_global_stp_forward_delay(db),
               'hello_time': get_global_stp_hello_time(db),
               'max_age': get_global_stp_max_age(db),
               'priority': get_global_stp_priority(db)
               }
        db.set_entry('STP_VLAN', vlan_name, fvs)
    else:
        db.mod_entry('STP_VLAN', vlan_name, {'enabled': 'true'})
    # Refresh stp_vlan_intf entry for vlan
    for vlan, intf in db.get_table('STP_VLAN_PORT'):
        if vlan == vlan_name:
            vlan_intf_key = "{}|{}".format(vlan_name, intf)
            vlan_intf_entry = db.get_entry('STP_VLAN_PORT', vlan_intf_key)
            db.mod_entry('STP_VLAN_PORT', vlan_intf_key, vlan_intf_entry)


@spanning_tree_vlan.command('disable')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_disable(_db, vid):
    """Disable STP for a VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_vlan_exist_in_db(db, ctx, vid)
    vlan_name = 'Vlan{}'.format(vid)
    db.mod_entry('STP_VLAN', vlan_name, {'enabled': 'false'})


@spanning_tree_vlan.command('forward_delay')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('forward_delay', metavar='<4-30 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_forward_delay(_db, vid, forward_delay):
    """Configure STP forward delay for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_vlan_exist_in_db(db, ctx, vid)
    vlan_name = 'Vlan{}'.format(vid)
    check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
    is_valid_forward_delay(ctx, forward_delay)
    is_valid_stp_vlan_parameters(ctx, db, vlan_name, "forward_delay", forward_delay)
    db.mod_entry('STP_VLAN', vlan_name, {'forward_delay': forward_delay})


@spanning_tree_vlan.command('hello')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('hello_interval', metavar='<1-10 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_hello_interval(_db, vid, hello_interval):
    """Configure STP hello interval for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_vlan_exist_in_db(db, ctx, vid)
    vlan_name = 'Vlan{}'.format(vid)
    check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
    is_valid_hello_interval(ctx, hello_interval)
    is_valid_stp_vlan_parameters(ctx, db, vlan_name, "hello_time", hello_interval)
    db.mod_entry('STP_VLAN', vlan_name, {'hello_time': hello_interval})


@spanning_tree_vlan.command('max_age')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('max_age', metavar='<6-40 seconds>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_max_age(_db, vid, max_age):
    """Configure STP max age for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_vlan_exist_in_db(db, ctx, vid)
    vlan_name = 'Vlan{}'.format(vid)
    check_if_stp_enabled_for_vlan(ctx, db, vlan_name)
    is_valid_max_age(ctx, max_age)
    is_valid_stp_vlan_parameters(ctx, db, vlan_name, "max_age", max_age)
    db.mod_entry('STP_VLAN', vlan_name, {'max_age': max_age})


@spanning_tree_vlan.command('priority')
@click.argument('vid', metavar='<Vlan>', required=True, type=int)
@click.argument('priority', metavar='<0-61440>', required=True, type=int)
@clicommon.pass_db
def stp_vlan_priority(_db, vid, priority):
    """Configure STP bridge priority for VLAN"""
    ctx = click.get_current_context()
    db = _db.cfgdb
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


@spanning_tree.group('interface')
@clicommon.pass_db
def spanning_tree_interface(_db):
    """Configure STP for interface"""
    pass


@spanning_tree_interface.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_enable(_db, interface_name):
    """Enable STP for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    if is_stp_enabled_for_interface(db, interface_name):
        ctx.fail("STP is already enabled for " + interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    stp_intf_entry = db.get_entry('STP_PORT', interface_name)
    if len(stp_intf_entry) == 0:
        fvs = {'enabled': 'true',
               'root_guard': 'false',
               'bpdu_guard': 'false',
               'bpdu_guard_do_disable': 'false',
               'portfast': 'false',
               'uplink_fast': 'false'}
        db.set_entry('STP_PORT', interface_name, fvs)
    else:
        db.mod_entry('STP_PORT', interface_name, {'enabled': 'true'})


@spanning_tree_interface.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_disable(_db, interface_name):
    """Disable STP for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_global_stp_enabled(db, ctx)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'enabled': 'false'})


# STP interface port priority
STP_INTERFACE_MIN_PRIORITY = 0
STP_INTERFACE_MAX_PRIORITY = 240
STP_INTERFACE_DEFAULT_PRIORITY = 128


def is_valid_interface_priority(ctx, intf_priority):
    if intf_priority not in range(STP_INTERFACE_MIN_PRIORITY, STP_INTERFACE_MAX_PRIORITY + 1):
        ctx.fail("STP interface priority must be in range 0-240")


@spanning_tree_interface.command('priority')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('priority', metavar='<0-240>', required=True, type=int)
@clicommon.pass_db
def stp_interface_priority(_db, interface_name, priority):
    """Configure STP port priority for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    is_valid_interface_priority(ctx, priority)
    curr_intf_proirty = db.get_entry('STP_PORT', interface_name).get('priority')
    db.mod_entry('STP_PORT', interface_name, {'priority': priority})
    # update interface priority in all stp_vlan_intf entries if entry exists
    for vlan, intf in db.get_table('STP_VLAN_PORT'):
        if intf == interface_name:
            vlan_intf_key = "{}|{}".format(vlan, interface_name)
            vlan_intf_entry = db.get_entry('STP_VLAN_PORT', vlan_intf_key)
            if len(vlan_intf_entry) != 0:
                vlan_intf_priority = vlan_intf_entry.get('priority')
                if curr_intf_proirty == vlan_intf_priority:
                    db.mod_entry('STP_VLAN_PORT', vlan_intf_key, {'priority': priority})
    # end


# STP interface port path cost
STP_INTERFACE_MIN_PATH_COST = 1
STP_INTERFACE_MAX_PATH_COST = 200000000


def is_valid_interface_path_cost(ctx, intf_path_cost):
    if intf_path_cost < STP_INTERFACE_MIN_PATH_COST or intf_path_cost > STP_INTERFACE_MAX_PATH_COST:
        ctx.fail("STP interface path cost must be in range 1-200000000")


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
    # end


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
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'root_guard': 'true'})


@spanning_tree_interface_root_guard.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_root_guard_disable(_db, interface_name):
    """Disable STP root guard for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'root_guard': 'false'})


# STP interface bpdu guard
@spanning_tree_interface.group('bpdu_guard')
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
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    if shutdown is True:
        bpdu_guard_do_disable = 'true'
    else:
        bpdu_guard_do_disable = 'false'
    fvs = {'bpdu_guard': 'true',
           'bpdu_guard_do_disable': bpdu_guard_do_disable}
    db.mod_entry('STP_PORT', interface_name, fvs)


@spanning_tree_interface_bpdu_guard.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_bpdu_guard_disable(_db, interface_name):
    """Disable STP bpdu guard for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'bpdu_guard': 'false'})


# STP interface portfast
@spanning_tree_interface.group('portfast')
@clicommon.pass_db
def spanning_tree_interface_portfast(_db):
    """Configure STP portfast for interface"""
    pass


@spanning_tree_interface_portfast.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_portfast_enable(_db, interface_name):
    """Enable STP portfast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'portfast': 'true'})


@spanning_tree_interface_portfast.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_portfast_disable(_db, interface_name):
    """Disable STP portfast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'portfast': 'false'})


# STP interface root uplink_fast
@spanning_tree_interface.group('uplink_fast')
@clicommon.pass_db
def spanning_tree_interface_uplink_fast(_db):
    """Configure STP uplink fast for interface"""
    pass


@spanning_tree_interface_uplink_fast.command('enable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_uplink_fast_enable(_db, interface_name):
    """Enable STP uplink fast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'uplink_fast': 'true'})


@spanning_tree_interface_uplink_fast.command('disable')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@clicommon.pass_db
def stp_interface_uplink_fast_disable(_db, interface_name):
    """Disable STP uplink fast for interface"""
    ctx = click.get_current_context()
    db = _db.cfgdb
    check_if_stp_enabled_for_interface(ctx, db, interface_name)
    check_if_interface_is_valid(ctx, db, interface_name)
    db.mod_entry('STP_PORT', interface_name, {'uplink_fast': 'false'})


###############################################
# STP interface per VLAN commands implementation
###############################################
@spanning_tree_vlan.group('interface')
@clicommon.pass_db
def spanning_tree_vlan_interface(_db):
    """Configure STP parameters for interface per VLAN"""
    pass


# STP interface per vlan port priority
def is_valid_vlan_interface_priority(ctx, priority):
    if priority not in range(STP_INTERFACE_MIN_PRIORITY, STP_INTERFACE_MAX_PRIORITY + 1):
        ctx.fail("STP per vlan port priority must be in range 0-240")


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


# Invoke main()
# if __name__ == '__main__':
#    spanning_tree()
