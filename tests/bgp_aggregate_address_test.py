import pytest
import os
import logging
import show.main as show
import config.main as config

from click.testing import CliRunner
from utilities_common.db import Db
from .mock_tables import dbconnector
from .bgp_input import assert_show_output


test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "bgp_input")
mock_config_path = os.path.join(input_path, "mock_config")

logger = logging.getLogger(__name__)


SUCCESS = 0


class TestBgpAggregateAddress:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs.clear()

    # ---------- CONFIG BGP AGGREGATE-ADDRESS ADD ---------- #

    def test_config_aggregate_address_add(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24", "--bbr-required", "--summary-only"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        # Verify entry in config DB
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "192.168.0.0/24" in table
        assert table["192.168.0.0/24"]["bbr-required"] == "true"
        assert table["192.168.0.0/24"]["summary-only"] == "true"
        assert table["192.168.0.0/24"]["as-set"] == "false"

    def test_config_aggregate_address_add_with_prefix_lists(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["fc00:1::/64", "--bbr-required",
             "--aggregate-address-prefix-list", "AGG_ROUTE_V6",
             "--contributing-address-prefix-list", "CONTRIBUTING_ROUTE_V6"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "fc00:1::/64" in table
        assert table["fc00:1::/64"]["bbr-required"] == "true"
        assert table["fc00:1::/64"]["aggregate-address-prefix-list"] == "AGG_ROUTE_V6"
        assert table["fc00:1::/64"]["contributing-address-prefix-list"] == "CONTRIBUTING_ROUTE_V6"

    def test_config_aggregate_address_add_all_options(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["10.0.0.0/8", "--bbr-required", "--summary-only", "--as-set"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "10.0.0.0/8" in table
        assert table["10.0.0.0/8"]["bbr-required"] == "true"
        assert table["10.0.0.0/8"]["summary-only"] == "true"
        assert table["10.0.0.0/8"]["as-set"] == "true"

    def test_config_aggregate_address_add_no_options(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["172.16.0.0/16"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "172.16.0.0/16" in table
        assert table["172.16.0.0/16"]["bbr-required"] == "false"
        assert table["172.16.0.0/16"]["summary-only"] == "false"
        assert table["172.16.0.0/16"]["as-set"] == "false"
        assert table["172.16.0.0/16"]["aggregate-address-prefix-list"] == ""
        assert table["172.16.0.0/16"]["contributing-address-prefix-list"] == ""

    def test_config_aggregate_address_add_invalid_prefix(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["invalid_prefix"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code != SUCCESS

    def test_config_aggregate_address_add_duplicate(self):
        db = Db()
        runner = CliRunner()

        # Add first time
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.1.0/24"],
            obj=db
        )
        assert result.exit_code == SUCCESS

        # Add same address again
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.1.0/24"],
            obj=db
        )
        assert result.exit_code != SUCCESS

    # ---------- CONFIG BGP AGGREGATE-ADDRESS REMOVE ---------- #

    def test_config_aggregate_address_remove(self):
        db = Db()
        runner = CliRunner()

        # Add first
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.2.0/24"],
            obj=db
        )
        assert result.exit_code == SUCCESS

        # Remove
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["remove"],
            ["192.168.2.0/24"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "192.168.2.0/24" not in table

    def test_config_aggregate_address_remove_nonexistent(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["remove"],
            ["192.168.99.0/24"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code != SUCCESS

    # ---------- SHOW IP BGP AGGREGATE-ADDRESS ---------- #

    def test_show_ip_bgp_aggregate_address(self, setup_bgp_commands):
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(
            mock_config_path, "aggregate_address")

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["aggregate-address"],
            [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_aggregate_address_ipv4

    def test_show_ipv6_bgp_aggregate_address(self, setup_bgp_commands):
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(
            mock_config_path, "aggregate_address")

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["ipv6"].commands["bgp"].commands["aggregate-address"],
            [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_aggregate_address_ipv6

    def test_show_ip_bgp_aggregate_address_empty(self, setup_bgp_commands):
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(
            mock_config_path, "aggregate_address_empty")

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["aggregate-address"],
            [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        assert result.output == assert_show_output.show_aggregate_address_empty
