import json
import os
import sys
import types
from unittest import mock

import pytest
from click.testing import CliRunner


test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

from cpoutil import main as cpoutil  # noqa: E402
from cpoutil.mapping import CpoMapping, CpoMappingError  # noqa: E402
from cpoutil.mapping import (  # noqa: E402
    EXTERNAL_LASER_SOURCE,
    OPTICAL_ENGINE,
    PORT,
)


@pytest.fixture(autouse=True)
def shared_port_mapping(monkeypatch):
    """Provide port data to the real shared logical-port resolver."""
    ports = mock.Mock()
    ports.is_logical_port.side_effect = (
        lambda port: port in cpoutil.current_port_config
    )

    def physical_ports(port):
        indexes = cpoutil.current_port_config[port]["index"]
        if isinstance(indexes, (list, tuple)):
            return list(indexes)
        return [int(index) for index in str(indexes).split(",")]

    ports.get_logical_to_physical.side_effect = physical_ports
    monkeypatch.setattr(cpoutil.platform_sfputil_helper, "platform_sfputil", ports)
    return ports


CPO_DATA = {
    "oes": {
        "oe0": {"index": 0, "oe_cmis_path": "/sys/oe0/"},
        "oe1": {"index": 1, "oe_cmis_path": "/sys/oe1/"},
    },
    "elss": {
        "els0": {"index": 0},
        "els1": {"index": 1},
    },
    "interfaces": {
        "Ethernet8": {
            "index": "2,2,2,2",
            "lanes": "5,6,7,8",
            "oe_id": 0,
            "oe_bank_id": 1,
            "els_id": 0,
            "laser_ids": [4, 5, 6, 7],
        },
        "Ethernet0": {
            "index": "1,1,1,1",
            "lanes": "1,2,3,4",
            "oe_id": 0,
            "oe_bank_id": 0,
            "els_id": 0,
            "laser_ids": [0, 1, 2, 3],
        },
        "Ethernet16": {
            "index": "3,3,3,3",
            "lanes": "9,10,11,12",
            "oe_id": 1,
            "oe_bank_id": 0,
            "els_id": 1,
            "laser_ids": [0, 1, 2, 3],
        },
    },
}


class FakeCpo(cpoutil.CpoBase):
    def __init__(self, name):
        super().__init__(None, mock.Mock(), mock.Mock())
        self.name = name


class FakeChassis(object):
    def __init__(self, cpos):
        self.cpos = cpos
        self.calls = []

    def get_cpo(self, index):
        self.calls.append(index)
        return self.cpos.get(index)


class TestCpoMapping(object):
    def test_parses_current_platform_schema(self):
        mapping = CpoMapping(CPO_DATA)
        assert mapping.ports() == ["Ethernet0", "Ethernet8", "Ethernet16"]
        ethernet8 = mapping.get_interface("Ethernet8")
        assert ethernet8.physical_ports == (2,)
        assert ethernet8.lanes == (5, 6, 7, 8)
        assert ethernet8.to_dict()["oe"] == {"id": "oe0", "bank": 1}
        assert ethernet8.to_dict()["els"] == {
            "id": "els0", "bank": "N/A"
        }

    def test_resolves_numeric_and_named_resources(self):
        mapping = CpoMapping(CPO_DATA)
        assert mapping.resolve_resource_ids("0", OPTICAL_ENGINE) == ["oe0"]
        assert mapping.resolve_resource_ids("ELS1", EXTERNAL_LASER_SOURCE) == [
            "els1"
        ]
        assert mapping.resolve_resource_ids(None, OPTICAL_ENGINE) == [
            "oe0", "oe1"
        ]

    def test_rejects_unknown_oe(self):
        invalid = dict(CPO_DATA)
        invalid["interfaces"] = {
            "Ethernet0": dict(CPO_DATA["interfaces"]["Ethernet0"], oe_id=99)
        }
        with pytest.raises(CpoMappingError, match="unknown OE"):
            CpoMapping(invalid)


class TestPlatformObjectMapping(object):
    def setup_method(self):
        cpoutil.platform_chassis = FakeChassis({
            1: FakeCpo("cpo1"),
            2: FakeCpo("cpo2"),
            3: FakeCpo("cpo3"),
        })
        cpoutil.current_port_config = {
            "Ethernet0": {"index": "1", "lanes": "1,2"},
            "Ethernet1": {"index": "1", "lanes": "2", "subport": "2"},
            "Ethernet8": {"index": "2", "lanes": "5,6,7,8"},
            "Ethernet16": {"index": "3", "lanes": "9,10,11,12"},
        }

    def test_builds_global_oe_els_port_map(self):
        device_info = types.ModuleType("sonic_py_common.device_info")
        device_info.get_cpo_data = lambda: CPO_DATA
        sonic_py_common = types.ModuleType("sonic_py_common")
        sonic_py_common.device_info = device_info
        with mock.patch.dict(sys.modules, {
                "sonic_py_common": sonic_py_common,
                "sonic_py_common.device_info": device_info,
        }):
            cpoutil.load_cpo_object_map()

        cpo1 = cpoutil.platform_chassis.cpos[1]
        assert cpoutil.cpo_object_map[PORT][1] is cpo1
        assert cpoutil.cpo_object_map[OPTICAL_ENGINE]["oe0"] is cpo1
        assert cpoutil.cpo_object_map[EXTERNAL_LASER_SOURCE]["els0"] is cpo1
        assert cpoutil.cpo_object_map[OPTICAL_ENGINE]["oe1"].name == "cpo3"

    def test_rejects_non_cpo_platform_object(self):
        cpoutil.platform_chassis.cpos[1] = object()
        device_info = types.ModuleType("sonic_py_common.device_info")
        device_info.get_cpo_data = lambda: CPO_DATA
        sonic_py_common = types.ModuleType("sonic_py_common")
        sonic_py_common.device_info = device_info
        with mock.patch.dict(sys.modules, {
                "sonic_py_common": sonic_py_common,
                "sonic_py_common.device_info": device_info,
        }):
            with pytest.raises(cpoutil.CpoCommandError, match="CpoBase"):
                cpoutil.load_cpo_object_map()

    def test_breakout_names_resolve_to_same_physical_cpo(self):
        cpoutil.cpo_object_map = {
            OPTICAL_ENGINE: {},
            EXTERNAL_LASER_SOURCE: {},
            PORT: {1: cpoutil.platform_chassis.cpos[1]},
        }
        objects = cpoutil.get_port_cpo_objects("Ethernet1")
        assert objects[0][1] == 1
        assert objects[0][2].name == "cpo1"

    def test_invalid_logical_port_is_rejected(self):
        with pytest.raises(cpoutil.CpoCommandError, match="Invalid port"):
            cpoutil.logical_port_name_to_physical_port_list("Ethernet999")


