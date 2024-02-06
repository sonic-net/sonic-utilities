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
import shutil
from unittest import mock
from jsonpatch import JsonPatchConflict

import click
from click.testing import CliRunner

from sonic_py_common import device_info
from utilities_common.db import Db
from utilities_common.general import load_module_from_source
from mock import call, patch, mock_open, MagicMock

from generic_config_updater.generic_updater import ConfigFormat

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector

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

# Load minigraph input Path
load_minigraph_input_path = os.path.join(test_path, "load_minigraph_input")
load_minigraph_platform_path = os.path.join(load_minigraph_input_path, "platform")
load_minigraph_platform_false_path = os.path.join(load_minigraph_input_path, "platform_false")

load_minigraph_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

load_minigraph_platform_plugin_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Running Platform plugin ............!
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
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
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_YANG_CFG_OUTPUT = """\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -Y /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_MASIC_CONFIG_DB_OUTPUT = """\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json -n asic0 --write-to-db
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json -n asic1 --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

reload_config_with_sys_info_command_output="""\
Running command: /usr/local/bin/sonic-cfggen -H -k Seastone-DX010-25-50 --write-to-db"""

reload_config_with_disabled_service_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -j /tmp/config.json --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

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

            assert "\n".join([l.rstrip() for l in result.output.split('\n')][:1]) == reload_config_with_sys_info_command_output

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

            assert "\n".join([l.rstrip() for l in result.output.split('\n')][:1]) == reload_config_with_sys_info_command_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

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

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == load_minigraph_command_output
            # Verify "systemctl reset-failed" is called for services under sonic.target
            mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'swss'])
            assert mock_run_command.call_count == 8

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
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == load_minigraph_platform_plugin_command_output
            # Verify "systemctl reset-failed" is called for services under sonic.target
            mock_run_command.assert_any_call(['systemctl', 'reset-failed', 'swss'])
            assert mock_run_command.call_count == 8

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
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
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
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "-y"])
            assert result.exit_code == 0
            assert "config override-config-table /etc/sonic/golden_config_db.json" in result.output

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
            with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
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
                == RELOAD_CONFIG_DB_OUTPUT

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

            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == reload_config_with_disabled_service_output

    def test_reload_config_masic(self, get_cmd_module, setup_multi_broadcom_masic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
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
                == RELOAD_MASIC_CONFIG_DB_OUTPUT

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
                == RELOAD_YANG_CFG_OUTPUT

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

    @mock.patch('config.main._wait_until_clear')
    def test_qos_clear_no_wait(self, _wait_until_clear):
        from config.main import _clear_qos
        _clear_qos(True, False)
        _wait_until_clear.assert_called_with(['BUFFER_*_TABLE:*', 'BUFFER_*_SET'], interval=0.5, timeout=0, verbose=False)

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
        self.any_checkpoints_list_as_text = json.dumps(self.any_checkpoints_list, indent=4)

    def test_apply_patch__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"PATCH_FILE_PATH\""

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_apply_patch__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

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
        expected_output = self.any_checkpoints_list_as_text
        expected_call_with_non_default_values = mock.call(True)
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.return_value = self.any_checkpoints_list
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        ["--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.list_checkpoints.assert_called_once()
        mock_generic_updater.list_checkpoints.assert_has_calls([expected_call_with_non_default_values])

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
            mock.call(True))

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

    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_add_ntp_server_failed_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "10.10.10.x"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_add_ntp_server_invalid_ip(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["add", "10.10.10.x"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid IP address" in result.output

    def test_del_ntp_server_invalid_ip(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["ntp"], ["del", "10.10.10.x"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid IP address" in result.output

    @patch("config.main.ConfigDBConnector.get_table", mock.Mock(return_value="10.10.10.10"))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_del_ntp_server_invalid_ip_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

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
