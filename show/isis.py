import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from utilities_common import bgp_util


def run_vtysh_command(vtysh_cmd, namespace=None):
    """Use the routing-stack-aware wrapper and shared namespace/error handling."""
    return bgp_util.run_bgp_command(vtysh_cmd, namespace, bgp_util.get_vtysh_shell_cmd())


@click.group(
    name="isis",
    cls=clicommon.AliasedGroup
)
def isis():
    """Show IS-IS routing protocol information"""
    pass


@isis.command()
@click.option('-j', '--json', 'json_format', is_flag=True, help="Display in JSON format")
@click.option('--namespace', '-n', default=None, type=str,
              help='Namespace name',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def summary(json_format, namespace):
    """Show IS-IS summary"""
    cmd = "show isis summary"
    if json_format:
        cmd += " json"
    output = run_vtysh_command(cmd, namespace)
    click.echo(output.rstrip('\n'))


@isis.command()
@click.option('-j', '--json', 'json_format', is_flag=True, help="Display in JSON format")
@click.option('--namespace', '-n', default=None, type=str,
              help='Namespace name',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def neighbor(json_format, namespace):
    """Show IS-IS neighbors"""
    cmd = "show isis neighbor"
    if json_format:
        cmd += " json"
    output = run_vtysh_command(cmd, namespace)
    click.echo(output.rstrip('\n'))


@isis.command()
@click.option('-j', '--json', 'json_format', is_flag=True, help="Display in JSON format")
@click.option('--namespace', '-n', default=None, type=str,
              help='Namespace name',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
@click.argument("detail", required=False, type=click.Choice(["detail"]))
def database(json_format, namespace, detail):
    """Show IS-IS database"""
    cmd = "show isis database" + (" detail" if detail else "")
    if json_format:
        cmd += " json"
    output = run_vtysh_command(cmd, namespace)
    click.echo(output.rstrip('\n'))


@isis.command()
@click.option('-j', '--json', 'json_format', is_flag=True, help="Display in JSON format")
@click.option('--namespace', '-n', default=None, type=str,
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def interface(json_format, namespace):
    """Show IS-IS interface configuration and state"""
    cmd = 'show isis interface' + (' json' if json_format else '')
    click.echo(run_vtysh_command(cmd, namespace).rstrip('\n'))