class TestMappingCommand(object):
    def test_show_single_interface_as_json(self):
        cpoutil.cpo_mapping = CpoMapping(CPO_DATA)
        cpoutil.current_port_config = {
            "Ethernet8": {"index": "2", "lanes": "5,6,7,8"},
        }
        with mock.patch("cpoutil.main.initialize_platform"):
            result = CliRunner().invoke(
                cpoutil.cli,
                ["show", "interface", "map", "Ethernet8", "--json"],
            )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert set(payload["Ethernet8"]) == {"oe", "els"}
        assert payload["Ethernet8"]["oe"]["bank"] == 1
        assert payload["Ethernet8"]["oe"]["lanes"] == [5, 6, 7, 8]
        assert payload["Ethernet8"]["els"] == {
            "id": "ELS0",
            "lasers": [4, 5, 6, 7],
        }


# Additional cpoutil command and topology coverage.

COVERAGE_CPO_DATA = {
    "oes": {"oe0": {"index": 0}},
    "elss": {"els0": {"index": 0}},
    "interfaces": {
        "Ethernet0": {
            "index": "1",
            "lanes": "1,2",
            "oe_id": 0,
            "oe_bank_id": 0,
            "els_id": 0,
            "els_bank_id": 0,
            "laser_ids": [0, 1],
        },
    },
}


COMMUNITY_DATA = {
    "devices": {
        "oe0": {
            "device_type": "optical_engine",
            "asic_lanes": [1, 2, 3, 4],
            "max_banks": 2,
        },
        "els0": {
            "device_type": "external_laser_source",
            "laser_to_asic_lane_mapping": {
                "1": [1, 2],
                "2": [3, 4],
            },
        },
        "ignored0": {"device_type": "other"},
    },
    "interfaces": {
        "Ethernet0": {
            "associated_devices": [
                {"device_id": "oe0", "bank": 0},
                {"device_id": "els0", "bank": 2},
            ],
        },
        "Ethernet4": {
            "associated_devices": [
                {"device_id": "oe0", "bank": 1},
                {"device_id": "els0"},
            ],
        },
    },
}


COVERAGE_PORT_CONFIG = {
    "Ethernet0": {"index": "1", "lanes": "1,2"},
    "Ethernet4": {"index": "2", "lanes": "3,4", "subport": "2"},
}


class CoverageFakeApi:
    """CLI test double independent of the installed platform-common version."""

    NUM_CHANNELS = 2

    def __init__(self):
        self.calls = []

    def get_lpmode(self):
        return False

    def set_lpmode(self, value):
        self.calls.append(("set_lpmode", value))
        return True

    def reset(self):
        self.calls.append(("reset",))
        return True

    def tx_disable(self, value):
        self.calls.append(("tx_disable", value))
        return True

    def tx_disable_channel(self, mask, value):
        self.calls.append(("tx_disable_channel", mask, value))
        return True

    def get_module_state(self):
        return "ModuleReady"

    def get_module_temperature(self):
        return 45.25

    def get_rx_power(self):
        return [1.25, 1.5]

    def get_application_advertisement(self):
        return {
            1: {"host_electrical_interface_id": "400GAUI-4-L"},
            2: {"host_electrical_interface_id": "200GAUI-4"},
        }

    def get_application(self, lane):
        return lane + 1

    def get_active_apsel_hostlane(self):
        return {"ActiveAppSelLane1": 1, "ActiveAppSelLane2": 2}

    def get_datapath_state(self):
        return {"DP1State": "Active", "DP2State": "Inactive"}

    def get_tx_disable(self):
        return [False, True]

    def get_transceiver_info(self):
        return {
            "manufacturer": "Example OE",
            "application_advertisement": self.get_application_advertisement(),
            "supported_max_tx_power": 4.0,
            "supported_max_laser_freq": 195000,
            "cable_type": "Length(km)",
            "cable_length": 2,
        }

    def get_transceiver_dom_real_value(self):
        return {
            "temperature": 45.25,
            "voltage": 3.3,
            "rx1power": 1.2,
        }

    def get_transceiver_threshold_info(self):
        return {"temphighalarm": 90.0, "txpowerhighalarm": 3.0}

    def get_elsfp_info(self):
        return {"manufacturer": "Example ELS", "lane_count": 2}

    def get_elsfp_status(self):
        return {
            "module_state": "ModuleReady",
            "module_low_power_state": False,
            "interrupt_status": False,
        }

    def get_elsfp_module_state(self):
        return "ModuleReady"

    def get_elsfp_dom_real_value(self):
        return {
            "temperature": 30.5,
            "voltage": 3.2,
            "optical_power_lane1": -1.0,
            "optical_power_lane3": -3.0,
        }

    def get_elsfp_threshold_info(self):
        return {"temperature_alarm_high": 75.0}

    def get_per_lane_state(self):
        return {"Laser0State": "Active", "Laser1State": "Inactive"}

    def get_per_lane_opt_power_monitor(self):
        return {
            "Laser0OpticalPowerMonitor": 9.1,
            "Laser1OpticalPowerMonitor": 9.2,
            "Laser2OpticalPowerMonitor": 9.3,
        }

    def set_elsfp_lpmode(self, value):
        self.calls.append(("set_elsfp_lpmode", value))
        return True

    def reset_elsfp(self):
        raise NotImplementedError("ELS reset is not implemented")

    def supports_per_lane_enable(self):
        return True

    def set_per_lane_enable(self, mask, enabled):
        self.calls.append(("set_per_lane_enable", mask, enabled))
        return True

    def get_max_supported_banks(self):
        return 1


