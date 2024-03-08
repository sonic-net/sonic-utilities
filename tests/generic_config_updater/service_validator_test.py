import copy
import json
import jsondiff
import os
import unittest
from collections import defaultdict
from unittest.mock import patch

from generic_config_updater.services_validator import vlan_validator, rsyslog_validator, caclmgrd_validator, vlanintf_validator
import generic_config_updater.gu_common


# Mimics os.system call
#
os_system_calls = []
os_system_call_index = 0
time_sleep_calls = []
time_sleep_call_index = 0
msg = ""

def mock_os_system_call(cmd):
    global os_system_calls, os_system_call_index

    assert os_system_call_index < len(os_system_calls)
    entry = os_system_calls[os_system_call_index]
    os_system_call_index += 1

    assert cmd == entry["cmd"], msg
    return entry["rc"]

def mock_time_sleep_call(sleep_time):
    global time_sleep_calls, time_sleep_call_index

    assert time_sleep_call_index < len(time_sleep_calls)
    entry = time_sleep_calls[time_sleep_call_index]
    time_sleep_call_index += 1

    assert sleep_time == entry["sleep_time"], msg


test_data = [
        { "old": {}, "upd": {}, "cmd": "" },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "cmd": ""
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.11" ] } } },
            "cmd": "systemctl restart dhcp_relay"
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": {
                "XXX": { "dhcp_servers": [ "10.10.10.10" ] },
                "YYY": { "dhcp_servers": [ ] } } },
            "cmd": ""
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": {
                "XXX": { "dhcp_servers": [ "10.10.10.10" ] },
                "YYY": { "dhcp_servers": [ "10.12.12.1" ] } } },
            "cmd": "systemctl restart dhcp_relay"
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": {},
            "cmd": "systemctl restart dhcp_relay"
        }
    ]

test_caclrule = [
        { "old": {}, "upd": {}, "sleep_time": 0 },
        {
            "old": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": { "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" } }
            },
            "upd": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": { "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" } }
            },
            "sleep_time": 0
        },
        {
            "old": {
                "ACL_TABLE": {
                    "XXX": { "type": "CTRLPLANE" },
                    "YYY": { "type": "L3" }
                },
                "ACL_RULE": {
                    "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" },
                    "YYY|RULE_1": { "SRC_IP": "192.168.1.10/32" }
                }
            },
            "upd": {
                "ACL_TABLE": {
                    "XXX": { "type": "CTRLPLANE" }
                },
                "ACL_RULE": {
                    "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" }
                }
            },
            "sleep_time": 0
        },
        {
            "old": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": { "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" } }
            },
            "upd": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": { "XXX|RULE_1": { "SRC_IP": "11.11.11.11/16" } }
            },
            "sleep_time": 1
        },
        {
            "old": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": {
                    "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" }
                }
            },
            "upd": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": {
                    "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" },
                    "XXX|RULE_2": { "SRC_IP": "12.12.12.12/16" }
                }
            },
            "sleep_time": 1
        },
        {
            "old": {
                "ACL_TABLE": { "XXX": { "type": "CTRLPLANE" } },
                "ACL_RULE": { "XXX|RULE_1": { "SRC_IP": "10.10.10.10/16" } }
            },
            "upd": {},
            "sleep_time": 1
        },
    ]


test_rsyslog_data = [
        { "old": {}, "upd": {}, "cmd": "" },
        {
            "old": { "SYSLOG_SERVER": {
                "10.13.14.17": {},
                "2001:aa:aa::aa": {} } },
            "upd": { "SYSLOG_SERVER": {
                "10.13.14.17": {},
                "2001:aa:aa::aa": {} } },
            "cmd": ""
        },
        {
            "old": { "SYSLOG_SERVER": {
                "10.13.14.17": {} } },
            "upd": { "SYSLOG_SERVER": {
                "10.13.14.18": {} } },
            "cmd": "systemctl reset-failed rsyslog-config rsyslog,systemctl restart rsyslog-config"
        },
        {
            "old": { "SYSLOG_SERVER": {
                "10.13.14.17": {} } },
            "upd": { "SYSLOG_SERVER": {
                "10.13.14.17": {},
                "2001:aa:aa::aa": {} } },
            "cmd": "systemctl reset-failed rsyslog-config rsyslog,systemctl restart rsyslog-config"
        },
        {
            "old": { "SYSLOG_SERVER": {
                "10.13.14.17": {} } },
            "upd": {},
            "cmd": "systemctl reset-failed rsyslog-config rsyslog,systemctl restart rsyslog-config"
        }
    ]

test_vlanintf_data = [
        { "old": {}, "upd": {}, "cmd": "" },
        {
            "old": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.1/21": {} } },
            "upd": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.1/21": {} } },
            "cmd": ""
        },
        {
            "old": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.1/21": {} } },
            "upd": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.2/21": {} } },
            "cmd": "ip neigh flush dev Vlan1000 192.168.0.1/21"
        },
        {
            "old": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.1/21": {} } },
            "upd": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.1/21": {},
                "Vlan1000|192.168.0.2/21": {} } },
            "cmd": ""
        },
        {
            "old": { "VLAN_INTERFACE": {
                "Vlan1000": {},
                "Vlan1000|192.168.0.1/21": {} } },
            "upd": {},
            "cmd": "ip neigh flush dev Vlan1000 192.168.0.1/21"
        }
   ]


class TestServiceValidator(unittest.TestCase):

    @patch("generic_config_updater.change_applier.os.system")
    def test_change_apply_os_system(self, mock_os_sys):
        global os_system_calls, os_system_call_index

        mock_os_sys.side_effect = mock_os_system_call

        for entry in test_data:
            if entry["cmd"]:
                os_system_calls.append({"cmd": entry["cmd"], "rc": 0 })
            msg = "case failed: {}".format(str(entry))

            vlan_validator(entry["old"], entry["upd"], None)


        os_system_calls = []
        os_system_call_index = 0
        for entry in test_rsyslog_data:
            if entry["cmd"]:
                for c in entry["cmd"].split(","):
                    os_system_calls.append({"cmd": c, "rc": 0})
            msg = "case failed: {}".format(str(entry))

            rsyslog_validator(entry["old"], entry["upd"], None)


        os_system_calls = []
        os_system_call_index = 0
        for entry in test_vlanintf_data:
            if entry["cmd"]:
                os_system_calls.append({"cmd": entry["cmd"], "rc": 0 })
            msg = "case failed: {}".format(str(entry))

            vlanintf_validator(entry["old"], entry["upd"], None)

    @patch("generic_config_updater.services_validator.time.sleep")
    def test_change_apply_time_sleep(self, mock_time_sleep):
        global time_sleep_calls, time_sleep_call_index

        mock_time_sleep.side_effect = mock_time_sleep_call

        for entry in test_caclrule:
            if entry["sleep_time"]:
                time_sleep_calls.append({"sleep_time": entry["sleep_time"]})
            msg = "case failed: {}".format(str(entry))

            caclmgrd_validator(entry["old"], entry["upd"], None)

