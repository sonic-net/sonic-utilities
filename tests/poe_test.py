#!/usr/bin/env python

import pytest
import os
import logging
import show.main as show
import config.main as config

from .poe_input import assert_show_output as valid_output
from utilities_common.db import Db
from click.testing import CliRunner
from .mock_tables import dbconnector

logger = logging.getLogger(__name__)
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "poe_input")

SUCCESS = 0
ERROR = 1
ERROR2 = 2

INVALID_VALUE = 'INVALID'
ETHERNET_0 = 'Ethernet0'
POE = 'poe'
PSE = 'pse'
INTERFACE = 'interface'
STATUS = 'status'
PRIORITY = 'priority'
POWER_LIMIT = 'power-limit'
config_db = 'config_db'
CONFIG_DB = 'CONFIG_DB'
state_db = 'state_db'
STATE_DB = 'STATE_DB'


class TestPOE:
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        logger.info("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        dbconnector.dedicated_dbs[CONFIG_DB] = None
        dbconnector.dedicated_dbs[STATE_DB] = None

    @pytest.mark.parametrize("command,value,output", [
        (STATUS, "enable", valid_output.show_poe_interface_configuration),
        (STATUS, "disable", valid_output.show_poe_interface_configuration_ethernet0_disable),
        (POWER_LIMIT, "200", valid_output.show_poe_interface_configuration_ethernet0_power_limit_200),
        (PRIORITY, "low", valid_output.show_poe_interface_configuration_ethernet0_priority_low),
        (PRIORITY, "high", valid_output.show_poe_interface_configuration_ethernet0_priority_high),
        (PRIORITY, "crit", valid_output.show_poe_interface_configuration_ethernet0_priority_crit),
        ])
    def test_config_and_show_poe_interface_success(self, command, value, output):
        dbconnector.dedicated_dbs[CONFIG_DB] = os.path.join(mock_db_path, config_db)
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands[POE].commands[INTERFACE].
            commands[command], [ETHERNET_0, value], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

        result = runner.invoke(
            show.cli.commands[POE].commands[INTERFACE].
            commands['configuration'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == output

    @pytest.mark.parametrize("intf,command,value,exit_code", [
        (INVALID_VALUE, STATUS, "enable", ERROR),
        (ETHERNET_0, STATUS, INVALID_VALUE, ERROR2),
        (ETHERNET_0, POWER_LIMIT, INVALID_VALUE, ERROR2),
        (ETHERNET_0, PRIORITY, INVALID_VALUE, ERROR2),
        ])
    def test_config_poe_interface_error(self, intf, command, value, exit_code):
        dbconnector.dedicated_dbs[CONFIG_DB] = os.path.join(mock_db_path, config_db)
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands[POE].commands[INTERFACE].
            commands[command], [intf, value], obj=db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == exit_code

    def test_show_poe_interface_status(self):
        dbconnector.dedicated_dbs[STATE_DB] = os.path.join(mock_db_path, state_db)
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands[POE].commands[INTERFACE].
            commands[STATUS], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == valid_output.show_poe_interface_status

    def test_show_poe_pse_status(self):
        dbconnector.dedicated_dbs[STATE_DB] = os.path.join(mock_db_path, state_db)
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands[POE].commands[PSE].
            commands[STATUS], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == valid_output.show_poe_pse_status

    def test_show_poe_status(self):
        dbconnector.dedicated_dbs[STATE_DB] = os.path.join(mock_db_path, state_db)
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands[POE].commands[STATUS], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == valid_output.show_poe_status
