import builtins

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
        real_import = builtins.__import__

        def mock_import_impl(name, globals=None, locals=None, fromlist=(), level=0):
            """Mock the import of the sonic_platform module."""
            if level == 0 and name == "sonic_platform":
                raise ImportError("No module named 'sonic_platform'")
            return real_import(name, globals, locals, fromlist, level)

        mock_import = MagicMock(side_effect=mock_import_impl)
        with patch("builtins.__import__", mock_import):
            runner = CliRunner()
            result = runner.invoke(watchdogutil.watchdogutil, ["version"])
        assert result.exit_code != 0
        assert result.exception
        assert any(
            call_record[0] and call_record[0][0] == "sonic_platform"
            for call_record in mock_import.call_args_list
        ), "expected \"import sonic_platform\" to be called"

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(watchdogutil.watchdogutil.commands["version"],
                               [])
        assert result.exit_code == 0
        assert watchdogutil.VERSION in result.output
