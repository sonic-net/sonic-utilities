import click
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

class TestDebugFrr(object):
    # debug
    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_allow_martians(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['allow-martians'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp allow-martians'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_as4(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp as4'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['as4'], ['segment'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp as4 segment'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_bestpath(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['bestpath'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp bestpath dummy_prefix'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_keepalives(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp keepalives'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['keepalives'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp keepalives dummy_prefix'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_neighbor_events(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['neighbor-events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp neighbor-events'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['neighbor-events'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp neighbor-events dummy_prefix'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_nht(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['nht'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp nht'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_pbr(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['pbr'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp pbr'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['pbr'], ['error'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp pbr error'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_update_groups(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['update-groups'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp update-groups'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_updates(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'], ['prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates prefix'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'], ['prefix', 'dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates prefix dummy_prefix'])


    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_bgp_zebra(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp zebra'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['zebra'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp zebra prefix dummy_prefix'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_dplane(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['dplane'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra dplane'])

        result = runner.invoke(debug.cli.commands['zebra'].commands['dplane'], ['detailed'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra dplane detailed'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_events(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra events'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_fpm(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra fpm'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_kernel(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra kernel'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_nht(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['nht'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra nht'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_packet(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra packet'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_rib(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra rib'])

        result = runner.invoke(debug.cli.commands['zebra'].commands['rib'], ['detailed'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra rib detailed'])

    @patch('debug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_debug_zebra_vxlan(self, mock_run_cmd):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['vxlan'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra vxlan'])

    # undebug
    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_allow_martians(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['allow-martians'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp allow-martians'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_as4(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp as4'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['as4'], ['segment'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp as4 segment'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_bestpath(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['bestpath'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp bestpath dummy_prefix'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_keepalives(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp keepalives'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['keepalives'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp keepalives dummy_prefix'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_neighbor_events(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['neighbor-events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp neighbor-events'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['neighbor-events'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp neighbor-events dummy_prefix'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_nht(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['nht'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp nht'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_pbr(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['pbr'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp pbr'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['pbr'], ['error'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp pbr error'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_update_groups(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['update-groups'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp update-groups'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_updates(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'], ['prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates prefix'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'], ['prefix', 'dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates prefix dummy_prefix'])


    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_bgp_zebra(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp zebra'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['zebra'], ['dummy_prefix'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp zebra prefix dummy_prefix'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_dplane(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['dplane'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra dplane'])

        result = runner.invoke(undebug.cli.commands['zebra'].commands['dplane'], ['detailed'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra dplane detailed'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_events(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra events'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_fpm(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra fpm'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_kernel(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra kernel'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_nht(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['nht'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra nht'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_packet(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra packet'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_rib(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra rib'])

        result = runner.invoke(undebug.cli.commands['zebra'].commands['rib'], ['detailed'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra rib detailed'])

    @patch('undebug.main.run_command')
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def test_undebug_zebra_vxlan(self, mock_run_cmd):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['vxlan'])
        assert result.exit_code == 0
        mock_run_cmd.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra vxlan'])

