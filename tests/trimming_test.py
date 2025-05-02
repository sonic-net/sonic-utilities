import pytest
import os
import logging
import show.main as show
import config.main as config

from click.testing import CliRunner
from utilities_common.db import Db
from .mock_tables import dbconnector
from .trimming_input import assert_show_output


test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "trimming_input")
mock_config_path = os.path.join(input_path, "mock_config")
mock_state_path = os.path.join(input_path, "mock_state")

logger = logging.getLogger(__name__)


SUCCESS = 0
ERROR2 = 2


class TestTrimming:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "all")

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs.clear()

    # ---------- CONFIG CONFIG SWITCH-TRIMMING GLOBAL ---------- #

    @pytest.mark.parametrize(
        "size,dscp,queue", [
            pytest.param(
                "200", "20", "2",
                id="queue-static"
            ),
            pytest.param(
                "300", "30", "dynamic",
                id="queue-dynamic"
            )
        ]
    )
    def test_config_trimming(self, size, dscp, queue):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-trimming"].commands["global"],
            ["--size", size, "--dscp", dscp, "--queue", queue], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize(
        "statedb,option,pattern", [
            pytest.param(
                os.path.join(mock_state_path, "all"),
                ["--size", "-1"],
                "is not in the valid range of",
                id="size-out-of-bound"
            ),
            pytest.param(
                os.path.join(mock_state_path, "all"),
                ["--dscp", "-1"],
                "is not in the valid range of",
                id="dscp-out-of-bound"
            ),
            pytest.param(
                os.path.join(mock_state_path, "all"),
                ["--queue", "-1"],
                "is not in the valid range of",
                id="queue-out-of-bound"
            ),
            pytest.param(
                os.path.join(mock_state_path, "queue_static"),
                ["--queue", "dynamic"],
                "dynamic queue resolution mode is not supported",
                id="queue-static-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "queue_dynamic"),
                ["--queue", "2"],
                "static queue resolution mode is not supported",
                id="queue-dynamic-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "no_capabilities"),
                ["--queue", "dynamic"],
                "no queue resolution mode capabilities",
                id="no-capabilities"
            ),
            pytest.param(
                os.path.join(mock_state_path, "not_supported"),
                ["--queue", "2"],
                "operation is not supported",
                id="not-supported"
            )
        ]
    )
    def test_config_trimming_neg(self, statedb, option, pattern):
        dbconnector.dedicated_dbs["STATE_DB"] = statedb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-trimming"].commands["global"],
            option, obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert pattern in result.output
        assert result.exit_code == ERROR2

    # ---------- SHOW SWITCH-TRIMMING GLOBAL ---------- #

    @pytest.mark.parametrize(
        "cfgdb,output", [
            pytest.param(
                os.path.join(mock_config_path, "empty"),
                {
                    "plain": assert_show_output.show_trim_empty,
                    "json": assert_show_output.show_trim_empty
                },
                id="empty"
            ),
            pytest.param(
                os.path.join(mock_config_path, "partial"),
                {
                    "plain": assert_show_output.show_trim_partial,
                    "json": assert_show_output.show_trim_partial_json
                },
                id="partial"
            ),
            pytest.param(
                os.path.join(mock_config_path, "queue_static"),
                {
                    "plain": assert_show_output.show_trim_queue_static,
                    "json": assert_show_output.show_trim_queue_static_json
                },
                id="queue-static"
            ),
            pytest.param(
                os.path.join(mock_config_path, "queue_dynamic"),
                {
                    "plain": assert_show_output.show_trim_queue_dynamic,
                    "json": assert_show_output.show_trim_queue_dynamic_json
                },
                id="queue-dynamic"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_trimming(self, cfgdb, output, format):
        dbconnector.dedicated_dbs["CONFIG_DB"] = cfgdb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-trimming"].commands["global"],
            [] if format == "plain" else ["--json"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output[format]
        assert result.exit_code == SUCCESS
