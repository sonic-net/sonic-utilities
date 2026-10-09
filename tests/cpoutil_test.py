import copy
import json
import os
import sys
import types
from unittest import mock

import click
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
        with pytest.raises(click.ClickException, match="Invalid port"):
            cpoutil.get_port_cpo_objects("Ethernet999")


class TestMappingCommand(object):
    def test_show_single_interface_as_json(self):
        cpoutil.cpo_mapping = CpoMapping(CPO_DATA)
        cpoutil.current_port_config = {
            "Ethernet8": {"index": "2", "lanes": "5,6,7,8"},
        }
        oe = mock.Mock()
        oe.oe.get_api.return_value.get_max_supported_banks.return_value = 8
        cpoutil.cpo_object_map = {OPTICAL_ENGINE: {"oe0": oe}, EXTERNAL_LASER_SOURCE: {}, PORT: {}}
        cpoutil.cpo_oe_bank_counts = {}
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


class TestOeLocalBank(object):
    """Interface and full-dump EEPROM access must use the declared OE bank."""

    @pytest.fixture
    def sparse_bank(self, coverage_environment, monkeypatch):
        def use_topology_bank(bank):
            data = copy.deepcopy(COVERAGE_CPO_DATA)
            data["interfaces"]["Ethernet0"]["oe_bank_id"] = bank
            cpoutil.cpo_mapping = CpoMapping(data, COVERAGE_PORT_CONFIG)
        monkeypatch.setattr(coverage_environment.api, "get_max_supported_banks", lambda: 8)
        return use_topology_bank

    @pytest.mark.parametrize("topology_bank", [4, 12])
    def test_sparse_or_global_bank_is_not_renumbered(self, coverage_environment, sparse_bank, topology_bank):
        # Only bank 4 of the OE is mapped; 12 is the same bank numbered across OEs.
        sparse_bank(topology_bank)
        mapping = cpoutil.cpo_mapping.get_interface("Ethernet0")
        assert cpoutil._local_oe_bank(mapping) == 4
        assert cpoutil._resource_banks(OPTICAL_ENGINE, "oe0") == [4]

        result = invoke_coverage(
            ["write-eeprom", "interface", "Ethernet0", "--oe", "-n", "0x10", "-o", "0x82", "-d", "ff"])
        assert result.exit_code == 0, result.output
        assert [offset for offset, _, _ in coverage_environment.writes] == [4 * 0x10000 + 0x10 * 0x100 + 0x82]

        coverage_environment.reads.clear()
        result = invoke_coverage(["read-eeprom", "interface", "Ethernet0", "--oe"])
        assert result.exit_code == 0, result.output
        assert "Upper page 10h bank 4h" in result.output
        assert "Upper page 10h bank 0h" not in result.output

    def test_map_reports_local_bank(self, coverage_environment, sparse_bank):
        sparse_bank(12)
        result = invoke_coverage(["show", "interface", "map", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["Ethernet0"]["oe"]["bank"] == 4

    def test_missing_oe_object_is_reported(self, coverage_environment):
        cpoutil.cpo_object_map[OPTICAL_ENGINE] = {}
        mapping = cpoutil.cpo_mapping.get_interface("Ethernet0")
        with pytest.raises(cpoutil.CpoCommandError, match="No CPO object"):
            cpoutil._local_oe_bank(mapping)


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
        from sonic_platform_base.sonic_xcvr.codes.public.elsfp import ElsfpCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.elsfp.elsfp import ElsfpMemMap

        super().__init__(None, self, self)
        self.api = CoverageFakeApi()
        self.api.xcvr_eeprom = mock.Mock(
            mem_map=ElsfpMemMap(ElsfpCodes), reader=self.read_eeprom,
        )
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


@pytest.fixture
def hooked(coverage_environment):
    """Give the coverage fake explicit CPO, OE and ELS hooks; its endpoints are itself."""
    for method in ("set_lpmode", "reset", "tx_disable"):
        setattr(coverage_environment, method, mock.Mock(return_value=True))
    coverage_environment.get_lpmode = mock.Mock(return_value=False)
    return coverage_environment


def invoke_coverage(arguments):
    return CliRunner().invoke(cpoutil.cli, arguments)


def command_paths(command, path=()):
    yield path
    for name, child in getattr(command, "commands", {}).items():
        yield from command_paths(child, path + (name,))


HARDWARE_COMMANDS = [
    ["show", "interface", name] for name in
    ("map", "presence", "dom", "tx_disable", "speed", "lane-status")
] + [
    ["show", "oe", name] for name in
    ("lpmode", "status", "temperature", "input-power")
] + [
    ["show", "els", name] for name in
    ("lpmode", "status", "temperature", "output-power")
] + [
    ["config", "interface", "tx_disable", "Ethernet0", "enable"],
    ["config", "interface", "lpmode", "Ethernet0", "low"],
    ["config", "interface", "reset", "Ethernet0"],
    ["config", "oe", "lpmode", "0", "full"],
    ["config", "oe", "reset", "0"],
    ["config", "els", "lpmode", "0", "full"],
    ["config", "els", "reset", "0"],
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
    @pytest.mark.parametrize("port_name", ["Ethernet999", "not-a-port"])
    def test_invalid_port_error_is_printed_once(self, coverage_environment, port_name):
        result = CliRunner().invoke(
            cpoutil.cli, ["show", "interface", "map", port_name]
        )
        assert result.exit_code != 0
        assert result.output.count("Invalid port '{}'".format(port_name)) == 1

    def test_port_and_lane_helpers(self, coverage_environment):
        assert cpoutil.get_cpo_interface_mapping("Ethernet0").physical_ports == (1,)
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
        assert cpoutil.get_cpo_presence(cpo, "Ethernet0")

        oe_api, els_api = object(), object()
        public_cpo = cpoutil.CpoBase(
            None, CoverageFakeEndpoint(oe_api), CoverageFakeEndpoint(els_api)
        )
        assert cpoutil.get_oe_api(public_cpo, "oe0") is oe_api
        assert cpoutil.get_els_api(public_cpo, "els0") is els_api
        with pytest.raises(cpoutil.CpoCommandError, match="CPO presence is not implemented"):
            cpoutil.get_cpo_presence(public_cpo, "Ethernet0")

    def test_normalizers_and_filters(self):
        assert cpoutil.get_els_lpmode(
            mock.Mock(get_elsfp_status=lambda: {"module_state": "ModuleLowPwr"})
        ) is True
        assert cpoutil.get_els_lpmode(
            mock.Mock(get_elsfp_status=lambda: {"module_state": "ModuleReady"})
        ) is False
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
        assert "Host Assign" in cpoutil.format_application_advertisement(
            advertisements
        )[0]
        assert cpoutil.format_application_advertisement("not-a-dict") == [
            "not-a-dict"
        ]
        info = {
            "manufacturer": "Vendor",
            "application_advertisement": advertisements,
            "cable_type": "Length(km)",
            "cable_length": 2,
            "supported_max_tx_power": 4,
            "supported_max_laser_freq": 195000,
            "max_laser_bias": 20,
        }
        assert any("Vendor" in line for line in cpoutil._format_cpo_info(info))
        dom = {
            "rx1power": 1.2,
            "txpowerhighalarm": 3.0,
            "temperature": 40.0,
            "temphighalarm": 90.0,
            "extra": {"nested": True},
        }
        lines = cpoutil._format_oe_dom(dom)
        assert any("AdditionalValues" in line for line in lines)
        assert "CPO EEPROM detected" in cpoutil._format_interface_dom(
            "Ethernet0", {"present": True,
                          "oe": {"info": None, "dom": None, "thresholds": None},
                          "els": {"info": None, "dom": None, "thresholds": None}}
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
            ["show", "interface", "presence"],
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
            ["config", "interface", "lpmode", "Ethernet0", "low"],
            ["config", "interface", "reset", "Ethernet0"],
            ["config", "oe", "lpmode", "0", "low"],
            ["config", "oe", "lpmode", "0", "full"],
            ["config", "oe", "reset", "0"],
            ["config", "els", "lpmode", "0", "low"],
            ["config", "els", "reset", "0"],
        ],
    )
    def test_config_commands(self, hooked, arguments):
        result = invoke_coverage(arguments)
        assert result.exit_code == 0, result.output
        assert "OK" in result.output
        # Configuration goes through the platform hooks, never the module APIs.
        assert hooked.api.calls == []
        assert not hooked.writes

    @pytest.mark.parametrize("arguments", [
        ["config", "oe", "tx_disable", "0", "enable"],
        ["config", "els", "tx_disable", "0", "enable"],
    ])
    def test_endpoint_tx_disable_commands_are_removed(self, hooked, arguments):
        result = invoke_coverage(arguments)
        assert result.exit_code != 0
        assert "No such command 'tx_disable'" in result.output
        hooked.tx_disable.assert_not_called()

    def test_oe_reset_reports_reprovisioning_requirement(self, hooked):
        result = invoke_coverage(["config", "oe", "reset", "0"])
        assert result.exit_code == 0, result.output
        assert "Resetting OE0 (Ethernet0) ... OK" in result.output
        assert "Affected ports may require application and datapath reprovisioning" in result.output
        hooked.reset.assert_called_once_with()
        assert hooked.api.calls == []
        assert not hooked.writes

    @pytest.mark.parametrize("unsupported", [False, True])
    def test_oe_reset_failure_is_reported(self, hooked, unsupported):
        hooked.reset.return_value = False
        if unsupported:
            hooked.reset.side_effect = NotImplementedError()
        result = invoke_coverage(["config", "oe", "reset", "0"])
        assert result.exit_code != 0
        assert "Resetting OE0 (Ethernet0) ... Failed" in result.output
        assert "reprovisioning" not in result.output
        error = "OE reset is not implemented for this platform" if unsupported else \
            "Resetting OE0 (Ethernet0) failed"
        assert error in result.output
        hooked.reset.assert_called_once_with()

    def test_oe_reset_help_describes_module_defaults(self):
        result = invoke_coverage(["config", "oe", "reset", "--help"])
        assert result.exit_code == 0, result.output
        help_text = " ".join(result.output.split())
        assert "Module settings may return to defaults" in help_text
        assert "application and datapath reprovisioning" in help_text

    def test_unimplemented_els_reset(self, hooked):
        hooked.reset.side_effect = NotImplementedError()
        result = invoke_coverage(["config", "els", "reset", "0"])
        assert result.exit_code != 0
        assert "ELS reset is not implemented for this platform" in result.output
        assert hooked.api.calls == []

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
        from sonic_platform_base.sonic_xcvr.codes.public.elsfp import ElsfpCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.elsfp.elsfp import (
            ElsfpMemMap,
        )

        coverage_environment.api.xcvr_eeprom = mock.Mock(
            mem_map=ElsfpMemMap(ElsfpCodes),
            reader=coverage_environment.read_eeprom,
        )
        for arguments in (
            ["read-eeprom", "interface", "Ethernet0", "--oe"],
            ["read-eeprom", "oe", "-i", "0"],
            ["read-eeprom", "els", "-i", "0"],
        ):
            result = invoke_coverage(arguments)
            assert result.exit_code == 0, result.output
            assert "EEPROM hexdump" in result.output
            if arguments[1] == "els":
                for page in ("0h", "1h", "2h", "1ah", "1bh", "2fh", "9fh"):
                    assert "Upper page {}".format(page) in result.output
                assert "Lower page 0h" in result.output

    def test_els_full_eeprom_uses_selected_memory_map(self, coverage_environment):
        from sonic_platform_base.sonic_xcvr.codes.public.elsfp import ElsfpCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.elsfp.elsfp import (
            ElsfpMemMap,
        )

        mem_map = ElsfpMemMap(ElsfpCodes)
        for index, page in enumerate(mem_map.pages):
            page._page = 0xB0 + index
        coverage_environment.api.xcvr_eeprom = mock.Mock(
            mem_map=mem_map,
            reader=coverage_environment.read_eeprom,
        )

        result = invoke_coverage(["read-eeprom", "els", "-i", "0"])
        assert result.exit_code == 0, result.output
        assert "Lower page b0h" in result.output
        assert "Upper page b7h" in result.output
        assert coverage_environment.reads == [
            (page.getaddr(0 if index == 0 else 128), 128)
            for index, page in enumerate(mem_map.pages)
        ]

    @pytest.mark.parametrize("page_offset", (0, 4))
    def test_els_dump_pairs_selected_pages_with_api_reader(
            self, coverage_environment, page_offset):
        from sonic_platform_base.sonic_xcvr.codes.public.elsfp import ElsfpCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.elsfp.elsfp import (
            ElsfpMemMap,
        )

        mem_map = ElsfpMemMap(ElsfpCodes)
        mem_map.pages = mem_map.pages[:3]
        for index, page in enumerate(mem_map.pages):
            page._page = 0xB0 + page_offset + index

        api_reads = []

        def api_reader(offset, size):
            api_reads.append((offset, size))
            return bytearray([0x41 + page_offset] * size)

        coverage_environment.api.xcvr_eeprom = mock.Mock(
            mem_map=mem_map, reader=api_reader,
        )
        coverage_environment.read_eeprom = mock.Mock(
            side_effect=AssertionError("ELS endpoint bypassed selected API reader")
        )

        result = invoke_coverage(["read-eeprom", "els", "-i", "0"])
        assert result.exit_code == 0, result.output
        assert "Lower page {:x}h".format(0xB0 + page_offset) in result.output
        assert "Upper page {:x}h".format(0xB2 + page_offset) in result.output
        assert api_reads == [
            (page.getaddr(0 if index == 0 else 128), 128)
            for index, page in enumerate(mem_map.pages)
        ]
        coverage_environment.read_eeprom.assert_not_called()

    def test_els_explicit_page_uses_selected_api_reader(self):
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages.page import (
            CmisPage,
        )

        reads = []

        def api_reader(offset, size):
            reads.append((offset, size))
            return bytes([0x42] * size)

        api = mock.Mock(xcvr_eeprom=mock.Mock(reader=api_reader))
        els = CoverageFakeEndpoint(api)
        els.read_eeprom = mock.Mock(
            side_effect=AssertionError("ELS endpoint bypassed selected API reader")
        )
        cpo = cpoutil.CpoBase(None, mock.Mock(), els)

        data = cpoutil._read_one_eeprom(
            EXTERNAL_LASER_SOURCE, "els1", cpo, 0, 0xB4, 0x80, 2
        )
        assert data == bytearray([0x42, 0x42])
        assert reads == [(CmisPage.linear_offset(0xB4, 0, 0x80), 2)]
        els.read_eeprom.assert_not_called()

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
    @pytest.mark.parametrize("case_sensitive, expected", [
        (False, ["lane1", "Lane2", "lane2", "Lane10"]),
        (True, ["Lane2", "Lane10", "lane1", "lane2"]),
    ])
    def test_natural_sort_case_sensitivity(self, case_sensitive, expected):
        names = ["Lane10", "lane1", "Lane2", "lane2"]
        assert sorted(
            names, key=lambda name: cpoutil._natural_sort_key(name, case_sensitive)
        ) == expected
        assert cpoutil._natural_sort_key("Lane2") == cpoutil._natural_sort_key("lane2")

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

    def test_only_cpo_presence_is_read(self):
        oe = mock.Mock(get_presence=mock.Mock(return_value=True))
        els = mock.Mock(get_presence=mock.Mock(return_value=False))
        cpo = cpoutil.CpoBase(None, oe, els)
        cpo.get_presence = mock.Mock(return_value=True)
        assert cpoutil.get_cpo_presence(cpo, "Ethernet0") is True
        cpo.get_presence.assert_called_once_with()
        oe.get_presence.assert_not_called()
        els.get_presence.assert_not_called()
        assert cpoutil.get_els_api(cpo, "els0") is els.get_api.return_value


class HookEndpoint(CoverageFakeEndpoint):
    """OE or ELS endpoint double with its own low-power and reset hooks."""

    def __init__(self, api):
        super().__init__(api)
        self.set_lpmode = mock.Mock(return_value=True)
        self.reset = mock.Mock(return_value=True)


class TestOptionalElsApis:
    @staticmethod
    def install(monkeypatch, cpo):
        monkeypatch.setattr(cpoutil, "cpo_object_map", {
            OPTICAL_ENGINE: {"oe0": cpo},
            EXTERNAL_LASER_SOURCE: {"els0": cpo}, PORT: {1: cpo},
        })

    @pytest.mark.parametrize("command, endpoint, method, args", [
        (["config", "oe", "lpmode", "0", "low"], "oe", "set_lpmode", (True,)),
        (["config", "oe", "lpmode", "0", "full"], "oe", "set_lpmode", (False,)),
        (["config", "oe", "reset", "0"], "oe", "reset", ()),
        (["config", "els", "lpmode", "0", "low"], "elsfp", "set_lpmode", (True,)),
        (["config", "els", "reset", "0"], "elsfp", "reset", ()),
    ])
    def test_endpoint_commands_call_only_the_selected_endpoint_hook(
            self, coverage_environment, monkeypatch, command, endpoint, method, args):
        oe_api, els_api = CoverageFakeApi(), CoverageFakeApi()
        oe, els = HookEndpoint(oe_api), HookEndpoint(els_api)
        cpo = cpoutil.CpoBase(None, oe, els)
        self.install(monkeypatch, cpo)
        result = invoke_coverage(command)
        assert result.exit_code == 0, result.output
        selected, other = (oe, els) if endpoint == "oe" else (els, oe)
        getattr(selected, method).assert_called_once_with(*args)
        other.set_lpmode.assert_not_called()
        other.reset.assert_not_called()
        assert oe_api.calls == [] and els_api.calls == []

    @pytest.mark.parametrize("command, label, method", [
        (["config", "oe", "lpmode", "0", "low"], "OE", "set_lpmode"),
        (["config", "oe", "reset", "0"], "OE", "reset"),
        (["config", "els", "lpmode", "0", "low"], "ELS", "set_lpmode"),
        (["config", "els", "reset", "0"], "ELS", "reset"),
    ])
    @pytest.mark.parametrize("unsupported", ["missing", "not_implemented"])
    def test_endpoint_commands_are_unsupported_by_default(
            self, coverage_environment, monkeypatch, command, label, method, unsupported):
        # Joint-mode platforms do not implement the endpoint hooks; older
        # platform-common packages do not declare them at all.
        oe_api, els_api = CoverageFakeApi(), CoverageFakeApi()
        if unsupported == "missing":
            oe, els = CoverageFakeEndpoint(oe_api), CoverageFakeEndpoint(els_api)
        else:
            oe, els = HookEndpoint(oe_api), HookEndpoint(els_api)
            for endpoint in (oe, els):
                getattr(endpoint, method).side_effect = NotImplementedError()
        self.install(monkeypatch, cpoutil.CpoBase(None, oe, els))
        result = invoke_coverage(command)
        assert result.exit_code != 0
        assert "{} {} is not implemented for this platform".format(label, method) in result.output
        assert "OK" not in result.output
        assert oe_api.calls == [] and els_api.calls == []

    @pytest.mark.parametrize("command", [
        ["config", "els", "lpmode", "0", "low"],
        ["config", "els", "lpmode", "0", "full"],
        ["config", "els", "reset", "0"],
    ])
    def test_public_elsfp_api_controls_are_never_called(self, coverage_environment, monkeypatch, command):
        from sonic_platform_base.sonic_xcvr.api.public.elsfp import ElsfpApi
        from sonic_platform_base.sonic_xcvr.fields import consts

        eeprom = mock.Mock()
        eeprom.read.side_effect = lambda field: "ModuleReady" if field == consts.MODULE_STATE else 0
        els_api = ElsfpApi(eeprom)
        cpo = cpoutil.CpoBase(None, CoverageFakeEndpoint(CoverageFakeApi()), CoverageFakeEndpoint(els_api))
        self.install(monkeypatch, cpo)
        status = invoke_coverage(["show", "els", "status", "0", "--json"])
        assert status.exit_code == 0, status.output
        assert json.loads(status.output) == {"els0": "ModuleReady"}
        result = invoke_coverage(command)
        assert result.exit_code != 0
        assert "not implemented for this platform" in result.output
        eeprom.write.assert_not_called()

    @pytest.mark.parametrize("arguments", [
        ["show", "els", "status", "0"],
        ["show", "interface", "lane-status", "Ethernet0"],
    ])
    def test_unsupported_els_reads_do_not_change_oe(
            self, coverage_environment, monkeypatch, arguments):
        els_api = CoverageFakeApi()
        for method in ("get_module_state", "get_per_lane_state"):
            monkeypatch.setattr(els_api, method, mock.Mock(
                side_effect=NotImplementedError("ELS operation is not implemented")))
        oe_api = CoverageFakeApi()
        self.install(monkeypatch, cpoutil.CpoBase(
            None, CoverageFakeEndpoint(oe_api), CoverageFakeEndpoint(els_api)))
        result = invoke_coverage(arguments)
        assert result.exit_code != 0
        assert "not implemented" in result.output
        assert "has no attribute" not in result.output
        assert oe_api.calls == [] and els_api.calls == []

    def test_els_module_state_read_failure_is_not_reported_as_success(self, coverage_environment):
        cpo = cpoutil.cpo_object_map[EXTERNAL_LASER_SOURCE]["els0"]
        cpo.api.get_module_state = mock.Mock(return_value=None)
        result = invoke_coverage(["show", "els", "status", "0", "--json"])
        assert result.exit_code != 0
        assert "module state API returned no data" in result.output

    def test_public_eeprom_uses_the_selected_endpoint(self, coverage_environment, monkeypatch):
        oe = CoverageFakeCpo()
        els = CoverageFakeCpo()
        cpo = cpoutil.CpoBase(None, oe, els)
        monkeypatch.setattr(cpoutil, "cpo_object_map", {
            OPTICAL_ENGINE: {"oe0": cpo}, EXTERNAL_LASER_SOURCE: {"els0": cpo}, PORT: {1: cpo}})
        for resource_type, endpoint in ((OPTICAL_ENGINE, oe), (EXTERNAL_LASER_SOURCE, els)):
            cpoutil._read_one_eeprom(resource_type, "{}0".format(resource_type), cpo, 0, 0, 0, 2)
            cpoutil._write_resource_eeprom(resource_type, "0", 0, 0, 0, bytearray([1, 2]))
            assert len(endpoint.reads) == len(endpoint.writes) == 1

    def test_public_els_range_uses_physical_page_without_base_mapping(self):
        cpo = cpoutil.CpoBase(None, mock.Mock(), mock.Mock())
        assert cpoutil._eeprom_linear_offset(
            EXTERNAL_LASER_SOURCE, "els0", cpo, 0, 0xB2, 0x80
        ) == 0xB2 * 128 + 0x80


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

    def test_shared_laser_across_banks_is_reported(self, monkeypatch, coverage_environment):
        data = json.loads(json.dumps(COMMUNITY_DATA))
        data["devices"]["els0"]["laser_to_asic_lane_mapping"] = {
            "1": [1, 3], "2": [2], "3": [4],
        }
        self.configure(monkeypatch, data, COVERAGE_PORT_CONFIG)
        assert cpoutil.get_cpo_laser_ids("Ethernet0") == ((0, 1), (0,))

    def test_shared_laser_within_bank_is_reported(self, monkeypatch, coverage_environment):
        self.configure(monkeypatch, self.nonuniform_topology(), {
            "Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"},
            "Ethernet1": {"index": "1", "lanes": "1,3"},
        })
        assert cpoutil.get_cpo_laser_ids("Ethernet1") == ((0,), (0,))

    def test_breakout_without_lane_mapping_cannot_resolve_lasers(self, monkeypatch, coverage_environment):
        self.configure(monkeypatch, COVERAGE_CPO_DATA, {
            "Ethernet0": {"index": "1", "lanes": "1,2"},
            "Ethernet1": {"index": "1", "lanes": "2"},
        })
        assert cpoutil.get_cpo_laser_ids("Ethernet0") == ((0, 1), ())
        with pytest.raises(cpoutil.CpoLaserResolutionError, match="laser_to_asic_lane_mapping"):
            cpoutil.get_cpo_laser_ids("Ethernet1")

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


@pytest.fixture
def bank_cpos(monkeypatch):
    cpos = {1: CoverageFakeCpo(), 2: CoverageFakeCpo(), 3: CoverageFakeCpo()}
    data = json.loads(json.dumps(CPO_DATA))
    # A second interface in the same bank must not duplicate reads or writes.
    data["interfaces"]["Ethernet4"] = dict(data["interfaces"]["Ethernet0"])
    monkeypatch.setattr(cpoutil, "cpo_mapping", CpoMapping(data))
    monkeypatch.setattr(cpoutil, "cpo_object_map", {
        OPTICAL_ENGINE: {"oe0": cpos[1], "oe1": cpos[3]},
        EXTERNAL_LASER_SOURCE: {"els0": cpos[1], "els1": cpos[3]},
        PORT: dict(cpos),
    })
    monkeypatch.setattr(cpoutil, "initialize_platform", lambda: None)
    for port, cpo in cpos.items():
        cpo.api.get_rx_power = mock.Mock(return_value=[port + lane / 10 for lane in range(8)])
    return cpos


class TestOeInputPower:
    @pytest.mark.parametrize("selector", [[], ["0"], ["oe0"]])
    def test_reads_each_bank_once_and_preserves_oe_ownership(self, bank_cpos, selector):
        result = invoke_coverage(["show", "oe", "input-power", *selector, "--json"])
        assert result.exit_code == 0, result.output
        expected = {"oe0": {
            "bank_0": bank_cpos[1].api.get_rx_power.return_value,
            "bank_1": bank_cpos[2].api.get_rx_power.return_value,
        }}
        if not selector:
            expected["oe1"] = {"bank_0": bank_cpos[3].api.get_rx_power.return_value}
            bank_cpos[3].api.get_rx_power.assert_called_once_with()
        else:
            bank_cpos[3].api.get_rx_power.assert_not_called()
        assert json.loads(result.output) == expected
        bank_cpos[1].api.get_rx_power.assert_called_once_with()
        bank_cpos[2].api.get_rx_power.assert_called_once_with()

    def test_table_identifies_each_bank_and_its_local_media_lanes(self, bank_cpos):
        result = invoke_coverage(["show", "oe", "input-power", "0"])
        assert result.exit_code == 0, result.output
        assert "Bank / Media Lane" in result.output
        for bank, port in [(0, 1), (1, 2)]:
            for lane, power in enumerate(bank_cpos[port].api.get_rx_power.return_value, 1):
                assert "OE0 bank {} / Lane {} {:g}".format(bank, lane, power) in [
                    " ".join(line.split()) for line in result.output.splitlines()
                ]

    def test_preserves_nonzero_topology_bank_ids(self, bank_cpos, monkeypatch):
        data = json.loads(json.dumps(CPO_DATA))
        data["interfaces"]["Ethernet0"]["oe_bank_id"] = 56
        data["interfaces"]["Ethernet8"]["oe_bank_id"] = 63
        monkeypatch.setattr(cpoutil, "cpo_mapping", CpoMapping(data))
        result = invoke_coverage(["show", "oe", "input-power", "0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"oe0": {
            "bank_56": bank_cpos[1].api.get_rx_power.return_value,
            "bank_63": bank_cpos[2].api.get_rx_power.return_value,
        }}

    @pytest.mark.parametrize("json_option", [[], ["--json"]])
    @pytest.mark.parametrize("missing", ["object", "api"])
    def test_missing_bank_fails_without_partial_output(self, bank_cpos, json_option, missing):
        if missing == "object":
            del cpoutil.cpo_object_map[PORT][2]
        else:
            bank_cpos[2].api = None
        result = invoke_coverage(["show", "oe", "input-power", "0", *json_option])
        assert result.exit_code != 0
        assert "oe0" in result.output and "bank 1" in result.output
        assert "Input Power (mW)" not in result.output
        assert "bank_0" not in result.output
        bank_cpos[1].api.get_rx_power.assert_not_called()

    @pytest.mark.parametrize("values", [None, [], {}])
    def test_empty_bank_read_is_reported_as_failure(self, bank_cpos, values):
        bank_cpos[2].api.get_rx_power.return_value = values
        result = invoke_coverage(["show", "oe", "input-power", "0", "--json"])
        assert result.exit_code != 0
        assert "oe0 bank 1 input-power API returned no lane data" in result.output
        assert "bank_0" not in result.output

    @pytest.mark.parametrize("error", [NotImplementedError("unsupported"), AttributeError("missing")])
    def test_bank_read_error_is_reported_with_bank_context(self, bank_cpos, error):
        bank_cpos[2].api.get_rx_power.side_effect = error
        result = invoke_coverage(["show", "oe", "input-power", "0", "--json"])
        assert result.exit_code != 0
        assert "oe0 bank 1 input-power read failed" in result.output
        assert "bank_0" not in result.output


VMODULE_PORT_CONFIG = {
    "Ethernet0": {"index": "1", "lanes": "1,2,3,4"},
    "Ethernet4": {"index": "1", "lanes": "1,2,3,4"},
    "Ethernet8": {"index": "2", "lanes": "5,6,7,8"},
    "Ethernet16": {"index": "3", "lanes": "9,10,11,12"},
}


@pytest.fixture
def vmodules(bank_cpos, monkeypatch):
    # OE0 serves Ethernet0 and its breakout sibling Ethernet4 (physical port 1)
    # and Ethernet8 (port 2); OE1 serves Ethernet16 (port 3). The fakes define
    # their own controls instead of relying on CpoBase defaults.
    monkeypatch.setattr(cpoutil, "current_port_config", dict(VMODULE_PORT_CONFIG))
    for port, cpo in bank_cpos.items():
        cpo.get_lpmode = mock.Mock(return_value=port == 3)
        cpo.set_lpmode = mock.Mock(return_value=True)
        cpo.reset = mock.Mock(return_value=True)
        cpo.tx_disable = mock.Mock(return_value=True)
    return bank_cpos


class TestVmoduleControls:
    def test_show_lpmode_per_interface(self, vmodules):
        result = invoke_coverage(["show", "interface", "lpmode", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {
            "Ethernet0": False, "Ethernet4": False, "Ethernet8": False, "Ethernet16": True,
        }
        table = invoke_coverage(["show", "interface", "lpmode", "Ethernet16"])
        assert table.exit_code == 0, table.output
        assert "Ethernet16" in table.output and "On" in table.output

    def test_show_lpmode_rejects_unavailable_state(self, vmodules):
        vmodules[2].get_lpmode.return_value = None
        result = invoke_coverage(["show", "interface", "lpmode", "Ethernet8"])
        assert result.exit_code != 0
        assert "unavailable for 'Ethernet8'" in result.output

    def test_dedicated_controller(self, vmodules):
        result = invoke_coverage(["config", "interface", "lpmode", "Ethernet16", "low"])
        assert result.exit_code == 0, result.output
        assert "Enabling low-power mode for OE1 (Ethernet16) ... OK" in result.output
        vmodules[3].set_lpmode.assert_called_once_with(True)
        vmodules[1].set_lpmode.assert_not_called()

    @pytest.mark.parametrize("ports", ["Ethernet8", "Ethernet4", "Ethernet0,Ethernet4,Ethernet8"])
    def test_one_port_controls_its_controller_once(self, vmodules, ports):
        result = invoke_coverage(["config", "interface", "lpmode", ports, "low"])
        assert result.exit_code == 0, result.output
        assert "Enabling low-power mode for OE0 (Ethernet0, Ethernet4, Ethernet8) ... OK" in result.output
        calls = [cpo.set_lpmode.call_args_list for cpo in vmodules.values()]
        assert sum(len(call) for call in calls) == 1
        assert mock.call(True) in calls[0] + calls[1]
        vmodules[3].set_lpmode.assert_not_called()

    @pytest.mark.parametrize("command", [["lpmode", "Ethernet8", "low"], ["reset", "Ethernet8"]])
    def test_all_ports_option_is_removed(self, vmodules, command):
        result = invoke_coverage(["config", "interface"] + command + ["--all-ports"])
        assert result.exit_code != 0
        assert "No such option" in result.output
        for cpo in vmodules.values():
            cpo.set_lpmode.assert_not_called()
            cpo.reset.assert_not_called()

    @pytest.mark.parametrize("port", ["Ethernet0", "Ethernet4"])
    def test_tx_disable_acts_on_the_port_cpo_object(self, vmodules, port):
        result = invoke_coverage(["config", "interface", "tx_disable", port, "enable"])
        assert result.exit_code == 0, result.output
        # Breakout subports share the physical port's CPO object.
        assert "Enabling Tx-disable for Ethernet0 (Ethernet0, Ethernet4) ... OK" in result.output
        vmodules[1].tx_disable.assert_called_once_with(True)
        vmodules[2].tx_disable.assert_not_called()
        vmodules[3].tx_disable.assert_not_called()
        assert all(cpo.api.calls == [] for cpo in vmodules.values())

    def test_tx_disable_calls_each_cpo_object_once(self, vmodules):
        result = invoke_coverage(
            ["config", "interface", "tx_disable", "Ethernet0,Ethernet4,Ethernet8", "disable"])
        assert result.exit_code == 0, result.output
        assert "Disabling Tx-disable for Ethernet0 (Ethernet0, Ethernet4) ... OK" in result.output
        assert "Disabling Tx-disable for Ethernet8 (Ethernet8) ... OK" in result.output
        vmodules[1].tx_disable.assert_called_once_with(False)
        vmodules[2].tx_disable.assert_called_once_with(False)
        vmodules[3].tx_disable.assert_not_called()

    def test_tx_disable_partial_failure_names_completed_targets(self, vmodules):
        vmodules[3].tx_disable.return_value = False
        result = invoke_coverage(["config", "interface", "tx_disable", "Ethernet0,Ethernet16", "enable"])
        assert result.exit_code != 0
        assert "Enabling Tx-disable for Ethernet0 (Ethernet0, Ethernet4) ... OK" in result.output
        assert "Enabling Tx-disable for Ethernet16 (Ethernet16) ... Failed" in result.output
        assert "already applied to Ethernet0" in result.output

    def test_reset_reports_ports_to_reprovision(self, vmodules):
        result = invoke_coverage(["config", "interface", "reset", "Ethernet16"])
        assert result.exit_code == 0, result.output
        assert "Resetting OE1 (Ethernet16) ... OK" in result.output
        assert "Re-provision the affected ports (admin toggle): Ethernet16" in result.output
        vmodules[3].reset.assert_called_once_with()

    @pytest.mark.parametrize("command", [
        ["config", "interface", "lpmode", "Ethernet16", "low"],
        ["config", "interface", "reset", "Ethernet16"],
        ["config", "interface", "tx_disable", "Ethernet16", "enable"],
        ["show", "interface", "lpmode", "Ethernet16"],
    ])
    @pytest.mark.parametrize("unsupported", ["missing", "not_implemented"])
    def test_unsupported_platform(self, vmodules, command, unsupported):
        method = {"lpmode": "set_lpmode", "reset": "reset", "tx_disable": "tx_disable"}[command[2]] \
            if command[0] == "config" else "get_lpmode"
        if unsupported == "missing":
            cpoutil.cpo_object_map[PORT][3] = types.SimpleNamespace()
        else:
            getattr(vmodules[3], method).side_effect = NotImplementedError()
        result = invoke_coverage(command)
        assert result.exit_code != 0
        assert "CPO {} is not implemented for this platform".format(method) in result.output
        assert "Re-provision" not in result.output

    def test_failed_control_is_reported(self, vmodules):
        vmodules[3].set_lpmode.return_value = False
        result = invoke_coverage(["config", "interface", "lpmode", "Ethernet16", "low"])
        assert result.exit_code != 0
        assert "OE1 (Ethernet16) ... Failed" in result.output

    def test_partial_failure_names_completed_controllers(self, vmodules):
        vmodules[3].set_lpmode.return_value = False
        result = invoke_coverage(
            ["config", "interface", "lpmode", "Ethernet0,Ethernet4,Ethernet8,Ethernet16", "low"])
        assert result.exit_code != 0
        assert "OE0 (Ethernet0, Ethernet4, Ethernet8) ... OK" in result.output
        assert "already applied to OE0" in result.output


class TestEepromPageOffset:
    """Offsets below 128 on a nonzero page alias the previous page's upper half."""

    @pytest.mark.parametrize("arguments", [
        ["read-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0x11", "-o", "2", "-s", "1"],
        ["read-eeprom", "els", "-i", "0", "-n", "0x1a", "-o", "0x7f", "-s", "1"],
        ["read-eeprom", "interface", "Ethernet0", "--oe", "-n", "0x11", "-o", "2", "-s", "1"],
        ["write-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0x11", "-o", "2", "-d", "ff"],
        ["write-eeprom", "els", "-i", "0", "-n", "0x1a", "-o", "0x7f", "-d", "ff"],
        ["write-eeprom", "interface", "Ethernet0", "--oe", "-n", "0x11", "-o", "2", "-d", "ff"],
    ])
    def test_lower_offset_on_nonzero_page_is_rejected(self, coverage_environment, arguments):
        page = int(arguments[arguments.index("-n") + 1], 0)
        result = invoke_coverage(arguments)
        assert result.exit_code != 0
        assert "valid range: 80h-FFh" in result.output
        assert "for page {:x}h".format(page) in result.output
        assert coverage_environment.reads == []
        assert coverage_environment.writes == []

    def test_page_11_offset_2_never_reaches_tx_disable(self, coverage_environment, monkeypatch):
        # With real CMIS addressing, page 0x11 offset 2 equals page 0x10 offset 130.
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages.page import CmisPage
        monkeypatch.setattr(
            cpoutil, "_eeprom_linear_offset",
            lambda resource_type, resource_id, obj, bank, page, offset:
            CmisPage.linear_offset(page, bank, offset))
        assert CmisPage.linear_offset(0x11, 0, 2) == CmisPage.linear_offset(0x10, 0, 130)
        result = invoke_coverage(
            ["write-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0x11", "-o", "2", "-d", "ff"])
        assert result.exit_code != 0
        assert coverage_environment.writes == []

    @pytest.mark.parametrize("arguments", [
        ["read-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0", "-o", "2", "-s", "1"],
        ["read-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0x11", "-o", "0x80", "-s", "1"],
        ["write-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0", "-o", "2", "-d", "ff"],
        ["write-eeprom", "oe", "-i", "0", "-b", "0", "-n", "0x11", "-o", "0x80", "-d", "ff"],
    ])
    def test_page_zero_and_upper_offsets_are_accepted(self, coverage_environment, arguments):
        result = invoke_coverage(arguments)
        assert result.exit_code == 0, result.output


class TestDuplicateAssociations:
    @pytest.mark.parametrize("device_type, message", [
        ("optical_engine", "more than one OE"),
        ("external_laser_source", "more than one ELS"),
    ])
    def test_second_association_of_a_type_is_rejected(self, device_type, message):
        data = copy.deepcopy(COMMUNITY_DATA)
        existing, extra = ("oe0", "oe1") if device_type == "optical_engine" else ("els0", "els1")
        data["devices"][extra] = dict(data["devices"][existing])
        data["interfaces"]["Ethernet0"]["associated_devices"].append({"device_id": extra, "bank": 0})
        with pytest.raises(CpoMappingError, match=message):
            CpoMapping(data, COVERAGE_PORT_CONFIG)


class TestGangedPorts:
    @pytest.fixture
    def ganged(self, coverage_environment, monkeypatch):
        # Ethernet0 is ganged across physical ports 1 and 2.
        monkeypatch.setattr(cpoutil, "current_port_config", {"Ethernet0": {"index": "1,2", "lanes": "1,2"}})
        cpoutil.cpo_object_map[PORT][2] = coverage_environment
        return coverage_environment

    @pytest.mark.parametrize("command", ["tx_disable", "speed", "lane-status"])
    def test_all_port_commands_use_the_logical_port(self, ganged, command):
        result = invoke_coverage(["show", "interface", command, "--json"])
        assert result.exit_code == 0, result.output
        assert set(json.loads(result.output)) == {"Ethernet0:1 (ganged)", "Ethernet0:2 (ganged)"}

    def test_entries_keep_the_logical_port(self, ganged):
        entries = cpoutil.get_port_cpo_entries()
        assert [(name, physical, logical) for name, physical, _, logical in entries] == [
            ("Ethernet0:1 (ganged)", 1, "Ethernet0"),
            ("Ethernet0:2 (ganged)", 2, "Ethernet0"),
        ]
        assert [entry[:3] for entry in entries] == cpoutil.get_port_cpo_objects()


class TestInterfaceElsEepromBank:
    @pytest.fixture
    def community(self, coverage_environment):
        # Ethernet0 is associated with ELS bank 2 in the community topology.
        cpoutil.cpo_mapping = CpoMapping(COMMUNITY_DATA, COVERAGE_PORT_CONFIG)
        assert cpoutil.cpo_mapping.get_interface("Ethernet0").els_bank == 2
        return coverage_environment

    def test_read_uses_bank_zero(self, community):
        result = invoke_coverage(
            ["read-eeprom", "interface", "Ethernet0", "--els", "-n", "0x1a", "-o", "0x80", "-s", "2"])
        assert result.exit_code == 0, result.output
        assert community.reads == [(0x1a * 0x100 + 0x80, 2)]

    def test_write_uses_bank_zero(self, community):
        result = invoke_coverage(
            ["write-eeprom", "interface", "Ethernet0", "--els", "-n", "0x1a", "-o", "0x80", "-d", "01"])
        assert result.exit_code == 0, result.output
        assert [offset for offset, _, _ in community.writes] == [0x1a * 0x100 + 0x80]


class TestLaneStatusLaserAssociation:
    """Each displayed OE lane must show the laser the topology associates with it."""

    # Laser states chosen so that any wrong pairing changes the displayed state.
    LASER_STATES = {"LaneState1": "Active", "LaneState2": "Inactive", "LaneState3": "Disabled"}

    @pytest.fixture
    def nonuniform(self, coverage_environment, monkeypatch):
        # laser 0 -> ASIC lanes 1, 3, 5; laser 1 -> lane 2; laser 2 -> lanes 4, 6
        TestExplicitLaserMapping.configure(
            monkeypatch, TestExplicitLaserMapping.nonuniform_topology(),
            {"Ethernet0": {"index": "1", "lanes": "1,2,3,4,5,6"}})
        api = coverage_environment.api
        monkeypatch.setattr(api, "get_datapath_state", lambda: ["DataPathActivated"] * 6, raising=False)
        monkeypatch.setattr(api, "get_per_lane_state", lambda: dict(self.LASER_STATES), raising=False)
        return coverage_environment

    EXPECTED = [  # (lane position, laser, state)
        (0, 0, "Active"), (1, 1, "Inactive"), (2, 0, "Active"),
        (3, 2, "Disabled"), (4, 0, "Active"), (5, 2, "Disabled"),
    ]

    def test_json_carries_the_topology_association(self, nonuniform):
        result = invoke_coverage(["show", "interface", "lane-status", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        record = json.loads(result.output)["Ethernet0"]
        assert record["Lane Lasers"] == {
            "lane{:02d}".format(position): laser for position, laser, _ in self.EXPECTED
        }

    def test_table_shows_the_correct_laser_and_state_in_every_row(self, nonuniform):
        result = invoke_coverage(["show", "interface", "lane-status", "Ethernet0"])
        assert result.exit_code == 0, result.output
        rows = [line.split() for line in result.output.splitlines() if line.startswith("Ethernet0")]
        lane_rows = [row for row in rows if "DataPathActivated" in row]
        assert len(lane_rows) == len(self.EXPECTED)
        for row, (_, laser, state) in zip(lane_rows, self.EXPECTED):
            # Columns end with: ELS, Laser, ELS Lane State, Shared
            assert row[-4:] == ["ELS0", str(laser), state, "No"], row
        assert "per-lane association unavailable" not in result.output

    def test_asic_lane_ids_differ_from_lane_positions(self, monkeypatch, coverage_environment):
        data = TestExplicitLaserMapping.nonuniform_topology()
        data["devices"]["oe0"]["asic_lanes"] = [33, 34, 35, 36]
        data["devices"]["els0"]["laser_to_asic_lane_mapping"] = {"1": [33, 35], "2": [34, 36]}
        TestExplicitLaserMapping.configure(
            monkeypatch, data, {"Ethernet0": {"index": "1", "lanes": "33,34,35,36"}})
        context = cpoutil.get_interface_context("Ethernet0")
        assert cpoutil._lane_lasers(context) == {"lane00": 0, "lane01": 1, "lane02": 0, "lane03": 1}

    def test_no_explicit_mapping_is_not_guessed(self, coverage_environment, monkeypatch):
        # The legacy topology lists the interface's lasers [0, 1] without a lane mapping.
        api = coverage_environment.api
        monkeypatch.setattr(api, "get_datapath_state", lambda: ["DataPathActivated"] * 2, raising=False)
        monkeypatch.setattr(api, "get_per_lane_state",
                            lambda: {"LaneState1": "Active", "LaneState2": "Inactive"}, raising=False)
        result = invoke_coverage(["show", "interface", "lane-status", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["Ethernet0"]["Lane Lasers"] == {"lane00": None, "lane01": None}

        table = invoke_coverage(["show", "interface", "lane-status", "Ethernet0"])
        assert table.exit_code == 0, table.output
        lane_rows = [line.split() for line in table.output.splitlines()
                     if line.startswith("Ethernet0") and "DataPathActivated" in line]
        assert lane_rows and all(row[-3:] == ["N/A", "N/A", "N/A"] for row in lane_rows)
        assert "per-lane association unavailable" in table.output
        assert "0: Active, 1: Inactive" in table.output


class TestBreakoutWithoutLaneMapping:
    """Display commands show unresolved lasers instead of aborting; controls still reject."""

    PORTS = {
        "Ethernet0": {"index": "1", "lanes": "1"},
        "Ethernet1": {"index": "1", "lanes": "2"},
    }

    @pytest.fixture
    def breakout(self, coverage_environment, monkeypatch):
        TestExplicitLaserMapping.configure(monkeypatch, COVERAGE_CPO_DATA, self.PORTS)
        api = coverage_environment.api
        monkeypatch.setattr(api, "get_datapath_state", lambda: ["DataPathActivated"] * 2, raising=False)
        monkeypatch.setattr(api, "get_per_lane_state",
                            lambda: {"LaneState1": "Active", "LaneState2": "Inactive"}, raising=False)
        return coverage_environment

    def test_map_lists_every_port_with_unresolved_lasers(self, breakout):
        result = invoke_coverage(["show", "interface", "map", "--json"])
        assert result.exit_code == 0, result.output
        records = json.loads(result.output)
        assert sorted(records) == ["Ethernet0", "Ethernet1"]
        assert records["Ethernet0"]["oe"]["lanes"] == [1]
        assert records["Ethernet1"]["oe"]["lanes"] == [2]
        assert all(record["els"]["lasers"] is None for record in records.values())

        table = invoke_coverage(["show", "interface", "map", "Ethernet1"])
        assert table.exit_code == 0, table.output
        assert cpoutil.UNRESOLVED_LASERS in table.output

    def test_lane_status_shows_no_guessed_laser_state(self, breakout):
        result = invoke_coverage(["show", "interface", "lane-status", "Ethernet1", "--json"])
        assert result.exit_code == 0, result.output
        record = json.loads(result.output)["Ethernet1"]
        assert record["Data Path State Indicator"] == {"lane01": "DataPathActivated"}
        assert record["ELS Lasers"] is None
        assert record["ELS Lane State"] == {}
        assert record["Lane Lasers"] == {"lane01": None}

        table = invoke_coverage(["show", "interface", "lane-status"])
        assert table.exit_code == 0, table.output
        lane_rows = [line.split() for line in table.output.splitlines()
                     if line.startswith("Ethernet") and "DataPathActivated" in line]
        assert [row[0] for row in lane_rows] == ["Ethernet0", "Ethernet1"]
        assert all(row[-3:] == ["N/A", "N/A", "N/A"] for row in lane_rows)
        assert table.output.count(cpoutil.UNRESOLVED_LASERS) == 2

    def test_full_port_on_same_topology_still_resolves_lasers(self, coverage_environment, monkeypatch):
        TestExplicitLaserMapping.configure(
            monkeypatch, COVERAGE_CPO_DATA, {"Ethernet0": {"index": "1", "lanes": "1,2"}})
        result = invoke_coverage(["show", "interface", "map", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["Ethernet0"]["els"]["lasers"] == [0, 1]

    def test_tx_disable_uses_the_cpo_object_without_laser_mapping(self, breakout, monkeypatch):
        monkeypatch.setattr(breakout, "tx_disable", mock.Mock(return_value=True), raising=False)
        result = invoke_coverage(["config", "interface", "tx_disable", "Ethernet1", "enable"])
        assert result.exit_code == 0, result.output
        assert "Enabling Tx-disable for Ethernet0 (Ethernet0, Ethernet1) ... OK" in result.output
        breakout.tx_disable.assert_called_once_with(True)
        assert breakout.api.calls == []
