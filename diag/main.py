"""
SONiC diagnostic CLI commands

Transient diagnostic operations that write to APPL_DB (not CONFIG_DB)
and do not survive config save or reboot.
"""

import click
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector, DBConnector, ProducerStateTable, FieldValuePairs
import utilities_common.cli as clicommon
from utilities_common.prbs_util import validate_mode


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

DIAG_PORT_TABLE = 'DIAG_PORT_TABLE'


@click.group(cls=click.Group, context_settings=CONTEXT_SETTINGS)
def cli():
    """SONiC command line - 'diag' command"""
    pass


@cli.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def interface(ctx):
    """Interface diagnostic commands"""
    pass


@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def prbs(ctx):
    """PRBS diagnostic commands"""
    pass


@prbs.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('--mode', '-m',
              type=click.Choice(['both', 'rx', 'tx'], case_sensitive=False),
              default='rx',
              help='PRBS mode: rx (default), tx, or both')
@click.option('--pattern', '-p',
              type=click.Choice(['none', 'PRBS7', 'PRBS9', 'PRBS10', 'PRBS11', 'PRBS13',
                                 'PRBS15', 'PRBS16', 'PRBS20', 'PRBS23', 'PRBS31', 'PRBS32',
                                 'PRBS49', 'PRBS58', 'PRBS7Q', 'PRBS9Q', 'PRBS13Q', 'PRBS15Q',
                                 'PRBS23Q', 'PRBS31Q', 'SSPRQ'], case_sensitive=False),
              default='none',
              help='PRBS pattern (optional)')
@click.pass_context
def enable(ctx, interface_name, mode, pattern):
    """Enable PRBS on an interface"""
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = clicommon.iface_alias_converter.alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("Invalid interface name")

    config_db = ConfigDBConnector(use_unix_socket_path=True)
    config_db.connect()
    port_table = config_db.get_table('PORT')
    if interface_name not in port_table:
        ctx.fail(f"Interface {interface_name} does not exist")

    if not validate_mode(mode):
        ctx.fail(f"Invalid mode: {mode}")
    mode = mode.lower()

    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB)
    supported_str = state_db.get(state_db.STATE_DB,
                                 f'PORT_TABLE|{interface_name}',
                                 'supported_prbs_patterns')
    if supported_str:
        supported_list = [s.strip() for s in supported_str.split(',') if s.strip()]
        if pattern not in supported_list:
            ctx.fail(f"PRBS pattern {pattern} is not supported on {interface_name}.\n"
                     f"Supported patterns: {', '.join(supported_list)}")

    appl_db = SonicV2Connector(host='127.0.0.1')
    appl_db.connect(appl_db.APPL_DB)
    current_mode = appl_db.get(appl_db.APPL_DB,
                               f'{DIAG_PORT_TABLE}:{interface_name}',
                               'prbs_mode')
    if current_mode in ('rx', 'tx', 'both'):
        ctx.fail(f"PRBS is already enabled on {interface_name} in '{current_mode}' mode. "
                 f"Please disable first using 'diag interface prbs disable {interface_name}' "
                 f"to capture results, then re-enable with new settings.")

    fvs = [('prbs_mode', mode), ('prbs_pattern', pattern)]

    appl_db_conn = DBConnector('APPL_DB', 0)
    diag_tbl = ProducerStateTable(appl_db_conn, DIAG_PORT_TABLE)
    diag_tbl.set(interface_name, FieldValuePairs(fvs))

    click.echo(f"PRBS enabled on {interface_name} (mode={mode}, pattern={pattern})")
    click.echo(f"Note: PRBS test is now running. Use 'diag interface prbs disable "
               f"{interface_name}' to stop and capture results.")


@prbs.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def disable(ctx, interface_name):
    """Disable PRBS on an interface and capture results"""
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = clicommon.iface_alias_converter.alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("Invalid interface name")

    config_db = ConfigDBConnector(use_unix_socket_path=True)
    config_db.connect()
    port_table = config_db.get_table('PORT')
    if interface_name not in port_table:
        ctx.fail(f"Interface {interface_name} does not exist")

    appl_db = SonicV2Connector(host='127.0.0.1')
    appl_db.connect(appl_db.APPL_DB)
    current_mode = appl_db.get(appl_db.APPL_DB,
                               f'{DIAG_PORT_TABLE}:{interface_name}',
                               'prbs_mode')
    if current_mode not in ('rx', 'tx', 'both'):
        click.echo(f"PRBS is not enabled on {interface_name}")
        return

    appl_db_conn = DBConnector('APPL_DB', 0)
    diag_tbl = ProducerStateTable(appl_db_conn, DIAG_PORT_TABLE)
    diag_tbl.set(interface_name, FieldValuePairs([('prbs_mode', 'disabled')]))

    click.echo(f"PRBS disabled on {interface_name}")
    click.echo(f"Results captured and stored. Use 'show interfaces prbs status -i {interface_name}' to view.")


if __name__ == '__main__':
    cli()