class CoverageFakeEndpoint(object):
    def __init__(self, api):
        self.api = api

    def get_api(self):
        return self.api

    def get_presence(self):
        return True


class CoverageFakeCpo(cpoutil.CpoBase):
    def __init__(self):
        super().__init__(None, self, self)
        self.api = CoverageFakeApi()
        self.reads = []
        self.writes = []

    def get_api(self):
        return self.api

    def get_presence(self):
        return True

    def read_eeprom(self, offset, size):
        self.reads.append((offset, size))
        return bytearray((index % 256 for index in range(size)))

    def write_eeprom(self, offset, size, data):
        self.writes.append((offset, size, bytearray(data)))
        return True


@pytest.fixture
def coverage_environment(monkeypatch):
    cpo = CoverageFakeCpo()
    cpoutil.cpo_mapping = CpoMapping(COVERAGE_CPO_DATA, COVERAGE_PORT_CONFIG)
    cpoutil.current_port_config = dict(COVERAGE_PORT_CONFIG)
    cpoutil.cpo_oe_bank_counts = {}
    cpoutil.cpo_object_map = {
        OPTICAL_ENGINE: {"oe0": cpo},
        EXTERNAL_LASER_SOURCE: {"els0": cpo},
        PORT: {1: cpo},
    }
    monkeypatch.setattr(cpoutil, "initialize_platform", lambda: None)
    monkeypatch.setattr(
        cpoutil,
        "_eeprom_linear_offset",
        lambda resource_type, resource_id, obj, bank, page, offset:
        bank * 0x10000 + page * 0x100 + offset,
    )
    return cpo


def invoke_coverage(arguments):
    return CliRunner().invoke(cpoutil.cli, arguments)


def command_paths(command, path=()):
    yield path
    for name, child in getattr(command, "commands", {}).items():
        yield from command_paths(child, path + (name,))


HARDWARE_COMMANDS = [
    ["show", "interface", name] for name in
    ("map", "dom", "tx_disable", "speed", "lane-status")
] + [
    ["show", "oe", name] for name in
    ("lpmode", "status", "temperature", "input-power")
] + [
    ["show", "els", name] for name in
    ("presence", "lpmode", "status", "temperature", "output-power")
] + [
    ["config", "interface", "tx_disable", "Ethernet0", "enable"],
    ["config", "oe", "lpmode", "0", "full"],
    ["config", "oe", "reset", "0"],
    ["config", "oe", "tx_disable", "0", "enable"],
    ["config", "els", "lpmode", "0", "full"],
    ["config", "els", "reset", "0"],
    ["config", "els", "tx_disable", "0", "enable"],
    ["read-eeprom"],
    ["read-eeprom", "interface", "Ethernet0", "--oe"],
    ["read-eeprom", "oe"],
    ["read-eeprom", "els"],
    ["write-eeprom", "interface", "Ethernet0", "--oe", "-n", "0", "-o", "0", "-d", "00"],
    ["write-eeprom", "oe", "-i", "0", "-n", "0", "-o", "0", "-d", "00"],
    ["write-eeprom", "els", "-i", "0", "-n", "0", "-o", "0", "-d", "00"],
]


class TestCommandInitialization:
    @pytest.mark.parametrize("path", list(command_paths(cpoutil.cli)))
    @pytest.mark.parametrize("help_option", ["-h", "--help"])
    def test_help_does_not_load_platform(self, monkeypatch, path, help_option):
        initialize = mock.Mock(side_effect=AssertionError("help accessed hardware"))
        monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
        result = invoke_coverage([*path, help_option])
        assert result.exit_code == 0, result.output
        assert "Usage:" in result.output
        initialize.assert_not_called()

    @pytest.mark.parametrize("arguments", HARDWARE_COMMANDS)
    def test_hardware_commands_require_topology(self, monkeypatch, arguments):
        initialize = mock.Mock(side_effect=cpoutil.CpoCommandError(
            "CPO topology is unavailable for this platform"))
        monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
        result = invoke_coverage(arguments)
        assert result.exit_code != 0
        assert "Error: CPO topology is unavailable for this platform" in result.output
        initialize.assert_called_once_with()

    @pytest.mark.parametrize("arguments", [
        ["config", "oe", "reset"],
        ["config", "oe", "lpmode", "0", "invalid"],
        ["read-eeprom", "oe", "--page", "invalid"],
    ])
    def test_invalid_arguments_do_not_load_platform(self, monkeypatch, arguments):
        initialize = mock.Mock(side_effect=AssertionError("invalid arguments accessed hardware"))
        monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
        result = invoke_coverage(arguments)
        assert result.exit_code == 2
        initialize.assert_not_called()

    @pytest.mark.parametrize("arguments", [
        ["show", "oe", "status", "0"],
        ["read-eeprom", "oe", "-i", "0", "-n", "0", "-o", "0", "-s", "1"],
        ["read-eeprom"],
    ])
    def test_successful_commands_initialize_once(self, coverage_environment, monkeypatch, arguments):
        initialize = mock.Mock()
        monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
        result = invoke_coverage(arguments)
        assert result.exit_code == 0, result.output
        initialize.assert_called_once_with()
        assert result.output

    @pytest.mark.parametrize("error", [cpoutil.CpoCommandError, CpoMappingError])
    def test_entry_point_preserves_initialization_error_code(self, monkeypatch, capsys, error):
        monkeypatch.setattr(cpoutil, "initialize_platform", mock.Mock(side_effect=error("unavailable")))
        monkeypatch.setattr(sys, "argv", ["cpoutil", "show", "oe", "status"])
        assert cpoutil.main() == cpoutil.ERROR_INVALID_RESOURCE
        assert "Error: unavailable" in capsys.readouterr().err


