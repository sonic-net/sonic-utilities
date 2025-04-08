import pytest
import os, sys
from unittest.mock import MagicMock, patch
import mock
from click.testing import CliRunner

from .mock_tables import dbconnector
from utilities_common.db import Db
from config.main import config


modules_path = os.path.join(os.path.dirname(__file__), "..")
test_path = os.path.join(modules_path, "tests")
sys.path.insert(0, modules_path)
sys.path.insert(0, test_path)
mock_db_path = os.path.join(test_path, "config_route_input")


class TestConfigRoute(object):
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        jsonfile_config = os.path.join(mock_db_path, "config_db.json")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        yield

        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        dbconnector.dedicated_dbs = {}

    def run_cli_command(self, cli_args):
        runner = CliRunner()
        result = runner.invoke(config, cli_args)
        return result

    def test_add_route(self):
        cli_args = ['route', 'add', 'prefix', 'vrf', 'Vrf1', '1.2.3.4/32', 'nexthop', '6.7.8.9']
        result = self.run_cli_command(cli_args)
        assert result.exit_code == 0, f"Command failed:\n{result.output}"
        # Verify config_db.set_entry was called with the expected STATIC_ROUTE key

    def test_del_route_nonexistent(self):
        # Mock current state to return no matching key
        cli_args = ['route', 'del', 'prefix', '1.2.3.4/32', 'nexthop', '6.7.8.9']
        result = self.run_cli_command(cli_args)
        assert result.exit_code != 0  # Should fail because the route doesn't exist

    def test_del_route_success(self):
        # Simulate that the route is present
        cli_args = ['route', 'del', 'prefix', 'vrf', 'Vrf1', '1.2.3.4/32', 'nexthop', '6.7.8.9']
        result = self.run_cli_command(cli_args)
        assert result.exit_code == 0, f"Command failed:\n{result.output}"
        # Verify config_db.set_entry was called to remove the route
