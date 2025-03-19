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
            (platform_path, hwsku_path) = device_info.get_paths_to_platform_and_hwsku_dirs()
            platform_sfputil.read_all_porttab_mappings(hwsku_path, multi_asic.get_num_asics())
        else:
            port_config_file_path = device_info.get_path_to_port_config_file()
            platform_sfputil.read_porttab_mappings(port_config_file_path, 0)

        platform_porttab_mapping_read = True
    except Exception as e:
        click.echo("Error reading port info (%s)" % str(e))
        sys.exit(1)

    return 0


def logical_port_to_physical_port_index(port_name):
    if not platform_sfputil.is_logical_port(port_name):
        click.echo("Error: invalid port '{}'
".format(port_name))
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


def get_value_from_db_by_field(db, table_name, field, key):
    if db is not None:
        db.connect()
        try:
            return db.get(db.CONFIG_DB, f"{table_name}|{key}", field)
        except TypeError:
            return None
    return None


def get_subport(port_name, config_db):
    subport = get_value_from_db_by_field(config_db, "PORT", "subport", port_name)

    if subport is None:
        click.echo(f"{port_name}: subport is not present in CONFIG_DB")
        sys.exit(EXIT_FAIL)

    return max(int(subport), 1)


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

    try:
        if not platform_chassis:
            import sonic_platform
            platform_chassis = sonic_platform.platform.Platform().get_chassis()
        if not platform_sfp_base:
            import sonic_platform_base
            platform_sfp_base = sonic_platform_base.sfp_base.SfpBase
    except (ModuleNotFoundError, FileNotFoundError):
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
        except Exception:
            pass

        return port_type == platform_sfp_base.SFP_PORT_TYPE_BIT_RJ45

    return False
