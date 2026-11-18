import copy

import pytest

from cpoutil.mapping import CpoMapping, CpoMappingError, CpoLaserResolutionError


@pytest.fixture
def topology():
    data = {
        "devices": {
            "oe0": {"device_type": "optical_engine", "max_banks": 1, "asic_lanes": [1, 2, 3, 4]},
            "els0": {"device_type": "external_laser_source",
                     "laser_to_asic_lane_mapping": {"1": [1, 2], "2": [3, 4]}},
        },
        "interfaces": {
            "Ethernet0": {"index": [1], "lanes": [1, 2, 3, 4],
                          "associated_devices": [{"device_id": "oe0", "bank": 0}, {"device_id": "els0"}]},
        },
    }
    ports = {
        "Ethernet0": {"index": (1,), "lanes": (1, 2)},
        "Ethernet2": {"index": (1,), "lanes": (3, 4)},
        "Ethernet8": {"index": (2,), "lanes": (9, 10)},
    }
    return data, ports


def test_mapping_resolves_breakout_and_computes_lane_and_laser_selection(topology):
    data, ports = topology
    mapping = CpoMapping(data, ports)
    assert mapping.resolve_interface("Ethernet2", ports).port == "Ethernet0"
    assert mapping.lane_positions("Ethernet2", ports) == (2, 3)
    assert mapping.lane_mask("Ethernet2", ports) == 12
    assert mapping.laser_selection("Ethernet2", ports) == ((1,), ())
    context = mapping.interface_context("Ethernet2", ports)
    assert context["lane_mask"] == 12
    assert context["laser_ids"] == (1,)
    assert mapping.lane_positions("1", ports) == (0, 1, 2, 3)


def test_mapping_finds_shared_lasers_and_resource_ports(topology):
    data, ports = topology
    ports["Ethernet0"]["lanes"] = (1,)
    mapping = CpoMapping(data, ports)
    assert mapping.laser_selection("Ethernet0", ports) == ((0,), (0,))
    assert mapping.ports_for_resource("oe", "oe0", ports) == ["Ethernet0", "Ethernet2"]
    assert mapping.ports_for_resource("els", 0, ports) == ["Ethernet0", "Ethernet2"]
    assert mapping.ports_for_physical_ports([1], ports) == ["Ethernet0", "Ethernet2"]


def test_mapping_preserves_missing_laser_mapping_read_only_policy(topology):
    data, ports = topology
    data["devices"]["els0"]["laser_to_asic_lane_mapping"] = {}
    data["platform_data"] = {"interfaces": {"Ethernet0": {"laser_ids": [0, 1]}}}
    mapping = CpoMapping(data, ports)
    with pytest.raises(CpoLaserResolutionError, match="needs laser_to_asic_lane_mapping"):
        mapping.interface_context("Ethernet2", ports)
    context = mapping.interface_context("Ethernet2", ports, require_lasers=False)
    assert context["laser_ids"] is None
    assert context["shared_laser_ids"] == ()
    ports["Ethernet0"]["lanes"] = (1, 2, 3, 4)
    assert mapping.laser_selection("Ethernet0", ports) == ((0, 1), ())


def test_mapping_rejects_unknown_and_ambiguous_interfaces(topology):
    data, ports = topology
    mapping = CpoMapping(data, ports)
    with pytest.raises(CpoMappingError, match="Unable to resolve"):
        mapping.resolve_interface("Ethernet8", ports)
    with pytest.raises(CpoMappingError, match="Invalid port"):
        mapping.resolve_interface("Ethernet999", ports)
    data["interfaces"]["Ethernet4"] = copy.deepcopy(data["interfaces"]["Ethernet0"])
    mapping = CpoMapping(data, ports)
    with pytest.raises(CpoMappingError, match="Unable to resolve"):
        mapping.resolve_interface("Ethernet2", ports)


@pytest.mark.parametrize("lanes, message", [((99,), "outside CPO interface"), ((), "has no lanes")])
def test_mapping_validates_active_lanes_without_mutating_input(topology, lanes, message):
    data, ports = topology
    ports["Ethernet2"]["lanes"] = lanes
    before = copy.deepcopy(ports)
    mapping = CpoMapping(data, ports)
    with pytest.raises(CpoMappingError, match=message):
        mapping.lane_positions("Ethernet2", ports)
    assert ports == before


@pytest.mark.parametrize("resource_type", ["oe", "els"])
@pytest.mark.parametrize("index", [0, 1, 17, 18])
def test_device_ids_accept_zero_and_unpadded_numbers(resource_type, index):
    name = "{}{}".format(resource_type.upper(), index)
    assert CpoMapping._resource_index(name, resource_type) == index


@pytest.mark.parametrize("resource_type", ["oe", "els"])
@pytest.mark.parametrize("digits", ["00", "01", "017", "018"])
def test_device_ids_reject_leading_zeros(resource_type, digits):
    name = resource_type.upper() + digits
    with pytest.raises(CpoMappingError, match="without leading zeros"):
        CpoMapping._resource_index(name, resource_type)


@pytest.mark.parametrize("device_id", ["OE17", "ELS18"])
def test_topology_keeps_unpadded_resource_names_consistent(topology, device_id):
    data, ports = topology
    resource_type = "oe" if device_id.startswith("OE") else "els"
    old_name = resource_type + "0"
    data["devices"][device_id] = data["devices"].pop(old_name)
    for association in data["interfaces"]["Ethernet0"]["associated_devices"]:
        if association["device_id"] == old_name:
            association["device_id"] = device_id
    mapping = CpoMapping(data, ports)
    name = device_id.lower()
    interface = mapping.get_interface("Ethernet0")
    assert getattr(interface, resource_type + "_name") == name
    assert mapping.resource_ids(resource_type) == [name]
    assert mapping.resolve_resource_ids(device_id, resource_type) == [name]
    assert mapping.resolve_resource_ids(device_id.lstrip("OELS"), resource_type) == [name]


@pytest.mark.parametrize("device_id", ["OE00", "ELS017"])
def test_topology_rejects_padded_device_ids_at_load(topology, device_id):
    data, ports = topology
    old_name = "oe0" if device_id.startswith("OE") else "els0"
    data["devices"][device_id] = data["devices"].pop(old_name)
    with pytest.raises(CpoMappingError, match="without leading zeros"):
        CpoMapping(data, ports)
