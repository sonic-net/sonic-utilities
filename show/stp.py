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
#   show spanning_tree mst
#   show spanning_tree mst detail
#   show spanning_tree mst instance <instance-id>
#   show spanning_tree mst instance <instance-id> interface <ifname>
#   show spanning_tree mst interface <interface_name>
#
###############################################################################
g_stp_vlanid = 0
g_stp_mst_instance_id = 0
g_stp_mode = ''
g_stp_appl_db = None
g_stp_cfg_db = None
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


def stp_get_entry_from_mst_inst_tb(db, instance_id):
    entry = stp_get_all_from_pattern(
        db, db.APPL_DB, "*STP_MST_INST_TABLE:{}".format(instance_id))
    if not entry:
        return entry

    defaults = {
        'bridge_address': 'NA',
        'root_address': 'NA',
        'regional_root_address': 'NA',
        'root_path_cost': '0',
        'regional_root_cost': '0',
        'root_max_age': '0',
        'root_hello_time': '0',
        'root_forward_delay': '0',
        'hold_time': '0',
        'root_port': 'NA',
        'remaining_hops': '0',
        'bridge_priority': '0',
        'vlan@': '',
    }
    for field, default in defaults.items():
        if field not in entry:
            entry[field] = default

    return entry


def stp_fill_mst_port_defaults(entry):
    defaults = {
        'port_number': 'NA',
        'priority': '0',
        'path_cost': '0',
        'port_state': 'NA',
        'desig_cost': '0',
        'external_cost': '0',
        'desig_root': 'NA',
        'desig_reg_root': 'NA',
        'desig_bridge': 'NA',
        'role': 'NA',
        'rem_time': '0',
        'bpdu_sent': '-',
        'bpdu_received': '-',
        'desig_port': 'NA',
        'fwd_transitions': '0',
    }
    for field, default in defaults.items():
        if field not in entry:
            entry[field] = default
    return entry


def stp_get_entry_from_mst_port_tb(db, instance_id, ifname):
    entry = stp_get_all_from_pattern(
        db, db.APPL_DB, "*STP_MST_PORT_TABLE:{}:{}".format(instance_id, ifname))
    if not entry:
        return entry
    return stp_fill_mst_port_defaults(entry)


def stp_get_mst_instance_id_from_key(key):
    """Extract MST instance id from a ConfigDB STP_MST_INST key."""
    if isinstance(key, tuple):
        return int(key[-1])
    if isinstance(key, str) and '|' in key:
        return int(key.rsplit('|', 1)[-1])
    return int(key)


def stp_get_mst_instance_cfg_key(instance_id):
    """Build YANG-compatible CONFIG_DB key for STP_MST_INST (list key: instance)."""
    return str(instance_id)


def stp_get_mst_inst_cfg_entry(cfg_db, instance_id):
    """Read STP_MST_INST from CONFIG_DB (YANG key first, legacy key fallback)."""
    if not cfg_db:
        return {}

    for key in (stp_get_mst_instance_cfg_key(instance_id),
                'MST_INSTANCE|{}'.format(instance_id)):
        entry = cfg_db.get_entry('STP_MST_INST', key)
        if entry:
            return entry

    return {}


def stp_get_mst_instance_ids(db):
    keys = db.keys(db.APPL_DB, "*STP_MST_INST_TABLE:*")
    instance_ids = []
    if keys:
        for key in keys:
            result = re.search(r'STP_MST_INST_TABLE:(\d+)$', key)
            if result:
                instance_ids.append(int(result.group(1)))

    if not instance_ids and g_stp_cfg_db:
        cfg_keys = g_stp_cfg_db.get_keys("STP_MST_INST")
        for key in cfg_keys:
            try:
                instance_ids.append(stp_get_mst_instance_id_from_key(key))
            except (TypeError, ValueError):
                continue

    instance_ids = sorted(set(instance_ids))
    return instance_ids


