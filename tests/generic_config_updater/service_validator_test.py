import json
import os
import unittest
from unittest.mock import call, patch

from generic_config_updater.services_validator import (
    command_wrapper,
    _service_restart,
    caclmgrd_validator,
    vlanintf_validator,
)
import generic_config_updater.change_applier
from generic_config_updater.change_applier import ChangeApplier

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


test_vlan_data = [
        { "old": {}, "upd": {}, "cmd": "" },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "cmd": ""
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.11" ] } } },
            "cmd": "systemctl reset-failed dhcp_relay,systemctl restart dhcp_relay"
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
            "cmd": "systemctl reset-failed dhcp_relay,systemctl restart dhcp_relay"
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": {},
            "cmd": "systemctl reset-failed dhcp_relay,systemctl restart dhcp_relay"
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
            "cmd": "systemctl reset-failed chrony,systemctl restart chrony"
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
        },
        {
            "old": {
                "VLAN_INTERFACE": {
                    "Vlan1000": {},
                    "Vlan1000|192.168.0.1/21": {}
                }
            },
            "upd": {},
            "cmd": "ip neigh flush dev Vlan1000 192.168.0.1/21",
            "rc": 2,
            "stderr": "RTNETLINK answers: No such file or directory\n",
            "expected_result": True,
            "description": "Stale-neighbor race: kernel RTNETLINK ENOENT is tolerated"
        },
        {
            "old": {
                "VLAN_INTERFACE": {
                    "Vlan1000": {},
                    "Vlan1000|192.168.0.1/21": {}
                }
            },
            "upd": {},
            "cmd": "ip neigh flush dev Vlan1000 192.168.0.1/21",
            "rc": 127,
            "stderr": "sh: ip: No such file or directory\n",
            "expected_result": False,
            "description": "Generic ENOENT (missing binary) must not be tolerated"
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
            "cmd": "systemctl reset-failed gnmi,systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "cmd": "systemctl reset-failed gnmi,systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052"}}},
            "cmd": "systemctl reset-failed gnmi,systemctl restart gnmi"
        },
        {
            "old": {"GNMI": {"gnmi": {"port": "50052", "vrf": "mgmt"}}},
            "upd": {"GNMI": {"gnmi": {"port": "50052", "vrf": "default"}}},
            "cmd": "systemctl reset-failed gnmi,systemctl restart gnmi"
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
            "cmd": "systemctl reset-failed telemetry,systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "cmd": "systemctl reset-failed telemetry,systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051"}}},
            "cmd": "systemctl reset-failed telemetry,systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "default"}}},
            "cmd": "systemctl reset-failed telemetry,systemctl restart telemetry"
        },
        {
            "old": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "upd": {"TELEMETRY": {"gnmi": {"port": "50051", "vrf": "mgmt"}}},
            "cmd": ""
        }
    ]


test_dhcp_data = [
        {
            "old": {"DHCP_RELAY": {"Vlan1000": {}}},
            "upd": {"DHCP_RELAY": {"Vlan1000": {}, "Vlan2000": {}}},
            "cmd": "systemctl reset-failed dhcp_relay,systemctl restart dhcp_relay"
        },
        {
            "old": {"DHCP_SERVER": {"Vlan1000": {"state": "enabled"}}},
            "upd": {"DHCP_SERVER": {"Vlan1000": {"state": "disabled"}}},
            "cmd": "systemctl reset-failed dhcp_relay,systemctl restart dhcp_relay"
        }
    ]

RESTART_BGP = "systemctl reset-failed bgp,systemctl restart bgp"
RESTART_SWSS = "systemctl reset-failed swss syncd,systemctl restart swss"
RESTART_DHCP_RELAY = "systemctl reset-failed dhcp_relay,systemctl restart dhcp_relay"

