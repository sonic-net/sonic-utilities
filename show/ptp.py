import click
from natsort import natsorted
from tabulate import tabulate

import utilities_common.cli as clicommon

PTP_PORT_TABLE = "PTP_PORT"
PORT_TABLE = "PORT"
PTP_MODE_NONE = "none"


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