class TestCommunityMappingCoverage(object):
    def test_normalizes_community_schema(self):
        mapping = CpoMapping(COMMUNITY_DATA, COVERAGE_PORT_CONFIG)
        first = mapping.get_interface("Ethernet0")
        second = mapping.get_interface("Ethernet4")
        assert first.physical_ports == (1,)
        assert first.lanes == (1, 2)
        assert first.laser_ids == (0,)
        assert first.els_bank == 2
        assert second.lanes == (3, 4)
        assert second.laser_ids == (1,)
        assert mapping.resource_ids(OPTICAL_ENGINE) == ["oe0"]
        assert mapping.get_interfaces("Ethernet0") == [first]

    @pytest.mark.parametrize(
        "data,match",
        [
            (None, "root must be an object"),
            ({"oes": {}, "elss": {}, "interfaces": {}}, "non-empty oes"),
            ({"oes": {"oe0": {}}, "elss": {}, "interfaces": {}},
             "non-empty elss"),
            ({"oes": {"oe0": {}}, "elss": {"els0": {}},
              "interfaces": {}}, "non-empty interfaces"),
        ],
    )
    def test_rejects_missing_topology_sections(self, data, match):
        with pytest.raises(CpoMappingError, match=match):
            CpoMapping(data)

    def test_rejects_bad_community_associations(self):
        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["interfaces"]["Ethernet0"] = "bad"
        with pytest.raises(CpoMappingError, match="must be an object"):
            CpoMapping(data, COVERAGE_PORT_CONFIG)

        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["interfaces"]["Ethernet0"].pop("associated_devices")
        with pytest.raises(CpoMappingError, match="no associated_devices"):
            CpoMapping(data, COVERAGE_PORT_CONFIG)

        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["interfaces"]["Ethernet0"]["associated_devices"][0][
            "device_id"
        ] = "missing0"
        with pytest.raises(CpoMappingError, match="unknown device"):
            CpoMapping(data, COVERAGE_PORT_CONFIG)

        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["interfaces"]["Ethernet0"]["associated_devices"] = [
            {"device_id": "oe0"}, "ignored"
        ]
        with pytest.raises(CpoMappingError, match="one OE and one ELS"):
            CpoMapping(data, COVERAGE_PORT_CONFIG)

    def test_mapping_validation_errors(self):
        bad = json.loads(json.dumps(COVERAGE_CPO_DATA))
        bad["oes"]["bad"] = bad["oes"].pop("oe0")
        with pytest.raises(CpoMappingError, match="inconsistent index"):
            CpoMapping(bad)

        bad = json.loads(json.dumps(COVERAGE_CPO_DATA))
        bad["interfaces"]["Ethernet0"]["els_bank_id"] = "bad"
        with pytest.raises(CpoMappingError, match="invalid ELS bank"):
            CpoMapping(bad)

        mapping = CpoMapping(COVERAGE_CPO_DATA)
        with pytest.raises(CpoMappingError, match="unsupported"):
            mapping.resource_ids("bad")
        with pytest.raises(KeyError):
            mapping.resolve_resource_ids("99", OPTICAL_ENGINE)
        with pytest.raises(KeyError):
            mapping.get_interface("Ethernet99")


class TestHelperCoverage(object):
    def test_port_and_lane_helpers(self, coverage_environment):
        assert cpoutil.logical_port_name_to_physical_port_list("Ethernet0") == [1]
        assert cpoutil.logical_port_name_to_physical_port_list("7") == [7]
        assert cpoutil.get_port_lanes("Ethernet0") == (1, 2)
        assert cpoutil.get_cpo_lane_positions("Ethernet0") == (0, 1)
        assert cpoutil.get_cpo_lane_mask("Ethernet0") == 3
        assert cpoutil.get_cpo_laser_ids("Ethernet0") == ((0, 1), ())
        assert cpoutil.get_physical_port_name("Ethernet0", 2, True).endswith(
            "(ganged)"
        )
        assert cpoutil.get_physical_port_name("Ethernet0", 1, False) == \
            "Ethernet0"
        assert cpoutil.get_port_cpo_objects("Ethernet0")[0][1] == 1
        assert cpoutil.get_resource_cpo_objects(OPTICAL_ENGINE, "0")[0][0] == \
            "oe0"

    def test_public_api_endpoint_paths(self, coverage_environment):
        cpo = coverage_environment
        assert cpoutil.get_oe_api(cpo, "oe0") is cpo.api
        assert cpoutil.get_els_api(cpo, "els0") is cpo.api
        assert cpoutil.get_els_presence(cpo)

        oe_api, els_api = object(), object()
        public_cpo = cpoutil.CpoBase(
            None, CoverageFakeEndpoint(oe_api), CoverageFakeEndpoint(els_api)
        )
        assert cpoutil.get_oe_api(public_cpo, "oe0") is oe_api
        assert cpoutil.get_els_api(public_cpo, "els0") is els_api
        assert cpoutil.get_els_presence(public_cpo)

    def test_normalizers_and_filters(self):
        assert cpoutil.get_els_lpmode(
            mock.Mock(get_elsfp_status=lambda: {"module_state": "ModuleLowPwr"})
        ) is True
        assert cpoutil.get_els_lpmode(
            mock.Mock(get_elsfp_status=lambda: {"module_state": "ModuleReady"})
        ) is False
        assert cpoutil._namespace_els_values({"temperature": 1, "els_x": 2}) == {
            "els_temperature": 1,
            "els_x": 2,
        }
        assert cpoutil._get_els_lane_count({"laser_count": "2"}) == 2
        assert "optical_power_lane3" not in cpoutil._filter_els_dom_lanes(
            {"optical_power_lane1": 1, "optical_power_lane3": 3}, 2
        )
        assert list(cpoutil._filter_els_monitor_lanes([1, 2, 3], 2)) == [1, 2]
        assert cpoutil._filter_els_monitor_lanes(
            {"Laser0State": 1, "Laser2State": 2}, 2
        ) == {"Laser0State": 1}
        assert cpoutil._select_lane_values({"DP2": 2, "DP1": 1}, (1,)) == {
            "lane01": 2
        }
        assert cpoutil._select_els_laser_values(
            {"Laser0": "a", "Laser1": "b"}, (1,)
        ) == {"lane01": "b"}

    def test_formatters(self, capsys):
        advertisements = {
            1: {
                "host_electrical_interface_id": "400GAUI-4-L",
                "module_media_interface_id": "FR4",
                "host_lane_assignment_options": 3,
                "media_lane_assignment_options": None,
            },
            2: "legacy",
        }
        assert "Host Assign" in cpoutil._format_application_advertisement(
            advertisements
        )[0]
        assert cpoutil._format_application_advertisement("not-a-dict") == [
            "not-a-dict"
        ]
        info = {
            "manufacturer": "Vendor",
            "application_advertisement": advertisements,
            "cable_type": "Length(km)",
            "cable_length": 2,
            "supported_max_tx_power": 4,
            "supported_max_laser_freq": 195000,
            "els_max_laser_bias": 20,
        }
        assert any("Vendor" in line for line in cpoutil._format_cpo_info(info))
        dom = {
            "rx1power": 1.2,
            "txpowerhighalarm": 3.0,
            "temperature": 40.0,
            "temphighalarm": 90.0,
            "els_temperature": 30.0,
            "els_temperature_alarm_high": 75.0,
            "els_optical_power_lane1": -1.0,
            "extra": {"nested": True},
        }
        lines = cpoutil._format_cpo_dom(dom)
        assert any("AdditionalValues" in line for line in lines)
        assert "CPO EEPROM detected" in cpoutil._format_interface_dom(
            "Ethernet0", None, None, None
        )
        cpoutil.print_records({"oe0": [1, 2]}, False, field_header="Lane")
        cpoutil.print_speed_records(
            {"Ethernet0": {"Application Select Controls": {"lane00": 400000}}},
            False,
        )
        cpoutil.print_lane_status_records(
            {
                "Ethernet0": {
                    "Data Path State Indicator": {"lane00": "Active"},
                    "ELS": "ELS0",
                    "ELS Status": {"module_state": "Ready"},
                    "ELS Lane State": {"lane00": "Active"},
                    "ELS Lasers": [0],
                    "Shared ELS Lasers": [],
                }
            },
            False,
        )
        assert "Ethernet0" in capsys.readouterr().out


