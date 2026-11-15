import copy
import datetime
import pytest
import filecmp
import importlib
import os
import subprocess
import traceback
import json
import jsonpatch
import sys
import unittest
import ipaddress

from datetime import timezone
from unittest import mock
from jsonpatch import JsonPatchConflict

import click
from click.testing import CliRunner

from sonic_py_common import device_info, multi_asic
from utilities_common import flock
from utilities_common.db import Db
from utilities_common.generation_transaction import GenerationCleanupError, GenerationRollbackError
from utilities_common.general import load_module_from_source
from mock import call, patch, mock_open, MagicMock

from generic_config_updater.generic_updater import ConfigFormat

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector
from config.main import config_file_yang_validation

# Add Test, module and script path.
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)
sys.path.insert(0, scripts_path)
os.environ["PATH"] += os.pathsep + scripts_path

# Config Reload input Path
mock_db_path = os.path.join(test_path, "config_reload_input")

mock_bmp_db_path = os.path.join(test_path, "bmp_input")


# Load minigraph input Path
load_minigraph_input_path = os.path.join(test_path, "load_minigraph_input")
load_minigraph_platform_path = os.path.join(load_minigraph_input_path, "platform")
load_minigraph_platform_false_path = os.path.join(load_minigraph_input_path, "platform_false")

load_minigraph_command_output="""\
Acquired lock on {0}
Disabling container, routeCheck and memory monitoring ...
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Restarting SONiC target ...
Enabling container, routeCheck and memory monitoring ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
Released lock on {0}
"""

load_minigraph_lock_failure_output = """\
Failed to acquire lock on {0}
"""

load_minigraph_command_bypass_lock_output = """\
Bypass lock on {}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

load_minigraph_platform_plugin_command_output="""\
Acquired lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Running Platform plugin ............!
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
Released lock on {0}
"""

load_mgmt_config_command_ipv4_only_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: cat /var/run/dhclient.eth0.pid
Running command: kill 101
Running command: rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv6_only_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: cat /var/run/dhclient.eth0.pid
Running command: kill 101
Running command: rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv4_ipv6_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: cat /var/run/dhclient.eth0.pid
Running command: kill 101
Running command: rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv4_ipv6_cat_failed_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: cat /var/run/dhclient.eth0.pid
Exit: 2. Command: cat /var/run/dhclient.eth0.pid failed.
"""

load_mgmt_config_command_ipv4_ipv6_kill_failed_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: cat /var/run/dhclient.eth0.pid
Running command: kill 104
Exit: 4. Command: kill 104 failed.
"""

RELOAD_CONFIG_DB_OUTPUT = """\
Acquired lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

RELOAD_CONFIG_DB_LOCK_FAILURE_OUTPUT = """\
Failed to acquire lock on {0}
"""

RELOAD_CONFIG_DB_BYPASS_LOCK_OUTPUT = """\
Bypass lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_YANG_CFG_OUTPUT = """\
Acquired lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -Y /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

RELOAD_MASIC_CONFIG_DB_OUTPUT = """\
Acquired lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config0.json -n asic0 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config1.json -n asic1 --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

reload_config_with_sys_info_command_output="""\
Acquired lock on {0}
Running command: /usr/local/bin/sonic-cfggen -H -k Seastone-DX010-25-50 --write-to-db"""

reload_config_with_disabled_service_output="""\
Acquired lock on {0}
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

reload_config_masic_onefile_output = """\
Acquired lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

reload_config_masic_onefile_gen_sysinfo_output = """\
Acquired lock on {0}
Running command: sudo systemctl stop featured.timer
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -k Mellanox-SN3800-D112C8 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -H -k multi_asic -n asic0 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -H -k multi_asic -n asic1 --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

save_config_output = """\
Running command: /usr/local/bin/sonic-cfggen -d --print-data > /etc/sonic/config_db.json
"""

save_config_filename_output = """\
Running command: /usr/local/bin/sonic-cfggen -d --print-data > /tmp/config_db.json
"""

save_config_masic_output = """\
Running command: /usr/local/bin/sonic-cfggen -d --print-data > /etc/sonic/config_db.json
Running command: /usr/local/bin/sonic-cfggen -n asic0 -d --print-data > /etc/sonic/config_db0.json
Running command: /usr/local/bin/sonic-cfggen -n asic1 -d --print-data > /etc/sonic/config_db1.json
"""

save_config_filename_masic_output = """\
Running command: /usr/local/bin/sonic-cfggen -d --print-data > config_db.json
Running command: /usr/local/bin/sonic-cfggen -n asic0 -d --print-data > config_db0.json
Running command: /usr/local/bin/sonic-cfggen -n asic1 -d --print-data > config_db1.json
"""

save_config_onefile_masic_output = """\
Integrate each ASIC's config into a single JSON file /tmp/all_config_db.json.
"""

config_temp = {
        "scope": {
            "ACL_TABLE": {
                "MY_ACL_TABLE": {
                    "policy_desc": "My ACL",
                    "ports": ["Ethernet1", "Ethernet2"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            "PORT": {
                "Ethernet1": {
                    "alias": "fortyGigE0/0",
                    "description": "fortyGigE0/0",
                    "index": "0",
                    "lanes": "29,30,31,32",
                    "mtu": "9100",
                    "pfc_asym": "off",
                    "speed": "40000"
                },
                "Ethernet2": {
                    "alias": "fortyGigE0/100",
                    "description": "fortyGigE0/100",
                    "index": "25",
                    "lanes": "125,126,127,128",
                    "mtu": "9100",
                    "pfc_asym": "off",
                    "speed": "40000"
                }
            }
        }
    }

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]
    if isinstance(command, str):
        command = command
    elif isinstance(command, list):
        command = ' '.join(command)

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target":
            return 'sonic.target\nswss\nfeatured.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target --reverse --type=service":
            return 'sonic.target\npmon', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled', 0
        elif command == 'cat /var/run/dhclient.eth0.pid':
            return '101', 0
        elif command == 'sudo systemctl show --no-pager interfaces-config -p ExecMainExitTimestamp --value':
            return f'{datetime.datetime.now()}', 0
        elif command == 'sudo systemctl show --no-pager networking -p ExecMainExitTimestamp --value':
            return f'{datetime.datetime.now()}', 0
        elif command.startswith('sudo monit status'):
            return '  monitoring status            Monitored\n', 0
        else:
            return '', 0

def mock_run_command_cat_failed_side_effect(*args, **kwargs):
    command = args[0]
    if isinstance(command, str):
        command = command
    elif isinstance(command, list):
        command = ' '.join(command)

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target":
            return 'sonic.target\nswss', 0
        elif command == "systemctl list-dependencies --plain sonic.target --reverse --type=service":
            return 'sonic.target\npmon', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled', 0
        elif command == 'cat /var/run/dhclient.eth0.pid':
            return '102', 2
        else:
            return '', 0

def mock_run_command_kill_failed_side_effect(*args, **kwargs):
    command = args[0]
    if isinstance(command, str):
        command = command
    elif isinstance(command, list):
        command = ' '.join(command)

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target":
            return 'sonic.target\nswss', 0
        elif command == "systemctl list-dependencies --plain sonic.target --reverse --type=service":
            return 'sonic.target\npmon', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled', 0
        elif command == 'cat /var/run/dhclient.eth0.pid':
            return '104', 0
        elif command == 'kill 104':
            return 'Failed to kill 104', 4
        else:
            return '', 0

def mock_run_command_side_effect_disabled_timer(*args, **kwargs):
    command = args[0]
    if isinstance(command, str):
        command = command
    elif isinstance(command, list):
        command = ' '.join(command)

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target":
            return 'sonic.target\nswss', 0
        elif command == "systemctl list-dependencies --plain sonic.target --reverse --type=service":
            return 'sonic.target\npmon', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'masked', 0
        elif command == "systemctl show swss.service --property ActiveState --value":
            return 'active', 0
        elif command == "systemctl show swss.service --property ActiveEnterTimestampMonotonic --value":
            return '0', 0
        else:
            return '', 0

# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')

class TestHelper(object):
    def setup_method(self):
        print("SETUP")

    @patch('config.main.subprocess.Popen')
    def test_get_device_type(self, mock_subprocess):
        mock_subprocess.return_value.communicate.return_value = ("BackendToRRouter ", None)
        device_type = config._get_device_type()
        mock_subprocess.assert_called_with(['/usr/local/bin/sonic-cfggen', '-m', '-v', 'DEVICE_METADATA.localhost.type'], text=True, stdout=-1)
        assert device_type == "BackendToRRouter"

        mock_subprocess.return_value.communicate.return_value = (None, "error")
        device_type = config._get_device_type()
        mock_subprocess.assert_called_with(['/usr/local/bin/sonic-cfggen', '-m', '-v', 'DEVICE_METADATA.localhost.type'], text=True, stdout=-1)
        assert device_type == "Unknown"

    def teardown_method(self):
        print("TEARDOWN")

class TestConfig(object):
    def setup_method(self):
        print("SETUP")

    @patch('config.main.subprocess.check_call')
    def test_platform_fw_install(self, mock_check_call):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['platform'].commands['firmware'].commands['install'], ['chassis', 'component', 'BIOS', 'fw', '/firmware_path'])
        assert result.exit_code == 0
        mock_check_call.assert_called_with(["fwutil", "install", 'chassis', 'component', 'BIOS', 'fw', '/firmware_path'])

    @patch('config.main.subprocess.check_call')
    def test_plattform_fw_update(self, mock_check_call):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['platform'].commands['firmware'].commands['update'], ['update', 'module', 'Module1', 'component', 'BIOS', 'fw'])
        assert result.exit_code == 0
        mock_check_call.assert_called_with(["fwutil", "update", 'update', 'module', 'Module1', 'component', 'BIOS', 'fw'])


