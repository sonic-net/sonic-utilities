"""
PRBS (Pseudo-Random Bit Sequence) configuration commands
"""

import click
from swsscommon.swsscommon import SonicV2Connector
import utilities_common.cli as clicommon
from utilities_common.prbs_util import validate_mode


def register(cli):
    """Register PRBS commands to the interface group"""
    cli_node = cli
    if hasattr(cli, 'commands') and 'interface' in cli.commands:
        cli_node = cli.commands['interface']
    
    cli_node.add_command(prbs)


@click.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def prbs(ctx):
    """PRBS configuration commands"""
    pass


@prbs.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('--mode', '-m', 
              type=click.Choice(['both', 'rx', 'tx'], case_sensitive=False),
              default='rx',
              help='PRBS mode: rx (default), tx, or both')
@click.option('--pattern', '-p',
              type=click.Choice(['none', 'PRBS7', 'PRBS9', 'PRBS10', 'PRBS11', 'PRBS13', 'PRBS15', 'PRBS16', 'PRBS20', 'PRBS23', 'PRBS31', 'PRBS32', 'PRBS49', 'PRBS58', 'PRBS7Q', 'PRBS9Q', 'PRBS13Q', 'PRBS15Q', 'PRBS23Q', 'PRBS31Q', 'SSPRQ'], case_sensitive=False),
              default='none',
              help='PRBS pattern (optional)')
@click.pass_context
def enable(ctx, interface_name, mode, pattern):
    """Enable PRBS on an interface"""
    config_db = ctx.obj['config_db']
    
    # Normalize interface name if using alias
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = clicommon.iface_alias_converter.alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("Invalid interface name")
    
    # Validate interface exists in PORT table
    port_table = config_db.get_table('PORT')
    if interface_name not in port_table:
        ctx.fail(f"Interface {interface_name} does not exist")
    
    if not validate_mode(mode):
        ctx.fail(f"Invalid mode: {mode}")
    mode = mode.lower()

    # Check against platform-supported patterns from STATE_DB
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

    # Check if PRBS is already enabled
    port_config = port_table.get(interface_name, {})
    current_mode = port_config.get('prbs_mode', 'disabled')
    
    if current_mode in ['rx', 'tx', 'both']:
        ctx.fail(f"PRBS is already enabled on {interface_name} in '{current_mode}' mode. "
                 f"Please disable first using 'config interface prbs disable {interface_name}' "
                 f"to capture results, then re-enable with new settings.")
    
    entry = {'prbs_mode': mode}
    if pattern.lower() != 'none':
        entry['prbs_pattern'] = pattern
    config_db.mod_entry('PORT', interface_name, entry)
    
    click.echo(f"PRBS enabled on {interface_name} (mode={mode}, pattern={pattern})")
    click.echo(f"Note: PRBS test is now running. Use 'config interface prbs disable {interface_name}' to stop and capture results.")


@prbs.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def disable(ctx, interface_name):
    """Disable PRBS on an interface and capture results"""
    config_db = ctx.obj['config_db']
    
    # Normalize interface name if using alias
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = clicommon.iface_alias_converter.alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("Invalid interface name")
    
    # Validate interface exists in PORT table
    port_table = config_db.get_table('PORT')
    if interface_name not in port_table:
        ctx.fail(f"Interface {interface_name} does not exist")
    
    # Check if PRBS is currently enabled
    port_config = port_table.get(interface_name, {})
    current_mode = port_config.get('prbs_mode', 'disabled')
    
    if current_mode not in ['rx', 'tx', 'both']:
        click.echo(f"PRBS is not enabled on {interface_name}")
        return
    
    # Update config DB with prbs_mode as 'disabled' (do not clear the entry)
    config_db.mod_entry('PORT', interface_name, {
        'prbs_mode': 'disabled'
    })
    
    click.echo(f"PRBS disabled on {interface_name}")
    click.echo(f"Results captured and stored. Use 'show interface prbs status -i {interface_name}' to view.")
