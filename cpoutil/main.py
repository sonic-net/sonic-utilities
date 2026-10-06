"""Command-line utility for Co-Packaged Optics devices."""

import json
import re
import sys

import click
from tabulate import tabulate

from sonic_platform_base.sonic_xcvr.cpo.cpo_base import CpoBase
from utilities_common import platform_sfputil_helper
from utilities_common.platform_sfputil_helper import (
    CMIS_INFO_FIELD_MAP,
    CMIS_DOM_CHANNEL_MONITOR_MAP,
    DOM_CHANNEL_THRESHOLD_MAP,
    DOM_MODULE_MONITOR_MAP,
    DOM_MODULE_THRESHOLD_MAP,
    CMIS_DOM_VALUE_UNIT_MAP as DOM_VALUE_UNIT_MAP,
    DOM_CHANNEL_THRESHOLD_UNIT_MAP,
    DOM_MODULE_THRESHOLD_UNIT_MAP,
    format_application_advertisement,
    format_dict_value_to_string,
    format_value_with_unit as _value_with_unit,
    get_physical_port_name,
    hexdump,
    natural_sort_key as _natural_sort_key,
)

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
    **CMIS_INFO_FIELD_MAP,
    'lane_count': 'Laser Count',
    'control_mode': 'Control Mode',
    'max_optical_power': 'Maximum Optical Power',
    'min_optical_power': 'Minimum Optical Power',
    'max_laser_bias': 'Maximum Laser Bias',
    'min_laser_bias': 'Minimum Laser Bias',
}


ELS_DOM_MONITOR_MAP = {
    "temperature": "Temperature",
    "voltage": "Vcc",
    "icc": "Icc",
}

ELS_THRESHOLD_MAP = {
    "temperature_alarm_high": "TempHighAlarm",
    "temperature_alarm_low": "TempLowAlarm",
    "temperature_warn_high": "TempHighWarning",
    "temperature_warn_low": "TempLowWarning",
    "voltage_alarm_high": "VccHighAlarm",
    "voltage_alarm_low": "VccLowAlarm",
    "voltage_warn_high": "VccHighWarning",
    "voltage_warn_low": "VccLowWarning",
    "optical_power_alarm_high": "TxPowerHighAlarm",
    "optical_power_alarm_low": "TxPowerLowAlarm",
    "optical_power_warn_high": "TxPowerHighWarning",
    "optical_power_warn_low": "TxPowerLowWarning",
    "laser_bias_alarm_high": "TxBiasHighAlarm",
    "laser_bias_alarm_low": "TxBiasLowAlarm",
    "laser_bias_warn_high": "TxBiasHighWarning",
    "laser_bias_warn_low": "TxBiasLowWarning",
}


ELS_DOM_MONITOR_UNIT_MAP = {
    "temperature": "C",
    "voltage": "Volts",
    "icc": "A",
}

ELS_THRESHOLD_UNIT_MAP = {
    key: (
        "C" if "temp" in key else
        "Volts" if "voltage" in key or "vcc" in key else
        "mA" if "laser_bias" in key or "txbias" in key else
        "dBm"
    )
    for key in ELS_THRESHOLD_MAP
}


class CpoCommandError(RuntimeError):
    """Raised when a CPO resource or platform API is unavailable."""


def load_platform_chassis():
    """Reuse the platform chassis shared by SONiC CLI helpers."""
    global platform_chassis

    platform_chassis = platform_sfputil_helper.load_chassis()
    if platform_chassis is None:
        raise CpoCommandError("Platform chassis is unavailable")


def load_current_port_config():
    """Load shared port mappings and snapshot active ASIC lanes for CPO."""
    global current_port_config

    if platform_sfputil_helper.platform_sfputil is None:
        platform_sfputil_helper.load_platform_sfputil()
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()
    current_port_config = {}
    for port in platform_sfputil_helper.get_logical_list():
        lanes = platform_sfputil_helper.get_value_from_db_by_field(
            "CONFIG_DB", "PORT", "lanes", port
        )
        current_port_config[port] = {
            "index": platform_sfputil_helper.get_validated_physical_port_list(port),
            "lanes": _parse_port_lanes(lanes, port),
        }

    if not current_port_config:
        raise CpoCommandError("Active PORT configuration is unavailable")


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


def get_port_config_entry(logical_port):
    """Return one active PORT entry from the cpoutil-owned configuration."""
    port_name = str(logical_port)
    entry = current_port_config.get(port_name)
    if entry is None:
        raise CpoCommandError(
            "No active PORT configuration found for '{}'".format(port_name)
        )
    return entry


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
        platform_sfputil_helper.get_validated_physical_port_list(logical_port)
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
    """Resolve ELS lasers using the explicit ASIC lane topology."""
    mapping = mapping or get_cpo_interface_mapping(logical_port)
    lane_positions = get_cpo_lane_positions(logical_port, mapping)
    if not mapping.laser_ids:
        return (), ()
    selected_lanes = {mapping.lanes[index] for index in lane_positions}
    if not mapping.laser_to_asic_lane_mapping:
        # Legacy topologies list lasers for a whole interface, but cannot
        # safely identify which lasers serve a breakout subport.
        if selected_lanes == set(mapping.lanes):
            shared = {
                laser for other in cpo_mapping.get_interfaces()
                if other.port != mapping.port and other.els_id == mapping.els_id
                for laser in other.laser_ids
            }
            return mapping.laser_ids, tuple(
                laser for laser in mapping.laser_ids if laser in shared
            )
        raise CpoCommandError(
            "CPO interface '{}' needs laser_to_asic_lane_mapping to resolve "
            "breakout port '{}'".format(mapping.port, logical_port)
        )

    selected = []
    shared = []
    for laser_id in mapping.laser_ids:
        laser_lanes = set(mapping.laser_to_asic_lane_mapping[laser_id])
        overlap = selected_lanes.intersection(laser_lanes)
        if not overlap:
            continue
        selected.append(laser_id)
        if overlap != laser_lanes:
            shared.append(laser_id)
    return tuple(selected), tuple(shared)


