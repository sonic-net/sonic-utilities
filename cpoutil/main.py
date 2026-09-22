"""Command-line utility for Co-Packaged Optics devices."""

import ast
import json
import re
import sys

import click
from tabulate import tabulate

from cpoutil.mapping import CpoMapping, CpoMappingError
from cpoutil.mapping import EXTERNAL_LASER_SOURCE, OPTICAL_ENGINE, PORT


ERROR_INVALID_RESOURCE = 3
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

# Keep one process-wide chassis, active port configuration, topology, and CPO
# object table. A shared OE or ELS uses its first associated CPO object.
platform_chassis = None
current_port_config = {}
cpo_mapping = None
cpo_oe_bank_counts = {}
cpo_object_map = {
    OPTICAL_ENGINE: {},
    EXTERNAL_LASER_SOURCE: {},
    PORT: {},
}

CPO_INFO_FIELD_MAP = {
    "model": "Vendor PN",
    "vendor_oui": "Vendor OUI",
    "vendor_date": "Vendor Date Code(YYYY-MM-DD Lot)",
    "manufacturer": "Vendor Name",
    "vendor_rev": "Vendor Rev",
    "serial": "Vendor SN",
    "type": "Identifier",
    "ext_identifier": "Extended Identifier",
    "ext_rateselect_compliance": "Extended RateSelect Compliance",
    "cable_length": "cable_length",
    "cable_type": "Length",
    "nominal_bit_rate": "Nominal Bit Rate(100Mbs)",
    "specification_compliance": "Specification compliance",
    "encoding": "Encoding",
    "connector": "Connector",
    "application_advertisement": "Application Advertisement",
    "hardware_rev": "Hardware Revision",
    "media_interface_code": "Media Interface Code",
    "host_electrical_interface": "Host Electrical Interface",
    "host_lane_count": "Host Lane Count",
    "media_lane_count": "Media Lane Count",
    "host_lane_assignment_option": "Host Lane Assignment Options",
    "media_lane_assignment_option": "Media Lane Assignment Options",
    "active_apsel_hostlane1": "Active App Selection Host Lane 1",
    "active_apsel_hostlane2": "Active App Selection Host Lane 2",
    "active_apsel_hostlane3": "Active App Selection Host Lane 3",
    "active_apsel_hostlane4": "Active App Selection Host Lane 4",
    "active_apsel_hostlane5": "Active App Selection Host Lane 5",
    "active_apsel_hostlane6": "Active App Selection Host Lane 6",
    "active_apsel_hostlane7": "Active App Selection Host Lane 7",
    "active_apsel_hostlane8": "Active App Selection Host Lane 8",
    "media_interface_technology": "Media Interface Technology",
    "cmis_rev": "CMIS Revision",
    "supported_max_tx_power": "Supported Max TX Power",
    "supported_min_tx_power": "Supported Min TX Power",
    "supported_max_laser_freq": "Supported Max Laser Frequency",
    "supported_min_laser_freq": "Supported Min Laser Frequency",
    "els_identifier": "ELS Identifier",
    "els_revision": "ELS Revision",
    "els_laser_count": "ELS Laser Count",
    "els_vendor_name": "ELS Vendor Name",
    "els_vendor_oui": "ELS Vendor OUI",
    "els_vendor_pn": "ELS Vendor PN",
    "els_vendor_rev": "ELS Vendor Rev",
    "els_vendor_sn": "ELS Vendor SN",
    "els_date_code": "ELS Vendor Date Code(YYYY-MM-DD Lot)",
    "els_max_power": "ELS Maximum Power Consumption",
    "rlm_laser_lpmode_control": "RLM Laser Lpower Mode Control",
    "rlm_laser_wavelength_grid": "RLM Laser Wavelength Grid",
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

ELS_DOM_MONITOR_MAP = {
    "els_temperature": "ELS Temperature",
    "els_voltage": "ELS Vcc",
}

ELS_THRESHOLD_MAP = {
    "els_temphighalarm": "ELS TempHighAlarm",
    "els_templowalarm": "ELS TempLowAlarm",
    "els_temphighwarning": "ELS TempHighWarning",
    "els_templowwarning": "ELS TempLowWarning",
    "els_vcchighalarm": "ELS VccHighAlarm",
    "els_vcclowalarm": "ELS VccLowAlarm",
    "els_vcchighwarning": "ELS VccHighWarning",
    "els_vcclowwarning": "ELS VccLowWarning",
    "els_txpowerhighalarm": "ELS TxPowerHighAlarm",
    "els_txpowerlowalarm": "ELS TxPowerLowAlarm",
    "els_txpowerhighwarning": "ELS TxPowerHighWarning",
    "els_txpowerlowwarning": "ELS TxPowerLowWarning",
    "els_txbiashighalarm": "ELS TxBiasHighAlarm",
    "els_txbiashighwarning": "ELS TxBiasHighWarning",
}

DOM_VALUE_UNIT_MAP = {
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

ELS_DOM_MONITOR_UNIT_MAP = {
    "els_temperature": "C",
    "els_voltage": "Volts",
}

ELS_THRESHOLD_UNIT_MAP = {
    key: (
        "C" if key.startswith("els_temp") else
        "Volts" if key.startswith("els_vcc") else
        "mA" if key.startswith("els_txbias") else
        "mW"
    )
    for key in ELS_THRESHOLD_MAP
}

DISPLAY_FIELD_MAP = {
    "els_interrupt_status": "Interrupt Status",
    "els_module_low_power_state": "Module Low-power State",
}


class CpoCommandError(RuntimeError):
    """Raised when a CPO resource or platform API is unavailable."""


def load_platform_chassis():
    """Instantiate the platform chassis used by CPO commands."""
    global platform_chassis

    try:
        import sonic_platform
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
    except Exception as exc:
        raise CpoCommandError(
            "Failed to instantiate platform chassis: {}".format(exc)
        ) from exc
    if platform_chassis is None:
        raise CpoCommandError("Platform chassis is unavailable")


def load_current_port_config():
    """Load the active PORT table used for CPO port resolution."""
    global current_port_config

    from portconfig import get_port_config
    from sonic_py_common import device_info, multi_asic

    current_port_config = {}
    try:
        platform, hwsku = device_info.get_platform_and_hwsku()
        if multi_asic.is_multi_asic():
            for asic_id in range(multi_asic.get_num_asics()):
                ports, _, _ = get_port_config(
                    hwsku, platform, asic_name="asic{}".format(asic_id)
                )
                current_port_config.update(ports or {})
        else:
            ports, _, _ = get_port_config(hwsku, platform)
            current_port_config.update(ports or {})
    except Exception as exc:
        raise CpoCommandError(
            "Failed to load active PORT configuration: {}".format(exc)
        ) from exc

    if not current_port_config:
        raise CpoCommandError("Active PORT configuration is unavailable")


def logical_port_name_to_physical_port_list(logical_port):
    """Convert a logical or numeric port name to physical port indices."""
    port_name = str(logical_port)
    if port_name.startswith("Ethernet"):
        entry = current_port_config.get(port_name)
        if entry is None:
            raise CpoCommandError(
                "Invalid port '{}'\nValid values for port: {}".format(
                    port_name,
                    sorted(current_port_config, key=_natural_sort_key),
                )
            )
        physical_ports = _parse_port_indexes(entry.get("index"), port_name)
        if not physical_ports:
            raise CpoCommandError(
                "No physical ports found for logical port '{}'".format(
                    port_name
                )
            )
        return list(dict.fromkeys(physical_ports))

    try:
        return [int(port_name)]
    except ValueError as exc:
        raise CpoCommandError("Invalid port '{}'".format(port_name)) from exc


def _parse_port_integer_list(value, port_name, field):
    if isinstance(value, (int, str)):
        value = str(value).split(",")
    if not isinstance(value, (list, tuple)):
        raise CpoCommandError(
            "PORT '{}' has no usable {} configuration".format(
                port_name, field
            )
        )
    try:
        return tuple(
            int(item) for item in value if str(item).strip()
        )
    except (TypeError, ValueError) as exc:
        raise CpoCommandError(
            "PORT '{}' has invalid {} configuration".format(
                port_name, field
            )
        ) from exc


def _parse_port_lanes(value, port_name):
    return _parse_port_integer_list(value, port_name, "lanes")


def _parse_port_indexes(value, port_name):
    return _parse_port_integer_list(value, port_name, "index")


def get_port_config_entry(logical_port):
    """Return one active PORT entry from the cpoutil-owned configuration."""
    port_name = str(logical_port)
    entry = current_port_config.get(port_name)
    if entry is None:
        raise CpoCommandError(
            "No active PORT configuration found for '{}'".format(port_name)
        )
    return entry


def get_subport(logical_port):
    """Return the active breakout subport number; zero means unsplit."""
    entry = get_port_config_entry(logical_port)
    try:
        return int(entry.get("subport") or 0)
    except (TypeError, ValueError) as exc:
        raise CpoCommandError(
            "PORT '{}' has invalid subport configuration".format(logical_port)
        ) from exc


def get_first_subport(logical_port):
    """Return the first active logical port sharing the physical CPO port."""
    physical_ports = set(
        logical_port_name_to_physical_port_list(logical_port)
    )
    logical_ports = []
    for port_name, entry in current_port_config.items():
        indexes = _parse_port_indexes(entry.get("index"), port_name)
        if physical_ports.intersection(indexes):
            logical_ports.append(port_name)
    if not logical_ports:
        raise CpoCommandError(
            "No logical ports share physical port(s) {}".format(
                ",".join(str(port) for port in sorted(physical_ports))
            )
        )

    def natural_key(value):
        return [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", value)
        ]

    return sorted(logical_ports, key=natural_key)[0]


def get_port_lanes(logical_port):
    """Return the ASIC lanes assigned to one active logical port."""
    entry = get_port_config_entry(logical_port)
    return _parse_port_lanes(entry.get("lanes"), logical_port)


def get_cpo_interface_mapping(logical_port):
    """Resolve an active logical subport to its static cpo.json interface."""
    port_name = str(logical_port)
    try:
        return cpo_mapping.get_interface(port_name)
    except KeyError:
        pass

    physical_ports = set(
        logical_port_name_to_physical_port_list(logical_port)
    )
    matches = [
        mapping for mapping in cpo_mapping.get_interfaces()
        if physical_ports.intersection(mapping.physical_ports)
    ]
    if len(matches) != 1:
        raise CpoCommandError(
            "Unable to resolve '{}' to one CPO interface".format(port_name)
        )
    return matches[0]


def get_cpo_lane_positions(logical_port, mapping=None):
    """Return zero-based OE lane positions assigned to a logical subport."""
    mapping = mapping or get_cpo_interface_mapping(logical_port)
    port_name = str(logical_port)
    if not port_name.startswith("Ethernet"):
        return tuple(range(len(mapping.lanes)))

    port_lanes = set(get_port_lanes(port_name))
    mapping_lanes = tuple(mapping.lanes)
    unknown_lanes = port_lanes.difference(mapping_lanes)
    if unknown_lanes:
        raise CpoCommandError(
            "PORT '{}' lanes {} are outside CPO interface '{}'".format(
                port_name,
                ",".join(str(lane) for lane in sorted(unknown_lanes)),
                mapping.port,
            )
        )
    positions = tuple(
        index for index, lane in enumerate(mapping_lanes)
        if lane in port_lanes
    )
    if not positions:
        raise CpoCommandError(
            "PORT '{}' has no lanes in CPO interface '{}'".format(
                port_name, mapping.port
            )
        )
    return positions


def get_cpo_lane_mask(logical_port, mapping=None):
    """Return the OE channel mask assigned to a logical subport."""
    return sum(
        1 << lane for lane in get_cpo_lane_positions(logical_port, mapping)
    )


def get_cpo_laser_ids(logical_port, mapping=None):
    """Return ELS lasers and any lasers shared with sibling subports."""
    mapping = mapping or get_cpo_interface_mapping(logical_port)
    lane_positions = get_cpo_lane_positions(logical_port, mapping)
    if not mapping.laser_ids:
        return (), ()
    if len(mapping.lanes) % len(mapping.laser_ids):
        raise CpoCommandError(
            "CPO interface '{}' cannot map {} lanes to {} ELS lasers".format(
                mapping.port, len(mapping.lanes), len(mapping.laser_ids)
            )
        )

    selected_positions = set(lane_positions)
    lanes_per_laser = len(mapping.lanes) // len(mapping.laser_ids)
    selected = []
    shared = []
    for index, laser_id in enumerate(mapping.laser_ids):
        first = index * lanes_per_laser
        laser_positions = set(range(first, first + lanes_per_laser))
        overlap = selected_positions.intersection(laser_positions)
        if not overlap:
            continue
        selected.append(laser_id)
        if overlap != laser_positions:
            shared.append(laser_id)
    return tuple(selected), tuple(shared)


def get_interface_context(logical_port):
    """Resolve static CPO mapping and active breakout data for one port."""
    mapping = get_cpo_interface_mapping(logical_port)
    lane_positions = get_cpo_lane_positions(logical_port, mapping)
    laser_ids, shared_laser_ids = get_cpo_laser_ids(logical_port, mapping)
    port_name = str(logical_port)
    return {
        "mapping": mapping,
        "subport": get_subport(port_name)
        if port_name.startswith("Ethernet") else 0,
        "first_subport": get_first_subport(logical_port),
        "lane_positions": lane_positions,
        "lane_mask": sum(1 << lane for lane in lane_positions),
        "laser_ids": laser_ids,
        "shared_laser_ids": shared_laser_ids,
    }


def get_physical_port_name(logical_port, member_index, ganged):
    """Return the display name for a physical port."""
    if ganged:
        return "{}:{} (ganged)".format(logical_port, member_index)
    return str(logical_port)


def load_cpo_object_map():
    """Build the global OE/ELS/port to CPO object mapping from cpo.json."""
    global cpo_mapping, cpo_oe_bank_counts, cpo_object_map

    from sonic_platform_base.sonic_xcvr.bailly_optoe_base import (
        CpoOptoeBase,
        get_cpo_json_data,
    )

    cpo_data = get_cpo_json_data()
    if cpo_data is None:
        raise CpoCommandError("CPO topology is unavailable for this platform")
    cpo_mapping = CpoMapping(cpo_data)
    cpo_oe_bank_counts = {}
    cpo_object_map = {
        OPTICAL_ENGINE: {},
        EXTERNAL_LASER_SOURCE: {},
        PORT: {},
    }

    for interface in cpo_mapping.get_interfaces():
        interface_cpo = None
        for physical_port in interface.physical_ports:
            try:
                cpo = platform_chassis.get_cpo(physical_port)
            except Exception as exc:
                raise CpoCommandError(
                    "Failed to get CPO object for physical port {}: {}".format(
                        physical_port, exc
                    )
                ) from exc
            if not isinstance(cpo, CpoOptoeBase):
                continue
            cpo_object_map[PORT][physical_port] = cpo
            if interface_cpo is None:
                interface_cpo = cpo

        if interface_cpo is None:
            continue
        cpo_object_map[OPTICAL_ENGINE].setdefault(
            interface.oe_name, interface_cpo
        )
        cpo_object_map[EXTERNAL_LASER_SOURCE].setdefault(
            interface.els_name, interface_cpo
        )

    if not cpo_object_map[PORT]:
        raise CpoCommandError("No CPO objects are available")


def initialize_platform():
    load_platform_chassis()
    load_current_port_config()
    load_cpo_object_map()


def get_port_cpo_objects(logical_port=None):
    """Return (name, physical port, CPO object) tuples."""
    if logical_port is None:
        logical_ports = sorted(current_port_config, key=_natural_sort_key)
    else:
        logical_ports = [logical_port]

    objects = []
    for port_name in logical_ports:
        physical_ports = logical_port_name_to_physical_port_list(port_name)
        ganged = len(physical_ports) > 1
        for member_index, physical_port in enumerate(physical_ports, start=1):
            cpo = cpo_object_map[PORT].get(physical_port)
            if cpo is None:
                if logical_port is None:
                    continue
                raise CpoCommandError(
                    "Port '{}' is not a CPO port".format(port_name)
                )
            objects.append((
                get_physical_port_name(port_name, member_index, ganged),
                physical_port,
                cpo,
            ))
    return objects


def get_resource_cpo_objects(resource_type, selector=None):
    """Return shared OE or ELS objects from the global CPO table."""
    try:
        resource_ids = cpo_mapping.resolve_resource_ids(
            selector, resource_type
        )
    except KeyError as exc:
        raise CpoCommandError(
            "Invalid {} index '{}'".format(resource_type, selector)
        ) from exc

    objects = []
    for resource_id in resource_ids:
        cpo = cpo_object_map[resource_type].get(resource_id)
        if cpo is None:
            raise CpoCommandError(
                "No CPO object is available for '{}'".format(resource_id)
            )
        objects.append((resource_id, cpo))
    return objects


def get_xcvr_api(cpo, label):
    """Get the existing PI/PD transceiver API from a CPO object."""
    try:
        api = cpo.get_xcvr_api()
    except NotImplementedError as exc:
        raise CpoCommandError(
            "{} API is not implemented".format(label)
        ) from exc
    except Exception as exc:
        raise CpoCommandError(
            "Failed to get {} API: {}".format(label, exc)
        ) from exc
    if api is None:
        raise CpoCommandError("{} API is unavailable".format(label))
    return api


def _normalize_lane_values(values):
    if isinstance(values, (list, tuple)):
        ordered = list(values)
    elif isinstance(values, dict):
        def lane_key(item):
            match = re.search(r"(\d+)(?!.*\d)", str(item[0]))
            if match:
                return 0, int(match.group(1))
            return 1, str(item[0])

        ordered = [value for _, value in sorted(values.items(), key=lane_key)]
    else:
        raise CpoCommandError("Expected per-lane data from platform API")
    return {
        "lane{:02d}".format(index): value
        for index, value in enumerate(ordered)
    }


def _select_lane_values(values, lane_positions):
    """Select the CMIS lanes assigned to one active logical subport."""
    normalized = _normalize_lane_values(values)
    selected = {}
    for lane in lane_positions:
        key = "lane{:02d}".format(lane)
        if key not in normalized:
            raise CpoCommandError(
                "Platform API did not return data for {}".format(key)
            )
        selected[key] = normalized[key]
    return selected


def _natural_sort_key(value):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", str(value))
    ]


def _case_sensitive_natural_sort_key(value):
    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", str(value))
    ]


