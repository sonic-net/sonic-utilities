from click.testing import CliRunner
from unittest.mock import patch

from utilities_common.db import Db


class TestWatchdogConfig:

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_enable(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["enable"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_table("WATCHDOG")["config"]["enabled"] == "true"
        run_command.assert_called_once_with(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_disable(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["disable"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_table("WATCHDOG")["config"]["enabled"] == "false"
        run_command.assert_called_once_with(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_identity(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["identity"], ["board"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_table("WATCHDOG")["config"]["identity"] == "board"
        run_command.assert_called_once_with(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_timeout(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["timeout"], ["45"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_table("WATCHDOG")["config"]["timeout"] == "45"
        run_command.assert_called_once_with(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_timeout_rejects_zero(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["timeout"], ["0"], obj=db)

        assert result.exit_code != 0
        assert db.cfgdb.get_table("WATCHDOG") == {}
        run_command.assert_not_called()