# DEVICE_METADATA|localhost fields read only when a service starts: field, unit restart, a non-default value
DEVICE_METADATA_RESTART_FIELDS = [
    ("bgp_asn", RESTART_BGP, "65100"),
    ("bgp_router_id", RESTART_BGP, "10.1.0.1"),
    ("bgp_adv_lo_prefix_as_128", RESTART_BGP, "true"),
    ("default_bgp_status", RESTART_BGP, "down"),
    ("deployment_id", RESTART_BGP + "," + RESTART_DHCP_RELAY, "8"),
    ("docker_routing_config_mode", RESTART_BGP, "unified"),
    ("frr_mgmt_framework_config", RESTART_BGP, "true"),
    ("nexthop_group", RESTART_BGP, "enabled"),
    ("zebra_nexthop", RESTART_BGP, "disabled"),
    ("mac", RESTART_SWSS, "e8:e4:9d:12:ad:d2"),
    ("synchronous_mode", RESTART_SWSS, "disable"),
    ("buffer_model", RESTART_SWSS, "dynamic"),
    ("switch_id", RESTART_SWSS, "2"),
    ("max_cores", RESTART_SWSS, "48"),
    ("ring_thread_enabled", RESTART_SWSS, "true"),
    ("orch_northbond_dash_zmq_enabled", RESTART_SWSS, "false"),
    ("suppress-fib-pending", RESTART_SWSS, "enabled"),
    ("has_sonic_dhcpv4_relay", RESTART_DHCP_RELAY, "True"),
]

test_device_metadata_data = [
    {"old": {"DEVICE_METADATA": {"localhost": {"hostname": "sw1"}}},
     "upd": {"DEVICE_METADATA": {"localhost": {"hostname": "sw1", field: value}}},
     "cmd": cmd}
    for field, cmd, value in DEVICE_METADATA_RESTART_FIELDS
] + [
    # Applied live, or not handled by a restart: no restart
    {"old": {"DEVICE_METADATA": {"localhost": {"hostname": "sw1", "timezone": "UTC", "default_lacp_mode": "coupled"}}},
     "upd": {"DEVICE_METADATA": {"localhost": {"hostname": "sw2", "timezone": "Etc/GMT+8",
                                               "default_lacp_mode": "independent"}}},
     "cmd": ""},
    # Fields set to the value the services use when they are absent: no restart
    {"old": {"DEVICE_METADATA": {"localhost": {"hostname": "sw1"}}},
     "upd": {"DEVICE_METADATA": {"localhost": {
         "hostname": "sw1", "synchronous_mode": "enable", "buffer_model": "traditional",
         "ring_thread_enabled": "false", "orch_northbond_dash_zmq_enabled": "true",
         "suppress-fib-pending": "disabled", "default_bgp_status": "up", "nexthop_group": "disabled",
         "zebra_nexthop": "enabled", "bgp_adv_lo_prefix_as_128": "false",
         "has_sonic_dhcpv4_relay": "False"}}},
     "cmd": ""},
    # One restart per unit, swss first since it restarts its dependents
    {"old": {"DEVICE_METADATA": {"localhost": {"bgp_asn": "65100", "synchronous_mode": "enable"}}},
     "upd": {"DEVICE_METADATA": {"localhost": {"bgp_asn": "65200", "bgp_router_id": "10.1.0.1",
                                               "synchronous_mode": "disable", "buffer_model": "dynamic",
                                               "deployment_id": "8"}}},
     "cmd": RESTART_SWSS + "," + RESTART_BGP + "," + RESTART_DHCP_RELAY},
]


test_port_speed_data = [
        {"old": {"PORT": {"Ethernet0": {"speed": "100000"}}},
         "upd": {"PORT": {"Ethernet0": {"speed": "100000"}}},
         "cmd": ""},
        {"old": {"PORT": {"Ethernet0": {"speed": "100000"}}},
         "upd": {"PORT": {"Ethernet0": {"speed": "400000"}}},
         "cmd": "systemctl reset-failed telemetry,systemctl restart telemetry"},
        # A port added or removed, or a speed set or cleared, is not a speed change.
        {"old": {"PORT": {}}, "upd": {"PORT": {"Ethernet1": {"speed": "100000"}}}, "cmd": ""},
        {"old": {"PORT": {"Ethernet2": {"speed": "100000"}}}, "upd": {"PORT": {}}, "cmd": ""},
        {"old": {"PORT": {"Ethernet0": {"mtu": "9100"}}},
         "upd": {"PORT": {"Ethernet0": {"mtu": "9100", "speed": "100000"}}},
         "cmd": ""},
        {"old": {"PORT": {"Ethernet0": {"speed": "100000"}, "Ethernet1": {"speed": "400000"}}},
         "upd": {"PORT": {"Ethernet0": {"speed": "400000"}, "Ethernet1": {"speed": "100000"}}},
         "cmd": "systemctl reset-failed telemetry,systemctl restart telemetry"},
    ]


