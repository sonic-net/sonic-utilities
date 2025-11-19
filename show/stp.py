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


# Redis DB only supports limiter pattern search wildcards.
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
    elif 'mst' == global_cfg['mode']:
        g_stp_mode = 'MSTP'

    if ctx.invoked_subcommand is None:
        # For MSTP mode, use new format
        if g_stp_mode == 'MSTP':
            ctx.invoke(show_mstp_summary)
        else:
            # For PVST mode, use existing format
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


def format_bridge_id(bridge_id_str):
    """Format bridge ID from hex string to the display format"""
    # Input is like "8000.80a2.3526.0c5e" or similar
    # Just return as-is if already formatted, otherwise format it
    if not bridge_id_str or bridge_id_str == 'NA':
        return 'NA'
    return bridge_id_str


def format_vlan_list(vlan_list_str):
    """Convert vlan mask string to readable vlan ranges"""
    if not vlan_list_str:
        return ""
   
    """Convert comma VLAN list to merged ranges. Example:
       '1,2,4,5,6,10,11,12,20' b'1-2,4-6,10-12,20'
    """

    # Fast conversion & sorting
    vlans = sorted({int(v) for v in vlan_list_str.split(",") if v.strip()})

    if not vlans:
        return ""

    ranges = []
    start = prev = vlans[0]

    for v in vlans[1:]:
        if v == prev + 1:
            prev = v
            continue

        # close range
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = v

    # close last range
    ranges.append(f"{start}-{prev}" if start != prev else str(start))

    return ",".join(ranges) 


def get_mst_global_info():
    """Get MST global configuration information"""
    mst_global = g_stp_cfg_db.get_entry("STP_MST", "GLOBAL")
    if not mst_global:
        mst_global = {}
    
    # Set defaults if not present
    if 'name' not in mst_global:
        mst_global['name'] = ''
    if 'revision' not in mst_global:
        mst_global['revision'] = '0'
    if 'max_hops' not in mst_global:
        mst_global['max_hops'] = '20'
    if 'max_age' not in mst_global:
        mst_global['max_age'] = '20'
    if 'hello_time' not in mst_global:
        mst_global['hello_time'] = '2'
    if 'forward_delay' not in mst_global:
        mst_global['forward_delay'] = '15'
    if 'hold_count' not in mst_global:
        mst_global['hold_count'] = '6'
    
    return mst_global


def get_mst_instance_entry(mst_id):
    """Get MST instance entry from application database"""
    entry = stp_get_all_from_pattern(g_stp_appl_db, g_stp_appl_db.APPL_DB, 
                                      "*STP_MST_INST_TABLE:{}".format(mst_id))
    if not entry:
        return None
    
    # Set defaults for missing fields
    if 'bridge_address' not in entry:
        entry['bridge_address'] = 'NA'
    if 'root_address' not in entry:
        entry['root_address'] = 'NA'
    if 'regional_root_address' not in entry:
        entry['regional_root_address'] = 'NA'
    if 'root_path_cost' not in entry:
        entry['root_path_cost'] = '0'
    if 'regional_root_cost' not in entry:
        entry['regional_root_cost'] = '0'
    if 'root_port' not in entry:
        entry['root_port'] = ''
    if 'remaining_hops' not in entry:
        entry['remaining_hops'] = '20'
    if 'root_hello_time' not in entry:
        entry['root_hello_time'] = '2'
    if 'root_forward_delay' not in entry:
        entry['root_forward_delay'] = '15'
    if 'root_max_age' not in entry:
        entry['root_max_age'] = '20'
    if 'hold_time' not in entry:
        entry['hold_time'] = '6'
    if 'vlan@' not in entry:
        entry['vlan@'] = ''
    if 'bridge_priority' not in entry:
        entry['bridge_priority'] = '32768'
    
    return entry


