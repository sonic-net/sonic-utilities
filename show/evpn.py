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

ESI_PATTERN = r'^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){9}$'
VNI_MIN = 1
VNI_MAX = 16777215

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
@click.pass_context
def es(ctx, es):
    """Show evpn es """
    cmd = "show evpn es"

    if es:
        if not re.match(ESI_PATTERN, es):
            ctx.fail(f"Invalid ESI format '{es}'. Expected format: XX:XX:XX:XX:XX:XX:XX:XX:XX:XX")
        cmd += " {}".format(es)

    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)


@evpn.command(name='es-evi')
@click.argument('vni', required=False, metavar='<vni|detail>')
@click.pass_context
def es_evi(ctx, vni):
    """Show Ethernet Segment per EVI information"""
    cmd = "show evpn es-evi"
    if vni:
        if vni == 'detail':
            cmd += " detail"
        else:
            # Validate VNI is a positive integer (VXLAN Network Identifier: 1-16777215)
            try:
                vni_int = int(vni)
            except ValueError:
                ctx.fail(f"Invalid VNI '{vni}'. VNI must be a numeric value")
            if vni_int < VNI_MIN or vni_int > VNI_MAX:
                ctx.fail(f"Invalid VNI '{vni}'. VNI must be between {VNI_MIN} and {VNI_MAX}")
            cmd += " vni {}".format(vni)

    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)


@evpn.group(name='l2-nh', invoke_without_command=True)
def l2_nh():
    """Show evpn Layer2 nexthops"""
    cmd = "show evpn l2-nh"

    output = bgp_util.run_bgp_show_command(cmd)
    click.echo(output)
