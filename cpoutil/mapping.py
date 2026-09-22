"""Helpers for interpreting the CPO topology used by the platform API."""

from dataclasses import dataclass
import re


OPTICAL_ENGINE = "oe"
EXTERNAL_LASER_SOURCE = "els"
PORT = "port"
SUPPORTED_RESOURCE_TYPES = {OPTICAL_ENGINE, EXTERNAL_LASER_SOURCE}


class CpoMappingError(ValueError):
    """Raised when cpo.json does not describe a usable CPO topology."""


def _natural_key(value):
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(value))]


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

    def __init__(self, cpo_data):
        if not isinstance(cpo_data, dict):
            raise CpoMappingError("cpo.json root must be an object")

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

            self._parsed_interfaces[port] = InterfaceMapping(
                port=port,
                physical_ports=physical_ports,
                lanes=_parse_integer_list(
                    interface.get("lanes"),
                    "interface {} lanes".format(port),
                ),
                oe_id=oe_id,
                oe_bank=oe_bank,
                els_id=els_id,
                els_bank=els_bank,
                laser_ids=_parse_integer_list(
                    interface.get("laser_ids"),
                    "interface {} laser_ids".format(port),
                ),
            )

    def ports(self):
        return sorted(self._parsed_interfaces, key=_natural_key)

    def resource_ids(self, resource_type):
        resources = {
            OPTICAL_ENGINE: self._oes,
            EXTERNAL_LASER_SOURCE: self._elss,
        }.get(resource_type)
        if resources is None:
            raise CpoMappingError(
                "unsupported CPO resource type '{}'".format(resource_type)
            )
        return sorted(resources, key=_natural_key)

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
