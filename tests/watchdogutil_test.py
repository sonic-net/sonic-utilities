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