class TestCommandCoverage(object):
    @pytest.mark.parametrize(
        "arguments",
        [
            ["show", "interface", "map"],
            ["show", "interface", "dom", "Ethernet0"],
            ["show", "interface", "dom", "Ethernet0", "--json"],
            ["show", "interface", "tx_disable", "Ethernet0"],
            ["show", "interface", "speed", "Ethernet0"],
            ["show", "interface", "lane-status", "Ethernet0"],
            ["show", "oe", "lpmode"],
            ["show", "oe", "status"],
            ["show", "oe", "temperature"],
            ["show", "oe", "input-power"],
            ["show", "els", "presence"],
            ["show", "els", "lpmode"],
            ["show", "els", "status"],
            ["show", "els", "temperature"],
            ["show", "els", "output-power"],
        ],
    )
    def test_read_only_commands(self, coverage_environment, arguments):
        result = invoke_coverage(arguments)
        assert result.exit_code == 0, result.output

    @pytest.mark.parametrize(
        "arguments",
        [
            ["config", "interface", "tx_disable", "Ethernet0", "enable"],
            ["config", "oe", "lpmode", "0", "low"],
            ["config", "oe", "lpmode", "0", "full"],
            ["config", "oe", "reset", "0"],
            ["config", "oe", "tx_disable", "0", "enable"],
            ["config", "els", "lpmode", "0", "low"],
            ["config", "els", "tx_disable", "0", "disable"],
        ],
    )
    def test_config_commands(self, coverage_environment, arguments):
        result = invoke_coverage(arguments)
        assert result.exit_code == 0, result.output
        assert "OK" in result.output

    def test_oe_reset_reports_reprovisioning_requirement(self, coverage_environment):
        result = invoke_coverage(["config", "oe", "reset", "0"])
        assert result.exit_code == 0, result.output
        assert "Resetting OE0 ... OK" in result.output
        assert "Affected ports may require application and datapath reprovisioning" in result.output
        assert coverage_environment.api.calls == [("reset",)]
        assert not coverage_environment.writes

    @pytest.mark.parametrize("unsupported", [False, True])
    def test_oe_reset_failure_is_reported(self, coverage_environment, monkeypatch, unsupported):
        reset = mock.Mock(return_value=False)
        if unsupported:
            reset.side_effect = NotImplementedError("OE reset is not implemented")
        monkeypatch.setattr(coverage_environment.api, "reset", reset)
        result = invoke_coverage(["config", "oe", "reset", "0"])
        assert result.exit_code != 0
        assert "Resetting OE0 ... Failed" in result.output
        assert "reprovisioning" not in result.output
        error = "OE reset is not implemented" if unsupported else "Resetting OE0 failed"
        assert error in result.output
        reset.assert_called_once_with()

    def test_oe_reset_help_describes_module_defaults(self):
        result = invoke_coverage(["config", "oe", "reset", "--help"])
        assert result.exit_code == 0, result.output
        help_text = " ".join(result.output.split())
        assert "Module settings may return to defaults" in help_text
        assert "application and datapath reprovisioning" in help_text

    def test_unimplemented_els_reset(self, coverage_environment):
        result = invoke_coverage(["config", "els", "reset", "0"])
        assert result.exit_code != 0
        assert "not implemented" in result.output

    @pytest.mark.parametrize(
        "arguments",
        [
            ["read-eeprom", "interface", "Ethernet0", "--oe",
             "-n", "0", "-o", "0", "-s", "16"],
            ["read-eeprom", "interface", "Ethernet0", "--els",
             "-n", "0x1a", "-o", "0x80", "-s", "16"],
            ["read-eeprom", "oe", "-i", "0", "-b", "0",
             "-n", "0", "-o", "0", "-s", "16"],
            ["read-eeprom", "els", "-i", "0",
             "-n", "0x1a", "-o", "0x80", "-s", "16"],
            ["write-eeprom", "interface", "Ethernet0", "--oe",
             "-n", "0", "-o", "0x80", "-d", "01 02"],
            ["write-eeprom", "interface", "Ethernet0", "--els",
             "-n", "0x1a", "-o", "0x80", "-d", "01 02"],
            ["write-eeprom", "oe", "-i", "0", "-b", "0",
             "-n", "0", "-o", "0x80", "-d", "01 02"],
            ["write-eeprom", "els", "-i", "0", "-b", "0",
             "-n", "0x1a", "-o", "0x80", "-d", "01 02"],
        ],
    )
    def test_eeprom_ranges_and_writes(self, coverage_environment, arguments):
        result = invoke_coverage(arguments)
        assert result.exit_code == 0, result.output

    def test_full_eeprom_commands(self, coverage_environment):
        for arguments in (
            ["read-eeprom", "interface", "Ethernet0", "--oe"],
            ["read-eeprom", "oe", "-i", "0"],
            ["read-eeprom", "els", "-i", "0"],
        ):
            result = invoke_coverage(arguments)
            assert result.exit_code == 0, result.output
            assert "EEPROM hexdump" in result.output

    def test_eeprom_validation_errors(self, coverage_environment):
        with pytest.raises(cpoutil.CpoCommandError):
            cpoutil._validate_eeprom_range(0, 0, 255, 2)
        with pytest.raises(cpoutil.CpoCommandError):
            cpoutil._parse_hex_data("")
        with pytest.raises(cpoutil.CpoCommandError):
            cpoutil._interface_target_option(True, True)
        with pytest.raises(cpoutil.CpoCommandError):
            cpoutil._eeprom_range_requested(0, None, 1)
        assert cpoutil._resource_banks(EXTERNAL_LASER_SOURCE, "els0") == [0]
        assert cpoutil._resource_banks(OPTICAL_ENGINE, "oe0") == [0]
        assert cpoutil._format_eeprom_hexdump(b"ABC", 0).endswith("|ABC|")


