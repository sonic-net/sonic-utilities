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


CPO_DATA = {
    "cpo_eeprom_mode": "joint",
    "oes": {
        "oe0": {"index": 0, "oe_cmis_path": "/sys/oe0/"},
        "oe1": {"index": 1, "oe_cmis_path": "/sys/oe1/"},
    },
    "elss": {
        "els0": {"index": 0, "base_page": 0},
        "els1": {"index": 1, "base_page": 4},
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


class FakeCpo(object):
    def __init__(self, name):
        self.name = name

    def get_xcvr_api(self):
        return self


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


class CoverageFakeApi(object):
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
            "els_legacy": "drop",
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

    def set_elsfp_lpmode(self, value):
        self.calls.append(("set_elsfp_lpmode", value))
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


class CoverageFakeCpo(object):
    def __init__(self):
        self.api = CoverageFakeApi()
        self.reads = []
        self.writes = []

    def get_xcvr_api(self):
        return self.api

    def get_presence(self):
        return True

    def get_els_presence(self):
        return True

    def get_els_base_page(self):
        return 0

    def read_eeprom(self, offset, size):
        self.reads.append((offset, size))
        return bytearray((index % 256 for index in range(size)))

    def write_eeprom(self, offset, size, data):
        self.writes.append((offset, size, bytearray(data)))
        return True


@pytest.fixture
def coverage_environment(monkeypatch):
    fields = types.ModuleType("sonic_platform_base.sonic_xcvr.fields")
    fields.consts = types.SimpleNamespace(
        ACTIVE_APSEL_HOSTLANE="ActiveAppSelLane"
    )
    platform_base = types.ModuleType("sonic_platform_base")
    sonic_xcvr = types.ModuleType("sonic_platform_base.sonic_xcvr")
    platform_base.sonic_xcvr = sonic_xcvr
    sonic_xcvr.fields = fields
    monkeypatch.setitem(sys.modules, "sonic_platform_base", platform_base)
    monkeypatch.setitem(
        sys.modules, "sonic_platform_base.sonic_xcvr", sonic_xcvr
    )
    monkeypatch.setitem(
        sys.modules, "sonic_platform_base.sonic_xcvr.fields", fields
    )

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
        assert cpoutil.get_subport("Ethernet0") == 0
        assert cpoutil.get_first_subport("Ethernet0") == "Ethernet0"
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

    def test_api_fallback_and_endpoint_paths(self, coverage_environment):
        cpo = coverage_environment
        assert cpoutil.get_oe_api(cpo, "oe0") is cpo.api
        assert cpoutil.get_oe_presence(cpo)
        assert cpoutil.get_els_api(cpo, "els0") is cpo.api
        assert cpoutil.get_els_presence(cpo)

        cpo.oe = CoverageFakeEndpoint(cpo.api)
        cpo.elsfp = CoverageFakeEndpoint(cpo.api)
        assert cpoutil.get_oe_presence(cpo)
        assert cpoutil.get_els_api(cpo, "els0") is cpo.api
        assert cpoutil.get_els_presence(cpo)

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
        assert cpoutil._drop_legacy_els_fields(
            {"temperature": 1, "els_temperature": 2, "rlm_x": 3}
        ) == {"temperature": 1}
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
            "RLM0Laser0": 2.0,
            "extra": {"nested": True},
        }
        lines = cpoutil._format_cpo_dom(dom)
        assert any("AdditionalValues" in line for line in lines)
        assert "not detected" in cpoutil._format_interface_dom(
            "Ethernet0", False, None, None, None
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
             "-n", "0xb2", "-o", "0x80", "-s", "16"],
            ["read-eeprom", "oe", "-i", "0", "-b", "0",
             "-n", "0", "-o", "0", "-s", "16"],
            ["read-eeprom", "els", "-i", "0",
             "-n", "0xb2", "-o", "0x80", "-s", "16"],
            ["write-eeprom", "interface", "Ethernet0", "--oe",
             "-n", "0", "-o", "0x80", "-d", "01 02"],
            ["write-eeprom", "interface", "Ethernet0", "--els",
             "-n", "0xb2", "-o", "0x80", "-d", "01 02"],
            ["write-eeprom", "oe", "-i", "0", "-b", "0",
             "-n", "0", "-o", "0x80", "-d", "01 02"],
            ["write-eeprom", "els", "-i", "0", "-b", "0",
             "-n", "0xb2", "-o", "0x80", "-d", "01 02"],
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
