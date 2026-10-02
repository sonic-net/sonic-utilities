"""Helpers for interpreting the CPO topology used by the platform API."""

from dataclasses import dataclass, field
import re

from utilities_common.platform_sfputil_helper import natural_sort_key

OPTICAL_ENGINE = "oe"
EXTERNAL_LASER_SOURCE = "els"
PORT = "port"
SUPPORTED_RESOURCE_TYPES = {OPTICAL_ENGINE, EXTERNAL_LASER_SOURCE}


class CpoMappingError(ValueError):
    """Raised when cpo.json does not describe a usable CPO topology."""


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
        raise CpoMappingError(
            "{} must contain integers".format(field_name)
        ) from exc


def _resource_name(resource_type, resource_id):
    return "{}{}".format(resource_type, int(resource_id))


def _parse_laser_lane_mapping(value, resource_name):
    """Normalize one-based JSON laser IDs to zero-based CLI/API IDs."""
    if not isinstance(value, dict):
        raise CpoMappingError(
            "{} laser_to_asic_lane_mapping must be an object".format(
                resource_name
            )
        )
    parsed = {}
    for laser, lanes in value.items():
        try:
            laser_id = int(laser) - 1
        except (TypeError, ValueError) as exc:
            raise CpoMappingError("laser IDs must be positive integers") from exc
        if laser_id < 0 or laser_id in parsed:
            raise CpoMappingError("laser IDs must be unique positive integers")
        parsed_lanes = _parse_integer_list(
            lanes, "{} laser {} lanes".format(resource_name, laser)
        )
        if not parsed_lanes:
            raise CpoMappingError(
                "{} laser {} must map to ASIC lanes".format(resource_name, laser)
            )
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
            "port": self.port,
            "physical_ports": list(self.physical_ports),
            "lanes": list(self.lanes),
            "oe": {"id": self.oe_name, "bank": self.oe_bank},
            "els": {"id": self.els_name, "bank": self.els_bank},
            "laser_ids": list(self.laser_ids),
        }


