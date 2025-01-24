import importlib
import unittest

from click.testing import CliRunner
from utilities_common.db import Db
from config.kdump import kdump_remote, add_kdump_item, remove_kdump_item
from unittest.mock import patch


class TestKdump(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_config_kdump_disable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["kdump"].commands["disable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table.
        db.cfgdb.delete_table("KDUMP")

        result = runner.invoke(config.config.commands["kdump"].commands["disable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    def test_config_kdump_enable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["kdump"].commands["enable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table.
        db.cfgdb.delete_table("KDUMP")

        result = runner.invoke(config.config.commands["kdump"].commands["enable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    def test_config_kdump_memory(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["kdump"].commands["memory"], ["256MB"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table.
        db.cfgdb.delete_table("KDUMP")

        result = runner.invoke(config.config.commands["kdump"].commands["memory"], ["256MB"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    def test_config_kdump_num_dumps(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["kdump"].commands["num_dumps"], ["10"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table.
        db.cfgdb.delete_table("KDUMP")

        result = runner.invoke(config.config.commands["kdump"].commands["num_dumps"], ["10"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1


class TestKdumpUtilities(unittest.TestCase):

    @patch('config.kdump.db')
    @patch('config.kdump.Path.read_text')
    @patch('config.kdump.Path.write_text')
    def test_kdump_remote_enable_already_enabled(self, mock_write_text, mock_read_text, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "true"}}
        runner = CliRunner()
        result = runner.invoke(kdump_remote, ['enable'], obj=mock_db)
        self.assertIn("Error: Kdump Remote Mode is already enabled.", result.output)
        mock_write_text.assert_not_called()

    @patch('config.kdump.db')
    @patch('config.kdump.Path.read_text')
    @patch('config.kdump.Path.write_text')
    def test_kdump_remote_disable_already_disabled(self, mock_write_text, mock_read_text, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "false"}}
        runner = CliRunner()
        result = runner.invoke(kdump_remote, ['disable'], obj=mock_db)
        self.assertIn("Error: Kdump Remote Mode is already disabled.", result.output)
        mock_write_text.assert_not_called()

    @patch('config.kdump.db')
    @patch('config.kdump.Path.read_text')
    @patch('config.kdump.Path.write_text')
    @patch('config.kdump.echo_reboot_warning')
    def test_kdump_remote_enable_success(self, mock_echo_reboot_warning, mock_write_text, mock_read_text, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "false"}}
        mock_read_text.return_value = '#SSH="test"\n#SSH_KEY="test_key"\n'
        runner = CliRunner()
        result = runner.invoke(kdump_remote, ['enable'], obj=mock_db)
        self.assertIn("Kdump Remote Mode Enabled", result.output)
        mock_write_text.assert_called_once()
        mock_echo_reboot_warning.assert_called_once()

    @patch('config.kdump.db')
    @patch('config.kdump.Path.read_text')
    @patch('config.kdump.Path.write_text')
    @patch('config.kdump.echo_reboot_warning')
    def test_kdump_remote_disable_success(self, mock_echo_reboot_warning, mock_write_text, mock_read_text, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "true"}}
        mock_read_text.return_value = 'SSH="test"\nSSH_KEY="test_key"\n'
        runner = CliRunner()
        result = runner.invoke(kdump_remote, ['disable'], obj=mock_db)
        self.assertIn("Kdump Remote Mode Disabled.", result.output)
        mock_write_text.assert_called_once()
        mock_echo_reboot_warning.assert_called_once()

    @patch('config.kdump.db')
    def test_add_kdump_item_remote_not_enabled(self, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "false"}}
        runner = CliRunner()
        result = runner.invoke(add_kdump_item, ['ssh_string', 'test_value'], obj=mock_db)
        self.assertIn("Error: Enable remote mode first.", result.output)

    @patch('config.kdump.db')
    @patch('config.kdump.Path.read_text')
    @patch('config.kdump.Path.write_text')
    @patch('config.kdump.echo_reboot_warning')
    def test_add_kdump_item_success(self, mock_echo_reboot_warning, mock_write_text, mock_read_text, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "true", "ssh_string": "", "ssh_path": ""}}
        mock_read_text.return_value = 'SSH=""\nSSH_KEY=""\n'
        runner = CliRunner()
        result = runner.invoke(add_kdump_item, ['ssh_string', 'test_value'], obj=mock_db)
        self.assertIn("Updated kdump configurations.", result.output)
        mock_write_text.assert_called_once()
        mock_echo_reboot_warning.assert_called_once()

    @patch('config.kdump.db')
    def test_remove_kdump_item_not_configured(self, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"ssh_string": ""}}
        runner = CliRunner()
        result = runner.invoke(remove_kdump_item, ['ssh_string'], obj=mock_db)
        self.assertIn("Error: ssh_string is not configured.", result.output)

    @patch('config.kdump.db')
    def test_remove_kdump_item_remote_not_enabled(self, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "false", "ssh_string": "test_value"}}
        runner = CliRunner()
        result = runner.invoke(remove_kdump_item, ['ssh_string'], obj=mock_db)
        self.assertIn("Error: Remote mode is not enabled.", result.output)

    @patch('config.kdump.db')
    @patch('config.kdump.Path.read_text')
    @patch('config.kdump.Path.write_text')
    @patch('config.kdump.echo_reboot_warning')
    def test_remove_kdump_item_success(self, mock_echo_reboot_warning, mock_write_text, mock_read_text, mock_db):
        mock_db.cfgdb.get_table.return_value = {"config": {"remote": "true", "ssh_string": "test_value"}}
        mock_read_text.return_value = 'SSH="test_value"\nSSH_KEY=""\n'
        runner = CliRunner()
        result = runner.invoke(remove_kdump_item, ['ssh_string'], obj=mock_db)
        self.assertIn("ssh_string removed successfully.", result.output)
        mock_write_text.assert_called_once()
        mock_echo_reboot_warning.assert_called_once()


    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