def _value_with_unit(value, unit):
    if isinstance(value, str):
        if value == "Unknown" or not unit or value.endswith(unit):
            return value
    return "{}{}".format(value, unit)


def _format_application_advertisement(advertisements):
    if isinstance(advertisements, str):
        try:
            advertisements = ast.literal_eval(advertisements)
        except (SyntaxError, ValueError):
            return [advertisements]
    if not isinstance(advertisements, dict):
        return [str(advertisements)]

    output = []
    for application in sorted(advertisements, key=_natural_sort_key):
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


def _format_cpo_info(info):
    indent = " " * 8
    if not isinstance(info, dict):
        return ["{}EEPROM info: N/A".format(indent)]

    lines = []
    keys = sorted(
        info,
        key=lambda key: (
            0 if key in CPO_INFO_FIELD_MAP else 1,
            _natural_sort_key(CPO_INFO_FIELD_MAP.get(key, key)),
        ),
    )
    for key in keys:
        if key == "cable_length":
            continue
        if key == "cable_type":
            label = info.get("cable_type", CPO_INFO_FIELD_MAP[key])
            value = info.get("cable_length", "N/A")
        elif key == "application_advertisement":
            label = CPO_INFO_FIELD_MAP[key]
            values = _format_application_advertisement(info[key])
            prefix = "{}{}: ".format(indent, label)
            lines.append("{}{}".format(prefix, values[0]))
            continuation = " " * len(prefix)
            lines.extend(
                "{}{}".format(continuation, value)
                for value in values[1:]
            )
            continue
        else:
            label = CPO_INFO_FIELD_MAP.get(key, key)
            value = info.get(key, "N/A")

        if key in ("supported_max_tx_power", "supported_min_tx_power"):
            value = _value_with_unit(value, "dBm")
        elif key in (
                "supported_max_laser_freq", "supported_min_laser_freq"):
            value = _value_with_unit(value, "GHz")
        lines.append("{}{}: {}".format(indent, label, value))
    return lines


