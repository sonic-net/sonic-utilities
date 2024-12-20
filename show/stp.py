import re
import click
# import subprocess
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector


##############################################################################
# 'spanning_tree' group ("show spanning_tree ...")
###############################################################################
#   STP show commands:-
#   show spanning_tree
#   show spanning_tree vlan <vlanid>
#   show spanning_tree vlan interface <vlanid> <ifname>
#   show spanning_tree bpdu_guard
#   show spanning_tree statistics
#   show spanning_tree statistics vlan <vlanid>
#
###############################################################################
g_stp_vlanid = 0
#
# Utility API's
#


def is_stp_docker_running():
    return True
#    running_docker = subprocess.check_output('docker ps', shell=True)
#    if running_docker.find("docker-stp".encode()) == -1:
#        return False
#    else:
#        return True


def connect_to_cfg_db():
    config_db = ConfigDBConnector()
    config_db.connect()
    return config_db


def connect_to_appl_db():
    appl_db = SonicV2Connector(host="127.0.0.1")
    appl_db.connect(appl_db.APPL_DB)
    return appl_db


# Redis  DB only supports limiter pattern search wildcards.
# check https://redis.io/commands/KEYS before using this api
# Redis-db uses glob-style patterns not regex
def stp_get_key_from_pattern(db_connect, db, pattern):
    keys = db_connect.keys(db, pattern)
    if keys:
        return keys[0]
    else:
        return None


# get_all doesnt accept regex patterns, it requires exact key
def stp_get_all_from_pattern(db_connect, db, pattern):
    key = stp_get_key_from_pattern(db_connect, db, pattern)
    if key:
        entry = db_connect.get_all(db, key)
        return entry


def stp_is_port_fast_enabled(ifname):
    app_db_entry = stp_get_all_from_pattern(
        g_stp_appl_db, g_stp_appl_db.APPL_DB, "*STP_PORT_TABLE:{}".format(ifname))
    if (not app_db_entry or not ('port_fast' in app_db_entry) or app_db_entry['port_fast'] == 'no'):
        return False
    return True


def stp_is_uplink_fast_enabled(ifname):
    entry = g_stp_cfg_db.get_entry("STP_PORT", ifname)
    if (entry and ('uplink_fast' in entry) and entry['uplink_fast'] == 'true'):
        return True
    return False


def stp_get_entry_from_vlan_tb(db, vlanid):
    entry = stp_get_all_from_pattern(db, db.APPL_DB, "*STP_VLAN_TABLE:Vlan{}".format(vlanid))
    if not entry:
        return entry

    if 'bridge_id' not in entry:
        entry['bridge_id'] = 'NA'
    if 'max_age' not in entry:
        entry['max_age'] = '0'
    if 'hello_time' not in entry:
        entry['hello_time'] = '0'
    if 'forward_delay' not in entry:
        entry['forward_delay'] = '0'
    if 'hold_time' not in entry:
        entry['hold_time'] = '0'
    if 'last_topology_change' not in entry:
        entry['last_topology_change'] = '0'
    if 'topology_change_count' not in entry:
        entry['topology_change_count'] = '0'
    if 'root_bridge_id' not in entry:
        entry['root_bridge_id'] = 'NA'
    if 'root_path_cost' not in entry:
        entry['root_path_cost'] = '0'
    if 'desig_bridge_id' not in entry:
        entry['desig_bridge_id'] = 'NA'
    if 'root_port' not in entry:
        entry['root_port'] = 'NA'
    if 'root_max_age' not in entry:
        entry['root_max_age'] = '0'
    if 'root_hello_time' not in entry:
        entry['root_hello_time'] = '0'
    if 'root_forward_delay' not in entry:
        entry['root_forward_delay'] = '0'
    if 'stp_instance' not in entry:
        entry['stp_instance'] = '65535'

    return entry


