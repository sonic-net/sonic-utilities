import os
import sys
import importlib.machinery
import importlib.util
import traceback
import mock
import jsonpatch
import pytest

from click.testing import CliRunner
from mock import patch
from jsonpatch import JsonPatchConflict

import config.main as config
import show.main as show
from utilities_common.db import Db
import config.validated_config_db_connector as validated_config_db_connector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

# Load scripts/storm_control.py as a module for direct function testing
# scripts/ is not a package, so use SourceFileLoader
_storm_loader = importlib.machinery.SourceFileLoader(
    "storm_control_script", os.path.join(scripts_path, "storm_control.py"))
_storm_spec = importlib.util.spec_from_loader("storm_control_script", _storm_loader)
storm_control_script = importlib.util.module_from_spec(_storm_spec)
_storm_loader.exec_module(storm_control_script)

show_storm_interface_output = """\
+------------------+-------------------+---------------+
| Interface Name   | Storm Type        |   Rate (kbps) |
+==================+===================+===============+
| Ethernet0        | broadcast         |        100000 |
+------------------+-------------------+---------------+
| Ethernet0        | unknown-unicast   |        200000 |
+------------------+-------------------+---------------+
| Ethernet0        | unknown-multicast |        300000 |
+------------------+-------------------+---------------+
"""

show_storm_namespace_output = """\
+------------------+-------------------+---------------+
| Interface Name   | Storm Type        |   Rate (kbps) |
+==================+===================+===============+
| Ethernet0        | broadcast         |        111000 |
+------------------+-------------------+---------------+
| Ethernet0        | unknown-unicast   |        222000 |
+------------------+-------------------+---------------+
| Ethernet0        | unknown-multicast |        333000 |
+------------------+-------------------+---------------+
"""


