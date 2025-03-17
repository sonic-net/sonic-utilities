import sys
import click
import sonic_platform
import sonic_platform_base.sonic_sfp.sfputilhelper
from sonic_platform_base.sfp_base import SfpBase
from sonic_py_common import multi_asic
import utilities_common.cli as clicommon
from utilities_common.platform_sfputil_helper import (
    logical_port_name_to_physical_port_list,
    logical_port_to_physical_port_index,
    get_subport_lane_mask,
    get_sfp_object,
    get_subport,
    is_rj45_port,
)
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector


# 'debug' subgroup
@click.group(cls=clicommon.AliasedGroup)
def debug():
    """Module debug and diagnostic control"""
    pass

# 'loopback' subcommand
@debug.command()
@click.argument('port_name', required=True)
@click.argument('loopback_mode', required=True,
                type=click.Choice(["host-side-input", "host-side-output",
                                   "media-side-input", "media-side-output"]))
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def loopback(port_name, loopback_mode, enable):
    """Set module diagnostic loopback mode
    """
    physical_port = logical_port_to_physical_port_index(port_name)
    sfp = platform_chassis.get_sfp(physical_port)

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
    if config_db is not None:
        config_db.connect()
        try:
            subport = int(config_db.get(config_db.CONFIG_DB, f'PORT|{port_name}', 'subport'))
        except TypeError:
            click.echo(f"{port_name}: subport is not present in CONFIG_DB")
            sys.exit(EXIT_FAIL)

        # If subport is set to 0, assign a default value of 1 to ensure valid subport configuration
        if subport == 0:
            subport = 1
    else:
        click.echo(f"{port_name}: Failed to connect to CONFIG_DB")
        sys.exit(EXIT_FAIL)

    state_db = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
    if state_db is not None:
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
    else:
        click.echo(f"{port_name}: Failed to connect to STATE_DB")
        sys.exit(EXIT_FAIL)

    if 'host-side' in loopback_mode:
        lane_mask = get_subport_lane_mask(subport, host_lane_count)
    elif 'media-side' in loopback_mode:
        lane_mask = get_subport_lane_mask(subport, media_lane_count)
    else:
        lane_mask = 0

    try:
        status = api.set_loopback_mode(loopback_mode, lane_mask=lane_mask, enable=enable == 'enable')
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


# Common function to enable/disable TX or RX output
def set_output(port_name, enable, direction):
    """
    Enable or disable TX/RX output based on direction ('tx' or 'rx').
    Uses subport as the channel.
    """
    sfp = get_sfp_object(port_name)
    subport = get_subport(port_name)

    try:
        if direction == "tx":
            sfp.tx_disable_channel(subport, enable == "disable")
            click.echo(f"{port_name}: TX output {'disabled' if enable == 'disable' else 'enabled'} on subport {subport}")
        elif direction == "rx":
            sfp.rx_disable_channel(subport, enable == "disable")
            click.echo(f"{port_name}: RX output {'disabled' if enable == 'disable' else 'enabled'} on subport {subport}")
    except AttributeError:
        click.echo(f"{port_name}: {direction.upper()} disable is not applicable for this module")
        sys.exit(ERROR_NOT_IMPLEMENTED)
    except Exception as e:
        click.echo(f"{port_name}: {direction.upper()} disable failed due to {str(e)}")
        sys.exit(EXIT_FAIL)


# 'tx-output' subcommand
@debug.command()
@click.argument('port_name', required=True)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def tx_output(port_name, enable):
    """Enable or disable TX output on a port (or specific channel based on subport)"""
    set_output(port_name, enable, "tx")


# 'rx-output' subcommand
@debug.command()
@click.argument('port_name', required=True)
@click.argument('enable', required=True, type=click.Choice(["enable", "disable"]))
def rx_output(port_name, enable):
    """Enable or disable RX output on a port (or specific channel based on subport)"""
    set_output(port_name, enable, "rx")