def get_mst_port_entry(mst_id, ifname):
    """Get MST port entry from application database"""
    entry = stp_get_all_from_pattern(g_stp_appl_db, g_stp_appl_db.APPL_DB,
                                      "*STP_MST_PORT_TABLE:{}:{}".format(mst_id, ifname))
    if not entry:
        return None
    
    # Set defaults for missing fields
    if 'port_number' not in entry:
        entry['port_number'] = 'NA'
    if 'priority' not in entry:
        entry['priority'] = '128'
    if 'path_cost' not in entry:
        entry['path_cost'] = '0'
    if 'port_state' not in entry:
        entry['port_state'] = 'NA'
    if 'role' not in entry:
        entry['role'] = 'NA'
    
    return entry


@spanning_tree.command('mstp')
@click.pass_context
def show_mstp_summary(ctx):
    """Show MSTP spanning tree information in detailed format"""
    
    # Print mode
    click.echo("Spanning-tree Mode: MSTP")
    
    # Get all MST instances
    keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_MST_INST_TABLE:*")
    if not keys:
        return
    
    mst_list = []
    for key in keys:
        result = re.search(r'STP_MST_INST_TABLE:(\d+)', key)
        if result:
            mst_id = int(result.group(1))
            mst_list.append(mst_id)
    
    mst_list.sort()
    
    # Display each MST instance
    for mst_id in mst_list:
        show_mst_instance_detail(mst_id)
    
    # Display MST region information at the end
    show_mst_region_info()


def show_mst_instance_detail(mst_id):
    """Display detailed information for a specific MST instance"""
    
    mst_entry = get_mst_instance_entry(mst_id)
    if not mst_entry:
        return
    
    mst_global = get_mst_global_info()
    
    # Print instance header
    vlan_str = mst_entry.get('vlan@', '')
    vlan_list = format_vlan_list(vlan_str)
    click.echo("")
    click.echo("#######  MST{:<8} Vlans mapped : {}".format(mst_id, vlan_list))
    
    # Bridge information
    bridge_addr = format_bridge_id(mst_entry['bridge_address'])
    bridge_priority = mst_entry.get('bridge_priority', '32768')
    click.echo("Bridge               Address {}".format(bridge_addr))
    
    # Root information
    root_addr = format_bridge_id(mst_entry['root_address'])
    click.echo("Root                 Address {}".format(root_addr))
    
    root_port = mst_entry.get('root_port', '')
    root_path_cost = mst_entry.get('root_path_cost', '0')
    
    if root_port:
        click.echo("                     Port     {}                  Path cost {}".format(
            root_port, root_path_cost))
    else:
        click.echo("                     Port     Root                  Path cost {}".format(
            root_path_cost))
    
    # Regional Root (for CIST)
    if mst_id == 0:
        reg_root_addr = format_bridge_id(mst_entry['regional_root_address'])
        click.echo("Regional Root        Address  {}".format(reg_root_addr))
        
        reg_root_cost = mst_entry.get('regional_root_cost', '0')
        rem_hops = mst_entry.get('remaining_hops', '20')
        click.echo("                     Internal cost {}                Rem hops {}".format(
            reg_root_cost, rem_hops))
        
        # Operational parameters
        hello_time = mst_entry.get('root_hello_time', mst_global['hello_time'])
        fwd_delay = mst_entry.get('root_forward_delay', mst_global['forward_delay'])
        max_age = mst_entry.get('root_max_age', mst_global['max_age'])
        hold_count = mst_entry.get('hold_time', mst_global['hold_count'])
        
        click.echo("Operational          Hello Time  {}, Forward Delay {}, Max Age {}, Txholdcount {}".format(
            hello_time, fwd_delay, max_age, hold_count))
        
        # Configured parameters
        click.echo("Configured           Hello Time  {}, Forward Delay {}, Max Age {}, Max Hops {}".format(
            mst_global['hello_time'], mst_global['forward_delay'], 
            mst_global['max_age'], mst_global['max_hops']))
    else:
        # For non-CIST instances
        rem_hops = mst_entry.get('remaining_hops', '20')
        click.echo("                     Port    Root            Path cost {}    Rem Hops {}".format(
            root_path_cost, rem_hops))
    
    click.echo("")
    
    # Port information table header
    click.echo("Interface           Role        State           Cost       Prio.Nbr    Type")
    click.echo("---------------    --------     ----------      -------    ---------   -----------")
    
    # Get all ports for this instance
    port_keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, 
                                    "*STP_MST_PORT_TABLE:{}:*".format(mst_id))
    if port_keys:
        intf_list = []
        for key in port_keys:
            result = re.search(r'STP_MST_PORT_TABLE:\d+:(.*)', key)
            if result:
                ifname = result.group(1)
                intf_list.append(ifname)
        
        # Sort interfaces: Ethernet first, then PortChannel
        eth_list = [ifname for ifname in intf_list if ifname.startswith("Ethernet")]
        po_list = [ifname for ifname in intf_list if ifname.startswith("PortChannel")]
        
        # Sort by numeric part
        eth_list.sort(key=lambda x: int(re.search(r'\d+', x).group()))
        po_list.sort(key=lambda x: int(re.search(r'\d+', x).group()))
        
        for ifname in eth_list + po_list:
            show_mst_port_info(mst_id, ifname)