def _append_dom_values(lines, values, value_map, unit_map, alignment=0):
    indent = " " * 16
    separator = ": "
    for key in sorted(value_map, key=_case_sensitive_natural_sort_key):
        if key not in values or values[key] == "N/A":
            continue
        label = value_map[key]
        aligned_separator = separator.rjust(
            len(separator) + alignment - len(label)
        )
        lines.append("{}{}{}{}".format(
            indent,
            label,
            aligned_separator,
            _value_with_unit(values[key], unit_map[key]),
        ))


def _format_cpo_dom(dom_values):
    indent = " " * 8
    values = dom_values if isinstance(dom_values, dict) else {}
    lines = ["{}ChannelMonitorValues:".format(indent)]
    _append_dom_values(
        lines,
        values,
        CMIS_DOM_CHANNEL_MONITOR_MAP,
        DOM_VALUE_UNIT_MAP,
    )

    lines.append("{}ChannelThresholdValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        DOM_CHANNEL_THRESHOLD_MAP,
        DOM_CHANNEL_THRESHOLD_UNIT_MAP,
        alignment=18,
    )

    lines.append("{}ModuleMonitorValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        DOM_MODULE_MONITOR_MAP,
        DOM_VALUE_UNIT_MAP,
    )

    lines.append("{}ModuleThresholdValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        DOM_MODULE_THRESHOLD_MAP,
        DOM_MODULE_THRESHOLD_UNIT_MAP,
        alignment=15,
    )

    laser_keys = [
        key for key in values
        if str(key).startswith("RLM") and "Laser" in str(key)
    ]
    els_monitor_map = dict(ELS_DOM_MONITOR_MAP)
    els_monitor_map.update({key: key for key in laser_keys})
    els_monitor_units = dict(ELS_DOM_MONITOR_UNIT_MAP)
    els_monitor_units.update({key: "" for key in laser_keys})
    lines.append("{}ELSMonitorValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        els_monitor_map,
        els_monitor_units,
    )

    lines.append("{}ELSThresholdValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        ELS_THRESHOLD_MAP,
        ELS_THRESHOLD_UNIT_MAP,
    )

    displayed_keys = set().union(
        CMIS_DOM_CHANNEL_MONITOR_MAP,
        DOM_CHANNEL_THRESHOLD_MAP,
        DOM_MODULE_MONITOR_MAP,
        DOM_MODULE_THRESHOLD_MAP,
        els_monitor_map,
        ELS_THRESHOLD_MAP,
    )
    additional_values = {
        key: value for key, value in values.items()
        if key not in displayed_keys and value != "N/A"
    }
    if additional_values:
        lines.append("{}AdditionalValues:".format(indent))
        for field, value in _flatten_record(additional_values):
            lines.append("{}{}: {}".format(
                " " * 16, _display_field(field), _display_value(value)
            ))
    return lines


