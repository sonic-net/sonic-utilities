import click
import utilities_common.cli as clicommon


#
# 'authentication' group ("show authentication ...")
#

@click.group(cls=clicommon.AliasedGroup)
def authentication():
    """Show details of the pac authentication """
    pass


# 'interface' subcommand ("show authentication interface")
@authentication.command('interface')
@click.option('-i', '--interface')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def authentication_interface(interface, verbose):
    """ Show authentication interface """
    if interface is not None:
        if interface.startswith("Ethernet"):
            cmd = ['sudo', 'pacshow', '-t', 'interface', '-i {}'.format(interface)]
            clicommon.run_command(cmd, display_cmd=verbose)
    else:
        cmd = ['sudo', 'pacshow', '-t', 'interface', '-a']
        clicommon.run_command(cmd, display_cmd=verbose)

# 'clients' subcommand ("show authentication clients")
@authentication.command('clients')
@click.option('-i', '--interface')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def authentication_interface(interface, verbose):
    """ Show authentication interface """
    if interface is not None:
        if interface.startswith("Ethernet"):
            cmd = ['sudo', 'pacshow', '-t', 'client', '-i {}'.format(interface)]
            clicommon.run_command(cmd, display_cmd=verbose)
    else:
        cmd = ['sudo', 'pacshow', '-t', 'client', '-a']
        clicommon.run_command(cmd, display_cmd=verbose)


@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
def dot1x():
    """Show details of the 802.1X """
    cmd = ['sudo', 'pacshow', '-t', 'dot1x', '-a']
    clicommon.run_command(cmd)

@click.group(cls=clicommon.AliasedGroup)
def mab():
    """Show details of the MAB """
    pass

# 'interface' subcommand ("show mab interface")
@mab.command('interface')
@click.option('-i', '--interface')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def mab_interface(interface, verbose):
    """ Show mab interface """
    if interface is not None:
        if interface.startswith("Ethernet"):
            cmd = ['sudo', 'pacshow', '-t', 'mab', '-i {}'.format(interface)]
            clicommon.run_command(cmd, display_cmd=verbose)
    else:
        cmd = ['sudo', 'pacshow', '-t', 'mab', '-a']
        clicommon.run_command(cmd, display_cmd=verbose)
