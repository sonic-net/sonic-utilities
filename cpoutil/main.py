"""Command-line utility for Co-Packaged Optics devices."""

from contextlib import contextmanager
import json
import math
import os
import re
import sys

import click
from tabulate import tabulate

from sonic_py_common import multi_asic
from sonic_platform_base.sonic_xcvr.cpo.cpo_base import CpoBase
from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages.consts import CMIS_LANES_PER_BANK
from sonic_platform_base.sonic_xcvr.optoe_eeprom_rw import OptoeEepromReadWriteMixin
from sonic_platform_base.sonic_xcvr.xcvr_eeprom import XcvrEeprom
from utilities_common import platform_sfputil_helper
from utilities_common.platform_sfputil_helper import (
    CMIS_DOM_CHANNEL_MONITOR_MAP,
    DOM_CHANNEL_THRESHOLD_MAP,
    DOM_CHANNEL_THRESHOLD_UNIT_MAP,
    format_application_advertisement,
    format_dict_value_to_string,
    format_value_with_unit as _value_with_unit,
    get_physical_port_name,
    hexdump,
    natural_sort_key as _natural_sort_key,
)

from cpoutil.helper import (
    CPO_INFO_FIELD_MAP,
    CPO_INFO_LANE_FIELD_MAP,
    CPO_DOM_MODULE_MONITOR_MAP,
    CPO_DOM_MODULE_THRESHOLD_MAP,
    CPO_DOM_VALUE_UNIT_MAP,
    CPO_DOM_MODULE_THRESHOLD_UNIT_MAP,
    ELS_DOM_MONITOR_MAP,
    ELS_STATUS_FIELD_MAP,
    ELS_THRESHOLD_MAP,
    ELS_DOM_MONITOR_UNIT_MAP,
    ELS_THRESHOLD_UNIT_MAP,
)

from cpoutil.mapping import CpoMapping, CpoMappingError
from cpoutil.mapping import EXTERNAL_LASER_SOURCE, OPTICAL_ENGINE, PORT


ERROR_PERMISSIONS = 1
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


class CpoCommandError(RuntimeError):
    """Raised when a CPO resource or platform API is unavailable."""