def get_interface_context(logical_port):
    """Resolve static CPO mapping and active breakout data for one port."""
    mapping = get_cpo_interface_mapping(logical_port)
    lane_positions = get_cpo_lane_positions(logical_port, mapping)
    laser_ids, shared_laser_ids = get_cpo_laser_ids(logical_port, mapping)
    return {
        "mapping": mapping,
        "lane_positions": lane_positions,
        "lane_mask": sum(1 << lane for lane in lane_positions),
        "laser_ids": laser_ids,
        "shared_laser_ids": shared_laser_ids,
    }


def load_cpo_object_map():
    """Build the global OE/ELS/port to CPO object mapping from cpo.json."""
    global cpo_mapping, cpo_oe_bank_counts, cpo_object_map

    from sonic_py_common import device_info

    cpo_data = device_info.get_cpo_data()

    if cpo_data is None:
        raise CpoCommandError("CPO topology is unavailable for this platform")
    cpo_mapping = CpoMapping(cpo_data, current_port_config)
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
            if cpo is None:
                continue
            if not isinstance(cpo, CpoBase):
                raise CpoCommandError(
                    "Physical port {} did not return a CpoBase object".format(
                        physical_port
                    )
                )
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
    return [
        (name, physical_port, cpo)
        for name, physical_port, cpo, _ in get_port_cpo_entries(logical_port)
    ]


def get_port_cpo_entries(logical_port=None):
    """Return (display name, physical port, CPO object, logical port) tuples.

    The display name labels each member of a ganged port; use the logical
    port for topology and lane lookups.
    """
    if logical_port is None:
        logical_ports = sorted(current_port_config, key=_natural_sort_key)
    else:
        logical_ports = [logical_port]

    objects = []
    for port_name in logical_ports:
        physical_ports = platform_sfputil_helper.get_validated_physical_port_list(port_name)
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
                port_name,
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


def get_oe_api(cpo, label):
    """Get the public OE API from a CPO object."""
    try:
        api = cpo.oe.get_api()
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


def get_els_api(cpo, label):
    """Get the public ELSFP API from a CPO object."""
    try:
        api = cpo.elsfp.get_api()
    except NotImplementedError as exc:
        raise CpoCommandError(
            "{} ELSFP API is not implemented".format(label)
        ) from exc
    except Exception as exc:
        raise CpoCommandError(
            "Failed to get {} ELSFP API: {}".format(label, exc)
        ) from exc
    if api is None:
        raise CpoCommandError("{} ELSFP API is unavailable".format(label))
    return api


def get_cpo_presence(cpo, label):
    """Read virtual-module presence without inferring it from an endpoint."""
    try:
        present = cpo.get_presence()
    except (NotImplementedError, AttributeError) as exc:
        raise CpoCommandError(
            "CPO presence is not implemented for '{}'".format(label)
        ) from exc
    except Exception as exc:
        raise CpoCommandError(
            "Failed to read CPO presence for '{}': {}".format(label, exc)
        ) from exc
    if not isinstance(present, bool):
        raise CpoCommandError(
            "CPO presence API returned invalid data for '{}'".format(label)
        )
    return present


def get_els_lpmode(_api):
    """Derive ELS low-power state from the public ELSFP status API."""
    status = _api.get_elsfp_status()
    if not isinstance(status, dict):
        raise CpoCommandError("The ELSFP status API returned no data")

    if "module_low_power_state" in status:
        return _normalize_lpmode(status["module_low_power_state"])

    module_state = status.get("module_state")
    if module_state is not None:
        normalized = str(module_state).strip().lower()
        if normalized == "modulelowpwr":
            return True
        if normalized == "moduleready":
            return False
        raise CpoCommandError(
            "Unable to normalize ELS module state {!r} as low-power "
            "mode".format(
                module_state
            )
        )

    raise NotImplementedError(
        "The active CPO backend does not report ELS low-power state"
    )


def set_els_lpmode(api, low_power):
    """Set ELS low-power mode through the active ELSFP backend."""
    return api.set_lpmode(low_power)


def reset_els(api):
    """Reset the ELS through its public API, independently of the OE."""
    return api.reset()


def set_els_tx_disable(api, lane_mask, disable):
    """Control ELS output through the public per-lane enable API."""
    return api.set_per_lane_enable(lane_mask, not disable)


def get_oe_bank_apis(resource_id):
    """Resolve one API per mapped OE bank before any reads or writes."""
    bank_ports = {}
    for mapping in cpo_mapping.get_interfaces():
        if mapping.oe_name == resource_id:
            bank_ports.setdefault(mapping.oe_bank, []).extend(mapping.physical_ports)
    targets = []
    for bank, physical_ports in sorted(bank_ports.items()):
        for physical_port in dict.fromkeys(physical_ports):
            cpo = cpo_object_map[PORT].get(physical_port)
            if cpo is not None:
                targets.append((bank, get_oe_api(
                    cpo, "{} bank {}".format(resource_id, bank)
                )))
                break
        else:
            raise CpoCommandError(
                "No CPO object is available for '{}' bank {}".format(
                    resource_id, bank
                )
            )
    if not targets:
        raise CpoCommandError(
            "No OE bank mapping is available for '{}'".format(resource_id)
        )
    return targets


def get_els_control_targets(resource_id):
    """Return one ELS API and combined lane mask for each ELS bank."""
    targets = {}
    for mapping in cpo_mapping.get_interfaces():
        if mapping.els_name != resource_id:
            continue
        local_mask = sum(1 << (laser % 8) for laser in mapping.laser_ids)
        if not local_mask:
            continue
        bank = mapping.els_bank
        target = targets.get(bank)
        if target is not None:
            target[1] |= local_mask
            continue
        for physical_port in mapping.physical_ports:
            cpo = cpo_object_map[PORT].get(physical_port)
            if cpo is None:
                continue
            api = get_els_api(cpo, resource_id)
            targets[bank] = [api, local_mask]
            break

    if not targets:
        raise CpoCommandError(
            "No ELS laser mapping is available for '{}'".format(resource_id)
        )
    return [tuple(target) for target in targets.values()]


