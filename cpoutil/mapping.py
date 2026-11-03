"""Interpret the community CPO topology and platform extension data."""

from dataclasses import dataclass, field
import re

from utilities_common.platform_sfputil_helper import natural_sort_key

OPTICAL_ENGINE = "oe"
EXTERNAL_LASER_SOURCE = "els"
PORT = "port"
SUPPORTED_RESOURCE_TYPES = {OPTICAL_ENGINE, EXTERNAL_LASER_SOURCE}


class CpoMappingError(ValueError):
    """Raised when cpo.json does not describe a usable CPO topology."""


class CpoLaserResolutionError(CpoMappingError):
    """Raised when the topology cannot identify a logical subport's lasers."""


def _parse_integer_list(value, field_name):
    if value is None:
        return ()
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple)):
        raise CpoMappingError("{} must be a list or string".format(field_name))
    try:
        return tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise CpoMappingError("{} must contain integers".format(field_name)) from exc


def _resource_name(resource_type, resource_id):
    return "{}{}".format(resource_type, int(resource_id))


def _parse_laser_lane_mapping(value, resource_name):
    """Normalize one-based JSON laser IDs to zero-based CLI/API IDs."""
    if not isinstance(value, dict):
        raise CpoMappingError("{} laser_to_asic_lane_mapping must be an object".format(resource_name))
    parsed = {}
    for laser, lanes in value.items():
        try:
            laser_id = int(laser) - 1
        except (TypeError, ValueError) as exc:
            raise CpoMappingError("laser IDs must be positive integers") from exc
        if laser_id < 0 or laser_id in parsed:
            raise CpoMappingError("laser IDs must be unique positive integers")
        parsed_lanes = _parse_integer_list(lanes, "{} laser {} lanes".format(resource_name, laser))
        if not parsed_lanes:
            raise CpoMappingError("{} laser {} must map to ASIC lanes".format(resource_name, laser))
        parsed[laser_id] = parsed_lanes
    return parsed


@dataclass(frozen=True)
class InterfaceMapping:
    port: str
    physical_ports: tuple
    lanes: tuple
    oe_id: int
    oe_bank: int
    els_id: int
    els_bank: object
    laser_ids: tuple
    laser_to_asic_lane_mapping: dict = field(default_factory=dict)

    @property
    def oe_name(self):
        return _resource_name(OPTICAL_ENGINE, self.oe_id)

    @property
    def els_name(self):
        return _resource_name(EXTERNAL_LASER_SOURCE, self.els_id)

    def to_dict(self):
        return {
            "port": self.port, "physical_ports": list(self.physical_ports), "lanes": list(self.lanes),
            "oe": {"id": self.oe_name, "bank": self.oe_bank},
            "els": {"id": self.els_name, "bank": self.els_bank}, "laser_ids": list(self.laser_ids),
        }


