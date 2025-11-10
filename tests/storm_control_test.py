import os
import traceback
import mock
import jsonpatch

from click.testing import CliRunner
from mock import patch
from jsonpatch import JsonPatchConflict

import config.main as config
import show.main as show
from utilities_common.db import Db
import config.validated_config_db_connector as validated_config_db_connector

show_storm_interface_output="""\
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

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
