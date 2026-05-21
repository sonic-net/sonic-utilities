import click
import utilities_common.cli as clicommon


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
        cmd += [str(table_name)]

    if rule_id is not None:
        cmd += [str(rule_id)]

    clicommon.run_command(cmd, display_cmd=verbose)


# 'table' subcommand  ("show acl table")
@acl.command()
@click.argument('table_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def table(table_name, verbose):
    """Show existing ACL tables"""
    cmd = ['acl-loader', 'show', 'table']

    if table_name is not None:
        cmd += [str(table_name)]

    clicommon.run_command(cmd, display_cmd=verbose)
