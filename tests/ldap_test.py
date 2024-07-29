#!/usr/bin/env python

import os
import logging
import show.main as show
import config.main as config

from .ldap_input import assert_show_output
from utilities_common.db import Db
from click.testing import CliRunner
from .mock_tables import dbconnector

logger = logging.getLogger(__name__)
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "ldap_input")

SUCCESS = 0
ERROR = 1
INVALID_VALUE = 'INVALID'
EXP_GOOD_FLOW = 1
EXP_BAD_FLOW = 0


class TestLdap:
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

    def verify_ldap_global_output(self, db, runner, output, expected=EXP_GOOD_FLOW):
        result = runner.invoke(show.cli.commands["ldap"].commands["global"], [], obj=db)
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        logger.info("\n" + result.output)
        logger.info(result.exit_code)

        if expected:  # good flow expected (default)
            assert result.exit_code == SUCCESS
            assert result.output == output
        else:  # bad flow expected
            assert result.exit_code == ERROR

    def verify_ldap_server_output(self, db, runner, output, expected=EXP_GOOD_FLOW):
        result = runner.invoke(show.cli.commands["ldap-server"], [], obj=db)
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        logger.info("\n" + result.output)
        logger.info(result.exit_code)

        if expected:  # good flow expected (default)
            assert result.exit_code == SUCCESS
            assert result.output == output
        else:  # bad flow expected
            assert result.exit_code == ERROR

    def ldap_global_set_policy(self, runner, db, attr, value, expected=EXP_GOOD_FLOW):
        result = runner.invoke(
            config.config.commands["ldap"].commands["global"].commands[attr],
            [value], obj=db
        )
        if expected:  # good flow expected (default)
            logger.debug("\n" + result.output)
            logger.debug(result.exit_code)
            assert result.exit_code == SUCCESS
        else:  # bad flow expected
            assert result.exit_code == ERROR

    def ldap_server_set_policy(self, runner, db, value, expected=EXP_GOOD_FLOW):
        result = runner.invoke(
            config.config.commands["ldap-server"].commands["add"],
            value, obj=db
        )

        if expected:  # good flow expected (default)
            logger.debug("\n" + result.output)
            logger.debug(result.exit_code)
            assert result.exit_code == SUCCESS
        else:  # bad flow expected
            assert result.exit_code == ERROR

    def ldap_server_del_policy(self, runner, db, value, expected=EXP_GOOD_FLOW):
        result = runner.invoke(
            config.config.commands["ldap-server"].commands["delete"],
            value, obj=db
        )
        if expected:  # good flow expected (default)
            logger.debug("\n" + result.output)
            logger.debug(result.exit_code)
            assert result.exit_code == SUCCESS
        else:  # bad flow expected
            assert result.exit_code == ERROR

    # LDAP

    def test_ldap_global_feature_enabled(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'default_config_db.json')
        db = Db()
        runner = CliRunner()

        self.ldap_global_set_policy(runner, db, "base-dn", "dc=test1,dc=test2")
        self.ldap_global_set_policy(runner, db, "bind-dn", "cn=ldapadm,dc=test1,dc=test2")
        self.ldap_global_set_policy(runner, db, "bind-password", "password")
        self.ldap_global_set_policy(runner, db, "bind-timeout", "3")
        self.ldap_global_set_policy(runner, db, "port", "389")
        self.ldap_global_set_policy(runner, db, "timeout", "2")
        self.ldap_global_set_policy(runner, db, "version", "3")

        self.verify_ldap_global_output(db, runner, assert_show_output.show_ldap_global)

    def test_ldap_server(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'server_config_db.json')
        db = Db()
        runner = CliRunner()

        self.ldap_server_set_policy(runner, db, ["10.0.0.1", "--priority", "1"])
        self.verify_ldap_server_output(db, runner, assert_show_output.show_ldap_server)

        self.ldap_server_del_policy(runner, db, ["10.0.0.1"])
        self.verify_ldap_server_output(db, runner, assert_show_output.show_ldap_server_deleted)
