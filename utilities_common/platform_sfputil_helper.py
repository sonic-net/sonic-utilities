import sys

import click

from . import cli as clicommon
from sonic_py_common import multi_asic, device_info

platform_sfputil = None
platform_chassis = None
platform_sfp_base = None
platform_porttab_mapping_read = False

EXIT_FAIL = -1
EXIT_SUCCESS = 0
ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_SFPUTILHELPER_LOAD = 3
ERROR_PORT_CONFIG_LOAD = 4
ERROR_NOT_IMPLEMENTED = 5
ERROR_INVALID_PORT = 6

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

def logical_port_to_physical_port_index(port_name):
    if not platform_sfputil.is_logical_port(port_name):
        click.echo("Error: invalid port '{}'\n".format(port_name))
        print_all_valid_port_values()
        sys.exit(ERROR_INVALID_PORT)
    
    physical_port = logical_port_name_to_physical_port_list(port_name)[0]
    if physical_port is None:
        click.echo("Error: No physical port found for logical port '{}'".format(port_name))
        sys.exit(EXIT_FAIL)
            
    return physical_port

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

def get_subport_lane_mask(subport, lane_count):
    """
    Get the lane mask for the given subport and lane count.

    This method calculates the lane mask based on the subport and lane count.

    Args:
        subport (int): The subport number to calculate the lane mask for.
        lane_count (int): The number of lanes per subport.

    Returns:
        int: The lane mask calculated for the given subport and lane count.
    """
    # Calculating the lane mask using bitwise operations.
    return ((1 << lane_count) - 1) << ((subport - 1) * lane_count)


def get_sfp_object(port_name):
    """
    Retrieve the SFP object for a given port.

    This function checks whether the port is a valid RJ45 port or if an SFP is present.
    If valid, it retrieves the SFP object for further operations.

    Args:
        port_name (str): The name of the logical port to fetch the SFP object for.

    Returns:
        SfpBase: The SFP object associated with the port.

    Raises:
        SystemExit: If the port is an RJ45 or the SFP EEPROM is not present.
    """
    # Retrieve the physical port corresponding to the logical port.
    physical_port = logical_port_to_physical_port_index(port_name)
    # Fetch the SFP object for the physical port.
    sfp = platform_chassis.get_sfp(physical_port)

    # Check if the port is an RJ45 port and exit if so.
    if is_rj45_port(port_name):
        click.echo(f"{port_name}: This functionality is not applicable for RJ45 port")
        sys.exit(EXIT_FAIL)

    # Check if the SFP EEPROM is present and exit if not.
    if not is_sfp_present(port_name):
        click.echo(f"{port_name}: SFP EEPROM not detected")
        sys.exit(EXIT_FAIL)

    return sfp

def get_value_from_db_by_field(db, table_name, field, key):
    """
    Retrieve a specific field value from a given table in the CONFIG_DB.

    Args:
        db: Database connection object.
        table_name (str): The table to query.
        field (str): The field whose value is needed.
        key (str): The specific key within the table.

    Returns:
        The retrieved value if found, otherwise None.
    """
    if db is not None:
        db.connect()
        try:
            return db.get(db.CONFIG_DB, f"{table_name}|{key}", field)
        except TypeError:
            return None
    return None

def get_subport(port_name, config_db):
    """
    Retrieve subport from the CONFIG_DB.

    Args:
        port_name (str): The logical port name to retrieve the subport for.
        config_db: Database connection object.

    Returns:
        int: The subport associated with the port (default is 1 if not found).

    Raises:
        SystemExit: If the subport value is not found or there is a failure connecting to CONFIG_DB.
    """
    subport = get_value_from_db_by_field(config_db, "PORT", "subport", port_name)
    
    if subport is None:
        click.echo(f"{port_name}: subport is not present in CONFIG_DB")
        sys.exit(EXIT_FAIL)
    
    return max(int(subport), 1)

def get_subport(port_name, config_db):
    """
    Retrieve subport from the CONFIG_DB.

    This function fetches the subport value from the configuration database. If no subport is specified, it defaults to 1.

    Args:
        port_name (str): The logical port name to retrieve the subport for.

    Returns:
        int: The subport associated with the port (default is 1 if not found).

    Raises:
        SystemExit: If the subport value is not found in the CONFIG_DB or there is a failure connecting to it.
    """

    if config_db is not None:
        config_db.connect()
        try:
            # Try to fetch the subport for the given port.
            subport = int(config_db.get(config_db.CONFIG_DB, f'PORT|{port_name}', 'subport'))
        except TypeError:
            # If no subport value is found, exit with an error.
            click.echo(f"{port_name}: subport is not present in CONFIG_DB")
            sys.exit(EXIT_FAIL)

        # Ensure subport is valid (non-zero).
        return max(subport, 1)
    
    # Exit if unable to connect to CONFIG_DB.
    click.echo(f"{port_name}: Failed to connect to CONFIG_DB")
    sys.exit(EXIT_FAIL)

def is_sfp_present(port_name):
    physical_port = logical_port_to_physical_port_index(port_name)
    sfp = platform_chassis.get_sfp(physical_port)

    try:
        presence = sfp.get_presence()
    except NotImplementedError:
        click.echo("sfp get_presence() NOT implemented!", err=True)
        sys.exit(ERROR_NOT_IMPLEMENTED)
        
    return bool(presence)

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
