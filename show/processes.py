import click
import utilities_common.cli as clicommon


#
# 'processes' group ("show processes ...")
#

@click.group(cls=clicommon.AliasedGroup)
def processes():
    """Show process information"""
    pass


@processes.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def summary(verbose):
    """Show processes info"""
    # Run top batch mode to prevent unexpected newline after each newline
    cmd = ['ps', '-eo', 'pid,ppid,cmd,%mem,%cpu']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'cpu' subcommand ("show processes cpu")
@processes.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def cpu(verbose):
    """Show processes CPU info"""
    # Run top in batch mode to prevent unexpected newline after each newline
    cmd = ['top', '-bn', '1', '-o', '%CPU']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'memory' subcommand
@processes.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def memory(verbose):
    """Show processes memory info"""
    # Run top batch mode to prevent unexpected newline after each newline
    cmd = ['top', '-bn', '1', '-o', '%MEM']
    clicommon.run_command(cmd, display_cmd=verbose)
