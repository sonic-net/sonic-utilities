import json
import os
import sys
from unittest import mock

import pytest
from click.testing import CliRunner

from .cpoutil_test import shared_port_mapping  # noqa: F401


test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

import cpoutil.main as cpoutil  # noqa: E402
from cpoutil.mapping import CpoMapping  # noqa: E402
from cpoutil.mapping import (  # noqa: E402
    EXTERNAL_LASER_SOURCE,
    OPTICAL_ENGINE,
    PORT,
)


CPO_DATA = {
    "oes": {"oe0": {"index": 0, "oe_cmis_path": "/sys/oe0/"}},
    "elss": {"els0": {"index": 0}},
    "interfaces": {
        "Ethernet0": {
            "index": "1,1",
            "lanes": "1,2",
            "oe_id": 0,
            "oe_bank_id": 0,
            "els_id": 0,
            "laser_ids": [0, 1],
        }
    },
}


class FakeApi:
    NUM_CHANNELS = 2

    def get_lpmode(self):
        return False

    def get_module_state(self):
        return "ModuleReady"

    def get_module_temperature(self):
        return 53.125

    def get_rx_power(self):
        return [1.5238, 1.1324]

    def get_application_advertisement(self):
        return {
            1: {"host_electrical_interface_id": "400GAUI-4-L"},
            2: {"host_electrical_interface_id": "200GAUI-4"},
        }

    def get_application(self, lane):
        return lane + 1

    def get_active_apsel_hostlane(self):
        return {"ActiveAppSelLane1": 2, "ActiveAppSelLane2": 1}

    def get_datapath_state(self):
        return {
            "DP1State": "DataPathActivated",
            "DP2State": "DataPathDeactivated",
        }

    def get_tx_disable(self):
        return [False, True]

    def get_transceiver_info(self):
        return {"manufacturer": "Example OE"}

    def get_transceiver_dom_real_value(self):
        return {"temperature": 71.25}

    def get_transceiver_threshold_info(self):
        return {"temphighalarm": 90.0}

    def get_elsfp_info(self):
        return {"manufacturer": "Example ELS"}

    def get_elsfp_status(self):
        status = {
            "module_low_power_state": False,
            "interrupt_status": True,
        }
        if getattr(self, "els_module_state", None) is not None:
            status["module_state"] = self.els_module_state
        return status

    def get_elsfp_module_state(self):
        if getattr(self, "els_module_state", None) is None:
            raise NotImplementedError("Independent ELS module state is not implemented")
        return self.els_module_state

    def get_per_lane_state(self):
        return {
            "Laser0State": "Active",
            "Laser1State": "Inactive",
            "Laser2State": "Active",
            "Laser3State": "Inactive",
        }

    def get_elsfp_dom_real_value(self):
        return {"temperature": 32.5, "voltage": 3.3}

    def get_elsfp_threshold_info(self):
        return {"temperature_alarm_high": 75.0}

    def get_per_lane_opt_power_monitor(self):
        return {
            "Laser0OpticalPowerMonitor": 9.1,
            "Laser1OpticalPowerMonitor": 70.8,
        }


class FakeCpo(cpoutil.CpoBase):
    def __init__(self):
        super().__init__(None, self, self)
        self.api = FakeApi()

    def get_api(self):
        return self.api

    def get_presence(self):
        return True

    def get_transceiver_info(self):
        return {"manufacturer": "Example OE"}

    def get_transceiver_dom_real_value(self):
        return {"temperature": 71.25}

    def get_transceiver_threshold_info(self):
        return {"temphighalarm": 90.0}


def invoke(command):
    with mock.patch("cpoutil.main.initialize_platform"):
        return CliRunner().invoke(cpoutil.cli, command)


