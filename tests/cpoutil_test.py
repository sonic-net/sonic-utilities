import json
import os
import sys
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
        with mock.patch(
                "sonic_py_common.device_info.get_cpo_data",
                return_value=CPO_DATA):
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