UNRESOLVED_LASERS = "N/A (needs laser_to_asic_lane_mapping)"


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
    # Read each namespace once instead of discovering it for every port.
    port_table = multi_asic.get_port_table()
    current_port_config = {}
    for port in platform_sfputil_helper.get_logical_list():
        lanes = port_table.get(port, {}).get("lanes")
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
    return entry["lanes"]


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
                try:
                    sfp = platform_chassis.get_sfp(physical_port)
                except (NotImplementedError, AttributeError, IndexError):
                    sfp = None
                if sfp is not None:
                    raise CpoCommandError(
                        "Port '{}' is an SFP port; please use sfputil instead".format(port_name)
                    )
                raise CpoCommandError(
                    "No CPO or SFP object is available for port '{}'".format(port_name)
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


def _select_els_laser_values(values, laser_ids, bank):
    """Select ELS lane states assigned to one logical interface."""
    normalized = _normalize_lane_values(values)
    selected = {}
    for laser in laser_ids:
        laser_bank, local_lane = divmod(laser, CMIS_LANES_PER_BANK)
        if laser_bank != bank:
            raise CpoCommandError(
                "ELS laser {} requires bank {}, but API uses bank {}".format(
                    laser, laser_bank, bank
                )
            )
        source_key = "lane{:02d}".format(local_lane)
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


def _json_safe(value):
    """Replace non-finite numbers, which standard JSON cannot represent, with None.

    For example, a 0 mW power threshold converted to dBm is -inf.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _json_records(records):
    return json.dumps(_json_safe(_ordered_top_level(records)), indent=4, allow_nan=False)


def _combine_cable_info(info):
    """Use the API's cable length descriptor as the field name."""
    if not isinstance(info, dict) or not info.get("cable_type"):
        return info
    combined = dict(info)
    label = combined.pop("cable_type")
    combined[label] = combined.pop("cable_length", "N/A")
    return combined


def _info_field_label(key):
    if key in CPO_INFO_FIELD_MAP:
        return CPO_INFO_FIELD_MAP[key]
    match = re.fullmatch(r"(fiber_mapping|frequency)_lane(\d+)", str(key))
    if match:
        field, lane = match.groups()
        return "Laser {} {}".format(lane, CPO_INFO_LANE_FIELD_MAP[field])
    return key


def _format_cpo_info(info):
    indent = " " * 8
    if not isinstance(info, dict):
        return ["{}EEPROM info: N/A".format(indent)]

    info = _combine_cable_info(info)
    lines = []
    keys = sorted(
        info,
        key=lambda key: (
            0 if key in CPO_INFO_FIELD_MAP else 1,
            _natural_sort_key(_info_field_label(key)),
        ),
    )
    for key in keys:
        if key == "N/A" and info[key] == "N/A":
            continue
        if key == "application_advertisement":
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
            label = _info_field_label(key)
            value = info.get(key, "N/A")

        if value in (None, "N/A", "Unknown"):
            lines.append("{}{}: {}".format(indent, label, "N/A" if value is None else value))
            continue
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
        CPO_DOM_VALUE_UNIT_MAP,
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
        CPO_DOM_MODULE_MONITOR_MAP,
        CPO_DOM_VALUE_UNIT_MAP,
    )

    lines.append("{}ModuleThresholdValues:".format(indent))
    _append_dom_values(
        lines,
        values,
        CPO_DOM_MODULE_THRESHOLD_MAP,
        CPO_DOM_MODULE_THRESHOLD_UNIT_MAP,
        alignment=15,
    )

    displayed_keys = set().union(
        CMIS_DOM_CHANNEL_MONITOR_MAP,
        DOM_CHANNEL_THRESHOLD_MAP,
        CPO_DOM_MODULE_MONITOR_MAP,
        CPO_DOM_MODULE_THRESHOLD_MAP,
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

    lines.append("{}ThresholdValues:".format(indent))
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


@contextmanager
def _eeprom_read_snapshot():
    """Reuse successful Optoe bytes for one read-only command invocation.

    Absolute offsets already encode bank/page selection. Cache only the
    unmodified community Optoe reader: custom platform readers may translate
    offsets themselves and must retain their existing behavior.
    """
    images = {}
    readers = {}

    def attach(endpoint, api=None):
        if api is None:
            if (not isinstance(endpoint, OptoeEepromReadWriteMixin)
                    or getattr(endpoint.read_eeprom, "__func__", None)
                    is not OptoeEepromReadWriteMixin.read_eeprom):
                return
            try:
                api = endpoint.get_api()
            except Exception:
                # A working platform hook must not depend on optional caching.
                return
        eeprom = getattr(api, "xcvr_eeprom", None)
        if not isinstance(eeprom, XcvrEeprom) or id(eeprom) in readers:
            return
        reader = eeprom.reader
        if (not isinstance(endpoint, OptoeEepromReadWriteMixin)
                or getattr(reader, "__self__", None) is not endpoint
                or getattr(reader, "__func__", None) is not OptoeEepromReadWriteMixin.read_eeprom):
            return
        path = endpoint.get_eeprom_path()
        if not isinstance(path, str) or not path:
            return
        image = images.setdefault(path, {})

        def read(offset, size):
            addresses = range(offset, offset + size)
            if size > 0 and all(address in image for address in addresses):
                return bytearray(image[address] for address in addresses)
            data = reader(offset, size)
            if isinstance(data, (bytes, bytearray)) and size > 0 and len(data) == size:
                image.update(zip(addresses, data))
            return data

        readers[id(eeprom)] = (eeprom, reader)
        eeprom.reader = read

    try:
        yield attach
    finally:
        for eeprom, reader in readers.values():
            eeprom.reader = reader


def _read_dom_section(failures, endpoint, section, read):
    """Read one DOM section at the platform API boundary.

    A read that fails, returns None, or returns no info or DOM data is recorded
    as a failure instead of being displayed as valid data.
    NotImplementedError and AttributeError still propagate as unsupported.
    """
    try:
        value = read()
    except (TypeError, ValueError, OSError) as exc:
        failures.append("{} {} ({})".format(endpoint, section, exc or type(exc).__name__))
        return None
    if value is None or (section != "thresholds" and value == {}):
        failures.append("{} {}".format(endpoint, section))
        return None
    return value


def _format_interface_dom(port_name, record):
    if not record["present"]:
        return "{}: CPO EEPROM not detected".format(port_name)
    lines = ["{}: CPO EEPROM detected".format(port_name)]
    if record.get("read_errors"):
        lines.append("    Read errors: {}".format(", ".join(record["read_errors"])))
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
    """Validate and return the OE-local CMIS bank declared by the HLD topology."""
    cpo = cpo_object_map[OPTICAL_ENGINE].get(mapping.oe_name)
    if cpo is None:
        raise CpoCommandError("No CPO object is available for '{}'".format(mapping.oe_name))
    bank_count = _get_oe_bank_count(mapping.oe_name, cpo)
    if mapping.oe_bank < 0 or mapping.oe_bank >= bank_count:
        raise CpoCommandError("Invalid bank {} for '{}'".format(mapping.oe_bank, mapping.oe_name))
    return mapping.oe_bank


def _interface_mapping_record(logical_port):
    context = cpo_mapping.interface_context(logical_port, current_port_config, require_lasers=False)
    mapping = context["mapping"]
    oe_lanes = [mapping.lanes[index] for index in context["lane_positions"]]
    laser_ids = context["laser_ids"]
    els = {
        "id": mapping.els_name.upper(),
        # None: the topology does not identify this subport's lasers.
        "lasers": list(laser_ids) if laser_ids is not None else None,
    }
    if mapping.els_bank not in (None, "N/A"):
        els["bank"] = mapping.els_bank
    return {
        "port": str(logical_port),
        "oe": {
            "id": mapping.oe_name.upper(),
            "bank": mapping.oe_bank,
            "lanes": oe_lanes,
        },
        "els": els,
    }


def _format_selected_application(advertisements, application):
    """Keep the AppSel and full public Host/Media interface descriptions."""
    if application is None or application == "N/A":
        return "N/A"
    details = advertisements.get(application)
    if details is None:
        details = advertisements.get(str(application))
    if not isinstance(details, dict):
        return "{}: N/A".format(application)
    host = details.get("host_electrical_interface_id", "N/A")
    media = details.get("module_media_interface_id", "N/A")
    return "{}: {} / {}".format(application, host, media)


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
            ",".join(str(laser) for laser in els["lasers"])
            if els["lasers"] is not None else UNRESOLVED_LASERS,
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


def print_application_records(records, json_output):
    if json_output:
        click.echo(_json_records(records))
        return

    rows = []
    for interface, values in records.items():
        advertisements = values.get("Application Advertisement", {})
        configured = values.get("Application Select Controls", {})
        active = values.get("Active Application Control Set", {})
        lanes = sorted(
            set(configured).union(active), key=_natural_sort_key
        )
        for lane in lanes:
            rows.append((
                interface,
                _display_field(lane),
                _format_selected_application(advertisements, configured.get(lane)),
                _format_selected_application(advertisements, active.get(lane)),
            ))
    click.echo(tabulate(
        rows,
        (
            "Interface",
            "Lane",
            "Configured Application",
            "Active Application",
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
    laser_ids = context["laser_ids"] or ()
    lane_lasers = {}
    for position in context["lane_positions"]:
        asic_lane = mapping.lanes[position]
        lasers = [
            laser for laser in laser_ids
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
        if lasers is None:
            status_rows.append((interface, els_id, "Lasers", UNRESOLVED_LASERS))
        elif lasers and any(lane_lasers.get(lane) is None for lane in lanes):
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
                    ELS_STATUS_FIELD_MAP.get(field, field),
                    _display_value(status[field]),
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
    """Debug and manually provision Co-Packaged Optics devices.

    Root privileges are required; run with sudo as a regular user.
    """
    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERROR_PERMISSIONS)


@cli.group()
def show():
    """Display CPO status."""


@show.group("interface")
def show_interface():
    """Display information for front-panel CPO interfaces and their associated OE and ELS."""


@show_interface.command("presence")
@click.option("-p", "--port", metavar="PORT",
              help="Front-panel interface; omit to display all CPO interfaces.")
@output_option
def show_interface_presence(port, json_output):
    """Display CPO virtual-module presence for each interface."""
    records = {}
    try:
        for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
            present = get_cpo_presence(cpo, port_name)
            mapping = cpo_mapping.resolve_interface(logical_port, current_port_config)
            records[port_name] = {"els": mapping.els_name.upper(), "present": present}
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))
    if json_output:
        click.echo(_json_records(records))
    else:
        rows = [
            (port_name, record["els"], "Present" if record["present"] else "Not present")
            for port_name, record in records.items()
        ]
        click.echo(tabulate(rows, headers=("Interface", "ELS", "Presence")))


@show_interface.command("map")
@click.option("-p", "--port", metavar="PORT",
              help="Front-panel interface; omit to display all CPO interfaces.")
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
    except (CpoMappingError, CpoCommandError) as exc:
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


@show_interface.command("dom")
@click.option("-p", "--port", metavar="PORT",
              help="Front-panel interface; omit to display all CPO interfaces.")
@output_option
def show_interface_dom(port, json_output):
    """Display CPO EEPROM information and monitoring data.

    OE and ELS data use separate sections; cable length fields are combined.
    JSON includes presence and each endpoint's info, dom and thresholds.
    """
    records = {}
    output = []
    failed_ports = []
    try:
        with _eeprom_read_snapshot() as attach_snapshot:
            for port_name, _, cpo in get_port_cpo_objects(port):
                present = get_cpo_presence(cpo, port_name)
                record = {"present": present, "oe": {}, "els": {}}
                records[port_name] = record
                if not present:
                    output.append(_format_interface_dom(port_name, record))
                    continue
                oe_api = get_oe_api(cpo, port_name)
                els_api = get_els_api(cpo, port_name)
                attach_snapshot(cpo.oe, oe_api)
                attach_snapshot(cpo.elsfp, els_api)

                failures = []
                record["oe"] = {
                    "info": _combine_cable_info(
                        _read_dom_section(failures, "OE", "info", oe_api.get_transceiver_info)),
                    "dom": _read_dom_section(failures, "OE", "dom", oe_api.get_transceiver_dom_real_value),
                    "thresholds": _read_dom_section(
                        failures, "OE", "thresholds", oe_api.get_transceiver_threshold_info),
                }
                els_info = _read_dom_section(failures, "ELS", "info", els_api.get_elsfp_info)
                record["els"] = {
                    "info": _combine_cable_info(els_info),
                    "dom": _filter_els_dom_lanes(
                        _read_dom_section(failures, "ELS", "dom", els_api.get_elsfp_dom_real_value),
                        _get_els_lane_count(els_info),
                    ),
                    "thresholds": _read_dom_section(
                        failures, "ELS", "thresholds", els_api.get_elsfp_threshold_info),
                }
                if failures:
                    record["read_errors"] = failures
                    failed_ports.append("{} ({})".format(port_name, ", ".join(failures)))
                output.append(_format_interface_dom(port_name, record))
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))
    if json_output:
        click.echo(_json_records(records))
    else:
        click.echo("\n\n".join(output))
    if failed_ports:
        # Other ports are still displayed; the command reports the failed reads.
        raise click.ClickException(
            "Failed to read CPO data for {}".format("; ".join(failed_ports))
        )