class TestDirectPlatformApiCommands(object):
    def setup_method(self):
        cpo = FakeCpo()
        self.cpo = cpo
        cpoutil.cpo_mapping = CpoMapping(CPO_DATA)
        cpoutil.current_port_config = {
            "Ethernet0": {"index": "1", "lanes": "1,2"},
            "Ethernet1": {"index": "1", "lanes": "2", "subport": "2"},
        }
        cpoutil.cpo_object_map = {
            OPTICAL_ENGINE: {"oe0": cpo},
            EXTERNAL_LASER_SOURCE: {"els0": cpo},
            PORT: {1: cpo},
        }

    def test_oe_status_calls_existing_xcvr_api(self):
        result = invoke(["show", "oe", "status", "0", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"oe0": "ModuleReady"}

    def test_els_commands_call_public_elsfp_api(self):
        temperature = invoke([
            "show", "els", "temperature", "els0", "--json"
        ])
        power = invoke([
            "show", "els", "output-power", "0", "--json"
        ])
        assert json.loads(temperature.output) == {"els0": 32.5}
        assert json.loads(power.output)["els0"][
            "Laser0OpticalPowerMonitor"
        ] == 9.1

    def test_els_output_power_table_uses_measurement_precision(self):
        result = invoke(["show", "els", "output-power", "0"])
        assert result.exit_code == 0
        assert "9.10" in result.output
        assert "70.80" in result.output

        json_result = invoke([
            "show", "els", "output-power", "0", "--json"
        ])
        assert json.loads(json_result.output)["els0"][
            "Laser1OpticalPowerMonitor"
        ] == 70.8

    @pytest.mark.parametrize("present", [True, False])
    def test_interface_presence_calls_cpo_instead_of_endpoints(self, present):
        self.cpo.oe = mock.Mock(get_presence=mock.Mock(return_value=not present))
        self.cpo.elsfp = mock.Mock(get_presence=mock.Mock(return_value=not present))
        self.cpo.get_presence = mock.Mock(return_value=present)
        result = invoke(["show", "interface", "presence", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"Ethernet0": present}
        self.cpo.get_presence.assert_called_once_with()
        self.cpo.oe.get_presence.assert_not_called()
        self.cpo.elsfp.get_presence.assert_not_called()

        table = invoke(["show", "interface", "presence", "Ethernet0"])
        assert ("Present" if present else "Not present") in table.output
        assert "Interface" in table.output

    def test_presence_lists_all_interfaces_and_breakouts(self):
        result = invoke(["show", "interface", "presence", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"Ethernet0": True, "Ethernet1": True}
        result = invoke(["show", "interface", "presence", "Ethernet1", "--json"])
        assert json.loads(result.output) == {"Ethernet1": True}

    @pytest.mark.parametrize("command", ["presence", "dom"])
    @pytest.mark.parametrize("error", [NotImplementedError(), AttributeError(), OSError("read failed")])
    def test_presence_failures_are_reported_without_endpoint_fallback(self, command, error):
        self.cpo.oe = mock.Mock()
        self.cpo.elsfp = mock.Mock()
        self.cpo.get_presence = mock.Mock(side_effect=error)
        result = invoke(["show", "interface", command, "Ethernet0", "--json"])
        assert result.exit_code != 0
        assert "CPO presence" in result.output and "Ethernet0" in result.output
        assert not self.cpo.oe.mock_calls
        assert not self.cpo.elsfp.mock_calls

    @pytest.mark.parametrize("value", [None, 1, "False"])
    def test_invalid_presence_result_is_not_reported_as_present(self, value):
        self.cpo.get_presence = mock.Mock(return_value=value)
        result = invoke(["show", "interface", "presence", "Ethernet0"])
        assert result.exit_code != 0
        assert "CPO presence API returned invalid data" in result.output

    def test_els_lpmode_has_boolean_json_and_readable_table(self):
        result = invoke(["show", "els", "lpmode", "0", "--json"])
        assert json.loads(result.output) == {"els0": False}

        table = invoke(["show", "els", "lpmode", "0"])
        assert "Off" in table.output

    def test_els_lpmode_normalizes_vendor_decoder_strings(self):
        with mock.patch.object(
                self.cpo.api,
                "get_elsfp_status",
                return_value={"module_low_power_state": "Low power mode"}):
            result = invoke(["show", "els", "lpmode", "0", "--json"])
        assert json.loads(result.output) == {"els0": True}

    def test_interface_dom_calls_public_oe_and_els_apis(self):
        result = invoke([
            "show", "interface", "dom", "Ethernet0", "--json"
        ])
        assert result.exit_code == 0, result.output
        values = json.loads(result.output)["Ethernet0"]
        assert values["present"] is True
        assert values["oe"]["info"]["manufacturer"] == "Example OE"
        assert values["els"]["info"]["manufacturer"] == "Example ELS"
        assert values["oe"]["dom"]["temperature"] == 71.25
        assert values["els"]["dom"]["temperature"] == 32.5
        assert values["oe"]["thresholds"]["temphighalarm"] == 90.0
        assert values["els"]["thresholds"]["temperature_alarm_high"] == 75.0
        assert isinstance(values["oe"]["dom"]["temperature"], float)
        for section in values["els"].values():
            assert not any(key.startswith("els_") for key in section)

    def test_interface_dom_queries_cpo_presence_before_endpoint_apis(self):
        self.cpo.get_presence = mock.Mock(return_value=True)
        self.cpo.oe = mock.Mock()
        self.cpo.elsfp = mock.Mock()
        self.cpo.oe.get_api.return_value = self.cpo.api
        self.cpo.elsfp.get_api.return_value = self.cpo.api
        result = invoke(["show", "interface", "dom", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        self.cpo.get_presence.assert_called_once_with()
        self.cpo.oe.get_presence.assert_not_called()
        self.cpo.elsfp.get_presence.assert_not_called()

    @pytest.mark.parametrize("json_output", [False, True])
    def test_absent_cpo_does_not_read_either_endpoint(self, json_output):
        self.cpo.get_presence = mock.Mock(return_value=False)
        self.cpo.oe = mock.Mock()
        self.cpo.elsfp = mock.Mock()
        args = ["show", "interface", "dom", "Ethernet0"] + (["--json"] if json_output else [])
        result = invoke(args)
        assert result.exit_code == 0, result.output
        if json_output:
            assert json.loads(result.output) == {"Ethernet0": {"present": False, "oe": {}, "els": {}}}
        else:
            assert result.output.strip() == "Ethernet0: CPO EEPROM not detected"
        assert not self.cpo.oe.mock_calls
        assert not self.cpo.elsfp.mock_calls

    def test_dom_table_separates_endpoint_values_and_preserves_units(self):
        self.cpo.api.get_elsfp_info = mock.Mock(return_value={
            "manufacturer": "Example ELS", "lane_count": 2, "max_optical_power": 3.5, "max_laser_bias": 20,
        })
        self.cpo.api.get_elsfp_dom_real_value = mock.Mock(return_value={
            "temperature": 32.5, "optical_power_lane1": -1.2, "optical_power_lane3": -8.0,
        })
        result = invoke(["show", "interface", "dom", "Ethernet0"])
        assert result.exit_code == 0, result.output
        oe_section, els_section = result.output.split("    ELS:\n")
        assert "    OE:\n" in oe_section and "Example OE" in oe_section
        assert "71.25C" in oe_section and "32.5C" not in oe_section
        assert "Example ELS" in els_section and "32.5C" in els_section
        assert "71.25C" not in els_section
        assert "Maximum Optical Power: 3.5dBm" in els_section
        assert "Maximum Laser Bias: 20mA" in els_section
        assert "Laser 1 Optical Power: -1.2dBm" in els_section
        assert "Laser 3" not in els_section
        assert els_section.count("TempHighAlarm:") == 1

    def test_dom_json_preserves_api_fields_without_mutating_or_overwriting(self):
        source_values = {}
        for endpoint, methods in {
                "oe": ("get_transceiver_info", "get_transceiver_dom_real_value", "get_transceiver_threshold_info"),
                "els": ("get_elsfp_info", "get_elsfp_dom_real_value", "get_elsfp_threshold_info"),
        }.items():
            source_values[endpoint] = {}
            for section, method in zip(("info", "dom", "thresholds"), methods):
                values = {"shared_name": "{} {}".format(endpoint, section)}
                source_values[endpoint][section] = values
                setattr(self.cpo.api, method, mock.Mock(return_value=values))
        result = invoke(["show", "interface", "dom", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        values = json.loads(result.output)["Ethernet0"]
        for endpoint in ("oe", "els"):
            for section in ("info", "dom", "thresholds"):
                expected = {"shared_name": "{} {}".format(endpoint, section)}
                assert values[endpoint][section] == expected
                assert source_values[endpoint][section] == expected

    def test_interface_tx_disable_supports_breakout_name(self):
        result = invoke([
            "show", "interface", "tx_disable", "Ethernet1", "--json"
        ])
        assert json.loads(result.output) == {
            "Ethernet1": {
                "lane01": True,
            }
        }

        table = invoke([
            "show", "interface", "tx_disable", "Ethernet1"
        ])
        assert "Tx output disable" in table.output

    def test_interface_speed_uses_existing_cmis_methods(self):
        result = invoke([
            "show", "interface", "speed", "Ethernet0", "--json"
        ])
        values = json.loads(result.output)["Ethernet0"]
        assert values["Application Select Controls"] == {
            "lane00": 400000,
            "lane01": 200000,
        }
        assert values["Active Application Control Set"] == {
            "lane00": 200000,
            "lane01": 400000,
        }

    def test_breakout_speed_does_not_require_els_lane_mapping(self):
        result = invoke([
            "show", "interface", "speed", "Ethernet1", "--json"
        ])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["Ethernet1"] == {
            "Application Select Controls": {"lane01": 200000},
            "Active Application Control Set": {"lane01": 400000},
        }

    def test_interface_lane_status_uses_public_elsfp_api(self):
        result = invoke([
            "show", "interface", "lane-status", "Ethernet0", "--json"
        ])
        values = json.loads(result.output)["Ethernet0"]
        assert values["Data Path State Indicator"]["lane00"] == \
            "DataPathActivated"
        assert values["ELS Status"] == {
            "low_power_mode": False,
            "interrupt_event": True,
        }
        assert values["ELS Lane State"] == {
            "lane00": "Active",
            "lane01": "Inactive",
        }

    def test_interrupt_event_normalizes_public_status(self):
        with mock.patch.object(
                self.cpo.api,
                "get_elsfp_status",
                return_value={
                    "module_low_power_state": "High power mode",
                    "interrupt_status": "Interrupt event cleared",
                }):
            result = invoke([
                "show", "interface", "lane-status", "Ethernet0", "--json"
            ])
        status = json.loads(result.output)["Ethernet0"]["ELS Status"]
        assert status == {
            "low_power_mode": False,
            "interrupt_event": False,
        }

    def test_els_status_requires_independent_module_state(self):
        missing = invoke(["show", "els", "status", "0", "--json"])
        assert missing.exit_code != 0
        assert (
            "Independent ELS module state is not implemented"
            in missing.output
        )

        self.cpo.api.els_module_state = "ModuleReady"
        result = invoke(["show", "els", "status", "0", "--json"])
        assert json.loads(result.output) == {"els0": "ModuleReady"}

    def test_measurements_keep_command_specific_precision(self):
        input_power = invoke(["show", "oe", "input-power", "0"])
        temperature = invoke(["show", "oe", "temperature", "0"])
        assert "1.5238" in input_power.output
        assert "53.125" in temperature.output

    def test_json_records_use_natural_top_level_order(self, capsys):
        cpoutil.print_records(
            {"els10": True, "els2": True, "els1": True}, True
        )
        output = capsys.readouterr().out
        assert output.index('"els1"') < output.index('"els2"')
        assert output.index('"els2"') < output.index('"els10"')

        cpoutil.print_records(
            {"Ethernet12": 1, "Ethernet4": 1, "Ethernet0": 1}, True
        )
        output = capsys.readouterr().out
        assert output.index('"Ethernet0"') < output.index('"Ethernet4"')
        assert output.index('"Ethernet4"') < output.index('"Ethernet12"')

    def test_unknown_resource_is_rejected(self):
        result = invoke(["show", "oe", "status", "99"])
        assert result.exit_code != 0
        assert "Invalid oe index '99'" in result.output