class TestCpoHelpers:
    def test_shared_eeprom_and_dom_formatting(self):
        assert cpoutil._format_eeprom_hexdump(b"", 128) == ""
        assert cpoutil._format_eeprom_hexdump(b"ABCDEFGHIJKLMNOPQ", 128) == (
            "        00000080 41 42 43 44 45 46 47 48  49 4a 4b 4c 4d 4e 4f 50 |ABCDEFGHIJKLMNOP|\n"
            "        00000090 51                                               |Q|"
        )
        lines = ["ChannelMonitorValues:"]
        cpoutil._append_dom_values(
            lines,
            {"rx10power": "Unknown", "rx2power": "-2.1dBm", "rx1power": "N/A"},
            {"rx10power": "Rx10", "rx2power": "Rx2", "rx1power": "Rx1"},
            {"rx10power": "dBm", "rx2power": "dBm", "rx1power": "dBm"},
        )
        assert lines == [
            "ChannelMonitorValues:",
            "                Rx2: -2.1dBm",
            "                Rx10: Unknown",
        ]

    def test_reuses_cached_chassis(self, monkeypatch):
        chassis = FakeChassis({})
        monkeypatch.setattr(cpoutil.platform_sfputil_helper, "platform_chassis", chassis)
        with mock.patch.dict(sys.modules, {"sonic_platform": None}):
            cpoutil.load_platform_chassis()
            cpoutil.load_platform_chassis()
        assert cpoutil.platform_chassis is chassis

    def test_chassis_load_failure_is_reported(self, monkeypatch, capsys):
        monkeypatch.setattr(cpoutil.platform_sfputil_helper, "platform_chassis", None)
        with mock.patch.dict(sys.modules, {"sonic_platform": None}):
            with pytest.raises(SystemExit):
                cpoutil.load_platform_chassis()
        assert "Failed to load platform chassis" in capsys.readouterr().out

    def test_port_configuration_uses_shared_helpers(self, monkeypatch, shared_port_mapping):
        helper = cpoutil.platform_sfputil_helper
        shared_port_mapping.logical = ["Ethernet0", "Ethernet2"]
        shared_port_mapping.get_logical_to_physical.side_effect = lambda port: [1]
        lane_fields = {"Ethernet0": "41,43", "Ethernet2": "42,44"}
        shared_port_mapping.is_logical_port.side_effect = lambda port: port in lane_fields
        monkeypatch.setattr(helper, "platform_sfputil", None)
        load = mock.Mock(side_effect=lambda: setattr(helper, "platform_sfputil", shared_port_mapping))
        read_mappings = mock.Mock()
        read_lanes = mock.Mock(side_effect=lambda db, table, field, port: lane_fields[port])
        monkeypatch.setattr(helper, "load_platform_sfputil", load)
        monkeypatch.setattr(helper, "platform_sfputil_read_porttab_mappings", read_mappings)
        monkeypatch.setattr(helper, "get_value_from_db_by_field", read_lanes)
        cpoutil.load_current_port_config()
        load.assert_called_once_with()
        read_mappings.assert_called_once_with()
        assert cpoutil.current_port_config == {
            "Ethernet0": {"index": [1], "lanes": (41, 43)},
            "Ethernet2": {"index": [1], "lanes": (42, 44)},
        }
        assert read_lanes.call_args_list == [
            mock.call("CONFIG_DB", "PORT", "lanes", "Ethernet0"),
            mock.call("CONFIG_DB", "PORT", "lanes", "Ethernet2"),
        ]
        cpoutil.load_current_port_config()
        load.assert_called_once_with()

    def test_missing_topology_is_reported_without_file_fallback(self, monkeypatch):
        from sonic_py_common import device_info

        loader = mock.Mock(return_value=None)
        monkeypatch.setattr(device_info, "get_cpo_data", loader)
        with mock.patch("builtins.open", side_effect=AssertionError("unexpected file read")):
            with pytest.raises(cpoutil.CpoCommandError, match="topology is unavailable"):
                cpoutil.load_cpo_object_map()
        loader.assert_called_once_with()

    def test_only_els_presence_is_read(self):
        oe = mock.Mock(get_presence=mock.Mock(return_value=True))
        els = mock.Mock(get_presence=mock.Mock(return_value=False))
        cpo = cpoutil.CpoBase(None, oe, els)
        assert cpoutil.get_els_presence(cpo) is False
        oe.get_presence.assert_not_called()
        assert cpoutil.get_els_api(cpo, "els0") is els.get_api.return_value