def stp_parse_vlan_id_from_key(key):
    """Extract numeric VLAN id from a ConfigDB VLAN key."""
    if isinstance(key, tuple):
        key = key[0] if key else ''
    if isinstance(key, str) and key.startswith('Vlan'):
        return int(key[4:])
    raise ValueError("invalid vlan key: {}".format(key))


def stp_get_configured_vlan_ids(cfg_db):
    vlan_ids = []
    keys = cfg_db.get_keys("VLAN")
    for key in keys:
        try:
            vlan_ids.append(stp_parse_vlan_id_from_key(key))
        except (TypeError, ValueError):
            continue
    vlan_ids.sort()
    return vlan_ids


def stp_get_mst_mapped_vlan_ids(cfg_db):
    mapped = set()
    keys = cfg_db.get_keys("STP_MST_INST")
    for key in keys:
        instance_id = stp_get_mst_instance_id_from_key(key)
        if instance_id == 0:
            continue
        entry = cfg_db.get_entry("STP_MST_INST", key)
        vlan_list = entry.get('vlan_list', '') if entry else ''
        if vlan_list:
            for vlan in vlan_list.split(','):
                vlan = vlan.strip()
                if vlan:
                    mapped.add(int(vlan))
    return mapped


def stp_compress_vlan_text(vlan_list):
    """Merge VLAN ids and ranges without expanding large spans."""
    if not vlan_list or vlan_list == 'none':
        return 'none'

    spans = []
    for part in vlan_list.replace(' ', '').split(','):
        if not part:
            continue
        try:
            if '-' in part:
                start_text, end_text = part.split('-', 1)
                start, end = int(start_text), int(end_text)
            else:
                start = end = int(part)
        except (TypeError, ValueError):
            continue
        if start > end:
            start, end = end, start
        spans.append((start, end))

    if not spans:
        return 'none'

    spans.sort()
    merged = [spans[0]]
    for start, end in spans[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    parts = []
    for start, end in merged:
        parts.append(str(start) if start == end else "{}-{}".format(start, end))
    return ', '.join(parts)


def stp_format_vlan_id_list(vlan_ids):
    if not vlan_ids:
        return 'none'
    return stp_compress_vlan_text(','.join(str(vlan_id) for vlan_id in vlan_ids))


def stp_get_instance0_vlan_list(cfg_db):
    configured = stp_get_configured_vlan_ids(cfg_db)
    mapped = stp_get_mst_mapped_vlan_ids(cfg_db)
    unmapped = [vlan_id for vlan_id in configured if vlan_id not in mapped]
    return stp_format_vlan_id_list(unmapped)


def stp_get_vlan_list_for_mst_instance(cfg_db, instance_id):
    if instance_id == 0:
        return stp_get_instance0_vlan_list(cfg_db)

    entry = stp_get_mst_inst_cfg_entry(cfg_db, instance_id)
    if entry and entry.get('vlan_list'):
        return entry['vlan_list']

    return 'none'


def stp_get_stp_port_cfg_entry(ifname):
    if not g_stp_cfg_db:
        return {}
    entry = g_stp_cfg_db.get_entry("STP_PORT", ifname)
    return entry if entry else {}


def stp_get_port_edge_port_config(ifname):
    entry = stp_get_stp_port_cfg_entry(ifname)
    return 'Y' if entry.get('edge_port') == 'true' else 'N'


def stp_resolve_interface_name(ifname_parts):
    if len(ifname_parts) == 1:
        return ifname_parts[0]
    if len(ifname_parts) == 2:
        return ifname_parts[0] + ifname_parts[1]
    return None


def stp_display_mst_instances(detail=False):
    instance_ids = stp_get_mst_instance_ids(g_stp_appl_db)
    if not instance_ids:
        click.echo("No MST instance information available")
        return

    if not detail:
        stp_print_mst_mode_header()
        click.echo("")
    for index, instance_id in enumerate(instance_ids):
        stp_display_mst_instance(instance_id, detail=detail)
        if index < len(instance_ids) - 1:
            click.echo("")


def stp_sort_interfaces(intf_list):
    eth_list = [ifname[len("Ethernet"):] for ifname in intf_list if ifname.startswith("Ethernet")]
    po_list = [ifname[len("PortChannel"):] for ifname in intf_list if ifname.startswith("PortChannel")]

    eth_list.sort()
    po_list.sort()

    sorted_list = []
    for port_num in eth_list:
        sorted_list.append("Ethernet" + str(port_num))
    for port_num in po_list:
        sorted_list.append("PortChannel" + port_num)

    return sorted_list


def stp_ensure_db_connected(silent=False):
    """Ensure STP DB handles are connected (needed for nested MST commands)."""
    global g_stp_appl_db
    global g_stp_cfg_db
    global g_stp_mode

    if not is_stp_docker_running():
        return False

    g_stp_appl_db = connect_to_appl_db()
    g_stp_cfg_db = connect_to_cfg_db()

    global_cfg = g_stp_cfg_db.get_entry("STP", "GLOBAL")
    if not global_cfg:
        if not silent:
            click.echo("Spanning-tree is not configured")
        return False

    if global_cfg.get('mode') == 'pvst':
        g_stp_mode = 'PVST'
    elif global_cfg.get('mode') == 'mst':
        g_stp_mode = 'MSTP'
    else:
        g_stp_mode = ''

    return True


def stp_ensure_mst_mode():
    if not stp_ensure_db_connected():
        return False

    global_cfg = g_stp_cfg_db.get_entry("STP", "GLOBAL")
    if global_cfg.get('mode') != 'mst':
        click.echo("Spanning-tree is not configured in MST mode")
        return False
    return True


def stp_print_mst_mode_header():
    global g_stp_mode
    if g_stp_mode:
        click.echo("Spanning-tree Mode: {}".format(g_stp_mode))
        g_stp_mode = ''


# YANG defaults for STP_MST|GLOBAL when fields are not explicitly configured.
MST_CFG_DEFAULT_MAX_AGE = '20'
MST_CFG_DEFAULT_HELLO_TIME = '2'
MST_CFG_DEFAULT_FORWARD_DELAY = '15'
MST_CFG_DEFAULT_MAX_HOPS = '20'


def stp_format_dotted_bridge_id(bridge_id):
    bridge_id = (bridge_id or '').strip()
    if not bridge_id or bridge_id == 'NA':
        return bridge_id
    if '.' in bridge_id:
        return bridge_id.lower()
    bridge_id = bridge_id.replace(':', '').lower()
    if len(bridge_id) < 16:
        bridge_id = bridge_id.zfill(16)
    elif len(bridge_id) > 16:
        bridge_id = bridge_id[:16]
    mac = bridge_id[4:]
    return "{}.{}.{}.{}".format(
        bridge_id[:4], mac[0:4], mac[4:8], mac[8:12])


def stp_get_mst_vlan_display(instance_id, inst_entry):
    vlan_list = stp_get_vlan_list_for_mst_instance(g_stp_cfg_db, instance_id)
    if instance_id != 0 and vlan_list in ('', 'none'):
        vlan_list = inst_entry.get('vlan@', '') if inst_entry else ''
    return stp_compress_vlan_text(vlan_list)


def stp_format_mst_role(role):
    if not role or role == 'NA':
        return role
    return role.upper()


def stp_is_bpdu_guard_shutdown(ifname):
    keys = g_stp_appl_db.keys(g_stp_appl_db.APPL_DB, "*STP_PORT_TABLE:{}".format(ifname))
    if not keys:
        return False
    appdb_entry = g_stp_appl_db.get_all(g_stp_appl_db.APPL_DB, keys[0])
    return bool(appdb_entry and appdb_entry.get('bpdu_guard_shutdown') == 'yes')


def stp_get_mst_port_link_type(ifname):
    link_type = stp_get_stp_port_cfg_entry(ifname).get('link_type', 'auto')
    if link_type in ('point-to-point', 'p2p'):
        return 'P2P'
    if link_type == 'shared':
        return 'Shared-Lan'
    if link_type == 'auto':
        return 'Auto'
    return link_type if link_type else 'NA'


def stp_get_mst_port_prio_nbr(port_entry):
    port_number = port_entry.get('port_number', 'NA')
    if port_number in ('NA', '', None):
        port_number = port_entry.get('desig_port', 'NA')
    return "{}.{}".format(port_entry.get('priority', '0'), port_number)


def stp_get_mst_instance_port_rows(instance_id):
    keys = g_stp_appl_db.keys(
        g_stp_appl_db.APPL_DB, "*STP_MST_PORT_TABLE:{}:*".format(instance_id))
    if not keys:
        return []

    rows = []
    for key in keys:
        result = re.search(r'STP_MST_PORT_TABLE:\d+:(.*)$', key)
        if not result:
            continue
        entry = g_stp_appl_db.get_all(g_stp_appl_db.APPL_DB, key)
        if entry:
            rows.append((result.group(1), stp_fill_mst_port_defaults(entry)))

    order = stp_sort_interfaces([ifname for ifname, _entry in rows])
    rank = {ifname: index for index, ifname in enumerate(order)}
    rows.sort(key=lambda row: rank.get(row[0], len(rank)))
    return rows


def stp_get_mst_root_path_cost(inst_entry):
    """Cost from this bridge to the root: external cost plus internal cost."""
    try:
        external_cost = int(inst_entry.get('root_path_cost', '0'))
    except (TypeError, ValueError):
        external_cost = 0
    try:
        internal_cost = int(inst_entry.get('regional_root_cost', '0'))
    except (TypeError, ValueError):
        internal_cost = 0
    return str(external_cost + internal_cost)


def stp_display_mst_instance(instance_id, detail=False):
    inst_entry = stp_get_entry_from_mst_inst_tb(g_stp_appl_db, instance_id)
    if not inst_entry:
        return

    vlan_list = stp_get_mst_vlan_display(instance_id, inst_entry)
    if instance_id == 0:
        click.echo("#######  MST0 (CIST)       Vlans mapped : {}".format(vlan_list))
    else:
        click.echo("#######  MST{}   (CIST)     Vlans mapped : {}".format(
            instance_id, vlan_list))

    bridge_addr = stp_format_dotted_bridge_id(inst_entry['bridge_address'])
    root_addr = stp_format_dotted_bridge_id(inst_entry['root_address'])
    root_port = inst_entry['root_port'] if inst_entry['root_port'] not in ('', 'NA', None) else 'Root'

    click.echo("Bridge               Address {}".format(bridge_addr))
    click.echo("Root                 Address {}".format(root_addr))
    if instance_id == 0 and not detail:
        click.echo("                     Port     {}                  Path cost {}".format(
            root_port, stp_get_mst_root_path_cost(inst_entry)))
        regional_addr = stp_format_dotted_bridge_id(inst_entry['regional_root_address'])
        click.echo("Regional Root        Address  {}".format(regional_addr))
        click.echo("                      Internal cost {}                Rem hops {}".format(
            inst_entry['regional_root_cost'], inst_entry['remaining_hops']))
        mst_global = g_stp_cfg_db.get_entry("STP_MST", "GLOBAL") or {}
        click.echo("Operational          Hello Time  {}, Forward Delay {}, Max Age {}, Txholdcount {}".format(
            inst_entry['root_hello_time'],
            inst_entry['root_forward_delay'],
            inst_entry['root_max_age'],
            inst_entry['hold_time']))
        click.echo("Configured           Hello Time  {}, Forward Delay {}, Max Age {}, Max Hops {}".format(
            mst_global.get('hello_time', MST_CFG_DEFAULT_HELLO_TIME),
            mst_global.get('forward_delay', MST_CFG_DEFAULT_FORWARD_DELAY),
            mst_global.get('max_age', MST_CFG_DEFAULT_MAX_AGE),
            mst_global.get('max_hops', MST_CFG_DEFAULT_MAX_HOPS)))
    else:
        click.echo("                     Port    {}            Path cost {}    Rem Hops {}".format(
            root_port, stp_get_mst_root_path_cost(inst_entry), inst_entry['remaining_hops']))

    if detail:
        for ifname, port_entry in stp_get_mst_instance_port_rows(instance_id):
            role = stp_format_mst_role(port_entry['role'])
            click.echo("")
            click.echo("{} is {} {}".format(ifname, role, port_entry['port_state']))
            click.echo("Port info              port id {} priority {}          cost {}".format(
                port_entry['port_number'], port_entry['priority'], port_entry['path_cost']))
            click.echo("Designated             Address {}      cost {}".format(
                stp_format_dotted_bridge_id(port_entry['desig_root']),
                port_entry['desig_cost']))
            click.echo("Designated bridge      Address {}      port id {}".format(
                stp_format_dotted_bridge_id(port_entry['desig_bridge']),
                port_entry['desig_port']))
            click.echo("Timers:  forward transitions {}".format(port_entry['fwd_transitions']))
            click.echo("Bpdu send {}, received {}".format(
                port_entry['bpdu_sent'], port_entry['bpdu_received']))
        return

    click.echo("")
    click.echo("{:<18} {:<12} {:<14} {:<10} {:<11} {:<11}".format(
        "Interface", "Role", "State", "Cost", "Prio.Nbr", "Type"))
    click.echo("{:<18} {:<12} {:<14} {:<10} {:<11} {:<11}".format(
        "---------------", "--------", "----------", "-------", "---------", "-----------"))
    for ifname, port_entry in stp_get_mst_instance_port_rows(instance_id):
        role = stp_format_mst_role(port_entry['role'])
        click.echo("{:<18} {:<12} {:<14} {:<10} {:<11} {:<11}".format(
            ifname, role, port_entry['port_state'], port_entry['path_cost'],
            stp_get_mst_port_prio_nbr(port_entry), stp_get_mst_port_link_type(ifname)))


#
# This group houses Spanning_tree commands and subgroups
@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def spanning_tree(ctx):
    """Show spanning_tree commands"""
    if not is_stp_docker_running():
        ctx.fail("STP docker is not running")

    if not stp_ensure_db_connected(silent=(ctx.invoked_subcommand is not None)):
        return

    global_cfg = g_stp_cfg_db.get_entry("STP", "GLOBAL")

    if ctx.invoked_subcommand is None:
        if global_cfg.get('mode') == 'mst':
            stp_display_mst_instances()
            return

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


def stp_show_mstp_bpdu_guard():
    print_header = True
    ifname_all = g_stp_cfg_db.get_keys("STP_PORT")
    for ifname in ifname_all:
        cfg_entry = g_stp_cfg_db.get_entry("STP_PORT", ifname)
        if not cfg_entry or cfg_entry.get('enabled') != 'true':
            continue

        if print_header:
            click.echo("{:<22}{:<29}{}".format(
                "PortNum", "Shutdown Configured", "Port Shut due to BPDU Guard"))
            click.echo("{:<22}{:<29}{}".format(
                "---------", "--------------------", "-----------------------------"))
            print_header = False

        shutdown_cfg = 'Yes' if cfg_entry.get('bpdu_guard_do_disable') == 'true' else 'No'
        port_shut = 'NA'
        if cfg_entry.get('bpdu_guard') == 'true' and shutdown_cfg == 'Yes':
            port_shut = 'Yes' if stp_is_bpdu_guard_shutdown(ifname) else 'No'
        click.echo("{:<22}{:<29}{}".format(ifname, shutdown_cfg, port_shut))


def stp_show_mstp_root_guard():
    print_header = True
    ifname_all = g_stp_cfg_db.get_keys("STP_PORT")
    for ifname in ifname_all:
        entry = g_stp_cfg_db.get_entry("STP_PORT", ifname)
        if not entry or entry.get('root_guard') != 'true' or entry.get('enabled') != 'true':
            continue

        if print_header:
            click.echo("{:<22}{:<30}{}".format(
                "PortNum", "VLAN/MST", "Current State"))
            click.echo("{:<22}{:<30}{}".format(
                "---------", "---------------------", "---------------------------------------------"))
            print_header = False

        vlan_parts = []
        state = 'Consistent state'
        for instance_id in stp_get_mst_instance_ids(g_stp_appl_db):
            port_entry = stp_get_entry_from_mst_port_tb(g_stp_appl_db, instance_id, ifname)
            if not port_entry:
                continue
            inst_entry = stp_get_entry_from_mst_inst_tb(g_stp_appl_db, instance_id)
            if inst_entry:
                vlan_parts.append(stp_get_mst_vlan_display(instance_id, inst_entry))
            rem_time = port_entry.get('rem_time', '0')
            try:
                if int(rem_time) > 0:
                    state = 'Inconsistent state'
            except (TypeError, ValueError):
                pass
        vlan_display = ', '.join([vlan for vlan in vlan_parts if vlan and vlan != 'none'])
        click.echo("{:<22}{:<30}{}".format(ifname, vlan_display, state))


@spanning_tree.command('bpdu_guard')
@click.pass_context
def show_stp_bpdu_guard(ctx):
    """Show spanning_tree bpdu_guard"""
    if not stp_ensure_db_connected():
        return

    if g_stp_cfg_db.get_entry("STP", "GLOBAL").get('mode') == 'mst':
        stp_show_mstp_bpdu_guard()
        return

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
    if not stp_ensure_db_connected():
        return

    if g_stp_cfg_db.get_entry("STP", "GLOBAL").get('mode') == 'mst':
        stp_show_mstp_root_guard()
        return

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


@spanning_tree.group('mst', cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def show_stp_mst(ctx):
    """Show spanning_tree MST information"""
    if ctx.invoked_subcommand is None:
        if not stp_ensure_mst_mode():
            return
        stp_display_mst_instances()


@show_stp_mst.command('detail')
@click.pass_context
def show_stp_mst_detail(ctx):
    """Show spanning_tree MST detailed information"""
    if not stp_ensure_mst_mode():
        return
    stp_display_mst_instances(detail=True)


@show_stp_mst.group('instance', cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.argument('instance_id', metavar='<instance-id>', required=True, type=int)
@click.pass_context
def show_stp_mst_instance(ctx, instance_id):
    """Show spanning_tree MST instance information"""
    if not stp_ensure_mst_mode():
        return
    global g_stp_mst_instance_id
    g_stp_mst_instance_id = instance_id
    if ctx.invoked_subcommand is None:
        stp_display_mst_instance(instance_id)


@show_stp_mst_instance.command('interface')
@click.argument('ifname_parts', metavar='<interface_name>', nargs=-1, required=True)
@click.pass_context
def show_stp_mst_instance_interface(ctx, ifname_parts):
    """Show spanning_tree MST instance interface information"""
    if not stp_ensure_mst_mode():
        return

    ifname = stp_resolve_interface_name(ifname_parts)
    if not ifname:
        ctx.fail("Invalid interface name")

    global g_stp_mst_instance_id
    port_entry = stp_get_entry_from_mst_port_tb(
        g_stp_appl_db, g_stp_mst_instance_id, ifname)
    if not port_entry:
        click.echo("No MST information for instance {} interface {}".format(
            g_stp_mst_instance_id, ifname))
        return

    click.echo("{:<12} {:<6} {:<8} {:<9} {:<14} {:<9} {:<14} {:<20} {:<20}".format(
        "Port", "Prio", "Path", "Edge", "State", "Role", "Designated", "Designated", "Designated"))
    click.echo("{:<12} {:<6} {:<8} {:<9} {:<14} {:<9} {:<14} {:<20} {:<20}".format(
        "Num", "rity", "Cost", "Port", "", "", "Cost", "Root", "Bridge"))
    role = stp_format_mst_role(port_entry['role'])
    click.echo("{:<12} {:<6} {:<8} {:<9} {:<14} {:<9} {:<14} {:<20} {:<20}".format(
        ifname,
        port_entry['priority'],
        port_entry['path_cost'],
        stp_get_port_edge_port_config(ifname),
        port_entry['port_state'],
        role,
        port_entry['desig_cost'],
        port_entry['desig_root'],
        port_entry['desig_bridge']))


@show_stp_mst.command('interface')
@click.argument('ifname_parts', metavar='<interface_name>', nargs=-1, required=True)
@click.pass_context
def show_stp_mst_interface(ctx, ifname_parts):
    """Show spanning_tree MST interface information"""
    if not stp_ensure_mst_mode():
        return

    ifname = stp_resolve_interface_name(ifname_parts)
    if not ifname:
        ctx.fail("Invalid interface name")

    instance_ids = stp_get_mst_instance_ids(g_stp_appl_db)
    if not instance_ids:
        click.echo("No MST instance information available")
        return

    rows = []
    for instance_id in instance_ids:
        port_entry = stp_get_entry_from_mst_port_tb(g_stp_appl_db, instance_id, ifname)
        if port_entry:
            rows.append((instance_id, port_entry))
    if not rows:
        click.echo("No MST information for interface {}".format(ifname))
        return

    port_cfg = stp_get_stp_port_cfg_entry(ifname)
    bpdu_filter = port_cfg.get('bpdu_filter', 'disable')
    if bpdu_filter in ('enable', 'true'):
        bpdu_filter_display = 'True'
    elif bpdu_filter in ('disable', 'false'):
        bpdu_filter_display = 'False'
    else:
        global_entry = g_stp_cfg_db.get_entry("STP", "GLOBAL") or {}
        bpdu_filter_display = 'True' if global_entry.get('bpdu_filter') in ('true', True) else 'False'

    app_port = stp_get_all_from_pattern(
        g_stp_appl_db, g_stp_appl_db.APPL_DB, "*STP_PORT_TABLE:{}".format(ifname)) or {}
    boundary = 'internal'
    if app_port.get('mst_boundary') == 'yes':
        boundary = app_port.get('mst_boundary_proto', '') or 'boundary'

    click.echo("Link Type: {}        Bpdu filter: {}".format(
        stp_get_mst_port_link_type(ifname), bpdu_filter_display))
    click.echo("Boundary : {}   Bpdu guard:  {}".format(
        boundary, 'True' if port_cfg.get('bpdu_guard') == 'true' else 'False'))
    click.echo("")
    click.echo("{:<18} {:<12} {:<14} {:<10} {:<11} {:<11}".format(
        "Instance", "Role", "State", "Cost", "Prio.Nbr", "Vlans"))
    click.echo("{:<18} {:<12} {:<14} {:<10} {:<11} {:<11}".format(
        "---------------", "--------", "----------", "-------", "---------", "-----------"))
    for instance_id, port_entry in rows:
        inst_entry = stp_get_entry_from_mst_inst_tb(g_stp_appl_db, instance_id)
        vlan_list = stp_get_mst_vlan_display(instance_id, inst_entry) if inst_entry else 'none'
        click.echo("{:<18} {:<12} {:<14} {:<10} {:<11} {:<11}".format(
            str(instance_id), stp_format_mst_role(port_entry['role']), port_entry['port_state'],
            port_entry['path_cost'], stp_get_mst_port_prio_nbr(port_entry), vlan_list))
