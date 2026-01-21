#!/usr/bin/env python

import os
import logging
import show.main as show
import config.main as config

from .dhcpv4_relay_input import assert_show_output
from utilities_common.db import Db
from click.testing import CliRunner
from .mock_tables import dbconnector

logger = logging.getLogger(__name__)
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "dhcpv4_relay_input")

SUCCESS = 0
ERROR = 1
ERROR2 = 2
INVALID_VALUE = 'INVALID'

class TestDhcpv4Relay:

    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        dbconnector.dedicated_dbs['CONFIG_DB'] = None

    def verify_output(self, output):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dhcpv4-relay"], [])

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        if result.output != output:
            print (f"Expected output:\n",output)
            print (f"Actual output:\n", result.output)
            assert False
        assert result.output == output

    def test_dhcpv4_relay_add_delete(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'empty_config_db')
        db = Db()
        runner = CliRunner()

        # Add DHCPv4 relay with mandatory parameters
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["add"],
            ["Vlan11", "--dhcpv4-servers", "192.168.11.12"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        self.verify_output(assert_show_output.show_dhcpv4_relay_add)

        # Add DHCPv4 relay for the same VLAN again
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["add"],
            ["Vlan11", "--dhcpv4-servers", "192.168.11.12"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # try to add a DHCPv4 relay with missing mandatory parameters
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["add"],
            ["Vlan12"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR2

        # try to add a DHCPv4 relay with invalid ipv4 address
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["add"],
            ["Vlan11", "--dhcpv4-servers", "192.168.11.256"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # try to add a DHCPv4 relay with ipv6 address
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["add"],
            ["Vlan11", "--dhcpv4-servers", "2001:db8::1"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # update server IP for the existing Vlan11 configuration
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["update"],
            ["Vlan11", "--dhcpv4-servers", "192.168.11.13"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        self.verify_output(db, runner, assert_show_output.show_dhcpv4_relay_update)

        # update the DHCPv4 relay configuration with a valid max_hop_count
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["update"],
            ["Vlan11", "--max-hop-count", "5"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        self.verify_output(db, runner, "dhcpv4-relay", assert_show_output.show_dhcpv4_relay_update_max_hop_count)

        # update the DHCPv4 relay configuration with an invalid max_hop_count
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["update"],
            ["Vlan11", "--max-hop-count", "abrakadabra"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # update the DHCPv4 relay configuration with a out of range valid max_hop_count
        result = runner.invoke(
            config.config.commands["dhcpv4-relay"].commands["update"],
            ["Vlan11", "--max-hop-count", "32"], obj=Db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR
