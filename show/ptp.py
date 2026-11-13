import ast

import click
from natsort import natsorted
from tabulate import tabulate

import utilities_common.cli as clicommon

PTP_TABLE = "PTP"
PTP_PORT_TABLE = "PTP_PORT"
PTP_UNICAST_MASTER_TABLE = "PTP_UNICAST_MASTER_TABLE"
PTP_UNICAST_MASTER_TABLE_IP = "PTP_UNICAST_MASTER_TABLE_IP"
PORT_TABLE = "PORT"
PTP_MODE_NONE = "none"
NOT_SET = "not set"
COUNTERS_PTP_TABLE = "COUNTERS_PTP"
PTP_STATE_CONFIG_TABLE = "PTP_CONFIG"
PTP_STATE_TIME_STATUS_TABLE = "PTP_TIME_STATUS"

PTP_PORT_STATE_NAMES = {
    1: "INITIALIZING",
    2: "FAULTY",
    3: "DISABLED",
    4: "LISTENING",
    5: "PRE_MASTER",
    6: "MASTER",
    7: "PASSIVE",
    8: "UNCALIBRATED",
    9: "SLAVE",
}

# linuxptp pmc GET PORT_STATS_NP: (display name, rx field, tx field)
PTP_COUNTER_PAIRS = (
    ("Sync", "rx_Sync", "tx_Sync"),
    ("Delay_Req", "rx_Delay_Req", "tx_Delay_Req"),
    ("Pdelay_Req", "rx_Pdelay_Req", "tx_Pdelay_Req"),
    ("Pdelay_Resp", "rx_Pdelay_Resp", "tx_Pdelay_Resp"),
    ("Follow_Up", "rx_Follow_Up", "tx_Follow_Up"),
    ("Delay_Resp", "rx_Delay_Resp", "tx_Delay_Resp"),
    ("Pdelay_Resp_Follow_Up", "rx_Pdelay_Resp_Follow_Up", "tx_Pdelay_Resp_Follow_Up"),
    ("Announce", "rx_Announce", "tx_Announce"),
    ("Signaling", "rx_Signaling", "tx_Signaling"),
    ("Management", "rx_Management", "tx_Management"),
)

# linuxptp pmc GET PORT_SERVICE_STATS_NP: (display name, field)
PTP_SERVICE_COUNTERS = (
    ("announce_timeout", "announce_timeout"),
    ("sync_timeout", "sync_timeout"),
    ("delay_timeout", "delay_timeout"),
    ("unicast_service_timeout", "unicast_service_timeout"),
    ("unicast_request_timeout", "unicast_request_timeout"),
    ("master_announce_timeout", "master_announce_timeout"),
    ("master_sync_timeout", "master_sync_timeout"),
    ("qualification_timeout", "qualification_timeout"),
    ("sync_mismatch", "sync_mismatch"),
    ("followup_mismatch", "followup_mismatch"),
)


def _convert_ifname(ctx, interface_name):
    if not interface_name:
        return interface_name
    if clicommon.get_interface_naming_mode() == "alias":
        alias = interface_name
        interface_name = clicommon.InterfaceAliasConverter().alias_to_name(alias)
        if interface_name == alias:
            ctx.fail("cannot find interface name for alias {}".format(alias))
    return interface_name


def _display_ifname(ifname):
    if clicommon.get_interface_naming_mode() == "alias":
        return clicommon.InterfaceAliasConverter().name_to_alias(ifname)
    return ifname


def _ptp_row(ifname, port_info, ptp_ports):
    mode = port_info.get('ptp_mode', PTP_MODE_NONE) or PTP_MODE_NONE
    enabled = (ifname in ptp_ports) or (mode not in (PTP_MODE_NONE, ''))
    return [
        _display_ifname(ifname),
        'enabled' if enabled else 'disabled',
        mode,
    ]