def _get_els_lane_count(info):
    """Return the number of lasers reported by the public ELSFP API."""
    if not isinstance(info, dict):
        return None
    for key in ("lane_count", "laser_count"):
        try:
            count = int(info.get(key))
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return None


def _filter_els_dom_lanes(values, lane_count):
    """Remove per-lane ELS values outside the reported laser count."""
    if not isinstance(values, dict) or lane_count is None:
        return values

    filtered = {}
    for key, value in values.items():
        match = re.search(r"lane(\d+)$", str(key), re.IGNORECASE)
        if match and int(match.group(1)) > lane_count:
            continue
        filtered[key] = value
    return filtered


def _filter_els_monitor_lanes(values, lane_count):
    """Remove zero-based laser monitor fields outside the ELS lane count."""
    if lane_count is None:
        return values
    if isinstance(values, (list, tuple)):
        return values[:lane_count]
    if not isinstance(values, dict):
        return values

    filtered = {}
    for key, value in values.items():
        match = re.search(r"Laser(\d+)", str(key), re.IGNORECASE)
        if match and int(match.group(1)) >= lane_count:
            continue
        filtered[key] = value
    return filtered


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


def _select_els_laser_values(values, laser_ids):
    """Select ELS lane states assigned to one logical interface."""
    normalized = _normalize_lane_values(values)
    selected = {}
    for laser in laser_ids:
        source_key = "lane{:02d}".format(laser % 8)
        if source_key not in normalized:
            raise CpoCommandError(
                "Platform API did not return data for ELS laser {}".format(
                    laser
                )
            )
        selected["lane{:02d}".format(laser)] = normalized[source_key]
    return selected


def _ordered_top_level(records):
    """Naturally order record identifiers without reordering nested fields."""
    if not isinstance(records, dict):
        return records
    return {
        key: records[key]
        for key in sorted(records, key=_natural_sort_key)
    }


def _json_records(records):
    return json.dumps(_ordered_top_level(records), indent=4)


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
            values = format_application_advertisement(info[key])
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

        if key in (
                "supported_max_tx_power", "supported_min_tx_power",
                "max_optical_power", "min_optical_power"):
            value = _value_with_unit(value, "dBm")
        elif key in (
                "supported_max_laser_freq", "supported_min_laser_freq"):
            value = _value_with_unit(value, "GHz")
        elif key in ("max_laser_bias", "min_laser_bias"):
            value = _value_with_unit(value, "mA")
        lines.append("{}{}: {}".format(indent, label, value))
    return lines


def _append_dom_values(lines, values, value_map, unit_map, alignment=0):
    sorted_keys = sorted(
        value_map, key=lambda key: _natural_sort_key(key, case_sensitive=True)
    )
    lines.extend(format_dict_value_to_string(
        sorted_keys, values, value_map, unit_map, alignment).splitlines())


def _format_oe_dom(dom_values):
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

    displayed_keys = set().union(
        CMIS_DOM_CHANNEL_MONITOR_MAP,
        DOM_CHANNEL_THRESHOLD_MAP,
        DOM_MODULE_MONITOR_MAP,
        DOM_MODULE_THRESHOLD_MAP,
    )
    _append_additional_dom_values(lines, values, displayed_keys)
    return lines


def _format_els_dom(dom_values):
    """Format public ELSFP fields within their own endpoint section."""
    values = dom_values if isinstance(dom_values, dict) else {}
    indent = " " * 8
    lines = []

    els_monitor_map = dict(ELS_DOM_MONITOR_MAP)
    els_monitor_units = dict(ELS_DOM_MONITOR_UNIT_MAP)

    lane_monitor_fields = {
        "laser_bias_current": ("Bias Current", "mA"),
        "optical_power": ("Optical Power", "dBm"),
        "voltage": ("Voltage", "Volts"),
    }
    for key in values:
        match = re.fullmatch(
            r"(laser_bias_current|optical_power|voltage)_lane(\d+)",
            str(key),
        )
        if not match:
            continue
        field, lane = match.groups()
        label, unit = lane_monitor_fields[field]
        els_monitor_map[key] = "Laser {} {}".format(lane, label)
        els_monitor_units[key] = unit
    lines.append("{}MonitorValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        els_monitor_map,
        els_monitor_units,
    )

    lines.append("{}ELSFPThresholdValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        ELS_THRESHOLD_MAP,
        ELS_THRESHOLD_UNIT_MAP,
    )

    # The public ELSFP API also returns standard CMIS channel thresholds.
    # These are distinct from the ELS laser limits; keep both sets visible.
    if any(key in values and values[key] != "N/A" for key in DOM_CHANNEL_THRESHOLD_MAP):
        lines.append("{}CMISChannelThresholdValues:".format(indent))
        _append_dom_values(
            lines,
            values,
            DOM_CHANNEL_THRESHOLD_MAP,
            DOM_CHANNEL_THRESHOLD_UNIT_MAP,
        )

    displayed_keys = set(els_monitor_map).union(ELS_THRESHOLD_MAP, DOM_CHANNEL_THRESHOLD_MAP)
    _append_additional_dom_values(lines, values, displayed_keys)
    return lines


def _append_additional_dom_values(lines, values, displayed_keys):
    additional_values = {
        key: value for key, value in values.items()
        if key not in displayed_keys and value != "N/A"
    }
    if additional_values:
        lines.append("        AdditionalValues:")
        for field, value in _flatten_record(additional_values):
            lines.append("{}{}: {}".format(
                " " * 16, _display_field(field), _display_value(value)
            ))