def stp_get_entry_from_vlan_intf_tb(db, vlanid, ifname):
    entry = stp_get_all_from_pattern(db, db.APPL_DB, "*STP_VLAN_PORT_TABLE:Vlan{}:{}".format(vlanid, ifname))
    if not entry:
        return entry

    if 'port_num' not in entry:
        entry['port_num'] = 'NA'
    if 'priority' not in entry:
        entry['priority'] = '0'
    if 'path_cost' not in entry:
        entry['path_cost'] = '0'
    if 'root_guard' not in entry:
        entry['root_guard'] = 'NA'
    if 'bpdu_guard' not in entry:
        entry['bpdu_guard'] = 'NA'
    if 'port_state' not in entry:
        entry['port_state'] = 'NA'
    if 'desig_cost' not in entry:
        entry['desig_cost'] = '0'
    if 'desig_root' not in entry:
        entry['desig_root'] = 'NA'
    if 'desig_bridge' not in entry:
        entry['desig_bridge'] = 'NA'

    return entry


#
# This group houses Spanning_tree commands and subgroups
@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def spanning_tree(ctx):
    """Show spanning_tree commands"""
    global g_stp_appl_db
    global g_stp_cfg_db

    if not is_stp_docker_running():
        ctx.fail("STP docker is not running")

    g_stp_appl_db = connect_to_appl_db()
    g_stp_cfg_db = connect_to_cfg_db()

    global_cfg = g_stp_cfg_db.get_entry("STP", "GLOBAL")
    if not global_cfg:
        click.echo("Spanning-tree is not configured")
        return

    global g_stp_mode
    if 'pvst' == global_cfg['mode']:
        g_stp_mode = 'PVST'

    if ctx.invoked_subcommand is None:
        keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_VLAN_TABLE:Vlan*")
        if not keys:
            return
        vlan_list = []
        for key in keys:
            result = re.search('.STP_VLAN_TABLE:Vlan(.*)', key)
            vlanid = result.group(1)
            vlan_list.append(int(vlanid))
        vlan_list.sort()
        for vlanid in vlan_list:
            ctx.invoke(show_stp_vlan, vlanid=vlanid)


