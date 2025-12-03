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

@neighbor.command('all')
@click.argument('ipaddress', required=False)
def neigh_all(ipaddress):
    """Clear all BGP peers"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp {}".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp *"]
    run_command(command)


# 'in' subcommand
@neighbor.command('in')
@click.argument('ipaddress', required=False)
def neigh_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp {} in".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp * in"]
    run_command(command)


# 'out' subcommand
@neighbor.command('out')
@click.argument('ipaddress', required=False)
def neigh_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', 'clear ipv6 bgp {} out'.format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', 'clear ipv6 bgp * out']
    run_command(command)


@neighbor.group()
def soft():
    """Soft reconfig BGP's inbound/outbound updates"""
    pass


@soft.command('all')
@click.argument('ipaddress', required=False)
def soft_all(ipaddress):
    """Clear BGP neighbors soft configuration"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp {} soft".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp * soft"]
    run_command(command)


# 'soft in' subcommand
@soft.command('in')
@click.argument('ipaddress', required=False)
def soft_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp {} soft in".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp * soft in"]
    run_command(command)


# 'soft out' subcommand
@soft.command('out')
@click.argument('ipaddress', required=False)
def soft_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = ['sudo' ,'vtysh' ,'-c', "clear ipv6 bgp {} soft out".format(ipaddress)]
    else:
        command = ['sudo', 'vtysh', '-c', "clear ipv6 bgp * soft out"]
    run_command(command)
