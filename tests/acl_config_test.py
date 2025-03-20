import pytest

import config.main as config

from click.testing import CliRunner
from config.main import expand_vlan_ports, parse_acl_table_info
from swsssdk import ConfigDBConnector

class TestConfigAcl(object):
    @pytest.fixture(scope="function", params= ["mellanox", "broadcom"])
    def asic_type(self, request):
        org_asic_type = config.asic_type
        config.asic_type = request.param

        yield request.param

        config.asic_type = org_asic_type

    def test_expand_vlan(self):
        assert set(expand_vlan_ports("Vlan1000")) == {"Ethernet4", "Ethernet8", "Ethernet12", "Ethernet16"}

    def test_expand_lag(self):
        assert set(expand_vlan_ports("PortChannel1001")) == {"PortChannel1001"}

    def test_expand_physical_interface(self):
        assert set(expand_vlan_ports("Ethernet4")) == {"Ethernet4"}

    def test_expand_empty_vlan(self):
        with pytest.raises(ValueError):
            expand_vlan_ports("Vlan3000")

    def test_parse_table_with_vlan_expansion(self, asic_type):
        table_info = parse_acl_table_info("TEST", "L3", None, "Vlan1000", "egress")

        assert table_info["type"] == "L3"
        assert table_info["policy_desc"] == "TEST"
        assert table_info["stage"] == "egress"

        if asic_type == "mellanox":
            assert set(table_info["ports"]) == {"Ethernet4", "Ethernet8", "Ethernet12", "Ethernet16"}
        else:
            assert set(table_info["ports"]) == {"Vlan1000"}

    def test_parse_table_with_vlan_and_duplicates(self, asic_type):
        table_info = parse_acl_table_info("TEST", "L3", None, "Ethernet4,Vlan1000", "egress")
        assert table_info["type"] == "L3"
        assert table_info["policy_desc"] == "TEST"
        assert table_info["stage"] == "egress"

        port_set = set(table_info["ports"])

        if asic_type == "mellanox":
            # Since Ethernet4 is a member of Vlan1000 we should not include it twice in the output
            assert len(port_set) == 4
            assert port_set == {"Ethernet4", "Ethernet8", "Ethernet12", "Ethernet16"}
        else:
            assert port_set == {"Ethernet4", "Vlan1000"}

    def test_parse_table_with_empty_vlan(self, asic_type):
        if asic_type == "mellanox":
            with pytest.raises(ValueError):
                parse_acl_table_info("TEST", "L3", None, "Ethernet4,Vlan3000", "egress")
        else:
            table_info = parse_acl_table_info("TEST", "L3", None, "Ethernet4,Vlan3000", "egress")
            assert table_info["type"] == "L3"
            assert table_info["policy_desc"] == "TEST"
            assert table_info["stage"] == "egress"
            assert set(table_info["ports"]) == {"Ethernet4", "Vlan3000"}

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

    def test_acl_add_table_empty_vlan(self, asic_type):
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["acl"].commands["add"].commands["table"],
            ["TEST", "L3", "-p", "Vlan3000"])

        if asic_type == "mellanox":
            assert result.exit_code != 0
            assert "Cannot bind empty VLAN Vlan3000" in result.output
        else:
            assert result.exit_code == 0