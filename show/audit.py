import click
import utilities_common.cli as clicommon


#
# 'audit' group ("show audit")
#
@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
def audit():
    """Show details of the audit enhancement"""
    cmd = ['sudo', 'auditctl', '-l']
    clicommon.run_command(cmd)