@show_interface.command("tx-disable")
@click.option("-p", "--port", metavar="PORT",
              help="Front-panel interface; omit to display all CPO interfaces.")
@output_option
def show_interface_tx_disable(port, json_output):
    """Display per-lane Tx disable status (true means disabled)."""
    records = {}
    try:
        with _eeprom_read_snapshot() as attach_snapshot:
            for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
                lane_positions = cpo_mapping.lane_positions(logical_port, current_port_config)
                attach_snapshot(getattr(cpo, "oe", None))
                values = _select_lane_values(
                    _call_vmodule(cpo, "get_tx_disable"), lane_positions
                )
                records[port_name] = values
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))
    print_records(
        records,
        json_output,
        ("Interface", "Tx Disable Status"),
        boolean_values=("true", "false"),
        field_header="Lane",
    )


@show_interface.group("speed")
def show_interface_speed():
    """Display CPO interface application settings."""


@show_interface_speed.command("application")
@click.option("-p", "--port", metavar="PORT",
              help="Front-panel interface; omit to display all CPO interfaces.")
@output_option
def show_interface_speed_application(port, json_output):
    """Display configured and active Application selections per lane.

    Each table entry is AppSel: Host interface / Media interface. JSON retains
    the complete public Application Advertisement and the per-lane AppSel IDs.
    """
    from sonic_platform_base.sonic_xcvr.fields import consts

    records = {}
    try:
        with _eeprom_read_snapshot() as attach_snapshot:
            for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
                api = get_oe_api(cpo, port_name)
                attach_snapshot(cpo.oe, api)
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
                    configured.append(api.get_application(lane))
                    active_application = active_applications.get(
                        "{}{}".format(
                            consts.ACTIVE_APSEL_HOSTLANE, lane + 1
                        ),
                        "N/A",
                    )
                    active.append(active_application)
                lane_positions = cpo_mapping.lane_positions(logical_port, current_port_config)
                records[port_name] = {
                    "Application Advertisement": advertisements,
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
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))
    print_application_records(records, json_output)