def _format_interface_dom(port_name, present, info, dom, thresholds):
    if not present:
        return "{}: CPO EEPROM not detected".format(port_name)

    lines = ["{}: CPO EEPROM detected".format(port_name)]
    lines.extend(_format_cpo_info(info))
    values = {}
    if isinstance(dom, dict):
        values.update(dom)
    if isinstance(thresholds, dict):
        values.update(thresholds)
    lines.extend(_format_cpo_dom(values))
    return "\n".join(lines)


def _local_oe_bank(mapping):
    """Return an OE-local bank index for one topology interface."""
    oe_banks = sorted({
        item.oe_bank for item in cpo_mapping.get_interfaces()
        if item.oe_name == mapping.oe_name
    })
    try:
        return oe_banks.index(mapping.oe_bank)
    except ValueError as exc:
        raise CpoCommandError(
            "Unable to resolve bank {} for '{}'".format(
                mapping.oe_bank, mapping.oe_name.upper()
            )
        ) from exc


def _interface_mapping_record(logical_port):
    mapping = get_cpo_interface_mapping(logical_port)
    return {
        "port": str(logical_port),
        "oe": {
            "id": mapping.oe_name.upper(),
            "bank": _local_oe_bank(mapping),
        },
        "els": {
            "id": mapping.els_name.upper(),
        },
    }


def _application_speed(advertisements, application):
    if not application or not isinstance(advertisements, dict):
        return "N/A"
    details = advertisements.get(application)
    if details is None:
        details = advertisements.get(str(application), {})
    if not isinstance(details, dict):
        return "N/A"
    interface = details.get("host_electrical_interface_id", "")
    match = re.search(r"(\d+(?:\.\d+)?)G", str(interface), re.IGNORECASE)
    if not match:
        return "N/A"
    return int(float(match.group(1)) * 1000)


def _format_map_table(mappings):
    headers = ("Interface", "OE", "ELS")
    rows = []
    for record in mappings:
        rows.append((
            record["port"],
            "{} bank{}".format(
                record["oe"]["id"], record["oe"]["bank"]
            ),
            record["els"]["id"],
        ))
    return tabulate(rows, headers, tablefmt="simple")


def _display_resource_id(resource_id):
    text = str(resource_id)
    if re.fullmatch(r"(?:oe|els)\d+", text, re.IGNORECASE):
        return text.upper()
    return text


def _display_value(value, boolean_values=None):
    if value is None:
        return "N/A"
    if isinstance(value, bool) and boolean_values is not None:
        return boolean_values[0] if value else boolean_values[1]
    return value


def _display_lpmode(value):
    if isinstance(value, bool):
        return "On" if value else "Off"
    text = str(value)
    normalized = text.lower()
    if "low power" in normalized or "low-power" in normalized:
        return "On"
    if "high power" in normalized or "full power" in normalized:
        return "Off"
    return text


def _display_field(field):
    parts = str(field).split(".")
    output = []
    for part in parts:
        lane_match = re.fullmatch(r"lane(\d+)", part, re.IGNORECASE)
        laser_match = re.fullmatch(
            r"Laser(\d+)OpticalPowerMonitor", part, re.IGNORECASE
        )
        if lane_match:
            output.append("Lane {}".format(int(lane_match.group(1)) + 1))
        elif laser_match:
            output.append("Laser {}".format(int(laser_match.group(1))))
        else:
            output.append(
                DISPLAY_FIELD_MAP.get(part, part.replace("_", " "))
            )
    return " / ".join(output)


def _flatten_record(value, field=""):
    if isinstance(value, dict):
        for key in sorted(value, key=_natural_sort_key):
            child_field = "{}.{}".format(field, key) if field else str(key)
            yield from _flatten_record(value[key], child_field)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            child_field = (
                "{}.lane{:02d}".format(field, index)
                if field else "lane{:02d}".format(index)
            )
            yield from _flatten_record(item, child_field)
        return
    yield field or "Value", value


def print_records(records, json_output, headers=("Resource", "Value"),
                  boolean_values=None, field_header="Field"):
    """Print platform values using SONiC-style simple tables."""
    if json_output:
        click.echo(json.dumps(records, indent=4, sort_keys=True))
        return

    nested = any(
        isinstance(value, (dict, list, tuple))
        for value in records.values()
    )
    if nested:
        rows = []
        for resource_id, value in records.items():
            for field, item in _flatten_record(value):
                rows.append((
                    _display_resource_id(resource_id),
                    _display_field(field),
                    _display_value(item, boolean_values),
                ))
        table_headers = (headers[0], field_header, headers[1])
    else:
        rows = [
            (
                _display_resource_id(resource_id),
                _display_value(value, boolean_values),
            )
            for resource_id, value in records.items()
        ]
        table_headers = headers
    click.echo(tabulate(rows, table_headers, tablefmt="simple"))


def print_speed_records(records, json_output):
    if json_output:
        click.echo(json.dumps(records, indent=4, sort_keys=True))
        return

    rows = []
    for interface, values in records.items():
        configured = values.get("Application Select Controls", {})
        active = values.get("Active Application Control Set", {})
        lanes = sorted(
            set(configured).union(active), key=_natural_sort_key
        )
        for lane in lanes:
            rows.append((
                interface,
                _display_field(lane),
                configured.get(lane, "N/A"),
                active.get(lane, "N/A"),
            ))
    click.echo(tabulate(
        rows,
        (
            "Interface",
            "Lane",
            "Configured Speed (Mbps)",
            "Active Speed (Mbps)",
        ),
        tablefmt="simple",
    ))


def print_lane_status_records(records, json_output):
    if json_output:
        click.echo(json.dumps(records, indent=4, sort_keys=True))
        return

    lane_rows = []
    status_rows = []
    for interface, values in records.items():
        lane_states = values.get("Data Path State Indicator", {})
        lanes = sorted(lane_states, key=_natural_sort_key)
        lasers = values.get("ELS Lasers", [])
        shared = set(values.get("Shared ELS Lasers", []))
        els_id = values.get("ELS", "N/A")
        for index, lane in enumerate(lanes):
            laser = "N/A"
            if lasers:
                laser_index = min(
                    index * len(lasers) // len(lanes), len(lasers) - 1
                )
                laser = lasers[laser_index]
            lane_rows.append((
                interface,
                _display_field(lane),
                lane_states[lane],
                els_id,
                laser,
                "Yes" if laser in shared else "No",
            ))

        status = values.get("ELS Status")
        if isinstance(status, dict):
            for field in sorted(status, key=_natural_sort_key):
                status_rows.append((
                    interface,
                    els_id,
                    _display_field(field),
                    status[field],
                ))
        elif status is not None:
            status_rows.append((interface, els_id, "Status", status))

    click.echo(tabulate(
        lane_rows,
        (
            "Interface",
            "Lane",
            "Data Path State",
            "ELS",
            "Laser",
            "Shared",
        ),
        tablefmt="simple",
    ))
    if status_rows:
        click.echo("\nELS status:")
        click.echo(tabulate(
            status_rows,
            ("Interface", "ELS", "Status field", "Value"),
            tablefmt="simple",
        ))


def output_option(function):
    return click.option(
        "-j", "--json", "json_output", is_flag=True,
        help="Display machine-readable JSON output.",
    )(function)


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """Debug and manually provision Co-Packaged Optics devices."""
    try:
        initialize_platform()
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))


@cli.group()
def show():
    """Display CPO status."""


@show.group("interface")
def show_interface():
    """Display front-panel interface information."""


@show_interface.command("map")
@click.argument("port", required=False)
@click.option("-j", "--json", "json_output", is_flag=True,
              help="Display machine-readable JSON output.")
def show_interface_map(port, json_output):
    """Display the OE and ELS mapped to each active interface."""
    try:
        if port is not None:
            records = [_interface_mapping_record(port)]
        else:
            records = []
            for logical_port in sorted(current_port_config, key=_natural_sort_key):
                physical_ports = logical_port_name_to_physical_port_list(
                    logical_port
                )
                if not any(
                        physical in cpo_object_map[PORT]
                        for physical in physical_ports):
                    continue
                records.append(_interface_mapping_record(logical_port))
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))

    if json_output:
        click.echo(json.dumps(
            {
                record["port"]: {
                    "oe": record["oe"],
                    "els": record["els"],
                }
                for record in records
            },
            indent=4,
            sort_keys=True,
        ))
    else:
        click.echo(_format_map_table(records))


