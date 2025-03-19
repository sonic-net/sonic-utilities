import sys
import click
import sonic_platform
import sonic_platform_base.sonic_sfp.sfputilhelper
from sonic_platform_base.sfp_base import SfpBase
from sonic_py_common import multi_asic
import utilities_common.cli as clicommon
from utilities_common import platform_sfputil_helper
from utilities_common.platform_sfputil_helper import (
    logical_port_name_to_physical_port_list,
    logical_port_to_physical_port_index,
    is_rj45_port,
    is_sfp_present,
    get_subport,
    get_sfp_object,
    get_subport_lane_mask
)
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector

# Global variables for platform-specific utilities
platform_sfputil = None
platform_chassis = None

EXIT_FAIL = -1
EXIT_SUCCESS = 0
ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_SFPUTILHELPER_LOAD = 3
ERROR_PORT_CONFIG_LOAD = 4
ERROR_NOT_IMPLEMENTED = 5
ERROR_INVALID_PORT = 6


# 'debug' command group
@click.group(cls=clicommon.AliasedGroup)
def debug():
    """
    Group for debugging and diagnostic control commands.
    
    This command group loads platform-specific utilities and prepares them for use in diagnostic commands.
    """
    global platform_sfputil
    global platform_chassis
    # Load platform-specific sfputil class to interact with platform-specific hardware.
    platform_sfputil_helper.load_platform_sfputil()
    # Load platform chassis information for further interaction.
    platform_sfputil_helper.load_chassis()

    # Load port information for further diagnostic operations.
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()

    platform_sfputil = platform_sfputil_helper.platform_sfputil
    platform_chassis = platform_sfputil_helper.platform_chassis


# 'loopback' subcommand for setting diagnostic loopback mode
@debug.command()
@click.argument('port_name', required=True)
@click.argument('loopback_mode', required=True,
                type=click.Choice(["host-side-input", "host-side-output",
                                   "media-side-input", "media-side-output"]))
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def loopback(port_name, loopback_mode, enable):
    """
    Set module diagnostic loopback mode.

    This function sets the diagnostic loopback mode for a given port. It interacts with the SFP object
    and checks the lane count and other settings based on the provided mode.

    Args:
        port_name (str): The logical port name where the loopback is to be set.
        loopback_mode (str): The loopback mode to set. Can be 'host-side-input', 'host-side-output',
                             'media-side-input', or 'media-side-output'.
        enable (str): Whether to enable or disable the loopback mode.

    Raises:
        SystemExit: If any error occurs during the loopback operation, including invalid port type or missing configuration.
    """
    # Get the physical port corresponding to the logical port.
    physical_port = logical_port_to_physical_port_index(port_name)
    # Retrieve the SFP object for the physical port.
    sfp = platform_chassis.get_sfp(physical_port)
    # Check if the port is RJ45, and exit if so.
    if is_rj45_port(port_name):
        click.echo(f"{port_name}: This functionality is not applicable for RJ45 port")
        sys.exit(EXIT_FAIL)

    # Check if the SFP is present, and exit if not.
    if not is_sfp_present(port_name):
        click.echo(f"{port_name}: SFP EEPROM not detected")
        sys.exit(EXIT_FAIL)

    try:
        # Attempt to get the API for the transceiver.
        api = sfp.get_xcvr_api()
    except NotImplementedError:
        # Exit if the API is not implemented for this module.
        click.echo(f"{port_name}: This functionality is not implemented")
        sys.exit(ERROR_NOT_IMPLEMENTED)

    # Connect to the CONFIG_DB to fetch subport and lane information.
    namespace = multi_asic.get_namespace_for_port(port_name)
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    if config_db is not None:
        config_db.connect()
        try:
            # Fetch the subport from the CONFIG_DB.
            subport = int(config_db.get(config_db.CONFIG_DB, f'PORT|{port_name}', 'subport'))
        except TypeError:
            # Exit if subport value is not present.
            click.echo(f"{port_name}: subport is not present in CONFIG_DB")
            sys.exit(EXIT_FAIL)

        # Default subport to 1 if set to 0.
        if subport == 0:
            subport = 1
    else:
        # Exit if failed to connect to CONFIG_DB.
        click.echo(f"{port_name}: Failed to connect to CONFIG_DB")
        sys.exit(EXIT_FAIL)

    # Connect to the STATE_DB to fetch lane counts.
    state_db = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
    if state_db is not None:
        state_db.connect(state_db.STATE_DB)
        try:
            # Fetch host lane count from the STATE_DB.
            host_lane_count = int(state_db.get(state_db.STATE_DB, f'TRANSCEIVER_INFO|{port_name}', 'host_lane_count'))
        except TypeError:
            click.echo(f"{port_name}: host_lane_count is not present in STATE_DB")
            sys.exit(EXIT_FAIL)

        try:
            # Fetch media lane count from the STATE_DB.
            media_lane_count = int(state_db.get(state_db.STATE_DB, f'TRANSCEIVER_INFO|{port_name}', 'media_lane_count'))
        except TypeError:
            click.echo(f"{port_name}: media_lane_count is not present in STATE_DB")
            sys.exit(EXIT_FAIL)
    else:
        # Exit if failed to connect to STATE_DB.
        click.echo(f"{port_name}: Failed to connect to STATE_DB")
        sys.exit(EXIT_FAIL)

    # Calculate the lane mask based on the loopback mode.
    if 'host-side' in loopback_mode:
        lane_mask = get_subport_lane_mask(subport, host_lane_count)
    elif 'media-side' in loopback_mode:
        lane_mask = get_subport_lane_mask(subport, media_lane_count)
    else:
        lane_mask = 0

    try:
        # Set the loopback mode using the API.
        status = api.set_loopback_mode(loopback_mode, lane_mask=lane_mask, enable=enable == 'enable')
    except AttributeError:
        click.echo(f"{port_name}: Set loopback mode is not applicable for this module")
        sys.exit(ERROR_NOT_IMPLEMENTED)
    except TypeError:
        click.echo(f"{port_name}: Set loopback mode failed. Parameter is not supported")
        sys.exit(EXIT_FAIL)

    # Output the result of the loopback operation.
    if status:
        click.echo(f"{port_name}: {enable} {loopback_mode} loopback")
    else:
        click.echo(f"{port_name}: {enable} {loopback_mode} loopback failed")
        sys.exit(EXIT_FAIL)


