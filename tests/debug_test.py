import click
import pytest
import importlib
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

class TestDebugFrr(object):
    @patch('subprocess.check_output', MagicMock(return_value='FRRouting'))
    def setup(self, check_output = None):
        print('SETUP')
        import debug.main as debug
        import undebug.main as undebug
        importlib.reload(debug)
        importlib.reload(undebug)

    # debug
    @patch('debug.main.run_command')
    def test_debug_bgp_allow_martians(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['allow-martians'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp allow-martians'])

    @patch('debug.main.run_command')
    def test_debug_bgp_as4(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp as4'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['as4'], ['segment'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp as4 segment'])

    @patch('debug.main.run_command')
    def test_debug_bgp_bestpath(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['bestpath'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp bestpath dummyprefix'])

    @patch('debug.main.run_command')
    def test_debug_bgp_keepalives(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp keepalives'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['keepalives'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp keepalives dummyprefix'])

    @patch('debug.main.run_command')
    def test_debug_bgp_neighbor_events(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['neighbor-events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp neighbor-events'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['neighbor-events'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp neighbor-events dummyprefix'])

    @patch('debug.main.run_command')
    def test_debug_bgp_nht(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['nht'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp nht'])

    @patch('debug.main.run_command')
    def test_debug_bgp_pbr(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['pbr'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp pbr'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['pbr'], ['error'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp pbr error'])

    @patch('debug.main.run_command')
    def test_debug_bgp_update_groups(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['update-groups'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp update-groups'])

    @patch('debug.main.run_command')
    def test_debug_bgp_updates(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'], ['prefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates prefix'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'], ['prefix', 'dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates prefix dummyprefix'])


    @patch('debug.main.run_command')
    def test_debug_bgp_zebra(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp zebra'])

        result = runner.invoke(debug.cli.commands['bgp'].commands['zebra'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp zebra prefix dummyprefix'])

    @patch('debug.main.run_command')
    def test_debug_zebra_dplane(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['dplane'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra dplane'])

        result = runner.invoke(debug.cli.commands['zebra'].commands['dplane'], ['detailed'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra dplane detailed'])

    @patch('debug.main.run_command')
    def test_debug_zebra_events(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra events'])

    @patch('debug.main.run_command')
    def test_debug_zebra_fpm(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra fpm'])

    @patch('debug.main.run_command')
    def test_debug_zebra_kernel(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra kernel'])

    @patch('debug.main.run_command')
    def test_debug_zebra_nht(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['nht'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra nht'])

    @patch('debug.main.run_command')
    def test_debug_zebra_packet(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra packet'])

    @patch('debug.main.run_command')
    def test_debug_zebra_rib(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra rib'])

        result = runner.invoke(debug.cli.commands['zebra'].commands['rib'], ['detailed'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra rib detailed'])

    @patch('debug.main.run_command')
    def test_debug_zebra_vxlan(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['vxlan'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra vxlan'])

    # undebug
    @patch('undebug.main.run_command')
    def test_undebug_bgp_allow_martians(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['allow-martians'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp allow-martians'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_as4(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp as4'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['as4'], ['segment'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp as4 segment'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_bestpath(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['bestpath'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp bestpath dummyprefix'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_keepalives(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp keepalives'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['keepalives'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp keepalives dummyprefix'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_neighbor_events(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['neighbor-events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp neighbor-events'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['neighbor-events'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp neighbor-events dummyprefix'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_nht(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['nht'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp nht'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_pbr(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['pbr'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp pbr'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['pbr'], ['error'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp pbr error'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_update_groups(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['update-groups'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp update-groups'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_updates(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'], ['prefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates prefix'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'], ['prefix', 'dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates prefix dummyprefix'])


    @patch('undebug.main.run_command')
    def test_undebug_bgp_zebra(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp zebra'])

        result = runner.invoke(undebug.cli.commands['bgp'].commands['zebra'], ['dummyprefix'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp zebra prefix dummyprefix'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_dplane(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['dplane'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra dplane'])

        result = runner.invoke(undebug.cli.commands['zebra'].commands['dplane'], ['detailed'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra dplane detailed'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_events(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra events'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_fpm(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra fpm'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_kernel(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra kernel'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_nht(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['nht'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra nht'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_packet(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra packet'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_rib(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra rib'])

        result = runner.invoke(undebug.cli.commands['zebra'].commands['rib'], ['detailed'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra rib detailed'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_vxlan(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['vxlan'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra vxlan'])

class TestDebugQuagga(object):
    @patch('subprocess.check_output', MagicMock(return_value='quagga'))
    def setup(self, check_output = None):
        print('SETUP')
        import debug.main as debug
        import undebug.main as undebug
        importlib.reload(debug)
        importlib.reload(undebug)

    # debug
    @patch('debug.main.run_command')
    def test_debug_bgp(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp'])

    @patch('debug.main.run_command')
    def test_debug_bgp_events(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp events'])

    @patch('debug.main.run_command')
    def test_debug_bgp_updates(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp updates'])

    @patch('debug.main.run_command')
    def test_debug_bgp_as4(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp as4'])

    @patch('debug.main.run_command')
    def test_debug_bgp_filters(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['filters'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp filters'])

    @patch('debug.main.run_command')
    def test_debug_bgp_fsm(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['fsm'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp fsm'])

    @patch('debug.main.run_command')
    def test_debug_bgp_keepalives(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp keepalives'])

    @patch('debug.main.run_command')
    def test_debug_bgp_zebra(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug bgp zebra'])

    @patch('debug.main.run_command')
    def test_debug_zebra_events(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra events'])

    @patch('debug.main.run_command')
    def test_debug_zebra_fpm(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra fpm'])

    @patch('debug.main.run_command')
    def test_debug_zebra_kernel(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra kernel'])

    @patch('debug.main.run_command')
    def test_debug_zebra_packet(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra packet'])

    @patch('debug.main.run_command')
    def test_debug_zebra_rib(self, run_command):
        import debug.main as debug
        runner = CliRunner()
        result = runner.invoke(debug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'debug zebra rib'])

    # undebug
    @patch('undebug.main.run_command')
    def test_undebug_bgp(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_events(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp events'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_updates(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['updates'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp updates'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_as4(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['as4'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp as4'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_filters(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['filters'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp filters'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_fsm(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['fsm'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp fsm'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_keepalives(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['keepalives'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp keepalives'])

    @patch('undebug.main.run_command')
    def test_undebug_bgp_zebra(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['bgp'].commands['zebra'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug bgp zebra'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_events(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['events'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra events'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_fpm(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['fpm'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra fpm'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_kernel(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['kernel'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra kernel'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_packet(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['packet'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra packet'])

    @patch('undebug.main.run_command')
    def test_undebug_zebra_rib(self, run_command):
        import undebug.main as undebug
        runner = CliRunner()
        result = runner.invoke(undebug.cli.commands['zebra'].commands['rib'])
        assert result.exit_code == 0

        run_command.assert_called_with(['sudo', 'vtysh', '-c', 'no debug zebra rib'])