class TestServiceValidator(unittest.TestCase):

    @patch("generic_config_updater.services_validator.logger")
    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_command_wrapper_logs_stable_command_format(self, mock_subprocess, mock_logger):
        mock_subprocess.return_value = MockSubprocessResult(1)

        result = command_wrapper(["systemctl", "restart", "dhcp_relay"])

        self.assertEqual(result, 1)
        mock_logger.log.assert_called_once_with(
            mock_logger.LOG_PRIORITY_ERROR,
            "Command failed: 'nsenter --target 1 --pid --mount --uts --ipc --net "
            "systemctl restart dhcp_relay', returncode: 1",
            False
        )

        mock_logger.reset_mock()
        mock_subprocess.side_effect = OSError("execution error")

        result = command_wrapper(["systemctl", "restart", "dhcp_relay"])

        self.assertEqual(result, 1)
        mock_logger.log.assert_called_once_with(
            mock_logger.LOG_PRIORITY_ERROR,
            "Command execution failed: 'nsenter --target 1 --pid --mount --uts --ipc --net "
            "systemctl restart dhcp_relay', error: execution error",
            False
        )

    @patch("generic_config_updater.services_validator.logger")
    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_command_wrapper_handles_command_formatting_error(self, mock_subprocess, mock_logger):
        with patch(
            "generic_config_updater.services_validator.shlex.quote",
            side_effect=TypeError("formatting error")
        ):
            result = command_wrapper(["echo", "value"])

        self.assertEqual(result, 1)
        mock_subprocess.assert_not_called()
        mock_logger.log.assert_called_once_with(
            mock_logger.LOG_PRIORITY_ERROR,
            "Command execution failed: '['echo', 'value']', error: formatting error",
            False
        )

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_change_apply_subprocess_run(self, mock_subprocess):
        global subprocess_calls, subprocess_call_index, msg

        mock_subprocess.side_effect = mock_subprocess_run
        subprocess_calls = []
        subprocess_call_index = 0

        for entry in test_vlanintf_data:
            if entry["cmd"]:
                subprocess_calls.append({"cmd": entry["cmd"], "rc": 0})
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

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_vlanintf_validator_ignores_invalid_keys(self, mock_subprocess):
        old_config = {
            "VLAN_INTERFACE": {
                "VlanNameThatIsTooLong|192.168.0.1/24": {},
                "Vlan1000|invalid": {},
            }
        }

        result = vlanintf_validator(old_config, {}, None)

        self.assertTrue(result)
        mock_subprocess.assert_not_called()

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