@show_interface.command("lane-status")
@click.option("-p", "--port", metavar="PORT",
              help="Front-panel interface; omit to display all CPO interfaces.")
@output_option
def show_interface_lane_status(port, json_output):
    """Display OE datapath and ELS status."""
    records = {}
    try:
        with _eeprom_read_snapshot() as attach_snapshot:
            for port_name, _, cpo, logical_port in get_port_cpo_entries(port):
                oe_api = get_oe_api(cpo, port_name)
                els_api = get_els_api(cpo, port_name)
                attach_snapshot(cpo.oe, oe_api)
                attach_snapshot(cpo.elsfp, els_api)
                context = cpo_mapping.interface_context(logical_port, current_port_config, require_lasers=False)
                laser_ids = context["laser_ids"]
                els_status = els_api.get_elsfp_status()
                if not isinstance(els_status, dict) or not els_status:
                    raise CpoCommandError(
                        "ELSFP status API returned no usable data for '{}'".format(port_name)
                    )
                records[port_name] = {
                    "Data Path State Indicator": _select_lane_values(
                        oe_api.get_datapath_state(), context["lane_positions"]
                    ),
                    "ELS": context["mapping"].els_name.upper(),
                    "ELS Status": els_status,
                    "ELS Lane State": _select_els_laser_values(
                        els_api.get_per_lane_state(), laser_ids, els_api.xcvr_eeprom.mem_map.bank
                    ) if laser_ids is not None else {},
                    "ELS Lasers": list(laser_ids) if laser_ids is not None else None,
                    "Lane Lasers": _lane_lasers(context),
                    "Shared ELS Lasers": list(context["shared_laser_ids"]),
                }
    except (NotImplementedError, AttributeError) as exc:
        raise click.ClickException(
            "This functionality is not implemented: {}".format(exc)
        )
    except (CpoMappingError, CpoCommandError) as exc:
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
            lpmode = cpo.oe.get_lpmode()
            if not isinstance(lpmode, bool):
                raise CpoCommandError(
                    "OE get_lpmode returned invalid data for '{}'".format(resource_id)
                )
            records[resource_id] = lpmode
    except (AttributeError, NotImplementedError) as exc:
        raise click.ClickException(
            "OE get_lpmode is not implemented for this platform"
        ) from exc
    except (CpoMappingError, CpoCommandError, OSError) as exc:
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
    except (CpoMappingError, CpoCommandError, NotImplementedError, AttributeError) as exc:
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
    except (CpoMappingError, CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("OE", "Temperature (C)"))


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
            lpmode = cpo.elsfp.get_lpmode()
            if not isinstance(lpmode, bool):
                raise CpoCommandError(
                    "ELS get_lpmode returned invalid data for '{}'".format(resource_id)
                )
            records[resource_id] = lpmode
    except (AttributeError, NotImplementedError) as exc:
        raise click.ClickException(
            "ELS get_lpmode is not implemented for this platform"
        ) from exc
    except (CpoMappingError, CpoCommandError, OSError) as exc:
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
    except (CpoMappingError, CpoCommandError, NotImplementedError, AttributeError) as exc:
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
            temperature = api.get_module_temperature()
            if temperature is None:
                raise CpoCommandError(
                    "ELSFP temperature is unavailable for '{}'".format(
                        resource_id
                    )
                )
            records[resource_id] = temperature
    except (CpoMappingError, CpoCommandError, NotImplementedError, AttributeError) as exc:
        raise click.ClickException(str(exc))
    print_records(records, json_output, ("ELS", "Temperature (C)"))


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