def show_mst_port_info(mst_id, ifname):
    """Display port information for MST instance"""
    
    port_entry = get_mst_port_entry(mst_id, ifname)
    if not port_entry:
        return
    
    role = port_entry.get('role', 'UNKNOWN').upper()
    state = port_entry.get('port_state', 'UNKNOWN').upper()
    cost = port_entry.get('path_cost', '0')
    priority = port_entry.get('priority', '128')
    port_num = port_entry.get('port_number', '0')
    
    # Determine link type (typically P2P for point-to-point)
    link_type = 'P2P'
    
    # Format priority.port number
    prio_nbr = "{}.{}".format(priority, port_num)
    
    click.echo("{:<19}{:<13}{:<16}{:<11}{:<12}{}".format(
        ifname, role, state, cost, prio_nbr, link_type))


def show_mst_region_info():
    """Display MST region configuration information"""
    
    mst_global = get_mst_global_info()
    
    # Get CIST information for some global stats
    cist_entry = get_mst_instance_entry(0)
    
    click.echo("")
    click.echo("Region Name                     : {}".format(mst_global['name']))
    click.echo("Revision                        : {}".format(mst_global['revision']))
    
    if cist_entry:
        bridge_id = cist_entry.get('bridge_address', 'NA')
        root_id = cist_entry.get('root_address', 'NA')
        ext_cost = cist_entry.get('root_path_cost', '0')
        
        # Remove dots and format as continuous hex
        cist_bridge_id = bridge_id.replace('.', '') if bridge_id != 'NA' else '0'
        cist_root_id = root_id.replace('.', '') if root_id != 'NA' else '0'
        
        click.echo("CIST Bridge Identifier          : {}".format(cist_bridge_id))
        click.echo("CIST Root Identifier            : {}".format(cist_root_id))
        click.echo("CIST External Path Cost         : {}".format(ext_cost))
    
    # Count configured instances (excluding CIST)
    keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_MST_INST_TABLE:*")
    instance_count = len([k for k in keys if not k.endswith(':0')]) if keys else 0
    
    click.echo("Instances configured            : {}".format(instance_count))
    
    # Topology change information
    click.echo("Last Topology Change            : 0s")
    click.echo("Number of Topology Changes      : 0")
    
    # Bridge timers
    click.echo("Bridge Timers                   : MaxAge {}s Hello {}s FwdDly {}s MaxHops {}".format(
        mst_global['max_age'], mst_global['hello_time'], 
        mst_global['forward_delay'], mst_global['max_hops']))
    
    # CIST Root timers (typically same as bridge timers)
    click.echo("CIST Root Timers                : MaxAge {}s Hello {}s FwdDly {}s MaxHops {}".format(
        mst_global['max_age'], mst_global['hello_time'], 
        mst_global['forward_delay'], mst_global['max_hops']))