@show_interface.command("dom")
@click.argument("port", required=False)
@output_option
def show_interface_dom(port, json_output):
    """Display CPO EEPROM information and monitoring data."""
    records = {}
    output = []
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            present = cpo.get_presence()
            values = {}
            info = dom = thresholds = None
            if present:
                info = cpo.get_transceiver_info()
                dom = cpo.get_transceiver_dom_real_value()
                thresholds = cpo.get_transceiver_threshold_info()
                for result in (info, dom, thresholds):
                    if isinstance(result, dict):
                        values.update(result)
            records[port_name] = values
            output.append(_format_interface_dom(
                port_name, present, info, dom, thresholds
            ))
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    if json_output:
        click.echo(json.dumps(records, indent=4, sort_keys=True))
    else:
        click.echo("\n\n".join(output))


@show_interface.command("tx_disable")
@click.argument("port", required=False)
@output_option
def show_interface_tx_disable(port, json_output):
    """Display per-lane Tx output state."""
    records = {}
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            logical_port = port if port is not None else port_name
            context = get_interface_context(logical_port)
            api = get_xcvr_api(cpo, port_name)
            values = _select_lane_values(
                api.get_tx_disable(), context["lane_positions"]
            )
            records[port_name] = {
                lane: "Tx output disable" if disabled else "Tx output enable"
                for lane, disabled in values.items()
            }
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("Interface", "Tx Output State"),
        field_header="Lane",
    )


@show_interface.command("speed")
@click.argument("port", required=False)
@output_option
def show_interface_speed(port, json_output):
    """Display configured and active speed per lane."""
    from sonic_platform_base.sonic_xcvr.fields import consts

    records = {}
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            api = get_xcvr_api(cpo, port_name)
            advertisements = api.get_application_advertisement()
            active_applications = api.get_active_apsel_hostlane()
            if not isinstance(advertisements, dict) or not isinstance(
                    active_applications, dict):
                raise CpoCommandError(
                    "Speed APIs returned no data for '{}'".format(port_name)
                )

            configured = []
            active = []
            for lane in range(api.NUM_CHANNELS):
                configured.append(_application_speed(
                    advertisements, api.get_application(lane)
                ))
                active_application = active_applications.get(
                    "{}{}".format(
                        consts.ACTIVE_APSEL_HOSTLANE, lane + 1
                    ),
                    "N/A",
                )
                active.append(_application_speed(
                    advertisements, active_application
                ))
            logical_port = port if port is not None else port_name
            lane_positions = get_interface_context(
                logical_port
            )["lane_positions"]
            records[port_name] = {
                "Application Select Controls": _select_lane_values(
                    configured, lane_positions
                ),
                "Active Application Control Set": _select_lane_values(
                    active, lane_positions
                ),
            }
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    print_speed_records(records, json_output)


@show_interface.command("lane-status")
@click.argument("port", required=False)
@output_option
def show_interface_lane_status(port, json_output):
    """Display OE datapath and ELS status."""
    records = {}
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            api = get_xcvr_api(cpo, port_name)
            logical_port = port if port is not None else port_name
            context = get_interface_context(logical_port)
            records[port_name] = {
                "Data Path State Indicator": _select_lane_values(
                    api.get_datapath_state(), context["lane_positions"]
                ),
                "ELS": context["mapping"].els_name.upper(),
                "ELS Status": api.get_rlm_status(),
                "ELS Lasers": list(context["laser_ids"]),
                "Shared ELS Lasers": list(context["shared_laser_ids"]),
            }
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    print_lane_status_records(records, json_output)


@show.group("oe")
def show_oe():
    """Display Optical Engine status."""


@show_oe.command("lpmode")
@click.argument("oe_index", required=False)
@output_option
def show_oe_lpmode(oe_index, json_output):
    """Display OE low-power mode."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                OPTICAL_ENGINE, oe_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_lpmode()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records, json_output, ("OE", "Low-power Mode"),
        boolean_values=("On", "Off"),
    )


@show_oe.command("status")
@click.argument("oe_index", required=False)
@output_option
def show_oe_status(oe_index, json_output):
    """Display OE module state."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                OPTICAL_ENGINE, oe_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_module_state()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("OE", "Module State"))


@show_oe.command("temperature")
@click.argument("oe_index", required=False)
@output_option
def show_oe_temperature(oe_index, json_output):
    """Display OE temperature."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                OPTICAL_ENGINE, oe_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_module_temperature()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("OE", "Temperature (C)"))


@show_oe.command("input-power")
@click.argument("oe_index", required=False)
@output_option
def show_oe_input_power(oe_index, json_output):
    """Display OE input optical power."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                OPTICAL_ENGINE, oe_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_rx_power()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("OE", "Input Power (mW)"),
        field_header="Media Lane",
    )


@show.group("els")
def show_els():
    """Display External Laser Source status."""


@show_els.command("presence")
@click.argument("els_index", required=False)
@output_option
def show_els_presence(els_index, json_output):
    """Display ELS presence."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            records[resource_id] = cpo.get_els_presence()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records, json_output, ("ELS", "Presence"),
        boolean_values=("Present", "Not present"),
    )


@show_els.command("lpmode")
@click.argument("els_index", required=False)
@output_option
def show_els_lpmode(els_index, json_output):
    """Display ELS low-power state."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            status = get_xcvr_api(cpo, resource_id).get_rlm_status()
            value = (
                status.get("els_module_low_power_state")
                if isinstance(status, dict) else status
            )
            records[resource_id] = _display_lpmode(value)
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("ELS", "Low-power Mode"))


@show_els.command("status")
@click.argument("els_index", required=False)
@output_option
def show_els_status(els_index, json_output):
    """Display ELS module status."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_rlm_status()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("ELS", "Status"),
        field_header="Status field",
    )


@show_els.command("temperature")
@click.argument("els_index", required=False)
@output_option
def show_els_temperature(els_index, json_output):
    """Display ELS temperature."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_rlm_temperature()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("ELS", "Temperature (C)"))


