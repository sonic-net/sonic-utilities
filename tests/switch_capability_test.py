import importlib
import json
import os
import sys

import click
import show.main as show
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_path)

SUCCESS = 0
ERROR2 = 2


class TestSwitchCapabilities:
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        from .mock_tables import dbconnector

        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(
            test_path, "mock_tables", "asic0", "state_db"
        )

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        from .mock_tables import dbconnector

        dbconnector.dedicated_dbs.pop("STATE_DB", None)

    def test_show_switch_capabilities(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["switch"],
            ["capabilities"],
            obj=Db(),
        )
        assert result.exit_code == SUCCESS
        assert "Capability" in result.output
        assert "ECMP_HASH_CAPABLE" in result.output
        assert "MIRROR" in result.output

    def test_show_switch_capabilities_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["switch"],
            ["capabilities", "--json"],
            obj=Db(),
        )
        assert result.exit_code == SUCCESS
        data = json.loads(result.output)
        assert data["ECMP_HASH_CAPABLE"] == "true"
        assert data["MIRROR"] == "true"


class TestSwitchCapabilitiesMultiAsic:
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

        import mock_tables.mock_multi_asic

        importlib.reload(mock_tables.mock_multi_asic)
        from mock_tables import dbconnector

        dbconnector.dedicated_dbs.pop("STATE_DB", None)
        dbconnector.load_namespace_config()

    @classmethod
    def teardown_class(cls):
        os.environ.pop("UTILITIES_UNIT_TESTING_TOPOLOGY", None)

    @patch.object(click.Choice, "convert", MagicMock(return_value="asic0"))
    def test_show_switch_capabilities_namespace(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["switch"],
            ["capabilities", "-n", "asic0"],
            obj=Db(),
        )
        assert result.exit_code == SUCCESS
        assert "ECMP_HASH_CAPABLE" in result.output

    def test_show_switch_capabilities_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["switch"],
            ["capabilities"],
            obj=Db(),
        )
        assert result.exit_code == SUCCESS
        assert "ECMP_HASH_CAPABLE" in result.output
        assert "Namespace asic1:" in result.output

    def test_show_switch_capabilities_all_namespaces_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["switch"],
            ["capabilities", "--json"],
            obj=Db(),
        )
        assert result.exit_code == SUCCESS
        data = json.loads(result.output)
        assert "asic0" in data
        assert "asic1" in data
        assert data["asic0"]["ECMP_HASH_CAPABLE"] == "true"
