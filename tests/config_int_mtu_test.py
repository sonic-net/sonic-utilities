import pytest
from unittest import mock
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

    def test_interface_mtu_exceeds_device_max(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('config.main.get_interface_max_mtu', return_value=9100):
            result = runner.invoke(
                config.config.commands["interface"].commands["mtu"],
                ["Ethernet0", "9216"], obj={'config_db': db.cfgdb, 'namespace': ''})
        assert result.exit_code != 0
        assert "exceeds maximum supported MTU 9100" in result.output

    def test_interface_mtu_within_device_max(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('config.main.get_interface_max_mtu', return_value=9100), \
                mock.patch('config.main.clicommon.run_command') as mock_run:
            result = runner.invoke(
                config.config.commands["interface"].commands["mtu"],
                ["Ethernet0", "9000"], obj={'config_db': db.cfgdb, 'namespace': ''})
        assert "exceeds maximum supported MTU" not in result.output
        mock_run.assert_called_once()

    def test_interface_mtu_unknown_device_max_fail_open(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('config.main.get_interface_max_mtu', return_value=None), \
                mock.patch('config.main.clicommon.run_command') as mock_run:
            runner.invoke(
                config.config.commands["interface"].commands["mtu"],
                ["Ethernet0", "9216"], obj={'config_db': db.cfgdb, 'namespace': ''})
        mock_run.assert_called_once()

    def test_get_interface_max_mtu_parses_netdev_output(self):
        sample = ("15: Ethernet0: <BROADCAST,MULTICAST,UP> mtu 9100 "
                  "minmtu 32 maxmtu 9198 addrgenmode eui64")
        with mock.patch('config.main.subprocess.check_output', return_value=sample):
            assert config.get_interface_max_mtu("Ethernet0") == 9198

    def test_get_interface_max_mtu_none_when_unreadable(self):
        with mock.patch('config.main.subprocess.check_output', side_effect=OSError):
            assert config.get_interface_max_mtu("Ethernet0") is None
