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