@spanning_tree.group('vlan', cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.argument('vlanid', metavar='<vlanid>', required=True, type=int)
@click.pass_context
def show_stp_vlan(ctx, vlanid):
    """Show spanning_tree vlan <vlanid> information"""
    global g_stp_vlanid
    g_stp_vlanid = vlanid

    vlan_tb_entry = stp_get_entry_from_vlan_tb(g_stp_appl_db, g_stp_vlanid)
    if not vlan_tb_entry:
        return

    global g_stp_mode
    if g_stp_mode:
        click.echo("Spanning-tree Mode: {}".format(g_stp_mode))
        # reset so we dont print again
        g_stp_mode = ''

    click.echo("")
    click.echo("VLAN {} - STP instance {}".format(g_stp_vlanid, vlan_tb_entry['stp_instance']))
    click.echo("--------------------------------------------------------------------")
    click.echo("STP Bridge Parameters:")

    click.echo("{:17}{:7}{:7}{:7}{:6}{:13}{}".format(
        "Bridge", "Bridge", "Bridge", "Bridge", "Hold", "LastTopology", "Topology"))
    click.echo("{:17}{:7}{:7}{:7}{:6}{:13}{}".format(
        "Identifier", "MaxAge", "Hello", "FwdDly", "Time", "Change", "Change"))
    click.echo("{:17}{:7}{:7}{:7}{:6}{:13}{}".format("hex", "sec", "sec", "sec", "sec", "sec", "cnt"))
    click.echo("{:17}{:7}{:7}{:7}{:6}{:13}{}".format(
               vlan_tb_entry['bridge_id'],
               vlan_tb_entry['max_age'],
               vlan_tb_entry['hello_time'],
               vlan_tb_entry['forward_delay'],
               vlan_tb_entry['hold_time'],
               vlan_tb_entry['last_topology_change'],
               vlan_tb_entry['topology_change_count']))

    click.echo("")
    click.echo("{:17}{:10}{:18}{:19}{:4}{:4}{}".format(
        "RootBridge", "RootPath", "DesignatedBridge", "RootPort", "Max", "Hel", "Fwd"))
    click.echo("{:17}{:10}{:18}{:19}{:4}{:4}{}".format("Identifier", "Cost", "Identifier", "", "Age", "lo", "Dly"))
    click.echo("{:17}{:10}{:18}{:19}{:4}{:4}{}".format("hex", "", "hex", "", "sec", "sec", "sec"))
    click.echo("{:17}{:10}{:18}{:19}{:4}{:4}{}".format(
               vlan_tb_entry['root_bridge_id'],
               vlan_tb_entry['root_path_cost'],
               vlan_tb_entry['desig_bridge_id'],
               vlan_tb_entry['root_port'],
               vlan_tb_entry['root_max_age'],
               vlan_tb_entry['root_hello_time'],
               vlan_tb_entry['root_forward_delay']))

    click.echo("")
    click.echo("STP Port Parameters:")
    click.echo("{:17}{:5}{:10}{:5}{:7}{:14}{:12}{:17}{}".format(
        "Port", "Prio", "Path", "Port", "Uplink", "State", "Designated", "Designated", "Designated"))
    click.echo("{:17}{:5}{:10}{:5}{:7}{:14}{:12}{:17}{}".format(
        "Name", "rity", "Cost", "Fast", "Fast", "", "Cost", "Root", "Bridge"))
    if ctx.invoked_subcommand is None:
        keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_VLAN_PORT_TABLE:Vlan{}:*".format(vlanid))
        if not keys:
            return
        intf_list = []
        for key in keys:
            result = re.search('.STP_VLAN_PORT_TABLE:Vlan{}:(.*)'.format(vlanid), key)
            ifname = result.group(1)
            intf_list.append(ifname)
        eth_list = [ifname[len("Ethernet"):] for ifname in intf_list if ifname.startswith("Ethernet")]
        po_list = [ifname[len("PortChannel"):] for ifname in intf_list if ifname.startswith("PortChannel")]

        eth_list.sort()
        po_list.sort()
        for port_num in eth_list:
            ctx.invoke(show_stp_interface, ifname="Ethernet"+str(port_num))
        for port_num in po_list:
            ctx.invoke(show_stp_interface, ifname="PortChannel"+port_num)


@show_stp_vlan.command('interface')
@click.argument('ifname', metavar='<interface_name>', required=True)
@click.pass_context
def show_stp_interface(ctx, ifname):
    """Show spanning_tree vlan interface <vlanid> <ifname> information"""

    vlan_intf_tb_entry = stp_get_entry_from_vlan_intf_tb(g_stp_appl_db, g_stp_vlanid, ifname)
    if not vlan_intf_tb_entry:
        return

    click.echo("{:17}{:5}{:10}{:5}{:7}{:14}{:12}{:17}{}".format(
        ifname,
        vlan_intf_tb_entry['priority'],
        vlan_intf_tb_entry['path_cost'],
        'Y' if (stp_is_port_fast_enabled(ifname)) else 'N',
        'Y' if (stp_is_uplink_fast_enabled(ifname)) else 'N',
        vlan_intf_tb_entry['port_state'],
        vlan_intf_tb_entry['desig_cost'],
        vlan_intf_tb_entry['desig_root'],
        vlan_intf_tb_entry['desig_bridge']
        ))


@spanning_tree.command('bpdu_guard')
@click.pass_context
def show_stp_bpdu_guard(ctx):
    """Show spanning_tree bpdu_guard"""

    print_header = 1
    ifname_all = g_stp_cfg_db.get_keys("STP_PORT")
    for ifname in ifname_all:
        cfg_entry = g_stp_cfg_db.get_entry("STP_PORT", ifname)
        if cfg_entry['bpdu_guard'] == 'true' and cfg_entry['enabled'] == 'true':
            if print_header:
                click.echo("{:17}{:13}{}".format("PortNum", "Shutdown", "Port Shut"))
                click.echo("{:17}{:13}{}".format("", "Configured", "due to BPDU guard"))
                click.echo("-------------------------------------------")
                print_header = 0

            if cfg_entry['bpdu_guard_do_disable'] == 'true':
                disabled = 'No'
                keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_PORT_TABLE:{}".format(ifname))
                # only 1 key per ifname is expected in BPDU_GUARD_TABLE.
                if keys:
                    appdb_entry = g_stp_appl_db.get_all(g_stp_appl_db.APPL_DB, keys[0])
                    if appdb_entry and 'bpdu_guard_shutdown' in appdb_entry:
                        if appdb_entry['bpdu_guard_shutdown'] == 'yes':
                            disabled = 'Yes'
                click.echo("{:17}{:13}{}".format(ifname, "Yes", disabled))
            else:
                click.echo("{:17}{:13}{}".format(ifname, "No", "NA"))


@spanning_tree.command('root_guard')
@click.pass_context
def show_stp_root_guard(ctx):
    """Show spanning_tree root_guard"""

    print_header = 1
    ifname_all = g_stp_cfg_db.get_keys("STP_PORT")
    for ifname in ifname_all:
        entry = g_stp_cfg_db.get_entry("STP_PORT", ifname)
        if entry['root_guard'] == 'true' and entry['enabled'] == 'true':
            if print_header:
                global_entry = g_stp_cfg_db.get_entry("STP", "GLOBAL")
                click.echo("Root guard timeout: {} secs".format(global_entry['rootguard_timeout']))
                click.echo("")
                click.echo("{:17}{:7}{}".format("Port", "VLAN", "Current State"))
                click.echo("-------------------------------------------")
                print_header = 0

            state = ''
            vlanid = ''
            keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_VLAN_PORT_TABLE:*:{}".format(ifname))
            if keys:
                for key in keys:
                    entry = g_stp_appl_db.get_all(g_stp_appl_db.APPL_DB, key)
                    if entry and 'root_guard_timer' in entry:
                        if entry['root_guard_timer'] == '0':
                            state = 'Consistent state'
                        else:
                            state = 'Inconsistent state ({} seconds left on timer)'.format(entry['root_guard_timer'])

                        vlanid = re.search(':Vlan(.*):', key)
                        if vlanid:
                            click.echo("{:17}{:7}{}".format(ifname, vlanid.group(1), state))
                        else:
                            click.echo("{:17}{:7}{}".format(ifname, vlanid, state))


@spanning_tree.group('statistics', cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def show_stp_statistics(ctx):
    """Show spanning_tree statistics"""

    if ctx.invoked_subcommand is None:
        keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_VLAN_TABLE:Vlan*")
        if not keys:
            return

        vlan_list = []
        for key in keys:
            result = re.search('.STP_VLAN_TABLE:Vlan(.*)', key)
            vlanid = result.group(1)
            vlan_list.append(int(vlanid))
        vlan_list.sort()
        for vlanid in vlan_list:
            ctx.invoke(show_stp_vlan_statistics, vlanid=vlanid)


@show_stp_statistics.command('vlan')
@click.argument('vlanid', metavar='<vlanid>', required=True, type=int)
@click.pass_context
def show_stp_vlan_statistics(ctx, vlanid):
    """Show spanning_tree statistics vlan"""

    stp_inst_entry = stp_get_all_from_pattern(
        g_stp_appl_db, g_stp_appl_db.APPL_DB, "*STP_VLAN_TABLE:Vlan{}".format(vlanid))
    if not stp_inst_entry:
        return

    click.echo("VLAN {} - STP instance {}".format(vlanid, stp_inst_entry['stp_instance']))
    click.echo("--------------------------------------------------------------------")
    click.echo("{:17}{:15}{:15}{:15}{}".format("PortNum", "BPDU Tx", "BPDU Rx", "TCN Tx", "TCN Rx"))
    keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_VLAN_PORT_TABLE:Vlan{}:*".format(vlanid))
    if keys:
        for key in keys:
            result = re.search('.STP_VLAN_PORT_TABLE:Vlan(.*):(.*)', key)
            ifname = result.group(2)
            entry = g_stp_appl_db.get_all(g_stp_appl_db.APPL_DB, key)
            if entry:
                if 'bpdu_sent' not in entry:
                    entry['bpdu_sent'] = '-'
                if 'bpdu_received' not in entry:
                    entry['bpdu_received'] = '-'
                if 'tc_sent' not in entry:
                    entry['tc_sent'] = '-'
                if 'tc_received' not in entry:
                    entry['tc_received'] = '-'

                click.echo("{:17}{:15}{:15}{:15}{}".format(
                    ifname, entry['bpdu_sent'], entry['bpdu_received'], entry['tc_sent'], entry['tc_received']))
