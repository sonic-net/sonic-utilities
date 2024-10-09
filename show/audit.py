import click
import utilities_common.cli as clicommon


AUDIT_CONFIG_DIR = "/etc/audit/rules.d/"
#
# 'audit' group ("show audit")
#
@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
def audit():
    """Show all current active audit rules"""
    click.echo("List of current .rules files in {} directory".format(AUDIT_CONFIG_DIR))
    cmd = ["sudo", "ls", AUDIT_CONFIG_DIR]
    clicommon.run_command(cmd)
    click.echo("\nList of all current active audit rules")
    cmd = ["sudo", "auditctl", "-l"]
    clicommon.run_command(cmd)
