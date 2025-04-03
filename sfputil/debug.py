import sys
import click
import utilities_common.cli as clicommon
from utilities_common import platform_sfputil_helper
from utilities_common.platform_sfputil_helper import (
    get_subport,
    get_sfp_object,
    get_subport_lane_mask,
    get_media_lane_count,
    get_host_lane_count,
)

EXIT_FAIL = -1
EXIT_SUCCESS = 0
ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_SFPUTILHELPER_LOAD = 3
ERROR_PORT_CONFIG_LOAD = 4
ERROR_NOT_IMPLEMENTED = 5
ERROR_INVALID_PORT = 6


@click.group(cls=clicommon.AliasedGroup)
def debug():
    """
    Group for debugging and diagnostic control commands.

    This command group loads platform-specific utilities and prepares them for use in diagnostic commands.
    """
    platform_sfputil_helper.load_platform_sfputil()
    platform_sfputil_helper.load_chassis()
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()


@debug.command()
@click.argument('port_name', required=True)
@click.argument(
    'loopback_mode',
    required=True,
    type=click.Choice(["host-side-input", "host-side-output", "media-side-input", "media-side-output"])
)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def loopback(port_name, loopback_mode, enable):
    """
    Set module diagnostic loopback mode.
    """
    sfp = get_sfp_object(port_name)

    try:
        api = sfp.get_xcvr_api()
    except NotImplementedError:
        click.echo(f"{port_name}: This functionality is not implemented")
        sys.exit(ERROR_NOT_IMPLEMENTED)

    subport = get_subport(port_name)

    host_lane_count = get_host_lane_count(port_name)

    media_lane_count = get_media_lane_count(port_name)

    lane_count = int(host_lane_count) if 'host-side' in loopback_mode else int(media_lane_count)
    lane_mask = get_subport_lane_mask(int(subport), lane_count)

    try:
        status = api.set_loopback_mode(loopback_mode, lane_mask=lane_mask, enable=(enable == 'enable'))
    except AttributeError:
        click.echo(f"{port_name}: Set loopback mode is not applicable for this module")
        sys.exit(ERROR_NOT_IMPLEMENTED)
    except TypeError:
        click.echo(f"{port_name}: Set loopback mode failed. Parameter is not supported")
        sys.exit(EXIT_FAIL)

    if status:
        click.echo(f"{port_name}: {enable} {loopback_mode} loopback")
    else:
        click.echo(f"{port_name}: {enable} {loopback_mode} loopback failed")
        sys.exit(EXIT_FAIL)


def set_output(port_name, enable, direction):
    """
    Enable or disable TX/RX output based on direction ('tx' or 'rx').
    """
    sfp = get_sfp_object(port_name)

    subport = get_subport(port_name)

    media_lane_count = get_media_lane_count(port_name)

    lane_mask = get_subport_lane_mask(int(subport), int(media_lane_count))

    try:
        if direction == "tx":
            sfp.tx_disable_channel(lane_mask, enable == "disable")
        elif direction == "rx":
            sfp.rx_disable_channel(lane_mask, enable == "disable")

        click.echo(
            f"{port_name}: {direction.upper()} output "
            f"{'disabled' if enable == 'disable' else 'enabled'} on subport {subport}"
        )

    except AttributeError:
        click.echo(f"{port_name}: {direction.upper()} disable is not applicable for this module")
        sys.exit(ERROR_NOT_IMPLEMENTED)
    except Exception as e:
        click.echo(f"{port_name}: {direction.upper()} disable failed due to {str(e)}")
        sys.exit(EXIT_FAIL)


@debug.command()
@click.argument('port_name', required=True)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def tx_output(port_name, enable):
    """Enable or disable TX output on a port."""
    set_output(port_name, enable, "tx")


@debug.command()
@click.argument('port_name', required=True)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def rx_output(port_name, enable):
    """Enable or disable RX output on a port."""
    set_output(port_name, enable, "rx")
