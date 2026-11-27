import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util


@click.group(cls=clicommon.AliasedGroup)
@multi_asic_util.multi_asic_click_option_namespace(required=True)
def gearbox(namespace):
    """Show gearbox info"""
    pass


def _run_gearboxutil(group, command, port_name=None):
    namespace = multi_asic_util.get_namespace_from_ctx()
    cmd = ['gearboxutil']
    if namespace is not None:
        cmd += ['-n', namespace]
    cmd += [group, command]
    if port_name:
        cmd.append(port_name)
    clicommon.run_command(cmd)


# 'phys' subcommand ("show gearbox phys")
@gearbox.group(cls=clicommon.AliasedGroup)
def phys():
    """Show external PHY information"""
    pass

# 'status' subcommand ("show gearbox phys status")
@phys.command()
@click.pass_context
def status(ctx):
    """Show gearbox phys status"""
    _run_gearboxutil('phys', 'status')

# 'interfaces' subcommand ("show gearbox interfaces")
@gearbox.group(cls=clicommon.AliasedGroup)
def interfaces():
    """Show gearbox interfaces information"""
    pass

# 'status' subcommand ("show gearbox interfaces status")
@interfaces.command()
@click.pass_context
def status(ctx):
    """Show gearbox interfaces status"""
    _run_gearboxutil('interfaces', 'status')


# 'fec-stats' subcommand ("show gearbox interfaces fec-stats")
@interfaces.command('fec-stats')
@click.argument('port_name', required=False)
@click.pass_context
def fec_stats(ctx, port_name):
    """Show gearbox interfaces FEC statistics"""
    _run_gearboxutil('interfaces', 'fec-stats', port_name)


# 'fec-histogram' subcommand ("show gearbox interfaces fec-histogram")
@interfaces.command('fec-histogram')
@click.argument('port_name', required=False)
@click.pass_context
def fec_histogram(ctx, port_name):
    """Show gearbox interfaces FEC codeword error histogram"""
    _run_gearboxutil('interfaces', 'fec-histogram', port_name)
