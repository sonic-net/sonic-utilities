import re
import click
from natsort import natsorted
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
#   show spanning_tree mst
#   show spanning_tree mst region
#   show spanning_tree mst instance <instance-id>
#   show spanning_tree mst interface <ifname>
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


def connect_to_state_db():
    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)
    return state_db


def echo_held_instances(table, what):
    """VLANs or MST instances spanning tree is configured for but the hardware
    has no instance left for; stpmgrd records them in STATE_DB."""
    state_db = connect_to_state_db()
    keys = state_db.keys(state_db.STATE_DB, table + "|*") or []
    held = []
    for key in keys:
        entry = state_db.get_all(state_db.STATE_DB, key) or {}
        if entry.get('instance_state') == 'unavailable':
            held.append((key.split('|', 1)[1], entry.get('reason', '')))
    if not held:
        return
    click.echo("")
    for name, reason in natsorted(held):
        click.echo("{} {} - no STP instance: {}".format(what, name.replace('Vlan', ''), reason))


# Redis DB only supports limiter pattern search wildcards.
# check https://redis.io/commands/KEYS before using this api
# Redis-db uses glob-style patterns not regex
def stp_get_key_from_pattern(db_connect, db, pattern):
    keys = db_connect.keys(db, pattern)
    if keys:
        return keys[0]
    else:
        return None


# get_all doesn't accept regex patterns, it requires exact key
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


def _summarize_vlans(vlan_str):
    """Compress a comma-separated VLAN list into ranges (e.g. '1-100,200')."""
    nums = sorted(int(v) for v in vlan_str.split(',') if v.strip().isdigit())
    if not nums:
        return "none"
    ranges = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append((start, prev))
            start = prev = n
    ranges.append((start, prev))
    return ",".join("{}-{}".format(a, b) if a != b else str(a) for a, b in ranges)


MST_REGION_FIELDS = (
    ("name", "Region Name"),
    ("revision", "Revision"),
    ("max_hops", "Max Hops"),
    ("max_age", "Max Age"),
    ("hello_time", "Hello Time"),
    ("forward_delay", "Forward Delay"),
    ("hold_count", "Hold Count"),
)


def mst_instance_ids():
    """Every MST instance the daemon has published, lowest first."""
    inst_ids = set()
    for key in (g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_MST_INST_TABLE:*") or []):
        m = re.search(r'STP_MST_INST_TABLE:(\d+)$', key)
        if m:
            inst_ids.add(int(m.group(1)))
    return sorted(inst_ids)


def mst_instance_entry(inst):
    return stp_get_all_from_pattern(
        g_stp_appl_db, g_stp_appl_db.APPL_DB, "*STP_MST_INST_TABLE:{}".format(inst))


def mst_instance_ports(inst):
    """Interfaces enrolled in one instance, by name."""
    ports = []
    pattern = "*STP_MST_PORT_TABLE:{}:*".format(inst)
    for key in (g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, pattern) or []):
        m = re.search(r'STP_MST_PORT_TABLE:{}:(.*)$'.format(inst), key)
        if m:
            ports.append(m.group(1))
    return sorted(ports)


def mst_port_entry(inst, ifname):
    return stp_get_all_from_pattern(
        g_stp_appl_db, g_stp_appl_db.APPL_DB,
        "*STP_MST_PORT_TABLE:{}:{}".format(inst, ifname))


def mst_boundary_state(ifname):
    """Boundary state, which the daemon writes to the port table, not the
    per-instance one. Returns None when the daemon has not published it."""
    entry = stp_get_all_from_pattern(
        g_stp_appl_db, g_stp_appl_db.APPL_DB, "*STP_PORT_TABLE:{}".format(ifname))
    if not entry or 'mst_boundary' not in entry:
        return None
    if entry.get('mst_boundary') != 'yes':
        return "no"
    proto = entry.get('mst_boundary_proto', '')
    return "yes ({})".format(proto) if proto else "yes"


