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
@click.option('--vrf', required=False)
@click.pass_context
def bgp(ctx, vrf):
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    ctx.ensure_object(dict)
    ctx.obj = {'vrf': vrf}


# 'summary' subcommand ("show ipv6 bgp summary")
@bgp.command()
@multi_asic_util.multi_asic_click_options
@click.pass_context
def summary(ctx, namespace, display):
    """Show summarized information of IPv6 BGP state"""
    vrf = ctx.obj.get('vrf', None)

    if vrf:
        bgp_summary = bgp_util.get_bgp_summary_from_per_vrf_instance(
            constants.IPV4, namespace, display, vrf)
    else:
        bgp_summary = bgp_util.get_bgp_summary_from_all_bgp_instances(constants.IPV6, namespace,display)
    bgp_util.display_bgp_summary(bgp_summary=bgp_summary, af=constants.IPV6)


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
@click.pass_context
def neighbors(ctx, ipaddress, info_type, namespace):
    """Show IPv6 BGP neighbors"""

    command = 'show bgp ipv6'
    vrf = ctx.obj.get('vrf', None)
    if vrf:
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
    command += ' neighbor {} {}'.format(
        ipaddress, info_type)

    ns_list = multi_asic.get_namespace_list(namespace)
    output = ""
    for ns in ns_list:
        output += bgp_util.run_bgp_show_command(command, ns)
    
    click.echo(output.rstrip('\n'))


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
@click.pass_context
def network(ctx, ipaddress, info_type, namespace):
    """Show BGP ipv6 network"""

    command = 'show bgp ipv6'
    vrf = ctx.obj.get('vrf', None)
    if vrf:
        command += ' vrf {}'.format(vrf)

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