def _format_interface_dom(port_name, record):
    if not record["present"]:
        return "{}: CPO EEPROM not detected".format(port_name)
    lines = ["{}: CPO EEPROM detected".format(port_name)]
    for endpoint, formatter in (("oe", _format_oe_dom), ("els", _format_els_dom)):
        data = record[endpoint]
        lines.append("    {}:".format(endpoint.upper()))
        lines.extend(_format_cpo_info(data["info"]))
        values = {}
        for section in ("dom", "thresholds"):
            if isinstance(data[section], dict):
                values.update(data[section])
        lines.extend(formatter(values))
    return "\n".join(lines)


def _local_oe_bank(mapping):
    """Return the OE-local CMIS bank of one topology interface.

    Community topologies declare OE-local banks. Legacy topologies may number
    banks across all OEs (OE n bank b as n * bank_count + b), so the declared
    bank is reduced modulo the OE's advertised bank count. The declared bank is
    never replaced by its position among the mapped banks.
    """
    cpo = cpo_object_map[OPTICAL_ENGINE].get(mapping.oe_name)
    if cpo is None:
        raise CpoCommandError(
            "No CPO object is available for '{}'".format(mapping.oe_name)
        )
    return mapping.oe_bank % _get_oe_bank_count(mapping.oe_name, cpo)


