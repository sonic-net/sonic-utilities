#!/usr/bin/env python

import os
import logging
import show.main as show
import config.main as config

from .fine_grained_ecmp_input import assert_show_output
from utilities_common.db import Db
from click.testing import CliRunner
from .mock_tables import dbconnector

logger = logging.getLogger(__name__)
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "fine_grained_ecmp_input")

SUCCESS = 0
ERROR = 1

INVALID_VALUE = 'INVALID'


class TestFineGrainedEcmp:
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        dbconnector.dedicated_dbs['CONFIG_DB'] = None

    def verify_output(self, db, runner, cmd, output):
        result = runner.invoke(show.cli.commands[cmd], [], obj=db)

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == output

    # CONFIG FG-NHG

    def test_fg_nhg_add_delete(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'empty_config_db')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["add"],
            ["fg_grp_1", "--bucket-size", "60", "--match-mode", "prefix-based", "--max-next-hops", "6"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["add"],
            ["fg_grp_2", "--bucket-size", "30", "--match-mode", "nexthop-based"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "fg-nhg", assert_show_output.show_fg_nhg)

        # delete
        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["delete"],
            ["fg_grp_1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["delete"],
            ["fg_grp_2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "fg-nhg", assert_show_output.show_fg_nhg_empty)

    # CONFIG FG-NHG-PREFIX

    def test_fg_nhg_prefix_add_delete(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'empty_config_db')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["add"],
            ["fg_grp_1", "--bucket-size", "30", "--match-mode", "prefix-based", "--max-next-hops", "6"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg-prefix"].commands["add"],
            ["192.168.11.0/24", "--fg-nhg", "fg_grp_1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "fg-nhg-prefix", assert_show_output.show_fg_nhg_prefix)

        # delete
        result = runner.invoke(
            config.config.commands["fg-nhg-prefix"].commands["delete"],
            ["192.168.11.0/24"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["delete"],
            ["fg_grp_1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "fg-nhg-prefix", assert_show_output.show_fg_nhg_prefix_empty)

    # CONFIG FG-NHG-MEMBERS

    def test_fg_nhg_members_add_delete(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'empty_config_db')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["add"],
            ["fg_grp_1", "--bucket-size", "30", "--match-mode", "nexthop-based"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg-member"].commands["add"],
            ["10.10.20.1", "--fg-nhg", "fg_grp_1", "--bank", "0"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg-member"].commands["add"],
            ["10.10.20.2", "--fg-nhg", "fg_grp_1", "--bank", "1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "fg-nhg-member", assert_show_output.show_fg_nhg_members)

        # delete
        result = runner.invoke(
            config.config.commands["fg-nhg-member"].commands["delete"],
            ["10.10.20.1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg-member"].commands["delete"],
            ["10.10.20.2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["fg-nhg"].commands["delete"],
            ["fg_grp_1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "fg-nhg-member", assert_show_output.show_fg_nhg_members_empty)
