import click
import utilities_common.cli as clicommon


@click.group(cls=clicommon.AliasedGroup)
def gearbox():
    """Show gearbox info"""
    pass

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
    clicommon.run_command(['gearboxutil', 'phys', 'status'])

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
    clicommon.run_command(['gearboxutil', 'interfaces', 'status'])
