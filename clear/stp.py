import click
import utilities_common.cli as clicommon

#
# This group houses Spanning_tree commands and subgroups
#

# Adding support for MSTP parameters here

@click.group(cls=clicommon.AliasedGroup)
@click.pass_context
def spanning_tree(ctx):
    '''Clear Spanning-tree counters'''
    pass


@spanning_tree.group('statistics', cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def stp_clr_stats(ctx):
    if ctx.invoked_subcommand is None:
        command = 'sudo stpctl clrstsall'
        clicommon.run_command(command)


@stp_clr_stats.command('interface')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def stp_clr_stats_intf(ctx, interface_name):
    command = 'sudo stpctl clrstsintf ' + interface_name
    clicommon.run_command(command)


@stp_clr_stats.command('vlan')
@click.argument('vlan_id', metavar='<vlan_id>', required=True)
@click.pass_context
def stp_clr_stats_vlan(ctx, vlan_id):
    command = 'sudo stpctl clrstsvlan ' + vlan_id
    clicommon.run_command(command)


@stp_clr_stats.command('vlan-interface')
@click.argument('vlan_id', metavar='<vlan_id>', required=True)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def stp_clr_stats_vlan_intf(ctx, vlan_id, interface_name):
    command = 'sudo stpctl clrstsvlanintf ' + vlan_id + ' ' + interface_name
    clicommon.run_command(command)