def _call_hook(target, method, label, *args):
    """Call a platform hook, reporting a missing or unimplemented hook."""
    function = getattr(target, method, None)
    unsupported = "{} {} is not implemented for this platform".format(label, method)
    if not callable(function):
        raise CpoCommandError(unsupported)
    try:
        return function(*args)
    except NotImplementedError as exc:
        raise CpoCommandError(unsupported) from exc
    except OSError as exc:
        # Hardware access errors are reported like any other failed control,
        # so a multi-target command can still name what it already applied.
        raise CpoCommandError("{} {} failed: {}".format(label, method, exc)) from exc


def _call_vmodule(cpo, method, *args):
    """Call a CPO virtual-module hook on a CpoBase object."""
    return _call_hook(cpo, method, "CPO", *args)


def get_vmodule_targets(ports):
    """Resolve selected interfaces to unique CPO objects for Tx-disable.

    Return each target with the interfaces sharing its physical port.
    """
    selected = [port.strip() for port in str(ports).split(",") if port.strip()]
    if not selected:
        raise CpoCommandError("At least one port is required")

    targets = {}
    for port in selected:
        port_cpos = get_port_cpo_objects(port)
        for _, physical_port, cpo in port_cpos:
            if physical_port not in targets:
                affected = cpo_mapping.ports_for_physical_ports([physical_port], current_port_config)
                targets[physical_port] = (affected[0] if affected else port, cpo, affected)
    return sorted(targets.values(), key=lambda target: _natural_sort_key(target[0]))


