import click
import utilities_common.cli as clicommon


#
# 'nat' group ("show nat ...")
#

@click.group(cls=clicommon.AliasedGroup)
def nat():
    """Show details of the nat """
    pass


# 'statistics' subcommand ("show nat statistics")
@nat.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def statistics(verbose):
    """ Show NAT statistics """

    cmd = ['sudo', 'natshow', '-s']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'translations' subcommand ("show nat translations")
@nat.group(invoke_without_command=True)
@click.pass_context
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def translations(ctx, verbose):
    """ Show NAT translations """

    if ctx.invoked_subcommand is None:
        cmd = ['sudo', 'natshow', '-t']
        clicommon.run_command(cmd, display_cmd=verbose)


# 'count' subcommand ("show nat translations count")
@translations.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def count(verbose):
    """ Show NAT translations count """

    cmd = ['sudo', 'natshow', '-c']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'config' subcommand ("show nat config")
@nat.group(invoke_without_command=True)
@click.pass_context
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def config(ctx, verbose):
    """Show NAT config related information"""
    if ctx.invoked_subcommand is None:
        click.echo("\nGlobal Values")
        cmd = ['sudo', 'natconfig', '-g']
        clicommon.run_command(cmd, display_cmd=verbose)

        click.echo("Static Entries")
        cmd = ['sudo', 'natconfig', '-s']
        clicommon.run_command(cmd, display_cmd=verbose)

        click.echo("Pool Entries")
        cmd = ['sudo', 'natconfig', '-p']
        clicommon.run_command(cmd, display_cmd=verbose)

        click.echo("NAT Bindings")
        cmd = ['sudo', 'natconfig', '-b']
        clicommon.run_command(cmd, display_cmd=verbose)

        click.echo("NAT Zones")
        cmd = ['sudo', 'natconfig', '-z']
        clicommon.run_command(cmd, display_cmd=verbose)


# 'static' subcommand  ("show nat config static")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def static(verbose):
    """Show static NAT configuration"""

    cmd = ['sudo', 'natconfig', '-s']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'pool' subcommand  ("show nat config pool")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def pool(verbose):
    """Show NAT Pool configuration"""

    cmd = ['sudo', 'natconfig', '-p']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'bindings' subcommand  ("show nat config bindings")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def bindings(verbose):
    """Show NAT binding configuration"""

    cmd = ['sudo', 'natconfig', '-b']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'globalvalues' subcommand  ("show nat config globalvalues")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def globalvalues(verbose):
    """Show NAT Global configuration"""

    cmd = ['sudo', 'natconfig', '-g']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'zones' subcommand  ("show nat config zones")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def zones(verbose):
    """Show NAT Zone configuration"""

    cmd = ['sudo', 'natconfig', '-z']
    clicommon.run_command(cmd, display_cmd=verbose)
