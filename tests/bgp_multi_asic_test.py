from unittest import mock
import show.main as show
import pytest
import logging
import importlib
import os
from click.testing import CliRunner
from unittest.mock import patch

from .mock_tables import dbconnector
from .bgp_input import assert_show_output

test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "bgp_input")
mock_config_path = os.path.join(input_path, "mock_config")

logger = logging.getLogger(__name__)

SUCCESS = 0


class TestBgpMultiAsic:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import mock_multi_asic

        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import mock_single_asic

        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()
        dbconnector.namespaces.clear()

    @pytest.mark.parametrize(
        "cfgdb,output",
        [
            pytest.param(
                {
                    "asic0": os.path.join(mock_config_path, "empty"),
                    "asic1": os.path.join(mock_config_path, "empty"),
                },
                {
                    "plain": assert_show_output.show_device_global_empty,
                    "json": assert_show_output.show_device_global_empty,
                },
                id="empty",
            ),
            pytest.param(
                {
                    "asic0": os.path.join(mock_config_path, "all_disabled"),
                    "asic1": os.path.join(mock_config_path, "all_disabled"),
                },
                {
                    "plain": assert_show_output.show_device_global_all_disabled_multi_asic,
                    "json": assert_show_output.show_device_global_all_disabled_multi_asic_json,
                },
                id="all-disabled",
            ),
            pytest.param(
                {
                    "asic0": os.path.join(mock_config_path, "all_enabled"),
                    "asic1": os.path.join(mock_config_path, "all_enabled"),
                },
                {
                    "plain": assert_show_output.show_device_global_all_enabled_multi_asic,
                    "json": assert_show_output.show_device_global_all_enabled_multi_asic_json,
                },
                id="all-enabled",
            ),
            pytest.param(
                {
                    "asic0": os.path.join(mock_config_path, "tsa_enabled"),
                    "asic1": os.path.join(mock_config_path, "tsa_enabled"),
                },
                {
                    "plain": assert_show_output.show_device_global_tsa_enabled_multi_asic,
                    "json": assert_show_output.show_device_global_tsa_enabled_multi_asic_json,
                },
                id="tsa-enabled",
            ),
            pytest.param(
                {
                    "asic0": os.path.join(mock_config_path, "wcmp_enabled"),
                    "asic1": os.path.join(mock_config_path, "wcmp_enabled"),
                },
                {
                    "plain": assert_show_output.show_device_global_wcmp_enabled_multi_asic,
                    "json": assert_show_output.show_device_global_wcmp_enabled_multi_asic_json,
                },
                id="w-ecmp-enabled",
            ),
            pytest.param(
                {
                    "asic0": os.path.join(mock_config_path, "tsa_enabled"),
                    "asic1": os.path.join(mock_config_path, "wcmp_enabled"),
                },
                {
                    "plain": assert_show_output.show_device_global_opposite_multi_asic,
                    "json": assert_show_output.show_device_global_opposie_multi_asic_json,
                },
                id="w-ecmp-enabled",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "format",
        [
            "plain",
            "json",
        ],
    )
    @patch(
        "show.bgp_cli.multi_asic.is_multi_asic",
        mock.Mock(return_value=True),
    )
    @patch(
        "show.bgp_cli.multi_asic.get_namespace_list",
        mock.Mock(return_value=["asic0", "asic1"]),
    )
    def test_show_device_global_multi_asic(self, cfgdb, output, format):
        for namespace in cfgdb.keys():
            dbconnector.namespaces[namespace] = {"CONFIG_DB": cfgdb[namespace]}
        runner = CliRunner()

        cmd_args = [] if format == "plain" else ["--json"]

        result = runner.invoke(
            show.cli.commands["bgp"].commands["device-global"],
            cmd_args,
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output[format]
        assert result.exit_code == SUCCESS
