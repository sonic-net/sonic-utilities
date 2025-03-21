import sys
import click
from sonic_py_common import multi_asic
import utilities_common.cli as clicommon
from utilities_common import platform_sfputil_helper
from utilities_common.platform_sfputil_helper import (
    is_rj45_port,
    is_sfp_present,
    get_subport,
    get_sfp_object,
    get_subport_lane_mask
)
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector

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

    if is_rj45_port(port_name):
        click.echo(f"{port_name}: This functionality is not applicable for RJ45 port")
        sys.exit(EXIT_FAIL)

    if not is_sfp_present(port_name):
        click.echo(f"{port_name}: SFP EEPROM not detected")
        sys.exit(EXIT_FAIL)

    try:
        api = sfp.get_xcvr_api()
    except NotImplementedError:
        click.echo(f"{port_name}: This functionality is not implemented")
        sys.exit(ERROR_NOT_IMPLEMENTED)

    namespace = multi_asic.get_namespace_for_port(port_name)
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    config_db.connect()

    try:
        subport = int(config_db.get(config_db.CONFIG_DB, f'PORT|{port_name}', 'subport'))
    except TypeError:
        click.echo(f"{port_name}: subport is not present in CONFIG_DB")
        sys.exit(EXIT_FAIL)

    subport = max(subport, 1)

    state_db = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
    state_db.connect(state_db.STATE_DB)

    try:
        host_lane_count = int(state_db.get(state_db.STATE_DB, f'TRANSCEIVER_INFO|{port_name}', 'host_lane_count'))
    except TypeError:
        click.echo(f"{port_name}: host_lane_count is not present in STATE_DB")
        sys.exit(EXIT_FAIL)

    try:
        media_lane_count = int(state_db.get(state_db.STATE_DB, f'TRANSCEIVER_INFO|{port_name}', 'media_lane_count'))
    except TypeError:
        click.echo(f"{port_name}: media_lane_count is not present in STATE_DB")
        sys.exit(EXIT_FAIL)

    lane_mask = get_subport_lane_mask(subport, host_lane_count if 'host-side' in loopback_mode else media_lane_count)

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

    try:
        if direction == "tx":
            sfp.tx_disable_channel(subport, enable == "disable")
        elif direction == "rx":
            sfp.rx_disable_channel(subport, enable == "disable")

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