class TestConfigSave(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    def test_config_save(self, get_cmd_module, setup_single_broadcom_asic):
        def read_json_file_side_effect(filename):
            return {}

        mock_file = MagicMock()
        mock_file.fileno.return_value = 1
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)),\
            mock.patch('config.main.open',
                       mock.MagicMock(return_value=mock_file)):
            (config, show) = get_cmd_module

            runner = CliRunner()

            result = runner.invoke(config.config.commands["save"], ["-y"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == save_config_output

    def test_config_save_filename(self, get_cmd_module, setup_single_broadcom_asic):
        def read_json_file_side_effect(filename):
            return {}

        mock_file = MagicMock()
        mock_file.fileno.return_value = 1
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)),\
            mock.patch('config.main.open',
                       mock.MagicMock(return_value=mock_file)):

            (config, show) = get_cmd_module

            runner = CliRunner()

            output_file = os.path.join(os.sep, "tmp", "config_db.json")
            result = runner.invoke(config.config.commands["save"], ["-y", output_file])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert (
                "\n".join([li.rstrip() for li in result.output.split('\n')])
                == save_config_filename_output)

    def test_config_save_calls_flush_and_fsync(
            self, get_cmd_module, setup_single_broadcom_asic):
        """Verify config save calls flush() and fsync() for persistence."""
        def read_json_file_side_effect(filename):
            return {}

        mock_file = MagicMock()
        mock_file.fileno.return_value = 1
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(
                            side_effect=mock_run_command_side_effect)), \
                mock.patch('config.main.read_json_file',
                           mock.MagicMock(
                               side_effect=read_json_file_side_effect)), \
                mock.patch('config.main.open',
                           mock.MagicMock(return_value=mock_file)), \
                mock.patch('config.main.os.fsync') as mock_fsync:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["save"], ["-y"])

            assert result.exit_code == 0
            mock_file.flush.assert_called()
            mock_fsync.assert_called()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigSaveMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_config_save_masic(self):
        def read_json_file_side_effect(filename):
            return {}

        mock_file = MagicMock()
        mock_file.fileno.return_value = 1
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(
                            side_effect=mock_run_command_side_effect)), \
                mock.patch('config.main.read_json_file',
                           mock.MagicMock(
                               side_effect=read_json_file_side_effect)), \
                mock.patch('config.main.open',
                           mock.MagicMock(return_value=mock_file)):

            runner = CliRunner()

            result = runner.invoke(config.config.commands["save"], ["-y"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split(
                '\n')]) == save_config_masic_output

    def test_config_save_filename_masic(self):
        def read_json_file_side_effect(filename):
            return {}

        mock_file = MagicMock()
        mock_file.fileno.return_value = 1
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(
                            side_effect=mock_run_command_side_effect)), \
                mock.patch('config.main.read_json_file',
                           mock.MagicMock(
                               side_effect=read_json_file_side_effect)), \
                mock.patch('config.main.open',
                           mock.MagicMock(return_value=mock_file)):

            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["save"],
                ["-y", "config_db.json,config_db0.json,config_db1.json"]
            )

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == save_config_filename_masic_output

    def test_config_save_filename_wrong_cnt_masic(self):
        def read_json_file_side_effect(filename):
            return {}

        with mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):

            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["save"],
                ["-y", "config_db.json,config_db0.json"]
            )

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert "Input 3 config file(s) separated by comma for multiple files" in result.output

    def test_config_save_onefile_masic(self):
        def get_config_side_effect():
            return {}

        with mock.patch('swsscommon.swsscommon.ConfigDBConnector.get_config',
                        mock.MagicMock(side_effect=get_config_side_effect)):
            runner = CliRunner()

            output_file = os.path.join(os.sep, "tmp", "all_config_db.json")
            print("Saving output in {}".format(output_file))
            try:
                os.remove(output_file)
            except OSError:
                pass
            result = runner.invoke(
                config.config.commands["save"],
                ["-y", output_file]
            )

            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert (
                "\n".join([li.rstrip() for li in result.output.split('\n')])
                == save_config_onefile_masic_output)

            cwd = os.path.dirname(os.path.realpath(__file__))
            expected_result = os.path.join(
                cwd, "config_save_output", "all_config_db.json"
            )
            assert filecmp.cmp(output_file, expected_result, shallow=False)

    def test_config_save_onefile_masic_calls_flush_and_fsync(self):
        """Verify multiasic save to single file calls flush() and fsync()."""
        def get_config_side_effect():
            return {}

        mock_file = MagicMock()
        mock_file.fileno.return_value = 1
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        with mock.patch('swsscommon.swsscommon.ConfigDBConnector.get_config',
                        mock.MagicMock(
                            side_effect=get_config_side_effect)), \
                mock.patch('config.main.open',
                           mock.MagicMock(return_value=mock_file)), \
                mock.patch('config.main.os.fsync') as mock_fsync:
            runner = CliRunner()
            output_file = os.path.join(
                os.sep, "tmp", "all_config_db_masic_fsync_test.json")
            result = runner.invoke(
                config.config.commands["save"],
                ["-y", output_file]
            )

            assert result.exit_code == 0
            mock_file.flush.assert_called()
            mock_fsync.assert_called()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestConfigReload(object):
    dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

        import config.main
        importlib.reload(config.main)
        open(cls.dummy_cfg_file, 'w').close()

    def test_config_reload(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch.object(config, "config_file_yang_validation") as mock_validate_config:

            jsonfile_config = os.path.join(mock_db_path, "config_db.json")
            jsonfile_init_cfg = os.path.join(mock_db_path, "init_cfg.json")

            # create object
            config.INIT_CFG_FILE = jsonfile_init_cfg
            config.DEFAULT_CONFIG_DB_FILE =  jsonfile_config

            db = Db()
            runner = CliRunner()
            obj = {'config_db': db.cfgdb}

            # simulate 'config reload' to provoke load_sys_info option
            result = runner.invoke(config.config.commands["reload"], ["-l", "-n", "-y"], obj=obj)

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0

            assert "\n".join([line.rstrip() for line in result.output.split('\n')][:2]) == \
                reload_config_with_sys_info_command_output.format(config.SYSTEM_RELOAD_LOCK)
            mock_validate_config.assert_called_once_with(jsonfile_config)

    def test_config_reload_default_config_validation_failure(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module

        jsonfile_config = os.path.join(mock_db_path, "config_db.json")
        config.DEFAULT_CONFIG_DB_FILE = jsonfile_config

        with mock.patch("utilities_common.cli.run_command") as mock_run_command, \
                mock.patch.object(
                    config, "config_file_yang_validation", side_effect=click.Abort) as mock_validate_config:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["reload"], ["-y", "-n"])

            assert result.exit_code != 0
            mock_validate_config.assert_called_once_with(jsonfile_config)
            mock_run_command.assert_not_called()

    def test_config_reload_force_skips_validation(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module

        config.DEFAULT_CONFIG_DB_FILE = os.path.join(
            mock_db_path, 'missing_config_db.json'
        )

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch.object(config, "config_file_yang_validation") as mock_validate_config:
            runner = CliRunner()
            result = runner.invoke(
                config.config.commands["reload"], ["-y", "-f", "-n"]
            )

            assert result.exit_code == 0
            mock_validate_config.assert_not_called()

    def test_config_reload_blocked_during_warm_boot(self, get_cmd_module, setup_single_broadcom_asic):
        """config reload must abort when a warm-boot is in progress (Redmine #5154490)."""
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db.json")

        mock_swsscommon = mock.MagicMock()
        mock_swsscommon.RestartWaiter.isWarmBootInProgress.return_value = True
        mock_swsscommon.RestartWaiter.isFastBootInProgress.return_value = False

        with mock.patch.object(config, "DEFAULT_CONFIG_DB_FILE", jsonfile_config), \
                mock.patch('config.main.swsscommon', mock_swsscommon), \
                mock.patch('config.main._is_system_starting', return_value=False), \
                mock.patch('config.main._swss_ready', return_value=True), \
                mock.patch.object(config, 'config_file_yang_validation'):
            result = CliRunner().invoke(config.config.commands["reload"], ["-y"])
            assert result.exit_code != 0
            assert "warm-boot" in result.output
            assert "still in progress" in result.output

    def test_config_reload_blocked_during_fast_boot(self, get_cmd_module, setup_single_broadcom_asic):
        """config reload must abort when a fast-reboot is in progress.
        fast-reboot sets both FAST_RESTART_ENABLE_TABLE and WARM_RESTART_ENABLE_TABLE;
        isFastBootInProgress is checked first so the label is correct."""
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db.json")

        mock_swsscommon = mock.MagicMock()
        mock_swsscommon.RestartWaiter.isWarmBootInProgress.return_value = True
        mock_swsscommon.RestartWaiter.isFastBootInProgress.return_value = True

        with mock.patch.object(config, "DEFAULT_CONFIG_DB_FILE", jsonfile_config), \
                mock.patch('config.main.swsscommon', mock_swsscommon), \
                mock.patch('config.main._is_system_starting', return_value=False), \
                mock.patch('config.main._swss_ready', return_value=True), \
                mock.patch.object(config, 'config_file_yang_validation'):
            result = CliRunner().invoke(config.config.commands["reload"], ["-y"])
            assert result.exit_code != 0
            assert "fast-reboot" in result.output
            assert "still in progress" in result.output

    def test_config_reload_not_blocked_when_no_boot_in_progress(self, get_cmd_module, setup_single_broadcom_asic):
        """Guard runs but does not block when no boot is in progress; both checks are invoked."""
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db.json")

        mock_swsscommon = mock.MagicMock()
        mock_swsscommon.RestartWaiter.isWarmBootInProgress.return_value = False
        mock_swsscommon.RestartWaiter.isFastBootInProgress.return_value = False

        with mock.patch.object(config, "DEFAULT_CONFIG_DB_FILE", jsonfile_config), \
                mock.patch('config.main.swsscommon', mock_swsscommon), \
                mock.patch.object(config, 'config_file_yang_validation'), \
                mock.patch('config.main._is_system_starting', return_value=False), \
                mock.patch('config.main._swss_ready', return_value=True), \
                mock.patch('config.main._stop_services'), \
                mock.patch('config.main._restart_services'), \
                mock.patch('config.main._reset_failed_services'), \
                mock.patch("utilities_common.cli.run_command",
                           mock.MagicMock(side_effect=mock_run_command_side_effect)):
            result = CliRunner().invoke(config.config.commands["reload"], ["-y"])
            assert result.exit_code == 0
            assert "still in progress" not in result.output
            mock_swsscommon.RestartWaiter.isFastBootInProgress.assert_called_once()
            mock_swsscommon.RestartWaiter.isWarmBootInProgress.assert_called_once()

    def test_config_reload_no_service_restart_skips_guard(self, get_cmd_module, setup_single_broadcom_asic):
        """With -n (no_service_restart), guard is skipped — no syncd teardown, no risk."""
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db.json")

        mock_swsscommon = mock.MagicMock()
        mock_swsscommon.RestartWaiter.isWarmBootInProgress.return_value = True

        with mock.patch.object(config, "DEFAULT_CONFIG_DB_FILE", jsonfile_config), \
                mock.patch('config.main.swsscommon', mock_swsscommon), \
                mock.patch.object(config, 'config_file_yang_validation'), \
                mock.patch("utilities_common.cli.run_command",
                           mock.MagicMock(side_effect=mock_run_command_side_effect)):
            result = CliRunner().invoke(config.config.commands["reload"], ["-y", "-n"])
            assert result.exit_code == 0
            assert "still in progress" not in result.output
            mock_swsscommon.RestartWaiter.isFastBootInProgress.assert_not_called()
            mock_swsscommon.RestartWaiter.isWarmBootInProgress.assert_not_called()

    def test_config_reload_default_config_missing_file(
        self, get_cmd_module, setup_single_broadcom_asic
    ):
        (config, show) = get_cmd_module

        config.DEFAULT_CONFIG_DB_FILE = os.path.join(
            mock_db_path, 'missing_config_db.json'
        )

        with mock.patch(
            "utilities_common.cli.run_command"
        ) as mock_run_command:
            runner = CliRunner()
            result = runner.invoke(
                config.config.commands["reload"], ["-y", "-n"]
            )

            assert result.exit_code != 0
            assert (
                "The config file {} doesn't exist".format(
                    config.DEFAULT_CONFIG_DB_FILE
                ) in result.output
            )
            assert "Traceback" not in result.output
            mock_run_command.assert_not_called()

    def test_config_reload_default_config_invalid_json(
        self, get_cmd_module, setup_single_broadcom_asic
    ):
        (config, show) = get_cmd_module

        jsonfile_config = os.path.join(mock_db_path, "config_db.json")
        config.DEFAULT_CONFIG_DB_FILE = jsonfile_config

        with mock.patch(
            "utilities_common.cli.run_command"
        ) as mock_run_command:
            with mock.patch('config.main.os.access', return_value=True):
                with mock.patch.object(
                    config,
                    "config_file_yang_validation",
                    side_effect=Exception("bad json"),
                ):
                    runner = CliRunner()
                    result = runner.invoke(
                        config.config.commands["reload"], ["-y", "-n"]
                    )

                    assert result.exit_code != 0
                    assert (
                        "Failed to read config file {}: bad json".format(
                            jsonfile_config
                        ) in result.output
                    )
                    assert "Traceback" not in result.output
                    mock_run_command.assert_not_called()

    def test_config_reload_default_config_invalid_root(
        self, get_cmd_module, setup_single_broadcom_asic
    ):
        (config, show) = get_cmd_module

        jsonfile_config = os.path.join(mock_db_path, "config_db.json")
        config.DEFAULT_CONFIG_DB_FILE = jsonfile_config

        with mock.patch(
            "utilities_common.cli.run_command"
        ) as mock_run_command:
            with mock.patch('config.main.os.access', return_value=True):
                with mock.patch.object(
                    config,
                    "config_file_yang_validation",
                    return_value=False,
                ) as mock_validate_config:
                    runner = CliRunner()
                    result = runner.invoke(
                        config.config.commands["reload"], ["-y", "-n"]
                    )

                    assert result.exit_code != 0
                    assert (
                        "Invalid config file:'{}'!".format(
                            jsonfile_config
                        ) in result.output
                    )
                    mock_validate_config.assert_called_once_with(
                        jsonfile_config
                    )
                    mock_run_command.assert_not_called()

    def test_config_reload_stdin(self, get_cmd_module, setup_single_broadcom_asic):
        def mock_json_load(f):
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "docker_routing_config_mode": "split",
                        "hostname": "sonic",
                        "hwsku": "Seastone-DX010-25-50",
                        "mac": "00:e0:ec:89:6e:48",
                        "platform": "x86_64-cel_seastone-r0",
                        "type": "ToRRouter"
                    }
                }
            }
            return device_metadata
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command,\
                mock.patch("json.load", mock.MagicMock(side_effect=mock_json_load)):
            (config, show) = get_cmd_module

            dev_stdin = "/dev/stdin"
            jsonfile_init_cfg = os.path.join(mock_db_path, "init_cfg.json")

            # create object
            config.INIT_CFG_FILE = jsonfile_init_cfg

            db = Db()
            runner = CliRunner()
            obj = {'config_db': db.cfgdb}

            # simulate 'config reload' to provoke load_sys_info option
            result = runner.invoke(config.config.commands["reload"], [dev_stdin, "-l", "-n", "-y"], obj=obj)

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0

            assert "\n".join([line.rstrip() for line in result.output.split('\n')][:2]) == \
                reload_config_with_sys_info_command_output.format(config.SYSTEM_RELOAD_LOCK)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestLoadGoldenConfig(object):
    class _RecordingGenerationTransaction(object):
        def __init__(self, namespaces, persistent_files, events):
            self.namespaces = tuple(namespaces)
            self.persistent_files = tuple(persistent_files)
            self.events = events
            self.commit_error = None
            self.rollback_error = None
            self.evidence_directory = "/tmp/recording-generation"
            self.evidence_parent = "{}-{}".format(
                self.evidence_directory,
                id(self),
            )
            self.database_adapter = None

        def begin(self, service_quiescence=None, service_recovery=None):
            self.events.append("begin")
            if service_quiescence is not None:
                service_quiescence()

        def mark_service_recovery_complete(self):
            pass

        def mark_scope_touched(self, namespace):
            self.events.append(("mark_scope", namespace))

        def mark_shared_databases_touched(self):
            self.events.append("mark_shared_databases")

        def mark_persistent_file_touched(self, path):
            self.events.append(("mark_persistent_file", path))

        def commit(self):
            self.events.append("commit")
            if self.commit_error is not None:
                raise self.commit_error

        def rollback(
                self, original_error, service_quiescence=None,
                service_recovery=None):
            self.events.append(("rollback", original_error))
            if service_quiescence is not None:
                self.events.append("service_quiescence")
                service_quiescence()
            if service_recovery is not None:
                self.events.append("service_recovery")
                service_recovery()
            if self.rollback_error is not None:
                raise self.rollback_error

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        import config.main
        importlib.reload(config.main)

    @staticmethod
    def _write_json(filename, data):
        with open(filename, 'w') as config_file:
            json.dump(data, config_file)

    @staticmethod
    def _valid_init_config():
        return {
            "FEATURE": {
                "bgp": {
                    "state": "enabled"
                }
            }
        }

    @staticmethod
    def _valid_hardware_config():
        return {
            "PORT": {
                "Ethernet0": {
                    "alias": "Ethernet0",
                    "index": "0",
                    "lanes": "1,2,3,4",
                    "speed": "100000"
                }
            }
        }

    @staticmethod
    def _valid_golden_config():
        return {
            "DEVICE_METADATA": {
                "localhost": {
                    "platform": "x86_64-kvm_x86_64-r0",
                    "mac": "00:01:02:03:04:05",
                    "hwsku": "Force10-S6000",
                    "hostname": "sonic",
                    "type": "ToRRouter"
                }
            },
            "FEATURE": {
                "bgp": {
                    "state": "enabled"
                }
            },
            **TestLoadGoldenConfig._valid_hardware_config()
        }

    @classmethod
    def _valid_multiasic_golden_config(cls):
        config_data = {
            "localhost": cls._valid_golden_config()
        }
        namespace_metadata = {
            "asic0": {
                "asic_id": "01.00.0",
                "mac": "02:42:f0:7f:01:05",
            },
            "asic1": {
                "mac": "02:42:f0:7f:01:06",
            },
        }
        for namespace in ("asic0", "asic1"):
            scope_config = cls._valid_golden_config()
            scope_config["DEVICE_METADATA"]["localhost"].update({
                "asic_name": namespace,
                "hostname": "sonic",
                "hwsku": "multi_asic",
                "mac": namespace_metadata[namespace]["mac"],
                "platform": "multi_asic",
            })
            if "asic_id" in namespace_metadata[namespace]:
                scope_config["DEVICE_METADATA"]["localhost"]["asic_id"] = \
                    namespace_metadata[namespace]["asic_id"]
            config_data[namespace] = scope_config
        return config_data

    @staticmethod
    def _support(config, profile, switch_type="npu", num_asics=1,
                 namespaces=(), supervisor=False, chassis=False,
                 dpu=False, smartswitch=False, chassis_scope=False,
                 trusted_device_type="ToRRouter"):
        return config.GoldenNativeSupport(
            profile=profile,
            switch_type=switch_type,
            num_asics=num_asics,
            namespaces=tuple(namespaces),
            hostname="sonic",
            platform="x86_64-kvm_x86_64-r0",
            hwsku="Force10-S6000",
            mac="00:01:02:03:04:05",
            trusted_device_type=trusted_device_type,
            is_supervisor=supervisor,
            is_chassis=chassis,
            is_dpu=dpu,
            is_smartswitch=smartswitch,
            has_chassis_scope=chassis_scope
        )

    @classmethod
    def _profile_golden_config(cls, config, profile, switch_type="npu"):
        golden_config = cls._valid_golden_config()
        metadata = golden_config["DEVICE_METADATA"]["localhost"]

        if switch_type != "npu":
            metadata["switch_type"] = switch_type

        if profile == "voq_linecard":
            golden_config["SYSTEM_PORT"] = {
                "Ethernet0": {
                    "hostname": "sonic",
                    "asic_name": "asic0",
                    "speed": "100000",
                    "switch_id": "0",
                    "core_index": "0",
                    "core_port_index": "0",
                    "num_voq": "8"
                }
            }
        elif profile == "smartswitch_host":
            metadata["subtype"] = "SmartSwitch"
            golden_config["DPUS"] = {"dpu0": {"midplane_interface": "dpu0"}}
            golden_config["CHASSIS_MODULE"] = {
                "DPU0": {"admin_status": "up"}
            }
            golden_config["DPU"] = {"dpu0": {"state": "up"}}
        elif profile == "dpu":
            metadata.update({
                "type": "SmartSwitchDPU",
                "subtype": "SmartSwitch"
            })

        return golden_config

    @pytest.fixture(autouse=True)
    def _mock_hardware_config(self, get_cmd_module):
        (config, _) = get_cmd_module
        with mock.patch.object(
                config,
                "_read_hardware_config",
                return_value=self._valid_hardware_config()), \
                mock.patch.object(
                    config.device_info,
                    "get_hostname",
                    return_value="sonic"), \
                mock.patch.object(
                    config.device_info,
                    "get_platform",
                    return_value="x86_64-kvm_x86_64-r0"), \
                mock.patch.object(
                    config.device_info,
                    "get_hwsku",
                    return_value="Force10-S6000"), \
                mock.patch.object(
                    config.device_info,
                    "get_system_mac",
                    return_value="00:01:02:03:04:05"), \
                mock.patch.object(
                    config.device_info,
                    "get_num_npus",
                    side_effect=lambda: (
                        len(config.multi_asic.get_namespace_list())
                        if config.multi_asic.is_multi_asic()
                        else 1
                    )), \
                mock.patch.object(
                    config.device_info,
                    "is_multi_npu",
                    side_effect=lambda: config.multi_asic.is_multi_asic()), \
                mock.patch.object(
                    config.device_info,
                    "is_supervisor",
                    return_value=False), \
                mock.patch.object(
                    config.device_info,
                    "is_chassis",
                    return_value=False), \
                mock.patch.object(
                    config.device_info,
                    "is_dpu",
                    return_value=False), \
                mock.patch.object(
                    config.device_info,
                    "is_smartswitch",
                    return_value=False), \
                mock.patch.object(
                    config.multi_asic,
                    "is_multi_asic",
                    return_value=False), \
                mock.patch.object(
                    config.multi_asic,
                    "get_namespace_list",
                    return_value=[config.DEFAULT_NAMESPACE]), \
                mock.patch.object(
                    config,
                    "_golden_native_chassis_scope_present",
                    return_value=False), \
                mock.patch.object(
                    config,
                    "_read_trusted_golden_native_device_metadata",
                    return_value={"type": "ToRRouter"}):
            yield

    @pytest.fixture(autouse=True)
    def _mock_generation_transaction(self, get_cmd_module):
        (config, _) = get_cmd_module
        self._generation_transaction_events = []
        self._generation_transactions = []
        self._generation_transaction_commit_error = None
        self._generation_transaction_rollback_error = None

        def new_transaction(support):
            transaction = self._RecordingGenerationTransaction(
                support.namespaces,
                config._golden_native_persistent_config_files(
                    support.namespaces
                ),
                self._generation_transaction_events,
            )
            transaction.commit_error = self._generation_transaction_commit_error
            transaction.rollback_error = self._generation_transaction_rollback_error
            self._generation_transactions.append(transaction)
            return transaction

        with mock.patch.object(
                config,
                "_new_golden_native_generation_transaction",
                side_effect=new_transaction):
            yield

    @pytest.fixture(autouse=True)
    def _mock_generation_runtime(self, get_cmd_module):
        (config, _) = get_cmd_module
        with mock.patch.object(config, "_stop_services"), \
                mock.patch.object(config, "_reset_failed_services"), \
                mock.patch.object(config, "update_sonic_environment"), \
                mock.patch.object(config, "_restart_services"), \
                mock.patch.object(
                    config, "_set_generation_config_db_initialized"), \
                mock.patch.object(
                    config, "_persist_generation_config_files"):
            yield

    def _new_recording_transaction(self, config):
        return self._RecordingGenerationTransaction(
            [config.DEFAULT_NAMESPACE, "asic0", "asic1"],
            config._golden_native_persistent_config_files(
                [config.DEFAULT_NAMESPACE, "asic0", "asic1"]
            ),
            self._generation_transaction_events,
        )

    def _invoke_real_single_asic_reload(
            self, config, run_command_error=None, reset_results=None,
            environment_results=None, restart_results=None, arguments=None):
        runner = CliRunner()
        db = Db()
        service_calls = []
        arguments = list(arguments) if arguments is not None else [
            "-y", "-f", "-b", "golden_config.json"
        ]
        reset_results = list(reset_results or [])
        environment_results = list(environment_results or [])
        restart_results = list(restart_results or [])
        mock_swsscommon = mock.MagicMock()
        mock_swsscommon.RestartWaiter.isFastBootInProgress.return_value = False
        mock_swsscommon.RestartWaiter.isWarmBootInProgress.return_value = False
        client = mock.MagicMock()
        config_db = mock.MagicMock()
        config_db.INIT_INDICATOR = "CONFIG_DB_INITIALIZED"

        def record_service_call(name):
            service_calls.append(name)
            self._generation_transaction_events.append(("service", name))

        def run_command(*_args, **_kwargs):
            if run_command_error is not None:
                raise run_command_error

        def restart_services():
            record_service_call("restart")
            if restart_results:
                result = restart_results.pop(0)
                if isinstance(result, BaseException):
                    raise result

        def reset_services():
            record_service_call("reset")
            if reset_results:
                result = reset_results.pop(0)
                if isinstance(result, BaseException):
                    raise result

        def prepare_environment():
            record_service_call("environment")
            if environment_results:
                result = environment_results.pop(0)
                if isinstance(result, BaseException):
                    raise result

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config,
                        "config_file_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config, "load_sysinfo_if_missing", return_value=False), \
                    mock.patch.object(config, "swsscommon", mock_swsscommon), \
                    mock.patch.object(
                        config, "flush_configdb",
                        return_value=(client, config_db)), \
                    mock.patch.object(config, "delete_transceiver_tables"), \
                    mock.patch.object(config, "delete_bgp_peer_table"), \
                    mock.patch.object(config, "migrate_db_to_lastest"), \
                    mock.patch.object(
                        config,
                        "update_sonic_environment",
                        side_effect=prepare_environment), \
                    mock.patch.object(
                        config.clicommon,
                        "run_command",
                        side_effect=run_command), \
                    mock.patch.object(
                        config,
                        "_stop_services",
                        side_effect=lambda: record_service_call("stop")), \
                    mock.patch.object(
                        config,
                        "_reset_failed_services",
                        side_effect=reset_services), \
                    mock.patch.object(
                        config,
                        "_restart_services",
                        side_effect=restart_services):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    arguments,
                    obj={"config_db": db.cfgdb}
                )

        return result, service_calls

    def test_check_only_validates_without_reloading(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True), \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

            assert result.exit_code == 0
            assert "Golden config validation succeeded." in result.output
            mock_reload.assert_not_called()

    def test_check_only_and_migrate_only_are_mutually_exclusive(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False):
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "--migrate-only", "-b", "golden_config.json"]
            )

        assert result.exit_code == 2
        assert "--check-only and --migrate-only cannot be used together" in result.output

    @pytest.mark.parametrize(
        "trusted_metadata, role_flags, expected_profile, expected_switch_type",
        [
            ({"type": "ToRRouter"}, {}, "standalone_npu", "npu"),
            (
                {"type": "ToRRouter", "switch_type": "voq"},
                {"is_chassis": True, "chassis_scope": True},
                "voq_linecard",
                "voq"
            ),
            (
                {"type": "ToRRouter", "switch_type": "chassis-packet"},
                {"is_chassis": True, "chassis_scope": True},
                "packet_linecard",
                "chassis-packet"
            ),
            (
                {"type": "ToRRouter", "switch_type": "npu"},
                {
                    "is_supervisor": True,
                    "is_chassis": True,
                    "chassis_scope": True
                },
                "supervisor",
                "npu"
            ),
            (
                {"type": "ToRRouter", "switch_type": "fabric"},
                {
                    "is_supervisor": True,
                    "is_chassis": True,
                    "chassis_scope": True
                },
                "supervisor",
                "fabric"
            ),
            (
                {"type": "ToRRouter", "switch_type": "fabric"},
                {"is_chassis": True, "chassis_scope": True},
                "fabric_card",
                "fabric"
            ),
            (
                {"type": "ToRRouter", "subtype": "SmartSwitch"},
                {"is_smartswitch": True},
                "smartswitch_host",
                "npu"
            ),
            (
                {"type": "SmartSwitchDPU", "switch_type": "dpu"},
                {"is_dpu": True},
                "dpu",
                "dpu"
            )
        ]
    )
    def test_trusted_profile_resolution(
            self, get_cmd_module, trusted_metadata, role_flags,
            expected_profile, expected_switch_type):
        (config, _) = get_cmd_module

        switch_type = config._normalize_golden_native_switch_type(
            trusted_metadata.get("switch_type")
        )
        profile = config._resolve_golden_native_profile(
            switch_type,
            role_flags.get("is_supervisor", False),
            role_flags.get("is_chassis", False),
            role_flags.get("is_dpu", False),
            role_flags.get("is_smartswitch", False),
            role_flags.get("chassis_scope", False)
        )

        assert profile == expected_profile
        assert switch_type == expected_switch_type

    @pytest.mark.parametrize(
        "trusted_metadata, role_flags, expected_error",
        [
            (
                {"switch_type": "unsupported-role"},
                {},
                "unsupported trusted switch_type 'unsupported-role'"
            ),
            (
                {"switch_type": "voq"},
                {},
                "voq switch_type requires trusted chassis scope"
            ),
            (
                {"switch_type": "dpu"},
                {"is_dpu": True, "is_chassis": True},
                "DPU role conflicts with chassis role signals"
            ),
            (
                {"subtype": "SmartSwitch"},
                {"is_smartswitch": True, "is_chassis": True},
                "SmartSwitch host role conflicts with chassis role signals"
            ),
            (
                {"switch_type": "voq"},
                {"is_supervisor": True, "is_chassis": True},
                "supervisor role conflicts with trusted switch_type 'voq'"
            )
        ]
    )
    def test_trusted_profile_conflicts_fail_closed(
            self, get_cmd_module, trusted_metadata, role_flags,
            expected_error):
        (config, _) = get_cmd_module

        switch_type = config._normalize_golden_native_switch_type(
            trusted_metadata.get("switch_type")
        )
        with pytest.raises(ValueError) as error:
            config._resolve_golden_native_profile(
                switch_type,
                role_flags.get("is_supervisor", False),
                role_flags.get("is_chassis", False),
                role_flags.get("is_dpu", False),
                role_flags.get("is_smartswitch", False),
                role_flags.get("chassis_scope", False)
            )

        assert expected_error in str(error.value)

    @pytest.mark.parametrize(
        "trusted_metadata, role_flags, expected_profile",
        [
            (
                {"type": "ToRRouter", "switch_type": "voq"},
                {"is_chassis": True, "chassis_scope": True},
                "voq_linecard"
            ),
            (
                {"type": "ToRRouter", "switch_type": "chassis-packet"},
                {"is_chassis": True, "chassis_scope": True},
                "packet_linecard"
            ),
            (
                {"type": "ToRRouter", "switch_type": "npu"},
                {
                    "is_supervisor": True,
                    "is_chassis": True,
                    "chassis_scope": True
                },
                "supervisor"
            ),
            (
                {"type": "ToRRouter", "switch_type": "fabric"},
                {"is_chassis": True, "chassis_scope": True},
                "fabric_card"
            ),
            (
                {"type": "ToRRouter", "subtype": "SmartSwitch"},
                {"is_smartswitch": True},
                "smartswitch_host"
            ),
            (
                {"type": "SmartSwitchDPU", "switch_type": "dpu"},
                {"is_dpu": True},
                "dpu"
            )
        ]
    )
    def test_recognized_unsupported_profile_fails_before_file_io(
            self, get_cmd_module, trusted_metadata, role_flags,
            expected_profile):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(
                config,
                "_read_trusted_golden_native_device_metadata",
                return_value=trusted_metadata), \
                mock.patch.object(
                    config.device_info,
                    "is_supervisor",
                    return_value=role_flags.get("is_supervisor", False)), \
                mock.patch.object(
                    config.device_info,
                    "is_chassis",
                    return_value=role_flags.get("is_chassis", False)), \
                mock.patch.object(
                    config.device_info,
                    "is_dpu",
                    return_value=role_flags.get("is_dpu", False)), \
                mock.patch.object(
                    config.device_info,
                    "is_smartswitch",
                    return_value=role_flags.get("is_smartswitch", False)), \
                mock.patch.object(
                    config,
                    "_golden_native_chassis_scope_present",
                    return_value=role_flags.get("chassis_scope", False)), \
                mock.patch.object(
                    config,
                    "_snapshot_golden_native_config") as mock_gold_snapshot, \
                mock.patch.object(
                    config,
                    "_snapshot_golden_native_init_config") as mock_init_snapshot:
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "-b", "golden_config.json"]
            )

        assert result.exit_code != 0
        assert (
            "trusted profile '{}' is unsupported".format(expected_profile)
            in result.output
        )
        mock_gold_snapshot.assert_not_called()
        mock_init_snapshot.assert_not_called()

    @pytest.mark.parametrize(
        "profile, switch_type, role_flags",
        [
            ("standalone_npu", "npu", {}),
            ("voq_linecard", "voq", {"chassis": True}),
            ("packet_linecard", "chassis-packet", {"chassis": True}),
            (
                "supervisor",
                "npu",
                {"supervisor": True, "chassis": True}
            ),
            (
                "supervisor",
                "fabric",
                {"supervisor": True, "chassis": True}
            ),
            ("fabric_card", "fabric", {"chassis": True}),
            ("smartswitch_host", "npu", {"smartswitch": True}),
            ("dpu", "dpu", {"dpu": True})
        ]
    )
    def test_supported_profile_validates_complete_gold(
            self, get_cmd_module, profile, switch_type, role_flags):
        (config, _) = get_cmd_module
        runner = CliRunner()
        support = self._support(
            config,
            profile,
            switch_type=switch_type,
            supervisor=role_flags.get("supervisor", False),
            chassis=role_flags.get("chassis", False),
            dpu=role_flags.get("dpu", False),
            smartswitch=role_flags.get("smartswitch", False),
            chassis_scope=role_flags.get("chassis", False),
            trusted_device_type=(
                "SmartSwitchDPU" if profile == "dpu" else "ToRRouter"
            )
        )
        golden_config = self._profile_golden_config(
            config, profile, switch_type
        )

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        assert "Golden config validation succeeded." in result.output
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "malformed_metadata, expected_error",
        [
            (
                [],
                "Golden config scope 'localhost' table DEVICE_METADATA must "
                "contain a JSON object."
            ),
            (
                {"localhost": []},
                "Golden config scope 'localhost' DEVICE_METADATA.localhost "
                "must contain a JSON object."
            )
        ]
    )
    def test_malformed_device_metadata_fails_before_yang_validation(
            self, get_cmd_module, malformed_metadata, expected_error):
        (config, _) = get_cmd_module
        runner = CliRunner()
        support = self._support(config, "standalone_npu")
        golden_config = self._valid_golden_config()
        golden_config["DEVICE_METADATA"] = malformed_metadata

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert expected_error in result.output
        mock_yang.assert_not_called()
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "arguments",
        [
            ["-y", "-b", "golden_config.json"],
            ["-y", "--migrate-only", "-b", "golden_config.json"]
        ]
    )
    def test_mismatched_host_device_type_fails_before_yang_or_mutation(
            self, get_cmd_module, arguments):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        golden_config["DEVICE_METADATA"]["localhost"]["type"] = "SpineRouter"

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest") as mock_migrate, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload, \
                    mock.patch.object(
                        config,
                        "_new_golden_native_generation_transaction"
                    ) as mock_transaction:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    arguments
                )

        assert result.exit_code != 0
        assert (
            "device type 'SpineRouter' does not match trusted local device "
            "type 'ToRRouter'"
        ) in result.output
        mock_yang.assert_not_called()
        mock_migrate.assert_not_called()
        mock_reload.assert_not_called()
        mock_transaction.assert_not_called()

    @pytest.mark.parametrize(
        "trusted_metadata",
        [
            {},
            {"type": ""},
            {"type": None},
            {"type": 42}
        ]
    )
    def test_invalid_trusted_device_type_fails_before_file_io(
            self, get_cmd_module, trusted_metadata):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(
                config,
                "_read_trusted_golden_native_device_metadata",
                return_value=trusted_metadata), \
                mock.patch.object(
                    config,
                    "_snapshot_golden_native_config") as mock_gold_snapshot, \
                mock.patch.object(
                    config,
                    "_snapshot_golden_native_init_config") as mock_init_snapshot:
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "-b", "golden_config.json"]
            )

        assert result.exit_code != 0
        assert (
            "trusted DEVICE_METADATA.localhost.type must be a non-empty "
            "string"
        ) in result.output
        mock_gold_snapshot.assert_not_called()
        mock_init_snapshot.assert_not_called()

    @pytest.mark.parametrize(
        "profile, switch_type, missing_table, role_flags",
        [
            (
                "voq_linecard", "voq", "PORT",
                {"chassis": True}
            ),
            (
                "voq_linecard", "voq", "SYSTEM_PORT",
                {"chassis": True}
            ),
            (
                "smartswitch_host", "npu", "DPUS",
                {"smartswitch": True}
            ),
            (
                "smartswitch_host", "npu", "CHASSIS_MODULE",
                {"smartswitch": True}
            ),
            (
                "smartswitch_host", "npu", "DPU",
                {"smartswitch": True}
            ),
            (
                "supervisor", "npu", "PORT",
                {"supervisor": True, "chassis": True}
            ),
            (
                "dpu", "dpu", "PORT",
                {"dpu": True}
            )
        ]
    )
    def test_missing_role_required_table_fails_closed(
            self, get_cmd_module, profile, switch_type, missing_table,
            role_flags):
        (config, _) = get_cmd_module
        runner = CliRunner()
        support = self._support(
            config,
            profile,
            switch_type=switch_type,
            supervisor=role_flags.get("supervisor", False),
            chassis=role_flags.get("chassis", False),
            dpu=role_flags.get("dpu", False),
            smartswitch=role_flags.get("smartswitch", False),
            chassis_scope=role_flags.get("chassis", False),
            trusted_device_type=(
                "SmartSwitchDPU" if profile == "dpu" else "ToRRouter"
            )
        )
        golden_config = self._profile_golden_config(
            config, profile, switch_type
        )
        golden_config.pop(missing_table)

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert (
            "Golden config scope 'localhost' profile '{}' requires non-empty "
            "table '{}'.".format(profile, missing_table)
        ) in result.output
        mock_reload.assert_not_called()

    def test_ambiguous_trusted_profile_fails_before_file_io(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(config.device_info, "is_chassis", return_value=True), \
                mock.patch.object(
                    config,
                    "_golden_native_chassis_scope_present",
                    return_value=True), \
                mock.patch.object(config, "_snapshot_golden_native_config") as mock_gold_snapshot, \
                mock.patch.object(config, "_snapshot_golden_native_init_config") as mock_init_snapshot, \
                mock.patch.object(config, "_validate_golden_native_config") as mock_validate:
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "-b", "golden_config.json"]
            )

        assert result.exit_code != 0
        assert (
            "ambiguous without a supervisor role signal" in
            result.output
        )
        mock_gold_snapshot.assert_not_called()
        mock_init_snapshot.assert_not_called()
        mock_validate.assert_not_called()

    def test_trusted_support_is_resolved_once_and_threaded_unchanged(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        support = self._support(
            config, "standalone_npu"
        )

        def validate(
                _snapshot_name, _display_filename, _init_snapshot_name,
                _init_display_filename, received_support):
            assert received_support is support
            return [(config.DEFAULT_NAMESPACE, self._valid_golden_config())]

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support) as mock_support, \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_config",
                        side_effect=validate):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        mock_support.assert_called_once_with()

    def test_support_detection_exception_fails_before_file_io(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(
                config.device_info,
                "get_num_npus",
                side_effect=RuntimeError("support detection failed")), \
                mock.patch.object(config, "_snapshot_golden_native_config") as mock_gold_snapshot, \
                mock.patch.object(config, "_snapshot_golden_native_init_config") as mock_init_snapshot, \
                mock.patch.object(config, "_validate_golden_native_config") as mock_validate, \
                mock.patch.object(config, "migrate_db_to_lastest") as mock_migrate, \
                mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "-b", "golden_config.json"]
            )

        assert result.exit_code != 0
        assert "support detection failed" in result.output
        mock_gold_snapshot.assert_not_called()
        mock_init_snapshot.assert_not_called()
        mock_validate.assert_not_called()
        mock_migrate.assert_not_called()
        mock_reload.assert_not_called()

    def test_inconsistent_trusted_asic_metadata_fails_before_file_io(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(config.device_info, "get_num_npus", return_value=2), \
                mock.patch.object(config.device_info, "is_multi_npu", return_value=False), \
                mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
                mock.patch.object(
                    config.multi_asic,
                    "get_namespace_list",
                    return_value=["asic0", "asic1"]), \
                mock.patch.object(config, "_snapshot_golden_native_config") as mock_snapshot:
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "-b", "golden_config.json"]
            )

        assert result.exit_code != 0
        assert "inconsistent trusted ASIC-count metadata" in result.output
        mock_snapshot.assert_not_called()

    @pytest.mark.parametrize(
        "namespaces",
        [
            ["asic1", "asic2"],
            ["asic0", "asic2"]
        ]
    )
    def test_non_contiguous_trusted_asic_namespaces_fail_before_file_io(
            self, get_cmd_module, namespaces):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with mock.patch.object(config.device_info, "get_num_npus", return_value=2), \
                mock.patch.object(config.device_info, "is_multi_npu", return_value=True), \
                mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
                mock.patch.object(
                    config.multi_asic,
                    "get_namespace_list",
                    return_value=namespaces), \
                mock.patch.object(config, "_snapshot_golden_native_config") as mock_gold_snapshot, \
                mock.patch.object(config, "_snapshot_golden_native_init_config") as mock_init_snapshot:
            result = runner.invoke(
                config.config.commands["load_golden_config"],
                ["--check-only", "-b", "golden_config.json"]
            )

        assert result.exit_code != 0
        assert "requires zero-based contiguous namespaces" in result.output
        mock_gold_snapshot.assert_not_called()
        mock_init_snapshot.assert_not_called()

    def test_migrate_only_uses_validated_snapshots_without_reloading(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        original_config = self._valid_golden_config()
        original_init_config = self._valid_init_config()

        with runner.isolated_filesystem():
            self._write_json("golden_config.json", original_config)
            self._write_json("init_cfg.json", original_init_config)

            def validate_snapshot(
                    snapshot_name, display_filename, init_snapshot_name,
                    init_display_filename, _support):
                assert display_filename == "golden_config.json"
                assert init_display_filename == "init_cfg.json"
                with open(snapshot_name) as snapshot:
                    assert json.load(snapshot) == original_config
                with open(init_snapshot_name) as init_snapshot:
                    assert json.load(init_snapshot) == original_init_config
                self._write_json("golden_config.json", {"replaced": True})
                self._write_json("init_cfg.json", {"replaced": True})
                return [(config.DEFAULT_NAMESPACE, original_config)]

            def migrate_snapshot(
                    namespace, config_source, snapshot_name, init_snapshot_name):
                assert namespace == config.DEFAULT_NAMESPACE
                assert config_source == config.DB_MIGRATION_SOURCE_GOLDEN
                with open(snapshot_name) as snapshot:
                    assert json.load(snapshot) == original_config
                with open(init_snapshot_name) as init_snapshot:
                    assert json.load(init_snapshot) == original_init_config

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_config",
                        side_effect=validate_snapshot), \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest",
                        side_effect=migrate_snapshot) as mock_migrate, \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "--migrate-only", "-b", "golden_config.json"]
                )

            snapshot_name = mock_migrate.call_args.args[2]
            init_snapshot_name = mock_migrate.call_args.args[3]
            assert result.exit_code == 0
            assert not os.path.exists(snapshot_name)
            assert not os.path.exists(init_snapshot_name)
            mock_reload.assert_not_called()

    def test_reload_delegates_without_sysinfo_or_nested_lock(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload",
                        return_value=None) as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "-f", "golden_config.json"]
                )

            assert result.exit_code == 0
            assert "Acquired lock on" in result.output
            assert "Released lock on" in result.output
            context, filename, no_service_restart, force, init_filename, \
                generation_transaction, persist_generation = \
                mock_reload.call_args.args
            assert isinstance(context, click.Context)
            assert os.path.basename(filename).startswith(
                "golden_config.normalized."
            )
            assert filename.endswith(".json")
            assert not os.path.exists(filename)
            assert os.path.basename(init_filename).startswith("init_cfg.")
            assert init_filename.endswith(".json")
            assert not os.path.exists(init_filename)
            assert no_service_restart is False
            assert force is True
            assert generation_transaction is self._generation_transactions[0]
            assert persist_generation is False

    def test_golden_native_mutation_rejects_no_service_restart(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["load_golden_config"],
            ["-y", "-n", "-b", "golden_config.json"]
        )

        assert result.exit_code == 2
        assert "Redis writers must be quiesced" in result.output

    def test_reload_helper_disables_sysinfo_and_bypasses_nested_lock(self, get_cmd_module):
        (config, _) = get_cmd_module
        context = mock.Mock()

        config._invoke_golden_native_reload(
            context,
            "golden_config.json",
            no_service_restart=True,
            force=True
        )

        context.invoke.assert_called_once_with(
            config.config.commands["reload"],
            filename="golden_config.json",
            yes=True,
            load_sysinfo=False,
            no_service_restart=True,
            force=True,
            file_format="config_db",
            bypass_lock=True,
            migration_config_source=config.DB_MIGRATION_SOURCE_GOLDEN,
            init_config_file=config.INIT_CFG_FILE,
            generation_transaction=None,
            persist_generation=False
        )

    def test_reload_helper_forwards_source_through_click_context(self, get_cmd_module):
        (config, _) = get_cmd_module
        reload_command = config.config.commands["reload"]
        callback = mock.Mock()
        context = click.Context(config.config.commands["load_golden_config"])

        with mock.patch.object(reload_command, "callback", callback):
            config._invoke_golden_native_reload(
                context,
                "golden_config.json",
                no_service_restart=True,
                force=True
            )

        assert callback.call_args.kwargs["migration_config_source"] == \
            config.DB_MIGRATION_SOURCE_GOLDEN
        assert callback.call_args.kwargs["init_config_file"] == config.INIT_CFG_FILE

    def test_reload_migrates_from_the_exact_loaded_gold(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        db = Db()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True), \
                    mock.patch.object(config, "migrate_db_to_lastest") as mock_migrate, \
                    mock.patch(
                        "utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)
                    ):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "-f", "golden_config.json"],
                    obj={"config_db": db.cfgdb}
                )

        assert result.exit_code == 0
        migration_args = mock_migrate.call_args.args
        assert migration_args[:2] == (
            config.DEFAULT_NAMESPACE,
            config.DB_MIGRATION_SOURCE_GOLDEN
        )
        assert os.path.basename(migration_args[2]).startswith(
            "golden_config.normalized."
        )
        assert migration_args[2].endswith(".json")
        assert not os.path.exists(migration_args[2])
        assert os.path.basename(migration_args[3]).startswith("init_cfg.")
        assert migration_args[3].endswith(".json")
        assert not os.path.exists(migration_args[3])

    def test_reload_uses_snapshot_after_source_replacement(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        original_config = self._valid_golden_config()
        original_init_config = self._valid_init_config()

        with runner.isolated_filesystem():
            self._write_json("golden_config.json", original_config)
            self._write_json("init_cfg.json", original_init_config)

            def validate_snapshot(
                    snapshot_name, display_filename, init_snapshot_name,
                    init_display_filename, _support):
                assert display_filename == "golden_config.json"
                assert init_display_filename == "init_cfg.json"
                with open(snapshot_name) as snapshot:
                    assert json.load(snapshot) == original_config
                with open(init_snapshot_name) as init_snapshot:
                    assert json.load(init_snapshot) == original_init_config
                self._write_json("golden_config.json", {"replaced": True})
                self._write_json("init_cfg.json", {"replaced": True})

            def invoke_snapshot(
                    _ctx, snapshot_name, _no_restart, _force,
                    init_snapshot_name, generation_transaction,
                    persist_generation):
                with open(snapshot_name) as snapshot:
                    assert json.load(snapshot) == original_config
                with open(init_snapshot_name) as init_snapshot:
                    assert json.load(init_snapshot) == original_init_config
                assert generation_transaction is self._generation_transactions[0]
                assert persist_generation is False

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                    config,
                    "_validate_golden_native_config",
                    side_effect=validate_snapshot), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload",
                        side_effect=invoke_snapshot) as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "-b", "golden_config.json"]
                )

            snapshot_name = mock_reload.call_args.args[1]
            init_snapshot_name = mock_reload.call_args.args[4]
            assert result.exit_code == 0
            assert not os.path.exists(snapshot_name)
            assert not os.path.exists(init_snapshot_name)
            with open("golden_config.json") as replaced:
                assert json.load(replaced) == {"replaced": True}
            with open("init_cfg.json") as replaced:
                assert json.load(replaced) == {"replaced": True}

    def test_db_migration_uses_exact_golden_source_file(self, get_cmd_module):
        (config, _) = get_cmd_module

        with mock.patch.object(config.os.path, "isfile", return_value=True), \
                mock.patch.object(config.os, "access", return_value=True), \
                mock.patch.object(config.clicommon, "run_command") as mock_run_command:
            config.migrate_db_to_lastest(
                config_source=config.DB_MIGRATION_SOURCE_GOLDEN,
                config_source_file="golden_config.json",
                init_config_file="init_cfg.json"
            )

        mock_run_command.assert_called_once_with(
            [
                "/usr/local/bin/db_migrator.py",
                "-o",
                "migrate",
                "--config-source",
                "golden",
                "--config-source-file",
                "golden_config.json",
                "--init-config-file",
                "init_cfg.json"
            ],
            display_cmd=True
        )

    def test_db_migration_preserves_automatic_source_by_default(self, get_cmd_module):
        (config, _) = get_cmd_module

        with mock.patch.object(config.os.path, "isfile", return_value=True), \
                mock.patch.object(config.os, "access", return_value=True), \
                mock.patch.object(config.clicommon, "run_command") as mock_run_command:
            config.migrate_db_to_lastest()

        mock_run_command.assert_called_once_with(
            ["/usr/local/bin/db_migrator.py", "-o", "migrate"],
            display_cmd=True
        )

    def test_missing_init_config_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            self._write_json("golden_config.json", self._valid_golden_config())
            with mock.patch.object(config, "INIT_CFG_FILE", "missing_init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Failed to snapshot init config 'missing_init_cfg.json'" in result.output

    def test_malformed_init_config_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            with open("init_cfg.json", 'w') as init_file:
                init_file.write("{")
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Failed to read init config 'init_cfg.json'" in result.output

    def test_malformed_golden_config_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            with open("golden_config.json", 'w') as golden_file:
                golden_file.write("{")

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Failed to read golden config 'golden_config.json'" in result.output

    def test_duplicate_wrapped_scope_key_fails_before_yang_validation(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        scope_config = json.dumps(self._valid_golden_config())
        raw_config = (
            '{"localhost": %s, "asic0": %s, "asic1": %s, "localhost": %s}'
            % (scope_config, scope_config, scope_config, scope_config)
        )

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            with open("golden_config.json", 'w') as golden_file:
                golden_file.write(raw_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic, "is_multi_asic", return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Duplicate JSON key 'localhost'" in result.output
        mock_yang.assert_not_called()
        mock_reload.assert_not_called()

    def test_duplicate_table_key_fails_before_yang_validation(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        raw_config = (
            '{"DEVICE_METADATA": %s, "FEATURE": %s, "FEATURE": %s, "PORT": %s}'
            % (
                json.dumps(golden_config["DEVICE_METADATA"]),
                json.dumps(golden_config["FEATURE"]),
                json.dumps(golden_config["FEATURE"]),
                json.dumps(golden_config["PORT"])
            )
        )

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            with open("golden_config.json", 'w') as golden_file:
                golden_file.write(raw_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Duplicate JSON key 'FEATURE'" in result.output
        mock_yang.assert_not_called()
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "switch_type, expected_error",
        [
            (
                "voq",
                "switch_type 'voq' does not match trusted profile "
                "'standalone_npu' switch_type 'npu'"
            ),
            (
                "fabric",
                "switch_type 'fabric' does not match trusted profile "
                "'standalone_npu' switch_type 'npu'"
            ),
            (
                "chassis-packet",
                "switch_type 'chassis-packet' does not match trusted profile "
                "'standalone_npu' switch_type 'npu'"
            ),
            (
                "dpu",
                "switch_type 'dpu' does not match trusted profile "
                "'standalone_npu' switch_type 'npu'"
            ),
            (None, "switch_type must be a string"),
            (7, "switch_type must be a string")
        ]
    )
    def test_candidate_switch_type_fails_before_yang_validation(
            self, get_cmd_module, switch_type, expected_error):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        golden_config["DEVICE_METADATA"]["localhost"]["switch_type"] = switch_type

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest") as mock_migrate, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert expected_error in result.output
        mock_yang.assert_not_called()
        mock_migrate.assert_not_called()
        mock_reload.assert_not_called()

    def test_wrapped_candidate_switch_type_reports_failing_scope_before_yang(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        golden_config["asic1"]["DEVICE_METADATA"]["localhost"]["switch_type"] = "dpu"

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic, "is_multi_asic", return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert (
            "scope 'asic1' switch_type 'dpu' does not match trusted profile "
            "'standalone_npu' switch_type 'npu'" in result.output
        )
        mock_yang.assert_not_called()
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "switch_type_present, switch_type, expected_switch_type",
        [
            (False, None, None),
            (True, "", None),
            (True, "   ", None),
            (True, "npu", "npu"),
            (True, " NpU ", "npu")
        ]
    )
    def test_candidate_switch_type_is_normalized_for_yang_and_reload(
            self, get_cmd_module, switch_type_present, switch_type,
            expected_switch_type):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        if switch_type_present:
            golden_config["DEVICE_METADATA"]["localhost"]["switch_type"] = \
                switch_type
        observed_paths = {}

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)
            with open("golden_config.json", "rb") as source:
                original_source = source.read()

            def assert_normalized_snapshot(snapshot_name):
                with open(snapshot_name) as snapshot:
                    normalized_config = json.load(snapshot)
                metadata = normalized_config["DEVICE_METADATA"]["localhost"]
                if expected_switch_type is None:
                    assert "switch_type" not in metadata
                else:
                    assert metadata["switch_type"] == expected_switch_type
                assert (os.stat(snapshot_name).st_mode & 0o777) == 0o600

            def validate_normalized_snapshot(snapshot_name, _scope_configs):
                assert_normalized_snapshot(snapshot_name)
                observed_paths["yang"] = snapshot_name
                return True

            def reload_normalized_snapshot(
                    _ctx, snapshot_name, _no_restart, _force,
                    _init_snapshot_name, generation_transaction,
                    _persist_generation):
                assert_normalized_snapshot(snapshot_name)
                observed_paths["reload"] = snapshot_name
                assert generation_transaction is self._generation_transactions[0]

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        side_effect=validate_normalized_snapshot), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload",
                        side_effect=reload_normalized_snapshot) as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "-b", "golden_config.json"]
                )
            with open("golden_config.json", "rb") as source:
                final_source = source.read()

        assert result.exit_code == 0
        mock_reload.assert_called_once()
        assert observed_paths["yang"] == observed_paths["reload"]
        assert os.path.basename(observed_paths["reload"]).startswith(
            "golden_config.normalized."
        )
        assert not os.path.exists(observed_paths["reload"])
        assert final_source == original_source

    def test_migrate_only_uses_normalized_switch_type_snapshot(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        golden_config["DEVICE_METADATA"]["localhost"]["switch_type"] = " NpU "
        observed_paths = {}

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)
            with open("golden_config.json", "rb") as source:
                original_source = source.read()

            def assert_normalized_snapshot(snapshot_name):
                with open(snapshot_name) as snapshot:
                    normalized_config = json.load(snapshot)
                assert normalized_config["DEVICE_METADATA"]["localhost"][
                    "switch_type"
                ] == "npu"
                assert (os.stat(snapshot_name).st_mode & 0o777) == 0o600

            def validate_normalized_snapshot(snapshot_name, _scope_configs):
                assert_normalized_snapshot(snapshot_name)
                observed_paths["yang"] = snapshot_name
                return True

            def migrate_normalized_snapshot(
                    _namespace, _config_source, snapshot_name,
                    _init_snapshot_name):
                assert_normalized_snapshot(snapshot_name)
                observed_paths["migration"] = snapshot_name

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        side_effect=validate_normalized_snapshot), \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest",
                        side_effect=migrate_normalized_snapshot), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "--migrate-only", "-b", "golden_config.json"]
                )
            with open("golden_config.json", "rb") as source:
                final_source = source.read()

        assert result.exit_code == 0
        mock_reload.assert_not_called()
        assert observed_paths["yang"] == observed_paths["migration"]
        assert os.path.basename(observed_paths["migration"]).startswith(
            "golden_config.normalized."
        )
        assert not os.path.exists(observed_paths["migration"])
        assert final_source == original_source

    def test_yang_invalid_golden_config_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=False):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Invalid golden config file 'golden_config.json'" in result.output

    def test_missing_required_metadata_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        del golden_config["DEVICE_METADATA"]["localhost"]["mac"]

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "DEVICE_METADATA.localhost.mac" in result.output

    def test_missing_device_type_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        del golden_config["DEVICE_METADATA"]["localhost"]["type"]

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "DEVICE_METADATA.localhost.type" in result.output

    def test_trusted_identity_uses_local_sources(self, get_cmd_module):
        (config, _) = get_cmd_module

        with mock.patch.object(
                config.device_info, "get_hostname", return_value="trusted-host"), \
                mock.patch.object(
                    config.device_info,
                    "get_platform",
                    return_value="x86_64-kvm_x86_64-r0") as mock_get_platform, \
                mock.patch.object(
                    config.device_info,
                    "get_hwsku",
                    return_value="Force10-S6000"), \
                mock.patch.object(
                    config.device_info,
                    "get_system_mac",
                    return_value="00:01:02:03:04:05") as mock_get_system_mac:
            identity = config._read_trusted_golden_native_identity()

        assert identity == {
            "platform": "x86_64-kvm_x86_64-r0",
            "hwsku": "Force10-S6000",
            "hostname": "trusted-host",
            "mac": "00:01:02:03:04:05",
        }
        mock_get_platform.assert_called_once_with(config_db=None)
        mock_get_system_mac.assert_called_once_with(hostname="trusted-host")

    @pytest.mark.parametrize("field,candidate_value,trusted_value", [
        ("hostname", "other-host", "sonic"),
        ("platform", "x86_64-other-r0", "x86_64-kvm_x86_64-r0"),
        ("hwsku", "Other-HWSKU", "Force10-S6000"),
        ("mac", "00:01:02:03:04:06", "00:01:02:03:04:05"),
    ])
    def test_mismatched_device_identity_fails_closed(
            self, get_cmd_module, field, candidate_value, trusted_value):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        golden_config["DEVICE_METADATA"]["localhost"][field] = candidate_value
        trusted_identity = {
            "hostname": "sonic",
            "platform": "x86_64-kvm_x86_64-r0",
            "mac": "00:01:02:03:04:05",
            "hwsku": "Force10-S6000"
        }
        trusted_identity[field] = trusted_value

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True), \
                    mock.patch.object(
                        config,
                        "_read_trusted_golden_native_identity",
                        return_value=trusted_identity):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "does not match trusted local device identity" in result.output
        assert "DEVICE_METADATA.localhost.{}".format(field) in result.output

    def test_mac_identity_comparison_is_case_and_separator_insensitive(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", self._valid_golden_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True), \
                    mock.patch.object(
                        config,
                        "_read_trusted_golden_native_identity",
                        return_value={
                            "hostname": "sonic",
                            "platform": "x86_64-kvm_x86_64-r0",
                            "mac": "00-01-02-03-04-05",
                            "hwsku": "Force10-S6000"
                        }):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0

    def test_incomplete_golden_config_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        del golden_config["FEATURE"]["bgp"]["state"]

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "FEATURE.bgp.state" in result.output

    def test_missing_hwsku_config_fails_closed(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        del golden_config["PORT"]

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "HWSKU config: PORT" in result.output

    def test_hard_dependency_failure_is_propagated(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_golden_config()
        golden_config["AAA"] = {"authentication": {"login": "tacacs+"}}
        golden_config["TACPLUS"] = {"global": {}}

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False), \
                    mock.patch.object(config, "_config_scopes_yang_validation", return_value=True):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert "Authentication with 'tacacs+' is not allowed" in result.output

    def test_multiasic_check_only_validates_host_and_asic_scopes(self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config,
                        "_read_hardware_config",
                        return_value=self._valid_hardware_config()) as mock_hardware, \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        assert "Golden config validation succeeded." in result.output
        assert golden_config["asic0"]["DEVICE_METADATA"]["localhost"][
            "asic_id"
        ] == "01.00.0"
        assert "asic_id" not in golden_config["asic1"][
            "DEVICE_METADATA"
        ]["localhost"]
        assert mock_hardware.call_args_list == [
            mock.call("multi_asic", "asic0"),
            mock.call("multi_asic", "asic1")
        ]
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "host_hwsku, expected_error",
        [
            (
                None,
                "localhost.DEVICE_METADATA.localhost.hwsku"
            ),
            (
                "Other-HWSKU",
                "localhost.DEVICE_METADATA.localhost.hwsku expected "
                "'Force10-S6000', got 'Other-HWSKU'"
            )
        ]
    )
    def test_multiasic_host_hwsku_is_required_and_trusted(
            self, get_cmd_module, host_hwsku, expected_error):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        host_metadata = golden_config["localhost"]["DEVICE_METADATA"][
            "localhost"
        ]
        if host_hwsku is None:
            del host_metadata["hwsku"]
        else:
            host_metadata["hwsku"] = host_hwsku

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic,
                        "is_multi_asic",
                        return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert expected_error in result.output
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "invalid_case, expected_error",
        [
            ("missing_host", "missing scopes: localhost"),
            ("missing_asic", "missing scopes: asic1"),
            ("extra_asic", "extra scopes: asic2"),
            ("empty_scope", "scope 'asic1' must not be empty"),
            ("non_object_scope", "scope 'asic1' must contain a JSON object")
        ]
    )
    def test_multiasic_wrapper_fails_before_migration(
            self, get_cmd_module, invalid_case, expected_error):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()

        if invalid_case == "missing_host":
            del golden_config["localhost"]
        elif invalid_case == "missing_asic":
            del golden_config["asic1"]
        elif invalid_case == "extra_asic":
            golden_config["asic2"] = self._valid_golden_config()
        elif invalid_case == "empty_scope":
            golden_config["asic1"] = {}
        else:
            golden_config["asic1"] = []

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(config, "migrate_db_to_lastest") as mock_migrate, \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "--migrate-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert expected_error in result.output
        mock_migrate.assert_not_called()
        mock_reload.assert_not_called()

    def test_multiasic_scope_ownership_fails_closed(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        metadata = golden_config["asic0"]["DEVICE_METADATA"]["localhost"]
        metadata["asic_name"] = "asic9"

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert (
            "scope 'asic0' must set DEVICE_METADATA.localhost.asic_name "
            "to 'asic0'"
        ) in result.output
        mock_reload.assert_not_called()

    def test_multiasic_namespace_identity_is_scope_local(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        metadata = golden_config["asic0"]["DEVICE_METADATA"]["localhost"]
        metadata.update({
            "platform": "namespace-platform",
            "hostname": "namespace-host",
            "mac": "02:42:f0:7f:99:99",
            "hwsku": "namespace-hwsku",
            "asic_id": "08:00.0",
        })
        golden_config["asic1"]["DEVICE_METADATA"]["localhost"].pop(
            "asic_id",
            None
        )

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic,
                        "is_multi_asic",
                        return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(
                        config,
                        "_read_hardware_config",
                        return_value=self._valid_hardware_config()), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        mock_reload.assert_not_called()

    def test_multiasic_namespace_device_types_are_scope_local(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        golden_config["asic0"]["DEVICE_METADATA"]["localhost"][
            "type"
        ] = "BackEndToRRouter"
        golden_config["asic1"]["DEVICE_METADATA"]["localhost"][
            "type"
        ] = "SpineRouter"

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic,
                        "is_multi_asic",
                        return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True) as mock_yang, \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        mock_yang.assert_called_once()
        mock_reload.assert_not_called()

    def test_multiasic_scope_name_is_trimmed_and_normalized(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        golden_config["asic0"]["DEVICE_METADATA"]["localhost"][
            "asic_name"
        ] = " ASIC0 "

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            def validate_normalized_snapshot(snapshot_name, _scope_configs):
                with open(snapshot_name) as snapshot:
                    normalized_config = json.load(snapshot)
                assert normalized_config["asic0"]["DEVICE_METADATA"][
                    "localhost"
                ]["asic_name"] == "asic0"
                return True

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config.multi_asic,
                        "is_multi_asic",
                        return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        side_effect=validate_normalized_snapshot), \
                    mock.patch.object(
                        config,
                        "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        mock_reload.assert_not_called()

    @pytest.mark.parametrize(
        "missing_source, expected_error",
        [
            (
                "init",
                "scope 'asic1' does not completely cover init config: FEATURE.bgp.state"
            ),
            (
                "hardware",
                "scope 'asic1' does not completely cover HWSKU config: PORT.Ethernet0"
            )
        ]
    )
    def test_multiasic_scope_completeness_reports_failing_scope(
            self, get_cmd_module, missing_source, expected_error):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        if missing_source == "init":
            del golden_config["asic1"]["FEATURE"]["bgp"]["state"]
        else:
            del golden_config["asic1"]["PORT"]["Ethernet0"]

        with runner.isolated_filesystem():
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("golden_config.json", golden_config)

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
                    mock.patch.object(
                        config.multi_asic,
                        "get_namespace_list",
                        return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config,
                        "_config_scopes_yang_validation",
                        return_value=True), \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["--check-only", "-b", "golden_config.json"]
                )

        assert result.exit_code != 0
        assert expected_error in result.output
        mock_reload.assert_not_called()

    def test_multiasic_migrate_only_uses_one_snapshot_in_scope_order(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        original_config = self._valid_multiasic_golden_config()
        original_init_config = self._valid_init_config()
        scope_configs = [
            (config.DEFAULT_NAMESPACE, original_config["localhost"]),
            ("asic0", original_config["asic0"]),
            ("asic1", original_config["asic1"])
        ]
        support = self._support(
            config,
            "standalone_npu",
            num_asics=2,
            namespaces=("asic0", "asic1")
        )

        with runner.isolated_filesystem():
            self._write_json("golden_config.json", original_config)
            self._write_json("init_cfg.json", original_init_config)

            def validate_snapshot(
                    snapshot_name, display_filename, init_snapshot_name,
                    init_display_filename, _support):
                assert display_filename == "golden_config.json"
                assert init_display_filename == "init_cfg.json"
                with open(snapshot_name) as snapshot:
                    assert json.load(snapshot) == original_config
                with open(init_snapshot_name) as init_snapshot:
                    assert json.load(init_snapshot) == original_init_config
                self._write_json("golden_config.json", {"replaced": True})
                self._write_json("init_cfg.json", {"replaced": True})
                return scope_configs

            def migrate_snapshot(
                    namespace, config_source, snapshot_name, init_snapshot_name):
                assert config_source == config.DB_MIGRATION_SOURCE_GOLDEN
                with open(snapshot_name) as snapshot:
                    assert json.load(snapshot) == original_config
                with open(init_snapshot_name) as init_snapshot:
                    assert json.load(init_snapshot) == original_init_config

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_config",
                        side_effect=validate_snapshot), \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest",
                        side_effect=migrate_snapshot) as mock_migrate, \
                    mock.patch.object(config, "_invoke_golden_native_reload") as mock_reload:
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "--migrate-only", "-b", "golden_config.json"]
                )

        assert result.exit_code == 0
        assert [migration_call.args[0] for migration_call in mock_migrate.call_args_list] == [
            config.DEFAULT_NAMESPACE,
            "asic0",
            "asic1"
        ]
        assert len({
            migration_call.args[2] for migration_call in mock_migrate.call_args_list
        }) == 1
        assert len({
            migration_call.args[3] for migration_call in mock_migrate.call_args_list
        }) == 1
        snapshot_name = mock_migrate.call_args.args[2]
        init_snapshot_name = mock_migrate.call_args.args[3]
        assert not os.path.exists(snapshot_name)
        assert not os.path.exists(init_snapshot_name)
        mock_reload.assert_not_called()

    def test_multiasic_write_failure_rolls_back_prior_scopes(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        transaction = self._new_recording_transaction(config)
        original_error = RuntimeError("asic1 write failed")
        connector = mock.MagicMock()
        connector.INIT_INDICATOR = "CONFIG_DB_INITIALIZED"
        clients = [
            (mock.MagicMock(), mock.MagicMock()),
            (mock.MagicMock(), mock.MagicMock())
        ]
        clients[0][1].INIT_INDICATOR = "CONFIG_DB_INITIALIZED"
        clients[1][1].INIT_INDICATOR = "CONFIG_DB_INITIALIZED"

        def flush_configdb(namespace):
            if namespace == "asic1":
                raise original_error
            return clients.pop(0)

        with CliRunner().isolated_filesystem():
            self._write_json(
                "golden_config.json",
                self._valid_multiasic_golden_config()
            )
            with mock.patch.object(
                    config.multi_asic,
                    "get_namespace_list",
                    return_value=["asic0", "asic1"]), \
                    mock.patch.object(
                        config, "load_sysinfo_if_missing", return_value=False), \
                    mock.patch.object(
                        config, "flush_configdb", side_effect=flush_configdb), \
                    mock.patch.object(
                        config, "ConfigDBPipeConnector",
                        return_value=connector), \
                    mock.patch.object(
                        config.sonic_cfggen.FormatConverter,
                        "to_deserialized"), \
                    mock.patch.object(
                        config.sonic_cfggen.FormatConverter,
                        "output_to_db",
                        side_effect=lambda value: value), \
                    mock.patch.object(
                        config, "migrate_db_to_lastest") as mock_migrate:
                with pytest.raises(RuntimeError) as caught:
                    with config._generation_transaction_context(transaction):
                        config.multiasic_write_to_db(
                            "golden_config.json",
                            load_sysinfo=False,
                            migration_config_source=(
                                config.DB_MIGRATION_SOURCE_GOLDEN),
                            init_config_file="init_cfg.json",
                            generation_transaction=transaction
                        )

        assert caught.value is original_error
        assert [
            event[1] for event in transaction.events
            if event[0] == "mark_scope"
        ] == [config.DEFAULT_NAMESPACE, "asic0", "asic1"]
        assert [
            migration_call.args[0]
            for migration_call in mock_migrate.call_args_list
        ] == [config.DEFAULT_NAMESPACE, "asic0"]
        assert ("rollback", original_error) in transaction.events
        assert "commit" not in transaction.events

    def test_multiasic_migrate_only_later_failure_rolls_back(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        original_error = RuntimeError("asic1 migration failed")
        golden_config = self._valid_multiasic_golden_config()
        scope_configs = [
            (config.DEFAULT_NAMESPACE, golden_config["localhost"]),
            ("asic0", golden_config["asic0"]),
            ("asic1", golden_config["asic1"])
        ]
        support = self._support(
            config,
            "standalone_npu",
            num_asics=2,
            namespaces=("asic0", "asic1")
        )
        migrated_namespaces = []

        def migrate(namespace, *_args):
            migrated_namespaces.append(namespace)
            if namespace == "asic1":
                raise original_error

        with runner.isolated_filesystem():
            self._write_json("golden_config.json", golden_config)
            self._write_json("init_cfg.json", self._valid_init_config())

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_config",
                        return_value=scope_configs), \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest",
                        side_effect=migrate):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    ["-y", "--migrate-only", "-b", "golden_config.json"]
                )

        transaction = self._generation_transactions[0]
        assert result.exit_code != 0
        assert migrated_namespaces == [
            config.DEFAULT_NAMESPACE,
            "asic0",
            "asic1"
        ]
        assert [
            event[1] for event in transaction.events
            if event[0] == "mark_scope"
        ] == [config.DEFAULT_NAMESPACE, "asic0", "asic1"]
        assert ("rollback", original_error) in transaction.events
        assert "commit" not in transaction.events

    def test_migrate_only_preloads_and_persists_inside_one_transaction(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        runner = CliRunner()
        golden_config = self._valid_multiasic_golden_config()
        support = self._support(
            config,
            "standalone_npu",
            num_asics=2,
            namespaces=("asic0", "asic1"),
        )
        scope_configs = [
            (config.DEFAULT_NAMESPACE, golden_config["localhost"]),
            ("asic0", golden_config["asic0"]),
            ("asic1", golden_config["asic1"]),
        ]
        preload_paths = []

        def record_preload(namespace, filename, _init_filename, write):
            preload_paths.append(filename)
            self._generation_transaction_events.append(
                ("preload-write" if write else "preload-check", namespace)
            )

        def record_migration(namespace, *_args):
            self._generation_transaction_events.append(
                ("migrate", namespace)
            )

        with runner.isolated_filesystem():
            self._write_json("golden_config.json", golden_config)
            self._write_json("init_cfg.json", self._valid_init_config())
            self._write_json("config_db0.json", {"scope": "asic0"})

            with mock.patch.object(config, "INIT_CFG_FILE", "init_cfg.json"), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_platform_support",
                        return_value=support), \
                    mock.patch.object(
                        config,
                        "_validate_golden_native_config",
                        return_value=scope_configs), \
                    mock.patch.object(
                        config,
                        "_run_golden_native_namespace_config",
                        side_effect=record_preload), \
                    mock.patch.object(
                        config,
                        "migrate_db_to_lastest",
                        side_effect=record_migration), \
                    mock.patch.object(
                        config,
                        "_set_generation_config_db_initialized",
                        side_effect=lambda _transaction:
                            self._generation_transaction_events.append(
                                "initialized"
                            )), \
                    mock.patch.object(
                        config,
                        "_persist_generation_config_files",
                        side_effect=lambda _transaction:
                            self._generation_transaction_events.append(
                                "persisted"
                            )), \
                    mock.patch.object(
                        config,
                        "_stop_services",
                        side_effect=lambda:
                            self._generation_transaction_events.append(
                                ("service", "stop")
                            )), \
                    mock.patch.object(
                        config,
                        "_reset_failed_services",
                        side_effect=lambda:
                            self._generation_transaction_events.append(
                                ("service", "reset")
                            )), \
                    mock.patch.object(
                        config,
                        "update_sonic_environment",
                        side_effect=lambda:
                            self._generation_transaction_events.append(
                                ("service", "environment")
                            )), \
                    mock.patch.object(
                        config,
                        "_restart_services",
                        side_effect=lambda:
                            self._generation_transaction_events.append(
                                ("service", "restart")
                            )):
                result = runner.invoke(
                    config.config.commands["load_golden_config"],
                    [
                        "-y",
                        "--migrate-only",
                        "--preload-namespace-config",
                        "asic0",
                        "config_db0.json",
                        "-b",
                        "golden_config.json",
                    ]
                )

        events = self._generation_transaction_events
        assert result.exit_code == 0
        ordered_events = [
            "begin",
            ("service", "stop"),
            ("preload-write", "asic0"),
            ("migrate", config.DEFAULT_NAMESPACE),
            ("migrate", "asic0"),
            ("migrate", "asic1"),
            "initialized",
            "persisted",
            ("service", "reset"),
            ("service", "environment"),
            ("service", "restart"),
            "commit",
        ]
        assert [
            event for event in events if event in ordered_events
        ] == ordered_events
        assert len(set(preload_paths)) == 1
        assert preload_paths[0] != "config_db0.json"
        assert not os.path.exists(preload_paths[0])

    def test_generation_context_rolls_back_system_exit_and_preserves_identity(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        transaction = self._new_recording_transaction(config)
        original_error = SystemExit(17)

        with pytest.raises(SystemExit) as caught:
            with config._generation_transaction_context(transaction):
                raise original_error

        assert caught.value is original_error
        assert ("rollback", original_error) in transaction.events
        assert "commit" not in transaction.events

    def test_generation_context_surfaces_rollback_failure_aggregation(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        transaction = self._new_recording_transaction(config)
        original_error = RuntimeError("write failed")
        rollback_error = GenerationRollbackError(
            original_error,
            [
                "CONFIG_DB restore failed",
                "service recovery failed"
            ],
            "/tmp/generation-rollback-evidence"
        )
        transaction.rollback_error = rollback_error

        with pytest.raises(GenerationRollbackError) as caught:
            with config._generation_transaction_context(transaction):
                raise original_error

        assert caught.value is rollback_error
        assert caught.value.original_error is original_error
        assert caught.value.failures == (
            "CONFIG_DB restore failed",
            "service recovery failed"
        )
        assert caught.value.evidence_directory == \
            "/tmp/generation-rollback-evidence"

    def test_reload_write_failure_rolls_back_then_recovers_services(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        original_error = RuntimeError("CONFIG_DB write failed")

        result, service_calls = self._invoke_real_single_asic_reload(
            config,
            run_command_error=original_error
        )

        transaction = self._generation_transactions[0]
        assert result.exit_code != 0
        assert result.exception is original_error
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        assert transaction.events.index(("rollback", original_error)) < \
            transaction.events.index(("service", "reset"))
        assert transaction.events.index(("service", "reset")) < \
            transaction.events.index(("service", "environment"))
        assert transaction.events.index(("service", "environment")) < \
            transaction.events.index(("service", "restart"))
        assert "commit" not in transaction.events

    def test_reload_restart_failure_rolls_back_and_recovers_services(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        original_error = RuntimeError("service restart failed")

        result, service_calls = self._invoke_real_single_asic_reload(
            config,
            restart_results=[original_error, None]
        )

        transaction = self._generation_transactions[0]
        assert result.exit_code != 0
        assert result.exception is original_error
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart",
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        rollback_index = transaction.events.index(
            ("rollback", original_error)
        )
        assert rollback_index < len(transaction.events) - 1
        assert transaction.events[rollback_index + 1:] == [
            "service_quiescence",
            ("service", "stop"),
            "service_recovery",
            ("service", "reset"),
            ("service", "environment"),
            ("service", "restart")
        ]
        assert "commit" not in transaction.events

    def test_reload_commits_only_after_successful_service_restart(
            self, get_cmd_module):
        (config, _) = get_cmd_module

        result, service_calls = self._invoke_real_single_asic_reload(config)

        transaction = self._generation_transactions[0]
        assert result.exit_code == 0
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        assert transaction.events.index("begin") < \
            transaction.events.index(("service", "stop"))
        assert transaction.events.index(("service", "reset")) < \
            transaction.events.index(("service", "environment"))
        assert transaction.events.index(("service", "environment")) < \
            transaction.events.index(("service", "restart"))
        assert transaction.events.index(("service", "restart")) < \
            transaction.events.index("commit")
        assert not any(event[0] == "rollback" for event in transaction.events)

    def test_reload_attempts_restart_when_reset_failed(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        original_error = SystemExit(17)

        result, service_calls = self._invoke_real_single_asic_reload(
            config,
            reset_results=[original_error, None]
        )

        transaction = self._generation_transactions[0]
        assert result.exit_code != 0
        assert result.exception is original_error
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart",
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        first_reset = transaction.events.index(("service", "reset"))
        first_environment = transaction.events.index(
            ("service", "environment")
        )
        first_restart = transaction.events.index(("service", "restart"))
        assert first_reset < first_environment < first_restart
        assert "commit" not in transaction.events

    def test_reload_attempts_restart_when_environment_generation_failed(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        original_error = RuntimeError("environment generation failed")

        result, service_calls = self._invoke_real_single_asic_reload(
            config,
            environment_results=[original_error, None]
        )

        transaction = self._generation_transactions[0]
        assert result.exit_code != 0
        assert result.exception is original_error
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart",
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        first_environment = transaction.events.index(
            ("service", "environment")
        )
        first_restart = transaction.events.index(("service", "restart"))
        assert first_environment < first_restart
        assert "commit" not in transaction.events

    def test_reload_generic_commit_failure_rolls_back_and_recovers_services(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        commit_error = RuntimeError("generation commit failed")
        self._generation_transaction_commit_error = commit_error

        result, service_calls = self._invoke_real_single_asic_reload(config)

        transaction = self._generation_transactions[0]
        assert result.exit_code != 0
        assert result.exception is commit_error
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart",
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        assert transaction.events.index("commit") < \
            transaction.events.index(("rollback", commit_error))
        rollback_index = transaction.events.index(
            ("rollback", commit_error)
        )
        assert transaction.events[rollback_index + 1:] == [
            "service_quiescence",
            ("service", "stop"),
            "service_recovery",
            ("service", "reset"),
            ("service", "environment"),
            ("service", "restart")
        ]

    @pytest.mark.parametrize(
        "arguments",
        [
            ["-y", "-f", "-b", "golden_config.json"],
            ["-y", "--migrate-only", "-b", "golden_config.json"],
        ]
    )
    def test_cleanup_failure_after_commit_exits_three_without_rollback(
            self, get_cmd_module, arguments):
        (config, _) = get_cmd_module
        cleanup_error = GenerationCleanupError(
            "committed evidence cleanup failed"
        )
        self._generation_transaction_commit_error = cleanup_error

        result, service_calls = self._invoke_real_single_asic_reload(
            config,
            arguments=arguments
        )

        transaction = self._generation_transactions[0]
        assert result.exit_code == 3
        assert isinstance(result.exception, SystemExit)
        click_error = result.exception.__context__
        assert isinstance(
            click_error,
            config.GoldenNativeCommittedCleanupError
        )
        assert click_error.__cause__ is cleanup_error
        assert "configuration committed successfully" in result.output.lower()
        assert service_calls == [
            "stop",
            "reset",
            "environment",
            "restart"
        ]
        assert transaction.events.index(("service", "restart")) < \
            transaction.events.index("commit")
        assert "commit" in transaction.events
        assert not any(
            isinstance(event, tuple) and event[0] == "rollback"
            for event in transaction.events
        )

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestHardwareConfigGeneration(object):
    @pytest.mark.parametrize(
        "namespace, expected_command",
        [
            (
                "",
                [
                    config.SONIC_CFGGEN_PATH,
                    "-H",
                    "-k",
                    "Force10-S6000",
                    "--print-data"
                ]
            ),
            (
                "asic0",
                [
                    config.SONIC_CFGGEN_PATH,
                    "-H",
                    "-k",
                    "Force10-S6000",
                    "-n",
                    "asic0",
                    "--print-data"
                ]
            )
        ]
    )
    def test_hardware_config_generation_is_namespace_aware(
            self, get_cmd_module, namespace, expected_command):
        (config, _) = get_cmd_module
        hardware_config = TestLoadGoldenConfig._valid_hardware_config()
        completed = mock.Mock(stdout=json.dumps(hardware_config))

        with mock.patch.object(
                config.subprocess,
                "run",
                return_value=completed) as mock_run:
            assert config._read_hardware_config(
                "Force10-S6000", namespace
            ) == hardware_config

        mock_run.assert_called_once_with(
            expected_command,
            check=True,
            capture_output=True,
            text=True
        )


class TestBMPConfig(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        yield
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    @pytest.mark.parametrize("table_name", [
        "bgp-neighbor-table",
        "bgp-rib-in-table",
        "bgp-rib-out-table"
    ])
    @pytest.mark.parametrize("enabled", ["true", "false"])
    @pytest.mark.parametrize("filename", ["bmp_invalid.json", "bmp.json"])
    def test_enable_disable_table(
            self,
            get_cmd_module,
            setup_single_broadcom_asic,
            table_name,
            enabled,
            filename):
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_bmp_db_path, filename)
        config.DEFAULT_CONFIG_DB_FILE = jsonfile_config
        runner = CliRunner()
        db = Db()

        # Enable table
        result = runner.invoke(config.config.commands["bmp"].commands["enable"],
                               [table_name], obj=db)
        assert result.exit_code == 0

        # Disable table
        result = runner.invoke(config.config.commands["bmp"].commands["disable"],
                               [table_name], obj=db)
        assert result.exit_code == 0

        # Enable table again
        result = runner.invoke(config.config.commands["bmp"].commands["enable"],
                               [table_name], obj=db)
        assert result.exit_code == 0


class TestConfigReloadMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def _create_dummy_config(self, path, content):
        """Helper method to create a dummy config file with JSON content."""
        with open(path, 'w') as f:
            f.write(json.dumps(content))

    def test_config_reload_onefile_masic(self):
        def read_json_file_side_effect(filename):
            return {
                "localhost": {
                    "DEVICE_METADATA": {
                        "localhost": {
                            "default_bgp_status": "down",
                            "default_pfcwd_status": "enable",
                            "deployment_id": "1",
                            "docker_routing_config_mode": "separated",
                            "hostname": "sonic-switch",
                            "hwsku": "Mellanox-SN3800-D112C8",
                            "mac": "1d:34:db:16:a6:00",
                            "platform": "x86_64-mlnx_msn3800-r0",
                            "peer_switch": "sonic-switch",
                            "type": "ToRRouter",
                            "suppress-fib-pending": "enabled"
                        }
                    }
                },
                "asic0": {
                    "DEVICE_METADATA": {
                        "localhost": {
                            "asic_id": "01.00.0",
                            "asic_name": "asic0",
                            "bgp_asn": "65100",
                            "cloudtype": "None",
                            "default_bgp_status": "down",
                            "default_pfcwd_status": "enable",
                            "deployment_id": "1",
                            "docker_routing_config_mode": "separated",
                            "hostname": "sonic",
                            "hwsku": "multi_asic",
                            "mac": "02:42:f0:7f:01:05",
                            "platform": "multi_asic",
                            "region": "None",
                            "sub_role": "FrontEnd",
                            "type": "LeafRouter"
                        }
                    }
                },
                "asic1": {
                    "DEVICE_METADATA": {
                        "localhost": {
                            "asic_id": "08:00.0",
                            "asic_name": "asic1",
                            "bgp_asn": "65100",
                            "cloudtype": "None",
                            "default_bgp_status": "down",
                            "default_pfcwd_status": "enable",
                            "deployment_id": "1",
                            "docker_routing_config_mode": "separated",
                            "hostname": "sonic",
                            "hwsku": "multi_asic",
                            "mac": "02:42:f0:7f:01:06",
                            "platform": "multi_asic",
                            "region": "None",
                            "sub_role": "BackEnd",
                            "type": "LeafRouter"
                        }
                    }
                }
            }

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)), \
                mock.patch(
                    'config.main.config_file_yang_validation',
                    return_value=True):

            runner = CliRunner()

            result = runner.invoke(config.config.commands["reload"], ["-y", "-f", "all_config_db.json"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == \
                reload_config_masic_onefile_output.format(config.SYSTEM_RELOAD_LOCK)

    def test_config_reload_onefile_gen_sysinfo_masic(self):
        def read_json_file_side_effect(filename):
            return {
                "localhost": {
                    "DEVICE_METADATA": {
                        "localhost": {
                            "default_bgp_status": "down",
                            "default_pfcwd_status": "enable",
                            "deployment_id": "1",
                            "docker_routing_config_mode": "separated",
                            "hostname": "sonic-switch",
                            "hwsku": "Mellanox-SN3800-D112C8",
                            "peer_switch": "sonic-switch",
                            "type": "ToRRouter",
                            "suppress-fib-pending": "enabled"
                        }
                    }
                },
                "asic0": {
                    "DEVICE_METADATA": {
                        "localhost": {
                            "asic_id": "01.00.0",
                            "asic_name": "asic0",
                            "bgp_asn": "65100",
                            "cloudtype": "None",
                            "default_bgp_status": "down",
                            "default_pfcwd_status": "enable",
                            "deployment_id": "1",
                            "docker_routing_config_mode": "separated",
                            "hostname": "sonic",
                            "hwsku": "multi_asic",
                            "region": "None",
                            "sub_role": "FrontEnd",
                            "type": "LeafRouter"
                        }
                    }
                },
                "asic1": {
                    "DEVICE_METADATA": {
                        "localhost": {
                            "asic_id": "08:00.0",
                            "asic_name": "asic1",
                            "bgp_asn": "65100",
                            "cloudtype": "None",
                            "default_bgp_status": "down",
                            "default_pfcwd_status": "enable",
                            "deployment_id": "1",
                            "docker_routing_config_mode": "separated",
                            "hostname": "sonic",
                            "hwsku": "multi_asic",
                            "region": "None",
                            "sub_role": "BackEnd",
                            "type": "LeafRouter"
                        }
                    }
                }
            }

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)), \
                mock.patch(
                    'config.main.config_file_yang_validation',
                    return_value=True):

            runner = CliRunner()

            result = runner.invoke(config.config.commands["reload"], ["-y", "-f", "all_config_db.json"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join(
                [li.rstrip() for li in result.output.split('\n')]
            ) == reload_config_masic_onefile_gen_sysinfo_output.format(config.SYSTEM_RELOAD_LOCK)

    def test_config_reload_onefile_bad_format_masic(self):
        def read_json_file_side_effect(filename):
            return {
                "localhost": {},
                "asic0": {}
            }

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)):

            runner = CliRunner()

            result = runner.invoke(config.config.commands["reload"], ["-y", "-f", "all_config_db.json"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code != 0
            assert "Input file all_config_db.json must contain all asics config" in result.output

    def test_config_reload_multiple_files(self):
        dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")
        dummy_cfg_file_asic0 = os.path.join(os.sep, "tmp", "config0.json")
        dummy_cfg_file_asic1 = os.path.join(os.sep, "tmp", "config1.json")
        device_metadata = {
            "DEVICE_METADATA": {
                "localhost": {
                    "platform": "some_platform",
                    "mac": "02:42:f0:7f:01:05"
                }
            }
        }
        self._create_dummy_config(dummy_cfg_file, device_metadata)
        self._create_dummy_config(dummy_cfg_file_asic0, device_metadata)
        self._create_dummy_config(dummy_cfg_file_asic1, device_metadata)

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch(
                    'config.main.config_file_yang_validation',
                    return_value=True):
            runner = CliRunner()
            # 3 config files: 1 for host and 2 for asic
            cfg_files = f"{dummy_cfg_file},{dummy_cfg_file_asic0},{dummy_cfg_file_asic1}"

            result = runner.invoke(
                config.config.commands["reload"],
                [cfg_files, '-y', '-f'])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == \
                RELOAD_MASIC_CONFIG_DB_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)

    def test_config_reload_multiple_files_with_spaces(self):
        dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")
        dummy_cfg_file_asic0 = os.path.join(os.sep, "tmp", "config0.json")
        dummy_cfg_file_asic1 = os.path.join(os.sep, "tmp", "config1.json")
        device_metadata = {
            "DEVICE_METADATA": {
                "localhost": {
                    "platform": "some_platform",
                    "mac": "02:42:f0:7f:01:05"
                }
            }
        }
        self._create_dummy_config(dummy_cfg_file, device_metadata)
        self._create_dummy_config(dummy_cfg_file_asic0, device_metadata)
        self._create_dummy_config(dummy_cfg_file_asic1, device_metadata)

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch(
                    'config.main.config_file_yang_validation',
                    return_value=True):
            runner = CliRunner()
            # add unnecessary spaces and comma at the end
            cfg_files = f"   {dummy_cfg_file} ,{dummy_cfg_file_asic0},  {dummy_cfg_file_asic1},"

            result = runner.invoke(
                config.config.commands["reload"],
                [cfg_files, '-y', '-f'])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == \
                RELOAD_MASIC_CONFIG_DB_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)

    def test_config_reload_default_files_validate_all_namespaces(self):
        dummy_cfg_file = os.path.join(
            os.sep, "tmp", "reload_validate_config_db.json"
        )
        dummy_cfg_file_asic0 = os.path.join(
            os.sep, "tmp", "reload_validate_config_db0.json"
        )
        dummy_cfg_file_asic1 = os.path.join(
            os.sep, "tmp", "reload_validate_config_db1.json"
        )
        device_metadata = {
            "DEVICE_METADATA": {
                "localhost": {
                    "platform": "some_platform",
                    "mac": "02:42:f0:7f:01:05"
                }
            }
        }
        self._create_dummy_config(dummy_cfg_file, device_metadata)
        self._create_dummy_config(dummy_cfg_file_asic0, device_metadata)
        self._create_dummy_config(dummy_cfg_file_asic1, device_metadata)

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(
                            side_effect=mock_run_command_side_effect
                        )), \
                mock.patch.object(
                    config, 'DEFAULT_CONFIG_DB_FILE', dummy_cfg_file
                ), \
                mock.patch(
                    'config.main.config_file_yang_validation',
                    return_value=True
                ) as mock_validate_config:
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"], ['-y', '-n']
            )

            assert result.exit_code == 0
            assert mock_validate_config.call_count == 3
            assert mock_validate_config.call_args_list == [
                mock.call(dummy_cfg_file),
                mock.call(dummy_cfg_file_asic0),
                mock.call(dummy_cfg_file_asic1),
            ]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestLoadMinigraph(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    def test_help_marks_command_as_deprecated(self, get_cmd_module):
        (config, _) = get_cmd_module
        result = CliRunner().invoke(
            config.config.commands["load_minigraph"],
            ["--help"]
        )

        assert result.exit_code == 0
        assert "Deprecated compatibility path" in result.output

    def read_json_file_side_effect(self, filename):
        return {
            'DEVICE_METADATA': {
                'localhost': {
                    'platform': 'x86_64-mlnx_msn2700-r0',
                    'mac': '00:02:03:04:05:07'
                }
            }
        }

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    @mock.patch('config.main.subprocess.check_call')
    def test_load_minigraph(self, mock_check_call, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([line.rstrip() for line in result.output.split('\n')]) == \
                (load_minigraph_command_output.format(config.SYSTEM_RELOAD_LOCK))
            # Verify "systemctl reset-failed" is called for services under sonic.target
            mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'swss'])
            mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'pmon'])
            assert mock_run_command.call_count == 23

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs',
                mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_lock_failure(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, _) = get_cmd_module

            fd = open(config.SYSTEM_RELOAD_LOCK, 'r')
            assert flock.acquire_flock(fd, 0)

            try:
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
                print(result.exit_code)
                print(result.output)
                traceback.print_tb(result.exc_info[2])
                assert result.exit_code != 0
                assert result.output == \
                    (load_minigraph_lock_failure_output.format(config.SYSTEM_RELOAD_LOCK))
                assert mock_run_command.call_count == 0
            finally:
                flock.release_flock(fd)

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs',
                mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_bypass_lock(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, _) = get_cmd_module

            fd = open(config.SYSTEM_RELOAD_LOCK, 'r')
            assert flock.acquire_flock(fd, 0)

            try:
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-y", "-b"])
                print(result.exit_code)
                print(result.output)
                traceback.print_tb(result.exc_info[2])
                assert result.exit_code == 0
                assert result.output == \
                    load_minigraph_command_bypass_lock_output.format(config.SYSTEM_RELOAD_LOCK)
                mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'swss'])
                mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'pmon'])
                assert mock_run_command.call_count == 17
            finally:
                flock.release_flock(fd)

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=(load_minigraph_platform_path, None)))
    def test_load_minigraph_platform_plugin(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([line.rstrip() for line in result.output.split('\n')]) == \
                (load_minigraph_platform_plugin_command_output.format(config.SYSTEM_RELOAD_LOCK))
            # Verify "systemctl reset-failed" is called for services under sonic.target
            mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'swss'])
            mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'pmon'])
            assert mock_run_command.call_count == 17

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=(load_minigraph_platform_false_path, None)))
    def test_load_minigraph_platform_plugin_fail(self, get_cmd_module, setup_single_broadcom_asic):
        print(load_minigraph_platform_false_path)
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code != 0
            assert "Platform plugin failed" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_port_config_bad_format(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            # Not in an array
            port_config = {"PORT": {"Ethernet0": {"admin_status": "up"}}}
            self.check_port_config(None, config, port_config, "Failed to load port_config.json, Error: Bad format: port_config is not an array")

            # No PORT table
            port_config = [{}]
            self.check_port_config(None, config, port_config, "Failed to load port_config.json, Error: Bad format: PORT table not exists")

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_port_config_inconsistent_port(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            db = Db()
            db.cfgdb.set_entry("PORT", "Ethernet1", {"admin_status": "up"})
            port_config = [{"PORT": {"Eth1": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "Failed to load port_config.json, Error: Port Eth1 is not defined in current device")

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_port_config(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            db = Db()

            # From up to down
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "up"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "down"}}}]
            self.check_port_config(db, config, port_config, "config interface shutdown Ethernet0")

            # From down to up
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "down"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "config interface startup Ethernet0")

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def check_port_config(self, db, config, port_config, expected_output):
        def read_json_file_side_effect(filename):
            return port_config
        with mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):
            def is_file_side_effect(filename):
                return True if 'port_config' in filename else False
            with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
                print(result.exit_code)
                print(result.output)
                assert result.exit_code == 0
                assert expected_output in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_non_exist_golden_config_path(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command, \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "--golden_config_path", "non_exist.json", "-y"])
            assert result.exit_code != 0
            assert "Cannot find 'non_exist.json'" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_specified_golden_config_path(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False

        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command, \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)), \
                mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=self.read_json_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "--golden_config_path",  "golden_config.json", "-y"])
            assert result.exit_code == 0
            assert "config override-config-table golden_config.json" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_default_golden_config_path(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False

        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command, \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)), \
                mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=self.read_json_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "-y"])
            assert result.exit_code == 0
            assert "config override-config-table /etc/sonic/golden_config_db.json" in result.output

    @mock.patch(
            'sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs',
            mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_invalid_golden_config(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)), \
                mock.patch('config.main.read_json_file', mock.MagicMock(return_value=[])):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "-y"])
            assert result.exit_code != 0
            assert "Invalid golden config file:" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs',
                mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_hard_dependency_check(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False

        def read_json_file_side_effect(filename):
            return {
                "AAA": {
                    "authentication": {
                        "login": "tacacs+"
                    }
                },
                "TACPLUS": {
                    "global": {
                    }
                }
            }

        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)), \
                mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):
            (config, _) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "-y"])
            assert result.exit_code != 0
            assert "Authentication with 'tacacs+' is not allowed when passkey not exists." in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs',
                mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_no_yang_failure(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False

        def read_json_file_side_effect(filename):
            return {
                "NEW_FEATURE": {
                    "global": {
                        "state": "enable"
                    }
                }
            }

        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)), \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)), \
                mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):
            (config, _) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "-y"])
            assert result.exit_code != 0
            assert "Config tables are missing yang models: dict_keys(['NEW_FEATURE'])" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_traffic_shift_away(self, get_cmd_module):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-ty"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "TSA" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_traffic_shift_away_with_golden_config(self, get_cmd_module):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            def is_file_side_effect(filename):
                return True if 'golden_config' in filename else False

            with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)), \
                    mock.patch('config.main.read_json_file', mock.MagicMock(
                        side_effect=self.read_json_file_side_effect)):
                (config, show) = get_cmd_module
                db = Db()
                golden_config = {}
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-ty", "--override_config"])
                print(result.exit_code)
                print(result.output)
                traceback.print_tb(result.exc_info[2])
                assert result.exit_code == 0
                assert "TSA" in result.output
                assert "[WARNING] Golden configuration may override Traffic-shift-away state" in result.output

    def test_config_file_yang_validation(self):
        # Test with empty config
        with mock.patch('config.main.read_json_file', return_value="") as mock_read_json_file:
            with mock.patch('config.main.sonic_yang.SonicYang.loadYangModel') as mock_load_yang_model:
                assert not config_file_yang_validation('dummy_file.json')
                mock_read_json_file.assert_called_once_with('dummy_file.json')
                mock_load_yang_model.assert_not_called()

        # Test with non-dict config
        with mock.patch('config.main.read_json_file', return_value=[]) as mock_read_json_file:
            with mock.patch('config.main.sonic_yang.SonicYang.loadYangModel') as mock_load_yang_model:
                assert not config_file_yang_validation('dummy_file.json')
                mock_read_json_file.assert_called_once_with('dummy_file.json')
                mock_load_yang_model.assert_not_called()

        # Test with valid config
        valid_config = {
                'DEVICE_METADATA': {
                    'localhost': {
                        'platform': 'x86_64-mlnx_msn2700-r0',
                        'mac': '00:02:03:04:05:07'
                    }
                }
            }

        with mock.patch('config.main.read_json_file', return_value=valid_config) as mock_read_json_file, \
                mock.patch('config.main.multi_asic.is_multi_asic', return_value=False), \
                mock.patch('config.main.sonic_yang.SonicYang.loadYangModel') as mock_load_yang_model, \
                mock.patch('config.main.sonic_yang.SonicYang.loadData') as mock_load_data, \
                mock.patch('config.main.sonic_yang.SonicYang.validate_data_tree') as mock_validate_data_tree:
            assert config_file_yang_validation('dummy_file.json')
            mock_read_json_file.assert_called_once_with('dummy_file.json')
            mock_load_yang_model.assert_called_once()
            mock_load_data.assert_called_once_with(configdbJson=valid_config)
            mock_validate_data_tree.assert_called_once()

    def test_config_file_yang_validation_uses_fresh_instance_per_multiasic_scope(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        scope_configs = TestLoadGoldenConfig._valid_multiasic_golden_config()
        yang_instances = [mock.Mock(tablesWithOutYang={}) for _ in range(3)]

        with mock.patch.object(
                config,
                "read_json_file",
                return_value=scope_configs), \
                mock.patch.object(
                config.multi_asic,
                "is_multi_asic",
                return_value=True), \
                mock.patch.object(
                    config.multi_asic,
                    "get_namespace_list",
                    return_value=["asic0", "asic1"]), \
                mock.patch.object(
                    config.sonic_yang,
                    "SonicYang",
                    side_effect=yang_instances) as mock_sonic_yang:
            assert config.config_file_yang_validation("dummy_file.json")

        assert mock_sonic_yang.call_count == 3
        for yang_instance, scope_name in zip(
                yang_instances, ("localhost", "asic0", "asic1")):
            yang_instance.loadYangModel.assert_called_once_with()
            yang_instance.loadData.assert_called_once_with(
                configdbJson=scope_configs[scope_name]
            )
            yang_instance.validate_data_tree.assert_called_once_with()

    def test_config_file_yang_validation_keeps_flat_namespace_files_supported(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        flat_config = TestLoadGoldenConfig._valid_golden_config()
        yang_instance = mock.Mock(tablesWithOutYang={})

        with mock.patch.object(
                config,
                "read_json_file",
                return_value=flat_config), \
                mock.patch.object(
                    config.multi_asic,
                    "is_multi_asic",
                    return_value=True), \
                mock.patch.object(
                    config.sonic_yang,
                    "SonicYang",
                    return_value=yang_instance):
            assert config.config_file_yang_validation("asic0-config.json")

        yang_instance.loadData.assert_called_once_with(configdbJson=flat_config)
        yang_instance.validate_data_tree.assert_called_once_with()

    def test_golden_native_scope_validation_rejects_malformed_multiasic_wrapper(
            self, get_cmd_module):
        (config, _) = get_cmd_module
        malformed_wrapper = {
            "asic0": TestLoadGoldenConfig._valid_golden_config()
        }

        with mock.patch.object(
                config.multi_asic,
                "get_namespace_list",
                return_value=["asic0"]), \
                pytest.raises(ValueError, match="missing scopes: localhost"):
            config._validate_multiasic_scope_configs(malformed_wrapper)

    @pytest.mark.parametrize(
        "namespaces",
        [
            ["asic1", "asic2"],
            ["asic0", "asic2"]
        ]
    )
    def test_golden_native_scope_validation_rejects_non_contiguous_namespaces(
            self, get_cmd_module, namespaces):
        (config, _) = get_cmd_module

        with mock.patch.object(
                config.multi_asic,
                "get_namespace_list",
                return_value=namespaces), \
                pytest.raises(ValueError, match="zero-based and contiguous"):
            config._validate_multiasic_scope_configs(
                self._valid_multiasic_golden_config()
            )

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

class TestReloadConfig(object):
    dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    def add_sysinfo_to_cfg_file(self):
        with open(self.dummy_cfg_file, 'w') as f:
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "platform": "some_platform",
                        "mac": "02:42:f0:7f:01:05"
                    }
                }
            }
            f.write(json.dumps(device_metadata))

    def test_reload_config_invalid_input(self, get_cmd_module, setup_single_broadcom_asic):
        open(self.dummy_cfg_file, 'w').close()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code != 0

    def test_reload_config_no_sysinfo(self, get_cmd_module, setup_single_broadcom_asic):
        with open(self.dummy_cfg_file, 'w') as f:
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "hwsku": "some_hwsku"
                    }
                }
            }
            f.write(json.dumps(device_metadata))

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0

    def test_reload_config(self, get_cmd_module, setup_single_broadcom_asic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) \
                == RELOAD_CONFIG_DB_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)

    def test_reload_config_lock_failure(self, get_cmd_module, setup_single_broadcom_asic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ):
            (config, show) = get_cmd_module
            runner = CliRunner()

            fd = open(config.SYSTEM_RELOAD_LOCK, 'r')
            assert flock.acquire_flock(fd, 0)

            try:
                result = runner.invoke(
                    config.config.commands["reload"],
                    [self.dummy_cfg_file, '-y', '-f'])

                print(result.exit_code)
                print(result.output)
                traceback.print_tb(result.exc_info[2])
                assert result.exit_code != 0
                assert "\n".join([line.rstrip() for line in result.output.split('\n')]) \
                    == RELOAD_CONFIG_DB_LOCK_FAILURE_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)
            finally:
                flock.release_flock(fd)

    def test_reload_config_bypass_lock(self, get_cmd_module, setup_single_broadcom_asic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ):
            (config, show) = get_cmd_module
            runner = CliRunner()

            fd = open(config.SYSTEM_RELOAD_LOCK, 'r')
            assert flock.acquire_flock(fd, 0)

            try:
                result = runner.invoke(
                    config.config.commands["reload"],
                    [self.dummy_cfg_file, '-y', '-f', '-b'])

                print(result.exit_code)
                print(result.output)
                traceback.print_tb(result.exc_info[2])
                assert result.exit_code == 0
                assert "\n".join([line.rstrip() for line in result.output.split('\n')]) \
                    == RELOAD_CONFIG_DB_BYPASS_LOCK_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)
            finally:
                flock.release_flock(fd)

    def test_config_reload_disabled_service(self, get_cmd_module, setup_single_broadcom_asic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
               "utilities_common.cli.run_command",
               mock.MagicMock(side_effect=mock_run_command_side_effect_disabled_timer)
        ) as mock_run_command:
            (config, show) = get_cmd_module

            runner = CliRunner()
            result = runner.invoke(config.config.commands["reload"], [self.dummy_cfg_file, "-y"])

            print(result.exit_code)
            print(result.output)
            print(reload_config_with_disabled_service_output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0

            assert "\n".join([line.rstrip() for line in result.output.split('\n')]) == \
                reload_config_with_disabled_service_output.format(config.SYSTEM_RELOAD_LOCK)

    def test_reload_yang_config(self, get_cmd_module,
                                        setup_single_broadcom_asic):
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(config.config.commands["reload"],
                                    [self.dummy_cfg_file, '-y', '-f', '-t', 'config_yang'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) \
                == RELOAD_YANG_CFG_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)

    def test_reload_config_fails_yang_validation(self, get_cmd_module, setup_single_broadcom_asic):
        with open(self.dummy_cfg_file, 'w') as f:
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "invalid_hwsku": "some_hwsku"
                    }
                }
            }
            f.write(json.dumps(device_metadata))

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ):
            (config, _) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code != 0
            assert "fails YANG validation! Error" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.remove(cls.dummy_cfg_file)
        print("TEARDOWN")


