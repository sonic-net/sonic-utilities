import pytest
import click

import config.main as config

from click.testing import CliRunner
from config.main import expand_vlan_ports, parse_acl_table_info
from unittest import mock
from mock import patch


class TestConfigAcl(object):
    def test_expand_vlan(self):
        assert set(expand_vlan_ports("Vlan1000")) == {"Ethernet4", "Ethernet8", "Ethernet12", "Ethernet16"}

    def test_expand_lag(self):
        assert set(expand_vlan_ports("PortChannel1001")) == {"PortChannel1001"}

    def test_expand_physical_interface(self):
        assert set(expand_vlan_ports("Ethernet4")) == {"Ethernet4"}

    def test_expand_empty_vlan(self):
        with pytest.raises(ValueError):
            expand_vlan_ports("Vlan3000")

    def test_parse_table_with_vlan_expansion(self):
        table_info = parse_acl_table_info("TEST", "L3", None, "Vlan1000", "egress")
        assert table_info["type"] == "L3"
        assert table_info["policy_desc"] == "TEST"
        assert table_info["stage"] == "egress"
        assert set(table_info["ports"]) == {"Ethernet4", "Ethernet8", "Ethernet12", "Ethernet16"}

    def test_parse_table_with_vlan_and_duplicates(self):
        table_info = parse_acl_table_info("TEST", "L3", None, "Ethernet4,Vlan1000", "egress")
        assert table_info["type"] == "L3"
        assert table_info["policy_desc"] == "TEST"
        assert table_info["stage"] == "egress"

        # Since Ethernet4 is a member of Vlan1000 we should not include it twice in the output
        port_set = set(table_info["ports"])
        assert len(port_set) == 4
        assert set(port_set) == {"Ethernet4", "Ethernet8", "Ethernet12", "Ethernet16"}

    def test_parse_table_with_empty_vlan(self):
        with pytest.raises(ValueError):
            parse_acl_table_info("TEST", "L3", None, "Ethernet4,Vlan3000", "egress")

    def test_parse_table_with_invalid_ports(self):
        with pytest.raises(ValueError):
            parse_acl_table_info("TEST", "L3", None, "Ethernet200", "egress")

    def test_parse_table_with_empty_ports(self):
        with pytest.raises(ValueError):
            parse_acl_table_info("TEST", "L3", None, "", "egress")

    def test_acl_add_table_nonexistent_port(self):
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["acl"].commands["add"].commands["table"],
            ["TEST", "L3", "-p", "Ethernet200"])

        assert result.exit_code != 0
        assert "Cannot bind ACL to specified port Ethernet200" in result.output

    def test_acl_add_table_empty_string_port_list(self):
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["acl"].commands["add"].commands["table"],
            ["TEST", "L3", "-p", ""])

        assert result.exit_code != 0
        assert "Cannot bind empty list of ports" in result.output

    def test_acl_add_table_empty_vlan(self):
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["acl"].commands["add"].commands["table"],
            ["TEST", "L3", "-p", "Vlan3000"])

        assert result.exit_code != 0
        assert "Cannot bind empty VLAN Vlan3000" in result.output

    @patch("config.main.ConfigDBConnector")
    def test_acl_add_table_with_namespace(self, mock_cfg_connector):
        mock_instance = mock.Mock()
        mock_cfg_connector.return_value = mock_instance
        mock_instance.connect.return_value = None

        def get_table_side_effect(name):
            if name == "PORTCHANNEL_MEMBER":
                return {}
            if name == "PORT":
                return {"Ethernet0": {}}
            return {}

        mock_instance.get_table.side_effect = get_table_side_effect

        def get_keys_side_effect(name):
            if name in ("VLAN", "VLAN_MEMBER"):
                return []
            return []

        mock_instance.get_keys.side_effect = get_keys_side_effect

        runner = CliRunner()
        cmd = config.config.commands["acl"].commands["add"].commands["table"]
        namespace_param = next(param for param in cmd.params if param.name == "namespace")
        namespace_param.type = click.Choice(["asic0", "asic1"])
        result = runner.invoke(
            cmd,
            ["DATAACL", "L3", "-p", "Ethernet0", "-s", "ingress", "-n", "asic0"]
        )
        assert result.exit_code == 0

        mock_cfg_connector.assert_any_call(namespace="asic0")
        mock_instance.set_entry.assert_called_once()
        table_name = mock_instance.set_entry.call_args[0][1]
        table_info = mock_instance.set_entry.call_args[0][2]
        assert table_name == "DATAACL"
        assert table_info["ports"] == ["Ethernet0"]
        assert table_info["stage"] == "ingress"
        assert table_info["type"] == "L3"

    @patch("config.main.ConfigDBConnector")
    def test_acl_remove_table_with_namespace(self, mock_cfg_connector):
        mock_instance = mock.Mock()
        mock_cfg_connector.return_value = mock_instance
        mock_instance.connect.return_value = None

        runner = CliRunner()
        cmd = config.config.commands["acl"].commands["remove"].commands["table"]
        namespace_param = next(param for param in cmd.params if param.name == "namespace")
        namespace_param.type = click.Choice(["asic0", "asic1"])
        result = runner.invoke(cmd, ["DATAACL", "-n", "asic0"])
        assert result.exit_code == 0

        mock_cfg_connector.assert_called_once_with(namespace="asic0")
        mock_instance.set_entry.assert_called_once_with("ACL_TABLE", "DATAACL", None)
