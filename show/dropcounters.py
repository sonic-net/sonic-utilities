import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util


#
# 'dropcounters' group ###
#

@click.group(cls=clicommon.AliasedGroup)
def dropcounters():
    """Show drop counter related information"""
    pass


# 'configuration' subcommand ("show dropcounters configuration")
@dropcounters.command()
@click.option('-g', '--group', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def configuration(group, verbose, namespace):
    """Show current drop counter configuration"""
    cmd = ['dropconfig', '-c', 'show_config']

    if group:
        cmd += ['-g', str(group)]

    if namespace:
        cmd += ['-ns', str(namespace)]

    clicommon.run_command(cmd, display_cmd=verbose)


# 'capabilities' subcommand ("show dropcounters capabilities")
@dropcounters.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def capabilities(verbose, namespace):
    """Show device drop counter capabilities"""
    cmd = ['dropconfig', '-c', 'show_capabilities']

    if namespace:
        cmd += ['-ns', str(namespace)]

    clicommon.run_command(cmd, display_cmd=verbose)


# 'counts' subcommand ("show dropcounters counts")
@dropcounters.command()
@click.option('-g', '--group', required=False)
@click.option('-t', '--counter_type', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@multi_asic_util.multi_asic_click_option_namespace
def counts(group, counter_type, verbose, namespace):
    """Show drop counts"""
    cmd = ['dropstat', '-c', 'show']

    if group:
        cmd += ['-g', str(group)]

    if counter_type:
        cmd += ['-t', str(counter_type)]

    if namespace:
        cmd += ['-n', str(namespace)]

    clicommon.run_command(cmd, display_cmd=verbose)
