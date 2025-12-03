#!/usr/bin/env python

import os
import logging
import show.main as show
import config.main as config

from .nvgre_tunnel_input import assert_show_output
from utilities_common.db import Db
from click.testing import CliRunner
from .mock_tables import dbconnector

logger = logging.getLogger(__name__)
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "nvgre_tunnel_input")

SUCCESS = 0
ERROR = 1

INVALID_VALUE = 'INVALID'


class TestNvgreTunnel:
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"


    @classmethod
    def teardown_class(cls):
        logger.info("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        dbconnector.dedicated_dbs['CONFIG_DB'] = None


    def verify_output(self, db, runner, cmd, output):
        result = runner.invoke(show.cli.commands[cmd], [], obj=db)

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == output


    ######### NVGRE-TUNNEL #########


    def test_nvgre_tunnel_add_del(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'empty_config_db')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["add"],
            ["tunnel_1", "--src-ip", "10.0.0.1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "nvgre-tunnel", assert_show_output.show_nvgre_tunnel)
        
        # delete
        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["delete"],
            ["tunnel_1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "nvgre-tunnel", assert_show_output.show_nvgre_tunnel_empty)

    
    def test_nvgre_tunnels_add_del(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'empty_config_db')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["add"],
            ["tunnel_1", "--src-ip", "10.0.0.1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["add"],
            ["tunnel_2", "--src-ip", "10.0.0.2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "nvgre-tunnel", assert_show_output.show_nvgre_tunnels)
        
        # delete
        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["delete"],
            ["tunnel_1"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["delete"],
            ["tunnel_2"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "nvgre-tunnel", assert_show_output.show_nvgre_tunnel_empty)


    def test_nvgre_tunnel_add_invalid(self):
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["nvgre-tunnel"].commands["add"],
            ["tunnel_1", "--src-ip", INVALID_VALUE], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # verify
        self.verify_output(db, runner, "nvgre-tunnel", assert_show_output.show_nvgre_tunnel_empty)


    ######### NVGRE-TUNNEL-MAP #########
        

    def test_nvgre_tunnel_maps_add_del(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'nvgre_tunnel')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["nvgre-tunnel-map"].commands["add"],
            ["tunnel_1", "Vlan1000", "--vlan-id", "1000", "--vsid", "5000"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["nvgre-tunnel-map"].commands["add"],
            ["tunnel_1", "Vlan2000", "--vlan-id", "2000", "--vsid", "6000"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "nvgre-tunnel-map", assert_show_output.show_nvgre_tunnel_maps)

        # delete
        result = runner.invoke(
            config.config.commands["nvgre-tunnel-map"].commands["delete"],
            ["tunnel_1", "Vlan1000"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            config.config.commands["nvgre-tunnel-map"].commands["delete"],
            ["tunnel_1", "Vlan2000"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        # verify
        self.verify_output(db, runner, "nvgre-tunnel-map", assert_show_output.show_nvgre_tunnel_map_empty)


    def test_nvgre_tunnel_map_add_invalid_vlan(self):
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["nvgre-tunnel-map"].commands["add"],
            ["tunnel_1", "Vlan5000", "--vlan-id", "5000", "--vsid", "5000"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # verify
        self.verify_output(db, runner, "nvgre-tunnel-map", assert_show_output.show_nvgre_tunnel_map_empty)


    def test_nvgre_tunnel_map_add_invalid_vsid(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'nvgre_tunnel')
        db = Db()
        runner = CliRunner()

        # add
        result = runner.invoke(
            config.config.commands["nvgre-tunnel-map"].commands["add"],
            ["tunnel_1", "Vlan1000", "--vlan-id", "1000", "--vsid", "999999999"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR

        # verify
        self.verify_output(db, runner, "nvgre-tunnel-map", assert_show_output.show_nvgre_tunnel_map_empty)

