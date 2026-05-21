import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util

from tabulate import tabulate

from flow_counter_util.route import FLOW_COUNTER_ROUTE_PATTERN_TABLE, FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD, FLOW_COUNTER_ROUTE_CONFIG_HEADER, DEFAULT_MAX_MATCH
from flow_counter_util.route import extract_route_pattern, exit_if_route_flow_counter_not_support

#
# 'flowcnt-trap' group ###
#

@click.group(cls=clicommon.AliasedGroup)
def flowcnt_trap():
    """Show trap flow counter related information"""
    pass

@flowcnt_trap.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
def stats(verbose, namespace):
    """Show trap flow counter statistic"""
    cmd = ['flow_counters_stat', '-t', 'trap']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    clicommon.run_command(cmd, display_cmd=verbose)

#
# 'flowcnt-route' group ###
#

@click.group(cls=clicommon.AliasedGroup)
def flowcnt_route():
    """Show route flow counter related information"""
    exit_if_route_flow_counter_not_support()


@flowcnt_route.command()
@clicommon.pass_db
def config(db):
    """Show route flow counter configuration"""
    route_pattern_table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
    data = []
    for key, entry in route_pattern_table.items():
        vrf, prefix = extract_route_pattern(key)
        max = entry.get(FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD, str(DEFAULT_MAX_MATCH))
        data.append([prefix, vrf, max])

    click.echo(tabulate(data, headers=FLOW_COUNTER_ROUTE_CONFIG_HEADER, tablefmt="simple", missingval=""))


@flowcnt_route.group(invoke_without_command=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
@click.pass_context
def stats(ctx, verbose, namespace):
    """Show statistics of all route flow counters"""
    if ctx.invoked_subcommand is None:
        command = ['flow_counters_stat', '-t', 'route']
        if namespace is not None:
            command += ['-n', str(namespace)]
        clicommon.run_command(command, display_cmd=verbose)


@stats.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--vrf', help='VRF/VNET name or default VRF')
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
@click.argument('prefix-pattern', required=True)
def pattern(prefix_pattern, vrf, verbose, namespace):
    """Show statistics of route flow counters by pattern"""
    command = ['flow_counters_stat', '-t', 'route', '--prefix_pattern', str(prefix_pattern)]
    if vrf:
        command += ['--vrf', str(vrf)]
    if namespace is not None:
        command += ['-n', str(namespace)]
    clicommon.run_command(command, display_cmd=verbose)


@stats.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--vrf', help='VRF/VNET name or default VRF')
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
@click.argument('prefix', required=True)
def route(prefix, vrf, verbose, namespace):
    """Show statistics of route flow counters by prefix"""
    command = ['flow_counters_stat', '-t', 'route', '--prefix', str(prefix)]
    if vrf:
        command += ['--vrf', str(vrf)]
    if namespace is not None:
        command += ['-n', str(namespace)]
    clicommon.run_command(command, display_cmd=verbose)
