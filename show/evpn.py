# CLI file to have these commands fetched from FRR
#
# show evpn
# show evpn es
# show evpn es-evi
# show evpn es-evi detail
# show evpn es 01:02:03:04:05:06:07:08:09:0a
# show evpn l2-nh

import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate
import utilities_common.bgp_util as bgp_util

#
# 'evpn' command ("show evpn")
#
@click.group(invoke_without_command=True)
@clicommon.pass_db
@click.pass_context
def evpn(ctx, db):
    """Show evpn related information"""
    if ctx.invoked_subcommand is None:
        cmd = "show evpn"
        output = bgp_util.run_bgp_show_command(cmd)
        print(output)

@evpn.command()
@click.argument('es', required=False)
def es(es):
    """Show evpn es """
    cmd = "show evpn es"

    if es is not None:
        cmd += " {}".format(es)

    output = bgp_util.run_bgp_show_command(cmd)
    print(output)

@evpn.group(invoke_without_command=True)
@click.argument('vni', required=False, metavar='<vni>')
def es_evi(vni):
    """Show Ethernet Segment per EVI information"""
    """"show evpn es-evi <vni>"""
    cmd = "show evpn es-evi"
    if vni is not None:
        cmd += " vni {}".format(vni)

    output = bgp_util.run_bgp_show_command(cmd)
    print(output)

@es_evi.command()
def detail():
    """Show Ethernet Segment per EVI detail"""
    cmd = "show evpn es-evi detail"
    output = bgp_util.run_bgp_show_command(cmd)
    print(output)

@evpn.group(name='l2-nh', invoke_without_command=True)
def l2_nh():
    """Show evpn Layer2 nexthops"""
    cmd = "show evpn l2-nh"

    output = bgp_util.run_bgp_show_command(cmd)
    print(output)