def show_ptp_port_status(db, interface_name):
    ctx = click.get_current_context()
    config_db = db.cfgdb
    port_tbl = config_db.get_table(PORT_TABLE)
    if not port_tbl:
        click.echo("No ports configured")
        return

    interface_name = _convert_ifname(ctx, interface_name)
    ptp_ports = config_db.get_table(PTP_PORT_TABLE) or {}

    if interface_name:
        if interface_name not in port_tbl:
            ctx.fail("Interface '{}' does not exist in the PORT table".format(interface_name))
        names = [interface_name]
    else:
        names = natsorted(list(port_tbl.keys()))

    header = ['Interface', 'PTP', 'Mode']
    body = [_ptp_row(name, port_tbl[name], ptp_ports) for name in names]
    click.echo(tabulate(body, header, tablefmt='simple'))


def _cfg_value(entry, field):
    if not entry:
        return NOT_SET
    value = entry.get(field)
    if value is None or value == '':
        return NOT_SET
    return str(value)


def _unicast_listen_enabled(port_info):
    return str(port_info.get('unicast_listen', 'false')).lower() == 'true'


def _port_role(port_info):
    """Configured unicast role: slave if a master table is bound, master if unicast listen is on."""
    has_table = bool(port_info.get('unicast_table'))
    listen = _unicast_listen_enabled(port_info)
    if has_table and listen:
        return 'slave/master'
    if has_table:
        return 'slave'
    if listen:
        return 'master'
    return 'auto'


