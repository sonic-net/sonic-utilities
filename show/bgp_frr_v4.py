import click
import sys
import subprocess

from sonic_py_common import multi_asic, device_info
from show.main import ip
import utilities_common.bgp_util as bgp_util
import utilities_common.cli as clicommon
import utilities_common.constants as constants
import utilities_common.multi_asic as multi_asic_util

###############################################################################
#
# 'show ip bgp' cli stanza
#
###############################################################################


@ip.group(cls=clicommon.AliasedGroup)
def bgp():
    """Show IPv4 BGP (Border Gateway Protocol) information"""
    if device_info.is_supervisor():
        # if the device is a chassis, the command need to be executed by rexec
        click.echo("Since the current device is a chassis supervisor, " +
                   "this command will be executed remotely on all linecards")
        proc = subprocess.run(["rexec", "all"] + ["-c", " ".join(sys.argv)])
        sys.exit(proc.returncode)
    pass


# 'summary' subcommand ("show ip bgp summary")
@bgp.command()
@multi_asic_util.multi_asic_click_options
def summary(namespace, display):
    bgp_summary = bgp_util.get_bgp_summary_from_all_bgp_instances(
        constants.IPV4, namespace, display)
    bgp_util.display_bgp_summary(bgp_summary=bgp_summary, af=constants.IPV4)


# 'neighbors' subcommand ("show ip bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=False)
@click.argument('info_type',
                type=click.Choice(
                    ['routes', 'advertised-routes', 'received-routes']),
                required=False)
@click.option('--namespace',
                '-n',
                'namespace',
                default=None,
                type=str,
                show_default=True,
                help='Namespace name or all',
                callback=multi_asic_util.multi_asic_namespace_validation_callback)
def neighbors(ipaddress, info_type, namespace):
    """Show IP (IPv4) BGP neighbors"""

    command = 'show ip bgp neighbor'
    if ipaddress is not None:
        if not bgp_util.is_ipv4_address(ipaddress):
            ctx = click.get_current_context()
            ctx.fail("{} is not valid ipv4 address\n".format(ipaddress))
        try:
            actual_namespace = bgp_util.get_namespace_for_bgp_neighbor(
                ipaddress)
            if namespace is not None and namespace != actual_namespace:
                click.echo(
                    "[WARNING]: bgp neighbor {} is present in namespace {} not in {}"
                    .format(ipaddress, actual_namespace, namespace))

            # save the namespace in which the bgp neighbor is configured
            namespace = actual_namespace

            command += ' {}'.format(ipaddress)

            # info_type is only valid if ipaddress is specified
            if info_type is not None:
                command += ' {}'.format(info_type)
        except ValueError as err:
            ctx = click.get_current_context()
            ctx.fail("{}\n".format(err))

    ns_list = multi_asic.get_namespace_list(namespace)
    output = ""
    for ns in ns_list:
        output += bgp_util.run_bgp_show_command(command, ns)

    click.echo(output.rstrip('\n'))


# 'network' subcommand ("show ip bgp network")
@bgp.command()
@click.argument('ipaddress',
                metavar='[<ipv4-address>|<ipv4-prefix>]',
                required=False)
@click.argument('info_type',
                metavar='[bestpath|json|longer-prefixes|multipath]',
                type=click.Choice(
                    ['bestpath', 'json', 'longer-prefixes', 'multipath']),
                required=False)
@click.option('--namespace',
                '-n',
                'namespace',
                type=str,
                show_default=True,
                required=True if multi_asic.is_multi_asic is True else False,
                help='Namespace name or all',
                default=multi_asic.DEFAULT_NAMESPACE,
                callback=multi_asic_util.multi_asic_namespace_validation_callback)
def network(ipaddress, info_type, namespace):
    """Show IP (IPv4) BGP network"""

    namespace = namespace.strip()
    if multi_asic.is_multi_asic():
        if namespace == multi_asic.DEFAULT_NAMESPACE:
            ctx = click.get_current_context()
            ctx.fail('-n/--namespace option required. provide namespace from list {}'
                     .format(multi_asic.get_namespace_list()))
        if namespace != "all" and namespace not in multi_asic.get_namespace_list():
            ctx = click.get_current_context()
            ctx.fail('invalid namespace {}. provide namespace from list {}'
                     .format(namespace, multi_asic.get_namespace_list()))

    command = 'show ip bgp'
    if ipaddress is not None:
        if '/' in ipaddress:
            # For network prefixes then this all info_type(s) are available
            pass
        else:
            # For an ipaddress then check info_type, exit if specified option doesn't work.
            if info_type in ['longer-prefixes']:
                click.echo('The parameter option: "{}" only available if passing a network prefix'.format(info_type))
                click.echo("EX: 'show ip bgp network 10.0.0.0/24 longer-prefixes'")
                raise click.Abort()

        command += ' {}'.format(ipaddress)

        # info_type is only valid if prefix/ipaddress is specified
        if info_type is not None:
            command += ' {}'.format(info_type)

    if namespace == "all":
        if multi_asic.is_multi_asic():
            for ns in multi_asic.get_namespace_list():
                click.echo("\n======== namespace {} ========".format(ns))
                output = bgp_util.run_bgp_show_command(command, ns)
                click.echo(output.rstrip('\n'))
        else:
            output = bgp_util.run_bgp_show_command(command, "")
            click.echo(output.rstrip('\n'))
    else:
        output = bgp_util.run_bgp_show_command(command, namespace)
        click.echo(output.rstrip('\n'))
