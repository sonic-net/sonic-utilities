import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate
import utilities_common.bgp_util as bgp_util

#
# 'evpn' command ("show evpn")
#
@click.group(cls=clicommon.AliasedGroup)
def evpn():
    """Show evpn related information"""
    pass

@evpn.command()
@click.argument('es', required=False)
def es(es):
    """Show evpn es """
    cmd = "show evpn es"

    if es is not None:
        cmd += " {}".format(es)

    output = bgp_util.run_bgp_show_command(cmd)
    print(output)

@evpn.command()
@click.argument('es_evi', required=False)
def es_evi(es_evi):
    """Show evpn Ethernet Segment per EVI information"""
    cmd = "show evpn es-evi"

    if es_evi is not None:
        cmd += " {}".format(es_evi)

    output = bgp_util.run_bgp_show_command(cmd)
    print(output)

