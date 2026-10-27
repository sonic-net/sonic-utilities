from contextlib import contextmanager
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
    "devices": {
        "oe0": {
            "device_type": "optical_engine",
            "max_banks": 1,
            "asic_lanes": [
                1,
                2
            ]
        },
        "els0": {
            "device_type": "external_laser_source",
            "laser_to_asic_lane_mapping": {}
        }
    },
    "interfaces": {
        "Ethernet0": {
            "index": (1, 1),
            "lanes": (1, 2),
            "associated_devices": [
                {
                    "device_id": "oe0",
                    "bank": 0
                },
                {
                    "device_id": "els0"
                }
            ]
        }
    },
    "platform_data": {
        "interfaces": {
            "Ethernet0": {
                "laser_ids": [
                    0,
                    1
                ]
            }
        }
    }
}


class FakeApi:
    NUM_CHANNELS = 2

    def __init__(self):
        self.xcvr_eeprom = mock.Mock(mem_map=mock.Mock(bank=0))

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
            1: {
                "host_electrical_interface_id": "400GAUI-4-L C2M (Annex 120G)",
                "module_media_interface_id": "400G-FR4/400GBASE-FR4 (Cl 151)",
                "host_lane_count": 4, "media_lane_count": 4,
                "host_lane_assignment_options": 17, "media_lane_assignment_options": 17,
            },
            2: {
                "host_electrical_interface_id": "CAUI-4 C2M (Annex 83E) with RS(528,514) FEC",
                "module_media_interface_id": "100G CWDM4 MSA Spec",
                "host_lane_count": 4, "media_lane_count": 4,
                "host_lane_assignment_options": 17, "media_lane_assignment_options": 17,
            },
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

    def get_lane_count(self):
        return 2

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
    def get_tx_disable(self):
        return self.api.get_tx_disable()

    def get_lpmode(self):
        return False

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
            "Ethernet0": {"index": (1,), "lanes": (1, 2)},
            "Ethernet1": {"index": (1,), "lanes": (2,), "subport": "2"},
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

    def test_els_temperature_calls_public_elsfp_api(self):
        with mock.patch.object(self.cpo.api, "get_module_temperature", return_value=32.5):
            temperature = invoke([
                "show", "els", "temperature", "els0", "--json"
            ])
        assert json.loads(temperature.output) == {"els0": 32.5}

    def test_els_output_power_command_is_not_exposed(self):
        help_result = invoke(["show", "els", "--help"])
        assert help_result.exit_code == 0
        assert "output-power" not in help_result.output
        for suffix in (["0"], ["--help"]):
            result = invoke(["show", "els", "output-power"] + suffix)
            assert result.exit_code == 2
            assert "No such command 'output-power'" in result.output

    @pytest.mark.parametrize("value", [0.0, -5.5, 32.5])
    @pytest.mark.parametrize("index", [None, "0"])
    @pytest.mark.parametrize("json_output", [False, True])
    def test_els_temperature_uses_module_api_without_dom(self, value, index, json_output):
        args = ["show", "els", "temperature"]
        if index is not None:
            args.append(index)
        if json_output:
            args.append("--json")
        with mock.patch.object(self.cpo.api, "get_module_temperature", return_value=value) as module:
            with mock.patch.object(self.cpo.api, "get_elsfp_dom_real_value", side_effect=AssertionError("DOM read")):
                result = invoke(args)
        assert result.exit_code == 0, result.output
        module.assert_called_once_with()
        if json_output:
            assert json.loads(result.output) == {"els0": value}
        else:
            assert float(result.output.splitlines()[-1].split()[-1]) == value

    @pytest.mark.parametrize("index", [None, "0"])
    def test_els_temperature_reports_missing_module_read(self, index):
        args = ["show", "els", "temperature"] + ([index] if index is not None else [])
        with mock.patch.object(self.cpo.api, "get_module_temperature", return_value=None):
            result = invoke(args)
        assert result.exit_code != 0
        assert "ELSFP temperature is unavailable for 'els0'" in result.output

    @pytest.mark.parametrize("present", [True, False])
    def test_interface_presence_calls_cpo_instead_of_endpoints(self, present):
        self.cpo.oe = mock.Mock(get_presence=mock.Mock(return_value=not present))
        self.cpo.elsfp = mock.Mock(get_presence=mock.Mock(return_value=not present))
        self.cpo.get_presence = mock.Mock(return_value=present)
        result = invoke(["show", "interface", "presence", "-p", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"Ethernet0": {"els": "ELS0", "present": present}}
        self.cpo.get_presence.assert_called_once_with()
        self.cpo.oe.get_presence.assert_not_called()
        self.cpo.elsfp.get_presence.assert_not_called()

        table = invoke(["show", "interface", "presence", "-p", "Ethernet0"])
        assert ("Present" if present else "Not present") in table.output
        assert "Interface" in table.output
        assert "ELS" in table.output and "ELS0" in table.output

    def test_presence_lists_all_interfaces_and_breakouts(self):
        result = invoke(["show", "interface", "presence", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {
            "Ethernet0": {"els": "ELS0", "present": True},
            "Ethernet1": {"els": "ELS0", "present": True},
        }
        result = invoke(["show", "interface", "presence", "-p", "Ethernet1", "--json"])
        assert json.loads(result.output) == {"Ethernet1": {"els": "ELS0", "present": True}}

    @pytest.mark.parametrize("command", ["presence", "dom"])
    @pytest.mark.parametrize("error", [NotImplementedError(), AttributeError(), OSError("read failed")])
    def test_presence_failures_are_reported_without_endpoint_fallback(self, command, error):
        self.cpo.oe = mock.Mock()
        self.cpo.elsfp = mock.Mock()
        self.cpo.get_presence = mock.Mock(side_effect=error)
        path = ["show", "interface", "presence"] if command == "presence" else ["show", "interface", command]
        result = invoke(path + ["-p", "Ethernet0", "--json"])
        assert result.exit_code != 0
        assert "CPO presence" in result.output and "Ethernet0" in result.output
        assert not self.cpo.oe.mock_calls
        assert not self.cpo.elsfp.mock_calls

    @pytest.mark.parametrize("value", [None, 1, "False"])
    def test_invalid_presence_result_is_not_reported_as_present(self, value):
        self.cpo.get_presence = mock.Mock(return_value=value)
        result = invoke(["show", "interface", "presence", "-p", "Ethernet0"])
        assert result.exit_code != 0
        assert "CPO presence API returned invalid data" in result.output

    @pytest.mark.parametrize("command", ["presence", "dom"])
    def test_inherited_presence_placeholder_is_reported_without_endpoint_reads(self, command):
        cpo = cpoutil.CpoBase(None, mock.Mock(), mock.Mock())
        cpoutil.cpo_object_map[PORT][1] = cpo
        path = ["show", "interface", "presence"] if command == "presence" else ["show", "interface", command]
        result = invoke(path + ["-p", "Ethernet0"])
        assert result.exit_code != 0
        assert "CPO presence is not implemented for 'Ethernet0'" in result.output
        assert not cpo.oe.mock_calls
        assert not cpo.elsfp.mock_calls

    @pytest.mark.parametrize("path", [["show", "presence"], ["show", "els", "presence"]])
    def test_presence_only_exists_under_interface(self, path):
        result = invoke(path)
        assert result.exit_code == 2
        assert "No such command 'presence'" in result.output

    def test_els_lpmode_has_boolean_json_and_readable_table(self):
        result = invoke(["show", "els", "lpmode", "0", "--json"])
        assert json.loads(result.output) == {"els0": False}

        table = invoke(["show", "els", "lpmode", "0"])
        assert "Off" in table.output

    def test_els_lpmode_rejects_platform_hook_strings(self):
        with mock.patch.object(
                self.cpo,
                "get_lpmode",
                return_value="Low Power Mode"):
            result = invoke(["show", "els", "lpmode", "0", "--json"])
        assert result.exit_code != 0
        assert "ELS get_lpmode returned invalid data" in result.output

    def test_interface_dom_calls_public_oe_and_els_apis(self):
        result = invoke([
            "show", "interface", "dom", "-p", "Ethernet0", "--json"
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
        result = invoke(["show", "interface", "dom", "-p", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        self.cpo.get_presence.assert_called_once_with()
        self.cpo.oe.get_presence.assert_not_called()
        self.cpo.elsfp.get_presence.assert_not_called()

    @pytest.mark.parametrize("json_output", [False, True])
    def test_absent_cpo_does_not_read_either_endpoint(self, json_output):
        self.cpo.get_presence = mock.Mock(return_value=False)
        self.cpo.oe = mock.Mock()
        self.cpo.elsfp = mock.Mock()
        args = ["show", "interface", "dom", "-p", "Ethernet0"] + (["--json"] if json_output else [])
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
        result = invoke(["show", "interface", "dom", "-p", "Ethernet0"])
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
        result = invoke(["show", "interface", "dom", "-p", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        values = json.loads(result.output)["Ethernet0"]
        for endpoint in ("oe", "els"):
            for section in ("info", "dom", "thresholds"):
                expected = {"shared_name": "{} {}".format(endpoint, section)}
                assert values[endpoint][section] == expected
                assert source_values[endpoint][section] == expected

    def test_dom_formats_complete_public_els_thresholds(self, public_els_threshold_api):
        self.cpo.api.get_elsfp_threshold_info = public_els_threshold_api.get_elsfp_threshold_info
        result = invoke(["show", "interface", "dom", "-p", "Ethernet0"])
        assert result.exit_code == 0, result.output
        els_section = result.output.split("    ELS:\n")[1]
        _, thresholds = els_section.split("        ThresholdValues:\n", 1)
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
        result = invoke(["show", "interface", "dom", "-p", "Ethernet0", "--json"])
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
        result = invoke(["show", "interface", "dom", "-p", "Ethernet0"])
        assert result.exit_code == 0, result.output
        els_section = result.output.split("    ELS:\n")[1]
        assert "TxPowerHighAlarm: Unknown" in els_section
        assert "TxPowerLowAlarm:" not in els_section
        assert "TxBiasHighAlarm: 20mA\n" in els_section
        assert "RxPowerHighAlarm: 3.01dBm\n" in els_section
        assert "AdditionalValues:" in els_section and "extra limit: 7" in els_section

    def test_interface_tx_disable_supports_breakout_name(self):
        result = invoke([
            "show", "interface", "tx-disable", "-p", "Ethernet1", "--json"
        ])
        assert json.loads(result.output) == {
            "Ethernet1": {
                "lane01": True,
            }
        }

        table = invoke([
            "show", "interface", "tx-disable", "-p", "Ethernet1"
        ])
        assert table.exit_code == 0, table.output
        assert table.output.splitlines()[0].split() == [
            "Interface", "Lane", "Tx", "Disable", "Status"
        ]
        assert table.output.splitlines()[2].split() == ["Ethernet1", "Lane", "2", "true"]

    def test_interface_tx_disable_displays_both_boolean_states(self):
        table = invoke(["show", "interface", "tx-disable", "-p", "Ethernet0"])
        assert table.exit_code == 0, table.output
        assert [row.split() for row in table.output.splitlines()[2:]] == [
            ["Ethernet0", "Lane", "1", "false"],
            ["Ethernet0", "Lane", "2", "true"],
        ]

        result = invoke(["show", "interface", "tx-disable", "-p", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {
            "Ethernet0": {"lane00": False, "lane01": True}
        }

    @pytest.mark.parametrize("port", ["Ethernet0", "Ethernet1"])
    def test_interface_tx_disable_uses_cpo_hook_without_oe_api(self, port):
        self.cpo.get_tx_disable = mock.Mock(return_value=[True, False])
        self.cpo.get_api = mock.Mock(side_effect=AssertionError("unexpected API access"))
        result = invoke(["show", "interface", "tx-disable", "-p", port, "--json"])
        assert result.exit_code == 0, result.output
        expected = {"lane00": True, "lane01": False} if port == "Ethernet0" else {"lane01": False}
        assert json.loads(result.output) == {port: expected}
        self.cpo.get_tx_disable.assert_called_once_with()
        self.cpo.get_api.assert_not_called()

    @pytest.mark.parametrize("error, message", [
        (NotImplementedError(), "get_tx_disable is not implemented"),
        (OSError("control read failed"), "get_tx_disable failed: control read failed"),
    ])
    def test_interface_tx_disable_reports_hook_errors(self, error, message):
        self.cpo.get_tx_disable = mock.Mock(side_effect=error)
        result = invoke(["show", "interface", "tx-disable", "-p", "Ethernet0"])
        assert result.exit_code == 1, result.output
        assert message in result.output

    def test_interface_application_preserves_public_api_values(self):
        result = invoke([
            "show", "interface", "speed", "application", "-p", "Ethernet0", "--json"
        ])
        assert result.exit_code == 0, result.output
        values = json.loads(result.output)["Ethernet0"]
        assert values["Application Select Controls"] == {"lane00": 1, "lane01": 2}
        assert values["Active Application Control Set"] == {"lane00": 2, "lane01": 1}
        assert values["Application Advertisement"] == {
            str(key): value for key, value in self.cpo.api.get_application_advertisement().items()
        }

    def test_application_table_has_four_columns_and_full_interface_names(self):
        result = invoke(["show", "interface", "speed", "application", "-p", "Ethernet0"])
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[0].split("  ")[0] == "Interface"
        assert "Configured Application" in result.output
        assert "Active Application" in result.output
        assert "Configured Speed" not in result.output
        assert "AppSel" not in result.output.splitlines()[0]
        for value in self.cpo.api.get_application_advertisement().values():
            assert value["host_electrical_interface_id"] in result.output
            assert value["module_media_interface_id"] in result.output
        assert "1: 400GAUI-4-L C2M (Annex 120G)" in result.output
        assert "2: CAUI-4 C2M (Annex 83E) with RS(528,514) FEC" in result.output

    def test_breakout_application_does_not_require_els_lane_mapping(self):
        result = invoke([
            "show", "interface", "speed", "application", "-p", "Ethernet1", "--json"
        ])
        assert result.exit_code == 0, result.output
        values = json.loads(result.output)["Ethernet1"]
        assert values["Application Select Controls"] == {"lane01": 2}
        assert values["Active Application Control Set"] == {"lane01": 1}
        assert values["Application Advertisement"]["2"]["host_electrical_interface_id"] == (
            "CAUI-4 C2M (Annex 83E) with RS(528,514) FEC"
        )

    @pytest.mark.parametrize("application", [0, 15])
    def test_unadvertised_application_keeps_the_selected_id(self, monkeypatch, application):
        monkeypatch.setattr(self.cpo.api, "get_application", lambda lane: application)
        result = invoke(["show", "interface", "speed", "application", "-p", "Ethernet1"])
        assert result.exit_code == 0, result.output
        assert "{}: N/A".format(application) in result.output

    def test_application_with_serialized_advertisement_keys(self, monkeypatch):
        advertisements = self.cpo.api.get_application_advertisement()
        monkeypatch.setattr(self.cpo.api, "get_application_advertisement", lambda: {
            str(key): value for key, value in advertisements.items()
        })
        result = invoke(["show", "interface", "speed", "application", "-p", "Ethernet1"])
        assert result.exit_code == 0, result.output
        assert advertisements[2]["host_electrical_interface_id"] in result.output

    def test_interface_lane_status_uses_public_elsfp_api(self):
        result = invoke([
            "show", "interface", "lane-status", "-p", "Ethernet0", "--json"
        ])
        values = json.loads(result.output)["Ethernet0"]
        assert values["Data Path State Indicator"]["lane00"] == \
            "DataPathActivated"
        assert values["ELS Status"] == {
            "module_low_power_state": False,
            "interrupt_status": True,
        }
        assert values["ELS Lane State"] == {
            "lane00": "Active",
            "lane01": "Inactive",
        }

    def test_els_status_preserves_api_strings(self):
        with mock.patch.object(
                self.cpo.api,
                "get_elsfp_status",
                return_value={
                    "module_low_power_state": "High power mode",
                    "interrupt_status": "Interrupt event cleared",
                }):
            result = invoke([
                "show", "interface", "lane-status", "-p", "Ethernet0", "--json"
            ])
        status = json.loads(result.output)["Ethernet0"]["ELS Status"]
        assert status == {
            "module_low_power_state": "High power mode",
            "interrupt_status": "Interrupt event cleared",
        }

    @pytest.mark.parametrize("json_output", [True, False])
    def test_els_status_preserves_fields_and_only_maps_text_labels(self, json_output):
        api_status = {
            "module_state": "ModuleReady",
            "module_fault_cause": "No Fault",
            "module_low_power_state": "High power mode",
            "interrupt_status": "Interrupt event cleared",
            "enable_lane1": True,
            "vendor_status": {"code": 3},
        }
        arguments = ["show", "interface", "lane-status", "-p", "Ethernet0"]
        if json_output:
            arguments.append("--json")
        with mock.patch.object(self.cpo.api, "get_elsfp_status", return_value=api_status):
            result = invoke(arguments)
        assert result.exit_code == 0, result.output
        if json_output:
            assert json.loads(result.output)["Ethernet0"]["ELS Status"] == api_status
        else:
            for label in ("Module State", "Module Fault Cause", "Module Low Power State",
                          "Interrupt Status", "enable_lane1", "vendor_status"):
                assert label in result.output
            assert "High power mode" in result.output
            assert "Interrupt event cleared" in result.output
        assert api_status["module_low_power_state"] == "High power mode"
        assert api_status["vendor_status"] == {"code": 3}

    @pytest.mark.parametrize("status", [None, {}, False, "ModuleReady"])
    def test_els_status_rejects_missing_or_invalid_result(self, status):
        with mock.patch.object(self.cpo.api, "get_elsfp_status", return_value=status):
            result = invoke(["show", "interface", "lane-status", "-p", "Ethernet0", "--json"])
        assert result.exit_code != 0
        assert "ELSFP status API returned no usable data" in result.output
        assert "Ethernet0" in result.output

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

    def test_temperature_keeps_measurement_precision(self):
        temperature = invoke(["show", "oe", "temperature", "0"])
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


class DomOptoeEndpoint(cpoutil.OptoeEepromReadWriteMixin):
    def __init__(self, path):
        self.path = str(path)

    def get_eeprom_path(self):
        return self.path

    def get_api(self):
        return self.api


class DomSnapshotApi:
    def __init__(self, endpoint):
        self.xcvr_eeprom = cpoutil.XcvrEeprom(endpoint.read_eeprom, endpoint.write_eeprom, None)

    def get_transceiver_info(self):
        return {"manufacturer": self.xcvr_eeprom.reader(0, 2).decode()}

    get_elsfp_info = get_transceiver_info

    def get_transceiver_dom_real_value(self):
        return {"temperature": float(self.xcvr_eeprom.reader(0, 1)[0])}

    get_elsfp_dom_real_value = get_transceiver_dom_real_value

    def get_transceiver_threshold_info(self):
        return {"temphighalarm": float(self.xcvr_eeprom.reader(1, 1)[0])}

    def get_elsfp_threshold_info(self):
        return {"temperature_alarm_high": float(self.xcvr_eeprom.reader(1, 1)[0])}


class TestDomEepromSnapshot:
    def endpoint(self, path):
        endpoint = DomOptoeEndpoint(path)
        endpoint.api = DomSnapshotApi(endpoint)
        return endpoint

    def test_global_dom_preserves_output_and_reads_shared_bytes_once(self, monkeypatch, tmp_path):
        oe_file, els_file = tmp_path / "oe", tmp_path / "els"
        oe_file.write_bytes(b"AB")
        els_file.write_bytes(b"CD")
        cpos = {}
        endpoints = []
        for port in range(1, 4):
            oe, els = self.endpoint(oe_file), self.endpoint(els_file)
            endpoints.extend([oe, els])
            cpo = cpoutil.CpoBase(None, oe, els)
            cpo.get_presence = mock.Mock(return_value=True)
            cpos[port] = cpo
        monkeypatch.setattr(cpoutil, "current_port_config", {
            "Ethernet{}".format(index * 8): {"index": str(index + 1), "lanes": (1, 2)}
            for index in range(3)
        })
        monkeypatch.setattr(cpoutil, "cpo_object_map", {
            PORT: cpos, OPTICAL_ENGINE: {"oe0": cpos[1]}, EXTERNAL_LASER_SOURCE: {"els0": cpos[1]},
        })

        @contextmanager
        def no_snapshot():
            yield lambda endpoint, api: None

        with mock.patch.object(cpoutil, "_eeprom_read_snapshot", no_snapshot):
            with mock.patch("builtins.open", wraps=open) as opened:
                baseline = invoke(["show", "interface", "dom", "--json"])
                baseline_reads = opened.call_count
        with mock.patch("builtins.open", wraps=open) as opened:
            optimized = invoke(["show", "interface", "dom", "--json"])
            optimized_reads = opened.call_count
        assert baseline.exit_code == optimized.exit_code == 0
        assert json.loads(baseline.output) == json.loads(optimized.output)
        assert baseline_reads == 18
        assert optimized_reads == 2
        for endpoint in endpoints:
            assert endpoint.api.xcvr_eeprom.reader == endpoint.read_eeprom

    def test_different_banks_and_paths_do_not_share_values(self, tmp_path):
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages.page import CmisPage
        first, second = tmp_path / "first", tmp_path / "second"
        data = bytearray(0x30000)
        bank0 = CmisPage.linear_offset(0x10, 0, 128)
        bank1 = CmisPage.linear_offset(0x10, 1, 128)
        assert bank0 != bank1
        data[bank0] = 17
        data[bank1] = 34
        first.write_bytes(data)
        data[bank0] = 51
        second.write_bytes(data)
        oe = self.endpoint(first)
        peer = self.endpoint(first)
        other = self.endpoint(second)
        with cpoutil._eeprom_read_snapshot() as attach:
            for endpoint in (oe, peer, other):
                attach(endpoint, endpoint.api)
            assert oe.api.xcvr_eeprom.reader(bank0, 1) == bytearray([17])
            assert peer.api.xcvr_eeprom.reader(bank1, 1) == bytearray([34])
            assert other.api.xcvr_eeprom.reader(bank0, 1) == bytearray([51])

    def test_returned_buffers_are_not_shared(self, tmp_path):
        path = tmp_path / "eeprom"
        path.write_bytes(b"ABCD")
        endpoint = self.endpoint(path)
        read = endpoint.api.xcvr_eeprom
        with cpoutil._eeprom_read_snapshot() as attach:
            attach(endpoint, endpoint.api)
            first = read.reader(0, 4)
            first[0] = 0
            second = read.reader(0, 4)
            second[1] = 0
            assert read.reader(0, 4) == bytearray(b"ABCD")

    def test_failed_or_short_reads_are_not_cached(self, tmp_path):
        path = tmp_path / "eeprom"
        endpoint = self.endpoint(path)
        read = endpoint.api.xcvr_eeprom
        with cpoutil._eeprom_read_snapshot() as attach:
            attach(endpoint, endpoint.api)
            assert read.reader(0, 4) is None
            path.write_bytes(b"AB")
            assert read.reader(0, 4) == bytearray(b"AB")
            path.write_bytes(b"WXYZ")
            assert read.reader(0, 4) == bytearray(b"WXYZ")

    def test_snapshot_expires_and_reader_restores_after_error(self, tmp_path):
        path = tmp_path / "eeprom"
        path.write_bytes(b"AB")
        endpoint = self.endpoint(path)
        read = endpoint.api.xcvr_eeprom
        original = read.reader
        with pytest.raises(RuntimeError, match="stop"):
            with cpoutil._eeprom_read_snapshot() as attach:
                attach(endpoint, endpoint.api)
                attach(endpoint, endpoint.api)
                assert read.reader(0, 2) == bytearray(b"AB")
                raise RuntimeError("stop")
        assert read.reader is original
        path.write_bytes(b"CD")
        with cpoutil._eeprom_read_snapshot() as attach:
            attach(endpoint, endpoint.api)
            assert read.reader(0, 2) == bytearray(b"CD")
        assert read.reader is original

    def test_custom_reader_is_not_wrapped(self, tmp_path):
        endpoint = self.endpoint(tmp_path / "unused")
        read = endpoint.api.xcvr_eeprom
        reader = mock.Mock(return_value=bytearray(b"AB"))
        read.reader = reader
        with cpoutil._eeprom_read_snapshot() as attach:
            attach(endpoint, endpoint.api)
            assert read.reader is reader
            assert read.reader(0, 2) == bytearray(b"AB")
            assert read.reader(0, 2) == bytearray(b"AB")
        assert reader.call_count == 2


class TestApplicationEepromSnapshot:
    @pytest.mark.parametrize("api_kind", ["cmis", "bailly"])
    @pytest.mark.parametrize("port", [None, "Ethernet0"])
    @pytest.mark.parametrize("json_output", [False, True])
    def test_reuses_file_reads_without_changing_application_output(
            self, monkeypatch, tmp_path, api_kind, port, json_output):
        from types import SimpleNamespace
        from sonic_platform_base.sonic_xcvr.api.public.cmis import CmisApi
        from sonic_platform_base.sonic_xcvr.api.broadcom.bailly import BaillyApi
        from sonic_platform_base.sonic_xcvr.codes.broadcom.bailly import BaillyCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.broadcom.bailly import BaillyMemMap

        path = tmp_path / "eeprom"
        data = bytearray(1024 * 1024)
        path.write_bytes(data)
        entries, endpoints = [], []
        expected = {0: list(range(8)), 1: [0, 7, 6, 5, 4, 3, 2, 1]}
        api_class = CmisApi if api_kind == "cmis" else BaillyApi
        for index, bank in enumerate((0, 1, 0)):
            endpoint = DomOptoeEndpoint(path)
            mem_map = BaillyMemMap(BaillyCodes, bank=bank, base_page=0)
            for lane, application in enumerate(expected[bank], 1):
                field = mem_map.get_field("{}_0_{}".format(consts.STAGED_CTRL_APSEL_FIELD, lane))
                data[field.get_offset()] = application << 4
            endpoint.api = api_class(cpoutil.XcvrEeprom(
                endpoint.read_eeprom, endpoint.write_eeprom, mem_map))
            endpoints.append(endpoint)
            name = "Ethernet{}".format(index * 8)
            entries.append((name, index + 1, SimpleNamespace(oe=endpoint), name))
        path.write_bytes(data)
        monkeypatch.setattr(cpoutil, "get_port_cpo_entries", lambda selected: [
            entry for entry in entries if selected is None or entry[3] == selected
        ])
        # One breakout view and two full-bank views, including a shared bank.
        monkeypatch.setattr(cpoutil.cpo_mapping, "lane_positions", lambda name, port_config: (
            (0, 1, 2, 3) if name == "Ethernet0" else tuple(range(8))))
        arguments = ["show", "interface", "speed", "application"]
        if port is not None:
            arguments.extend(["-p", port])
        if json_output:
            arguments.append("--json")

        @contextmanager
        def no_snapshot():
            yield lambda endpoint, api: None

        with mock.patch.object(cpoutil, "_eeprom_read_snapshot", no_snapshot):
            with mock.patch("builtins.open", wraps=open) as opened:
                baseline = invoke(arguments)
                baseline_reads = opened.call_count
        with mock.patch("builtins.open", wraps=open) as opened:
            optimized = invoke(arguments)
            optimized_reads = opened.call_count
        assert baseline.exit_code == optimized.exit_code == 0, (baseline.output, optimized.output)
        assert baseline.output == optimized.output
        if api_kind == "cmis" and port is not None:
            # This single-bank public API path has no repeated addresses.
            assert optimized_reads == baseline_reads
        else:
            assert optimized_reads < baseline_reads
        for endpoint in endpoints:
            assert endpoint.api.xcvr_eeprom.reader == endpoint.read_eeprom
        if json_output:
            records = json.loads(optimized.output)
            assert records["Ethernet0"]["Application Select Controls"] == {
                "lane{:02d}".format(lane): expected[0][lane] for lane in range(4)
            }
            if port is None:
                assert records["Ethernet8"]["Application Select Controls"] == {
                    "lane{:02d}".format(lane): application for lane, application in enumerate(expected[1])
                }
                assert records["Ethernet16"]["Application Select Controls"] == {
                    "lane{:02d}".format(lane): application for lane, application in enumerate(expected[0])
                }


class TestLaneStatusEepromSnapshot:
    def setup_method(self):
        TestDirectPlatformApiCommands.setup_method(self)

    @pytest.mark.parametrize("port", [None, "Ethernet0"])
    @pytest.mark.parametrize("json_output", [False, True])
    def test_preserves_status_and_reduces_shared_oe_els_reads(self, tmp_path, port, json_output):
        from sonic_platform_base.sonic_xcvr.api.public.cmis import CmisApi
        from sonic_platform_base.sonic_xcvr.api.public.elsfp import ElsfpApi
        from sonic_platform_base.sonic_xcvr.codes.public.cmis import CmisCodes
        from sonic_platform_base.sonic_xcvr.codes.public.elsfp import ElsfpCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis import CmisMemMap
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.elsfp import ElsfpMemMap
        from sonic_platform_base.sonic_xcvr.fields import elsfp_consts

        path = tmp_path / "eeprom"
        data = bytearray(1024 * 1024)
        oe_map = CmisMemMap(CmisCodes, bank=0)
        els_map = ElsfpMemMap(ElsfpCodes, bank=0)
        # CMIS byte 3 bits 3:1 encode ModuleLowPwr as 1.
        data[els_map.get_field(consts.MODULE_STATE).get_offset()] = 1 << 1
        data[els_map.get_field(elsfp_consts.LANE_ENABLE_FIELD).get_offset()] = 0x0F
        path.write_bytes(data)
        oe, els = DomOptoeEndpoint(path), DomOptoeEndpoint(path)
        oe.api = CmisApi(cpoutil.XcvrEeprom(oe.read_eeprom, oe.write_eeprom, oe_map))
        els.api = ElsfpApi(cpoutil.XcvrEeprom(els.read_eeprom, els.write_eeprom, els_map))
        self.cpo.oe, self.cpo.elsfp = oe, els
        arguments = ["show", "interface", "lane-status"]
        if port is not None:
            arguments.extend(["-p", port])
        if json_output:
            arguments.append("--json")

        @contextmanager
        def no_snapshot():
            yield lambda endpoint, api: None

        with mock.patch.object(cpoutil, "_eeprom_read_snapshot", no_snapshot):
            with mock.patch("builtins.open", wraps=open) as opened:
                baseline = invoke(arguments)
                before_reads = opened.call_count
        with mock.patch("builtins.open", wraps=open) as opened:
            optimized = invoke(arguments)
            after_reads = opened.call_count
        assert baseline.exit_code == optimized.exit_code == 0, (baseline.output, optimized.output)
        assert baseline.output == optimized.output
        assert after_reads < before_reads
        for endpoint in (oe, els):
            assert endpoint.api.xcvr_eeprom.reader == endpoint.read_eeprom
        if json_output:
            records = json.loads(optimized.output)
            assert set(records) == ({"Ethernet0"} if port else {"Ethernet0", "Ethernet1"})
            assert records["Ethernet0"]["ELS Status"]["module_state"] == "ModuleLowPwr"


class TestReadOptimizations:
    def setup_method(self):
        TestDirectPlatformApiCommands.setup_method(self)

    @pytest.mark.parametrize("state, expected", [(True, True), (False, False)])
    @pytest.mark.parametrize("index", [None, "0"])
    @pytest.mark.parametrize("json_output", [False, True])
    def test_els_lpmode_reads_only_endpoint_hook(self, state, expected, index, json_output):
        arguments = ["show", "els", "lpmode"] + ([index] if index else [])
        if json_output:
            arguments.append("--json")
        with mock.patch.object(self.cpo, "get_lpmode", return_value=state) as read:
            with mock.patch.object(self.cpo.api, "get_elsfp_status", side_effect=AssertionError("aggregate read")):
                result = invoke(arguments)
        assert result.exit_code == 0, result.output
        read.assert_called_once_with()
        if json_output:
            assert json.loads(result.output) == {"els0": expected}
        else:
            assert ("On" if expected else "Off") in result.output

    @pytest.mark.parametrize("state", [None, "ModuleFault", "ModulePwrUp", "Unknown", ""])
    def test_els_lpmode_does_not_treat_unavailable_state_as_full_power(self, state):
        with mock.patch.object(self.cpo, "get_lpmode", return_value=state):
            result = invoke(["show", "els", "lpmode", "0", "--json"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    @pytest.mark.parametrize("port", [None, "Ethernet0"])
    @pytest.mark.parametrize("json_output", [False, True])
    def test_tx_disable_snapshot_preserves_output_and_reuses_shared_reads(self, tmp_path, port, json_output):
        from sonic_platform_base.sonic_xcvr.api.public.cmis import CmisApi
        from sonic_platform_base.sonic_xcvr.codes.public.cmis import CmisCodes
        from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis import CmisMemMap

        path = tmp_path / "eeprom"
        data = bytearray(1024 * 1024)
        mem_map = CmisMemMap(CmisCodes, bank=0)
        data[mem_map.get_field(consts.TX_DISABLE_FIELD).get_offset()] = 2
        path.write_bytes(data)
        endpoint = DomOptoeEndpoint(path)
        endpoint.api = CmisApi(cpoutil.XcvrEeprom(endpoint.read_eeprom, endpoint.write_eeprom, mem_map))
        endpoint.api.get_tx_disable_support = lambda: True
        self.cpo.oe = endpoint
        self.cpo.get_tx_disable = mock.Mock(side_effect=endpoint.api.get_tx_disable)
        arguments = ["show", "interface", "tx-disable"] + (["-p", port] if port else [])
        if json_output:
            arguments.append("--json")

        @contextmanager
        def no_snapshot():
            yield lambda endpoint, api=None: None

        with mock.patch.object(cpoutil, "_eeprom_read_snapshot", no_snapshot):
            with mock.patch("builtins.open", wraps=open) as opened:
                baseline = invoke(arguments)
                baseline_reads = opened.call_count
        with mock.patch("builtins.open", wraps=open) as opened:
            optimized = invoke(arguments)
            optimized_reads = opened.call_count
        assert baseline.exit_code == optimized.exit_code == 0, (baseline.output, optimized.output)
        assert baseline.output == optimized.output
        assert optimized_reads <= baseline_reads
        if port is None:
            assert optimized_reads < baseline_reads
        assert endpoint.api.xcvr_eeprom.reader == endpoint.read_eeprom

    def test_optional_snapshot_api_failure_preserves_platform_hook(self, tmp_path):
        endpoint = DomOptoeEndpoint(tmp_path / "unused")
        endpoint.get_api = mock.Mock(side_effect=RuntimeError("API unavailable"))
        self.cpo.oe = endpoint
        self.cpo.get_tx_disable = mock.Mock(return_value=[False, True])
        result = invoke(["show", "interface", "tx-disable", "-p", "Ethernet0", "--json"])
        assert result.exit_code == 0, result.output
        self.cpo.get_tx_disable.assert_called_once_with()
