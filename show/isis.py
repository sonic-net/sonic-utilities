import click
import sys
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic


def run_vtysh_command(vtysh_cmd, namespace=None):
    """Run vtysh command in the correct namespace"""
    cmd = ['sudo', 'vtysh']
    if namespace and namespace != multi_asic.DEFAULT_NAMESPACE:
        asic_id = multi_asic.get_asic_id_from_name(namespace)
        if asic_id is not None:
            cmd += ['-n', str(asic_id)]
    cmd += ['-c', vtysh_cmd]

    output, ret = clicommon.run_command(cmd, return_cmd=True)
    return output


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
def database(json_format, namespace):
    """Show IS-IS database"""
    cmd = "show isis database"
    if json_format:
        cmd += " json"
    output = run_vtysh_command(cmd, namespace)
    click.echo(output.rstrip('\n'))
