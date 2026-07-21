from click.testing import CliRunner

import config.main as config
from utilities_common.db import Db


class TestConfigMac(object):
    def test_config_mac_add(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["mac"].commands["add"],
                               ["00:11:22:33:44:55", "1000", "Ethernet4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("FDB", ("Vlan1000", "00:11:22:33:44:55")) == {"port": "Ethernet4"}

    def test_config_mac_add_invalid_mac(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["mac"].commands["add"],
                               ["invalid-mac", "1000", "Ethernet4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "not a valid unicast MAC address" in result.output

    def test_config_mac_add_multicast_mac(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["mac"].commands["add"],
                               ["01:00:5e:00:00:01", "1000", "Ethernet4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "not a valid unicast MAC address" in result.output

    def test_config_mac_add_nonexistent_vlan(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["mac"].commands["add"],
                               ["00:11:22:33:44:55", "999", "Ethernet4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Vlan999 does not exist" in result.output

    def test_config_mac_add_invalid_interface(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["mac"].commands["add"],
                               ["00:11:22:33:44:55", "1000", "Ethernet999"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "is invalid" in result.output

    def test_config_mac_del(self):
        runner = CliRunner()
        db = Db()

        runner.invoke(config.config.commands["mac"].commands["add"],
                      ["00:11:22:33:44:55", "1000", "Ethernet4"], obj=db)
        result = runner.invoke(config.config.commands["mac"].commands["del"],
                               ["00:11:22:33:44:55", "1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("FDB", ("Vlan1000", "00:11:22:33:44:55")) == {}