class TestOptionalElsApis:
    @pytest.mark.parametrize("arguments", [
        ["config", "els", "lpmode", "0", "low"],
        ["config", "els", "reset", "0"],
        ["config", "els", "tx_disable", "0", "enable"],
        ["config", "interface", "tx_disable", "Ethernet0", "enable"],
        ["show", "els", "status", "0"],
        ["show", "interface", "lane-status", "Ethernet0"],
    ])
    def test_unsupported_els_commands_do_not_change_oe(
            self, coverage_environment, monkeypatch, arguments):
        # Exercise the CLI's handling of the optional API contract here.
        # The companion platform-common PR defines the optional ELS API stubs.
        els_api = CoverageFakeApi()
        for method in (
                "set_elsfp_lpmode", "reset_elsfp", "set_per_lane_enable",
                "get_elsfp_module_state", "get_per_lane_state"):
            monkeypatch.setattr(els_api, method, mock.Mock(
                side_effect=NotImplementedError("ELS operation is not implemented")))
        monkeypatch.setattr(els_api, "supports_per_lane_enable", lambda: False)
        oe_api = CoverageFakeApi()
        cpo = cpoutil.CpoBase(
            None, CoverageFakeEndpoint(oe_api), CoverageFakeEndpoint(els_api))
        monkeypatch.setattr(cpoutil, "cpo_object_map", {
            OPTICAL_ENGINE: {"oe0": cpo},
            EXTERNAL_LASER_SOURCE: {"els0": cpo},
            PORT: {1: cpo},
        })
        result = invoke_coverage(arguments)
        assert result.exit_code != 0
        assert "not implemented" in result.output
        assert "has no attribute" not in result.output
        assert "OK" not in result.output
        assert oe_api.calls == []
        assert els_api.calls == []
        els_api.set_per_lane_enable.assert_not_called()

    def test_supported_els_reset_is_dispatched_without_resetting_oe(self, coverage_environment):
        cpo = cpoutil.cpo_object_map[EXTERNAL_LASER_SOURCE]["els0"]
        cpo.api.reset_elsfp = mock.Mock(return_value=True)
        result = invoke_coverage(["config", "els", "reset", "0"])
        assert result.exit_code == 0, result.output
        cpo.api.reset_elsfp.assert_called_once_with()
        assert cpo.api.calls == []

    def test_els_module_state_read_failure_is_not_reported_as_success(self, coverage_environment):
        cpo = cpoutil.cpo_object_map[EXTERNAL_LASER_SOURCE]["els0"]
        cpo.api.get_elsfp_module_state = mock.Mock(return_value=None)
        result = invoke_coverage(["show", "els", "status", "0", "--json"])
        assert result.exit_code != 0
        assert "module state API returned no data" in result.output

    def test_public_eeprom_uses_the_selected_endpoint(self, coverage_environment, monkeypatch):
        oe = CoverageFakeCpo()
        els = CoverageFakeCpo()
        cpo = cpoutil.CpoBase(None, oe, els)
        cpo.get_els_base_page = mock.Mock(return_value=0)
        monkeypatch.setattr(cpoutil, "cpo_object_map", {
            OPTICAL_ENGINE: {"oe0": cpo}, EXTERNAL_LASER_SOURCE: {"els0": cpo}, PORT: {1: cpo}})
        for resource_type, endpoint in ((OPTICAL_ENGINE, oe), (EXTERNAL_LASER_SOURCE, els)):
            cpoutil._read_one_eeprom(resource_type, "{}0".format(resource_type), cpo, 0, 0, 0, 2)
            cpoutil._write_resource_eeprom(resource_type, "0", 0, 0, 0, bytearray([1, 2]))
            assert len(endpoint.reads) == len(endpoint.writes) == 1

    @pytest.mark.parametrize("placeholder", [False, True])
    def test_unmapped_public_els_eeprom_is_not_implemented(
            self, monkeypatch, placeholder):
        monkeypatch.delattr(cpoutil.CpoBase, "get_els_base_page", raising=False)
        cpo = cpoutil.CpoBase(None, mock.Mock(), mock.Mock())
        if placeholder:
            cpo.get_els_base_page = mock.Mock(side_effect=NotImplementedError())
        with pytest.raises(
                cpoutil.CpoCommandError,
                match="ELS EEPROM page mapping is not implemented"):
            cpoutil._physical_eeprom_page(EXTERNAL_LASER_SOURCE, "els0", cpo, 0)
        cpo.elsfp.read_eeprom.assert_not_called()
        cpo.elsfp.write_eeprom.assert_not_called()

    def test_public_els_eeprom_uses_platform_page_mapping(self):
        cpo = cpoutil.CpoBase(None, mock.Mock(), mock.Mock())
        cpo.get_els_base_page = mock.Mock(return_value=0xB0)
        assert cpoutil._physical_eeprom_page(
            EXTERNAL_LASER_SOURCE, "els0", cpo, 2) == 0xB2


