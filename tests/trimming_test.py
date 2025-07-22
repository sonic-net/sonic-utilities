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
        "size,dscp,tc,queue", [
            pytest.param(
                "200", "20", None, "2",
                id="dscp-symmetric"
            ),
            pytest.param(
                "200", "from-tc", "2", "2",
                id="dscp-asymmetric"
            ),
            pytest.param(
                "200", "20", None, "2",
                id="queue-static"
            ),
            pytest.param(
                "200", "20", None, "dynamic",
                id="queue-dynamic"
            )
        ]
    )
    def test_config_trimming(self, size, dscp, tc, queue):
        db = Db()
        runner = CliRunner()

        args = ["--size", size, "--dscp", dscp, "--queue", queue]
        if tc is not None:
            args.extend(["--tc", tc])

        result = runner.invoke(
            config.config.commands["switch-trimming"].commands["global"],
            args, obj=db
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
                ["--tc", "-1"],
                "is not in the valid range of",
                id="tc-out-of-bound"
            ),
            pytest.param(
                os.path.join(mock_state_path, "all"),
                ["--queue", "-1"],
                "is not in the valid range of",
                id="queue-out-of-bound"
            ),
            pytest.param(
                os.path.join(mock_state_path, "dscp_symmetric"),
                ["--dscp", "from-tc"],
                "asymmetric dscp resolution mode is not supported",
                id="dscp-symmetric-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "dscp_asymmetric"),
                ["--dscp", "20"],
                "symmetric dscp resolution mode is not supported",
                id="dscp-asymmetric-only"
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
                ["--dscp", "from-tc"],
                "no dscp resolution mode capabilities",
                id="no-dscp-capabilities"
            ),
            pytest.param(
                os.path.join(mock_state_path, "no_capabilities"),
                ["--queue", "dynamic"],
                "no queue resolution mode capabilities",
                id="no-queue-capabilities"
            ),
            pytest.param(
                os.path.join(mock_state_path, "not_supported"),
                ["--size", "200"],
                "operation is not supported",
                id="not-supported"
            ),
            pytest.param(
                os.path.join(mock_state_path, "not_supported"),
                [],
                "no options are provided",
                id="no-options"
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
        "statedb,pattern", [
            pytest.param(
                os.path.join(mock_state_path, "dscp_asymmetric"),
                "-d, --dscp from-tc",
                id="dscp-asymmetric-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "dscp_symmetric"),
                "-d, --dscp INTEGER",
                id="dscp-symmetric-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "all"),
                "-d, --dscp [INTEGER|from-tc]",
                id="dscp-asymmetric-and-symmetric"
            ),
            pytest.param(
                os.path.join(mock_state_path, "queue_dynamic"),
                "-q, --queue dynamic",
                id="queue-dynamic-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "queue_static"),
                "-q, --queue INTEGER",
                id="queue-static-only"
            ),
            pytest.param(
                os.path.join(mock_state_path, "all"),
                "-q, --queue [INTEGER|dynamic]",
                id="queue-dynamic-and-static"
            )
        ]
    )
    def test_show_trimming_meta(self, statedb, pattern):
        dbconnector.dedicated_dbs["STATE_DB"] = statedb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-trimming"].commands["global"],
            ["--help"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert pattern in result.output
        assert result.exit_code == SUCCESS

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
                os.path.join(mock_config_path, "dscp_asymmetric"),
                {
                    "plain": assert_show_output.show_trim_dscp_asymmetric,
                    "json": assert_show_output.show_trim_dscp_asymmetric_json
                },
                id="dscp-asymmetric"
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