class TestConfigCbf(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        import config.main
        importlib.reload(config.main)

    def test_cbf_reload_single(
            self, get_cmd_module, setup_cbf_mock_apis,
            setup_single_broadcom_asic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "cbf_config_output.json")
        print("Saving output in {}".format(output_file))
        try:
            os.remove(output_file)
        except OSError:
            pass
        result = runner.invoke(
           config.config.commands["cbf"],
             ["reload", "--dry_run", output_file]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "cbf_config_input", "config_cbf.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigCbfMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_cbf_reload_masic(
            self, get_cmd_module, setup_cbf_mock_apis,
            setup_multi_broadcom_masic
    ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "cbf_config_output.json")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        print(num_asic)
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        result = runner.invoke(
            config.config.commands["cbf"],
            ["reload", "--dry_run", output_file]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "cbf_config_input", str(asic), "config_cbf.json"
            )
            file = "{}{}".format(output_file, asic)
            assert filecmp.cmp(file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestConfigQos(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        import config.main
        importlib.reload(config.main)

    def _keys(args, kwargs):
        if not TestConfigQos._keys_counter:
            return []
        TestConfigQos._keys_counter-=1
        return ["BUFFER_POOL_TABLE:egress_lossy_pool"]

    def test_qos_wait_until_clear_empty(self):
        from config.main import _wait_until_clear

        with mock.patch('swsscommon.swsscommon.SonicV2Connector.keys',  side_effect=TestConfigQos._keys):
            TestConfigQos._keys_counter = 1
            empty = _wait_until_clear(["BUFFER_POOL_TABLE:*"], 0.5,2)
        assert empty

    def test_qos_wait_until_clear_not_empty(self):
        from config.main import _wait_until_clear

        with mock.patch('swsscommon.swsscommon.SonicV2Connector.keys', side_effect=TestConfigQos._keys):
            TestConfigQos._keys_counter = 10
            empty = _wait_until_clear(["BUFFER_POOL_TABLE:*"], 0.5,2)
        assert not empty

    @patch('click.echo')
    @patch('swsscommon.swsscommon.SonicV2Connector.keys')
    def test_qos_wait_until_clear_no_timeout(self, mock_keys, mock_echo):
        from config.main import _wait_until_clear
        assert _wait_until_clear(["BUFFER_POOL_TABLE:*"], 0.5, 0)
        mock_keys.assert_not_called()
        mock_echo.assert_not_called()

    @mock.patch('config.main._wait_until_clear')
    def test_qos_clear_no_wait(self, _wait_until_clear):
        from config.main import _clear_qos
        _clear_qos(True, False)
        _wait_until_clear.assert_called_with(['BUFFER_*_TABLE:*', 'BUFFER_*_SET'], interval=0.5, timeout=0, verbose=False)

    @mock.patch('config.main._wait_until_clear')
    def test_clear_qos_without_delay(self, mock_wait_until_clear):
        from config.main import _clear_qos

        status = _clear_qos(False, False)
        mock_wait_until_clear.assert_not_called()
        assert status is True

    @mock.patch('config.main._wait_until_clear')
    def test_clear_qos_with_delay_returns_true(self, mock_wait_until_clear):
        from config.main import _clear_qos
        mock_wait_until_clear.return_value = True

        status = _clear_qos(True, False)
        mock_wait_until_clear.assert_called_once()
        assert status is True

    @mock.patch('config.main._wait_until_clear')
    def test_clear_qos_with_delay_returns_false(self, mock_wait_until_clear):
        from config.main import _clear_qos
        mock_wait_until_clear.return_value = False

        status = _clear_qos(True, False)
        mock_wait_until_clear.assert_called_once()
        assert status is False

    @patch('config.main._wait_until_clear')
    def test_qos_reload_not_empty_should_exit(self, mock_wait_until_clear):
        mock_wait_until_clear.return_value = False
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}".format(output_file))
        result = runner.invoke(
            config.config.commands["qos"], ["reload"]
        )
        print(result.exit_code)
        print(result.output)
        # Expect sys.exit(1) when _wait_until_clear returns False
        assert result.exit_code == 1

    def test_qos_reload_single(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_single_broadcom_asic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}".format(output_file))
        try:
            os.remove(output_file)
        except OSError:
            pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--dry_run", output_file, "--json-data", json_data]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "qos_config_input", "config_qos.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    def test_qos_update_single(
            self, get_cmd_module, setup_qos_mock_apis
        ):
        (config, show) = get_cmd_module
        json_data = '{"DEVICE_METADATA": {"localhost": {}}, "PORT": {"Ethernet0": {}}}'
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_update.json")
        cmd_vector = ["reload", "--ports", "Ethernet0", "--json-data", json_data, "--dry_run", output_file]
        result = runner.invoke(config.config.commands["qos"], cmd_vector)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "qos_config_input", "update_qos.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigQosMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_qos_reload_masic(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_multi_broadcom_masic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--dry_run", output_file, "--json-data", json_data]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "qos_config_input", str(asic), "config_qos.json"
            )
            file = "{}{}".format(output_file, asic)
            assert filecmp.cmp(file, expected_result, shallow=False)

    def test_qos_update_masic(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_multi_broadcom_masic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()

        output_file = os.path.join(os.sep, "tmp", "qos_update_output")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}, "PORT": {"Ethernet0": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--ports", "Ethernet0,Ethernet4", "--json-data", json_data, "--dry_run", output_file]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "qos_config_input", str(asic), "update_qos.json"
            )

            assert filecmp.cmp(output_file + "asic{}".format(asic), expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()

class TestGenericUpdateCommands(unittest.TestCase):
    def setUp(self):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        self.runner = CliRunner()
        self.any_patch_as_json = [{"op": "remove", "path": "/PORT"}]
        self.any_patch = jsonpatch.JsonPatch(self.any_patch_as_json)
        self.any_patch_as_text = json.dumps(self.any_patch_as_json)
        self.any_path = '/usr/admin/patch.json-patch'
        self.any_target_config = {"PORT": {}}
        self.any_target_config_as_text = json.dumps(self.any_target_config)
        self.any_checkpoint_name = "any_checkpoint_name"
        self.any_checkpoints_list = ["checkpoint1", "checkpoint2", "checkpoint3"]
        self.any_checkpoints_list_with_time = [
            {"name": "checkpoint1", "time": datetime.datetime.now(timezone.utc).isoformat()},
            {"name": "checkpoint2", "time": datetime.datetime.now(timezone.utc).isoformat()},
            {"name": "checkpoint3", "time": datetime.datetime.now(timezone.utc).isoformat()}
        ]
        self.any_checkpoints_list_as_text = json.dumps(self.any_checkpoints_list, indent=4)
        self.any_checkpoints_list_with_time_as_text = json.dumps(self.any_checkpoints_list_with_time, indent=4)

    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument 'PATCH_FILE_PATH'"

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        expected_call_with_default_values = mock.call(
            mock.ANY,
            ConfigFormat.CONFIGDB,
            False,
            False,
            False,
            (),
            trace_io=None,
        )
        mock_generic_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"], [self.any_path], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call_with_default_values])

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(mock.ANY, ConfigFormat.SONICYANG, True, True, True, expected_ignore_path_tuple, trace_io=None)
        mock_generic_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path,
                                             "--format", ConfigFormat.SONICYANG.name,
                                             "--dry-run",
                                             "--ignore-non-yang-tables",
                                             "--ignore-path", "/ANY_TABLE",
                                             "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                             "--ignore-path", "",
                                             "--verbose"],
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call_with_non_default_values])

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.apply_patch.side_effect = Exception(any_error_message)
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path],
                                            catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertIn(any_error_message, result.output)

    def test_apply_patch__optional_parameters_passed_correctly(self):
        self.validate_apply_patch_optional_parameter(
            ["--format", ConfigFormat.SONICYANG.name],
            mock.call(mock.ANY, ConfigFormat.SONICYANG, False, False, False, (), trace_io=None))
        self.validate_apply_patch_optional_parameter(
            ["--verbose"],
            mock.call(mock.ANY, ConfigFormat.CONFIGDB, True, False, False, (), trace_io=None))
        self.validate_apply_patch_optional_parameter(
            ["--dry-run"],
            mock.call(mock.ANY, ConfigFormat.CONFIGDB, False, True, False, (), trace_io=None))
        self.validate_apply_patch_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(mock.ANY, ConfigFormat.CONFIGDB, False, False, True, (), trace_io=None))
        self.validate_apply_patch_optional_parameter(
            ["--ignore-path", "/ANY_TABLE"],
            mock.call(mock.ANY, ConfigFormat.CONFIGDB, False, False, False, ("/ANY_TABLE",), trace_io=None))

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__path_trace_option__trace_file_opened_and_passed(self):
        # Arrange
        import tempfile
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        mock_generic_updater = mock.Mock()
        mock_file_handle = mock.MagicMock()

        # Create a temporary file for the trace output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as trace_file:
            trace_file_path = trace_file.name

        try:
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_generic_updater):
                with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)) as mock_open_func:
                    # Configure mock to return different handles for patch file and trace file
                    def open_side_effect(filename, mode='r'):
                        if filename == trace_file_path:
                            return mock_file_handle
                        else:
                            return mock.mock_open(read_data=self.any_patch_as_text).return_value
                    mock_open_func.side_effect = open_side_effect

                    # Act
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.any_path, "--path-trace", trace_file_path],
                                                catch_exceptions=False)

            # Assert
            self.assertEqual(expected_exit_code, result.exit_code)
            self.assertIn(expected_output, result.output)
            mock_generic_updater.apply_patch.assert_called_once()
            # Verify that trace_io parameter is not None when --path-trace is used
            call_args = mock_generic_updater.apply_patch.call_args
            self.assertIsNotNone(call_args[1]['trace_io'])
            # Verify the file handle was closed
            mock_file_handle.close.assert_called_once()
        finally:
            # Clean up the temporary file
            import os
            if os.path.exists(trace_file_path):
                os.unlink(trace_file_path)

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def validate_apply_patch_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path] + param_args,
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call])

    def test_filter_duplicate_patch_operations_basic(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        # Patch tries to add duplicate port to ACL_TABLE leaf-list
        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet1"},
            {"op": "add", "path": "/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet2"},
            {"op": "add", "path": "/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet3"}
        ]
        config = {
            "ACL_TABLE": {
                "MY_ACL_TABLE": {
                    "ports": ["Ethernet1", "Ethernet2"]
                }
            }
        }
        filtered_patch_ops = filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        # Only the non-duplicate add ops should remain
        self.assertEqual(len(filtered_patch_ops), 1, "Only Ethernet3 add op should remain")
        self.assertEqual(filtered_patch_ops[0]['value'], "Ethernet3", "Only Ethernet3 add op should remain")

    def test_filter_duplicate_patch_operations_no_duplicates(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        # Patch does not contain any duplicate ops
        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet3"},
            {"op": "remove", "path": "/ACL_TABLE/MY_ACL_TABLE/ports/0"},
            {"op": "replace", "path": "/ACL_TABLE/MY_ACL_TABLE/description", "value": "New description"}
        ]
        config = {
            "ACL_TABLE": {
                "MY_ACL_TABLE": {
                    "ports": ["Ethernet1", "Ethernet2"],
                    "description": "Old description"
                }
            }
        }
        filtered_patch_ops = filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        # All ops should remain as there are no duplicates
        self.assertEqual(len(filtered_patch_ops), len(patch_ops), "All patch should remain as no duplicates")
        self.assertEqual(filtered_patch_ops, patch_ops, "Filtered ops should match original ops")

    def test_filter_duplicate_patch_operations_non_list_field(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        # Patch tries to add duplicate entries to a non-list field
        patch_ops = [
            {"op": "add", "path": "/PORT/Ethernet0/description", "value": "Desc1"},
            {"op": "add", "path": "/PORT/Ethernet0/description", "value": "Desc2"}
        ]
        config = {
            "PORT": {
                "Ethernet0": {
                    "description": "Existing description"
                }
            }
        }
        filtered_patch_ops = filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        # Both ops should remain as description is not a list field
        self.assertEqual(len(filtered_patch_ops), len(patch_ops), "Both add ops should remain for non-list field")
        self.assertEqual(filtered_patch_ops, patch_ops, "Filtered ops should match original ops")

    def test_filter_duplicate_patch_operations_empty_config(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        patch_ops = [
            {"op": "add", "path": "/PORT/Ethernet0/allowed_vlans/-", "value": "100"},
            {"op": "add", "path": "/PORT/Ethernet0/allowed_vlans/-", "value": "200"}
        ]
        config = {
            "PORT": {
                "Ethernet0": {
                    "allowed_vlans": []
                }
            }
        }
        filtered_patch_ops = filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        # All ops should remain as config is empty and has no existing entries
        self.assertEqual(len(filtered_patch_ops), len(patch_ops), "All add ops should remain for empty list")
        self.assertEqual(filtered_patch_ops, patch_ops, "Filtered ops should match original ops")

    def test_append_emptytables_if_required_basic_config(self):
        from generic_config_updater.main import append_emptytables_if_required

        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE2/ports", "value": ["Ethernet1", "Ethernet2"]}
        ]
        config = {
            "ACL_TABLE": {
                "ports": ["Ethernet3"]
            }
        }
        updated_patch_ops = append_emptytables_if_required(patch_ops, json.dumps(config))
        assert len(updated_patch_ops) == 2, "Patch should have 2 operations after appending empty tables"
        assert updated_patch_ops[0]['path'] == "/ACL_TABLE2", "First op should create ACL_TABLE2"
        assert updated_patch_ops[0]['op'] == "add", "First op should be an add operation"
        assert updated_patch_ops[1] == patch_ops[0], "Second op should be the original add operation"

    def test_append_emptytables_if_required_no_action_needed(self):
        from generic_config_updater.main import append_emptytables_if_required
        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE/ports", "value": ["Ethernet1", "Ethernet2"]}
        ]
        config = {
            "ACL_TABLE": {
                "ports": ["Ethernet3"]
            }
        }
        updated_patch_ops = append_emptytables_if_required(patch_ops, json.dumps(config))
        assert len(updated_patch_ops) == 1, "Patch should remain unchanged with 1 operation"
        assert updated_patch_ops[0] == patch_ops[0], "Patch operation should remain unchanged"

    def test_append_emptytables_if_required_multiple_tables(self):
        from generic_config_updater.main import append_emptytables_if_required

        patch_ops = [
            {"op": "add", "path": "/TABLE1/field", "value": "value1"},
            {"op": "add", "path": "/TABLE2/field", "value": "value2"}
        ]
        config = {}
        updated_patch_ops = append_emptytables_if_required(patch_ops, json.dumps(config))
        assert len(updated_patch_ops) == 4, "Patch should have 4 operations after appending empty tables"
        assert updated_patch_ops[0]['path'] == "/TABLE1", "First op should create TABLE1"
        assert updated_patch_ops[1] == patch_ops[0], "Second op should be the original TABLE1 add operation"
        assert updated_patch_ops[2]['path'] == "/TABLE2", "Third op should create TABLE2"
        assert updated_patch_ops[3] == patch_ops[1], "Fourth op should be the original TABLE2 add operation"

    # ------------------------------------------------------------------
    # print_dry_run_message
    # ------------------------------------------------------------------

    def test_print_dry_run_message_dry_run_true_prints_banner(self):
        """print_dry_run_message with dry_run=True should echo a banner."""
        from config.main import print_dry_run_message
        result = self.runner.invoke(
            click.command()(lambda: print_dry_run_message(True))
        )
        self.assertIn("DRY RUN", result.output)

    def test_print_dry_run_message_dry_run_false_no_output(self):
        """print_dry_run_message with dry_run=False should produce no output."""
        from config.main import print_dry_run_message
        result = self.runner.invoke(
            click.command()(lambda: print_dry_run_message(False))
        )
        self.assertEqual(result.output.strip(), "")

    def test_replace__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument 'TARGET_FILE_PATH'"

        # Act
        result = self.runner.invoke(config.config.commands["replace"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_replace__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["replace"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_replace__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        expected_call_with_default_values = mock.call(
            mock.ANY,
            ConfigFormat.CONFIGDB,
            False,
            False,
            False,
            (),
            trace_io=None
        )
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"], [self.any_path], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call_with_default_values])

    def test_replace__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(
                self.any_target_config,
                ConfigFormat.SONICYANG,
                True,
                True,
                True,
                expected_ignore_path_tuple,
                trace_io=None
            )
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path,
                                             "--format", ConfigFormat.SONICYANG.name,
                                             "--dry-run",
                                             "--ignore-non-yang-tables",
                                             "--ignore-path", "/ANY_TABLE",
                                             "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                             "--ignore-path", "",
                                             "--verbose"],
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call_with_non_default_values])

    def test_replace__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.replace.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path],
                                            catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_replace__optional_parameters_passed_correctly(self):
        self.validate_replace_optional_parameter(
            ["--format", ConfigFormat.SONICYANG.name],
            mock.call(self.any_target_config, ConfigFormat.SONICYANG, False, False, False, (), trace_io=None))
        self.validate_replace_optional_parameter(
            ["--verbose"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, True, False, False, (), trace_io=None))
        self.validate_replace_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, True, False, (), trace_io=None))
        self.validate_replace_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, True, (), trace_io=None))
        self.validate_replace_optional_parameter(
            ["--ignore-path", "/ANY_TABLE"],
            mock.call(
                self.any_target_config,
                ConfigFormat.CONFIGDB,
                False,
                False,
                False,
                ("/ANY_TABLE",),
                trace_io=None,
            )
        )

    def test_replace__path_trace_option__trace_file_opened_and_passed(self):
        # Arrange
        import tempfile
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        mock_generic_updater = mock.Mock()
        mock_file_handle = mock.MagicMock()

        # Create a temporary file for the trace output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as trace_file:
            trace_file_path = trace_file.name

        try:
            with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
                with (
                    mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)) as
                    mock_open_func
                ):
                    # Configure mock to return different handles for config file and trace file
                    def open_side_effect(filename, mode='r'):
                        if filename == trace_file_path:
                            return mock_file_handle
                        else:
                            return mock.mock_open(read_data=self.any_target_config_as_text).return_value
                    mock_open_func.side_effect = open_side_effect

                    # Act
                    result = self.runner.invoke(config.config.commands["replace"],
                                                [self.any_path, "--path-trace", trace_file_path],
                                                catch_exceptions=False)

            # Assert
            self.assertEqual(expected_exit_code, result.exit_code)
            self.assertIn(expected_output, result.output)
            mock_generic_updater.replace.assert_called_once()
            # Verify that trace_io parameter is not None when --path-trace is used
            call_args = mock_generic_updater.replace.call_args
            self.assertIsNotNone(call_args[1]['trace_io'])
            # Verify the file handle was closed
            mock_file_handle.close.assert_called_once()
        finally:
            # Clean up the temporary file
            import os
            if os.path.exists(trace_file_path):
                os.unlink(trace_file_path)

    def validate_replace_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path] + param_args,
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call])

    def test_rollback__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument 'CHECKPOINT_NAME'"

        # Act
        result = self.runner.invoke(config.config.commands["rollback"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_rollback__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["rollback"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_rollback__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(
                config.config.commands["rollback"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call_with_default_values])

    def test_rollback__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(self.any_checkpoint_name, True, True, True, expected_ignore_path_tuple)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name,
                                            "--dry-run",
                                            "--ignore-non-yang-tables",
                                            "--ignore-path", "/ANY_TABLE",
                                            "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                            "--ignore-path", "",
                                            "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call_with_non_default_values])

    def test_rollback__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.rollback.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_rollback__optional_parameters_passed_correctly(self):
        self.validate_rollback_optional_parameter(
            ["--verbose"],
            mock.call(self.any_checkpoint_name, True, False, False, ()))
        self.validate_rollback_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_checkpoint_name, False, True, False, ()))
        self.validate_rollback_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_checkpoint_name, False, False, True, ()))
        self.validate_rollback_optional_parameter(
            ["--ignore-path", "/ACL_TABLE"],
            mock.call(self.any_checkpoint_name, False, False, False, ("/ACL_TABLE",)))

    def validate_rollback_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name] + param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call])

    def test_checkpoint__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument 'CHECKPOINT_NAME'"

        # Act
        result = self.runner.invoke(config.config.commands["checkpoint"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_checkpoint__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["checkpoint"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_checkpoint__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint created successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call_with_default_values])

    def test_checkpoint__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint created successfully"
        expected_call_with_non_default_values = mock.call(self.any_checkpoint_name, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"],
                                        [self.any_checkpoint_name,
                                            "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call_with_non_default_values])

    def test_checkpoint__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.checkpoint.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"],
                                        [self.any_checkpoint_name],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_checkpoint__optional_parameters_passed_correctly(self):
        self.validate_checkpoint_optional_parameter(
            ["--verbose"],
            mock.call(self.any_checkpoint_name, True))

    def validate_checkpoint_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint created successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"],
                                        [self.any_checkpoint_name] + param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call])

    def test_delete_checkpoint__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument 'CHECKPOINT_NAME'"

        # Act
        result = self.runner.invoke(config.config.commands["delete-checkpoint"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_delete_checkpoint__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["delete-checkpoint"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_delete_checkpoint__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint deleted successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.delete_checkpoint.assert_called_once()
        mock_generic_updater.delete_checkpoint.assert_has_calls([expected_call_with_default_values])

    def test_delete_checkpoint__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint deleted successfully"
        expected_call_with_non_default_values = mock.call(self.any_checkpoint_name, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [self.any_checkpoint_name,
                                            "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.delete_checkpoint.assert_called_once()
        mock_generic_updater.delete_checkpoint.assert_has_calls([expected_call_with_non_default_values])

    def test_delete_checkpoint__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.delete_checkpoint.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [self.any_checkpoint_name],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_delete_checkpoint__optional_parameters_passed_correctly(self):
        self.validate_delete_checkpoint_optional_parameter(
            ["--verbose"],
            mock.call(self.any_checkpoint_name, True))

    def validate_delete_checkpoint_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint deleted successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [self.any_checkpoint_name] + param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.delete_checkpoint.assert_called_once()
        mock_generic_updater.delete_checkpoint.assert_has_calls([expected_call])

    def test_list_checkpoints__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["list-checkpoints"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)

    def test_list_checkpoints__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = self.any_checkpoints_list_with_time_as_text
        expected_call_with_non_default_values = mock.call(True, True)
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.return_value = self.any_checkpoints_list_with_time
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        ["--time", "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.list_checkpoints.assert_called_once()
        mock_generic_updater.list_checkpoints.assert_has_calls([expected_call_with_non_default_values])

    def test_list_checkpoints__time_param_true__time_included_in_output(self):
        # Arrange
        expected_exit_code = 0
        expected_output = self.any_checkpoints_list_with_time_as_text
        expected_call_with_time_param = mock.call(True, False)
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.return_value = self.any_checkpoints_list_with_time
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        ["--time"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.list_checkpoints.assert_called_once()
        mock_generic_updater.list_checkpoints.assert_has_calls([expected_call_with_time_param])

    def test_list_checkpoints__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_list_checkpoints__optional_parameters_passed_correctly(self):
        self.validate_list_checkpoints_optional_parameter(
            ["--verbose"],
            mock.call(False, True))

    def validate_list_checkpoints_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = self.any_checkpoints_list_as_text
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.return_value = self.any_checkpoints_list
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertIn(expected_output, result.output)
        mock_generic_updater.list_checkpoints.assert_called_once()
        mock_generic_updater.list_checkpoints.assert_has_calls([expected_call])


class TestConfigLoadMgmtConfig(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

        import config.main
        importlib.reload(config.main)

    def test_config_load_mgmt_config_ipv4_only(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_only_output, 7)

    def test_config_load_mgmt_config_ipv6_only(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv6_only_output, 7)

    def test_config_load_mgmt_config_ipv4_ipv6(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                },
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_ipv6_output, 10)

    def check_output(self, get_cmd_module, parse_device_desc_xml_result, expected_output, expected_command_call_count):
        def parse_device_desc_xml_side_effect(filename):
            print("parse dummy device_desc.xml")
            return parse_device_desc_xml_result
        def change_hostname_side_effect(hostname):
            print("change hostname to {}".format(hostname))
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            with mock.patch('os.path.isfile', mock.MagicMock(return_value=True)):
                with mock.patch('config.main.parse_device_desc_xml', mock.MagicMock(side_effect=parse_device_desc_xml_side_effect)):
                    with mock.patch('config.main._change_hostname', mock.MagicMock(side_effect=change_hostname_side_effect)):
                        (config, show) = get_cmd_module
                        runner = CliRunner()
                        with runner.isolated_filesystem():
                            with open('device_desc.xml', 'w') as f:
                                f.write('dummy')
                                result = runner.invoke(config.config.commands["load_mgmt_config"], ["-y", "device_desc.xml"])
                                print(result.exit_code)
                                print(result.output)
                                traceback.print_tb(result.exc_info[2])
                                assert result.exit_code == 0
                                assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == expected_output
                                assert mock_run_command.call_count == expected_command_call_count


    def test_config_load_mgmt_config_ipv4_ipv6_cat_failed(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                },
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output_cat_failed(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_ipv6_cat_failed_output, 8)

    def check_output_cat_failed(self, get_cmd_module, parse_device_desc_xml_result, expected_output, expected_command_call_count):
        def parse_device_desc_xml_side_effect(filename):
            print("parse dummy device_desc.xml")
            return parse_device_desc_xml_result
        def change_hostname_side_effect(hostname):
            print("change hostname to {}".format(hostname))
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_cat_failed_side_effect)) as mock_run_command:
            with mock.patch('os.path.isfile', mock.MagicMock(return_value=True)):
                with mock.patch('config.main.parse_device_desc_xml', mock.MagicMock(side_effect=parse_device_desc_xml_side_effect)):
                    with mock.patch('config.main._change_hostname', mock.MagicMock(side_effect=change_hostname_side_effect)):
                        (config, show) = get_cmd_module
                        runner = CliRunner()
                        with runner.isolated_filesystem():
                            with open('device_desc.xml', 'w') as f:
                                f.write('dummy')
                                result = runner.invoke(config.config.commands["load_mgmt_config"], ["-y", "device_desc.xml"])
                                print(result.exit_code)
                                print(result.output)
                                traceback.print_tb(result.exc_info[2])
                                assert result.exit_code == 1
                                assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == expected_output
                                assert mock_run_command.call_count == expected_command_call_count

    def test_config_load_mgmt_config_ipv4_ipv6_kill_failed(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                },
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output_kill_failed(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_ipv6_kill_failed_output, 9)

    def check_output_kill_failed(self, get_cmd_module, parse_device_desc_xml_result, expected_output, expected_command_call_count):
        def parse_device_desc_xml_side_effect(filename):
            print("parse dummy device_desc.xml")
            return parse_device_desc_xml_result
        def change_hostname_side_effect(hostname):
            print("change hostname to {}".format(hostname))
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_kill_failed_side_effect)) as mock_run_command:
            with mock.patch('os.path.isfile', mock.MagicMock(return_value=True)):
                with mock.patch('config.main.parse_device_desc_xml', mock.MagicMock(side_effect=parse_device_desc_xml_side_effect)):
                    with mock.patch('config.main._change_hostname', mock.MagicMock(side_effect=change_hostname_side_effect)):
                        (config, show) = get_cmd_module
                        runner = CliRunner()
                        with runner.isolated_filesystem():
                            with open('device_desc.xml', 'w') as f:
                                f.write('dummy')
                                result = runner.invoke(config.config.commands["load_mgmt_config"], ["-y", "device_desc.xml"])
                                print(result.exit_code)
                                print(result.output)
                                traceback.print_tb(result.exc_info[2])
                                assert result.exit_code == 1
                                assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == expected_output
                                assert mock_run_command.call_count == expected_command_call_count

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()

class TestConfigRate(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

        import config.main
        importlib.reload(config.main)

    def test_config_rate(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            runner = CliRunner()
            result = runner.invoke(config.config.commands["rate"], ["smoothing-interval", "500"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert result.output == ""

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigHostname(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    @mock.patch('config.main.ValidatedConfigDBConnector')
    def test_hostname_add(self, db_conn_patch, get_cmd_module):
        db_conn_patch().mod_entry = mock.Mock()
        (config, show) = get_cmd_module

        runner = CliRunner()
        result = runner.invoke(config.config.commands["hostname"],
                               ["new_hostname"])

        # Verify success
        assert result.exit_code == 0

        # Check was called
        args_list = db_conn_patch().mod_entry.call_args_list
        assert len(args_list) > 0

        args, _ = args_list[0]
        assert len(args) > 0

        # Check new hostname was part of args
        assert {'hostname': 'new_hostname'} in args

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_invalid_hostname_add_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["hostname"],
                               ["invalid_hostname"], obj=obj)
        assert result.exit_code != 0
        assert "Failed to write new hostname" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


class TestConfigWarmRestart(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_warm_restart_neighsyncd_timer_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["neighsyncd_timer"], ["2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    def test_warm_restart_neighsyncd_timer(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["neighsyncd_timer"], ["0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "neighsyncd warm restart timer must be in range 1-9999" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_warm_restart_bgp_timer_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["bgp_timer"], ["2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    def test_warm_restart_bgp_timer(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["bgp_timer"], ["0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "bgp warm restart timer must be in range 1-3600" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_warm_restart_teamsyncd_timer_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["teamsyncd_timer"], ["2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    def test_warm_restart_teamsyncd_timer(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["teamsyncd_timer"], ["0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "teamsyncd warm restart timer must be in range 1-3600" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_warm_restart_bgp_eoiu_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db': {'': db.cfgdb}, 'asic_namespaces': ['']}

        result = runner.invoke(config.config.commands["warm_restart"].commands["bgp_eoiu"], ["true"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


class TestConfigCableLength(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    @patch("config.main.is_dynamic_buffer_enabled", mock.Mock(return_value=True))
    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value=False))
    def test_add_cablelength_with_nonexistent_name_valid_length(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["cable-length"], ["Ethernet0","40m"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Port Ethernet0 doesn't exist" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value="Port Info"))
    @patch("config.main.is_dynamic_buffer_enabled", mock.Mock(return_value=True))
    @patch("config.main.ConfigDBConnector.get_keys", mock.Mock(return_value=["sample_key"]))
    def test_add_cablelength_invalid_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["cable-length"], ["Ethernet0","40"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value="Port Info"))
    @patch("config.main.is_dynamic_buffer_enabled", mock.Mock(return_value=True))
    def test_add_cablelength_with_invalid_name_invalid_length(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["cable-length"], ["Ethernet0","40x"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid cable length" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


class TestConfigLoopback(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_add_loopback_with_invalid_name_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["add"], ["Loopbax1"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Loopbax1 is invalid, name should have prefix 'Loopback' and suffix '<0-999>'" in result.output

    def test_add_loopback_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["add"], ["Loopbax1"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Loopbax1 is invalid, name should have prefix 'Loopback' and suffix '<0-999>'" in result.output

        result = runner.invoke(config.config.commands["loopback"].commands["add"], ["Loopback0000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Loopback0000 is invalid, name should have prefix 'Loopback' and suffix '<0-999>' and " \
            "should not exceed 15 characters" in result.output

    def test_del_nonexistent_loopback_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["del"], ["Loopback12"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Loopback12 does not exist" in result.output

    def test_del_nonexistent_loopback_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["del"], ["Loopbax1"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Loopbax1 is invalid, name should have prefix 'Loopback' and suffix '<0-999>'" in result.output

    def test_del_loopback_with_dhcpv4_relay_entry(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["add"], ["Loopback1"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("LOOPBACK_INTERFACE", "Loopback1") == {}

        # Enable has_sonic_dhcpv4_relay flag
        db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {"has_sonic_dhcpv4_relay": "True"})

        db.cfgdb.set_entry("DHCPV4_RELAY", "Vlan100", {
            "dhcpv4_servers": ["192.0.2.100"],
            "source_interface": "Loopback1"
        })

        result = runner.invoke(config.config.commands["loopback"].commands["del"], ["Loopback1"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Interface 'Loopback1' is in use by Vlan100" in result.output

        db.cfgdb.set_entry("DHCPV4_RELAY", "Vlan200", None)

    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(return_value=True))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_add_loopback_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["add"], ["Loopback12"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_add_loopback_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["loopback"].commands["add"], ["Loopback12"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


class TestConfigNtp(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    @patch('utilities_common.cli.run_command')
    def test_add_ntp_server(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "10.10.10.4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_add_ntp_server_version_3(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "--version", "3", "10.10.10.4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_add_ntp_server_with_iburst(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "--iburst", "10.10.10.4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_add_ntp_server_with_server_association(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "--association-type", "server", "10.10.10.4"],
                               obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_add_ntp_server_with_pool_association(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "--association-type", "pool", "pool.ntp.org"],
                               obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry",
           mock.Mock(side_effect=ValueError))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_add_ntp_server_failed_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "10.10.10.x"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_add_ntp_server_invalid_ip(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "10.10.10.x"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid IP address" in result.output

    @patch('utilities_common.cli.run_command')
    def test_add_ntp_server_twice(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        db.cfgdb.set_entry("NTP_SERVER", "10.10.10.4", {})

        result = runner.invoke(config.config.commands["ntp"], ["add", "10.10.10.4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "is already configured" in result.output
        mock_run_command.assert_not_called()

    @patch('utilities_common.cli.run_command')
    def test_del_ntp_server(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        db.cfgdb.set_entry("NTP_SERVER", "10.10.10.4", {})

        result = runner.invoke(config.config.commands["ntp"], ["del", "10.10.10.4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_del_pool_ntp_server(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        db.cfgdb.set_entry("NTP_SERVER", "pool.ntp.org", {})

        result = runner.invoke(config.config.commands["ntp"], ["del", "pool.ntp.org"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['systemctl', 'restart', 'chrony'], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_del_ntp_server_not_configured(self, mock_run_command):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["del", "10.10.10.4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "not configured" in result.output
        mock_run_command.assert_not_called()

    @patch("config.main.ConfigDBConnector.get_table", mock.Mock(return_value="10.10.10.10"))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_del_ntp_server_invalid_ip_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["del", "10.10.10.10"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


class TestConfigPfcwd(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_start(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['pfcwd'].commands['start'], ['-a', 'forward', '-r', 150, 'Ethernet0', '200', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['pfcwd', 'start', '--action', 'forward', 'Ethernet0', '200', '--restoration-time', '150'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_stop(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['pfcwd'].commands['stop'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['pfcwd', 'stop'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_interval(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['pfcwd'].commands['interval'], ['300', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['pfcwd', 'interval', '300'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_counter_poll(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['pfcwd'].commands['counter_poll'], ['enable', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['pfcwd', 'counter_poll', 'enable'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_big_red_switch(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['pfcwd'].commands['big_red_switch'], ['enable', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['pfcwd', 'big_red_switch', 'enable'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_start_default(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['pfcwd'].commands['start_default'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['pfcwd', 'start_default'], display_cmd=True)

    def teardown_method(self):
        print("TEARDOWN")


class TestConfigAclUpdate(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_full(self, mock_run_command):
        file_name = '/etc/sonic/full_snmp.json'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['acl'].commands['update'].commands['full'], [file_name])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['acl-loader', 'update', 'full', file_name])

    @patch('utilities_common.cli.run_command')
    def test_incremental(self, mock_run_command):
        file_name = '/etc/sonic/full_snmp.json'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['acl'].commands['update'].commands['incremental'], [file_name])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['acl-loader', 'update', 'incremental', file_name])

    def teardown_method(self):
        print("TEARDOWN")


class TestConfigDropcounters(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_install(self, mock_run_command):
        counter_name = 'DEBUG_2'
        counter_type = 'PORT_INGRESS_DROPS'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        alias = 'BAD_DROPS'
        group = 'BAD'
        desc = 'more port ingress drops'

        # Parameters for configurable drop monitor
        dct = '10'  # Drop count threshold
        ict = '2'  # Incident count threshold
        window = '300'

        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['install'],
                               [counter_name, counter_type, reasons, '-d', desc, '-g', group,
                               '-a', alias, '-w', window, '-dct', dct, '-ict', ict])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'install',
                                                  '-n', str(counter_name),
                                                  '-t', str(counter_type),
                                                  '-r', str(reasons), '-a', str(alias),
                                                  '-g', str(group), '-d', str(desc),
                                                  '-w', str(window), '-dct', str(dct),
                                                  '-ict', str(ict)],
                                                 display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_delete(self, mock_run_command):
        counter_name = 'DEBUG_2'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['delete'], [counter_name, '-v'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'uninstall', '-n', str(counter_name)], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_add_reasons(self, mock_run_command):
        counter_name = 'DEBUG_2'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['add-reasons'],
                               [counter_name, reasons, '-v'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'add', '-n', str(counter_name),
                                                  '-r', str(reasons)], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_remove_reasons(self, mock_run_command):
        counter_name = 'DEBUG_2'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['remove-reasons'], [counter_name, reasons, '-v'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'remove', '-n', str(counter_name), '-r', str(reasons)], display_cmd=True)

    def teardown_method(self):
        print("TEARDOWN")


class TestConfigDropcountersMasic(object):
    def setup_method(self):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    @patch('utilities_common.cli.run_command')
    def test_install_multi_asic(self, mock_run_command):
        counter_name = 'DEBUG_2'
        counter_type = 'PORT_INGRESS_DROPS'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        alias = 'BAD_DROPS'
        group = 'BAD'
        desc = 'more port ingress drops'
        namespace = 'asic0'

        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['install'],
                               [counter_name, counter_type, reasons, '-d', desc, '-g', group, '-a',
                               alias, '-n', namespace])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'install', '-n', str(counter_name),
                                                  '-t', str(counter_type), '-r', str(reasons), '-a', str(alias),
                                                  '-g', str(group), '-d', str(desc),
                                                  '-ns', str(namespace)], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_enable_monitor_multi_asic(self, mock_run_command):
        counter_name = 'DEBUG_2'
        window = '300'
        dct = '10'  # Drop count threshold
        ict = '5'  # Incident count threshold
        namespace = 'asic0'

        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['enable-monitor'],
                               ['-c', counter_name, '-w', window, '-dct', dct, '-ict', ict,
                               '-n', namespace])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'enable_drop_monitor', '-n', str(counter_name),
                                                  '-w', str(window), '-dct', str(dct), '-ict', str(ict),
                                                  '-ns', str(namespace)], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_disable_monitor_multi_asic(self, mock_run_command):
        counter_name = 'DEBUG_2'
        namespace = 'asic0'

        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['disable-monitor'],
                               ['-c', counter_name, '-n', namespace])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'disable_drop_monitor', '-n', str(counter_name),
                                                  '-ns', str(namespace)], display_cmd=False)

    @patch('utilities_common.cli.run_command')
    def test_delete_multi_asic(self, mock_run_command):
        counter_name = 'DEBUG_2'
        namespace = 'asic0'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['delete'],
                               [counter_name, '-v', '-n', namespace])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'uninstall', '-n',
                                                 str(counter_name), '-ns', namespace], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_add_reasons_multi_asic(self, mock_run_command):
        counter_name = 'DEBUG_2'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        namespace = 'asic0'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['add-reasons'],
                               [counter_name, reasons, '-v', '-n', namespace])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'add', '-n',
                                                 str(counter_name), '-r', str(reasons), '-ns', namespace],
                                                 display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_remove_reasons_multi_asic(self, mock_run_command):
        counter_name = 'DEBUG_2'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        namespace = 'asic0'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['remove-reasons'],
                               [counter_name, reasons, '-v', '-n', namespace])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'remove', '-n', str(counter_name),
                                                 '-r', str(reasons), '-ns', namespace], display_cmd=True)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()

class TestConfigWatermarkTelemetry(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_interval(self, mock_run_command):
        interval = '18'
        runner = CliRunner()
        result = runner.invoke(config.config.commands['watermark'].commands['telemetry'].commands['interval'], [interval])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['watermarkcfg', '--config-interval', str(interval)])

    def teardown_method(self):
        print("TEARDOWN")


class TestConfigZtp(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_run(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['ztp'].commands['run'], ['-y'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['ztp', 'run', '-y'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_disable(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['ztp'].commands['disable'], ['-y'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['ztp', 'disable', '-y'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_enable(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(config.config.commands['ztp'].commands['enable'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['ztp', 'enable'], display_cmd=True)

    def teardown_method(self):
        print("TEARDOWN")


@patch('utilities_common.cli.run_command')
@patch('os.uname', MagicMock(return_value=['Linux', 'current-hostname', '5.11.0-34-generic', '#36~20.04.1-Ubuntu SMP Thu Aug 5 14:22:16 UTC 2021', 'x86_64']))
def test_change_hostname(mock_run_command):
    new_hostname = 'new_hostname'
    with patch('builtins.open', mock_open()) as mock_file:
        config._change_hostname(new_hostname)

    assert mock_file.call_args_list == [
        call('/etc/hostname', 'w'),
        call('/etc/hosts', 'a')
    ]
    assert mock_file().write.call_args_list == [
        call('new_hostname\n'),
        call('127.0.0.1 new_hostname\n')
    ]
    assert mock_run_command.call_args_list == [
        call(['hostname', '-F', '/etc/hostname'], display_cmd=True),
        call(['sed', '-i', r"/\scurrent-hostname$/d", '/etc/hosts'], display_cmd=True)
    ]


class TestConfigInterface(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_speed(self, mock_run_command):
        interface_name = 'Ethernet0'
        interface_speed = '100'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['speed'], [interface_name, interface_speed, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-s', str(interface_speed), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['speed'], [interface_name, interface_speed, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-s', str(interface_speed), '-n', 'ns', '-vv'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_link_training(self, mock_run_command):
        interface_name = 'Ethernet0'
        mode = 'on'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['link-training'], [interface_name, mode, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-lt', str(mode), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['link-training'], [interface_name, mode, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-lt', str(mode), '-n', 'ns', '-vv'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_advertised_speeds(self, mock_run_command):
        interface_name = 'Ethernet0'
        speed_list = '50,100'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['advertised-speeds'], [interface_name, speed_list, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-S', str(speed_list), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['advertised-speeds'], [interface_name, speed_list, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-S', str(speed_list), '-n', 'ns', '-vv'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_advertised_types(self, mock_run_command):
        interface_name = 'Ethernet0'
        interface_type = 'CR,CR4'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['advertised-types'], [interface_name, interface_type, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-T', str(interface_type), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['advertised-types'], [interface_name, interface_type, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-T', str(interface_type), '-n', 'ns', '-vv'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_mtu(self, mock_run_command):
        interface_name = 'Ethernet0'
        interface_mtu = '1000'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['mtu'], [interface_name, interface_mtu, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-m', str(interface_mtu), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['mtu'], [interface_name, interface_mtu, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-m', str(interface_mtu), '-n', 'ns', '-vv'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_tpid(self, mock_run_command):
        interface_name = 'Ethernet0'
        interface_tpid = '0x9200'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['tpid'], [interface_name, interface_tpid, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-tp', str(interface_tpid), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['tpid'], [interface_name, interface_tpid, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-tp', str(interface_tpid), '-n', 'ns', '-vv'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_fec(self, mock_run_command):
        interface_name = 'Ethernet0'
        interface_fec = 'rs'
        db = Db()
        runner = CliRunner()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands['interface'].commands['fec'], [interface_name, interface_fec, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-f', str(interface_fec), '-vv'], display_cmd=True)

        obj = {'config_db': db.cfgdb, 'namespace': 'ns'}
        result = runner.invoke(config.config.commands['interface'].commands['fec'], [interface_name, interface_fec, '--verbose'], obj=obj)
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['portconfig', '-p', str(interface_name), '-f', str(interface_fec), '-n', 'ns', '-vv'], display_cmd=True)

    def test_startup_shutdown_loopback(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(config.config.commands['interface'].commands['ip'].commands['add'],
                               ['Loopback0', '10.0.1.0/32'], obj=obj)
        assert result.exit_code == 0
        assert 'Loopback0' in db.cfgdb.get_table('LOOPBACK_INTERFACE')

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'], ['Loopback0'], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table('LOOPBACK_INTERFACE')['Loopback0']['admin_status'] == 'down'

        result = runner.invoke(config.config.commands['interface'].commands['startup'], ['Loopback0'], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table('LOOPBACK_INTERFACE')['Loopback0']['admin_status'] == 'up'

    def test_expand_single_intf_filter_is_range(self):
        from utilities_common.intf_filter import expand_single_intf_filter
        intfs, is_range = expand_single_intf_filter('Ethernet0-4')
        assert intfs == ['Ethernet0', 'Ethernet1', 'Ethernet2', 'Ethernet3', 'Ethernet4']
        assert is_range is True
        intfs, is_range = expand_single_intf_filter('PortChannel1-4')
        assert intfs == ['PortChannel1', 'PortChannel2', 'PortChannel3', 'PortChannel4']
        assert is_range is True
        intfs, is_range = expand_single_intf_filter('Ethernet-BP0-3')
        assert intfs == ['Ethernet-BP0', 'Ethernet-BP1', 'Ethernet-BP2', 'Ethernet-BP3']
        assert is_range is True
        intfs, is_range = expand_single_intf_filter('Ethernet0')
        assert intfs == ['Ethernet0']
        assert is_range is False
        intfs, is_range = expand_single_intf_filter('Ethernet-BP0')
        assert intfs == ['Ethernet-BP0']
        assert is_range is False
        intfs, is_range = expand_single_intf_filter('Ethernet-Rec0')
        assert intfs == []
        assert is_range is False
        intfs, is_range = expand_single_intf_filter('Ethernet-IB0')
        assert intfs == []
        assert is_range is False

    def test_startup_shutdown_sparse_port_range(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb, 'namespace': ''}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               ['Ethernet0-4'], obj=obj)
        assert result.exit_code == 0

        port_table = db.cfgdb.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'down'
        assert port_table['Ethernet4']['admin_status'] == 'down'
        assert 'Ethernet1' not in port_table

        result = runner.invoke(config.config.commands['interface'].commands['startup'],
                               ['Ethernet0-4'], obj=obj)
        assert result.exit_code == 0

        port_table = db.cfgdb.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'up'
        assert port_table['Ethernet4']['admin_status'] == 'up'

    def test_startup_shutdown_mixed_interface_filter(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        interface_filter = 'Ethernet8,Ethernet16-20,Ethernet32'
        expected_interfaces = ['Ethernet8', 'Ethernet16', 'Ethernet20', 'Ethernet32']

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               [interface_filter], obj=obj)
        assert result.exit_code == 0

        port_table = db.cfgdb.get_table('PORT')
        for interface_name in expected_interfaces:
            assert port_table[interface_name]['admin_status'] == 'down'
        assert 'Ethernet17' not in port_table
        assert 'Ethernet18' not in port_table
        assert 'Ethernet19' not in port_table

        result = runner.invoke(config.config.commands['interface'].commands['startup'],
                               [interface_filter], obj=obj)
        assert result.exit_code == 0

        port_table = db.cfgdb.get_table('PORT')
        for interface_name in expected_interfaces:
            assert port_table[interface_name]['admin_status'] == 'up'

    def test_single_asic_explicit_invalid_interface_fails(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb, 'namespace': ''}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               ['Ethernet0,Ethernet999'], obj=obj)
        assert result.exit_code != 0
        assert "Ethernet999" in result.output

    def test_sparse_port_range_with_no_valid_interfaces_fails(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb, 'namespace': ''}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               ['Ethernet1-3'], obj=obj)
        assert result.exit_code != 0
        assert "Ethernet1, Ethernet2, Ethernet3" in result.output

    @pytest.mark.parametrize("interface_name", [
        "Ethernet320-Ethernet376",  # range bounds not numeric
        "Ethernet0-",               # missing end of range
        "Ethernet0-foo",            # non-numeric end of range
        "Eth0-3",                   # range with unsupported prefix
        "Ethernet8-4",              # start of range greater than the end
    ])
    def test_startup_malformed_range(self, interface_name):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(config.config.commands['interface'].commands['startup'],
                               [interface_name], obj=obj)
        assert result.exit_code != 0
        assert "Invalid interface range" in result.output

    @pytest.mark.parametrize("interface_name", [
        "Ethernet320-Ethernet376",  # range bounds not numeric
        "Ethernet0-",               # missing end of range
        "Ethernet0-foo",            # non-numeric end of range
        "Eth0-3",                   # range with unsupported prefix
        "Ethernet8-4",              # start of range greater than the end
    ])
    def test_shutdown_malformed_range(self, interface_name):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               [interface_name], obj=obj)
        assert result.exit_code != 0
        assert "Invalid interface range" in result.output

    def teardown_method(self):
        print("TEARDOWN")


class TestConfigInterfaceMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        cls.original_topology = os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_startup_shutdown_single_port(self, get_cmd_module, setup_multi_broadcom_masic):
        (config, _) = get_cmd_module
        config_db = config.ConfigDBConnector(use_unix_socket_path=True, namespace='asic0')
        config_db.connect()
        runner = CliRunner()
        obj = {'config_db': config_db, 'namespace': 'asic0'}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               ['Ethernet0'], obj=obj)
        assert result.exit_code == 0

        port_table = config_db.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'down'

        result = runner.invoke(config.config.commands['interface'].commands['startup'],
                               ['Ethernet0'], obj=obj)
        assert result.exit_code == 0

        port_table = config_db.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'up'

    def test_startup_shutdown_comma_separated_ports(self, get_cmd_module, setup_multi_broadcom_masic):
        (config, _) = get_cmd_module
        config_db = config.ConfigDBConnector(use_unix_socket_path=True, namespace='asic0')
        config_db.connect()
        runner = CliRunner()
        obj = {'config_db': config_db, 'namespace': 'asic0'}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               ['Ethernet0,Ethernet4'], obj=obj)
        assert result.exit_code == 0

        port_table = config_db.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'down'
        assert port_table['Ethernet4']['admin_status'] == 'down'

        result = runner.invoke(config.config.commands['interface'].commands['startup'],
                               ['Ethernet0,Ethernet4'], obj=obj)
        assert result.exit_code == 0

        port_table = config_db.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'up'
        assert port_table['Ethernet4']['admin_status'] == 'up'

    def test_startup_shutdown_sparse_port_range(self, get_cmd_module, setup_multi_broadcom_masic):
        (config, _) = get_cmd_module
        config_db = config.ConfigDBConnector(use_unix_socket_path=True, namespace='asic0')
        config_db.connect()
        runner = CliRunner()
        obj = {'config_db': config_db, 'namespace': 'asic0'}

        result = runner.invoke(config.config.commands['interface'].commands['shutdown'],
                               ['Ethernet0-4'], obj=obj)
        assert result.exit_code == 0

        port_table = config_db.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'down'
        assert port_table['Ethernet4']['admin_status'] == 'down'
        assert 'Ethernet1' not in port_table

        result = runner.invoke(config.config.commands['interface'].commands['startup'],
                               ['Ethernet0-4'], obj=obj)
        assert result.exit_code == 0

        port_table = config_db.get_table('PORT')
        assert port_table['Ethernet0']['admin_status'] == 'up'
        assert port_table['Ethernet4']['admin_status'] == 'up'

    @pytest.mark.parametrize("command_name,initial_status", [
        ("shutdown", "up"),
        ("startup", "down"),
    ])
    def test_startup_shutdown_mixed_filter_with_interface_in_other_namespace_fails(
            self, get_cmd_module, setup_multi_broadcom_masic, command_name, initial_status
    ):
        (config, _) = get_cmd_module
        config_db = config.ConfigDBConnector(use_unix_socket_path=True, namespace='asic0')
        config_db.connect()
        runner = CliRunner()
        obj = {'config_db': config_db, 'namespace': 'asic0'}

        # The explicit Ethernet0/Ethernet4 members and the generated
        # Ethernet16/Ethernet20 members belong to asic0. Ethernet64 is also
        # generated by the range filter but belongs to asic1
        local_interfaces = ['Ethernet0', 'Ethernet4', 'Ethernet16', 'Ethernet20']
        for interface_name in local_interfaces:
            config_db.mod_entry('PORT', interface_name, {'admin_status': initial_status})
        try:
            result = runner.invoke(config.config.commands['interface'].commands[command_name],
                                   ['Ethernet0,Ethernet16-64,Ethernet4'], obj=obj)
            assert result.exit_code != 0
            assert ("Interface(s) not in provided namespace 'asic0'. "
                    "Interface(s) Ethernet64 exist(s) on namespace 'asic1'") in result.output

            port_table = config_db.get_table('PORT')
            for interface_name in local_interfaces:
                assert port_table[interface_name]['admin_status'] == initial_status
        finally:
            for interface_name in local_interfaces:
                config_db.mod_entry('PORT', interface_name, {'admin_status': 'up'})

    @pytest.mark.parametrize("command_name,initial_status", [
        ("shutdown", "up"),
        ("startup", "down"),
    ])
    def test_startup_shutdown_explicit_invalid_interface_fails(
            self, get_cmd_module, setup_multi_broadcom_masic, command_name, initial_status
    ):
        (config, _) = get_cmd_module
        config_db = config.ConfigDBConnector(use_unix_socket_path=True, namespace='asic0')
        config_db.connect()
        runner = CliRunner()
        obj = {'config_db': config_db, 'namespace': 'asic0'}

        config_db.mod_entry('PORT', 'Ethernet0', {'admin_status': initial_status})
        try:
            result = runner.invoke(config.config.commands['interface'].commands[command_name],
                                   ['Ethernet0,Ethernet272'], obj=obj)
            assert result.exit_code != 0
            assert ("Provided interface(s) : 'Ethernet272' are invalid "
                    "in namespace 'asic0'") in result.output

            port_table = config_db.get_table('PORT')
            assert port_table['Ethernet0']['admin_status'] == initial_status
        finally:
            config_db.mod_entry('PORT', 'Ethernet0', {'admin_status': 'up'})

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        if cls.original_topology is None:
            os.environ.pop("UTILITIES_UNIT_TESTING_TOPOLOGY", None)
        else:
            os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = cls.original_topology
        print("TEARDOWN")


class TestConfigClock(object):
    timezone_test_val = ['Europe/Kyiv', 'Asia/Israel', 'UTC']

    @classmethod
    def setup_class(cls):
        print('SETUP')
        import config.main
        importlib.reload(config.main)

    @patch('utilities_common.cli.run_command')
    def test_get_tzs(self, mock_run_command):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        runner.invoke(config.config.commands['clock'].commands['timezone'], ['Atlantis'], obj=obj)
        mock_run_command.assert_called_with(['timedatectl', 'list-timezones'], display_cmd=False, ignore_error=False, return_cmd=True)

    @patch('config.main.get_tzs', mock.Mock(return_value=timezone_test_val))
    def test_timezone_good(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['clock'].commands['timezone'],
            ['UTC'], obj=obj)

        assert result.exit_code == 0

    @patch('config.main.get_tzs', mock.Mock(return_value=timezone_test_val))
    def test_timezone_bad(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['clock'].commands['timezone'],
            ['Atlantis'], obj=obj)

        assert result.exit_code != 0
        assert 'Timezone Atlantis does not conform format' in result.output

    @patch('utilities_common.cli.run_command',
           mock.MagicMock(side_effect=mock_run_command_side_effect))
    def test_date_good(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['clock'].commands['date'],
            ['2020-10-10', '10:20:30'], obj=obj)

        assert result.exit_code == 0

    @patch('utilities_common.cli.run_command',
           mock.MagicMock(side_effect=mock_run_command_side_effect))
    def test_date_bad(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['clock'].commands['date'],
            ['20-10-10', '60:70:80'], obj=obj)

        assert result.exit_code != 0
        assert 'Date 20-10-10 does not conform format' in result.output
        assert 'Time 60:70:80 does not conform format' in result.output

    @classmethod
    def teardown_class(cls):
        print('TEARDOWN')


class TestApplyPatchMultiAsic(unittest.TestCase):
    def setUp(self):
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

        self.runner = CliRunner()
        self.patch_file_path = 'path/to/patch.json'
        self.replace_file_path = 'path/to/replace.json'
        self.patch_content = [
            {
                "op": "add",
                "path": "/localhost/ACL_TABLE/NEW_ACL_TABLE",
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet1", "Ethernet2"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            {
                "op": "add",
                "path": "/asic0/ACL_TABLE/NEW_ACL_TABLE",
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet3", "Ethernet4"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            {
                "op": "replace",
                "path": "/asic1/PORT/Ethernet1/mtu",
                "value": "9200"
            }
        ]

        test_config = copy.deepcopy(config_temp)
        data = test_config.pop("scope")
        self.all_config = {}
        self.all_config["localhost"] = data
        self.all_config["asic0"] = data
        self.all_config["asic0"]["bgpraw"] = ""
        self.all_config["asic1"] = data
        self.all_config["asic1"]["bgpraw"] = ""

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_multiasic(self):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"], [self.patch_file_path], catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertEqual(result.exit_code, 0, "Command should succeed")
                self.assertIn("Patch applied successfully.", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_dryrun_multiasic(self):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                 "--format", ConfigFormat.SONICYANG.name,
                                                 "--dry-run",
                                                 "--ignore-non-yang-tables",
                                                 "--ignore-path", "/ANY_TABLE",
                                                 "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                 "--ignore-path", "",
                                                 "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    @patch('generic_config_updater.main.concurrent.futures.wait', autospec=True)
    def test_apply_patch_dryrun_parallel_multiasic(self, MockThreadPoolWait):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                 "--format", ConfigFormat.SONICYANG.name,
                                                 "--dry-run",
                                                 "--parallel",
                                                 "--ignore-non-yang-tables",
                                                 "--ignore-path", "/ANY_TABLE",
                                                 "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                 "--ignore-path", "",
                                                 "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Assertions to check if ThreadPoolExecutor was used correctly
                    MockThreadPoolWait.assert_called_once()

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    @patch('generic_config_updater.main.concurrent.futures.wait', autospec=True)
    def test_apply_patch_check_running_in_parallel_multiasic(self, MockThreadPoolWait):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                 "--format", ConfigFormat.SONICYANG.name,
                                                 "--parallel",
                                                 "--ignore-non-yang-tables",
                                                 "--ignore-path", "/ANY_TABLE",
                                                 "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                 "--ignore-path", "",
                                                 "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Assertions to check if ThreadPoolExecutor was used correctly
                    MockThreadPoolWait.assert_called_once()

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    @patch('generic_config_updater.main._apply_patch_wrapper')
    def test_apply_patch_check_apply_call_parallel_multiasic(self, mock_apply_patch):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                 "--format", ConfigFormat.SONICYANG.name,
                                                 "--parallel",
                                                 "--ignore-non-yang-tables",
                                                 "--ignore-path", "/ANY_TABLE",
                                                 "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                 "--ignore-path", "",
                                                 "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Assertions to check if ThreadPoolExecutor was used correctly
                    self.assertEqual(mock_apply_patch.call_count,
                                     multi_asic.get_num_asics() + 1,
                                     "apply_patch_wrapper function should be called number of ASICs plus host times")

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    @patch('generic_config_updater.main.concurrent.futures.wait', autospec=True)
    def test_apply_patch_check_running_in_not_parallel_multiasic(self, MockThreadPoolWait):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                 "--format", ConfigFormat.SONICYANG.name,
                                                 "--ignore-non-yang-tables",
                                                 "--ignore-path", "/ANY_TABLE",
                                                 "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                 "--ignore-path", "",
                                                 "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Assertions to check if ThreadPoolExecutor was used correctly
                    MockThreadPoolWait.assert_not_called()

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_parallel_with_error_multiasic(self):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                "--format", ConfigFormat.SONICYANG.name,
                                                 "--dry-run",
                                                 "--parallel",
                                                 "--ignore-non-yang-tables",
                                                 "--ignore-path", "/ANY_TABLE",
                                                 "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                 "--ignore-path", "",
                                                 "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    def test_filter_duplicate_patch_operations_basic_multiasic(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        import jsonpatch
        # Multi-ASIC config: each ASIC has its own ACL_TABLE
        config = {
            "localhost": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet1", "Ethernet2"]
                    }
                }
            },
            "asic0": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet3", "Ethernet4"]
                    }
                }
            },
            "asic1": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet5", "Ethernet6"]
                    }
                }
            }
        }
        # Patch tries to add duplicate ports to each ASIC's ACL_TABLE leaf-list
        patch_ops = [
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet1"},
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet2"},
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet3"},
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet4"},
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet5"},
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet6"}
        ]
        patch = jsonpatch.JsonPatch(patch_ops)
        filtered_patch = filter_duplicate_patch_operations(patch, config)
        filtered_ops = list(filtered_patch)
        self.assertEqual(len(filtered_ops), 0, "All adds are duplicates, should be filtered out in multi-asic config")

    def test_filter_duplicate_patch_operations_no_duplicates_multiasic(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        import jsonpatch
        # Multi-ASIC config: each ASIC has its own ACL_TABLE
        config = {
            "localhost": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet1", "Ethernet2"]
                    }
                }
            },
            "asic0": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet3", "Ethernet4"]
                    }
                }
            },
            "asic1": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet5", "Ethernet6"]
                    }
                }
            }
        }
        # Patch tries to add new ports to each ASIC's ACL_TABLE leaf-list
        patch_ops = [
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet7"},
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet8"},
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet9"},
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet10"},
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet11"},
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet12"}
        ]
        patch = jsonpatch.JsonPatch(patch_ops)
        filtered_patch = filter_duplicate_patch_operations(patch, config)
        filtered_ops = list(filtered_patch)
        self.assertEqual(
            len(filtered_ops),
            len(patch_ops),
            "No adds are duplicates, none should be filtered out in multi-asic config"
        )

    def test_filter_duplicate_patch_operations_mixed_multiasic(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        import jsonpatch
        # Multi-ASIC config: each ASIC has its own ACL_TABLE
        config = {
            "localhost": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet1", "Ethernet2"]
                    }
                }
            },
            "asic0": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet3", "Ethernet4"]
                    }
                }
            },
            "asic1": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": ["Ethernet5", "Ethernet6"]
                    }
                }
            }
        }
        # Patch tries to add some duplicate and some new ports to each ASIC's ACL_TABLE leaf-list
        patch_ops = [
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet1"},  # duplicate
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet8"},  # new
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet3"},      # duplicate
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet10"},    # new
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet5"},      # duplicate
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet12"}     # new
        ]
        patch = jsonpatch.JsonPatch(patch_ops)
        filtered_patch = filter_duplicate_patch_operations(patch, config)
        filtered_ops = list(filtered_patch)
        self.assertEqual(
            len(filtered_ops),
            3,
            "Three adds are duplicates, three are new and should remain in multi-asic config"
        )

    def test_filter_duplicate_patch_operations_empty_config_multiasic(self):
        from generic_config_updater.main import filter_duplicate_patch_operations
        import jsonpatch
        config = {
            "localhost": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": []
                    }
                }
            },
            "asic0": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": []
                    }
                }
            },
            "asic1": {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "ports": []
                    }
                }
            }
        }
        # Patch tries to add ports to each ASIC's ACL_TABLE leaf-list
        patch_ops = [
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet1"},
            {"op": "add", "path": "/localhost/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet2"},
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet3"},
            {"op": "add", "path": "/asic0/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet4"},
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet5"},
            {"op": "add", "path": "/asic1/ACL_TABLE/MY_ACL_TABLE/ports/-", "value": "Ethernet6"}
        ]
        patch = jsonpatch.JsonPatch(patch_ops)
        filtered_patch = filter_duplicate_patch_operations(patch, config)
        filtered_ops = list(filtered_patch)
        self.assertEqual(
            len(filtered_ops),
            len(patch_ops),
            "No adds are duplicates in empty list, "
            "none should be filtered out in multi-asic config"
        )

    def test_test_append_emptytables_if_required_basic_config_multiasic(self):
        from generic_config_updater.main import append_emptytables_if_required
        # Multi-ASIC config: each ASIC has its own PORT table
        config = {
            "localhost": {
                "PORT": {
                    "Ethernet0": {
                        "mtu": "9100"
                    }
                }
            },
            "asic0": {
                "PORT": {
                    "Ethernet1": {
                        "mtu": "9100"
                    }
                }
            },
            "asic1": {
                "PORT": {
                    "Ethernet2": {
                        "mtu": "9100"
                    }
                }
            }
        }
        # Patch does not include PORT table for asic1
        patch_ops = [
            {"op": "add", "path": "/localhost/BGP_NEIGHBOR/ARISTA01T1", "value": "10.0.0.1"},
            {"op": "add", "path": "/asic0/BGP_NEIGHBOR/ARISTA02T1", "value": "10.0.0.2"},
            {"op": "add", "path": "/asic1/BGP_NEIGHBOR/ARISTA02T1", "value": "10.0.0.3"}
        ]
        updated_patch = append_emptytables_if_required(patch_ops, config)
        updated_patch_list = list(updated_patch)
        assert len(updated_patch_list) == 6, "BGP_NEIGHBOR table for each namespace should be added to the patch"
        assert updated_patch_list[0] == {"op": "add", "path": "/localhost/BGP_NEIGHBOR", "value": {}}
        assert updated_patch_list[2] == {"op": "add", "path": "/asic0/BGP_NEIGHBOR", "value": {}}
        assert updated_patch_list[4] == {"op": "add", "path": "/asic1/BGP_NEIGHBOR", "value": {}}
        assert updated_patch_list[1] == patch_ops[0]
        assert updated_patch_list[3] == patch_ops[1]
        assert updated_patch_list[5] == patch_ops[2]

    def test_test_append_emptytables_if_required_no_additional_tables_multiasic(self):
        from generic_config_updater.main import append_emptytables_if_required
        # Multi-ASIC config: each ASIC has its own PORT table
        config = {
            "localhost": {
                "PORT": {
                    "Ethernet0": {
                        "mtu": "9100"
                    }
                }
            },
            "asic0": {
                "PORT": {
                    "Ethernet1": {
                        "mtu": "9100"
                    }
                }
            },
            "asic1": {
                "PORT": {
                    "Ethernet2": {
                        "mtu": "9100"
                    }
                }
            }
        }
        # Patch already includes PORT table for each namespace
        patch_ops = [
            {"op": "add", "path": "/localhost/PORT/Ethernet0/mtu", "value": "9200"},
            {"op": "add", "path": "/asic0/PORT/Ethernet1/mtu", "value": "9200"},
            {"op": "add", "path": "/asic1/PORT/Ethernet2/mtu", "value": "9200"}
        ]
        updated_patch = append_emptytables_if_required(patch_ops, config)
        assert len(updated_patch) == len(patch_ops), "No additional tables should be added to the patch"

    @patch('generic_config_updater.main.subprocess.Popen')
    @patch('sonic_yang_cfg_generator.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_multiasic(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 0)
        mock_instance.returncode = 0
        mock_subprocess_popen.return_value = mock_instance

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertEqual(result.exit_code, 0, "Command should succeed.")
                self.assertIn("Patch applied successfully.", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('generic_config_updater.main.subprocess.Popen')
    @patch('sonic_yang_cfg_generator.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_with_badpath_multiasic(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 0)
        mock_subprocess_popen.return_value = mock_instance

        bad_patch = copy.deepcopy(self.patch_content)
        bad_patch.append({
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet3", "Ethernet4"],
                    "stage": "ingress",
                    "type": "L3"
                }
            })

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(bad_patch)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertNotEqual(result.exit_code, 0, "Command should failed.")
                self.assertIn("Failed to apply patch", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('generic_config_updater.main.subprocess.Popen')
    @patch('sonic_yang_cfg_generator.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_parallel_badpath_multiasic(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 0)
        mock_subprocess_popen.return_value = mock_instance

        bad_patch = copy.deepcopy(self.patch_content)
        bad_patch.append({
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet3", "Ethernet4"],
                    "stage": "ingress",
                    "type": "L3"
                }
            })

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(bad_patch)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path,
                                            "--parallel"],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertNotEqual(result.exit_code, 0, "Command should failed.")
                self.assertIn("Failed to apply patch", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('generic_config_updater.main.subprocess.Popen')
    @patch('sonic_yang_cfg_generator.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_with_wrong_fetch_config(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 2)
        mock_subprocess_popen.return_value = mock_instance

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertNotEqual(result.exit_code, 0, "Command should failed.")
                self.assertIn("Failed to apply patch", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    def test_replace_multiasic(self):
        # Mock open to simulate file reading
        mock_replace_content = copy.deepcopy(self.all_config)
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_replace_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.replace_all = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.replace_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertEqual(result.exit_code, 0, "Command should succeed")
                self.assertIn("Config replaced successfully.", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.replace_file_path, 'r')

    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    def test_replace_multiasic_missing_scope(self):
        # Mock open to simulate file reading
        mock_replace_content = copy.deepcopy(self.all_config)
        mock_replace_content.pop("asic0")
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_replace_content)), create=True):
            print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
            # Invocation of the command with the CliRunner
            result = self.runner.invoke(config.config.commands["replace"],
                                        [self.replace_file_path],
                                        catch_exceptions=True)

            print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
            # Assertions and verifications
            self.assertNotEqual(result.exit_code, 0, "Command should failed")
            self.assertIn("Failed to replace config", result.output)

    @patch('generic_config_updater.generic_updater.subprocess.Popen')
    @patch('generic_config_updater.generic_updater.Util.ensure_checkpoints_dir_exists', mock.Mock(return_value=True))
    @patch('generic_config_updater.generic_updater.Util.save_json_file', MagicMock())
    def test_checkpoint_multiasic(self, mock_subprocess_popen):
        allconfigs = copy.deepcopy(self.all_config)

        # Create mock instances for each subprocess call
        mock_instance_localhost = MagicMock()
        mock_instance_localhost.communicate.return_value = (json.dumps(allconfigs["localhost"]), 0)
        mock_instance_localhost.returncode = 0

        mock_instance_asic0 = MagicMock()
        mock_instance_asic0.communicate.return_value = (json.dumps(allconfigs["asic0"]), 0)
        mock_instance_asic0.returncode = 0

        mock_instance_asic1 = MagicMock()
        mock_instance_asic1.communicate.return_value = (json.dumps(allconfigs["asic1"]), 0)
        mock_instance_asic1.returncode = 0

        # Setup side effect to return different mock instances based on input arguments
        def side_effect(*args, **kwargs):
            if "asic" not in args[0]:
                return mock_instance_localhost
            elif "asic0" in args[0]:
                return mock_instance_asic0
            elif "asic1" in args[0]:
                return mock_instance_asic1
            else:
                return MagicMock()  # Default case

        mock_subprocess_popen.side_effect = side_effect

        checkpointname = "checkpointname"
        print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
        # Invocation of the command with the CliRunner
        result = self.runner.invoke(config.config.commands["checkpoint"],
                                    [checkpointname],
                                    catch_exceptions=True)

        print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
        # Assertions and verifications
        self.assertEqual(result.exit_code, 0, "Command should succeed")
        self.assertIn("Checkpoint created successfully.", result.output)

    @patch('generic_config_updater.generic_updater.Util.check_checkpoint_exists', mock.Mock(return_value=True))
    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    @patch('generic_config_updater.generic_updater.Util.get_checkpoint_content')
    def test_rollback_multiasic(self, mock_get_checkpoint_content):
        mock_get_checkpoint_content.return_value = copy.deepcopy(self.all_config)
        checkpointname = "checkpointname"
        print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
        # Invocation of the command with the CliRunner
        result = self.runner.invoke(config.config.commands["rollback"],
                                    [checkpointname],
                                    catch_exceptions=True)

        print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
        # Assertions and verifications
        self.assertEqual(result.exit_code, 0, "Command should succeed")
        self.assertIn("Config rolled back successfully.", result.output)

    @patch('os.path.getmtime', mock.Mock(return_value=1700000000.0))
    @patch('generic_config_updater.generic_updater.Util.checkpoints_dir_exist', mock.Mock(return_value=True))
    @patch('generic_config_updater.generic_updater.Util.get_checkpoint_names',
           mock.Mock(return_value=["checkpointname"]))
    def test_list_checkpoint_multiasic(self):
        print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
        # Invocation of the command with the CliRunner
        result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                    catch_exceptions=True)

        print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
        # Assertions and verifications
        self.assertEqual(result.exit_code, 0, "Command should succeed")
        self.assertIn("checkpointname", result.output)

    @patch('generic_config_updater.generic_updater.Util.delete_checkpoint', MagicMock())
    @patch('generic_config_updater.generic_updater.Util.check_checkpoint_exists', mock.Mock(return_value=True))
    def test_delete_checkpoint_multiasic(self):
        checkpointname = "checkpointname"
        # Mock GenericUpdater to avoid actual patch application
        with patch('config.main.GenericUpdater') as mock_generic_updater:
            mock_generic_updater.return_value.delete_checkpoint = MagicMock()

            print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
            # Invocation of the command with the CliRunner
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [checkpointname],
                                        catch_exceptions=True)

            print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
            # Assertions and verifications
            self.assertEqual(result.exit_code, 0, "Command should succeed")
            self.assertIn("Checkpoint deleted successfully.", result.output)

    @patch('subprocess.Popen', mock.Mock(return_value=mock.Mock(
        communicate=mock.Mock(return_value=('{"some": "config"}', None)),
        returncode=0
    )))
    @patch('generic_config_updater.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__path_trace_option_multiasic__trace_file_opened_and_passed(self):
        # Arrange
        import tempfile
        mock_file_handle = mock.MagicMock()

        # Create a temporary file for the trace output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as trace_file:
            trace_file_path = trace_file.name

        try:
            # Mock open to simulate file reading
            with (
                patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as
                mock_open_func
            ):
                # Configure mock to return different handles for patch file and trace file
                def open_side_effect(filename, mode='r'):
                    if filename == trace_file_path:
                        return mock_file_handle
                    else:
                        return mock.mock_open(read_data=json.dumps(self.patch_content)).return_value
                mock_open_func.side_effect = open_side_effect

                # Mock GenericUpdater to avoid actual patch application
                with patch('generic_config_updater.main.GenericUpdater') as mock_generic_updater:
                    mock_generic_updater.return_value.apply_patch = MagicMock()

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path, "--path-trace", trace_file_path],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Verify the file handle was closed
                    mock_file_handle.close.assert_called_once()
        finally:
            # Clean up the temporary file
            import os
            if os.path.exists(trace_file_path):
                os.unlink(trace_file_path)

    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    def test_replace__path_trace_option_multiasic__trace_file_opened_and_passed(self):
        # Arrange
        import tempfile
        mock_file_handle = mock.MagicMock()
        mock_replace_content = copy.deepcopy(self.all_config)

        # Create a temporary file for the trace output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as trace_file:
            trace_file_path = trace_file.name

        try:
            with (
                patch('builtins.open', mock_open(read_data=json.dumps(mock_replace_content)), create=True) as
                mock_open_func
            ):
                # Configure mock to return different handles for config file and trace file
                def open_side_effect(filename, mode='r'):
                    if filename == trace_file_path:
                        return mock_file_handle
                    else:
                        return mock.mock_open(read_data=json.dumps(mock_replace_content)).return_value
                mock_open_func.side_effect = open_side_effect

                # Mock GenericUpdater to avoid actual replace operation
                with patch('config.main.GenericUpdater') as mock_generic_updater:
                    mock_generic_updater.return_value.replace_all = MagicMock()

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["replace"],
                                                [self.replace_file_path, "--path-trace", trace_file_path],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Config replaced successfully.", result.output)

                    # Verify the file handle was closed
                    mock_file_handle.close.assert_called_once()
        finally:
            # Clean up the temporary file
            import os
            if os.path.exists(trace_file_path):
                os.unlink(trace_file_path)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_database_config()


class TestConfigBanner(object):
    @classmethod
    def setup_class(cls):
        print('SETUP')
        import config.main
        importlib.reload(config.main)

    @patch('utilities_common.cli.run_command',
           mock.MagicMock(side_effect=mock_run_command_side_effect))
    def test_banner_state(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['banner'].commands['state'],
            ['enabled'], obj=obj)

        assert result.exit_code == 0

    @patch('utilities_common.cli.run_command',
           mock.MagicMock(side_effect=mock_run_command_side_effect))
    def test_banner_login(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['banner'].commands['login'],
            ['Login message'], obj=obj)

        assert result.exit_code == 0

    @patch('utilities_common.cli.run_command',
           mock.MagicMock(side_effect=mock_run_command_side_effect))
    def test_banner_logout(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['banner'].commands['logout'],
            ['Logout message'], obj=obj)

        assert result.exit_code == 0

    @patch('utilities_common.cli.run_command',
           mock.MagicMock(side_effect=mock_run_command_side_effect))
    def test_banner_motd(self):
        runner = CliRunner()
        obj = {'db': Db().cfgdb}

        result = runner.invoke(
            config.config.commands['banner'].commands['motd'],
            ['Motd message'], obj=obj)

        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        print('TEARDOWN')


class TestSwssReady(object):
    """Tests for the 'config reload' swss readiness gate on platforms without
    swss (e.g. BMC), plus regression guards for normal switches."""

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        import config.main
        importlib.reload(config.main)

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def test_swss_ready_when_service_not_found(self):
        # BMC: swss not built in -> not-found -> ready, only LoadState queried.
        with mock.patch('config.main.clicommon.run_command',
                        mock.MagicMock(return_value=("not-found", 0))) as mock_run:
            assert config._per_namespace_swss_ready("swss.service") is True
            assert mock_run.call_count == 1

    def test_swss_ready_when_service_masked(self):
        # Masked service -> ready, same as not-found.
        with mock.patch('config.main.clicommon.run_command',
                        mock.MagicMock(return_value=("masked", 0))) as mock_run:
            assert config._per_namespace_swss_ready("swss.service") is True
            assert mock_run.call_count == 1

    def test_swss_not_ready_when_loaded_but_inactive(self):
        # Switch still booting: loaded but inactive -> not ready.
        side_effect = [("loaded", 0), ("inactive", 0)]
        with mock.patch('config.main.clicommon.run_command',
                        mock.MagicMock(side_effect=side_effect)):
            assert config._per_namespace_swss_ready("swss.service") is False

    def test_swss_not_ready_when_active_but_not_settled(self):
        # Active for < 120s -> not ready.
        side_effect = [("loaded", 0), ("active", 0), ("1000000000", 0)]  # up = 1000s
        with mock.patch('config.main.clicommon.run_command',
                        mock.MagicMock(side_effect=side_effect)), \
                mock.patch('config.main.time.monotonic',
                           mock.MagicMock(return_value=1050.0)):  # 50s < 120s
            assert config._per_namespace_swss_ready("swss.service") is False

    def test_swss_ready_when_active_and_settled(self):
        # Active for > 120s -> ready.
        side_effect = [("loaded", 0), ("active", 0), ("1000000000", 0)]  # up = 1000s
        with mock.patch('config.main.clicommon.run_command',
                        mock.MagicMock(side_effect=side_effect)), \
                mock.patch('config.main.time.monotonic',
                           mock.MagicMock(return_value=2000.0)):  # 1000s > 120s
            assert config._per_namespace_swss_ready("swss.service") is True

    def test_swss_ready_single_asic_not_found(self):
        # _swss_ready() end-to-end, single-ASIC, swss not-found.
        with mock.patch('config.main.multi_asic.get_num_asics',
                        mock.MagicMock(return_value=1)), \
                mock.patch('config.main.clicommon.run_command',
                           mock.MagicMock(return_value=("not-found", 0))):
            assert config._swss_ready() is True


class TestGetMonitServicesByPrefix(object):
    """Tests for _get_monit_services_by_prefix()."""

    @mock.patch('config.main.subprocess.check_output')
    def test_finds_container_memory_services(self, mock_check_output):
        mock_check_output.return_value = (
            "Monit 5.33.0 uptime: 1h 2m\n"
            " routeCheck                       OK                          Program\n"
            " container_checker                OK                          Program\n"
            " container_memory_snmp            OK                          Program\n"
            " container_memory_gnmi            OK                          Program\n"
            " container_memory_bmp             OK                          Program\n"
        )
        result = config._get_monit_services_by_prefix('container_memory_')
        assert result == ['container_memory_snmp', 'container_memory_gnmi', 'container_memory_bmp']

    @mock.patch('config.main.subprocess.check_output')
    def test_no_matching_services(self, mock_check_output):
        mock_check_output.return_value = (
            " routeCheck                       OK                          Program\n"
            " container_checker                OK                          Program\n"
        )
        result = config._get_monit_services_by_prefix('container_memory_')
        assert result == []

    @mock.patch('config.main.subprocess.check_output',
                side_effect=subprocess.CalledProcessError(1, 'monit'))
    def test_monit_not_running(self, mock_check_output):
        result = config._get_monit_services_by_prefix('container_memory_')
        assert result == []


class TestRestartServicesMonitOrdering(object):
    """Regression test for sonic-net/sonic-utilities#4774.

    `monit monitor <service>` is asynchronous. If `monit reload` runs before
    the monitor action for a container_memory_* service has completed, that
    service can be left "Not monitored" permanently. This test verifies that
    every container_memory_* service discovered by
    _get_monit_services_by_prefix() is both monitored and waited on (via
    _wait_for_monit_service_monitored()) strictly before `monit reload`.
    """

    @mock.patch('config.main.reset_mgmt_interface_if_usb_not_running')
    @mock.patch('config.main.get_device_name', return_value=None)
    @mock.patch('config.main._monit_service_exists', return_value=False)
    @mock.patch('config.main.subprocess.check_call')
    @mock.patch('config.main.wait_service_restart_finish')
    @mock.patch('config.main.get_service_finish_timestamp', return_value="0")
    @mock.patch('config.main._get_monit_services_by_prefix',
                return_value=['container_memory_snmp', 'container_memory_gnmi'])
    @mock.patch('config.main._wait_for_monit_service_monitored')
    @mock.patch('config.main.clicommon.run_command')
    def test_memory_services_monitored_and_waited_before_reload(
        self, run_cmd, wait_mock, get_svcs, _gst, _wsrf, _check_call,
        _monit_exists, _get_dev, _reset_usb,
    ):
        # Shared event recorder so ordering across the two independent mocks
        # (clicommon.run_command and _wait_for_monit_service_monitored) can
        # actually be compared on a single timeline.
        events = []

        def run_command_side_effect(cmd, *args, **kwargs):
            if cmd[:3] == ['sudo', 'monit', 'monitor']:
                events.append(('monitor', cmd[3]))
            elif cmd == ['sudo', 'monit', 'reload']:
                events.append(('reload', None))
            return ("", 0)

        def wait_side_effect(service, timeout=10):
            events.append(('wait', service))

        run_cmd.side_effect = run_command_side_effect
        wait_mock.side_effect = wait_side_effect

        config._restart_services()

        memory_services = {'container_memory_snmp', 'container_memory_gnmi'}
        monitored = [svc for kind, svc in events if kind == 'monitor']
        waited = [svc for kind, svc in events if kind == 'wait']

        # sudo monit monitor container_checker / container_memory_snmp / container_memory_gnmi
        assert 'container_checker' in monitored
        assert memory_services <= set(monitored)

        # _wait_for_monit_service_monitored() called for container_checker and
        # both container_memory_* services.
        assert 'container_checker' in waited
        assert memory_services <= set(waited)

        # All memory-service waits must occur strictly before monit reload.
        reload_idx = next(i for i, e in enumerate(events) if e[0] == 'reload')
        memory_wait_idxs = [
            i for i, (kind, svc) in enumerate(events)
            if kind == 'wait' and svc in memory_services
        ]
        assert memory_wait_idxs, "no wait recorded for container_memory_* services"
        assert all(i < reload_idx for i in memory_wait_idxs)
