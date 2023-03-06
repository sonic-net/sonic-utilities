import click
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

class TestDebugQuagga(object):
    # debug
    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_events(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp events'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_updates(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_as4(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp as4'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_filters(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['filters'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp filters'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_fsm(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['fsm'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp fsm'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_keepalives(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp keepalives'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_bgp_zebra(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp zebra'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_zebra_events(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra events'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_zebra_fpm(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra fpm'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_zebra_kernel(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra kernel'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_zebra_packet(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra packet'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_debug_zebra_rib(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra rib'])

    # undebug
    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_events(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp events'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_updates(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_as4(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp as4'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_filters(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['filters'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp filters'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_fsm(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['fsm'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp fsm'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_keepalives(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp keepalives'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_bgp_zebra(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp zebra'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_zebra_events(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra events'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_zebra_fpm(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra fpm'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_zebra_kernel(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra kernel'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_zebra_packet(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra packet'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def test_undebug_zebra_rib(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra rib'])