def require_mst_mode(ctx):
    if g_stp_mode != 'MSTP':
        ctx.fail("Spanning-tree is not running in MST mode")


def echo_instance_summary(inst, entry):
    """The instance header, including the fields that only MST has."""
    click.echo("MST Instance {} ({})".format(inst, "CIST" if inst == 0 else "MSTI"))
    click.echo("--------------------------------------------------------------------")
    if not entry:
        click.echo("  No state published for this instance")
        return
    vlan_str = entry.get('vlan@', entry.get('vlan', ''))
    vlan_cnt = len([v for v in vlan_str.split(',') if v.strip()])
    click.echo("  Bridge Address : {}   Bridge Priority: {}".format(
        entry.get('bridge_address', ''), entry.get('bridge_priority', '')))
    click.echo("  Root Address   : {}   Root Cost: {}   Root Port: {}".format(
        entry.get('root_address', ''), entry.get('root_path_cost', ''),
        entry.get('root_port', '')))
    click.echo("  Regional Root  : {}   Regional Root Cost: {}".format(
        entry.get('regional_root_address', ''), entry.get('regional_root_cost', '')))
    click.echo("  MaxAge: {}  Hello: {}  FwdDelay: {}  RemainingHops: {}  HoldTime: {}".format(
        entry.get('root_max_age', ''), entry.get('root_hello_time', ''),
        entry.get('root_forward_delay', ''), entry.get('remaining_hops', ''),
        entry.get('hold_time', '')))
    click.echo("  VLANs mapped   : {} ({} vlan(s))".format(
        _summarize_vlans(vlan_str), vlan_cnt))


def echo_instance_ports(inst, detail=False):
    """The per-instance port table. detail adds the designated-bridge columns
    and the counters, which are what you need when a role looks wrong."""
    ports = mst_instance_ports(inst)
    click.echo("")
    click.echo("  {:17}{:12}{:13}{:8}{:6}{}".format(
        "Port", "Role", "State", "Cost", "Prio", "Designated Bridge"))
    if not ports:
        click.echo("  No interfaces are enrolled in this instance")
        return
    for ifname in ports:
        pe = mst_port_entry(inst, ifname)
        if not pe:
            continue
        click.echo("  {:17}{:12}{:13}{:8}{:6}{}".format(
            ifname, pe.get('role', ''), pe.get('port_state', ''),
            pe.get('path_cost', ''), pe.get('priority', ''), pe.get('desig_bridge', '')))
        if not detail:
            continue
        click.echo("    {:15}{}".format("Desig Root:", pe.get('desig_root', '')))
        click.echo("    {:15}{}".format("Desig RegRoot:", pe.get('desig_reg_root', '')))
        click.echo("    {:15}{:14}{:17}{}".format(
            "Desig Cost:", pe.get('desig_cost', ''),
            "Desig Port:", pe.get('desig_port', '')))
        click.echo("    {:15}{:14}{:17}{}".format(
            "External Cost:", pe.get('external_cost', ''),
            "Fwd Transitions:", pe.get('fwd_transitions', '')))
        click.echo("    {:15}{:14}{:17}{}".format(
            "BPDUs Sent:", pe.get('bpdu_sent', ''),
            "BPDUs Recvd:", pe.get('bpdu_received', '')))
        boundary = mst_boundary_state(ifname)
        if boundary is not None:
            click.echo("    {:15}{}".format("Boundary:", boundary))
        click.echo("")


