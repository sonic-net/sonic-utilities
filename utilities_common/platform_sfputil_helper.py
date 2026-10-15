import ast
import re
import sys

import click

from . import cli as clicommon
from .sfp_helper import QSFP_DATA_MAP
from sonic_py_common import multi_asic, device_info
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector

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


CMIS_INFO_FIELD_MAP = {
    **QSFP_DATA_MAP,
    'hardware_rev': 'Hardware Revision',
    'media_interface_code': 'Media Interface Code',
    'host_electrical_interface': 'Host Electrical Interface',
    'host_lane_count': 'Host Lane Count',
    'media_lane_count': 'Media Lane Count',
    'host_lane_assignment_option': 'Host Lane Assignment Options',
    'media_lane_assignment_option': 'Media Lane Assignment Options',
    'active_apsel_hostlane1': 'Active App Selection Host Lane 1',
    'active_apsel_hostlane2': 'Active App Selection Host Lane 2',
    'active_apsel_hostlane3': 'Active App Selection Host Lane 3',
    'active_apsel_hostlane4': 'Active App Selection Host Lane 4',
    'active_apsel_hostlane5': 'Active App Selection Host Lane 5',
    'active_apsel_hostlane6': 'Active App Selection Host Lane 6',
    'active_apsel_hostlane7': 'Active App Selection Host Lane 7',
    'active_apsel_hostlane8': 'Active App Selection Host Lane 8',
    'media_interface_technology': 'Media Interface Technology',
    'cmis_rev': 'CMIS Revision',
    'supported_max_tx_power': 'Supported Max TX Power',
    'supported_min_tx_power': 'Supported Min TX Power',
    'supported_max_laser_freq': 'Supported Max Laser Frequency',
    'supported_min_laser_freq': 'Supported Min Laser Frequency',
}


CMIS_DOM_CHANNEL_MONITOR_MAP = {
    **{"rx{}power".format(i): "RX{}Power".format(i) for i in range(1, 9)},
    **{"tx{}bias".format(i): "TX{}Bias".format(i) for i in range(1, 9)},
    **{"tx{}power".format(i): "TX{}Power".format(i) for i in range(1, 9)},
}

DOM_CHANNEL_THRESHOLD_MAP = {
    "txpowerhighalarm": "TxPowerHighAlarm",
    "txpowerlowalarm": "TxPowerLowAlarm",
    "txpowerhighwarning": "TxPowerHighWarning",
    "txpowerlowwarning": "TxPowerLowWarning",
    "rxpowerhighalarm": "RxPowerHighAlarm",
    "rxpowerlowalarm": "RxPowerLowAlarm",
    "rxpowerhighwarning": "RxPowerHighWarning",
    "rxpowerlowwarning": "RxPowerLowWarning",
    "txbiashighalarm": "TxBiasHighAlarm",
    "txbiaslowalarm": "TxBiasLowAlarm",
    "txbiashighwarning": "TxBiasHighWarning",
    "txbiaslowwarning": "TxBiasLowWarning",
}

DOM_MODULE_MONITOR_MAP = {
    "temperature": "Temperature",
    "voltage": "Vcc",
}

DOM_MODULE_THRESHOLD_MAP = {
    "temphighalarm": "TempHighAlarm",
    "templowalarm": "TempLowAlarm",
    "temphighwarning": "TempHighWarning",
    "templowwarning": "TempLowWarning",
    "vcchighalarm": "VccHighAlarm",
    "vcclowalarm": "VccLowAlarm",
    "vcchighwarning": "VccHighWarning",
    "vcclowwarning": "VccLowWarning",
}

CMIS_DOM_VALUE_UNIT_MAP = {
    **{"rx{}power".format(i): "dBm" for i in range(1, 9)},
    **{"tx{}bias".format(i): "mA" for i in range(1, 9)},
    **{"tx{}power".format(i): "dBm" for i in range(1, 9)},
    "temperature": "C",
    "voltage": "Volts",
}

DOM_CHANNEL_THRESHOLD_UNIT_MAP = {
    key: "mA" if key.startswith("txbias") else "dBm"
    for key in DOM_CHANNEL_THRESHOLD_MAP
}

