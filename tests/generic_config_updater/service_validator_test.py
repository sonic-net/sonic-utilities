import copy
import json
import jsondiff
import os
import unittest
from collections import defaultdict
from unittest.mock import patch

from generic_config_updater.services_validator import vlan_validator, rsyslog_validator, caclmgrd_validator, vlanintf_validator
import generic_config_updater.gu_common
from generic_config_updater.services_validator import ntp_validator

# Mimics subprocess.run call
#
subprocess_calls = []
subprocess_call_index = 0
time_sleep_calls = []
time_sleep_call_index = 0
msg = ""


class MockSubprocessResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def mock_subprocess_run(cmd_args, capture_output=False, check=False, text=True):
    global subprocess_calls, subprocess_call_index

    assert subprocess_call_index < len(subprocess_calls)
    entry = subprocess_calls[subprocess_call_index]
    subprocess_call_index += 1

    # Convert cmd_args list back to string for comparison
    cmd_str = ' '.join(cmd_args)
    assert cmd_str == entry["cmd"], msg

    # Get stdout and stderr from entry, default to empty strings
    stdout = entry.get("stdout", "")
    stderr = entry.get("stderr", "")

    return MockSubprocessResult(entry["rc"], stdout, stderr)


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


test_ntp_data = [
        {
            "old": {
                "NTP_SERVER": {
                    "0.pool.ntp.org": {}
                    }
                },
            "upd": {
                "NTP_SERVER": {
                    "0.pool.ntp.org": {},
                    "1.pool.ntp.org": {}
                    }
                },
            "cmd": "systemctl restart chrony"
        }
   ]


test_vlanintf_failure_data = [
        {
            "old": {
                "VLAN_INTERFACE": {
                    "Vlan9999": {},
                    "Vlan9999|192.168.99.1/24": {}
                }
            },
            "upd": {},
            "cmd": "ip neigh flush dev Vlan9999 192.168.99.1/24",
            "rc": 1,
            "stderr": "Cannot find device \"Vlan9999\"\n",
            "expected_result": False,
            "description": "VLAN interface not found - command fails with stderr"
        },
        {
            "old": {
                "VLAN_INTERFACE": {
                    "Vlan1000": {},
                    "Vlan1000|192.168.0.1/21": {},
                    "Vlan9999": {},
                    "Vlan9999|10.10.10.1/24": {}
                }
            },
            "upd": {
                "VLAN_INTERFACE": {
                    "Vlan1000": {},
                    "Vlan1000|192.168.0.1/21": {}
                }
            },
            "cmd": "ip neigh flush dev Vlan9999 10.10.10.1/24",
            "rc": 255,
            "stdout": "Flushing neighbors...\n",
            "stderr": "Device \"Vlan9999\" does not exist.\n",
            "expected_result": False,
            "description": "Non-existent VLAN deletion fails with both stdout and stderr"
        }
   ]


class TestServiceValidator(unittest.TestCase):

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_change_apply_subprocess_run(self, mock_subprocess):
        global subprocess_calls, subprocess_call_index

        mock_subprocess.side_effect = mock_subprocess_run

        for entry in test_data:
            if entry["cmd"]:
                subprocess_calls.append({"cmd": entry["cmd"], "rc": 0})
            msg = "case failed: {}".format(str(entry))

            vlan_validator(entry["old"], entry["upd"], None)

        subprocess_calls = []
        subprocess_call_index = 0
        for entry in test_rsyslog_data:
            if entry["cmd"]:
                for c in entry["cmd"].split(","):
                    subprocess_calls.append({"cmd": c, "rc": 0})
            msg = "case failed: {}".format(str(entry))

            rsyslog_validator(entry["old"], entry["upd"], None)

        subprocess_calls = []
        subprocess_call_index = 0
        for entry in test_vlanintf_data:
            if entry["cmd"]:
                subprocess_calls.append({"cmd": entry["cmd"], "rc": 0})
            msg = "case failed: {}".format(str(entry))

            vlanintf_validator(entry["old"], entry["upd"], None)

        subprocess_calls = []
        subprocess_call_index = 0
        for entry in test_ntp_data:
            if entry["cmd"]:
                for c in entry["cmd"].split(","):
                    subprocess_calls.append({"cmd": c, "rc": 0})

            ntp_validator(entry["old"], entry["upd"], None)

    @patch("generic_config_updater.services_validator.time.sleep")
    def test_change_apply_time_sleep(self, mock_time_sleep):
        global time_sleep_calls, time_sleep_call_index

        mock_time_sleep.side_effect = mock_time_sleep_call

        for entry in test_caclrule:
            if entry["sleep_time"]:
                time_sleep_calls.append({"sleep_time": entry["sleep_time"]})
            msg = "case failed: {}".format(str(entry))

            caclmgrd_validator(entry["old"], entry["upd"], None)

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_vlanintf_validator_failure_vlan_not_found(self, mock_subprocess):
        """Test vlanintf_validator when trying to flush neighbors on non-existent VLAN"""
        global subprocess_calls, subprocess_call_index

        mock_subprocess.side_effect = mock_subprocess_run

        for entry in test_vlanintf_failure_data:
            subprocess_calls = []
            subprocess_call_index = 0

            if entry["cmd"]:
                call_entry = {"cmd": entry["cmd"], "rc": entry["rc"]}
                if "stdout" in entry:
                    call_entry["stdout"] = entry["stdout"]
                if "stderr" in entry:
                    call_entry["stderr"] = entry["stderr"]
                subprocess_calls.append(call_entry)

            msg = "case failed: {} - {}".format(entry["description"], str(entry))

            result = vlanintf_validator(entry["old"], entry["upd"], None)

            assert result == entry["expected_result"], \
                f"{msg} - Expected {entry['expected_result']} but got {result}"
