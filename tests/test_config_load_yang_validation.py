import importlib
import os
import sys
import traceback
import click
import pytest
from unittest import mock
from click.testing import CliRunner
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

config_load_input_path = os.path.join(test_path, "config_load_input")
mock_db_path = os.path.join(test_path, "config_reload_input")

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]
    if isinstance(command, list):
        command = ' '.join(command)
    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') +
                   click.style(command, fg='green'))
    if kwargs.get('return_cmd'):
        return '', 0

class TestConfigLoadYangValidation(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        from tests.mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        import config.main
        importlib.reload(config.main)

    def test_config_load_calls_yang_validation(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        valid_file = os.path.join(config_load_input_path, "valid_config.json")
        with mock.patch("utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)), \
             mock.patch.object(config, "config_file_yang_validation", return_value=True) as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [valid_file, "-y"])
            print(result.output)
            if result.exception:
                traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            mock_validate.assert_called_once_with(valid_file)

    def test_config_load_blocked_on_yang_abort(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        valid_file = os.path.join(config_load_input_path, "valid_config.json")
        with mock.patch("utilities_common.cli.run_command") as mock_run, \
             mock.patch.object(config, "config_file_yang_validation", side_effect=click.Abort) as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [valid_file, "-y"])
            print(result.output)
            assert result.exit_code != 0
            mock_validate.assert_called_once_with(valid_file)
            mock_run.assert_not_called()

    def test_config_load_blocked_on_validation_false(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        valid_file = os.path.join(config_load_input_path, "valid_config.json")
        with mock.patch("utilities_common.cli.run_command") as mock_run, \
             mock.patch.object(config, "config_file_yang_validation", return_value=False) as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [valid_file, "-y"])
            print(result.output)
            assert "Invalid config file" in result.output
            mock_validate.assert_called_once_with(valid_file)
            mock_run.assert_not_called()

    def test_config_load_blocked_on_validation_exception(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        valid_file = os.path.join(config_load_input_path, "valid_config.json")
        with mock.patch("utilities_common.cli.run_command") as mock_run, \
             mock.patch.object(config, "config_file_yang_validation",
                side_effect=Exception("YANG model load failed")) as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [valid_file, "-y"])
            print(result.output)
            assert "Failed to validate config file" in result.output
            assert "YANG model load failed" in result.output
            mock_validate.assert_called_once_with(valid_file)
            mock_run.assert_not_called()

    def test_config_load_proceeds_after_validation_passes(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        valid_file = os.path.join(config_load_input_path, "valid_config.json")
        with mock.patch("utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run, \
             mock.patch.object(config, "config_file_yang_validation", return_value=True):
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [valid_file, "-y"])
            print(result.output)
            if result.exception:
                traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert '--write-to-db' in call_args
            assert valid_file in call_args

    def test_config_load_default_file_calls_validation(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        default_cfg = os.path.join(mock_db_path, "config_db.json")
        config.DEFAULT_CONFIG_DB_FILE = default_cfg
        with mock.patch("utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)), \
             mock.patch.object(config, "config_file_yang_validation", return_value=True) as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], ["-y"])
            print(result.output)
            if result.exception:
                traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            mock_validate.assert_called_once_with(default_cfg)

    def test_config_load_missing_file(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        missing_file = "/tmp/nonexistent_config_db_test_3502.json"
        with mock.patch("utilities_common.cli.run_command") as mock_run, \
             mock.patch.object(config, "config_file_yang_validation") as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [missing_file, "-y"])
            print(result.output)
            assert "doesn't exist" in result.output
            mock_validate.assert_not_called()
            mock_run.assert_not_called()

    def test_config_load_rejects_acl_rule_without_acl_table(self, get_cmd_module, setup_single_broadcom_asic):
        (config, show) = get_cmd_module
        bad_file = os.path.join(config_load_input_path, "invalid_acl_rule.json")
        with mock.patch("utilities_common.cli.run_command") as mock_run, \
             mock.patch.object(config, "config_file_yang_validation", side_effect=click.Abort) as mock_validate:
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load"], [bad_file, "-y"])
            print(result.output)
            assert result.exit_code != 0
            mock_validate.assert_called_once_with(bad_file)
            mock_run.assert_not_called()