class CpoMapping(object):
    """Validated view of the current platform ``cpo.json`` schema."""

    def __init__(self, cpo_data, port_config=None):
        if not isinstance(cpo_data, dict):
            raise CpoMappingError("cpo.json root must be an object")

        self._port_config = port_config or {}
        if isinstance(cpo_data.get("devices"), dict):
            cpo_data = self._normalize_community_schema(cpo_data)

        self._oes = cpo_data.get("oes")
        self._elss = cpo_data.get("elss")
        self._interfaces = cpo_data.get("interfaces")
        if not isinstance(self._oes, dict) or not self._oes:
            raise CpoMappingError(
                "cpo.json must contain a non-empty oes object"
            )
        if not isinstance(self._elss, dict) or not self._elss:
            raise CpoMappingError(
                "cpo.json must contain a non-empty elss object"
            )
        if not isinstance(self._interfaces, dict) or not self._interfaces:
            raise CpoMappingError(
                "cpo.json must contain a non-empty interfaces object"
            )

        self._parsed_interfaces = {}
        self._validate_resources(self._oes, OPTICAL_ENGINE)
        self._validate_resources(self._elss, EXTERNAL_LASER_SOURCE)
        self._validate_interfaces()

    @staticmethod
    def _resource_index(resource_name, resource_type):
        match = re.fullmatch(
            r"{}(\d+)".format(resource_type),
            str(resource_name),
            re.IGNORECASE,
        )
        if not match:
            raise CpoMappingError(
                "invalid {} device id '{}'".format(
                    resource_type, resource_name
                )
            )
        return int(match.group(1))

    def _normalize_community_schema(self, cpo_data):
        """Translate devices/associated_devices into the internal schema."""
        devices = cpo_data.get("devices", {})
        interfaces = cpo_data.get("interfaces", {})
        normalized_devices = {
            str(name).lower(): dict(device)
            for name, device in devices.items()
            if isinstance(device, dict)
        }

        oes = {}
        elss = {}
        for name, device in normalized_devices.items():
            device_type = device.get("device_type")
            if device_type == "optical_engine":
                resource_type = OPTICAL_ENGINE
                resources = oes
            elif device_type == "external_laser_source":
                resource_type = EXTERNAL_LASER_SOURCE
                resources = elss
            else:
                continue
            device["index"] = self._resource_index(name, resource_type)
            resources[name] = device

        normalized_interfaces = {}
        for port, interface in interfaces.items():
            if not isinstance(interface, dict):
                raise CpoMappingError(
                    "interface {} must be an object".format(port)
                )

            associated = interface.get("associated_devices")
            if not isinstance(associated, list):
                raise CpoMappingError(
                    "interface {} has no associated_devices".format(port)
                )

            oe_association = None
            els_association = None
            for association in associated:
                if not isinstance(association, dict):
                    continue
                device_name = str(
                    association.get("device_id", "")
                ).lower()
                device = normalized_devices.get(device_name)
                if device is None:
                    raise CpoMappingError(
                        "interface {} references unknown device '{}'".format(
                            port, association.get("device_id")
                        )
                    )
                if device.get("device_type") == "optical_engine":
                    oe_association = (device_name, association)
                elif device.get("device_type") == \
                        "external_laser_source":
                    els_association = (device_name, association)

            if oe_association is None or els_association is None:
                raise CpoMappingError(
                    "interface {} must reference one OE and one ELS".format(
                        port
                    )
                )

            oe_name, oe_data = oe_association
            els_name, els_data = els_association
            oe_device = normalized_devices[oe_name]
            oe_lanes = _parse_integer_list(
                oe_device.get("asic_lanes"),
                "{} asic_lanes".format(oe_name),
            )
            oe_bank = int(oe_data.get("bank", 0))
            max_oe_banks = int(oe_device.get("max_banks", 1))
            if oe_lanes and len(oe_lanes) % max_oe_banks == 0:
                lanes_per_bank = len(oe_lanes) // max_oe_banks
                first_lane = oe_bank * lanes_per_bank
                parsed_lanes = oe_lanes[
                    first_lane:first_lane + lanes_per_bank
                ]
            else:
                port_entry = self._port_config.get(port, {})
                parsed_lanes = _parse_integer_list(
                    port_entry.get("lanes", interface.get("lanes")),
                    "interface {} lanes".format(port),
                )

            port_entry = self._port_config.get(port, {})
            physical_ports = port_entry.get(
                "index", interface.get("index")
            )
            if physical_ports is None and parsed_lanes:
                matching_ports = []
                for active_port, active_entry in self._port_config.items():
                    active_lanes = _parse_integer_list(
                        active_entry.get("lanes"),
                        "interface {} lanes".format(active_port),
                    )
                    if set(parsed_lanes).intersection(active_lanes):
                        matching_ports.extend(_parse_integer_list(
                            active_entry.get("index"),
                            "interface {} index".format(active_port),
                        ))
                physical_ports = tuple(dict.fromkeys(matching_ports))

            laser_map = _parse_laser_lane_mapping(
                normalized_devices[els_name].get("laser_to_asic_lane_mapping", {}),
                els_name,
            )
            selected_lasers = [
                laser_id for laser_id, laser_lanes in sorted(laser_map.items())
                if set(parsed_lanes).intersection(laser_lanes)
            ]

            normalized_interfaces[port] = {
                "index": physical_ports,
                "lanes": parsed_lanes,
                "oe_id": self._resource_index(
                    oe_name, OPTICAL_ENGINE
                ),
                "oe_bank_id": oe_bank,
                "els_id": self._resource_index(
                    els_name, EXTERNAL_LASER_SOURCE
                ),
                "els_bank_id": els_data.get("bank", "N/A"),
                "laser_ids": selected_lasers,
            }

        return {
            "oes": oes,
            "elss": elss,
            "interfaces": normalized_interfaces,
        }

    @staticmethod
    def _validate_resources(resources, resource_type):
        for name, resource in resources.items():
            if not isinstance(resource, dict):
                raise CpoMappingError(
                    "{} {} must be an object".format(resource_type, name)
                )
            resource_id = resource.get("index")
            expected_name = _resource_name(resource_type, resource_id)
            if name.lower() != expected_name:
                raise CpoMappingError(
                    "{} entry '{}' has inconsistent index '{}'".format(
                        resource_type, name, resource_id
                    )
                )

    def _validate_interfaces(self):
        for port, interface in self._interfaces.items():
            if not isinstance(interface, dict):
                raise CpoMappingError(
                    "interface {} must be an object".format(port)
                )

            physical_ports = tuple(dict.fromkeys(_parse_integer_list(
                interface.get("index"), "interface {} index".format(port)
            )))
            if not physical_ports:
                raise CpoMappingError(
                    "interface {} must contain a physical port index".format(
                        port
                    )
                )

            try:
                oe_id = int(interface["oe_id"])
                oe_bank = int(interface["oe_bank_id"])
                els_id = int(interface["els_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CpoMappingError(
                    "interface {} has invalid OE/ELS mapping".format(port)
                ) from exc

            oe_name = _resource_name(OPTICAL_ENGINE, oe_id)
            els_name = _resource_name(EXTERNAL_LASER_SOURCE, els_id)
            if oe_name not in self._oes:
                raise CpoMappingError(
                    "interface {} references unknown OE '{}'".format(
                        port, oe_name
                    )
                )
            if els_name not in self._elss:
                raise CpoMappingError(
                    "interface {} references unknown ELS '{}'".format(
                        port, els_name
                    )
                )

            els_bank = interface.get("els_bank_id", "N/A")
            if els_bank != "N/A":
                try:
                    els_bank = int(els_bank)
                except (TypeError, ValueError) as exc:
                    raise CpoMappingError(
                        "interface {} has invalid ELS bank".format(port)
                    ) from exc

            lanes = _parse_integer_list(
                interface.get("lanes"), "interface {} lanes".format(port)
            )
            laser_ids = _parse_integer_list(
                interface.get("laser_ids"), "interface {} laser_ids".format(port)
            )
            laser_map = _parse_laser_lane_mapping(
                self._elss[els_name].get("laser_to_asic_lane_mapping", {}), els_name
            )
            if laser_map:
                if any(laser not in laser_map for laser in laser_ids):
                    raise CpoMappingError(
                        "interface {} references an unmapped ELS laser".format(port)
                    )
                covered_lanes = {
                    lane for laser in laser_ids for lane in laser_map[laser]
                }
                if not set(lanes).issubset(covered_lanes):
                    raise CpoMappingError(
                        "interface {} has ASIC lanes without an ELS laser mapping".format(port)
                    )

            self._parsed_interfaces[port] = InterfaceMapping(
                port=port,
                physical_ports=physical_ports,
                lanes=lanes,
                oe_id=oe_id,
                oe_bank=oe_bank,
                els_id=els_id,
                els_bank=els_bank,
                laser_ids=laser_ids,
                laser_to_asic_lane_mapping=laser_map,
            )

    def ports(self):
        return sorted(self._parsed_interfaces, key=natural_sort_key)

    def resource_ids(self, resource_type):
        resources = {
            OPTICAL_ENGINE: self._oes,
            EXTERNAL_LASER_SOURCE: self._elss,
        }.get(resource_type)
        if resources is None:
            raise CpoMappingError(
                "unsupported CPO resource type '{}'".format(resource_type)
            )
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
        try:
            return self._parsed_interfaces[port]
        except KeyError:
            raise KeyError(port)

    def get_interfaces(self, port=None):
        if port is not None:
            return [self.get_interface(port)]
        return [self.get_interface(name) for name in self.ports()]