class TestStormControlScript(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    def _run_main(self, *argv):
        with mock.patch.object(sys, 'argv', ["storm_control.py", *argv]):
            storm_control_script.main()

    def test_list_all_ports(self, capsys):
        sc = storm_control_script.storm_control()
        sc.show_storm_config(None)
        out = capsys.readouterr().out
        print(out)
        assert "Ethernet0" in out
        assert "Ethernet4" in out
        assert "Ethernet8" in out
        assert "100000" in out
        assert "600000" in out

    def test_list_single_port(self, capsys):
        sc = storm_control_script.storm_control()
        sc.show_storm_config("Ethernet4")
        out = capsys.readouterr().out
        print(out)
        assert "Ethernet4" in out
        assert "400000" in out
        assert "Ethernet0" not in out

    def test_add_new_entry(self):
        sc = storm_control_script.storm_control()
        assert sc.add_storm_config("Ethernet12", "broadcast", 150000) is True
        entry = sc.config_db.get_entry("PORT_STORM_CONTROL", "Ethernet12|broadcast")
        print("Ethernet12|broadcast ->", entry)
        assert entry == {"kbps": "150000"}

    def test_add_updates_existing_entry(self):
        sc = storm_control_script.storm_control()
        before = sc.config_db.get_entry("PORT_STORM_CONTROL", "Ethernet0|broadcast")
        assert sc.add_storm_config("Ethernet0", "broadcast", 123456) is True
        after = sc.config_db.get_entry("PORT_STORM_CONTROL", "Ethernet0|broadcast")
        print("Ethernet0|broadcast:", before, "->", after)
        assert after == {"kbps": "123456"}

    def test_del_existing_entry(self):
        sc = storm_control_script.storm_control()
        assert sc.del_storm_config("Ethernet0", "broadcast") is True
        entry = sc.config_db.get_entry("PORT_STORM_CONTROL", "Ethernet0|broadcast")
        print("Ethernet0|broadcast after delete ->", entry)
        assert entry == {}

    def test_del_missing_entry_is_noop(self):
        sc = storm_control_script.storm_control()
        assert sc.del_storm_config("Ethernet12", "broadcast") is True

    def test_invalid_interface_rejected(self, capsys):
        sc = storm_control_script.storm_control()
        assert sc.add_storm_config("Vlan10", "broadcast", 1) is False
        assert sc.del_storm_config("Vlan10", "broadcast") is False
        assert "Invalid Interface:Vlan10" in capsys.readouterr().out

    def test_main_list_alone(self, capsys):
        self._run_main("-l")
        out = capsys.readouterr().out
        print(out)
        assert "Ethernet0" in out

    def test_main_list_port(self, capsys):
        self._run_main("-l", "-p", "Ethernet8")
        out = capsys.readouterr().out
        print(out)
        assert "Ethernet8" in out
        assert "Ethernet0" not in out

    def test_main_add_accepts_zero_rate(self):
        self._run_main("-p", "Ethernet0", "-t", "broadcast", "-r", "0")

    def test_main_delete_is_a_flag(self):
        self._run_main("-p", "Ethernet0", "-t", "broadcast", "-d")

    def test_main_delete_with_value_rejected(self):
        with pytest.raises(SystemExit) as e:
            self._run_main("-p", "Ethernet0", "-t", "broadcast", "-d", "yes")
        print("exit code:", e.value.code)
        assert e.value.code == 2

    def test_main_invalid_storm_type_rejected(self):
        with pytest.raises(SystemExit) as e:
            self._run_main("-p", "Ethernet0", "-t", "bcast", "-r", "1")
        print("exit code:", e.value.code)
        assert e.value.code == 2

    def test_main_incomplete_args_prints_help(self, capsys):
        with pytest.raises(SystemExit) as e:
            self._run_main("-p", "Ethernet0")
        out = capsys.readouterr().out
        print("exit code:", e.value.code)
        print(out)
        assert e.value.code == 1
        assert "usage:" in out


class TestStormControl(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_add_broadcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "broadcast", "10000"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_add_uucast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "unknown-unicast", "10000"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value=""))
    def test_add_umcast_storm_yang_empty_entry(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "unknown-multicast", "10000"], obj = obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value={'kbps': '1000'}))
    def test_add_umcast_storm_yang_non_empty_entry(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "unknown-multicast", "10000"], obj = obj)
        print(result.exit_code)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_add_umcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "unknown-multicast", "10000"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_del_broadcast_storm_yang(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "broadcast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_del_broadcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "broadcast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0
    
    def test_del_uucast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "unknown-unicast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_del_umcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "unknown-multicast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_show_storm(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["storm-control"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_show_storm_interface(self):
        runner = CliRunner()
        result = runner.invoke(show.cli, ["storm-control", "interface", "Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_storm_interface_output

    @patch("utilities_common.multi_asic.multi_asic.is_multi_asic",
           mock.Mock(return_value=True))
    @patch("show.main.multi_asic_util.multi_asic_get_ip_intf_from_ns",
           mock.Mock(return_value=['Ethernet0']))
    def test_show_storm_namespace(self):
        # On multi-ASIC, storm-control config lives in the per-ASIC CONFIG_DB. The
        # asic0 mock DB has distinctive rates (111000/222000/333000) that differ from
        # the host DB, so asserting this output proves the namespace path reads the
        # correct per-ASIC database. is_multi_asic is patched True so the
        # -n/--namespace option is accepted even when
        # multi_asic_namespace_validation_callback is fixed to call is_multi_asic().
        runner = CliRunner()
        result = runner.invoke(show.cli, ["storm-control", "-n", "asic0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_storm_namespace_output

    @patch("show.main.multi_asic.is_multi_asic", mock.Mock(return_value=True))
    @patch("show.main.multi_asic.get_namespace_list",
           mock.Mock(return_value=['asic0', 'asic1']))
    def test_show_storm_interface_namespace(self):
        # On multi-ASIC, 'show storm-control -n <ns> interface <intf>' must read the
        # per-ASIC CONFIG_DB. The asic0 mock DB uses distinctive rates
        # (111000/222000/333000), so asserting this output proves the interface
        # subcommand honors the selected namespace instead of the host database.
        runner = CliRunner()
        result = runner.invoke(
            show.cli, ["storm-control", "-n", "asic0", "interface", "Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_storm_namespace_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
