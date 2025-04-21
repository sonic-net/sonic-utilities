import copy
import datetime
import pytest
import filecmp
import importlib
import os
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
Disabling container and routeCheck monitoring ...
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Restarting SONiC target ...
Enabling container and routeCheck monitoring ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
Released lock on {0}
"""

load_minigraph_lock_failure_output = """\
Failed to acquire lock on {0}
"""

load_minigraph_command_bypass_lock_output = """\
Bypass lock on {}
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
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_YANG_CFG_OUTPUT = """\
Acquired lock on {0}
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -Y /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

RELOAD_MASIC_CONFIG_DB_OUTPUT = """\
Acquired lock on {0}
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -k  --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Running command: /usr/local/bin/sonic-cfggen -H -k  -n asic0 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json -n asic0 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -H -k  -n asic1 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json -n asic1 --write-to-db
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
Stopping SONiC target ...
Restarting SONiC target ...
Reloading Monit configuration ...
Released lock on {0}
"""

reload_config_masic_onefile_gen_sysinfo_output = """\
Acquired lock on {0}
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
            return 'sonic.target\nswss', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled', 0
        elif command == 'cat /var/run/dhclient.eth0.pid':
            return '101', 0
        elif command == 'sudo systemctl show --no-pager interfaces-config -p ExecMainExitTimestamp --value':
            return f'{datetime.datetime.now()}', 0
        elif command == 'sudo systemctl show --no-pager networking -p ExecMainExitTimestamp --value':
            return f'{datetime.datetime.now()}', 0
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
    def setup(self):
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

    def teardown(self):
        print("TEARDOWN")

class TestConfig(object):
    def setup(self):
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

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)),\
            mock.patch('config.main.open',
                       mock.MagicMock()):
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

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)),\
            mock.patch('config.main.open',
                       mock.MagicMock()):

            (config, show) = get_cmd_module

            runner = CliRunner()

            output_file = os.path.join(os.sep, "tmp", "config_db.json")
            result = runner.invoke(config.config.commands["save"], ["-y", output_file])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == save_config_filename_output

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

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)),\
            mock.patch('config.main.open',
                       mock.MagicMock()):

            runner = CliRunner()

            result = runner.invoke(config.config.commands["save"], ["-y"])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == save_config_masic_output

    def test_config_save_filename_masic(self):
        def read_json_file_side_effect(filename):
            return {}

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)),\
            mock.patch('config.main.open',
                       mock.MagicMock()):

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
            assert "\n".join([li.rstrip() for li in result.output.split('\n')]) == save_config_onefile_masic_output

            cwd = os.path.dirname(os.path.realpath(__file__))
            expected_result = os.path.join(
                cwd, "config_save_output", "all_config_db.json"
            )
            assert filecmp.cmp(output_file, expected_result, shallow=False)

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
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

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
                       mock.MagicMock(side_effect=read_json_file_side_effect)):

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
                       mock.MagicMock(side_effect=read_json_file_side_effect)):

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
            assert mock_run_command.call_count == 16

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
                assert mock_run_command.call_count == 12
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
            assert mock_run_command.call_count == 12

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

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

