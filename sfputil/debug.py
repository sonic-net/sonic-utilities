import sys
import time
import click
from natsort import natsorted
import utilities_common.cli as clicommon
from utilities_common import platform_sfputil_helper
from utilities_common.platform_sfputil_helper import (
    get_subport,
    get_sfp_object,
    get_logical_list,
    is_rj45_port,
    is_sfp_present,
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

CMIS_MAX_CHANNELS = 8
TX_RX_OUTPUT_UPDATE_WAIT_TIME = 2  # seconds

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
        if not api.get_diag_page_support():
            click.echo(f"{port_name}: The module does not support diagnostic pages required for loopback configuration")
            click.echo(f"{port_name}: {enable} {loopback_mode} loopback failed")
            sys.exit(EXIT_FAIL)
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
    try:
        api = sfp.get_xcvr_api()
    except NotImplementedError:
        click.echo(f"{port_name}: This functionality is not implemented")
        sys.exit(ERROR_NOT_IMPLEMENTED)

    subport = get_subport(port_name)

    if hasattr(api, 'get_cmis_rev'):
        cmis_rev = api.get_cmis_rev()
        if cmis_rev is None:
            click.echo(f"{port_name}: CMIS revision not available for subport {subport}")
            sys.exit(EXIT_FAIL)

        # OutputStatusRx and OutputStatusTx are supported from CMIS 5.0
        if float(cmis_rev) < 5.0:
            click.echo(
                f"{port_name}: This functionality is not supported"
                f" with CMIS version {cmis_rev}, requires CMIS 5.0 and above"
            )
            sys.exit(EXIT_FAIL)

    try:
        if direction == "tx":
            lane_count = get_media_lane_count(port_name)
            disable_func = sfp.tx_disable_channel
            get_status_func = api.get_tx_output_status
            status_key = "TxOutputStatus"
        elif direction == "rx":
            lane_count = get_host_lane_count(port_name)
            disable_func = sfp.rx_disable_channel
            get_status_func = api.get_rx_output_status
            status_key = "RxOutputStatus"

        lane_mask = get_subport_lane_mask(int(subport), int(lane_count))
        if not disable_func(lane_mask, enable == "disable"):
            click.echo(f"{port_name}: {direction.upper()} disable failed for subport {subport}")
            sys.exit(EXIT_FAIL)

        time.sleep(TX_RX_OUTPUT_UPDATE_WAIT_TIME)

        output_dict = get_status_func()
        if output_dict is None:
            click.echo(f"{port_name}: {direction.upper()} output status not available for subport {subport}")
            sys.exit(EXIT_FAIL)

        for lane in range(1, CMIS_MAX_CHANNELS + 1):
            if lane_mask & (1 << (lane - 1)):
                lane_status = output_dict.get(f'{status_key}{lane}')
                if lane_status is None:
                    click.echo(
                        f"{port_name}: {direction.upper()} output status not available for "
                        f"lane {lane} on subport {subport}"
                    )
                    sys.exit(EXIT_FAIL)
                if enable == "disable":
                    if lane_status:
                        click.echo(
                            f"{port_name}: {direction.upper()} output on lane {lane} is still "
                            f"enabled on subport {subport}. Restoring state."
                        )
                        sys.exit(EXIT_FAIL)
                else:
                    if not lane_status:
                        click.echo(
                            f"{port_name}: {direction.upper()} output on lane {lane} is still disabled "
                            f"on subport {subport}. Restoring state."
                        )
                        sys.exit(EXIT_FAIL)

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


@debug.command(name='loopback-capability')
@click.argument('port_name', required=False, default=None)
def loopback_capability(port_name):
    """Show the loopback modes advertised as supported by the module.

    If PORT_NAME is omitted, prints capability for all ports that support loopback.
    """
    port_list = [port_name] if port_name else natsorted(set(get_logical_list()))
    single_port = port_name is not None
    found = False

    for port in port_list:
        if not single_port and (is_rj45_port(port) or not is_sfp_present(port)):
            continue

        sfp = get_sfp_object(port)

        try:
            api = sfp.get_xcvr_api()
        except NotImplementedError:
            if single_port:
                click.echo(f"{port}: This functionality is not implemented")
                sys.exit(ERROR_NOT_IMPLEMENTED)
            continue

        try:
            if not api.get_diag_page_support():
                if single_port:
                    click.echo(f"{port}: The module does not support diagnostic pages required for loopback")
                    sys.exit(EXIT_FAIL)
                continue
        except AttributeError:
            pass  # Older sonic-platform-common does not have diag page method

        try:
            cap = api.get_loopback_capability()
        except AttributeError:
            if single_port:
                click.echo(f"{port}: Loopback capability is not applicable for this module")
                sys.exit(ERROR_NOT_IMPLEMENTED)
            continue

        found = True
        if not cap:
            click.echo(f"{port}: The module does not advertise any loopback capability")
            continue

        click.echo(f"{port}: loopback capability: ")
        for key, value in cap.items():
            click.echo(f"  {key}: {value}")

    if not single_port and not found:
        click.echo("No ports found that support loopback capability")


@debug.command(name='loopback-status')
@click.argument('port_name', required=False, default=None)
def loopback_status(port_name):
    """Show which loopback modes are currently enabled on the module.

    If PORT_NAME is omitted, prints status for all ports that support loopback.
    """
    port_list = [port_name] if port_name else natsorted(set(get_logical_list()))
    single_port = port_name is not None
    found = False

    for port in port_list:
        if not single_port and (is_rj45_port(port) or not is_sfp_present(port)):
            continue

        sfp = get_sfp_object(port)

        try:
            api = sfp.get_xcvr_api()
        except NotImplementedError:
            if single_port:
                click.echo(f"{port}: This functionality is not implemented")
                sys.exit(ERROR_NOT_IMPLEMENTED)
            continue

        try:
            if not api.get_diag_page_support():
                if single_port:
                    click.echo(f"{port}: The module does not support diagnostic pages required for loopback")
                    sys.exit(EXIT_FAIL)
                continue
        except AttributeError:
            pass  # Older sonic-platform-common does not have diag_page_support function

        try:
            host_input = api.get_host_input_loopback()
            host_output = api.get_host_output_loopback()
            media_input = api.get_media_input_loopback()
            media_output = api.get_media_output_loopback()
        except AttributeError:
            if single_port:
                click.echo(f"{port}: Loopback status is not applicable for this module")
                sys.exit(ERROR_NOT_IMPLEMENTED)
            continue

        found = True
        click.echo(f"{port}: loopback status: ")
        click.echo(f"  host-side-input:   {host_input}")
        click.echo(f"  host-side-output:  {host_output}")
        click.echo(f"  media-side-input:  {media_input}")
        click.echo(f"  media-side-output: {media_output}")

    if not single_port and not found:
        click.echo("No ports found that support loopback status")


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
