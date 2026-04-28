from click.testing import CliRunner
import watchdogutil.main as watchdogutil
from unittest.mock import patch, MagicMock


class TestWatchdog(object):
    @patch('os.geteuid', MagicMock(return_value=1000))
    def test_non_root_fails(self):
        runner = CliRunner()
        result = runner.invoke(watchdogutil.watchdogutil, ["version"])
        assert result.exit_code != 0
        assert "Root privileges are required" in result.output

    @patch('os.geteuid', MagicMock(return_value=0))
    def test_import_fails(self):
        runner = CliRunner()
        result = runner.invoke(watchdogutil.watchdogutil, ["version"])
        assert result.exit_code != 0
        assert result.exception

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(watchdogutil.watchdogutil.commands["version"],
                               [])
        assert result.exit_code == 0
        assert watchdogutil.VERSION in result.output

    @patch('watchdogutil.main.platform_watchdog')
    def test_status_armed_with_remaining_time(self, mock_platform_watchdog):
        """Test status command when watchdog is armed and has remaining time"""
        mock_platform_watchdog.is_armed.return_value = True
        mock_platform_watchdog.get_remaining_time.return_value = 300

        runner = CliRunner()
        result = runner.invoke(watchdogutil.watchdogutil.commands["status"], [])

        assert result.exit_code == 0
        assert "Status: Armed" in result.output
        assert "Time remaining: 300 seconds" in result.output
