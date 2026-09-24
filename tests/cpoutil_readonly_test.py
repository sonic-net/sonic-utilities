import json
import os
import sys
from unittest import mock

from click.testing import CliRunner


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
    "elss": {"els0": {"index": 0, "base_page": 0}},
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


class FakeApi(object):
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
            "els_module_low_power_state": False,
            "els_interrupt_status": True,
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


class FakeCpo(object):
    def __init__(self):
        self.api = FakeApi()

    def get_xcvr_api(self):
        return self.api

    def get_presence(self):
        return True

    def get_els_presence(self):
        return True

    def get_transceiver_info(self):
        return {"manufacturer": "Example OE"}

    def get_transceiver_dom_real_value(self):
        return {"temperature": 71.25, "RLM0_temperature": 32.5}

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

    def test_els_presence_calls_cpo_object(self):
        result = invoke(["show", "els", "presence", "0", "--json"])
        assert json.loads(result.output) == {"els0": True}

        table = invoke(["show", "els", "presence", "0"])
        assert "Present" in table.output

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
        values = json.loads(result.output)["Ethernet0"]
        assert values["manufacturer"] == "Example OE"
        assert values["els_vendor_name"] == "Example ELS"
        assert values["els_temperature"] == 32.5
        assert values["temphighalarm"] == 90.0
        assert values["els_temperature_alarm_high"] == 75.0
        assert isinstance(values["temperature"], float)

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

    def test_interrupt_event_normalizes_bailly_polarity(self):
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
            "does not report an independent ELS module state"
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
