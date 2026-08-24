import unittest
from unittest.mock import patch

from generic_config_updater.services_validator import (
    vlan_validator,
    rsyslog_validator,
    caclmgrd_validator,
    vlanintf_validator,
    port_speed_change_validator,
)
from generic_config_updater.services_validator import ntp_validator
from generic_config_updater.services_validator import gnmi_validator, telemetry_validator
from generic_config_updater.services_validator import frr_routing_mode_validator

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

    # Convert cmd_args list back to string for comparison.
    cmd_str = ' '.join(cmd_args)
    assert entry["cmd"] in cmd_str, msg

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


test_gnmi_data = [
        {"old": {}, "upd": {}, "cmd": ""},
        {
            "old": {"GNMI": {"gnmi": {"port": "50052"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50053"}}},
            "cmd": ""
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "default"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "default"}}},
            "cmd": ""
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "default"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "cmd": "systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "cmd": "systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052"}}},
            "cmd": "systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "default"}}},
            "cmd": "systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "cmd": ""
        }
    ]


test_telemetry_data = [
        {"old": {}, "upd": {}, "cmd": ""},
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50052"}}},
            "cmd": ""
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "default"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "default"}}},
            "cmd": ""
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "default"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "cmd": "systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "cmd": "systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051"}}},
            "cmd": "systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "default"}}},
            "cmd": "systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "cmd": ""
        }
    ]


RESTART_BGP = "systemctl reset-failed bgp,systemctl restart bgp"

