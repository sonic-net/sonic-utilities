import json

from click.testing import CliRunner
from unittest.mock import call, patch

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
        assert run_command.call_args_list == [
            call(
                ["/usr/local/bin/watchdog-control.sh", "--validate", json.dumps({"enabled": "true"})],
                display_cmd=False,
            ),
            call(["/usr/local/bin/watchdog-control.sh"], display_cmd=False),
        ]

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
        assert run_command.call_count == 2
        assert json.loads(run_command.call_args_list[0].args[0][2])["identity"] == "board"
        assert run_command.call_args_list[-1] == call(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_timeout(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["timeout"], ["45"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_table("WATCHDOG")["config"]["timeout"] == "45"
        assert run_command.call_count == 2
        assert json.loads(run_command.call_args_list[0].args[0][2])["timeout"] == "45"
        assert run_command.call_args_list[-1] == call(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_timeout_rejects_zero(self, run_command, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["watchdog"].commands["timeout"], ["0"], obj=db)

        assert result.exit_code != 0
        assert db.cfgdb.get_table("WATCHDOG") == {}
        run_command.assert_not_called()

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_pretimeout(self, run_command, get_cmd_module):
        config, _ = get_cmd_module
        db = Db()
        result = CliRunner().invoke(config.config.commands["watchdog"], ["pretimeout", "120"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_entry("WATCHDOG", "config")["pretimeout"] == "120"
        candidate = json.loads(run_command.call_args_list[0].args[0][2])
        assert candidate["pretimeout"] == "120"
        assert run_command.call_args_list[-1] == call(["/usr/local/bin/watchdog-control.sh"], display_cmd=False)

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_disable_pretimeout(self, run_command, get_cmd_module):
        config, _ = get_cmd_module
        db = Db()
        db.cfgdb.set_entry("WATCHDOG", "config", {"timeout": "480", "pretimeout": "300"})
        result = CliRunner().invoke(config.config.commands["watchdog"], ["pretimeout", "0"], obj=db)

        assert result.exit_code == 0
        assert db.cfgdb.get_entry("WATCHDOG", "config") == {"timeout": "480", "pretimeout": "0"}

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_pretimeout_rejects_negative(self, run_command, get_cmd_module):
        config, _ = get_cmd_module
        db = Db()
        result = CliRunner().invoke(config.config.commands["watchdog"], ["pretimeout", "--", "-1"], obj=db)

        assert result.exit_code != 0
        assert db.cfgdb.get_table("WATCHDOG") == {}
        run_command.assert_not_called()

    @patch("config.watchdog.clicommon.run_command")
    def test_config_watchdog_updates_pair_together(self, run_command, get_cmd_module):
        config, _ = get_cmd_module
        db = Db()
        db.cfgdb.set_entry("WATCHDOG", "config", {"enabled": "true", "timeout": "600", "pretimeout": "300"})
        result = CliRunner().invoke(
            config.config.commands["watchdog"], ["timeout", "180", "--pretimeout", "60"], obj=db
        )

        assert result.exit_code == 0
        expected = {"enabled": "true", "timeout": "180", "pretimeout": "60"}
        assert db.cfgdb.get_entry("WATCHDOG", "config") == expected
        assert json.loads(run_command.call_args_list[0].args[0][2]) == expected
        assert run_command.call_count == 2

    @patch("config.watchdog.clicommon.run_command", side_effect=SystemExit(1))
    def test_config_watchdog_validation_failure_preserves_config(self, run_command, get_cmd_module):
        config, _ = get_cmd_module
        db = Db()
        previous = {"enabled": "true", "timeout": "600", "pretimeout": "300"}
        db.cfgdb.set_entry("WATCHDOG", "config", previous)
        result = CliRunner().invoke(config.config.commands["watchdog"], ["timeout", "180"], obj=db)

        assert result.exit_code != 0
        assert db.cfgdb.get_entry("WATCHDOG", "config") == previous
        assert run_command.call_count == 1

    @patch("config.watchdog.clicommon.run_command", side_effect=[None, SystemExit(1), None])
    def test_config_watchdog_apply_failure_restores_config(self, run_command, get_cmd_module):
        config, _ = get_cmd_module
        db = Db()
        previous = {"enabled": "true", "timeout": "600", "pretimeout": "300"}
        db.cfgdb.set_entry("WATCHDOG", "config", previous)
        result = CliRunner().invoke(config.config.commands["watchdog"], ["timeout", "480"], obj=db)

        assert result.exit_code != 0
        assert db.cfgdb.get_entry("WATCHDOG", "config") == previous
        assert run_command.call_args_list[-1] == call(
            ["/usr/local/bin/watchdog-control.sh"], display_cmd=False, ignore_error=True
        )
