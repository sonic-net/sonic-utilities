import os
import sys
import importlib
from unittest.mock import patch, MagicMock

import click
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestIPv6LinkLocalMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_show_ipv6_link_local_mode_with_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ipv6"].commands["link-local-mode"],
                               ["-n", "asic0"])
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet16" in result.output
        assert "Ethernet64" not in result.output

    def test_show_ipv6_link_local_mode_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ipv6"].commands["link-local-mode"], [])
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet16" in result.output
        assert "Ethernet64" in result.output

    def test_config_ipv6_enable_disable_link_local_with_namespace(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb_clients['asic0']}

        # Enable on asic0
        result = runner.invoke(config.config.commands["ipv6"].commands["enable"].commands["link-local"],
                               obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Verify asic0 Ethernet16 is enabled
        intf_entry = db.cfgdb_clients['asic0'].get_entry('INTERFACE', 'Ethernet16')
        assert intf_entry.get('ipv6_use_link_local_only') == 'enable'

        # Verify asic1 is NOT affected
        intf_entry_asic1 = db.cfgdb_clients['asic1'].get_entry('INTERFACE', 'Ethernet64')
        assert intf_entry_asic1.get('ipv6_use_link_local_only') != 'enable'

        # Disable on asic0
        result = runner.invoke(config.config.commands["ipv6"].commands["disable"].commands["link-local"],
                               obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_interface_ipv6_enable_disable_link_local_with_namespace(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb_clients['asic0']}

        # Enable on Ethernet16 (external port, not a portchannel/vlan member)
        result = runner.invoke(
            config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"],
            ["Ethernet16"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        intf_entry = db.cfgdb_clients['asic0'].get_entry('INTERFACE', 'Ethernet16')
        assert intf_entry.get('ipv6_use_link_local_only') == 'enable'

        # Disable
        result = runner.invoke(
            config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"],
            ["Ethernet16"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_interface_ipv6_enable_link_local_on_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb_clients['asic0']}

        # Ethernet0 is a member of PortChannel1002, should fail
        result = runner.invoke(
            config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"],
            ["Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "is configured as a member of portchannel" in result.output

    def test_config_interface_ipv6_enable_link_local_on_asic1(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb_clients['asic1']}

        # Enable on Ethernet64 (external port in asic1)
        result = runner.invoke(
            config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"],
            ["Ethernet64"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        intf_entry = db.cfgdb_clients['asic1'].get_entry('INTERFACE', 'Ethernet64')
        assert intf_entry.get('ipv6_use_link_local_only') == 'enable'

        # Disable
        result = runner.invoke(
            config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"],
            ["Ethernet64"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.dedicated_dbs = {}
        dbconnector.load_namespace_config()