class TestExplicitLaserMapping:
    @staticmethod
    def configure(monkeypatch, data, ports):
        mapping = CpoMapping(data, ports)
        monkeypatch.setattr(cpoutil, "cpo_mapping", mapping)
        monkeypatch.setattr(cpoutil, "current_port_config", ports)
        return mapping

    @staticmethod
    def nonuniform_topology():
        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["devices"]["oe0"].update(asic_lanes=[1, 2, 3, 4, 5, 6], max_banks=1)
        # The first laser owns noncontiguous lanes; the groups have unequal sizes.
        data["devices"]["els0"]["laser_to_asic_lane_mapping"] = {
            "1": [1, 3, 5], "2": [2], "3": [4, 6],
        }
        del data["interfaces"]["Ethernet4"]
        return data

    def test_noncontiguous_unequal_groups_select_exact_lasers(self, monkeypatch):
        self.configure(monkeypatch, self.nonuniform_topology(), {
            "Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"},
            "Ethernet1": {"index": "1", "lanes": "1,3,5"},
            "Ethernet2": {"index": "1", "lanes": "2,4,6"},
        })
        assert cpoutil.get_cpo_laser_ids("Ethernet1") == ((0,), ())
        assert cpoutil.get_cpo_laser_ids("Ethernet2") == ((1, 2), ())

    def test_explicit_mapping_controls_only_selected_lanes(self, monkeypatch, coverage_environment):
        self.configure(monkeypatch, self.nonuniform_topology(), {
            "Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"},
            "Ethernet1": {"index": "1", "lanes": "1,3,5"},
        })
        result = invoke_coverage(["config", "interface", "tx_disable", "Ethernet1", "enable"])
        assert result.exit_code == 0, result.output
        assert coverage_environment.api.calls == [
            ("tx_disable_channel", 0b010101, True),
            ("set_per_lane_enable", 0b001, False),
        ]

    def test_shared_laser_across_banks_blocks_all_writes(self, monkeypatch, coverage_environment):
        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["devices"]["els0"]["laser_to_asic_lane_mapping"] = {
            "1": [1, 3], "2": [2], "3": [4],
        }
        self.configure(monkeypatch, data, COVERAGE_PORT_CONFIG)
        assert cpoutil.get_cpo_laser_ids("Ethernet0") == ((0, 1), (0,))
        result = invoke_coverage(["config", "interface", "tx_disable", "Ethernet0", "enable"])
        assert result.exit_code != 0
        assert "shares ELS laser(s) 0" in result.output
        assert coverage_environment.api.calls == []

    def test_shared_laser_within_bank_blocks_all_writes(self, monkeypatch, coverage_environment):
        self.configure(monkeypatch, self.nonuniform_topology(), {
            "Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"},
            "Ethernet1": {"index": "1", "lanes": "1,3"},
        })
        assert cpoutil.get_cpo_laser_ids("Ethernet1") == ((0,), (0,))
        result = invoke_coverage(["config", "interface", "tx_disable", "Ethernet1", "enable"])
        assert result.exit_code != 0
        assert coverage_environment.api.calls == []

    def test_breakout_without_lane_mapping_is_rejected(self, monkeypatch, coverage_environment):
        self.configure(monkeypatch, COVERAGE_CPO_DATA, {
            "Ethernet0": {"index": "1", "lanes": "1,2"},
            "Ethernet1": {"index": "1", "lanes": "2"},
        })
        assert cpoutil.get_cpo_laser_ids("Ethernet0") == ((0, 1), ())
        result = invoke_coverage(["config", "interface", "tx_disable", "Ethernet1", "enable"])
        assert result.exit_code != 0
        assert "needs laser_to_asic_lane_mapping" in result.output
        assert coverage_environment.api.calls == []

    def test_incomplete_explicit_lane_mapping_is_rejected(self):
        data = self.nonuniform_topology()
        del data["devices"]["els0"]["laser_to_asic_lane_mapping"]["3"]
        with pytest.raises(CpoMappingError, match="ASIC lanes without an ELS laser mapping"):
            CpoMapping(data, {"Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"}})

    @pytest.mark.parametrize("laser_map", [{"0": [1, 2]}, {"bad": [1, 2]}, {"1": []}, []])
    def test_invalid_explicit_mapping_is_rejected(self, laser_map):
        data = self.nonuniform_topology()
        data["devices"]["els0"]["laser_to_asic_lane_mapping"] = laser_map
        with pytest.raises(CpoMappingError):
            CpoMapping(data, {"Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"}})

    def test_normalized_integer_laser_ids_and_string_lanes(self, monkeypatch):
        data = self.nonuniform_topology()
        data["devices"]["els0"]["laser_to_asic_lane_mapping"] = {
            1: "1,3,5", 2: "2", 3: "4,6",
        }
        self.configure(monkeypatch, data, {
            "Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"},
            "Ethernet1": {"index": "1", "lanes": "1,3,5"},
        })
        assert cpoutil.get_cpo_laser_ids("Ethernet1") == ((0,), ())


class TestOeBankControls:
    @pytest.fixture
    def bank_cpos(self, monkeypatch):
        cpos = {1: CoverageFakeCpo(), 2: CoverageFakeCpo(), 3: CoverageFakeCpo()}
        data = json.loads(json.dumps(CPO_DATA))
        # A second interface in the same bank must not cause a duplicate write.
        data["interfaces"]["Ethernet4"] = dict(data["interfaces"]["Ethernet0"])
        monkeypatch.setattr(cpoutil, "cpo_mapping", CpoMapping(data))
        monkeypatch.setattr(cpoutil, "cpo_object_map", {
            OPTICAL_ENGINE: {"oe0": cpos[1], "oe1": cpos[3]},
            EXTERNAL_LASER_SOURCE: {"els0": cpos[1], "els1": cpos[3]},
            PORT: dict(cpos),
        })
        monkeypatch.setattr(cpoutil, "initialize_platform", lambda: None)
        return cpos

    @pytest.mark.parametrize("state,disabled", [("enable", True), ("disable", False)])
    def test_operates_once_per_bank_and_leaves_other_oes_alone(self, bank_cpos, state, disabled):
        result = invoke_coverage(["config", "oe", "tx_disable", "0", state])
        assert result.exit_code == 0, result.output
        assert bank_cpos[1].api.calls == [("tx_disable", disabled)]
        assert bank_cpos[2].api.calls == [("tx_disable", disabled)]
        assert bank_cpos[3].api.calls == []

    def test_missing_bank_is_detected_before_any_write(self, bank_cpos):
        del cpoutil.cpo_object_map[PORT][2]
        result = invoke_coverage(["config", "oe", "tx_disable", "0", "enable"])
        assert result.exit_code != 0
        assert "bank 1" in result.output
        assert all(not cpo.api.calls for cpo in bank_cpos.values())

    def test_unavailable_api_is_detected_before_any_write(self, bank_cpos):
        bank_cpos[2].api = None
        result = invoke_coverage(["config", "oe", "tx_disable", "0", "enable"])
        assert result.exit_code != 0
        assert "API is unavailable" in result.output
        assert bank_cpos[1].api.calls == []

    def test_failed_bank_does_not_report_success(self, bank_cpos, monkeypatch):
        monkeypatch.setattr(bank_cpos[2].api, "tx_disable", lambda disabled: False)
        result = invoke_coverage(["config", "oe", "tx_disable", "0", "enable"])
        assert result.exit_code != 0
        assert "oe0 bank 1 Tx-disable enable failed" in result.output
        assert "OK" not in result.output
