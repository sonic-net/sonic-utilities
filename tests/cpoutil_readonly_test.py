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
from sonic_platform_base.sonic_xcvr.api.public.elsfp import ElsfpApi  # noqa: E402
from sonic_platform_base.sonic_xcvr.fields import consts, elsfp_consts  # noqa: E402


@pytest.fixture
def public_els_threshold_api():
    """Exercise the public aggregate API with decoded EEPROM register values."""
    cmis_thresholds = {}
    for field, values in (
            ("TEMP", (75.0, -5.0, 70.0, 0.0)),
            ("VOLTAGE", (3.6, 3.0, 3.5, 3.1)),
            ("RX_POWER", (2.0, 0.1, 1.0, 0.2)),
            ("TX_POWER", (2.0, 0.1, 1.0, 0.2)),
            ("TX_BIAS", (10.0, 1.0, 9.0, 2.0))):
        for limit, value in zip(("HIGH_ALARM", "LOW_ALARM", "HIGH_WARNING", "LOW_WARNING"), values):
            cmis_thresholds[getattr(consts, "{}_{}_FIELD".format(field, limit))] = value
    registers = {
        consts.THRESHOLDS_FIELD: cmis_thresholds,
        consts.TX_BIAS_SCALE: 1,
        elsfp_consts.BIAS_HIGH_ALARM: 0.1,
        elsfp_consts.BIAS_LOW_ALARM: 0.01,
        elsfp_consts.BIAS_HIGH_WARN: 0.09,
        elsfp_consts.BIAS_LOW_WARN: 0.02,
        elsfp_consts.OPT_POWER_HIGH_ALARM: 10.0,
        elsfp_consts.OPT_POWER_LOW_ALARM: 0.1,
        elsfp_consts.OPT_POWER_HIGH_WARN: 9.0,
        elsfp_consts.OPT_POWER_LOW_WARN: 0.2,
    }
    eeprom = mock.Mock()
    eeprom.read.side_effect = registers.__getitem__
    return ElsfpApi(eeprom)


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

    @pytest.mark.parametrize("command", ["presence", "dom"])
    def test_inherited_presence_placeholder_is_reported_without_endpoint_reads(self, command):
        cpo = cpoutil.CpoBase(None, mock.Mock(), mock.Mock())
        cpoutil.cpo_object_map[PORT][1] = cpo
        result = invoke(["show", "interface", command, "Ethernet0"])
        assert result.exit_code != 0
        assert "CPO presence is not implemented for 'Ethernet0'" in result.output
        assert not cpo.oe.mock_calls
        assert not cpo.elsfp.mock_calls

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

    def test_dom_formats_complete_public_els_thresholds(self, public_els_threshold_api):
        self.cpo.api.get_elsfp_threshold_info = public_els_threshold_api.get_elsfp_threshold_info
        result = invoke(["show", "interface", "dom", "Ethernet0"])
        assert result.exit_code == 0, result.output
        els_section = result.output.split("    ELS:\n")[1]
        _, thresholds = els_section.split("ELSFPThresholdValues:\n")
        els_thresholds, cmis_thresholds = thresholds.split("CMISChannelThresholdValues:\n")
        assert [line.strip() for line in els_thresholds.strip().splitlines()] == [
            "TxBiasHighAlarm: 100.0mA", "TxBiasLowAlarm: 10.0mA",
            "TxBiasHighWarning: 90.0mA", "TxBiasLowWarning: 20.0mA",
            "TxPowerHighAlarm: 10.0dBm", "TxPowerLowAlarm: -10.0dBm",
            "TxPowerHighWarning: 9.542dBm", "TxPowerLowWarning: -6.99dBm",
            "TempHighAlarm: 75.0C", "TempLowAlarm: -5.0C",
            "TempHighWarning: 70.0C", "TempLowWarning: 0.0C",
            "VccHighAlarm: 3.6Volts", "VccLowAlarm: 3.0Volts",
            "VccHighWarning: 3.5Volts", "VccLowWarning: 3.1Volts",
        ]
        assert [line.strip() for line in cmis_thresholds.splitlines()] == [
            "RxPowerHighAlarm: 3.01dBm", "RxPowerHighWarning: 0.0dBm",
            "RxPowerLowAlarm: -10.0dBm", "RxPowerLowWarning: -6.99dBm",
            "TxBiasHighAlarm: 20.0mA", "TxBiasHighWarning: 18.0mA",
            "TxBiasLowAlarm: 2.0mA", "TxBiasLowWarning: 4.0mA",
            "TxPowerHighAlarm: 3.01dBm", "TxPowerHighWarning: 0.0dBm",
            "TxPowerLowAlarm: -10.0dBm", "TxPowerLowWarning: -6.99dBm",
        ]
        assert "AdditionalValues:" not in els_section
        public_els_threshold_api.xcvr_eeprom.write.assert_not_called()

    def test_dom_json_retains_distinct_public_els_thresholds(self, public_els_threshold_api):
        self.cpo.api.get_elsfp_threshold_info = public_els_threshold_api.get_elsfp_threshold_info
        result = invoke(["show", "interface", "dom", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        record = json.loads(result.output)["Ethernet0"]
        thresholds = record["els"]["thresholds"]
        assert thresholds == public_els_threshold_api.get_elsfp_threshold_info()
        assert len(thresholds) == 28
        assert thresholds["laser_bias_alarm_high"] == 100.0
        assert thresholds["txbiashighalarm"] == 20.0
        assert thresholds["optical_power_alarm_high"] == 10.0
        assert thresholds["txpowerhighalarm"] == 3.01
        assert record["oe"]["thresholds"] == {"temphighalarm": 90.0}
        assert all(not key.startswith("els_") for key in thresholds)

    def test_dom_cmis_thresholds_handle_unknown_missing_and_extra_fields(self):
        self.cpo.api.get_elsfp_threshold_info = mock.Mock(return_value={
            "txpowerhighalarm": "Unknown", "txpowerlowalarm": "N/A",
            "txbiashighalarm": "20mA", "rxpowerhighalarm": "3.01dBm", "extra_limit": 7,
        })
        result = invoke(["show", "interface", "dom", "Ethernet0"])
        assert result.exit_code == 0, result.output
        els_section = result.output.split("    ELS:\n")[1]
        assert "TxPowerHighAlarm: Unknown" in els_section
        assert "TxPowerLowAlarm:" not in els_section
        assert "TxBiasHighAlarm: 20mA\n" in els_section
        assert "RxPowerHighAlarm: 3.01dBm\n" in els_section
        assert "AdditionalValues:" in els_section and "extra limit: 7" in els_section

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
        els_api = mock.Mock(spec=["get_module_state"])
        els_api.get_module_state.side_effect = NotImplementedError(
            "Independent ELS module state is not implemented")
        self.cpo.elsfp = mock.Mock(get_api=mock.Mock(return_value=els_api))
        missing = invoke(["show", "els", "status", "0", "--json"])
        assert missing.exit_code != 0
        assert (
            "Independent ELS module state is not implemented"
            in missing.output
        )

        els_api.get_module_state.side_effect = None
        els_api.get_module_state.return_value = "ModuleReady"
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
