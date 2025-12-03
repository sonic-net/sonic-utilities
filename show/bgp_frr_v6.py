import click

from sonic_py_common import multi_asic
import utilities_common.cli as clicommon
from show.main import ipv6
import utilities_common.multi_asic as multi_asic_util
import utilities_common.bgp_util as bgp_util
import utilities_common.constants as constants

###############################################################################
#
# 'show ipv6 bgp' cli stanza
#
###############################################################################


@ipv6.group(cls=clicommon.AliasedGroup)
def bgp():
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ipv6 bgp summary")
@bgp.command()
@multi_asic_util.multi_asic_click_options
def summary(namespace, display):
    """Show summarized information of IPv6 BGP state"""
    summary_helper(namespace, display)


# 'neighbors' subcommand ("show ipv6 bgp neighbors")
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
    """Show IPv6 BGP neighbors"""
    neighbors_helper(ipaddress, info_type, namespace)


# 'network' subcommand ("show ipv6 bgp network")
@bgp.command()
@click.argument('ipaddress',
                metavar='[<ipv6-address>|<ipv6-prefix>]',
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
    """Show BGP ipv6 network"""
    network_helper(ipaddress, info_type, namespace)


@bgp.group(cls=clicommon.AliasedGroup)
@click.argument('vrf', required=True)
@click.pass_context
def vrf(ctx, vrf):
    """Show IPv6 BGP information for a given VRF"""
    pass


# 'summary' subcommand ("show ipv6 bgp summary")
@vrf.command('summary')
@multi_asic_util.multi_asic_click_options
@click.pass_context
def vrf_summary(ctx, namespace, display):
    """Show summarized information of IPv6 BGP state"""
    vrf = ctx.parent.params['vrf']
    summary_helper(namespace, display, vrf)


# 'neighbors' subcommand ("show ipv6 bgp vrf neighbors")
@vrf.command('neighbors')
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
@click.pass_context
def vrf_neighbors(ctx, ipaddress, info_type, namespace):
    """Show IPv6 BGP neighbors"""
    vrf = ctx.parent.params['vrf']
    neighbors_helper(ipaddress, info_type, namespace, vrf)


# 'network' subcommand ("show ipv6 bgp network")
@vrf.command('network')
@click.argument('ipaddress',
                metavar='[<ipv6-address>|<ipv6-prefix>]',
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
@click.pass_context
def vrf_network(ctx, ipaddress, info_type, namespace):
    """Show BGP ipv6 network"""
    vrf = ctx.parent.params['vrf']
    network_helper(ipaddress, info_type, namespace, vrf)


def summary_helper(namespace, display, vrf=None):
    bgp_summary = bgp_util.get_bgp_summary_from_all_bgp_instances(constants.IPV6, namespace, display, vrf)
    bgp_util.display_bgp_summary(bgp_summary=bgp_summary, af=constants.IPV6)


def neighbors_helper(ipaddress, info_type, namespace, vrf=None):
    command = 'show bgp'
    if vrf is not None:
        command += ' vrf {}'.format(vrf)

    if ipaddress is not None:
        if not bgp_util.is_ipv6_address(ipaddress):
            ctx = click.get_current_context()
            ctx.fail("{} is not valid ipv6 address\n".format(ipaddress))
        try:
            actual_namespace = bgp_util.get_namespace_for_bgp_neighbor(
                ipaddress)
            if namespace is not None and namespace != actual_namespace:
                click.echo(
                    "bgp neighbor {} is present in namespace {} not in {}"
                    .format(ipaddress, actual_namespace, namespace))

            # save the namespace in which the bgp neighbor is configured
            namespace = actual_namespace
        except ValueError as err:
            ctx = click.get_current_context()
            ctx.fail("{}\n".format(err))
    else:
        ipaddress = ""

    info_type = "" if info_type is None else info_type
    command += ' ipv6 neighbor {} {}'.format(
        ipaddress, info_type)

    ns_list = multi_asic.get_namespace_list(namespace)
    output = ""
    for ns in ns_list:
        output += bgp_util.run_bgp_show_command(command, ns)
    
    click.echo(output.rstrip('\n'))


def network_helper(ipaddress, info_type, namespace, vrf=None):
    command = 'show bgp'
    if vrf is not None:
        command += ' vrf {}'.format(vrf)
    command += ' ipv6'

    if multi_asic.is_multi_asic() and namespace not in multi_asic.get_namespace_list():
        ctx = click.get_current_context()
        ctx.fail('-n/--namespace option required. provide namespace from list {}'\
            .format(multi_asic.get_namespace_list()))

    if ipaddress is not None:
        if '/' in ipaddress:
            # For network prefixes then this all info_type(s) are available
            pass
        else:
            # For an ipaddress then check info_type, exit if specified option doesn't work.
            if info_type in ['longer-prefixes']:
                click.echo('The parameter option: "{}" only available if passing a network prefix'.format(info_type))
                click.echo("EX: 'show ipv6 bgp network fc00:1::/64 longer-prefixes'")
                raise click.Abort()

        command += ' {}'.format(ipaddress)

        # info_type is only valid if prefix/ipaddress is specified
        if info_type is not None:
            command += ' {}'.format(info_type)

    output  =  bgp_util.run_bgp_show_command(command, namespace)
    click.echo(output.rstrip('\n'))