def _interface_mapping_record(logical_port):
    context = get_interface_context(logical_port)
    mapping = context["mapping"]
    oe_lanes = [mapping.lanes[index] for index in context["lane_positions"]]
    els = {
        "id": mapping.els_name.upper(),
        "lasers": list(context["laser_ids"]),
    }
    if mapping.els_bank not in (None, "N/A"):
        els["bank"] = mapping.els_bank
    return {
        "port": str(logical_port),
        "oe": {
            "id": mapping.oe_name.upper(),
            "bank": _local_oe_bank(mapping),
            "lanes": oe_lanes,
        },
        "els": els,
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
    headers = ("Interface", "OE", "OE Lanes", "ELS", "ELS Lasers")
    rows = []
    for record in mappings:
        els = record["els"]
        els_name = els["id"]
        if "bank" in els:
            els_name = "{} bank{}".format(els_name, els["bank"])
        rows.append((
            record["port"],
            "{} bank{}".format(
                record["oe"]["id"], record["oe"]["bank"]
            ),
            ",".join(str(lane) for lane in record["oe"]["lanes"]),
            els_name,
            ",".join(str(laser) for laser in els["lasers"]),
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


def _normalize_lpmode(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in ("low power mode", "low-power mode"):
        return True
    if normalized in ("high power mode", "full power mode"):
        return False
    raise CpoCommandError(
        "Unable to normalize low-power mode value {!r}".format(value)
    )


def _normalize_interrupt_event(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in ("interrupt event occurred", "interrupt asserted"):
        return True
    if normalized in (
            "interrupt event cleared", "interrupt cleared",
            "interrupt not asserted"):
        return False
    raise CpoCommandError(
        "Unable to normalize interrupt event value {!r}".format(value)
    )


def _normalize_els_status(status):
    """Convert vendor ELS status fields to the cpoutil semantic contract."""
    if not isinstance(status, dict):
        raise CpoCommandError("The ELSFP status API returned no data")

    normalized = {}
    if status.get("module_state") is not None:
        normalized["module_state"] = status["module_state"]
    if "module_low_power_state" in status:
        normalized["low_power_mode"] = _normalize_lpmode(
            status["module_low_power_state"]
        )
    if "interrupt_status" in status:
        normalized["interrupt_event"] = _normalize_interrupt_event(
            status["interrupt_status"]
        )
    if not normalized:
        raise CpoCommandError("The ELSFP status API returned no known fields")
    return normalized


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
            output.append(part.replace("_", " "))
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
                  boolean_values=None, field_header="Field", floatfmt=None):
    """Print platform values using SONiC-style simple tables."""
    if json_output:
        click.echo(_json_records(records))
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
    options = {"tablefmt": "simple"}
    if floatfmt is not None:
        options["floatfmt"] = floatfmt
    click.echo(tabulate(rows, table_headers, **options))


def print_speed_records(records, json_output):
    if json_output:
        click.echo(_json_records(records))
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


def _lane_lasers(context):
    """Map each selected OE lane to the ELS laser that feeds its ASIC lane.

    The OE lane position is translated to its ASIC lane ID, which is looked up
    in the topology's laser_to_asic_lane_mapping. A lane maps to None when the
    topology does not associate exactly one of the interface's lasers with it.
    """
    mapping = context["mapping"]
    laser_lanes = mapping.laser_to_asic_lane_mapping or {}
    lane_lasers = {}
    for position in context["lane_positions"]:
        asic_lane = mapping.lanes[position]
        lasers = [
            laser for laser in context["laser_ids"]
            if asic_lane in laser_lanes.get(laser, ())
        ]
        lane_lasers["lane{:02d}".format(position)] = (
            lasers[0] if len(lasers) == 1 else None
        )
    return lane_lasers


def print_lane_status_records(records, json_output):
    if json_output:
        click.echo(_json_records(records))
        return

    lane_rows = []
    status_rows = []
    for interface, values in records.items():
        lane_states = values.get("Data Path State Indicator", {})
        lanes = sorted(lane_states, key=_natural_sort_key)
        lasers = values.get("ELS Lasers", [])
        lane_lasers = values.get("Lane Lasers", {})
        els_lane_states = values.get("ELS Lane State", {})
        shared = set(values.get("Shared ELS Lasers", []))
        els_id = values.get("ELS", "N/A")
        for lane in lanes:
            # Use only the topology's lane-to-laser association; never infer
            # it from row positions.
            laser = lane_lasers.get(lane)
            if laser is None:
                laser_display, laser_state, shared_display = "N/A", "N/A", "N/A"
            else:
                laser_display = laser
                laser_state = els_lane_states.get("lane{:02d}".format(laser), "N/A")
                shared_display = "Yes" if laser in shared else "No"
            lane_rows.append((
                interface,
                _display_field(lane),
                lane_states[lane],
                els_id,
                laser_display,
                laser_state,
                shared_display,
            ))
        if lasers and any(lane_lasers.get(lane) is None for lane in lanes):
            status_rows.append((
                interface, els_id, "Lasers (per-lane association unavailable)",
                ", ".join(
                    "{}: {}".format(laser, els_lane_states.get("lane{:02d}".format(laser), "N/A"))
                    for laser in lasers
                ),
            ))

        status = values.get("ELS Status")
        if isinstance(status, dict):
            for field in sorted(status, key=_natural_sort_key):
                status_rows.append((
                    interface,
                    els_id,
                    _display_field(field),
                    _display_value(
                        status[field],
                        ("On", "Off") if field == "low_power_mode" else None,
                    ),
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
            "ELS Lane State",
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


def initialize_command_platform():
    """Translate initialization failures when a hardware command executes."""
    try:
        initialize_platform()
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))


class CpoCommand(click.Command):
    """Load the platform after command arguments and help have been parsed."""

    def invoke(self, ctx):
        initialize_command_platform()
        return super().invoke(ctx)


class CpoGroup(click.Group):
    """Apply deferred platform loading to commands at every nesting level."""

    command_class = CpoCommand
    group_class = type


@click.group(cls=CpoGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """Debug and manually provision Co-Packaged Optics devices."""


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
                physical_ports = platform_sfputil_helper.get_validated_physical_port_list(
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
        click.echo(_json_records({
            record["port"]: {
                "oe": record["oe"],
                "els": record["els"],
            }
            for record in records
        }))
    else:
        click.echo(_format_map_table(records))


@show_interface.command("presence")
@click.argument("port", required=False)
@output_option
def show_interface_presence(port, json_output):
    """Display CPO virtual-module presence for each interface."""
    records = {}
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            records[port_name] = get_cpo_presence(cpo, port_name)
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    print_records(
        records, json_output, ("Interface", "Presence"),
        boolean_values=("Present", "Not present"),
    )


@show_interface.command("lpmode")
@click.argument("port", required=False)
@output_option
def show_interface_lpmode(port, json_output):
    """Display the low-power mode of each interface's CPO virtual module."""
    records = {}
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            lpmode = _call_vmodule(cpo, "get_lpmode")
            if not isinstance(lpmode, bool):
                raise CpoCommandError(
                    "CPO low-power mode is unavailable for '{}'".format(port_name)
                )
            records[port_name] = lpmode
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    print_records(
        records, json_output, ("Interface", "Low-power Mode"),
        boolean_values=("On", "Off"),
    )


@show_interface.command("dom")
@click.argument("port", required=False)
@output_option
def show_interface_dom(port, json_output):
    """Display CPO EEPROM information and monitoring data.

    OE and ELS data retain public API field names in separate sections.
    JSON includes presence and each endpoint's info, dom and thresholds.
    """
    records = {}
    output = []
    try:
        for port_name, _, cpo in get_port_cpo_objects(port):
            present = get_cpo_presence(cpo, port_name)
            record = {"present": present, "oe": {}, "els": {}}
            records[port_name] = record
            if not present:
                output.append(_format_interface_dom(port_name, record))
                continue
            oe_api = get_oe_api(cpo, port_name)
            els_api = get_els_api(cpo, port_name)

            record["oe"] = {
                "info": oe_api.get_transceiver_info(),
                "dom": oe_api.get_transceiver_dom_real_value(),
                "thresholds": oe_api.get_transceiver_threshold_info(),
            }
            els_info = els_api.get_elsfp_info()
            record["els"] = {
                "info": els_info,
                "dom": _filter_els_dom_lanes(
                    els_api.get_elsfp_dom_real_value(), _get_els_lane_count(els_info)
                ),
                "thresholds": els_api.get_elsfp_threshold_info(),
            }
            output.append(_format_interface_dom(port_name, record))
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    if json_output:
        click.echo(_json_records(records))
    else:
        click.echo("\n\n".join(output))


@show_interface.command("tx_disable")
@click.argument("port", required=False)
@output_option
def show_interface_tx_disable(port, json_output):
    """Display per-lane Tx output state."""
    records = {}
    try:
        for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
            lane_positions = get_cpo_lane_positions(logical_port)
            api = get_oe_api(cpo, port_name)
            values = _select_lane_values(
                api.get_tx_disable(), lane_positions
            )
            records[port_name] = values
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
        boolean_values=("Tx output disable", "Tx output enable"),
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
        for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
            api = get_oe_api(cpo, port_name)
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
            lane_positions = get_cpo_lane_positions(logical_port)
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
        for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
            oe_api = get_oe_api(cpo, port_name)
            els_api = get_els_api(cpo, port_name)
            context = get_interface_context(logical_port)
            records[port_name] = {
                "Data Path State Indicator": _select_lane_values(
                    oe_api.get_datapath_state(), context["lane_positions"]
                ),
                "ELS": context["mapping"].els_name.upper(),
                "ELS Status": _normalize_els_status(
                    els_api.get_elsfp_status()
                ),
                "ELS Lane State": _select_els_laser_values(
                    els_api.get_per_lane_state(), context["laser_ids"]
                ),
                "ELS Lasers": list(context["laser_ids"]),
                "Lane Lasers": _lane_lasers(context),
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
            records[resource_id] = get_oe_api(
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
            records[resource_id] = get_oe_api(
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
            records[resource_id] = get_oe_api(
                cpo, resource_id
            ).get_module_temperature()
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("OE", "Temperature (C)"))


@show_oe.command("input-power")
@click.argument("oe_index", required=False)
@output_option
def show_oe_input_power(oe_index, json_output):
    """Display input optical power for every mapped OE bank.

    Bank IDs come from the topology; media lanes are local to each bank.
    """
    records = {}
    try:
        for resource_id, _ in get_resource_cpo_objects(
                OPTICAL_ENGINE, oe_index):
            records[resource_id] = {}
            for bank, api in get_oe_bank_apis(resource_id):
                try:
                    values = api.get_rx_power()
                except (NotImplementedError, AttributeError) as exc:
                    raise CpoCommandError(
                        "{} bank {} input-power read failed: {}".format(resource_id, bank, exc)
                    ) from exc
                if not isinstance(values, (list, tuple, dict)) or not values:
                    raise CpoCommandError(
                        "{} bank {} input-power API returned no lane data".format(resource_id, bank)
                    )
                records[resource_id]["bank_{}".format(bank)] = values
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("OE", "Input Power (mW)"),
        field_header="Bank / Media Lane",
    )


@show.group("els")
def show_els():
    """Display External Laser Source status."""


@show_els.command("lpmode")
@click.argument("els_index", required=False)
@output_option
def show_els_lpmode(els_index, json_output):
    """Display ELS low-power state."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            api = get_els_api(cpo, resource_id)
            records[resource_id] = get_els_lpmode(api)
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records, json_output, ("ELS", "Low-power Mode"),
        boolean_values=("On", "Off"),
    )


@show_els.command("status")
@click.argument("els_index", required=False)
@output_option
def show_els_status(els_index, json_output):
    """Display the independent ELS module state."""
    records = {}
    try:
        for resource_id, cpo in get_resource_cpo_objects(
                EXTERNAL_LASER_SOURCE, els_index):
            state = get_els_api(cpo, resource_id).get_module_state()
            if state is None:
                raise CpoCommandError("The ELSFP module state API returned no data")
            records[resource_id] = state
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("ELS", "Status"),
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
            api = get_els_api(cpo, resource_id)
            dom = api.get_elsfp_dom_real_value()
            if not isinstance(dom, dict) or "temperature" not in dom:
                raise CpoCommandError(
                    "ELSFP temperature is unavailable for '{}'".format(
                        resource_id
                    )
                )
            records[resource_id] = dom["temperature"]
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
            api = get_els_api(cpo, resource_id)
            lane_count = _get_els_lane_count(api.get_elsfp_info())
            records[resource_id] = _filter_els_monitor_lanes(
                api.get_per_lane_opt_power_monitor(),
                lane_count,
            )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("ELS", "Output Power (mW)"),
        field_header="Laser",
        floatfmt=".2f",
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


def _call_vmodule(cpo, method, *args):
    """Call a CPO virtual-module control, reporting unsupported platforms."""
    function = getattr(cpo, method, None)
    if not callable(function):
        raise CpoCommandError(
            "CPO {} is not implemented for this platform".format(method)
        )
    try:
        return function(*args)
    except NotImplementedError as exc:
        raise CpoCommandError(
            "CPO {} is not implemented for this platform".format(method)
        ) from exc


def _controller_ports(oe_name):
    """Return the logical ports served by one OE controller in the topology."""
    physical_ports = {
        physical_port
        for mapping in cpo_mapping.get_interfaces()
        if mapping.oe_name == oe_name
        for physical_port in mapping.physical_ports
    }
    return sorted(
        (
            port for port in current_port_config
            if physical_ports.intersection(
                platform_sfputil_helper.get_validated_physical_port_list(port)
            )
        ),
        key=_natural_sort_key,
    )


def get_vmodule_targets(ports, all_ports):
    """Resolve one CPO object per controller for comma-separated ports.

    A controller can serve several ports, including breakout subports. Unless
    all_ports is set, every port served by a selected controller must be
    selected, so no port is affected without being named.
    """
    selected = [port.strip() for port in str(ports).split(",") if port.strip()]
    if not selected:
        raise CpoCommandError("At least one port is required")

    targets = {}
    for port in selected:
        port_cpos = get_port_cpo_objects(port)
        oe_name = get_cpo_interface_mapping(port).oe_name
        if oe_name not in targets:
            targets[oe_name] = (port_cpos[0][2], _controller_ports(oe_name))

    unselected = sorted(
        {port for _, controller_ports in targets.values() for port in controller_ports}
        - set(selected),
        key=_natural_sort_key,
    )
    if unselected and not all_ports:
        raise CpoCommandError(
            "The selected CPO controller(s) also serve {}; select all affected "
            "ports or use --all-ports".format(", ".join(unselected))
        )
    return [
        (oe_name, cpo, controller_ports)
        for oe_name, (cpo, controller_ports) in sorted(
            targets.items(), key=lambda item: _natural_sort_key(item[0])
        )
    ]


def _run_vmodule_action(targets, verb, method, *args):
    """Apply one virtual-module control to each selected controller."""
    completed = []
    for oe_name, cpo, controller_ports in targets:
        message = "{} {} ({})".format(
            verb, oe_name.upper(), ", ".join(controller_ports)
        )
        try:
            _run_action(message, lambda cpo=cpo: _call_vmodule(cpo, method, *args))
        except CpoCommandError as exc:
            if completed:
                raise CpoCommandError(
                    "{}; already applied to {}".format(exc, ", ".join(completed))
                ) from exc
            raise
        completed.append(oe_name.upper())


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

        port_cpos = get_port_cpo_objects(port)
        els_api = get_els_api(port_cpos[0][2], mapping.els_name)
        # Resolve both endpoints before writing; an existing method may still
        # raise NotImplementedError when invoked by a platform implementation.
        els_operation = els_api.set_per_lane_enable
        oe_targets = [
            (physical_port, get_oe_api(cpo, port).tx_disable_channel)
            for _, physical_port, cpo in port_cpos
        ]

        laser_mask = sum(
            1 << (laser % 8) for laser in context["laser_ids"]
        )

        def apply_tx_disable():
            completed_oe_ports = []
            try:
                for physical_port, operation in oe_targets:
                    _require_success(
                        operation(context["lane_mask"], disable),
                        "{} OE Tx-disable {}".format(port, state),
                    )
                    completed_oe_ports.append(str(physical_port))
                _require_success(
                    els_operation(laser_mask, not disable),
                    "{} ELS Tx-disable {}".format(port, state),
                )
            except (CpoCommandError, NotImplementedError, AttributeError) as exc:
                if completed_oe_ports:
                    raise CpoCommandError(
                        "{}; OE Tx-disable already applied to physical port(s) "
                        "{}; configuration may be partially applied".format(
                            exc, ", ".join(completed_oe_ports)
                        )
                    ) from exc
                raise
            return True

        _run_action(
            "{} Tx-disable for port {}".format(
                "Enabling" if disable else "Disabling", port
            ),
            apply_tx_disable,
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


ALL_PORTS_HELP = "Apply to every port served by the selected CPO controller(s)."


@config_interface.command("lpmode")
@click.argument("port")
@click.argument("mode", type=click.Choice(["full", "low"]))
@click.option("--all-ports", is_flag=True, help=ALL_PORTS_HELP)
def config_interface_lpmode(port, mode, all_ports):
    """Set full-power or low-power mode of a CPO virtual module.

    PORT is one or more comma-separated ports. The setting applies to the CPO
    controller and every port it serves. It is not persistent: xcvrd restores
    full power when it next provisions the ports.
    """
    low_power = mode == "low"
    try:
        targets = get_vmodule_targets(port, all_ports)
        _run_vmodule_action(
            targets,
            "Enabling low-power mode for" if low_power else "Disabling low-power mode for",
            "set_lpmode", low_power,
        )
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))


@config_interface.command("reset")
@click.argument("port")
@click.option("--all-ports", is_flag=True, help=ALL_PORTS_HELP)
def config_interface_reset(port, all_ports):
    """Reset a CPO virtual module through its controller.

    PORT is one or more comma-separated ports. The reset applies to the CPO
    controller and every port it serves. The affected ports must be
    re-provisioned (admin toggle) after the reset.
    """
    try:
        targets = get_vmodule_targets(port, all_ports)
        _run_vmodule_action(targets, "Resetting", "reset")
    except CpoCommandError as exc:
        raise click.ClickException(str(exc))
    click.echo(
        "Re-provision the affected ports (admin toggle): {}".format(
            ", ".join(port for _, _, ports in targets for port in ports)
        )
    )


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
        api = get_oe_api(cpo, resource_id)
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
    """Reset an Optical Engine through the platform API.

    Module settings may return to defaults. Affected ports may require
    application and datapath reprovisioning after the reset.
    """
    try:
        resource_id, cpo = _single_resource(OPTICAL_ENGINE, oe_index)
        api = get_oe_api(cpo, resource_id)
        _run_action(
            "Resetting {}".format(resource_id.upper()), api.reset
        )
        click.echo(
            "Affected ports may require application and datapath "
            "reprovisioning after the reset."
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config_oe.command("tx_disable")
@click.argument("oe_index")
@click.argument("state", type=click.Choice(["enable", "disable"]))
def config_oe_tx_disable(oe_index, state):
    """Enable or disable Tx-disable across every mapped OE bank."""
    try:
        resource_id, _ = _single_resource(OPTICAL_ENGINE, oe_index)
        targets = get_oe_bank_apis(resource_id)
        disable = state == "enable"

        def apply_tx_disable():
            # CMIS tx_disable() writes the bank bound to this CPO's API,
            # so an OE-wide command must visit each bank explicitly.
            for bank, api in targets:
                _require_success(
                    api.tx_disable(disable),
                    "{} bank {} Tx-disable {}".format(resource_id, bank, state),
                )
            return True

        _run_action(
            "{} Tx-disable for {}".format(
                "Enabling" if disable else "Disabling",
                resource_id.upper(),
            ),
            apply_tx_disable,
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
    """Set ELS endpoint full-power or low-power mode.

    For platforms that control the ELS independently (separate mode). Use
    'config interface lpmode' for the CPO virtual module.
    """
    try:
        resource_id, cpo = _single_resource(
            EXTERNAL_LASER_SOURCE, els_index
        )
        api = get_els_api(cpo, resource_id)
        low_power = mode == "low"
        _run_action(
            "{} low-power mode for {}".format(
                "Enabling" if low_power else "Disabling",
                resource_id.upper(),
            ),
            lambda: set_els_lpmode(api, low_power),
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config_els.command("reset")
@click.argument("els_index")
def config_els_reset(els_index):
    """Reset an External Laser Source endpoint.

    For platforms that control the ELS independently (separate mode). Use
    'config interface reset' for the CPO virtual module.
    """
    try:
        resource_id, cpo = _single_resource(
            EXTERNAL_LASER_SOURCE, els_index
        )
        api = get_els_api(cpo, resource_id)
        _run_action(
            "Resetting {}".format(resource_id.upper()),
            lambda: reset_els(api),
        )
    except (CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))


@config_els.command("tx_disable")
@click.argument("els_index")
@click.argument("state", type=click.Choice(["enable", "disable"]))
def config_els_tx_disable(els_index, state):
    """Enable or disable Tx-disable for every ELS laser."""
    try:
        resource_ids = cpo_mapping.resolve_resource_ids(
            els_index, EXTERNAL_LASER_SOURCE
        )
        if len(resource_ids) != 1:
            raise CpoCommandError("Exactly one els index is required")
        resource_id = resource_ids[0]
        targets = get_els_control_targets(resource_id)
        disable = state == "enable"

        def apply_tx_disable():
            for api, laser_mask in targets:
                _require_success(
                    set_els_tx_disable(api, laser_mask, disable),
                    "{} ELS Tx-disable {}".format(resource_id, state),
                )
            return True

        _run_action(
            "{} Tx-disable for {}".format(
                "Enabling" if disable else "Disabling",
                resource_id.upper(),
            ),
            apply_tx_disable,
        )
    except (CpoCommandError, CpoMappingError, KeyError,
            NotImplementedError, AttributeError) as exc:
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
    # Offsets 0-127 always address lower memory; a nonzero page only owns
    # offsets 128-255. Accepting a lower offset would alias the previous page.
    if page != 0 and offset < EEPROM_PAGE_OFFSET:
        raise CpoCommandError(
            "Invalid offset 0x{:02x} for page {:x}h; valid range: 80h-FFh".format(
                offset, page
            )
        )
    if size <= 0:
        raise CpoCommandError("size must be greater than zero")
    if offset + size > 0x100:
        raise CpoCommandError(
            "EEPROM range crosses the CMIS page boundary"
        )


def _get_oe_bank_count(resource_id, cpo):
    """Return the number of CMIS banks advertised by one OE."""
    bank_count = cpo_oe_bank_counts.get(resource_id)
    if bank_count is not None:
        return bank_count
    api = get_oe_api(cpo, str(resource_id).upper())
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
    return bank_count


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

    bank_count = _get_oe_bank_count(resource_id, cpo)
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

    physical_bank = _physical_eeprom_bank(
        resource_type, resource_id, cpo, bank
    )
    return CmisPage.linear_offset(page, physical_bank, offset)


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


def _get_eeprom_device(cpo, resource_type):
    """Return the public OE or ELSFP EEPROM endpoint."""
    return cpo.oe if resource_type == OPTICAL_ENGINE else cpo.elsfp


def _get_els_eeprom(cpo, resource_id):
    """Keep ELS page addresses and reads on the same selected API."""
    api = get_els_api(cpo, str(resource_id).upper())
    eeprom = getattr(api, "xcvr_eeprom", None)
    if not callable(getattr(eeprom, "reader", None)):
        raise CpoCommandError(
            "ELS EEPROM reader is unavailable for '{}'".format(resource_id)
        )
    return eeprom


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
    device = _get_eeprom_device(cpo, resource_type)
    try:
        _run_action(
            "Writing EEPROM for {}".format(str(resource_id).upper()),
            lambda: device.write_eeprom(linear_offset, len(data), data),
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
        # The selected ELS endpoint and its memory map resolve ELS addressing;
        # raw ELS EEPROM access, like 'read-eeprom els', uses bank 0.
        return mapping.els_id, 0
    raise CpoCommandError("Specify exactly one of --oe or --els")


def _interface_target_option(oe, els):
    if oe == els:
        raise CpoCommandError("Specify exactly one of --oe or --els")
    return OPTICAL_ENGINE if oe else EXTERNAL_LASER_SOURCE


EEPROM_PAGE_SIZE = 128
EEPROM_PAGE_OFFSET = 128
EEPROM_DUMP_INDENT = " " * 8


def _format_eeprom_hexdump(data, address, indent=EEPROM_DUMP_INDENT):
    return hexdump(indent, data, address, start_newline=False)


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

    local_banks = sorted({
        _local_oe_bank(interface)
        for interface in cpo_mapping.get_interfaces()
        if interface.oe_name == resource_id
    })
    return local_banks or [0]


def _read_one_eeprom(resource_type, resource_id, cpo,
                     bank, page, offset, size):
    _validate_eeprom_range(bank, page, offset, size)
    linear_offset = _eeprom_linear_offset(
        resource_type, resource_id, cpo, bank, page, offset
    )
    if resource_type == EXTERNAL_LASER_SOURCE:
        reader = _get_els_eeprom(cpo, resource_id).reader
    else:
        reader = _get_eeprom_device(cpo, resource_type).read_eeprom
    return _read_eeprom_at(reader, resource_id, linear_offset, size)


def _read_eeprom_at(reader, resource_id, linear_offset, size):
    """Read one range at the address selected by a CPO memory map."""
    try:
        data = reader(linear_offset, size)
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


def _full_eeprom_sections(banks):
    """Return the standard OE pages printed by a full dump."""
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


def _els_eeprom_sections(eeprom, resource_id):
    """Read physical pages already resolved by the selected ELS API map."""
    from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages import (
        CmisAdministrativeLowerPage,
    )

    mem_map = getattr(eeprom, "mem_map", None)
    if mem_map is None or not getattr(mem_map, "pages", None):
        raise CpoCommandError(
            "ELS EEPROM memory map is unavailable for '{}'".format(
                resource_id
            )
        )

    sections = []
    for page in mem_map.pages:
        lower = isinstance(page, CmisAdministrativeLowerPage)
        offset = 0 if lower else EEPROM_PAGE_OFFSET
        title = "{} page {:x}h".format(
            "Lower" if lower else "Upper", page.page
        )
        if page.bank:
            title += " bank {:x}h".format(page.bank)
        sections.append((title, page.getaddr(offset), offset))
    return sections


def _format_full_eeprom(resource_type, resource_id, cpo, banks,
                        display_name=None):
    label = display_name or str(resource_id).upper()
    lines = ["EEPROM hexdump for {}".format(label)]
    if resource_type == EXTERNAL_LASER_SOURCE:
        eeprom = _get_els_eeprom(cpo, resource_id)
        for title, linear_offset, offset in _els_eeprom_sections(
                eeprom, resource_id):
            lines.append("{}{}".format(EEPROM_DUMP_INDENT, title))
            data = _read_eeprom_at(
                eeprom.reader, resource_id, linear_offset, EEPROM_PAGE_SIZE
            )
            lines.append(_format_eeprom_hexdump(data, offset))
            lines.append("")
        return "\n".join(lines)

    for title, bank, page, offset, size in _full_eeprom_sections(banks):
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
        initialize_command_platform()
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
              help="Physical CMIS page number on the ELS device.")
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
              help="Physical CMIS page number on the ELS device.")
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