class CpoMapping:
    """Validated devices/associated_devices topology; legacy references are ignored."""

    def __init__(self, cpo_data, port_config=None):
        if not isinstance(cpo_data, dict):
            raise CpoMappingError("cpo.json root must be an object")
        devices = cpo_data.get("devices")
        interfaces = cpo_data.get("interfaces")
        if not isinstance(devices, dict) or not devices:
            raise CpoMappingError("cpo.json must contain a non-empty devices object")
        if not isinstance(interfaces, dict) or not interfaces:
            raise CpoMappingError("cpo.json must contain a non-empty interfaces object")
        self._port_config = port_config or {}
        self._devices = {}
        self._oes = {}
        self._elss = {}
        for name, device in devices.items():
            if not isinstance(device, dict):
                raise CpoMappingError("device {} must be an object".format(name))
            key = str(name).lower()
            if key in self._devices:
                raise CpoMappingError("duplicate device id '{}'".format(name))
            self._devices[key] = device
            resource_type = {"optical_engine": OPTICAL_ENGINE,
                             "external_laser_source": EXTERNAL_LASER_SOURCE}.get(device.get("device_type"))
            if resource_type is not None:
                self._resource_index(key, resource_type)
                (self._oes if resource_type == OPTICAL_ENGINE else self._elss)[key] = device
        if not self._oes or not self._elss:
            raise CpoMappingError("devices must contain at least one OE and one ELS")
        platform_data = cpo_data.get("platform_data", {})
        if not isinstance(platform_data, dict) or not isinstance(platform_data.get("interfaces", {}), dict):
            raise CpoMappingError("platform_data and its interfaces must be objects")
        self._platform_interfaces = platform_data.get("interfaces", {})
        self._parsed_interfaces = {
            port: self._parse_interface(port, interface) for port, interface in interfaces.items()
        }

    @staticmethod
    def _resource_index(resource_name, resource_type):
        match = re.fullmatch(r"{}(0|[1-9][0-9]*)".format(resource_type), str(resource_name), re.IGNORECASE)
        if not match:
            raise CpoMappingError(
                "invalid {} device id '{}'; expected {}0, {}1, ... without leading zeros".format(
                    resource_type, resource_name, resource_type, resource_type))
        return int(match.group(1))

    @staticmethod
    def _bank(association, device, resource_name, optional=False):
        value = association.get("bank", "N/A" if optional else 0)
        if optional and value == "N/A":
            return value
        try:
            bank = int(value)
            maximum = int(device["max_banks"]) if "max_banks" in device else None
            if bank < 0 or (maximum is not None and (maximum <= 0 or bank >= maximum)):
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise CpoMappingError("invalid {} bank for {}".format("ELS" if optional else "OE", resource_name)) from exc
        return bank

    def _associations(self, port, interface):
        associated = interface.get("associated_devices")
        if not isinstance(associated, list):
            raise CpoMappingError("interface {} has no associated_devices".format(port))
        found = {}
        for association in associated:
            if not isinstance(association, dict):
                continue
            name = str(association.get("device_id", "")).lower()
            device = self._devices.get(name)
            if device is None:
                raise CpoMappingError("interface {} references unknown device '{}'".format(port, name))
            device_type = device.get("device_type")
            if device_type not in ("optical_engine", "external_laser_source"):
                continue
            if device_type in found:
                raise CpoMappingError("interface {} references more than one {}".format(
                    port, "OE" if device_type == "optical_engine" else "ELS"))
            found[device_type] = (name, device, association)
        if len(found) != 2:
            raise CpoMappingError("interface {} must reference one OE and one ELS".format(port))
        return found["optical_engine"], found["external_laser_source"]

    def _parse_interface(self, port, interface):
        if not isinstance(interface, dict):
            raise CpoMappingError("interface {} must be an object".format(port))
        (oe_name, oe, oe_assoc), (els_name, els, els_assoc) = self._associations(port, interface)
        oe_bank = self._bank(oe_assoc, oe, oe_name)
        els_bank = self._bank(els_assoc, els, els_name, optional=True)
        oe_lanes = _parse_integer_list(oe.get("asic_lanes"), "{} asic_lanes".format(oe_name))
        try:
            max_banks = int(oe.get("max_banks", 1))
            if max_banks <= 0:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise CpoMappingError("{} max_banks must be positive".format(oe_name)) from exc
        port_entry = self._port_config.get(port, {})
        if oe_lanes and len(oe_lanes) % max_banks == 0:
            count = len(oe_lanes) // max_banks
            parsed_lanes = oe_lanes[oe_bank * count:(oe_bank + 1) * count]
        else:
            parsed_lanes = _parse_integer_list(
                port_entry.get("lanes", interface.get("lanes")), "interface {} lanes".format(port))
        if not parsed_lanes:
            raise CpoMappingError("interface {} has no ASIC lanes".format(port))
        physical_ports = port_entry.get("index", interface.get("index"))
        if physical_ports is None:
            physical_ports = [index for entry in self._port_config.values()
                              if set(parsed_lanes).intersection(_parse_integer_list(entry.get("lanes"), "PORT lanes"))
                              for index in _parse_integer_list(entry.get("index"), "PORT index")]
        physical_ports = tuple(dict.fromkeys(_parse_integer_list(physical_ports, "interface {} index".format(port))))
        if not physical_ports or any(index < 0 for index in physical_ports):
            raise CpoMappingError("interface {} must contain a physical port index".format(port))
        laser_map = _parse_laser_lane_mapping(els.get("laser_to_asic_lane_mapping", {}), els_name)
        if laser_map:
            laser_ids = tuple(laser for laser, lanes in sorted(laser_map.items())
                              if set(parsed_lanes).intersection(lanes))
            covered = {lane for laser in laser_ids for lane in laser_map[laser]}
            if not set(parsed_lanes).issubset(covered):
                raise CpoMappingError("interface {} has ASIC lanes without an ELS laser mapping".format(port))
        else:
            extension = self._platform_interfaces.get(port, {})
            if not isinstance(extension, dict):
                raise CpoMappingError("platform_data interface {} must be an object".format(port))
            laser_ids = _parse_integer_list(extension.get("laser_ids"), "interface {} laser_ids".format(port))
            if any(laser < 0 for laser in laser_ids) or len(laser_ids) != len(set(laser_ids)):
                raise CpoMappingError("platform laser_ids must be unique non-negative integers")
        return InterfaceMapping(port, physical_ports, parsed_lanes,
                                self._resource_index(oe_name, OPTICAL_ENGINE), oe_bank,
                                self._resource_index(els_name, EXTERNAL_LASER_SOURCE), els_bank,
                                laser_ids, laser_map)

    def ports(self):
        return sorted(self._parsed_interfaces, key=natural_sort_key)

    def resource_ids(self, resource_type):
        resources = {OPTICAL_ENGINE: self._oes, EXTERNAL_LASER_SOURCE: self._elss}.get(resource_type)
        if resources is None:
            raise CpoMappingError("unsupported CPO resource type '{}'".format(resource_type))
        return sorted(resources, key=natural_sort_key)

    def resolve_resource_ids(self, selector, resource_type):
        resource_ids = self.resource_ids(resource_type)
        if selector is None:
            return resource_ids
        selector_text = str(selector).strip().lower()
        if selector_text.isdigit():
            selector_text = _resource_name(resource_type, selector_text)
        if selector_text in resource_ids:
            return [selector_text]
        raise KeyError(selector)

    def get_interface(self, port):
        return self._parsed_interfaces[port]

    def get_interfaces(self, port=None):
        if port is not None:
            return [self.get_interface(port)]
        return [self.get_interface(name) for name in self.ports()]

    def resolve_interface(self, logical_port, port_config):
        """Resolve an active port against static interfaces using a PORT snapshot."""
        port_name = str(logical_port)
        if port_name in self._parsed_interfaces:
            return self.get_interface(port_name)
        if port_name.startswith("Ethernet"):
            entry = port_config.get(port_name)
            if entry is None:
                raise CpoMappingError("Invalid port '{}'".format(port_name))
            physical_ports = set(entry["index"])
        else:
            try:
                physical_ports = {int(port_name)}
            except ValueError as exc:
                raise CpoMappingError("Invalid port '{}'".format(port_name)) from exc
        matches = [mapping for mapping in self.get_interfaces()
                   if physical_ports.intersection(mapping.physical_ports)]
        if len(matches) != 1:
            raise CpoMappingError("Unable to resolve '{}' to one CPO interface".format(port_name))
        return matches[0]

    def lane_positions(self, logical_port, port_config, mapping=None):
        """Return zero-based OE lane positions using already-parsed active lanes."""
        mapping = mapping or self.resolve_interface(logical_port, port_config)
        port_name = str(logical_port)
        if not port_name.startswith("Ethernet"):
            return tuple(range(len(mapping.lanes)))
        entry = port_config.get(port_name)
        if entry is None:
            raise CpoMappingError("No active PORT configuration found for '{}'".format(port_name))
        port_lanes = set(entry["lanes"])
        unknown_lanes = port_lanes.difference(mapping.lanes)
        if unknown_lanes:
            raise CpoMappingError("PORT '{}' lanes {} are outside CPO interface '{}'".format(
                port_name, ",".join(str(lane) for lane in sorted(unknown_lanes)), mapping.port))
        positions = tuple(index for index, lane in enumerate(mapping.lanes) if lane in port_lanes)
        if not positions:
            raise CpoMappingError("PORT '{}' has no lanes in CPO interface '{}'".format(port_name, mapping.port))
        return positions

    def lane_mask(self, logical_port, port_config, mapping=None):
        return sum(1 << lane for lane in self.lane_positions(logical_port, port_config, mapping))

    def _laser_selection(self, logical_port, mapping, lane_positions):
        if not mapping.laser_ids:
            return (), ()
        selected_lanes = {mapping.lanes[index] for index in lane_positions}
        if not mapping.laser_to_asic_lane_mapping:
            if selected_lanes == set(mapping.lanes):
                shared = {laser for other in self.get_interfaces()
                          if other.port != mapping.port and other.els_id == mapping.els_id
                          for laser in other.laser_ids}
                return mapping.laser_ids, tuple(laser for laser in mapping.laser_ids if laser in shared)
            raise CpoLaserResolutionError(
                "CPO interface '{}' needs laser_to_asic_lane_mapping to resolve breakout port '{}'".format(
                    mapping.port, logical_port))
        selected, shared = [], []
        for laser_id in mapping.laser_ids:
            laser_lanes = set(mapping.laser_to_asic_lane_mapping[laser_id])
            overlap = selected_lanes.intersection(laser_lanes)
            if overlap:
                selected.append(laser_id)
                if overlap != laser_lanes:
                    shared.append(laser_id)
        return tuple(selected), tuple(shared)

    def laser_selection(self, logical_port, port_config, mapping=None):
        mapping = mapping or self.resolve_interface(logical_port, port_config)
        return self._laser_selection(logical_port, mapping, self.lane_positions(logical_port, port_config, mapping))

    def interface_context(self, logical_port, port_config, require_lasers=True):
        """Return lane and laser associations without accessing platform objects."""
        mapping = self.resolve_interface(logical_port, port_config)
        positions = self.lane_positions(logical_port, port_config, mapping)
        try:
            laser_ids, shared_laser_ids = self._laser_selection(logical_port, mapping, positions)
        except CpoLaserResolutionError:
            if require_lasers:
                raise
            laser_ids, shared_laser_ids = None, ()
        return {"mapping": mapping, "lane_positions": positions,
                "lane_mask": sum(1 << lane for lane in positions),
                "laser_ids": laser_ids, "shared_laser_ids": shared_laser_ids}

    def ports_for_physical_ports(self, physical_ports, port_config):
        physical_ports = set(physical_ports)
        return sorted((port for port, entry in port_config.items()
                       if physical_ports.intersection(entry["index"])), key=natural_sort_key)

    def ports_for_resource(self, resource_type, resource_id, port_config):
        if resource_type not in SUPPORTED_RESOURCE_TYPES:
            raise CpoMappingError("unsupported CPO resource type '{}'".format(resource_type))
        name = str(resource_id).lower()
        if name.isdigit():
            name = _resource_name(resource_type, name)
        return self.ports_for_physical_ports(
            (pport for mapping in self.get_interfaces()
             if (mapping.oe_name if resource_type == OPTICAL_ENGINE else mapping.els_name) == name
             for pport in mapping.physical_ports), port_config)
