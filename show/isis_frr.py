import click

import utilities_common.bgp_util as bgp_util
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import ConfigDBConnector


###############################################################################
#
# 'show isis' cli stanza
#
############################################################################### 

def get_interfaces():
    """Get list of interfaces 
    """
    tables = ['LOOPBACK_INTERFACE', 'PORT', 'PORTCHANNEL']
    data = []

    config_db = ConfigDBConnector()
    config_db.connect()

    for table_name in tables:
        interface_list = list(config_db.get_table(table_name).keys())
        interface_list = [x for x in interface_list if isinstance(x, str)]
        data += natsorted(interface_list)
    return data

INTERFACE_LIST = get_interfaces()

def invalid_arg(input:str):
    if input == '?':
        ctx = click.get_current_context()
        ctx.fail('The argument: "{}" is invalid. Try "-?".'.format(input))

@click.group(cls=clicommon.AliasedGroup, name="isis")
def isis():
    """Show ISIS (Intermediate System to Intermediate System) information"""
    pass


# 'neighbors' subcommand ("show isis neighbors")
@isis.command()
@click.argument('system_id', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def neighbors(system_id, verbose):
    """Show ISIS neighbors"""

    command = 'show isis neighbor'
    if system_id is not None:
        invalid_arg(system_id)
        command += ' {}'.format(system_id)
    elif verbose:
        command += ' detail'

    output = ""
    output += bgp_util.run_bgp_show_command(command)

    click.echo(output.rstrip('\n'))

# 'database' subcommand ("show isis database")
@isis.command()
@click.argument('lsp_id', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def database(lsp_id, verbose):
    """Show ISIS database"""

    command = 'show isis database'
    if verbose:
        command += ' detail'
    if lsp_id is not None:
        invalid_arg(lsp_id)
        command += ' {0}'.format(lsp_id)

    output = ""
    output += bgp_util.run_bgp_show_command(command)

    click.echo(output.rstrip('\n'))

# 'hostname' subcommand ("show isis hostname")
@isis.command()
def hostname():
    """Show ISIS hostname"""

    command = 'show isis hostname'

    output = ""
    output += bgp_util.run_bgp_show_command(command)

    click.echo(output.rstrip('\n'))

# 'interface' subcommand ("show isis interface")
@isis.command()
@click.argument('interface',
                metavar='[INTERFACE]',
                type=click.Choice(
                    INTERFACE_LIST),
                required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--display', is_flag=True, help=f"Display available [INTERFACE] options:\n{INTERFACE_LIST}")
def interface(interface, verbose, display):
    """Show ISIS interface"""

    if display:
        d = f"[INTERFACE] options: {INTERFACE_LIST}"
        click.echo(d.rstrip('\n'))

    command = 'show isis interface'

    if interface is not None:
        command += ' {0}'.format(interface)
    elif verbose:
        command += ' detail'

    output = ""
    output += bgp_util.run_bgp_show_command(command)

    click.echo(output.rstrip('\n'))

# 'topology' subcommand ("show isis topology")
@isis.command()
@click.option('--level-1', is_flag=True, help="Show IS-IS level-1 information")
@click.option('--level-2', is_flag=True, help="Show IS-IS level-2 information")
def topology(level_1, level_2):
    """Show ISIS topology"""

    command = 'show isis topology'

    if level_1:
        command += ' level-1'
    elif level_2:
        command += ' level-2'

    output = ""
    output += bgp_util.run_bgp_show_command(command)

    click.echo(output.rstrip('\n'))

# 'summary' subcommand ("show isis summary") 
@isis.command()
def summary():
    """Show ISIS summary"""

    command = 'show isis summary'

    output = ""
    output += bgp_util.run_bgp_show_command(command)

    click.echo(output.rstrip('\n'))
