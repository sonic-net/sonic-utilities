import click
import utilities_common.cli as clicommon


@click.group(cls=clicommon.AliasedGroup)
def srv6():
    """Show SRv6 related information"""
    pass


# 'stats' subcommand  ("show srv6 stats")
@srv6.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('sid', required=False)
def stats(verbose, sid):
    """Show SRv6 counter statistic"""
    cmd = ['srv6stat']
    if sid:
        cmd += ['-s', sid]
    clicommon.run_command(cmd, display_cmd=verbose)
