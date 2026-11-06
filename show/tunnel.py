import click
from sonic_py_common import multi_asic
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from swsscommon.swsscommon import SonicV2Connector


#
# 'tunnel' group ("show tunnel ...")
#
@click.group(cls=clicommon.AliasedGroup)
@multi_asic_util.multi_asic_click_option_namespace
def tunnel(namespace):
    """Show tunnel related information"""
    pass


#
# 'counters' subcommand ("show tunnel counters")
#
@tunnel.command()
@click.argument('tunnel_name', required=False)
@click.option('-p', '--period')
@click.option('-T', '--type', 'tunnel_type',
              type=click.Choice(['vxlan', 'ipinip']), required=False,
              help="Show counters for a specific tunnel type")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(tunnel_name, period, tunnel_type, verbose):
    """Show tunnel counters (all tunnel types)"""
    namespace = multi_asic_util.get_namespace_from_ctx()
    ns_list = multi_asic_util.multi_asic_get_ns_list(namespace)

    # On multi-asic, when a tunnel name is given without a namespace, only run
    # tunnelstat in namespaces where that tunnel exists (mirrors 'show vxlan
    # counters'); otherwise tunnelstat would error in namespaces lacking it.
    if multi_asic.is_multi_asic() and namespace is None and tunnel_name is not None:
        filtered = []
        for ns in ns_list:
            db = SonicV2Connector(use_unix_socket_path=False, namespace=ns)
            db.connect(db.COUNTERS_DB)
            name_map = db.get_all(db.COUNTERS_DB, 'COUNTERS_TUNNEL_NAME_MAP')
            if name_map and tunnel_name in name_map:
                filtered.append(ns)
        ns_list = filtered
        if not ns_list:
            click.echo("Tunnel {} not found".format(tunnel_name))
            return

    for ns in ns_list:
        if multi_asic.is_multi_asic() and namespace is None:
            click.echo("\nNamespace: {}".format(ns))

        cmd = ['tunnelstat']
        if tunnel_type is not None:
            cmd += ['-T', tunnel_type]
        if period is not None:
            cmd += ['-p', str(period)]
        if tunnel_name is not None:
            cmd += ['-i', str(tunnel_name)]
        if ns:
            cmd = ['sudo', 'ip', 'netns', 'exec', str(ns)] + cmd

        clicommon.run_command(cmd, display_cmd=verbose)
