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


class TestBgp:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs.clear()

    # ---------- CONFIG BGP ---------- #

    @pytest.mark.parametrize(
        "feature", [
            "tsa",
            "w-ecmp"
        ]
    )
    @pytest.mark.parametrize(
        "state", [
            "enabled",
            "disabled"
        ]
    )
    def test_config_device_global(self, feature, state):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["device-global"].
            commands[feature].commands[state], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    # ---------- SHOW BGP ---------- #

    @pytest.mark.parametrize(
        "cfgdb,output", [
            pytest.param(
                os.path.join(mock_config_path, "empty"),
                {
                    "plain": assert_show_output.show_device_global_empty,
                    "json": assert_show_output.show_device_global_empty
                },
                id="empty"
            ),
            pytest.param(
                os.path.join(mock_config_path, "all_disabled"),
                {
                    "plain": assert_show_output.show_device_global_all_disabled,
                    "json": assert_show_output.show_device_global_all_disabled_json
                },
                id="all-disabled"
            ),
            pytest.param(
                os.path.join(mock_config_path, "all_enabled"),
                {
                    "plain": assert_show_output.show_device_global_all_enabled,
                    "json": assert_show_output.show_device_global_all_enabled_json
                },
                id="all-enabled"
            ),
            pytest.param(
                os.path.join(mock_config_path, "tsa_enabled"),
                {
                    "plain": assert_show_output.show_device_global_tsa_enabled,
                    "json": assert_show_output.show_device_global_tsa_enabled_json
                },
                id="tsa-enabled"
            ),
            pytest.param(
                os.path.join(mock_config_path, "wcmp_enabled"),
                {
                    "plain": assert_show_output.show_device_global_wcmp_enabled,
                    "json": assert_show_output.show_device_global_wcmp_enabled_json
                },
                id="w-ecmp-enabled"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_device_global(self, cfgdb, output, format):
        dbconnector.dedicated_dbs["CONFIG_DB"] = cfgdb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["bgp"].commands["device-global"],
            [] if format == "plain" else ["--json"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output[format]
        assert result.exit_code == SUCCESS
