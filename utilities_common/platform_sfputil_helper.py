import sys

import click

from . import cli as clicommon
from sonic_py_common import multi_asic, device_info

platform_sfputil = None
platform_chassis = None
platform_sfp_base = None
platform_porttab_mapping_read = False

RJ45_PORT_TYPE = 'RJ45'


def load_chassis():
    """Load the platform chassis if not already loaded"""
    global platform_chassis

    if platform_chassis is None:
        try:
            import sonic_platform
            platform_chassis = sonic_platform.platform.Platform().get_chassis()
        except Exception as e:
            click.echo(f"Failed to load platform chassis: {str(e)}")
            sys.exit(1)
    return platform_chassis

def load_platform_sfputil():

    global platform_sfputil
    try:
        import sonic_platform_base.sonic_sfp.sfputilhelper
        platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
    except Exception as e:
        click.echo("Failed to instantiate platform_sfputil due to {}".format(repr(e)))
        sys.exit(1)

    return 0


def platform_sfputil_read_porttab_mappings():
    global platform_porttab_mapping_read

    if platform_porttab_mapping_read:
        return 0

    try:

        if multi_asic.is_multi_asic():
            # For multi ASIC platforms we pass DIR of port_config_file_path and the number of asics
            (platform_path, hwsku_path) = device_info.get_paths_to_platform_and_hwsku_dirs()

            # Load platform module from source
            platform_sfputil.read_all_porttab_mappings(hwsku_path, multi_asic.get_num_asics())
        else:
            # For single ASIC platforms we pass port_config_file_path and the asic_inst as 0
            port_config_file_path = device_info.get_path_to_port_config_file()
            platform_sfputil.read_porttab_mappings(port_config_file_path, 0)

        platform_porttab_mapping_read = True
    except Exception as e:
        click.echo("Error reading port info (%s)" % str(e))
        sys.exit(1)

    return 0


def logical_port_name_to_physical_port_list(port_name):
    try:
        if port_name.startswith("Ethernet"):
            if platform_sfputil.is_logical_port(port_name):
                return platform_sfputil.get_logical_to_physical(port_name)
        else:
            return [int(port_name)]
    except ValueError:
        pass

    click.echo("Invalid port '{}'".format(port_name))
    return None


def get_logical_list():

    return platform_sfputil.logical


def get_asic_id_for_logical_port(port):

    return platform_sfputil.get_asic_id_for_logical_port(port)


def get_physical_to_logical():

    return platform_sfputil.physical_to_logical


def get_interface_name(port, db):

    if port != "all" and port is not None:
        alias = port
        iface_alias_converter = clicommon.InterfaceAliasConverter(db)
        if clicommon.get_interface_naming_mode() == "alias":
            port = iface_alias_converter.alias_to_name(alias)
            if port is None:
                click.echo("cannot find port name for alias {}".format(alias))
                sys.exit(1)

    return port

def get_interface_alias(port, db):

    if port != "all" and port is not None:
        alias = port
        iface_alias_converter = clicommon.InterfaceAliasConverter(db)
        if clicommon.get_interface_naming_mode() == "alias":
            port = iface_alias_converter.name_to_alias(alias)
            if port is None:
                click.echo("cannot find port name for alias {}".format(alias))
                sys.exit(1)

    return port


def is_rj45_port(port_name):
    global platform_sfputil
    global platform_chassis
    global platform_sfp_base
    global platform_sfputil_loaded

    try:
        if not platform_chassis:
            import sonic_platform
            platform_chassis = sonic_platform.platform.Platform().get_chassis()
        if not platform_sfp_base:
            import sonic_platform_base
            platform_sfp_base = sonic_platform_base.sfp_base.SfpBase
    except (ModuleNotFoundError, FileNotFoundError) as e:
        # This method is referenced by intfutil which is called on vs image
        # sonic_platform API support is added for vs image(required for chassis), it expects a metadata file, which
        # wont be available on vs pizzabox duts, So False is returned(if either ModuleNotFound or FileNotFound)
        return False

    if platform_chassis and platform_sfp_base:
        if not platform_sfputil:
            load_platform_sfputil()

        if not platform_porttab_mapping_read:
            platform_sfputil_read_porttab_mappings()

        port_type = None
        try:
            physical_port = platform_sfputil.get_logical_to_physical(port_name)
            if physical_port:
                port_type = platform_chassis.get_port_or_cage_type(physical_port[0])
        except Exception as e:
            pass

        return port_type == platform_sfp_base.SFP_PORT_TYPE_BIT_RJ45

    return False


def get_first_subport(logical_port):
    """
    Retrieve the first subport associated with a given logical port.

    Args:
        logical_port (str): The name of the logical port.

    Returns:
        str: The name of the first subport if found, otherwise None.
    """
    try:
        physical_port = platform_sfputil.get_logical_to_physical(logical_port)
        if physical_port is not None:
            # Get the first subport for the given logical port
            logical_port_list = platform_sfputil.get_physical_to_logical(physical_port[0])
            if logical_port_list is not None:
                return logical_port_list[0]
    except KeyError:
        click.echo(f"Error: Found KeyError while getting first subport for {logical_port}")
        return None

    return None