def echo_mst_region():
    """Region identity, which lives only in CONFIG_DB: the daemon publishes
    no region table, so there is nothing operational to read it from."""
    cfg = g_stp_cfg_db.get_entry("STP_MST", "GLOBAL") or {}
    click.echo("MST Region")
    click.echo("--------------------------------------------------------------------")
    if not cfg:
        click.echo("  No MST region is configured")
    else:
        for field, label in MST_REGION_FIELDS:
            if field in cfg:
                click.echo("  {:16}{}".format(label + ":", cfg[field]))
    click.echo("")
    click.echo("  {:12}{}".format("Instance", "VLANs mapped"))
    inst_ids = mst_instance_ids()
    if not inst_ids:
        click.echo("  No MST instances are operational")
        return
    for inst in inst_ids:
        entry = mst_instance_entry(inst) or {}
        vlan_str = entry.get('vlan@', entry.get('vlan', ''))
        click.echo("  {:12}{}".format(
            "{} ({})".format(inst, "CIST" if inst == 0 else "MSTI"),
            _summarize_vlans(vlan_str)))


def show_mst_instances():
    """Render MSTP instances and their ports from APPL_DB."""
    click.echo("Spanning-tree Mode: MSTP")
    inst_ids = mst_instance_ids()
    if not inst_ids:
        click.echo("No MST instances are operational")
    for inst in inst_ids:
        click.echo("")
        echo_instance_summary(inst, mst_instance_entry(inst))
        echo_instance_ports(inst)
    echo_held_instances("STP_MST_INST_TABLE", "MST Instance")


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

    if ctx.invoked_subcommand is None and g_stp_mode == 'MSTP':
        show_mst_instances()
        return

    if ctx.invoked_subcommand is None:
        keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_VLAN_TABLE:Vlan*") or []
        vlan_list = []
        for key in keys:
            result = re.search('.STP_VLAN_TABLE:Vlan(.*)', key)
            vlanid = result.group(1)
            vlan_list.append(int(vlanid))
        vlan_list.sort()
        for vlanid in vlan_list:
            ctx.invoke(show_stp_vlan, vlanid=vlanid)
        echo_held_instances("STP_VLAN_TABLE", "VLAN")


@spanning_tree.group('mst', cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def show_stp_mst(ctx):
    """Show spanning_tree mst region and instance information"""
    require_mst_mode(ctx)
    if ctx.invoked_subcommand is not None:
        return
    echo_mst_region()
    click.echo("")
    show_mst_instances()


@show_stp_mst.command('region')
@click.pass_context
def show_stp_mst_region(ctx):
    """Show spanning_tree mst region information"""
    require_mst_mode(ctx)
    echo_mst_region()


@show_stp_mst.command('instance')
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.pass_context
def show_stp_mst_instance(ctx, instance_id):
    """Show spanning_tree mst instance <instance-id> information"""
    require_mst_mode(ctx)
    if instance_id not in mst_instance_ids():
        ctx.fail("MST instance {} is not operational".format(instance_id))
    echo_instance_summary(instance_id, mst_instance_entry(instance_id))
    echo_instance_ports(instance_id, detail=True)


@show_stp_mst.command('interface')
@click.argument('ifname', metavar='<ifname>', required=True)
@click.pass_context
def show_stp_mst_interface(ctx, ifname):
    """Show spanning_tree mst interface <ifname> across every instance"""
    require_mst_mode(ctx)
    found = [inst for inst in mst_instance_ids() if mst_port_entry(inst, ifname)]
    if not found:
        ctx.fail("{} is not enrolled in any MST instance".format(ifname))
    click.echo("{:10}{:12}{:13}{:8}{:6}{}".format(
        "Instance", "Role", "State", "Cost", "Prio", "Designated Bridge"))
    for inst in found:
        pe = mst_port_entry(inst, ifname)
        click.echo("{:10}{:12}{:13}{:8}{:6}{}".format(
            "{} ({})".format(inst, "CIST" if inst == 0 else "MSTI"),
            pe.get('role', ''), pe.get('port_state', ''),
            pe.get('path_cost', ''), pe.get('priority', ''),
            pe.get('desig_bridge', '')))
    boundary = mst_boundary_state(ifname)
    if boundary is not None:
        click.echo("")
        click.echo("{:10}{}".format("Boundary:", boundary))


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