class TestRestartRules(unittest.TestCase):
    """The shipped restart_on_change rules restart what the per-table validators they replaced did."""

    NSENTER = ["nsenter", "--target", "1", "--pid", "--mount", "--uts", "--ipc", "--net"]

    def shipped_conf(self):
        conf_file = os.path.join(os.path.dirname(generic_config_updater.change_applier.__file__),
                                 "gcu_services_validator.conf.json")
        with open(conf_file) as f:
            return json.load(f)

    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_service_restart__retries_after_reset_failed(self, mock_subprocess):
        mock_subprocess.side_effect = [MockSubprocessResult(1), MockSubprocessResult(0), MockSubprocessResult(0)]
        assert _service_restart("telemetry")
        actual = [c.args[0][len(self.NSENTER):] for c in mock_subprocess.call_args_list]
        self.assertEqual(actual, [["systemctl", "restart", "telemetry"],
                                  ["systemctl", "reset-failed", "telemetry"],
                                  ["systemctl", "restart", "telemetry"]])

    @patch("generic_config_updater.services_validator._service_restart", return_value=True)
    @patch("generic_config_updater.services_validator.command_wrapper", return_value=0)
    @patch("generic_config_updater.change_applier.get_config_db")
    def test_namespace_scope__restarts_all_but_host_only_rules(self, mock_db, mock_command, mock_restart):
        with patch.object(ChangeApplier, "updater_conf", self.shipped_conf()):
            applier = ChangeApplier(scope="asic0")
            applier._collect_restarts({}, {"NTP_SERVER": {"10.0.0.1": {}}, "SNMP": {"LOCATION": {"Location": "x"}}})
            assert applier.restart_services()
        mock_restart.assert_called_once_with("chrony")

    @patch("generic_config_updater.services_validator._service_restart", return_value=True)
    @patch("generic_config_updater.services_validator.command_wrapper", return_value=0)
    @patch("generic_config_updater.change_applier.get_config_db")
    def test_device_metadata__asic_scope_restarts_asic_instances(self, mock_db, mock_command, mock_restart):
        meta = {field: value for field, _, value in DEVICE_METADATA_RESTART_FIELDS}
        with patch.object(ChangeApplier, "updater_conf", self.shipped_conf()):
            applier = ChangeApplier(scope="asic2")
            applier._collect_restarts({}, {"DEVICE_METADATA": {"localhost": meta}})
            assert applier.restart_services()
        assert mock_restart.call_args_list == [call("swss@2"), call("bgp@2")]
        assert mock_command.call_args_list == [call(["systemctl", "reset-failed", "swss@2", "syncd@2"]),
                                               call(["systemctl", "reset-failed", "bgp@2"])]

    @patch("generic_config_updater.services_validator._service_restart", return_value=True)
    @patch("generic_config_updater.change_applier.multi_asic.is_multi_asic", return_value=True)
    @patch("generic_config_updater.services_validator.command_wrapper", return_value=0)
    @patch("generic_config_updater.change_applier.get_config_db")
    def test_device_metadata__multi_asic_host_restarts_host_units_only(self, mock_db, mock_command, mock_multi,
                                                                       mock_restart):
        meta = {field: value for field, _, value in DEVICE_METADATA_RESTART_FIELDS}
        with patch.object(ChangeApplier, "updater_conf", self.shipped_conf()):
            applier = ChangeApplier()
            applier._collect_restarts({}, {"DEVICE_METADATA": {"localhost": meta}})
            assert applier.restart_services()
        mock_restart.assert_called_once_with("dhcp_relay")

    def test_device_metadata__reload_only_fields_have_no_rule(self):
        rules = self.shipped_conf()["tables"]["DEVICE_METADATA"]["restart_on_change"]
        fields = {field for rule in rules for field in rule["fields"]}
        assert fields == {field for field, _, _ in DEVICE_METADATA_RESTART_FIELDS}
        assert not fields & {"hwsku", "switch_type", "type", "subtype", "sub_role", "asic_id"}

    @patch("generic_config_updater.change_applier.multi_asic.is_multi_asic", return_value=False)
    @patch("generic_config_updater.change_applier.get_config_db")
    @patch("generic_config_updater.services_validator.subprocess.run")
    def test_restart_rules(self, mock_subprocess, mock_db, mock_multi):
        mock_subprocess.return_value = MockSubprocessResult(0)
        conf = self.shipped_conf()
        nsenter = self.NSENTER
        with patch.object(ChangeApplier, "updater_conf", conf):
            applier = ChangeApplier()
            for data in (test_vlan_data,
                         test_rsyslog_data,
                         test_ntp_data,
                         test_gnmi_data,
                         test_telemetry_data,
                         test_port_speed_data,
                         test_dhcp_data,
                         test_device_metadata_data):
                for entry in data:
                    mock_subprocess.reset_mock()
                    applier._collect_restarts(entry["old"], entry["upd"])
                    assert applier.restart_services()
                    expected = [nsenter + c.split() for c in entry["cmd"].split(",")] if entry["cmd"] else []
                    actual = [c.args[0] for c in mock_subprocess.call_args_list]
                    self.assertEqual(actual, expected, str(entry))