# Common function to enable/disable TX or RX output
def set_output(port_name, enable, direction):
    """
    Enable or disable TX/RX output based on the direction ('tx' or 'rx').

    This method enables or disables the output for either TX or RX based on the specified direction.
    It interacts with the SFP object and uses the subport as the channel.

    Args:
        port_name (str): The port name on which the output is to be enabled/disabled.
        enable (str): Whether to enable or disable the output. Should be 'enable' or 'disable'.
        direction (str): The direction of the output. Can be either 'tx' or 'rx'.

    Raises:
        SystemExit: If there is an error disabling the output or if the direction is not supported.
    """
    # Retrieve the SFP object for the given port.
    sfp = get_sfp_object(port_name)
    # Get the namespace for the port
    namespace = multi_asic.get_namespace_for_port(port_name)
    # Connect to the CONFIG_DB to fetch subport information
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    subport = get_subport(port_name, config_db)

    try:
        # Enable or disable TX output based on the direction.
        if direction == "tx":
            sfp.tx_disable_channel(subport, enable == "disable")
            click.echo(f"{port_name}: TX output {'disabled' if enable == 'disable' else 'enabled'} on subport {subport}")
        # Enable or disable RX output based on the direction.
        elif direction == "rx":
            sfp.rx_disable_channel(subport, enable == "disable")
            click.echo(f"{port_name}: RX output {'disabled' if enable == 'disable' else 'enabled'} on subport {subport}")
    except AttributeError:
        # If the direction is not applicable for this module, exit.
        click.echo(f"{port_name}: {direction.upper()} disable is not applicable for this module")
        sys.exit(ERROR_NOT_IMPLEMENTED)
    except Exception as e:
        # Exit if there is an error disabling the output.
        click.echo(f"{port_name}: {direction.upper()} disable failed due to {str(e)}")
        sys.exit(EXIT_FAIL)


# 'tx-output' subcommand for enabling/disabling TX output
@debug.command()
@click.argument('port_name', required=True)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def tx_output(port_name, enable):
    """
    Enable or disable TX output on a port (or specific channel based on subport).

    Args:
        port_name (str): The port to enable/disable TX output on.
        enable (str): Whether to enable or disable TX output.

    Raises:
        SystemExit: If the operation fails for any reason.
    """
    # Call the common function to set TX output.
    set_output(port_name, enable, "tx")


# 'rx-output' subcommand for enabling/disabling RX output
@debug.command()
@click.argument('port_name', required=True)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def rx_output(port_name, enable):
    """
    Enable or disable RX output on a port (or specific channel based on subport).

    Args:
        port_name (str): The port to enable/disable RX output on.
        enable (str): Whether to enable or disable RX output.

    Raises:
        SystemExit: If the operation fails for any reason.
    """
    # Call the common function to set RX output.
    set_output(port_name, enable, "rx")

