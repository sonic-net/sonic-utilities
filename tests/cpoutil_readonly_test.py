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
        return 71.25

    def get_rx_power(self):
        return [1.1, 1.2]

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

    def get_rlm_status(self):
        return {
            "els_module_low_power_state": False,
            "els_interrupt_status": True,
        }

    def get_rlm_temperature(self):
        return 32.5

    def get_rlm_laser_power(self):
        return {
            "Laser0OpticalPowerMonitor": 9.1,
            "Laser1OpticalPowerMonitor": 9.2,
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

    def test_els_commands_call_bailly_rlm_api(self):
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

    def test_els_presence_calls_cpo_object(self):
        result = invoke(["show", "els", "presence", "0", "--json"])
        assert json.loads(result.output) == {"els0": True}

    def test_interface_dom_calls_cpo_methods(self):
        result = invoke([
            "show", "interface", "dom", "Ethernet0", "--json"
        ])
        values = json.loads(result.output)["Ethernet0"]
        assert values["manufacturer"] == "Example OE"
        assert values["RLM0_temperature"] == 32.5
        assert values["temphighalarm"] == 90.0

    def test_interface_tx_disable_supports_breakout_name(self):
        result = invoke([
            "show", "interface", "tx_disable", "Ethernet1", "--json"
        ])
        assert json.loads(result.output) == {
            "Ethernet1": {
                "lane01": "Tx output disable",
            }
        }

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

    def test_interface_lane_status_uses_existing_bailly_api(self):
        result = invoke([
            "show", "interface", "lane-status", "Ethernet0", "--json"
        ])
        values = json.loads(result.output)["Ethernet0"]
        assert values["Data Path State Indicator"]["lane00"] == \
            "DataPathActivated"
        assert values["ELS Status"]["els_interrupt_status"] is True

    def test_unknown_resource_is_rejected(self):
        result = invoke(["show", "oe", "status", "99"])
        assert result.exit_code != 0
        assert "Invalid oe index '99'" in result.output
