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

    # ---------- PREFIX NORMALIZATION ---------- #

    def test_config_aggregate_address_add_normalizes_host_bits(self):
        """Verify that non-canonical prefix (with host bits) is normalized to network form"""
        db = Db()
        runner = CliRunner()

        # 10.1.1.5/24 should be normalized to 10.1.1.0/24
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["10.1.1.5/24"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "10.1.1.0/24" in table
        assert "10.1.1.5/24" not in table

    def test_config_aggregate_address_add_normalizes_ipv6(self):
        """Verify that non-canonical IPv6 prefix is normalized"""
        db = Db()
        runner = CliRunner()

        # fc00:1::5/64 should be normalized to fc00:1::/64
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["fc00:1::5/64"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "fc00:1::/64" in table
        assert "fc00:1::5/64" not in table

    def test_config_aggregate_address_remove_with_normalized_prefix(self):
        """Verify add with host bits, then remove with canonical form succeeds"""
        db = Db()
        runner = CliRunner()

        # Add with host bits
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["10.2.3.4/16"],
            obj=db
        )
        assert result.exit_code == SUCCESS

        # Remove with canonical form
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["remove"],
            ["10.2.0.0/16"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "10.2.0.0/16" not in table

    def test_config_aggregate_address_duplicate_after_normalization(self):
        """Verify that adding the same network with different host bits is rejected as duplicate"""
        db = Db()
        runner = CliRunner()

        # Add 10.1.1.5/24 (normalized to 10.1.1.0/24)
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["10.1.1.5/24"],
            obj=db
        )
        assert result.exit_code == SUCCESS

        # Add 10.1.1.99/24 (also normalizes to 10.1.1.0/24) — should fail as duplicate
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["10.1.1.99/24"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code != SUCCESS

    # ---------- PREFIX LIST NAME VALIDATION ---------- #

    def test_config_aggregate_address_add_invalid_prefix_list_pattern(self):
        """Verify that prefix list names with invalid characters are rejected"""
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24",
             "--aggregate-address-prefix-list", "bad!name@#"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code != SUCCESS
        assert "invalid" in result.output.lower()

    def test_config_aggregate_address_add_invalid_contributing_prefix_list_pattern(self):
        """Verify that contributing prefix list names with invalid characters are rejected"""
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24",
             "--contributing-address-prefix-list", "has spaces"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code != SUCCESS
        assert "invalid" in result.output.lower()

    def test_config_aggregate_address_add_prefix_list_too_long(self):
        """Verify that prefix list names exceeding 128 characters are rejected"""
        db = Db()
        runner = CliRunner()

        long_name = "a" * 129
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24",
             "--aggregate-address-prefix-list", long_name],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code != SUCCESS
        assert "length" in result.output.lower()

    def test_config_aggregate_address_add_valid_prefix_list_names(self):
        """Verify that valid prefix list names with allowed characters are accepted"""
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24",
             "--aggregate-address-prefix-list", "AGG_ROUTE-v4",
             "--contributing-address-prefix-list", "CONTRIB_ROUTE-v4"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert "192.168.0.0/24" in table
        assert table["192.168.0.0/24"]["aggregate-address-prefix-list"] == "AGG_ROUTE-v4"
        assert table["192.168.0.0/24"]["contributing-address-prefix-list"] == "CONTRIB_ROUTE-v4"

    def test_config_aggregate_address_add_prefix_list_max_length(self):
        """Verify that prefix list name at exactly 128 characters is accepted"""
        db = Db()
        runner = CliRunner()

        max_name = "a" * 128
        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24",
             "--aggregate-address-prefix-list", max_name],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    def test_config_aggregate_address_add_empty_prefix_list(self):
        """Verify that empty prefix list name (default) is accepted"""
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["aggregate-address"].
            commands["add"],
            ["192.168.0.0/24"],
            obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS
        table = db.cfgdb.get_table("BGP_AGGREGATE_ADDRESS")
        assert table["192.168.0.0/24"]["aggregate-address-prefix-list"] == ""
        assert table["192.168.0.0/24"]["contributing-address-prefix-list"] == ""
