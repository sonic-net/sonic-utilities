#!/usr/bin/env python

import pytest
import os
import logging
import show.main as show
import config.main as config
import clear.main as clear
import importlib

from .pbh_input import assert_show_output
from utilities_common.db import Db
from utilities_common.cli import UserCache
from click.testing import CliRunner
from .mock_tables import dbconnector
from .mock_tables import mock_single_asic

logger = logging.getLogger(__name__)
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "pbh_input")

SUCCESS = 0
ERROR = 1
ERROR2 = 2

INVALID_VALUE = 'INVALID'


class TestPBH:
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        logger.info("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        dbconnector.dedicated_dbs['CONFIG_DB'] = None
        dbconnector.dedicated_dbs['STATE_DB'] = None
        dbconnector.dedicated_dbs['COUNTERS_DB'] = None


    ########## CONFIG PBH HASH-FIELD ##########


    def test_config_pbh_hash_field_add_delete_no_ip_mask(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], ["inner_ip_proto", "--hash-field",
            "INNER_IP_PROTOCOL", "--sequence-id", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["delete"], ["inner_ip_proto"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    @pytest.mark.parametrize("hash_field_name,hash_field,ip_mask", [
        ("inner_dst_ipv6", "INNER_DST_IPV6", "ffff::"),
        ("inner_dst_ipv4", "INNER_DST_IPV4", "255.0.0.0")
        ])
    def test_config_pbh_hash_field_add_ip_mask(
        self,
        hash_field_name,
        hash_field,
        ip_mask,
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], [hash_field_name, "--hash-field",
            hash_field, "--ip-mask", ip_mask,
            "--sequence-id", "3"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS


    @pytest.mark.parametrize("hash_field_name,hash_field,ip_mask", [
        ("inner_ip_protocol", "INNER_IP_PROTOCOL", "255.0.0.0"),
        ("inner_src_ipv6", "INNER_SRC_IPV6", "255.0.0.0"),
        ("inner_src_ipv4", "INNER_SRC_IPV4", "ffff::")
        ])
    def test_config_pbh_hash_field_add_mismatch_hash_field_ip_mask(
        self,
        hash_field_name,
        hash_field,
        ip_mask,
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], [hash_field_name, "--hash-field",
            hash_field, "--ip-mask", ip_mask,
            "--sequence-id", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_hash_field_add_invalid_ip(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], ["inner_src_ipv4", "--hash-field",
            "INNER_SRC_IPV4", "--ip-mask", INVALID_VALUE,
            "--sequence-id", "2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    @pytest.mark.parametrize("hash_field_name,hash_field", [
        ("inner_src_ipv6", "INNER_SRC_IPV6"),
        ("inner_src_ipv4", "INNER_SRC_IPV4")
        ])
    def test_config_pbh_hash_field_add_none_ip_mask(
        self,
        hash_field_name,
        hash_field,
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], [hash_field_name, "--hash-field",
            hash_field, "--sequence-id", "2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    @pytest.mark.parametrize("hash_field_name,hash_field,updated_hash_field,sequence_id", [
        ("inner_ip_proto", "INNER_IP_PROTOCOL", "INNER_L4_DST_PORT", "1"),
        ("inner_l4_src_port", "INNER_L4_SRC_PORT", "INNER_L4_DST_PORT", "2")
        ])
    def test_config_pbh_hash_field_update_hash_field_sequence_id_no_ip(
        self,
        hash_field_name,
        hash_field,
        updated_hash_field,
        sequence_id
    ):
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"],[hash_field_name, "--hash-field",
            hash_field, "--sequence-id", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["update"],[hash_field_name, "--hash-field",
            updated_hash_field, "--sequence-id", sequence_id], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR


    @pytest.mark.parametrize("hash_field_name,hash_field,updated_hash_field,ip_mask,updated_ip_mask", [
        ("inner_dst_ipv4", "INNER_DST_IPV4", "INNER_SRC_IPV4", "255.0.0.0", "0.0.0.255"),
        ("inner_dst_ipv6", "INNER_DST_IPV6", "INNER_SRC_IPV6", "ffff::", "::ffff"),
        ])
    def test_config_pbh_hash_field_update_hash_field_ip_mask(
        self,
        hash_field_name,
        hash_field,
        updated_hash_field,
        ip_mask,
        updated_ip_mask
    ):
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], [hash_field_name, "--hash-field",
            hash_field, "--ip-mask", ip_mask,
            "--sequence-id", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["update"], [hash_field_name, "--hash-field",
            updated_hash_field, "--ip-mask", updated_ip_mask], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR


    def test_config_pbh_hash_field_update_invalid_hash_field(self):
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], ["inner_ip_proto", "--hash-field",
            "INNER_IP_PROTOCOL", "--sequence-id", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["update"], ["inner_ip_proto", "--hash-field",
            "INNER_DST_IPV4", "--sequence-id", "2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_hash_field_update_invalid_ipv4_mask(self):
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"],["inner_ip_proto", "--hash-field",
            "INNER_IP_PROTOCOL", "--sequence-id", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["update"], ["inner_ip_proto", "--ip-mask",
            "0.0.0.255"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    @pytest.mark.parametrize("hash_field_name,hash_field,ip_mask,updated_ip_mask", [
        ("inner_dst_ipv6", "INNER_DST_IPV6", "ffff::", "255.0.0.0"),
        ("inner_dst_ipv4", "INNER_DST_IPV4", "255.0.0.0", "ffff::")
        ])
    def test_config_pbh_hash_field_update_invalid_ip_mask(
        self,
        hash_field_name,
        hash_field,
        ip_mask,
        updated_ip_mask
    ):
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["add"], [hash_field_name, "--hash-field",
            hash_field, "--ip-mask", ip_mask, "--sequence-id",
            "3"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash-field"].
            commands["update"], [hash_field_name, "--ip-mask",
            updated_ip_mask], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    ########## CONFIG PBH HASH ##########


    def test_config_pbh_hash_add_delete_ipv4(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'hash_fields')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash"].
            commands["add"], ["inner_v4_hash", "--hash-field-list",
            "inner_ip_proto,inner_l4_dst_port,inner_l4_src_port,inner_dst_ipv4,inner_dst_ipv4"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash"].
            commands["delete"],["inner_v4_hash"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_hash_add_update_ipv6(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'hash_fields')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash"].
            commands["add"], ["inner_v6_hash", "--hash-field-list",
            "inner_ip_proto,inner_l4_dst_port,inner_l4_src_port,inner_dst_ipv6,inner_dst_ipv6"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash"].
            commands["update"], ["inner_v6_hash", "--hash-field-list",
            "inner_l4_dst_port,inner_l4_src_port,inner_dst_ipv6,inner_dst_ipv6"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize("hash_name,hash_field_list,exit_code", [
        ("inner_v6_hash", INVALID_VALUE, ERROR2),
        ("inner_v6_hash", "", ERROR2),
        ("inner_v6_hash", None, ERROR2)
        ])
    def test_config_pbh_hash_add_invalid_hash_field_list(
        self,
        hash_name,
        hash_field_list,
        exit_code
    ):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'hash_fields')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["hash"].
            commands["add"], [hash_name, "--hash-field-list",
            hash_field_list], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == exit_code


    ########## CONFIG PBH TABLE ##########


    def test_config_pbh_table_add_delete_ports(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'table')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["add"],["pbh_table1", "--interface-list",
            "Ethernet0,Ethernet4", "--description", "NVGRE"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["delete"], ["pbh_table1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_table_add_update_portchannels(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'table')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["add"], ["pbh_table2", "--interface-list",
            "PortChannel0001", "--description", "VxLAN"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["update"],["pbh_table2", "--interface-list",
            "PortChannel0002", "--description", "VxLAN TEST"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["update"],["pbh_table2", "--interface-list",
            "PortChannel0001"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["update"], ["pbh_table2", "--description",
            "TEST"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_table_add_port_and_portchannel(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'table')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["add"], ["pbh_table3", "--interface-list",
            "PortChannel0002,Ethernet8", "--description",
            "VxLAN adn NVGRE"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_table_add_invalid_port(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'table')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["add"], ["pbh_table3", "--interface-list",
            INVALID_VALUE, "--description", "VxLAN adn NVGRE"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_table_add_update_invalid_interface(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'table')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["add"], ["pbh_table2", "--interface-list",
            "PortChannel0001", "--description", "VxLAN"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["table"].
            commands["update"], ["pbh_table2", "--interface-list",
            INVALID_VALUE], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    ########## CONFIG PBH RULE ##########


    def test_config_pbh_rule_add_delete_nvgre(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"],["pbh_table1", "nvgre", "--priority",
            "1", "--gre-key", "0x2500/0xffffff00", "--inner-ether-type",
            "0x86dd", "--hash", "inner_v6_hash", "--packet-action",
            "SET_ECMP_HASH", "--flow-counter", "DISABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["delete"], ["pbh_table1", "nvgre"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_rule_add_update_vxlan(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan",
            "--priority", "2", "--ip-protocol", "0x11",
            "--inner-ether-type", "0x0800","--l4-dst-port",
            "0x12b5", "--hash", "inner_v4_hash", "--packet-action",
            "SET_LAG_HASH", "--flow-counter", "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["update"].commands["field"].
            commands["set"], ["pbh_table1", "vxlan",
            "--priority", "3", "--inner-ether-type", "0x086d",
            "--packet-action", "SET_LAG_HASH", "--flow-counter",
            "DISABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_rule_update_nvgre_to_vxlan(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"],["pbh_table1", "nvgre", "--priority", "1",
            "--ether-type", "0x0800", "--ip-protocol", "0x2f",
            "--gre-key", "0x2500/0xffffff00", "--inner-ether-type",
            "0x86dd", "--hash", "inner_v6_hash", "--packet-action",
            "SET_ECMP_HASH", "--flow-counter", "DISABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["update"].commands["field"].
            commands["set"], ["pbh_table1", "nvgre",
            "--ether-type", "0x86dd", "--ipv6-next-header", "0x11",
            "--l4-dst-port", "0x12b5", "--inner-ether-type", "0x0800",
            "--hash", "inner_v4_hash"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["update"].commands["field"].
            commands["del"], ["pbh_table1", "nvgre",
            "--ip-protocol", "--gre-key",
            "--packet-action", "--flow-counter"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS


    def test_config_pbh_rule_update_invalid(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan", "--priority",
            "2", "--ip-protocol", "0x11", "--inner-ether-type",
            "0x0800", "--l4-dst-port", "0x12b5", "--hash",
            "inner_v6_hash", "--packet-action", "SET_ECMP_HASH",
            "--flow-counter", "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["update"], ["pbh_table1", "vxlan",
            "--flow-counter", INVALID_VALUE], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_rule_add_invalid_ip_protocol(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan", "--priority",
            "2", "--ip-protocol", INVALID_VALUE, "--inner-ether-type",
            "0x0800", "--l4-dst-port", "0x12b5", "--hash", "inner_v6_hash",
            "--packet-action", "SET_ECMP_HASH", "--flow-counter",
            "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_rule_add_invalid_inner_ether_type(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan", "--priority",
            "2", "--ip-protocol", "0x11", "--inner-ether-type",
            INVALID_VALUE, "--l4-dst-port", "0x12b5", "--hash",
            "inner_v6_hash", "--packet-action", "SET_ECMP_HASH",
            "--flow-counter", "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_rule_add_invalid_hash(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan", "--priority",
            "2", "--ip-protocol", "0x11", "--inner-ether-type", "0x0800",
            "--l4-dst-port", "0x12b5", "--hash", INVALID_VALUE,
            "--packet-action", "SET_ECMP_HASH", "--flow-counter",
            "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_rule_add_invalid_packet_action(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan", "--priority",
            "2", "--ip-protocol", "0x11", "--inner-ether-type",
            "0x0800", "--l4-dst-port", "0x12b5", "--hash",
            "inner_v6_hash", "--packet-action", INVALID_VALUE,
            "--flow-counter", "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2


    def test_config_pbh_rule_add_invalid_flow_counter(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'rule')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table1", "vxlan", "--priority",
            "2", "--ip-protocol", "0x11", "--inner-ether-type",
            "0x0800", "--l4-dst-port", "0x12b5", "--hash",
            "inner_v6_hash", "--packet-action", "SET_ECMP_HASH",
            "--flow-counter", INVALID_VALUE], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2

    ########## SHOW PBH HASH-FIELD ##########

    def test_show_pbh_hash_field(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["hash-field"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_hash_fields


    ########## SHOW PBH HASH ##########


    def test_show_pbh_hash(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["hash"], [], obj=db
        )

        logger.debug("\n" + result.stdout)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_hash


    ########## SHOW PBH TABLE ##########


    def test_show_pbh_table(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["table"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_table


    ########## SHOW PBH RULE ##########


    def test_show_pbh_rule(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["rule"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_rule


    ########## SHOW PBH STATISTICS ##########


    def remove_pbh_counters_file(self):
        UserCache('pbh').remove_all()

    def test_show_pbh_statistics_on_empty_config(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = None
        dbconnector.dedicated_dbs['COUNTERS_DB'] = None

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_empty


    def test_show_pbh_statistics(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )
        
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics


    def test_show_pbh_statistics_after_clear(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            clear.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_zero

    def test_show_pbh_statistics_after_clear_and_counters_partial(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db_partial')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            clear.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_partial

    def test_show_pbh_statistics_after_clear_and_counters_updated(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            clear.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db_updated')

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_updated


    def test_show_pbh_statistics_after_disabling_rule(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            clear.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            config.config.commands["pbh"].
            commands["rule"].commands["update"].
            commands["field"].commands["set"],
            ["pbh_table2", "vxlan", "--flow-counter",
             "DISABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_after_disabling_rule


    def test_show_pbh_statistics_after_flow_counter_toggle(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            clear.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            config.config.commands["pbh"].
            commands["rule"].commands["update"].
            commands["field"].commands["set"],
            ["pbh_table1", "nvgre", "--flow-counter",
             "DISABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            config.config.commands["pbh"].
            commands["rule"].commands["update"].
            commands["field"].commands["set"],
            ["pbh_table1", "nvgre", "--flow-counter",
             "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_after_toggling_counter


    def test_show_pbh_statistics_after_rule_toggle(self):
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, 'counters_db')
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'full_pbh_config')

        self.remove_pbh_counters_file()

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            clear.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            config.config.commands["pbh"].
            commands["rule"].commands["delete"],
            ["pbh_table2", "vxlan"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            config.config.commands["pbh"].commands["rule"].
            commands["add"], ["pbh_table2", "vxlan", "--priority",
            "2", "--ip-protocol", "0x11", "--inner-ether-type",
            "0x0800", "--l4-dst-port", "0x12b5", "--hash",
            "inner_v4_hash", "--packet-action", "SET_LAG_HASH",
            "--flow-counter", "ENABLED"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show.cli.commands["pbh"].
            commands["statistics"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_pbh_statistics_after_toggling_rule
