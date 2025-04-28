import pytest
from typing import Tuple

import config.main as config

from click.testing import CliRunner
from config.main import expand_vlan_ports, parse_acl_table_info

from swsssdk import ConfigDBConnector

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

    @pytest.fixture(scope="function")
    def mock_configDBConnector(self):
        db = {
            "ACL_RULE": {},
            "ACL_TABLE": {}
        }

        def _get_keys(self, table_name):
            data = []
            for key in db[table_name]:
                k = key.split('|')
                data.append((k[0], k[1]))

            return data

        def _set_entry(self, table_name, key, value):
            tmp_key = key
            if isinstance(key, Tuple):
                tmp_key = '|'.join(key)

            # if tmp_key not in db[table_name]:
            #     assert False

            data = db[table_name][tmp_key]
            if value == None:
                data['removed'] = True

        orig_get_keys = ConfigDBConnector.get_keys
        orig_set_entry= ConfigDBConnector.set_entry

        ConfigDBConnector.get_keys = _get_keys
        ConfigDBConnector.set_entry = _set_entry

        yield db

        ConfigDBConnector.get_keys = orig_get_keys
        ConfigDBConnector.get_keys = orig_set_entry

    def test_acl_remove_table(self, mock_configDBConnector):
        runner = CliRunner()

        config_db = ConfigDBConnector()
        config_db.connect()

        ACL_TABLE_NAME = "DATA_ACL2"

        mock_configDBConnector["ACL_RULE"]["DATA_ACL|RULE1"] = {}
        mock_configDBConnector["ACL_RULE"]["DATA_ACL|RULE1"]["removed"] = False
        mock_configDBConnector["ACL_RULE"]["DATA_ACL|RULE2"] = {}
        mock_configDBConnector["ACL_RULE"]["DATA_ACL|RULE2"]["removed"] = False

        mock_configDBConnector["ACL_RULE"]["{}|RULE1".format(ACL_TABLE_NAME)] = {}
        mock_configDBConnector["ACL_RULE"]["{}|RULE1".format(ACL_TABLE_NAME)]["removed"] = False
        mock_configDBConnector["ACL_RULE"]["{}|RULE2".format(ACL_TABLE_NAME)] = {}
        mock_configDBConnector["ACL_RULE"]["{}|RULE2".format(ACL_TABLE_NAME)]["removed"] = False

        mock_configDBConnector["ACL_TABLE"][ACL_TABLE_NAME] = {}

        result = runner.invoke(
            config.config.commands["acl"].commands["remove"].commands["table"],
            [ACL_TABLE_NAME])

        assert result.exit_code == 0
        assert mock_configDBConnector["ACL_RULE"]["DATA_ACL|RULE1"]["removed"] == False
        assert mock_configDBConnector["ACL_RULE"]["DATA_ACL|RULE2"]["removed"] == False
        assert mock_configDBConnector["ACL_RULE"]["{}|RULE1".format(ACL_TABLE_NAME)]["removed"] == True
        assert mock_configDBConnector["ACL_RULE"]["{}|RULE2".format(ACL_TABLE_NAME)]["removed"] == True