def _run_vmodule_action(targets, verb, method, *args):
    """Apply one virtual-module hook to each target, naming the affected ports."""
    completed = []
    for label, cpo, affected_ports in targets:
        message = "{} {} ({})".format(verb, label, ", ".join(affected_ports))
        try:
            _run_action(message, lambda cpo=cpo: _call_vmodule(cpo, method, *args))
        except CpoCommandError as exc:
            if completed:
                raise CpoCommandError(
                    "{}; already applied to {}".format(exc, ", ".join(completed))
                ) from exc
            raise
        completed.append(label)


@cli.group()
def config():
    """Control CPO hardware."""


@config.group("interface")
def config_interface():
    """Control Tx-disable on the OE bank associated with a front-panel interface."""


@config_interface.command("tx-disable")
@click.option("-p", "--port", required=True, metavar="PORT",
              help="Front-panel interface or comma-separated list of interfaces.")
@click.argument("state", type=click.Choice(["true", "false"]))
def config_interface_tx_disable(port, state):
    """Enable or disable Tx-disable on every lane of one OE bank.

    -p/--port selects the mapped OE bank. All lanes of that bank are affected,
    including other breakout subports sharing it; affected ports are listed.
    The value true disables TX, and false enables TX.
    """
    disable = state == "true"
    try:
        targets = get_vmodule_targets(port)
        _run_vmodule_action(
            targets,
            "Enabling Tx-disable for" if disable else "Disabling Tx-disable for",
            "tx_disable", disable,
        )
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))