test_frr_routing_mode_data = [
        # Both empty — no restart
        {"old": {}, "upd": {}, "cmd": ""},
        # DEVICE_METADATA present but neither startup field changed — no restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {"hostname": "sonic"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {"hostname": "switch"}}},
            "cmd": ""
        },
        # frr_mgmt_framework_config flipped false -> true — restart bgp
        {
            "old": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "false"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "true"}}},
            "cmd": RESTART_BGP
        },
        # frr_mgmt_framework_config added where none existed (default "false") -> "true" — restart bgp
        {
            "old": {"DEVICE_METADATA": {"localhost": {}}},
            "upd": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "true"}}},
            "cmd": RESTART_BGP
        },
        # frr_mgmt_framework_config added but equals the default "false" — no restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {}}},
            "upd": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "false"}}},
            "cmd": ""
        },
        # frr_mgmt_framework_config removed (was "true", default "false") — restart bgp
        {
            "old": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "true"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {}}},
            "cmd": RESTART_BGP
        },
        # docker_routing_config_mode separated -> unified — restart bgp
        {
            "old": {"DEVICE_METADATA": {"localhost": {"docker_routing_config_mode": "separated"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {"docker_routing_config_mode": "unified"}}},
            "cmd": RESTART_BGP
        },
        # docker_routing_config_mode added where none existed (default "separated") — no restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {}}},
            "upd": {"DEVICE_METADATA": {"localhost": {"docker_routing_config_mode": "separated"}}},
            "cmd": ""
        },
        # docker_routing_config_mode removed (was "unified", default "separated") — restart bgp
        {
            "old": {"DEVICE_METADATA": {"localhost": {"docker_routing_config_mode": "unified"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {}}},
            "cmd": RESTART_BGP
        },
        # docker_routing_config_mode unchanged, unrelated field changed — no restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {
                "docker_routing_config_mode": "unified", "buffer_model": "traditional"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {
                "docker_routing_config_mode": "unified", "buffer_model": "dynamic"}}},
            "cmd": ""
        },
        # Both startup fields change together — single restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {
                "docker_routing_config_mode": "separated", "frr_mgmt_framework_config": "false"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {
                "docker_routing_config_mode": "unified", "frr_mgmt_framework_config": "true"}}},
            "cmd": RESTART_BGP
        },
        # DEVICE_METADATA table entirely absent from upd, old had non-default field — restart bgp
        {
            "old": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "true"}}},
            "upd": {},
            "cmd": RESTART_BGP
        },
        # DEVICE_METADATA table absent from old, added in upd with non-default field — restart bgp
        {
            "old": {},
            "upd": {"DEVICE_METADATA": {"localhost": {"docker_routing_config_mode": "unified"}}},
            "cmd": RESTART_BGP
        },
        # frr_mgmt_framework_config removed while at its default ("false") — no restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {"frr_mgmt_framework_config": "false"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {}}},
            "cmd": ""
        },
        # docker_routing_config_mode removed while at its default ("separated") — no restart
        {
            "old": {"DEVICE_METADATA": {"localhost": {"docker_routing_config_mode": "separated"}}},
            "upd": {"DEVICE_METADATA": {"localhost": {}}},
            "cmd": ""
        },
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

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_port_speed_change_validator(self, mock_subprocess):
        """Test port_speed_change_validator for port speed changes and no changes"""
        global subprocess_calls, subprocess_call_index

        mock_subprocess.side_effect = mock_subprocess_run

        # Case 1: No speed change, should not call systemctl
        old_config = {"PORT": {"Ethernet0": {"speed": "100000"}}}
        upd_config = {"PORT": {"Ethernet0": {"speed": "100000"}}}
        subprocess_calls = []
        subprocess_call_index = 0
        result = port_speed_change_validator(old_config, upd_config, None)
        self.assertTrue(result)

        # Case 2: Speed changed, successful restart
        old_config = {"PORT": {"Ethernet0": {"speed": "100000"}}}
        upd_config = {"PORT": {"Ethernet0": {"speed": "400000"}}}
        subprocess_calls = [{
            "cmd": "nsenter --target 1 --pid --mount --uts --ipc --net systemctl restart telemetry",
            "rc": 0
        }]
        subprocess_call_index = 0
        result = port_speed_change_validator(old_config, upd_config, None)
        self.assertTrue(result)
        self.assertEqual(subprocess_call_index, 1)

        # Case 2b: Speed changed, restart fails then succeeds after reset-failed
        old_config = {"PORT": {"Ethernet0": {"speed": "100000"}}}
        upd_config = {"PORT": {"Ethernet0": {"speed": "400000"}}}
        subprocess_calls = [
            {"cmd": "nsenter --target 1 --pid --mount --uts --ipc --net systemctl restart telemetry", "rc": 1},
            {"cmd": "nsenter --target 1 --pid --mount --uts --ipc --net systemctl reset-failed telemetry", "rc": 0},
            {"cmd": "nsenter --target 1 --pid --mount --uts --ipc --net systemctl restart telemetry", "rc": 0}
        ]
        subprocess_call_index = 0
        result = port_speed_change_validator(old_config, upd_config, None)
        self.assertTrue(result)
        self.assertEqual(subprocess_call_index, 3)

        # Case 3: Port added with speed, should not restart (no old speed to compare)
        old_config = {"PORT": {}}
        upd_config = {"PORT": {"Ethernet1": {"speed": "100000"}}}
        subprocess_calls = []
        subprocess_call_index = 0
        result = port_speed_change_validator(old_config, upd_config, None)
        self.assertTrue(result)

        # Case 4: Port removed, should not restart
        old_config = {"PORT": {"Ethernet2": {"speed": "100000"}}}
        upd_config = {"PORT": {}}
        subprocess_calls = []
        subprocess_call_index = 0
        result = port_speed_change_validator(old_config, upd_config, None)
        self.assertTrue(result)

        # Case 5: Multiple ports, one speed changed (with nsenter)
        old_config = {"PORT": {"Ethernet0": {"speed": "100000"}, "Ethernet1": {"speed": "400000"}}}
        upd_config = {"PORT": {"Ethernet0": {"speed": "400000"}, "Ethernet1": {"speed": "400000"}}}
        subprocess_calls = [{
            "cmd": "nsenter --target 1 --pid --mount --uts --ipc --net systemctl restart telemetry",
            "rc": 0
        }]
        subprocess_call_index = 0
        result = port_speed_change_validator(old_config, upd_config, None)
        self.assertTrue(result)
        self.assertEqual(subprocess_call_index, 1)

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

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_gnmi_validator(self, mock_subprocess):
        """Test gnmi_validator restarts gnmi service on VRF change"""
        global subprocess_calls, subprocess_call_index

        mock_subprocess.side_effect = mock_subprocess_run

        for entry in test_gnmi_data:
            subprocess_calls = []
            subprocess_call_index = 0

            if entry["cmd"]:
                subprocess_calls.append({"cmd": entry["cmd"], "rc": 0})

            result = gnmi_validator(entry["old"], entry["upd"], None)
            assert result, "gnmi_validator failed: {}".format(str(entry))

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_telemetry_validator(self, mock_subprocess):
        """Test telemetry_validator restarts telemetry service on VRF change"""
        global subprocess_calls, subprocess_call_index

        mock_subprocess.side_effect = mock_subprocess_run

        for entry in test_telemetry_data:
            subprocess_calls = []
            subprocess_call_index = 0

            if entry["cmd"]:
                subprocess_calls.append({"cmd": entry["cmd"], "rc": 0})

            result = telemetry_validator(entry["old"], entry["upd"], None)
            assert result, "telemetry_validator failed: {}".format(str(entry))

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_frr_routing_mode_validator(self, mock_subprocess):
        """Test frr_routing_mode_validator restarts the bgp container when the
        startup-only DEVICE_METADATA fields docker_routing_config_mode or
        frr_mgmt_framework_config change.

        On a change the validator first issues `systemctl reset-failed bgp` (to
        clear systemd's StartLimit counter) and only then `systemctl restart bgp`.
        Both calls must appear in the expected order. Absent fields are compared
        against their startup defaults, so adding/removing a field only restarts
        when it actually changes the effective value.
        """
        global subprocess_calls, subprocess_call_index

        mock_subprocess.side_effect = mock_subprocess_run

        for entry in test_frr_routing_mode_data:
            subprocess_calls = []
            subprocess_call_index = 0

            if entry["cmd"]:
                for c in entry["cmd"].split(","):
                    subprocess_calls.append({"cmd": c, "rc": 0})

            result = frr_routing_mode_validator(entry["old"], entry["upd"], None)
            assert result, "frr_routing_mode_validator failed: {}".format(str(entry))
            # Ensure exactly the expected number of subprocess calls fired
            # (0 when no restart is expected).
            expected = len(entry["cmd"].split(",")) if entry["cmd"] else 0
            self.assertEqual(subprocess_call_index, expected,
                             "unexpected call count for: {}".format(str(entry)))
