# CLI file to have these commands fetched from FRR
#
# show evpn
# show evpn es
# show evpn es-evi
# show evpn es-evi detail
# show evpn es 01:02:03:04:05:06:07:08:09:0a
# show evpn l2-nh

import click
import re
import utilities_common.cli as clicommon
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
        click.echo(output)


@evpn.command()
@click.argument('es', required=False)
def es(es):
    """Show evpn es """
    cmd = "show evpn es"

    if es:
        # Validate ESI format (XX:XX:XX:XX:XX:XX:XX:XX:XX:XX - 10 hex bytes separated by colons)
        esi_pattern = r'^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){9}$'
        if not re.match(esi_pattern, es):
            click.echo(f"Error: Invalid ESI format '{es}'. Expected format: XX:XX:XX:XX:XX:XX:XX:XX:XX:XX")
            return
        cmd += " {}".format(es)

    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)


@evpn.group(invoke_without_command=True)
@click.argument('vni', required=False, metavar='<vni>')
def es_evi(vni):
    """Show Ethernet Segment per EVI information (show evpn es-evi <vni>)"""
    cmd = "show evpn es-evi"
    if vni:
        # Validate VNI is a positive integer (VXLAN Network Identifier: 1-16777215)
        try:
            vni_int = int(vni)
            if vni_int < 1 or vni_int > 16777215:
                click.echo(f"Error: Invalid VNI '{vni}'. VNI must be between 1 and 16777215")
                return
        except ValueError:
            click.echo(f"Error: Invalid VNI '{vni}'. VNI must be a numeric value")
            return
        cmd += " vni {}".format(vni)

    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)


@es_evi.command()
def detail():
    """Show Ethernet Segment per EVI detail"""
    cmd = "show evpn es-evi detail"
    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)


@evpn.group(name='l2-nh', invoke_without_command=True)
def l2_nh():
    """Show evpn Layer2 nexthops"""
    cmd = "show evpn l2-nh"

    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)
