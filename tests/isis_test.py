import os
import pytest
from unittest import mock
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


class TestIsis(object):
    config_isis_enable = config.config.commands["isis"].commands["enable"]
    config_isis_disable = config.config.commands["isis"].commands["disable"]
    config_isis_net = config.config.commands["isis"].commands["net"]
    config_isis_level = config.config.commands["isis"].commands["level"]
    config_isis_hostname = config.config.commands["isis"].commands["hostname"]

    config_isis_timer_lsp_mtu = config.config.commands["isis"].commands["timer"].commands["lsp-mtu"]
    config_isis_timer_lsp_refresh = config.config.commands["isis"].commands["timer"].commands["lsp-refresh"]
    config_isis_timer_lsp_lifetime = config.config.commands["isis"].commands["timer"].commands["lsp-lifetime"]

    config_interface_isis_enable = config.interface.commands["isis"].commands["enable"]
    config_interface_isis_disable = config.interface.commands["isis"].commands["disable"]
    config_interface_isis_metric = config.interface.commands["isis"].commands["metric"]
    config_interface_isis_circuit_type = config.interface.commands["isis"].commands["circuit-type"]
    config_interface_isis_passive = config.interface.commands["isis"].commands["passive"]

    show_isis_summary = show.cli.commands["isis"].commands["summary"]
    show_isis_neighbor = show.cli.commands["isis"].commands["neighbor"]
    show_isis_database = show.cli.commands["isis"].commands["database"]

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        pass

    def test_isis_enable_disable(self):
        db = Db()
        runner = CliRunner()
        obj = db

        # Enable IS-IS default VRF
        result = runner.invoke(self.config_isis_enable, [], obj=obj)
        assert result.exit_code == 0
        assert "default" in db.cfgdb.get_table("ISIS_GLOBALS")
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["enabled"] == "true"

        # Enable IS-IS for non-default VRF Vrf2
        result = runner.invoke(self.config_isis_enable, ["Vrf2"], obj=obj)
        assert result.exit_code == 0
        assert "Vrf2" in db.cfgdb.get_table("ISIS_GLOBALS")
        assert db.cfgdb.get_table("ISIS_GLOBALS")["Vrf2"]["enabled"] == "true"

        # Disable IS-IS for Vrf2
        result = runner.invoke(self.config_isis_disable, ["Vrf2"], obj=obj)
        assert result.exit_code == 0
        assert "Vrf2" not in db.cfgdb.get_table("ISIS_GLOBALS")

        # Disable IS-IS default VRF
        result = runner.invoke(self.config_isis_disable, [], obj=obj)
        assert result.exit_code == 0
        assert "default" not in db.cfgdb.get_table("ISIS_GLOBALS")

    def test_isis_net_level_hostname(self):
        db = Db()
        runner = CliRunner()
        obj = db

        # Try configuring without enabling first (should fail)
        result = runner.invoke(self.config_isis_net, ["49.0001.1921.6800.0001.00"], obj=obj)
        assert result.exit_code != 0

        # Enable first
        runner.invoke(self.config_isis_enable, [], obj=obj)

        # Set valid NET
        result = runner.invoke(self.config_isis_net, ["49.0001.1921.6800.0001.00"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["net_title"] == "49.0001.1921.6800.0001.00"

        # Set invalid NET (should fail)
        result = runner.invoke(self.config_isis_net, ["invalid-net"], obj=obj)
        assert result.exit_code != 0

        # Set level
        result = runner.invoke(self.config_isis_level, ["level-1"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["level"] == "level-1"

        # Set hostname
        result = runner.invoke(self.config_isis_hostname, ["enabled"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["dynamic_hostname"] == "true"

    def test_isis_timers(self):
        db = Db()
        runner = CliRunner()
        obj = db

        # Enable first
        runner.invoke(self.config_isis_enable, [], obj=obj)

        # Set lsp-mtu
        result = runner.invoke(self.config_isis_timer_lsp_mtu, ["1400"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS_TIMERS")["default"]["lsp_mtu"] == "1400"

        # Set out-of-range lsp-mtu (should fail)
        result = runner.invoke(self.config_isis_timer_lsp_mtu, ["9999"], obj=obj)
        assert result.exit_code != 0

        # Set lsp-refresh
        result = runner.invoke(self.config_isis_timer_lsp_refresh, ["900"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS_TIMERS")["default"]["lsp_refresh_interval"] == "900"

        # Set lsp-lifetime
        result = runner.invoke(self.config_isis_timer_lsp_lifetime, ["1500"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS_TIMERS")["default"]["lsp_lifetime"] == "1500"

    def test_isis_interface(self):
        db = Db()
        runner = CliRunner()

        # Let's mock a port in CONFIG_DB so validation passes
        db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "up"})

        obj = {'config_db': db.cfgdb, 'namespace': 'default'}

        # Enable ISIS on Ethernet0
        result = runner.invoke(self.config_interface_isis_enable, ["Ethernet0"], obj=obj)
        assert result.exit_code == 0
        assert "Ethernet0" in db.cfgdb.get_table("ISIS_INTERFACE")

        # Configure Metric
        result = runner.invoke(self.config_interface_isis_metric, ["Ethernet0", "20"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_INTERFACE")["Ethernet0"]["metric"] == "20"

        # Configure Circuit Type
        result = runner.invoke(self.config_interface_isis_circuit_type, ["Ethernet0", "p2p"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_INTERFACE")["Ethernet0"]["circuit_type"] == "p2p"

        # Configure Passive Mode
        result = runner.invoke(self.config_interface_isis_passive, ["Ethernet0", "enable"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_INTERFACE")["Ethernet0"]["passive"] == "true"

        # Disable ISIS on Ethernet0
        result = runner.invoke(self.config_interface_isis_disable, ["Ethernet0"], obj=obj)
        assert result.exit_code == 0
        assert "Ethernet0" not in db.cfgdb.get_table("ISIS_INTERFACE")

    @mock.patch('utilities_common.cli.run_command')
    def test_show_isis(self, mock_run_command):
        mock_run_command.return_value = ("IS-IS output summary mock", 0)
        runner = CliRunner()

        # show isis summary
        result = runner.invoke(self.show_isis_summary, [])
        assert result.exit_code == 0
        assert "IS-IS output summary mock" in result.output
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', 'show isis summary'], return_cmd=True)

        # show isis neighbor --json
        mock_run_command.return_value = ("[]", 0)
        result = runner.invoke(self.show_isis_neighbor, ["--json"])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', 'show isis neighbor json'], return_cmd=True)
