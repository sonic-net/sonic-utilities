import click
from clear.main import ipv6, run_command


###############################################################################
#
# 'clear ipv6 bgp' cli stanza
#
###############################################################################


@ipv6.group()
def bgp():
    """Clear IPv6 BGP (Border Gateway Protocol) information"""
    pass

@bgp.group()
def neighbor():
    """Clear specific BGP peers"""
    pass

# 'all' subcommand
@neighbor.command('all')
@click.argument('ipaddress', required=False)
def neigh_all(ipaddress):
    """Clear all BGP peers"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 {}".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 *"]
    run_command(command)

# 'in' subcommand
@neighbor.command('in')
@click.argument('ipaddress', required=False)
def neigh_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 {} in".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 * in"]
    run_command(command)


# 'out' subcommand
@neighbor.command('out')
@click.argument('ipaddress', required=False)
def neigh_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 {} out".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 * out"]
    run_command(command)


@neighbor.group()
def soft():
    """Soft reconfig BGP's inbound/outbound updates"""
    pass

# 'soft in' subcommand
@soft.command('in')
@click.argument('ipaddress', required=False)
def soft_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 {} soft in".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 * soft in"]
    run_command(command)


# 'soft all' subcommand
@soft.command('all')
@click.argument('ipaddress', required=False)
def soft_all(ipaddress):
    """Clear BGP neighbors soft configuration"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 {} soft".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 * soft"]
    run_command(command)

# 'soft out' subcommand
@soft.command('out')
@click.argument('ipaddress', required=False)
def soft_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 {} soft out".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear bgp ipv6 * soft out"]
    run_command(command)
