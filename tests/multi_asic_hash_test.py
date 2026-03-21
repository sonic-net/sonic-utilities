import pytest
import os
import sys
import logging
import importlib
from unittest.mock import patch, MagicMock

import click
import show.main as show
import config.main as config

from click.testing import CliRunner
from utilities_common.db import Db
from .hash_input import assert_show_output

test_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_path)


logger = logging.getLogger(__name__)

HASH_FIELD_LIST = [
    "DST_MAC",
    "SRC_MAC",
    "ETHERTYPE",
    "IP_PROTOCOL",
    "DST_IP",
    "SRC_IP",
    "L4_DST_PORT",
    "L4_SRC_PORT"
]

SUCCESS = 0
ERROR2 = 2


class TestHashMultiAsic:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

        import mock_tables.mock_multi_asic
        importlib.reload(mock_tables.mock_multi_asic)
        from mock_tables import dbconnector
        dbconnector.load_namespace_config()

        # Reload plugins to register switch-hash commands for multi-asic
        sonic_hash_show = importlib.import_module('show.plugins.sonic-hash')
        importlib.reload(sonic_hash_show)
        if sonic_hash_show.SWITCH_HASH.name in show.cli.commands:
            del show.cli.commands[sonic_hash_show.SWITCH_HASH.name]
        sonic_hash_show.register(show.cli)

        sonic_hash_config = importlib.import_module('config.plugins.sonic-hash')
        importlib.reload(sonic_hash_config)
        if sonic_hash_config.SWITCH_HASH.name in config.config.commands:
            del config.config.commands[sonic_hash_config.SWITCH_HASH.name]
        sonic_hash_config.register(config.config)

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

        from mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from mock_tables import dbconnector
        dbconnector.load_database_config()

        # Reload plugins back to single-asic
        sonic_hash_show = importlib.import_module('show.plugins.sonic-hash')
        importlib.reload(sonic_hash_show)
        if sonic_hash_show.SWITCH_HASH.name in show.cli.commands:
            del show.cli.commands[sonic_hash_show.SWITCH_HASH.name]
        sonic_hash_show.register(show.cli)

        sonic_hash_config = importlib.import_module('config.plugins.sonic-hash')
        importlib.reload(sonic_hash_config)
        if sonic_hash_config.SWITCH_HASH.name in config.config.commands:
            del config.config.commands[sonic_hash_config.SWITCH_HASH.name]
        sonic_hash_config.register(config.config)

    # CONFIG SWITCH-HASH GLOBAL (multi-asic)

    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash",
            "lag-hash"
        ]
    )
    def test_config_hash_multi_asic(self, hash):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"],
            ["-n", "asic0", hash] + HASH_FIELD_LIST, obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash-algorithm",
            "lag-hash-algorithm"
        ]
    )
    def test_config_hash_algorithm_multi_asic(self, hash):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"],
            ["-n", "asic0", hash, "CRC"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    # SHOW SWITCH-HASH GLOBAL (multi-asic)

    def test_show_hash_global_multi_asic_all_ns(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"],
            ["global"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == assert_show_output.show_hash_global_multi_asic
        assert result.exit_code == SUCCESS

    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_show_hash_global_multi_asic_single_ns(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"],
            ["-n", "asic0", "global"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == assert_show_output.show_hash_global_multi_asic_single_ns
        assert result.exit_code == SUCCESS

    # SHOW SWITCH-HASH CAPABILITIES (multi-asic)

    def test_show_hash_capabilities_multi_asic_all_ns(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"],
            ["capabilities"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == assert_show_output.show_hash_capabilities_multi_asic
        assert result.exit_code == SUCCESS

    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_show_hash_capabilities_multi_asic_single_ns(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"],
            ["-n", "asic0", "capabilities"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == assert_show_output.show_hash_capabilities_multi_asic_single_ns
        assert result.exit_code == SUCCESS
