import click
from show.main import ip, run_command
from utilities_common.bgp_util import get_bgp_summary_extended
import utilities_common.constants as constants
import utilities_common.cli as clicommon


###############################################################################
#
# 'show ip bgp' cli stanza
#
###############################################################################


@ip.group(cls=clicommon.AliasedGroup)
def bgp():
    """Show IPv4 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ip bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv4 BGP state"""
    try:
        device_output = run_command(['sudo', constants.RVTYSH_COMMAND, '-c', "show ip bgp summary"], return_cmd=True)
        get_bgp_summary_extended(device_output)
    except Exception:
        run_command(['sudo', constants.RVTYSH_COMMAND, '-c', "show ip bgp summary"])


# 'neighbors' subcommand ("show ip bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=False)
@click.argument('info_type', type=click.Choice(['routes', 'advertised-routes', 'received-routes']), required=False)
def neighbors(ipaddress, info_type):
    """Show IP (IPv4) BGP neighbors"""

    command = ['sudo', constants.RVTYSH_COMMAND, '-c', "show ip bgp neighbor"]

    if ipaddress is not None:
        command[-1] += ' {}'.format(ipaddress)

        # info_type is only valid if ipaddress is specified
        if info_type is not None:
            command[-1] += ' {}'.format(info_type)

    run_command(command)