@config.group("oe")
def config_oe():
    """Control an Optical Engine endpoint through its platform hooks."""


@config_oe.command("lpmode")
@click.argument("oe_index")
@click.argument("mode", type=click.Choice(["full", "low"]))
def config_oe_lpmode(oe_index, mode):
    """Set OE endpoint full-power or low-power mode."""
    try:
        resource_id, cpo = _single_resource(OPTICAL_ENGINE, oe_index)
        low_power = mode == "low"
        _run_action(
            "{} low-power mode for {} ({})".format(
                "Enabling" if low_power else "Disabling",
                resource_id.upper(),
                ", ".join(cpo_mapping.ports_for_resource(OPTICAL_ENGINE, resource_id, current_port_config)),
            ),
            lambda: _call_hook(getattr(cpo, "oe", None), "set_lpmode", "OE", low_power),
        )
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))


@config_oe.command("reset")
@click.argument("oe_index")
def config_oe_reset(oe_index):
    """Reset an Optical Engine endpoint.

    Module settings may return to defaults. Affected ports may require
    application and datapath reprovisioning after the reset.
    """
    try:
        resource_id, cpo = _single_resource(OPTICAL_ENGINE, oe_index)
        _run_action(
            "Resetting {} ({})".format(
                resource_id.upper(),
                ", ".join(cpo_mapping.ports_for_resource(OPTICAL_ENGINE, resource_id, current_port_config))
            ),
            lambda: _call_hook(getattr(cpo, "oe", None), "reset", "OE"),
        )
        click.echo(
            "Affected ports may require application and datapath "
            "reprovisioning after the reset."
        )
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))


@config.group("els")
def config_els():
    """Control an External Laser Source endpoint through its platform hooks."""


@config_els.command("lpmode")
@click.argument("els_index")
@click.argument("mode", type=click.Choice(["full", "low"]))
def config_els_lpmode(els_index, mode):
    """Set ELS endpoint full-power or low-power mode."""
    try:
        resource_id, cpo = _single_resource(EXTERNAL_LASER_SOURCE, els_index)
        low_power = mode == "low"
        _run_action(
            "{} low-power mode for {}".format(
                "Enabling" if low_power else "Disabling", resource_id.upper(),
            ),
            lambda: _call_hook(getattr(cpo, "elsfp", None), "set_lpmode", "ELS", low_power),
        )
    except (CpoMappingError, CpoCommandError) as exc:
        raise click.ClickException(str(exc))


@config_els.command("reset")
@click.argument("els_index")
def config_els_reset(els_index):
    """Reset an External Laser Source endpoint."""
    try:
        resource_id, cpo = _single_resource(EXTERNAL_LASER_SOURCE, els_index)
        _run_action(
            "Resetting {}".format(resource_id.upper()),
            lambda: _call_hook(getattr(cpo, "elsfp", None), "reset", "ELS"),
        )
    except (CpoMappingError, CpoCommandError) as exc:
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


def _validate_eeprom_page(resource_type, resource_id, cpo, page, offset, size):
    """Restrict raw access to pages and memory halves declared by the endpoint."""
    from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages import CmisAdministrativeLowerPage

    label = str(resource_id).upper()
    api = get_oe_api(cpo, label) if resource_type == OPTICAL_ENGINE else get_els_api(cpo, label)
    mem_map = getattr(getattr(api, "xcvr_eeprom", None), "mem_map", None)
    pages = getattr(mem_map, "pages", None)
    if not isinstance(pages, (list, tuple)) or not pages:
        raise CpoCommandError("EEPROM memory map is unavailable for '{}'".format(label))
    selected = [item for item in pages if item.page == page]
    if not selected:
        valid_pages = ", ".join("0x{:02x}".format(number) for number in sorted({item.page for item in pages}))
        raise CpoCommandError(
            "Page 0x{:02x} is not declared for '{}'; valid pages: {}".format(page, label, valid_pages)
        )
    has_lower = any(isinstance(item, CmisAdministrativeLowerPage) for item in selected)
    has_upper = any(not isinstance(item, CmisAdministrativeLowerPage) for item in selected)
    if (offset < EEPROM_PAGE_OFFSET and not has_lower
            or offset + size > EEPROM_PAGE_OFFSET and not has_upper):
        raise CpoCommandError(
            "Page 0x{:02x} does not cover offsets 0x{:02x}-0x{:02x} for '{}'".format(
                page, offset, offset + size - 1, label)
        )