@show_els.command("output-power")
@click.argument("els_index", required=False)
@output_option
def show_els_output_power(els_index, json_output):
    """Display ELS output optical power."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            records[resource_id] = get_xcvr_api(
                cpo, resource_id
            ).get_rlm_laser_power()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("ELS", "Output Power (mW)"),
        field_header="Laser",
    )


def _require_success(result, action):
    if not result:
        raise CpoCommandError("{} failed".format(action))


def _run_action(message, operation):
    """Run one control operation with SONiC-style progress output."""
    click.echo("{} ... ".format(message), nl=False)
    try:
        result = operation()
    except Exception:
        click.echo("Failed")
        raise
    if result:
        click.echo("OK")
        return
    click.echo("Failed")
    raise CpoCommandError("{} failed".format(message))


def _single_resource(resource_type, index):
    objects = get_resource_cpo_objects(resource_type, index)
    if len(objects) != 1:
        raise CpoCommandError(
            "Exactly one {} index is required".format(resource_type)
        )
    return objects[0]


def _get_interface_mapping(port):
    return get_cpo_interface_mapping(port)


@cli.group()
def config():
    """Control CPO hardware."""


@config.group("interface")
def config_interface():
    """Control a front-panel CPO interface."""


@config_interface.command("tx_disable")
@click.argument("port")
@click.argument("state", type=click.Choice(["enable", "disable"]))
def config_interface_tx_disable(port, state):
    """Enable or disable Tx-disable on mapped OE and ELS lanes."""
    disable = state == "enable"
    try:
        context = get_interface_context(port)
        mapping = context["mapping"]
        if context["shared_laser_ids"]:
            raise CpoCommandError(
                "PORT '{}' shares ELS laser(s) {} with another subport; "
                "interface Tx-disable is unsafe".format(
                    port,
                    ",".join(
                        str(laser) for laser
                        in context["shared_laser_ids"]
                    ),
                )
            )
        if not context["laser_ids"]:
            raise CpoCommandError(
                "No ELS laser mapping is available for '{}'".format(port)
            )

        _, els_cpo = _single_resource(
            EXTERNAL_LASER_SOURCE, mapping.els_id
        )
        api = get_xcvr_api(els_cpo, mapping.els_name)
        set_els_tx_disable = api.set_rlm_tx_disable_channel

        laser_mask = sum(1 << laser for laser in context["laser_ids"])
        port_cpos = get_port_cpo_objects(port)

        def apply_tx_disable():
            for _, _, cpo in port_cpos:
                oe_api = get_xcvr_api(cpo, port)
                _require_success(
                    oe_api.tx_disable_channel(
                        context["lane_mask"], disable
                    ),
                    "{} OE Tx-disable {}".format(port, state),
                )
            _require_success(
                set_els_tx_disable(laser_mask, disable),
                "{} ELS Tx-disable {}".format(port, state),
            )
            return True

        _run_action(
            "{} Tx-disable for port {}".format(
                "Enabling" if disable else "Disabling", port
            ),
            apply_tx_disable,
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config.group("oe")
def config_oe():
    """Control an Optical Engine."""


@config_oe.command("lpmode")
@click.argument("oe_index")
@click.argument("mode", type=click.Choice(["full", "low"]))
def config_oe_lpmode(oe_index, mode):
    """Set OE full-power or low-power mode."""
    try:
        resource_id, cpo = _single_resource(OPTICAL_ENGINE, oe_index)
        api = get_xcvr_api(cpo, resource_id)
        low_power = mode == "low"
        _run_action(
            "{} low-power mode for {}".format(
                "Enabling" if low_power else "Disabling",
                resource_id.upper(),
            ),
            lambda: api.set_lpmode(low_power),
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config_oe.command("reset")
@click.argument("oe_index")
def config_oe_reset(oe_index):
    """Reset an Optical Engine through the platform API."""
    try:
        resource_id, cpo = _single_resource(OPTICAL_ENGINE, oe_index)
        api = get_xcvr_api(cpo, resource_id)
        _run_action(
            "Resetting {}".format(resource_id.upper()), api.reset
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config_oe.command("tx_disable")
@click.argument("oe_index")
@click.argument("state", type=click.Choice(["enable", "disable"]))
def config_oe_tx_disable(oe_index, state):
    """Enable or disable OE Tx-disable."""
    try:
        resource_id, cpo = _single_resource(OPTICAL_ENGINE, oe_index)
        api = get_xcvr_api(cpo, resource_id)
        disable = state == "enable"
        _run_action(
            "{} Tx-disable for {}".format(
                "Enabling" if disable else "Disabling",
                resource_id.upper(),
            ),
            lambda: api.tx_disable(disable),
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config.group("els")
def config_els():
    """Control an External Laser Source."""


@config_els.command("lpmode")
@click.argument("els_index")
@click.argument("mode", type=click.Choice(["full", "low"]))
def config_els_lpmode(els_index, mode):
    """Set ELS full-power or low-power mode."""
    try:
        resource_id, cpo = _single_resource(
            EXTERNAL_LASER_SOURCE, els_index
        )
        api = get_xcvr_api(cpo, resource_id)
        low_power = mode == "low"
        _run_action(
            "{} low-power mode for {}".format(
                "Enabling" if low_power else "Disabling",
                resource_id.upper(),
            ),
            lambda: api.set_rlm_lpmode(low_power),
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config_els.command("reset")
@click.argument("els_index")
def config_els_reset(els_index):
    """Report the missing platform ELS reset API."""
    try:
        resource_id, _ = _single_resource(EXTERNAL_LASER_SOURCE, els_index)
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    raise click.ClickException(
        "{} reset: This functionality is currently not implemented for "
        "this platform".format(resource_id.upper())
    )


@config_els.command("tx_disable")
@click.argument("els_index")
@click.argument("state", type=click.Choice(["enable", "disable"]))
def config_els_tx_disable(els_index, state):
    """Enable or disable Tx-disable for every ELS laser."""
    try:
        resource_id, cpo = _single_resource(
            EXTERNAL_LASER_SOURCE, els_index
        )
        api = get_xcvr_api(cpo, resource_id)
        disable = state == "enable"
        _run_action(
            "{} Tx-disable for {}".format(
                "Enabling" if disable else "Disabling",
                resource_id.upper(),
            ),
            lambda: api.set_rlm_tx_disable(disable),
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


def _parse_integer(value):
    """Parse decimal or 0x-prefixed CLI integers."""
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def _validate_eeprom_range(bank, page, offset, size):
    """Validate one raw CMIS EEPROM operation."""
    for name, value, maximum in (
            ("bank", bank, 0xFF),
            ("page", page, 0xFF),
            ("offset", offset, 0xFF)):
        if value < 0 or value > maximum:
            raise CpoCommandError(
                "{} must be between 0 and 0x{:02x}".format(name, maximum)
            )
    if size <= 0:
        raise CpoCommandError("size must be greater than zero")
    if offset + size > 0x100:
        raise CpoCommandError(
            "EEPROM range crosses the CMIS page boundary"
        )


def _physical_eeprom_page(resource_type, resource_id, cpo, page):
    physical_page = page
    if resource_type == EXTERNAL_LASER_SOURCE:
        try:
            physical_page += cpo.get_els_base_page()
        except (NotImplementedError, AttributeError,
                TypeError, ValueError) as exc:
            raise CpoCommandError(
                "Failed to resolve ELS EEPROM page for '{}': {}".format(
                    resource_id, exc
                )
            ) from exc
        if physical_page > 0xFF:
            raise CpoCommandError(
                "ELS page 0x{:02x} exceeds the CMIS page range after "
                "platform mapping".format(page)
            )
    return physical_page


def _physical_eeprom_bank(resource_type, resource_id, cpo, bank):
    """Validate and return an OE-local CMIS bank."""
    if resource_type != OPTICAL_ENGINE:
        if bank != 0:
            raise CpoCommandError(
                "{} does not define EEPROM banks".format(
                    str(resource_id).upper()
                )
            )
        return 0

    bank_count = cpo_oe_bank_counts.get(resource_id)
    if bank_count is None:
        api = get_xcvr_api(cpo, str(resource_id).upper())
        try:
            bank_count = int(api.get_max_supported_banks())
        except (NotImplementedError, AttributeError, TypeError, ValueError) as exc:
            raise CpoCommandError(
                "Failed to determine the OE bank count for '{}': {}".format(
                    resource_id, exc
                )
            ) from exc
        if bank_count <= 0:
            raise CpoCommandError(
                "Invalid OE bank count {} for '{}'".format(
                    bank_count, resource_id
                )
            )
        cpo_oe_bank_counts[resource_id] = bank_count
    if bank >= bank_count:
        raise CpoCommandError(
            "OE bank {} is invalid for '{}'; valid banks are 0-{}".format(
                bank, str(resource_id).upper(), bank_count - 1
            )
        )
    return bank


def _eeprom_linear_offset(resource_type, resource_id, cpo,
                          bank, page, offset):
    from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages.page import (
        CmisPage,
    )

    physical_page = _physical_eeprom_page(
        resource_type, resource_id, cpo, page
    )
    physical_bank = _physical_eeprom_bank(
        resource_type, resource_id, cpo, bank
    )
    return CmisPage.linear_offset(physical_page, physical_bank, offset)


def _read_resource_eeprom(resource_type, index, bank, page, offset, size):
    """Read raw EEPROM bytes through mapped CPO objects."""
    results = []
    for resource_id, cpo in get_resource_cpo_objects(resource_type, index):
        data = _read_one_eeprom(
            resource_type, resource_id, cpo,
            bank, page, offset, size
        )
        results.append((resource_id, data))
    return results


def _parse_hex_data(value):
    try:
        data = bytearray.fromhex(value)
    except (TypeError, ValueError) as exc:
        raise CpoCommandError(
            "data must be an even-length hexadecimal byte string"
        ) from exc
    if not data:
        raise CpoCommandError("data must contain at least one byte")
    return data


def _write_resource_eeprom(resource_type, index, bank, page, offset, data):
    """Write raw EEPROM bytes through one mapped CPO object."""
    _validate_eeprom_range(bank, page, offset, len(data))
    resource_id, cpo = _single_resource(resource_type, index)
    linear_offset = _eeprom_linear_offset(
        resource_type, resource_id, cpo, bank, page, offset
    )
    try:
        _run_action(
            "Writing EEPROM for {}".format(str(resource_id).upper()),
            lambda: cpo.write_eeprom(linear_offset, len(data), data),
        )
    except (NotImplementedError, AttributeError, OSError) as exc:
        raise CpoCommandError(
            "Failed to write EEPROM for '{}': {}".format(resource_id, exc)
        ) from exc
    return resource_id


def _interface_eeprom_target(port, target):
    mapping = _get_interface_mapping(port)
    if target == OPTICAL_ENGINE:
        return mapping.oe_id, _local_oe_bank(mapping)
    if target == EXTERNAL_LASER_SOURCE:
        bank = mapping.els_bank
        return mapping.els_id, bank if isinstance(bank, int) else 0
    raise CpoCommandError("Specify exactly one of --oe or --els")


def _interface_target_option(oe, els):
    if oe == els:
        raise CpoCommandError("Specify exactly one of --oe or --els")
    return OPTICAL_ENGINE if oe else EXTERNAL_LASER_SOURCE


EEPROM_PAGE_SIZE = 128
EEPROM_PAGE_OFFSET = 128
EEPROM_DUMP_INDENT = " " * 8
ELS_FULL_DUMP_PAGES = (0xB0, 0xB1, 0xB2)


def _eeprom_ascii(value):
    return chr(value) if 32 <= value <= 126 else "."


def _format_eeprom_hexdump(data, address, indent=EEPROM_DUMP_INDENT):
    """Format bytes as a standard EEPROM hex dump."""
    lines = []
    for start in range(0, len(data), 16):
        chunk = data[start:start + 16]
        first_half = " ".join(
            "{:02x}".format(value) for value in chunk[:8]
        )
        second_half = " ".join(
            "{:02x}".format(value) for value in chunk[8:]
        )
        if len(chunk) > 8:
            hex_text = "{}  {}".format(first_half, second_half)
        else:
            hex_text = first_half
        ascii_text = "".join(_eeprom_ascii(value) for value in chunk)
        lines.append(
            "{}{:08x} {:<48} |{}|".format(
                indent, address + start, hex_text, ascii_text
            )
        )
    return "\n".join(lines)


def _resource_banks(resource_type, resource_id, requested_bank=None):
    """Return mapped banks for a full dump of one CPO resource."""
    if requested_bank is not None:
        _validate_eeprom_range(requested_bank, 0, 0, 1)
        if (resource_type == EXTERNAL_LASER_SOURCE
                and requested_bank != 0):
            raise CpoCommandError(
                "{} does not define EEPROM banks".format(
                    str(resource_id).upper()
                )
            )
        return [requested_bank]

    if resource_type == EXTERNAL_LASER_SOURCE:
        return [0]

    topology_banks = sorted({
        interface.oe_bank
        for interface in cpo_mapping.get_interfaces()
        if interface.oe_name == resource_id
    })
    return list(range(len(topology_banks))) or [0]


def _read_one_eeprom(resource_type, resource_id, cpo,
                     bank, page, offset, size):
    _validate_eeprom_range(bank, page, offset, size)
    linear_offset = _eeprom_linear_offset(
        resource_type, resource_id, cpo, bank, page, offset
    )
    try:
        data = cpo.read_eeprom(linear_offset, size)
    except (NotImplementedError, AttributeError, OSError) as exc:
        raise CpoCommandError(
            "Failed to read EEPROM for '{}': {}".format(resource_id, exc)
        ) from exc
    if data is None or len(data) != size:
        raise CpoCommandError(
            "Failed to read {} EEPROM byte(s) for '{}'".format(
                size, resource_id
            )
        )
    return bytearray(data)


def _full_eeprom_sections(resource_type, banks):
    if resource_type == OPTICAL_ENGINE:
        # CMIS lower and non-banked upper pages are printed once. Banked
        # pages 10h/11h are printed for every bank mapped to this OE.
        common_bank = banks[0]
        sections = [
            ("Lower page 0h", common_bank, 0, 0, EEPROM_PAGE_SIZE),
            ("Upper page 0h", common_bank, 0,
             EEPROM_PAGE_OFFSET, EEPROM_PAGE_SIZE),
            ("Upper page 1h", common_bank, 1,
             EEPROM_PAGE_OFFSET, EEPROM_PAGE_SIZE),
            ("Upper page 2h", common_bank, 2,
             EEPROM_PAGE_OFFSET, EEPROM_PAGE_SIZE),
        ]
        for bank in banks:
            sections.extend((
                ("Upper page 10h bank {:x}h".format(bank), bank,
                 0x10, EEPROM_PAGE_OFFSET, EEPROM_PAGE_SIZE),
                ("Upper page 11h bank {:x}h".format(bank), bank,
                 0x11, EEPROM_PAGE_OFFSET, EEPROM_PAGE_SIZE),
            ))
        return sections

    return [
        ("Upper page {:x}h".format(page), bank,
         page, EEPROM_PAGE_OFFSET, EEPROM_PAGE_SIZE)
        for bank in banks
        for page in ELS_FULL_DUMP_PAGES
    ]


def _format_full_eeprom(resource_type, resource_id, cpo, banks,
                        display_name=None):
    label = display_name or str(resource_id).upper()
    lines = ["EEPROM hexdump for {}".format(label)]
    for title, bank, page, offset, size in _full_eeprom_sections(
            resource_type, banks):
        lines.append("{}{}".format(EEPROM_DUMP_INDENT, title))
        data = _read_one_eeprom(
            resource_type, resource_id, cpo,
            bank, page, offset, size
        )
        lines.append(_format_eeprom_hexdump(data, offset))
        lines.append("")
    return "\n".join(lines)


def _print_full_resource_eeprom(resource_type, index=None, bank=None):
    outputs = []
    resources = get_resource_cpo_objects(resource_type, index)
    for resource_id, cpo in resources:
        banks = _resource_banks(resource_type, resource_id, bank)
        try:
            outputs.append(_format_full_eeprom(
                resource_type, resource_id, cpo, banks
            ))
        except CpoCommandError as exc:
            if index is not None:
                raise
            outputs.append(
                "EEPROM hexdump for {}\n{}{}".format(
                    str(resource_id).upper(),
                    EEPROM_DUMP_INDENT, exc,
                )
            )
    click.echo("\n".join(outputs).rstrip())


def _eeprom_range_requested(page, offset, size):
    values = (page, offset, size)
    if all(value is None for value in values):
        return False
    if any(value is None for value in values):
        raise CpoCommandError(
            "--page, --offset and --size must be supplied together"
        )
    return True


def _print_eeprom_data(resource_type, resource_id, bank,
                       page, offset, data, display_name=None):
    label = display_name or str(resource_id).upper()
    if resource_type == OPTICAL_ENGINE:
        heading = (
            "EEPROM hexdump for {} bank {:x}h page {:x}h "
            "offset {:x}h size {}"
        ).format(label, bank, page, offset, len(data))
    else:
        heading = (
            "EEPROM hexdump for {} page {:x}h offset {:x}h size {}"
        ).format(label, page, offset, len(data))
    click.echo(heading)
    click.echo(_format_eeprom_hexdump(data, offset))


def _print_all_eeprom():
    _print_full_resource_eeprom(OPTICAL_ENGINE)
    click.echo()
    _print_full_resource_eeprom(EXTERNAL_LASER_SOURCE)


@cli.group("read-eeprom", invoke_without_command=True)
@click.pass_context
def read_eeprom(ctx):
    """Read raw CMIS EEPROM data; omit a target to dump all CPO EEPROMs."""
    if ctx.invoked_subcommand is None:
        try:
            _print_all_eeprom()
        except CpoCommandError as exc:
            raise click.ClickException(str(exc))


@read_eeprom.command("interface")
@click.argument("port")
@click.option("--oe", is_flag=True, help="Read the mapped Optical Engine.")
@click.option("--els", is_flag=True, help="Read the mapped External Laser Source.")
@click.option("-n", "--page", required=False, type=_parse_integer,
              metavar="INTEGER", help="CMIS page number.")
@click.option("-o", "--offset", required=False, type=_parse_integer,
              metavar="INTEGER", help="Offset within the CMIS page.")
@click.option("-s", "--size", required=False, type=_parse_integer,
              metavar="INTEGER", help="Number of bytes to read.")
def read_eeprom_interface(port, oe, els, page, offset, size):
    """Read EEPROM through a front-panel interface mapping."""
    try:
        target = _interface_target_option(oe, els)
        index, bank = _interface_eeprom_target(port, target)
        if not _eeprom_range_requested(page, offset, size):
            resource_id, cpo = _single_resource(target, index)
            click.echo(_format_full_eeprom(
                target, resource_id, cpo, [bank],
                "port {} ({})".format(port, str(resource_id).upper()),
            ).rstrip())
            return
        results = _read_resource_eeprom(
            target, index, bank, page, offset, size
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    for resource_id, data in results:
        _print_eeprom_data(
            target, resource_id, bank, page, offset, data,
            "port {} ({})".format(port, str(resource_id).upper()),
        )


@read_eeprom.command("oe")
@click.option("-i", "--index", required=False, type=_parse_integer,
              metavar="INTEGER",
              help="OE index; omit to read all Optical Engines.")
@click.option("-b", "--bank", required=False, type=_parse_integer,
              metavar="INTEGER",
              help="EEPROM bank; omit for all mapped banks in a full dump.")
@click.option("-n", "--page", required=False, type=_parse_integer,
              metavar="INTEGER", help="CMIS page number.")
@click.option("-o", "--offset", required=False, type=_parse_integer,
              metavar="INTEGER", help="Offset within the CMIS page.")
@click.option("-s", "--size", required=False, type=_parse_integer,
              metavar="INTEGER", help="Number of bytes to read.")
def read_eeprom_oe(index, bank, page, offset, size):
    """Dump one/all OE EEPROMs, or read an explicit byte range."""
    try:
        if not _eeprom_range_requested(page, offset, size):
            _print_full_resource_eeprom(OPTICAL_ENGINE, index, bank)
            return
        target_bank = 0 if bank is None else bank
        results = _read_resource_eeprom(
            OPTICAL_ENGINE, index, target_bank, page, offset, size
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    for resource_id, data in results:
        _print_eeprom_data(
            OPTICAL_ENGINE, resource_id, target_bank, page, offset, data
        )


@read_eeprom.command("els")
@click.option("-i", "--index", required=False, type=_parse_integer,
              metavar="INTEGER",
              help="ELS index; omit to read all External Laser Sources.")
@click.option("-b", "--bank", required=False, type=_parse_integer,
              metavar="INTEGER",
              help="EEPROM bank; omit to use mapped banks in a full dump.")
@click.option("-n", "--page", required=False, type=_parse_integer,
              metavar="INTEGER",
              help="CMIS page number before platform ELS mapping.")
@click.option("-o", "--offset", required=False, type=_parse_integer,
              metavar="INTEGER", help="Offset within the CMIS page.")
@click.option("-s", "--size", required=False, type=_parse_integer,
              metavar="INTEGER", help="Number of bytes to read.")
def read_eeprom_els(index, bank, page, offset, size):
    """Dump one/all ELS EEPROMs, or read an explicit byte range."""
    try:
        if not _eeprom_range_requested(page, offset, size):
            _print_full_resource_eeprom(
                EXTERNAL_LASER_SOURCE, index, bank
            )
            return
        target_bank = 0 if bank is None else bank
        results = _read_resource_eeprom(
            EXTERNAL_LASER_SOURCE, index, target_bank, page, offset, size
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    for resource_id, data in results:
        _print_eeprom_data(
            EXTERNAL_LASER_SOURCE, resource_id,
            target_bank, page, offset, data
        )


@cli.group("write-eeprom")
def write_eeprom():
    """Write raw CMIS EEPROM data for engineering debug."""


@write_eeprom.command("interface")
@click.argument("port")
@click.option("--oe", is_flag=True, help="Write the mapped Optical Engine.")
@click.option("--els", is_flag=True, help="Write the mapped External Laser Source.")
@click.option("-n", "--page", required=True, type=_parse_integer,
              metavar="INTEGER", help="CMIS page number.")
@click.option("-o", "--offset", required=True, type=_parse_integer,
              metavar="INTEGER", help="Offset within the CMIS page.")
@click.option("-d", "--data", required=True,
              help="Hexadecimal bytes, for example '01 02 ff'.")
def write_eeprom_interface(port, oe, els, page, offset, data):
    """Write EEPROM through a front-panel interface mapping."""
    try:
        target = _interface_target_option(oe, els)
        index, bank = _interface_eeprom_target(port, target)
        payload = _parse_hex_data(data)
        _write_resource_eeprom(
            target, index, bank, page, offset, payload
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))


@write_eeprom.command("oe")
@click.option("-i", "--index", required=True, type=_parse_integer,
              metavar="INTEGER", help="OE index.")
@click.option("-b", "--bank", default=0, show_default=True,
              type=_parse_integer, metavar="INTEGER", help="EEPROM bank.")
@click.option("-n", "--page", required=True, type=_parse_integer,
              metavar="INTEGER", help="CMIS page number.")
@click.option("-o", "--offset", required=True, type=_parse_integer,
              metavar="INTEGER", help="Offset within the CMIS page.")
@click.option("-d", "--data", required=True,
              help="Hexadecimal bytes, for example '01 02 ff'.")
def write_eeprom_oe(index, bank, page, offset, data):
    """Write raw EEPROM bytes to an Optical Engine."""
    try:
        payload = _parse_hex_data(data)
        _write_resource_eeprom(
            OPTICAL_ENGINE, index, bank, page, offset, payload
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))


@write_eeprom.command("els")
@click.option("-i", "--index", required=True, type=_parse_integer,
              metavar="INTEGER", help="ELS index.")
@click.option("-b", "--bank", default=0, show_default=True,
              type=_parse_integer, metavar="INTEGER", help="EEPROM bank.")
@click.option("-n", "--page", required=True, type=_parse_integer,
              metavar="INTEGER",
              help="CMIS page number before platform ELS mapping.")
@click.option("-o", "--offset", required=True, type=_parse_integer,
              metavar="INTEGER", help="Offset within the CMIS page.")
@click.option("-d", "--data", required=True,
              help="Hexadecimal bytes, for example '01 02 ff'.")
def write_eeprom_els(index, bank, page, offset, data):
    """Write raw EEPROM bytes to an External Laser Source."""
    try:
        payload = _parse_hex_data(data)
        _write_resource_eeprom(
            EXTERNAL_LASER_SOURCE, index, bank, page, offset, payload
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))


def main():
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return ERROR_INVALID_RESOURCE
    return 0


if __name__ == "__main__":
    sys.exit(main())
