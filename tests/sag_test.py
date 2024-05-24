import pytest
import os
import logging
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db
from importlib import reload

show_sag_output="""\
Static Anycast Gateway Information
MacAddress         Interfaces
-----------------  ------------
00:11:22:33:44:55  Vlan1000
"""

class TestSag(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_config_add_sag_with_existed_mac(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["add"],
                        ["00:22:33:44:55:66"], obj=db)
        assert result.exit_code != 0, f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert {"gateway_mac": "00:11:22:33:44:55"} == db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_del_add_invalid_sag_mac_address(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["del"],
                        obj=db)
        assert result.exit_code == 0, f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert not db.cfgdb.get_entry("SAG", "GLOBAL")

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["add"],
                        ["01:22:33:44:55:66"], obj=db)
        assert result.exit_code != 0, f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert {"gateway_mac": "01:11:22:33:44:55"} != db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_del_add_sag_mac_address(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["del"],
                        obj=db)
        assert result.exit_code == 0, f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert not db.cfgdb.get_entry("SAG", "GLOBAL")

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["add"],
                        ["00:22:33:44:55:66"], obj=db)
        assert result.exit_code == 0, f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert {"gateway_mac": "00:22:33:44:55:66"} == db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_enable_sag_on_vlan_interface(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["enable"],
                        ["2000"], obj=db)
        assert result.exit_code == 0, f"sag invalid vlan with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert {"static_anycast_gateway": "true"}.items() <= db.cfgdb.get_entry("VLAN_INTERFACE", "Vlan2000").items()

    def test_config_disable_sag_on_vlan_interface(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["disable"],
                        ["1000"], obj=db)
        assert result.exit_code == 0, f"sag invalid vlan with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert {"static_anycast_gateway": "false"}.items() <= db.cfgdb.get_entry("VLAN_INTERFACE", "Vlan1000").items()

    def test_show_sag_mac(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["static-anycast-gateway"], [])
        assert result.exit_code == 0, f"invalid show sag with code {type(result.exit_code)}:{result.exit_code} Output:{result.output}"
        assert result.output == show_sag_output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
