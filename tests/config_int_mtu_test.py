import pytest
import config.main as config
from click.testing import CliRunner
from utilities_common.db import Db

class TestConfigInterfaceMtu(object):
    def test_interface_mtu_check(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["interface"].commands["mtu"],
            ["Ethernet0", "68"], obj=db)
        assert result.exit_code != 0

        result1 = runner.invoke(config.config.commands["interface"].commands["mtu"],
            ["Ethernet0", "9216"], obj=db)
        assert result1.exit_code != 0

    def test_interface_invalid_mtu_check(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["interface"].commands["mtu"],
            ["Ethernet0", "67"], obj=db)
        assert "Error: Invalid value" in result.output
        result1 = runner.invoke(config.config.commands["interface"].commands["mtu"],
            ["Ethernet0", "9217"], obj=db)
        assert "Error: Invalid value" in result1.output

    def test_portchannel_mtu_check(self):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'db_wrap': db, 'namespace': ''}
        # Ethernet32 is already member of PortChannel1001, try (fail) to change mtu
        result = runner.invoke(
                            config.config.commands["interface"].commands["mtu"],
                            ["Ethernet32", "1000"], obj=obj)
        assert result.exit_code != 0
        # remove port from portchannel
        result = runner.invoke(
                            config.config.commands["portchannel"].commands["member"].commands["del"],
                            ["PortChannel1001", "Ethernet32"], obj=obj)
        assert result.exit_code == 0
        # Set mtu for port interface
        result = runner.invoke(config.config.commands["interface"].commands["mtu"], ["Ethernet32", "1000"], obj=obj)
        assert result.exit_code != 0
        # Add port back to portchannel
        result = runner.invoke(
                            config.config.commands["portchannel"].commands["member"].commands["add"],
                            ["PortChannel1001", "Ethernet32"], obj=obj)
        print(result.output)
        assert result.exit_code == 0