class TestReloadConfig(object):
    dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")
    dummy_cfg_file_asic0 = os.path.join(os.sep, "tmp", "config0.json")
    dummy_cfg_file_asic1 = os.path.join(os.sep, "tmp", "config1.json")

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

    def test_reload_config_masic(self, get_cmd_module, setup_multi_broadcom_masic):
        def read_json_file_side_effect(filename):
            return {}

        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)),\
            mock.patch('config.main.read_json_file',
                       mock.MagicMock(side_effect=read_json_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            # 3 config files: 1 for host and 2 for asic
            cfg_files = "{},{},{}".format(
                            self.dummy_cfg_file,
                            self.dummy_cfg_file,
                            self.dummy_cfg_file)

            result = runner.invoke(
                config.config.commands["reload"],
                [cfg_files, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) \
                == RELOAD_MASIC_CONFIG_DB_OUTPUT.format(config.SYSTEM_RELOAD_LOCK)

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


    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"PATCH_FILE_PATH\""

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        expected_call_with_default_values = mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"], [self.any_path], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call_with_default_values])

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(self.any_patch, ConfigFormat.SONICYANG, True, True, True, expected_ignore_path_tuple)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
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
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call_with_non_default_values])

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.apply_patch.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path],
                                            catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_apply_patch__optional_parameters_passed_correctly(self):
        self.validate_apply_patch_optional_parameter(
            ["--format", ConfigFormat.SONICYANG.name],
            mock.call(self.any_patch, ConfigFormat.SONICYANG, False, False, False, ()))
        self.validate_apply_patch_optional_parameter(
            ["--verbose"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, True, False, False, ()))
        self.validate_apply_patch_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, True, False, ()))
        self.validate_apply_patch_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False, True, ()))
        self.validate_apply_patch_optional_parameter(
            ["--ignore-path", "/ANY_TABLE"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False, False, ("/ANY_TABLE",)))

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def validate_apply_patch_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path] + param_args,
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call])

    def test_replace__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"TARGET_FILE_PATH\""

        # Act
        result = self.runner.invoke(config.config.commands["replace"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_replace__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["replace"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_replace__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        expected_call_with_default_values = mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"], [self.any_path], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call_with_default_values])

    def test_replace__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(self.any_target_config, ConfigFormat.SONICYANG, True, True, True, expected_ignore_path_tuple)
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
        self.assertTrue(expected_output in result.output)
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
            mock.call(self.any_target_config, ConfigFormat.SONICYANG, False, False, False, ()))
        self.validate_replace_optional_parameter(
            ["--verbose"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, True, False, False, ()))
        self.validate_replace_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, True, False, ()))
        self.validate_replace_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, True, ()))
        self.validate_replace_optional_parameter(
            ["--ignore-path", "/ANY_TABLE"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, False, ("/ANY_TABLE",)))

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
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call])

    def test_rollback__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"CHECKPOINT_NAME\""

        # Act
        result = self.runner.invoke(config.config.commands["rollback"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_rollback__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["rollback"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_rollback__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["rollback"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call])

    def test_checkpoint__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"CHECKPOINT_NAME\""

        # Act
        result = self.runner.invoke(config.config.commands["checkpoint"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_checkpoint__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["checkpoint"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call])

    def test_delete_checkpoint__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"CHECKPOINT_NAME\""

        # Act
        result = self.runner.invoke(config.config.commands["delete-checkpoint"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_delete_checkpoint__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["delete-checkpoint"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)

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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
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
        self.assertTrue(expected_output in result.output)
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
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["warm_restart"].commands["neighsyncd_timer"], ["2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    def test_warm_restart_neighsyncd_timer(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

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
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["warm_restart"].commands["bgp_timer"], ["2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    def test_warm_restart_bgp_timer(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

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
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["warm_restart"].commands["teamsyncd_timer"], ["2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid ConfigDB. Error" in result.output

    def test_warm_restart_teamsyncd_timer(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

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
        obj = {'db':db.cfgdb}

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
    def setup(self):
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

    def teardown(self):
        print("TEARDOWN")


class TestConfigAclUpdate(object):
    def setup(self):
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

    def teardown(self):
        print("TEARDOWN")


class TestConfigDropcounters(object):
    def setup(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_install(self, mock_run_command):
        counter_name = 'DEBUG_2'
        counter_type = 'PORT_INGRESS_DROPS'
        reasons = '[EXCEEDS_L2_MTU,DECAP_ERROR]'
        alias = 'BAD_DROPS'
        group = 'BAD'
        desc = 'more port ingress drops'

        runner = CliRunner()
        result = runner.invoke(config.config.commands['dropcounters'].commands['install'], [counter_name, counter_type, reasons, '-d', desc, '-g', group, '-a', alias])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'install', '-n', str(counter_name), '-t', str(counter_type), '-r', str(reasons), '-a', str(alias), '-g', str(group), '-d', str(desc)], display_cmd=False)

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
        result = runner.invoke(config.config.commands['dropcounters'].commands['add-reasons'], [counter_name, reasons, '-v'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['dropconfig', '-c', 'add', '-n', str(counter_name), '-r', str(reasons)], display_cmd=True)

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

    def teardown(self):
        print("TEARDOWN")


class TestConfigDropcountersMasic(object):
    def setup(self):
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
    def setup(self):
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

    def teardown(self):
        print("TEARDOWN")


class TestConfigZtp(object):
    def setup(self):
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

    def teardown(self):
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
    def setup(self):
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

    def teardown(self):
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_multiasic(self):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_dryrun_multiasic(self):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    @patch('config.main.concurrent.futures.wait', autospec=True)
    def test_apply_patch_dryrun_parallel_multiasic(self, MockThreadPoolWait):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    @patch('config.main.concurrent.futures.wait', autospec=True)
    def test_apply_patch_check_running_in_parallel_multiasic(self, MockThreadPoolWait):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    @patch('config.main.apply_patch_wrapper')
    def test_apply_patch_check_apply_call_parallel_multiasic(self, mock_apply_patch):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    @patch('config.main.concurrent.futures.wait', autospec=True)
    def test_apply_patch_check_running_in_not_parallel_multiasic(self, MockThreadPoolWait):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_parallel_with_error_multiasic(self):
        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_multiasic(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 0)
        mock_subprocess_popen.return_value = mock_instance

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
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
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
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
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_with_wrong_fetch_config(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 2)
        mock_subprocess_popen.return_value = mock_instance

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
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
