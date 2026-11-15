import os

import click
import utilities_common.cli as clicommon


def _run_acl_show(command, verbose):
    if os.geteuid() != 0:
        command = ['/usr/bin/sudo', '-n', '/usr/local/bin/acl-loader', *command[1:]]
    clicommon.run_command(command, display_cmd=verbose)


#
# 'acl' group ###
#

@click.group(cls=clicommon.AliasedGroup)
def acl():
    """Show ACL related information"""
    pass


# 'rule' subcommand  ("show acl rule")
@acl.command()
@click.argument('table_name', required=False)
@click.argument('rule_id', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def rule(table_name, rule_id, verbose):
    """Show existing ACL rules"""
    cmd = ['acl-loader', 'show', 'rule']

    if table_name is not None:
        cmd += ['--', str(table_name)]

    if rule_id is not None:
        cmd += [str(rule_id)]

    _run_acl_show(cmd, verbose)


# 'table' subcommand  ("show acl table")
@acl.command()
@click.argument('table_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def table(table_name, verbose):
    """Show existing ACL tables"""
    cmd = ['acl-loader', 'show', 'table']

    if table_name is not None:
        cmd += ['--', str(table_name)]

    _run_acl_show(cmd, verbose)