DOM_MODULE_THRESHOLD_UNIT_MAP = {
    key: "C" if key.startswith("temp") else "Volts"
    for key in DOM_MODULE_THRESHOLD_MAP
}


def natural_sort_key(value, case_sensitive=False):
    """Order numeric parts naturally, optionally preserving letter case."""
    text = str(value)
    if not case_sensitive:
        text = text.lower()
    return [int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", text)]


def format_application_advertisement(advertisements):
    """Render API application dictionaries or serialized values in natural order."""
    if isinstance(advertisements, str):
        try:
            advertisements = ast.literal_eval(advertisements)
        except (SyntaxError, ValueError):
            return [advertisements]
    if not isinstance(advertisements, dict):
        return [str(advertisements)]

    output = []
    for application in sorted(advertisements, key=natural_sort_key):
        details = advertisements[application]
        if not isinstance(details, dict):
            output.append(str(details))
            continue
        host = details.get("host_electrical_interface_id", "N/A")
        media = details.get("module_media_interface_id", "N/A")
        host_assignment = details.get("host_lane_assignment_options")
        media_assignment = details.get("media_lane_assignment_options")

        def assignment(value):
            try:
                return "0x{:02x}".format(int(value))
            except (TypeError, ValueError):
                return str(value) if value is not None else "N/A"

        output.append(
            "{} - Host Assign ({}) - {} - Media Assign ({})".format(
                host,
                assignment(host_assignment),
                media,
                assignment(media_assignment),
            )
        )
    return output or ["N/A"]


def get_physical_port_name(logical_port, physical_port, ganged):
    """Return a physical port label, including its member index when ganged."""
    if logical_port == physical_port:
        return str(logical_port)
    if ganged:
        return "{}:{} (ganged)".format(logical_port, physical_port)
    return str(logical_port)


def convert_byte_to_valid_ascii_char(byte):
    """Render non-printable EEPROM bytes as dots."""
    return chr(byte) if 32 <= byte <= 126 else '.'


def hexdump(indent, data, mem_address, start_newline=True):
    """Format EEPROM bytes in rows of sixteen with an ASCII column."""
    size = len(data)
    offset = 0
    lines = [''] if start_newline else []
    while size > 0:
        offset_str = "{}{:08x}".format(indent, mem_address)
        if size >= 16:
            first_half = ' '.join("{:02x}".format(x) for x in data[offset:offset + 8])
            second_half = ' '.join("{:02x}".format(x) for x in data[offset + 8:offset + 16])
            ascii_str = ''.join(convert_byte_to_valid_ascii_char(x) for x in data[offset:offset + 16])
            lines.append(f'{offset_str} {first_half}  {second_half} |{ascii_str}|')
        elif size > 8:
            first_half = ' '.join("{:02x}".format(x) for x in data[offset:offset + 8])
            second_half = ' '.join("{:02x}".format(x) for x in data[offset + 8:offset + size])
            padding = '   ' * (16 - size)
            ascii_str = ''.join(convert_byte_to_valid_ascii_char(x) for x in data[offset:offset + size])
            lines.append(f'{offset_str} {first_half}  {second_half}{padding} |{ascii_str}|')
            break
        else:
            hex_part = ' '.join("{:02x}".format(x) for x in data[offset:offset + size])
            padding = '   ' * (16 - size)
            ascii_str = ''.join(convert_byte_to_valid_ascii_char(x) for x in data[offset:offset + size])
            lines.append(f'{offset_str} {hex_part} {padding} |{ascii_str}|')
            break
        size -= 16
        offset += 16
        mem_address += 16
    return '\n'.join(lines)


def format_value_with_unit(value, unit):
    """Append a DOM unit without duplicating it or changing Unknown values."""
    if isinstance(value, str) and (value == 'Unknown' or not unit or value.endswith(unit)):
        return value
    return "{}{}".format(value, unit)


def format_dict_value_to_string(sorted_key_table, dom_info_dict, dom_value_map,
                                dom_unit_map, alignment=0):
    """Format available DOM fields in the caller's order and alignment."""
    output = ''
    indent = ' ' * 16
    separator = ': '
    for key in sorted_key_table:
        if dom_info_dict is not None and key in dom_info_dict and dom_info_dict[key] != 'N/A':
            label = dom_value_map[key]
            output += '{}{}{}{}\n'.format(
                indent, label,
                separator.rjust(len(separator) + alignment - len(label)),
                format_value_with_unit(dom_info_dict[key], dom_unit_map[key]))
    return output


def get_validated_physical_port_list(port_name):
    """Resolve a port to unique physical indexes or raise one CLI error.

    Keep validation separate so existing callers retain the legacy resolver's
    signature, return values and printed diagnostics.
    """
    port_name = str(port_name)
    # Reject invalid names before the legacy resolver prints its own error.
    if port_name.startswith("Ethernet"):
        if not platform_sfputil.is_logical_port(port_name):
            raise click.ClickException("Invalid port '{}'".format(port_name))
    else:
        try:
            int(port_name)
        except ValueError as exc:
            raise click.ClickException("Invalid port '{}'".format(port_name)) from exc
    physical_ports = logical_port_name_to_physical_port_list(port_name)
    if not physical_ports:
        raise click.ClickException("Invalid port '{}'".format(port_name))
    return list(dict.fromkeys(physical_ports))


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
        click.echo("Error: invalid port {} ".format(port_name))
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
    return ((1 << lane_count) - 1) << ((0 if subport == 0 else subport - 1) * lane_count)


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

    if sfp is None:
        click.echo(f"{port_name}: SFP object is not retrieved")
        sys.exit(EXIT_FAIL)

    return sfp


def get_host_lane_count(port_name):

    lane_count = get_value_from_db_by_field("STATE_DB", "TRANSCEIVER_INFO", "host_lane_count", port_name)

    if lane_count == 0 or lane_count is None or lane_count == '':
        click.echo(f"{port_name}: unable to retrieve correct host lane count")
        sys.exit(EXIT_FAIL)

    return lane_count


def get_media_lane_count(port_name):

    lane_count = get_value_from_db_by_field("STATE_DB", "TRANSCEIVER_INFO", "media_lane_count", port_name)

    if lane_count == 0 or lane_count is None or lane_count == '':
        click.echo(f"{port_name}: unable to retrieve correct media lane count")
        sys.exit(EXIT_FAIL)

    return lane_count


def get_value_from_db_by_field(db_name, table_name, field, key):
    """
    Retrieve a specific field value from a given table in the specified DB.

    Args:
        db_name (str): The database to query (CONFIG_DB, STATE_DB, etc.).
        table_name (str): The table to query.
        field (str): The field whose value is needed.
        key (str): The specific key within the table (typically a port name).

    Returns:
        The retrieved value if found, otherwise None.
    """
    namespace = multi_asic.get_namespace_for_port(key)  # Use key (port) for namespace lookup

    # Choose the appropriate connector
    if db_name == "CONFIG_DB":
        db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    else:
        db = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)

    try:
        if db_name == "CONFIG_DB":
            db.connect()  # CONFIG_DB doesn't need the db_name passed explicitly
        else:
            db.connect(getattr(db, db_name))  # Get the corresponding attribute (e.g., STATE_DB) from the connector

        # Retrieve the value from the database
        value = db.get(db_name, f"{table_name}|{key}", field)
        if value is None:
            click.echo(f"Field '{field}' not found in table '{table_name}' for key '{key}' in {db_name}.")
            return ''
        else:
            return value
    except (TypeError, KeyError, AttributeError) as e:
        click.echo(f"Error: {e}")
        return None
    finally:
        # Ensure to close the connection if it's valid
        if db is not None:
            db.close()


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


def get_subport(port_name):
    subport = get_value_from_db_by_field("CONFIG_DB", "PORT", "subport", port_name)

    # An absent or empty subport means the port is not breakout/split, so it
    # occupies all lanes as subport 0. Default to 0 instead of bailing out so a
    # missing subport does not crash loopback/output diagnostics.
    if subport is None or subport == '':
        subport = 0

    return int(subport)


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
        # won't be available on vs pizzabox duts, So False is returned(if either ModuleNotFound or FileNotFound)
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