def _split_umt_ip_key(key):
    if isinstance(key, (list, tuple)) and len(key) >= 2:
        return str(key[0]), str(key[1])
    parts = str(key).split('|', 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _unicast_master_rows(tables, ip_entries):
    ips_by_table = {}
    for key in ip_entries:
        parsed = _split_umt_ip_key(key)
        if not parsed:
            continue
        table_id, ip_address = parsed
        ips_by_table.setdefault(table_id, []).append(ip_address)

    table_ids = natsorted({str(k) for k in tables} | set(ips_by_table))
    rows = []
    for table_id in table_ids:
        addresses = natsorted(ips_by_table.get(table_id, []))
        if not addresses:
            rows.append([table_id, NOT_SET])
            continue
        for address in addresses:
            rows.append([table_id, address])
    return rows


def _parse_ptp_state_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (ValueError, SyntaxError, TypeError):
        pass
    return value


def _ptp_deep_parse_state(value):
    parsed = _parse_ptp_state_value(value)
    if isinstance(parsed, dict):
        return {k: _ptp_deep_parse_state(v) for k, v in parsed.items()}
    if isinstance(parsed, list):
        return [_ptp_deep_parse_state(item) for item in parsed]
    return parsed


def _ptp_parsed_field(entry, field):
    """Parse a PTP STATE_DB field written by ptp telemetry (str() dict/list leaves)."""
    if not entry:
        return None
    if field not in entry:
        return None
    return _ptp_deep_parse_state(entry[field])


def _ptp_int_field(value):
    if value is None or value == '' or value == NOT_SET:
        return None
    return int(value)


def _offset_scaled_log_variance_ns2(oslv):
    """Decode IEEE 1588 ClockQuality offsetScaledLogVariance to variance (ns^2)."""
    val = _ptp_int_field(oslv)
    if val is None:
        return NOT_SET
    scaled = val & 0xFF
    s_log = (val >> 8) & 0xFF
    if s_log >= 0x80:
        s_log -= 0x100
    return scaled * (2.0 ** s_log)


def _cumulative_scaled_rate_offset_double_ppb(value):
    """Decode TIME_STATUS_NP cumulativeScaledRateOffset (dimensionless rate offset in ppb)."""
    val = _ptp_int_field(value)
    if val is None:
        return NOT_SET
    return val * 1e9 / (2.0 ** 41)  # ppb


def _format_ptp_double(value):
    if value is NOT_SET:
        return NOT_SET
    if isinstance(value, float):
        return '{:.6f}'.format(value)
    return value


def _state_db_table_keys(db, table_name):
    sep = db.db.get_db_separator(db.db.STATE_DB)
    prefix = table_name + sep
    keys = []
    for key in db.db.keys(db.db.STATE_DB, prefix + '*') or []:
        entry_key = key[len(prefix):]
        if entry_key:
            keys.append(entry_key)
    return natsorted(keys)


def _state_db_entry(db, table_name, entry_key):
    sep = db.db.get_db_separator(db.db.STATE_DB)
    return db.db.get_all(db.db.STATE_DB, sep.join((table_name, entry_key))) or {}


def _show_ptp_status(config, time_status):
    default_ds = _ptp_parsed_field(config, 'default-ds') or {}
    current_ds = _ptp_parsed_field(config, 'current-ds') or {}
    parent_ds = _ptp_parsed_field(config, 'parent-ds') or {}
    time_properties = _ptp_parsed_field(config, 'time-properties-ds') or {}

    click.echo('Local Clock')

    number_of_ports = default_ds.get('number-ports', 0)
    if number_of_ports > 1:
        clock_type = 'Boundary Clock'
    elif number_of_ports == 1:
        clock_type = 'Ordinary Clock'
    else:
        clock_type = 'Unknown'

    clock_identity_str = default_ds.get('clock-identity', NOT_SET)
    clock_quality = default_ds.get('clock-quality', {})
    clock_class_str = clock_quality.get('clock-class', NOT_SET)
    clock_accuracy_str = clock_quality.get('clock-accuracy', NOT_SET)

    body = [
        ['clock type', clock_type],
        ['domain', default_ds.get('domain-number', NOT_SET)],
        #['announce interval', config.get('announce-interval', NOT_SET)],
        ['clock id', clock_identity_str],
        ['clock class', clock_class_str],
        ['clock accuracy', clock_accuracy_str],
        ['clock priority1', default_ds.get('priority1', NOT_SET)],
        ['clock priority2', default_ds.get('priority2', NOT_SET)],
        ['steps removed', current_ds.get('steps-removed', NOT_SET)],
    ]
    click.echo(tabulate(body, ['Parameter', 'Value'], tablefmt='simple'))
    click.echo('')

    parent_port_identity = parent_ds.get('parent-port-identity', {})
    parent_clock_identity_str = parent_port_identity.get('clock-identity', NOT_SET)

    grandmaster_clock_quality = parent_ds.get('grandmaster-clock-quality', {})
    grandmaster_clock_class_str = grandmaster_clock_quality.get('clock-class', NOT_SET)
    grandmaster_clock_accuracy_str = grandmaster_clock_quality.get('clock-accuracy', NOT_SET)
    grandmaster_clock_variance_str = _format_ptp_double(
        _offset_scaled_log_variance_ns2(
            grandmaster_clock_quality.get('offset-scaled-log-variance', NOT_SET),
        ),
    )

    click.echo('Parent Clock')
    body = [
        #['ip address', parent_ds.get('ip-address', NOT_SET)],
        ['parent clock id', parent_clock_identity_str],
        ['gm clock id', parent_ds.get('grandmaster-identity', NOT_SET)],
        ['gm clock class', grandmaster_clock_class_str],
        ['gm clock accuracy', grandmaster_clock_accuracy_str],
        ['gm clock variance', grandmaster_clock_variance_str],
        ['gm clock priority1', parent_ds.get('grandmaster-priority1', NOT_SET)],
        ['gm clock priority2', parent_ds.get('grandmaster-priority2', NOT_SET)],
    ]
    click.echo(tabulate(body, ['Parameter', 'Value'], tablefmt='simple'))
    click.echo('')

    click.echo('Time Properties')
    body = [
        ['time traceable', time_properties.get('time-traceable', NOT_SET)],
        ['frequency traceable', time_properties.get('frequency-traceable', NOT_SET)],
        ['time source', time_properties.get('time-source', NOT_SET)],
        ['ptp timescale', time_properties.get('ptp-timescale', NOT_SET)],
    ]
    if time_properties.get('current-utc-offset-valid') == 'True':
        body.append([
            ['utc offset', time_properties.get('current-utc-offset', NOT_SET)]
            ])

    click.echo(tabulate(body, ['Parameter', 'Value'], tablefmt='simple'))
    click.echo('')

    click.echo('Time Status')
    if not time_status:
        click.echo('No time status available')
        return

    body = []
    for field, label in (
        ('master-offset', 'master offset'),
        ('ingress-time', 'ingress time'),
        ('cumulative-scaled-rate-offset', 'cumulative offset(ppb)'),
        ('scaled-last-gm-phase-change', 'last GM phase change'),
        ('gm-time-base-indicator', 'GM time base indicator'),
        ('nanoseconds', 'nanoseconds'),
        ('fractional-nanoseconds', 'fractional nanoseconds'),
    ):
        if field in time_status:
            raw = time_status[field]
            if field == 'cumulative-scaled-rate-offset':
                display = _format_ptp_double(_cumulative_scaled_rate_offset_double_ppb(raw))
            else:
                display = raw
            body.append([label, display])
    if not body:
        click.echo('No time status available')
        return
    click.echo(tabulate(body, ['Parameter', 'Value'], tablefmt='simple'))


def show_ptp_status(db):
    entry_keys = _state_db_table_keys(db, PTP_STATE_CONFIG_TABLE)

    if not entry_keys:
        click.echo("No PTP operational status in STATE_DB")
        return

    first_instance = True
    for entry_key in entry_keys:
        if not first_instance:
            click.echo('')
        first_instance = False

        config = _state_db_entry(db, PTP_STATE_CONFIG_TABLE, entry_key)
        time_status = _state_db_entry(db, PTP_STATE_TIME_STATUS_TABLE, entry_key)

        click.echo("PTP Instance: {}".format(entry_key))
        click.echo('')
        
        _show_ptp_status(config, time_status)


def show_ptp_protocol_status(db):
    config_db = db.cfgdb
    global_cfg = config_db.get_entry(PTP_TABLE, 'global') or {}
    tables = config_db.get_table(PTP_UNICAST_MASTER_TABLE) or {}
    ip_entries = config_db.get_table(PTP_UNICAST_MASTER_TABLE_IP) or {}
    ptp_ports = config_db.get_table(PTP_PORT_TABLE) or {}

    click.echo('PTP Protocol')
    click.echo('')
    proto_header = ['Parameter', 'Value']
    proto_body = [
        ['domain-number', _cfg_value(global_cfg, 'domain_number')],
        ['sync-interval', _cfg_value(global_cfg, 'sync_interval')],
        ['announce-interval', _cfg_value(global_cfg, 'announce_interval')],
    ]
    click.echo(tabulate(proto_body, proto_header, tablefmt='simple'))
    click.echo('')

    click.echo('Unicast Master Table')
    umt_rows = _unicast_master_rows(tables, ip_entries)
    if not umt_rows:
        click.echo('No unicast master tables configured')
    else:
        click.echo(tabulate(umt_rows, ['Table ID', 'Address'], tablefmt='simple'))
    click.echo('')

    click.echo('PTP Ports')
    if not ptp_ports:
        click.echo('No PTP ports configured')
        return

    port_header = ['Interface', 'Role', 'Unicast Table', 'Unicast Listen']
    port_body = []
    for ifname in natsorted(list(ptp_ports.keys())):
        info = ptp_ports[ifname] or {}
        port_body.append([
            _display_ifname(ifname),
            _port_role(info),
            info.get('unicast_table') or '-',
            'true' if _unicast_listen_enabled(info) else 'false',
        ])
    click.echo(tabulate(port_body, port_header, tablefmt='simple'))


def _counters_key(db, ifname):
    sep = db.db.get_db_separator(db.db.COUNTERS_DB)
    return "{}{}{}".format(COUNTERS_PTP_TABLE, sep, ifname)


def _counters_ifnames(db):
    sep = db.db.get_db_separator(db.db.COUNTERS_DB)
    prefix = COUNTERS_PTP_TABLE + sep
    names = []
    for key in db.db.keys(db.db.COUNTERS_DB, prefix + '*') or []:
        ifname = key[len(prefix):]
        if ifname:
            names.append(ifname)
    return natsorted(names)


def _show_one_ptp_counters(db, ifname):
    entry = db.db.get_all(db.db.COUNTERS_DB, _counters_key(db, ifname)) or {}
    if not entry:
        click.echo("No PTP counters for interface '{}'".format(_display_ifname(ifname)))
        return False

    click.echo("Interface: {}".format(_display_ifname(ifname)))
    if entry.get('portIdentity'):
        click.echo("portIdentity: {}".format(entry['portIdentity']))
    click.echo('')
    body = []
    for label, rx_field, tx_field in PTP_COUNTER_PAIRS:
        body.append([
            label,
            entry.get(rx_field, '0'),
            entry.get(tx_field, '0'),
        ])
    click.echo(tabulate(body, ['Message', 'RX', 'TX'], tablefmt='simple'))
    click.echo('')
    click.echo('Service')
    service_body = []
    for label, field in PTP_SERVICE_COUNTERS:
        service_body.append([label, entry.get(field, '0')])
    click.echo(tabulate(service_body, ['Event', 'Count'], tablefmt='simple'))
    return True


def show_ptp_counters(db, interface_name):
    ctx = click.get_current_context()
    interface_name = _convert_ifname(ctx, interface_name)

    if interface_name:
        port_tbl = db.cfgdb.get_table(PORT_TABLE) or {}
        if interface_name not in port_tbl:
            ctx.fail("Interface '{}' does not exist in the PORT table".format(interface_name))
        if not _show_one_ptp_counters(db, interface_name):
            return
        return

    names = _counters_ifnames(db)
    if not names:
        click.echo("No PTP counters in COUNTERS_DB")
        return

    first = True
    for ifname in names:
        if not first:
            click.echo('')
        first = False
        _show_one_ptp_counters(db, ifname)


#
# 'ptp' group ("show ptp ...")
#
@click.group(cls=clicommon.AbbreviationGroup, name='ptp', invoke_without_command=False)
def ptp():
    """Show PTP (IEEE 1588) information"""
    pass


#
# 'port' group ("show ptp port ...")
#
@ptp.group(cls=clicommon.AbbreviationGroup, name='port')
def port():
    """Show PTP port information"""
    pass


#
# 'status' command ("show ptp port status [interface]")
#
@port.command('status')
@click.argument('interface_name', metavar='<interface_name>', required=False)
@clicommon.pass_db
def port_status(db, interface_name):
    """Show PTP enable state and timestamp mode per port"""
    show_ptp_port_status(db, interface_name)


#
# 'protocol' group ("show ptp protocol ...")
#
@ptp.group(cls=clicommon.AbbreviationGroup, name='protocol')
def protocol():
    """Show PTP protocol configuration and port roles"""
    pass


#
# 'status' command ("show ptp protocol status")
#
@protocol.command('status')
@clicommon.pass_db
def protocol_status(db):
    """Show PTP domain, intervals, unicast master tables, and port master/slave roles"""
    show_ptp_protocol_status(db)


#
# 'status' command ("show ptp status")
#
@ptp.command('status')
@clicommon.pass_db
def status(db):
    """Show PTP clock and port runtime status from STATE_DB"""
    show_ptp_status(db)


#
# 'counters' command ("show ptp counters [interface]")
#
@ptp.command('counters')
@click.argument('interface_name', metavar='<interface_name>', required=False)
@clicommon.pass_db
def counters(db, interface_name):
    """Show PTP PORT_STATS_NP and PORT_SERVICE_STATS_NP counters from COUNTERS_DB"""
    show_ptp_counters(db, interface_name)