def _validate_requested_eeprom_bank(bank, page):
    """Reject explicit nonzero banks on pages the CMIS reader treats as shared."""
    if bank != 0 and (page < 0x10 or 0x9F <= page <= 0xAF):
        raise CpoCommandError(
            "Page {:x}h does not use bank selection; --bank must be 0".format(page)
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
    if bank_count < 0:
        raise CpoCommandError(
            "Invalid OE bank count {} for '{}'".format(
                bank_count, resource_id
            )
        )
    elif bank_count == 0:
        # TODO: get_max_supported_banks() should return 1 for flat memory instead of 0.
        bank_count = 1
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
    _validate_eeprom_page(resource_type, resource_id, cpo, page, offset, len(data))
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


def _interface_eeprom_target(port, target, page=None):
    mapping = cpo_mapping.resolve_interface(port, current_port_config)
    if target == OPTICAL_ENGINE:
        bank = _local_oe_bank(mapping)
        if page is not None and (page < 0x10 or 0x9F <= page <= 0xAF):
            bank = 0
        return mapping.oe_id, bank
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
    _validate_eeprom_page(resource_type, resource_id, cpo, page, offset, size)
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
    common_bank = 0
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
    failed_resources = []
    for resource_id, cpo in resources:
        try:
            banks = _resource_banks(resource_type, resource_id, bank)
            for selected_bank in banks:
                _physical_eeprom_bank(resource_type, resource_id, cpo, selected_bank)
            outputs.append(_format_full_eeprom(
                resource_type, resource_id, cpo, banks
            ))
        except CpoCommandError as exc:
            if index is not None:
                raise
            failed_resources.append(str(resource_id).upper())
            outputs.append(
                "EEPROM hexdump for {}\n{}{}".format(
                    str(resource_id).upper(),
                    EEPROM_DUMP_INDENT, exc,
                )
            )
    click.echo("\n".join(outputs).rstrip())
    if failed_resources:
        raise CpoCommandError(
            "Failed to dump EEPROM for: {}".format(", ".join(failed_resources))
        )


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
@click.option("-p", "--port", required=True, metavar="PORT",
              help="Front-panel interface.")
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
        index, bank = _interface_eeprom_target(port, target, page=page)
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
    except (CpoMappingError, CpoCommandError) as exc:
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
        _validate_eeprom_range(target_bank, page, offset, size)
        _validate_requested_eeprom_bank(target_bank, page)
        results = _read_resource_eeprom(
            OPTICAL_ENGINE, index, target_bank, page, offset, size
        )
    except (CpoMappingError, CpoCommandError) as exc:
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
    except (CpoMappingError, CpoCommandError) as exc:
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
@click.option("-p", "--port", required=True, metavar="PORT",
              help="Front-panel interface.")
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
        index, bank = _interface_eeprom_target(port, target, page=page)
        payload = _parse_hex_data(data)
        _write_resource_eeprom(
            target, index, bank, page, offset, payload
        )
    except (CpoMappingError, CpoCommandError) as exc:
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
        _validate_eeprom_range(bank, page, offset, len(payload))
        _validate_requested_eeprom_bank(bank, page)
        _write_resource_eeprom(
            OPTICAL_ENGINE, index, bank, page, offset, payload
        )
    except (CpoMappingError, CpoCommandError) as exc:
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
    except (CpoMappingError, CpoCommandError) as exc:
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
