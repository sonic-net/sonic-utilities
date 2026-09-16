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
# 'counters' command ("show ptp counters [interface]")
#
@ptp.command('counters')
@click.argument('interface_name', metavar='<interface_name>', required=False)
@clicommon.pass_db
def counters(db, interface_name):
    """Show PTP PORT_STATS_NP and PORT_SERVICE_STATS_NP counters from COUNTERS_DB"""
    show_ptp_counters(db, interface_name)
