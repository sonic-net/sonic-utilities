import os
import sys
import click
import pytest
import importlib
import subprocess
import show.main as show
import utilities_common.bgp_util as bgp_util
from unittest import mock
from click.testing import CliRunner
from utilities_common import constants
from unittest.mock import call, MagicMock, patch, mock_open

EXPECTED_BASE_COMMAND = 'sudo '
EXPECTED_BASE_COMMAND_LIST = ['sudo']

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

expected_nat_config_output = \
"""
Global Values
Static Entries
Pool Entries
NAT Bindings
NAT Zones
"""


class TestShowRunAllCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())

    def mock_run_bgp_command():
        return ""

    def test_show_runningconfiguration_all_json_loads_failure(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "", 0
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code != 0

    def test_show_runningconfiguration_all_get_cmd_ouput_failure(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "{}", 2
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code != 0

    def test_show_runningconfiguration_all(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "{}", 0
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code == 0
        assert mock_get_cmd_output.call_count == 1
        assert mock_get_cmd_output.call_args_list == [
            call(['sonic-cfggen', '-d', '--print-data'])]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        bgp_util.run_bgp_command = cls._old_run_bgp_command
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"


class TestShowRunAllCommandsMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def mock_run_bgp_command():
        return ""

    def test_show_runningconfiguration_all_masic(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "{}", 0
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code == 0
        assert mock_get_cmd_output.call_count == 3
        assert mock_get_cmd_output.call_args_list == [
            call(['sonic-cfggen', '-d', '--print-data']),
            call(['sonic-cfggen', '-d', '--print-data', '-n', 'asic0']),
            call(['sonic-cfggen', '-d', '--print-data', '-n', 'asic1'])]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        bgp_util.run_bgp_command = cls._old_run_bgp_command
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


@patch('show.main.run_command')
@pytest.mark.parametrize(
        "cli_arguments0,expected0",
        [
            ([], 'cat /var/log/syslog'),
            (['xcvrd'], "cat /var/log/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log/syslog | tail -10'),
        ]
)
@pytest.mark.parametrize(
        "cli_arguments1,expected1",
        [
            (['-f'], ['tail', '-F', '/var/log/syslog']),
        ]
)
def test_show_logging_default(run_command, cli_arguments0, expected0, cli_arguments1, expected1):
    runner = CliRunner()
    runner.invoke(show.cli.commands["logging"], cli_arguments0)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected0, display_cmd=False, shell=True)
    runner.invoke(show.cli.commands["logging"], cli_arguments1)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND_LIST + expected1, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.isfile', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments0,expected0",
        [
            ([], 'cat /var/log/syslog.1 /var/log/syslog'),
            (['xcvrd'], "cat /var/log/syslog.1 /var/log/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log/syslog.1 /var/log/syslog | tail -10'),
        ]
)
@pytest.mark.parametrize(
        "cli_arguments1,expected1",
        [
            (['-f'], ['tail', '-F', '/var/log/syslog']),
        ]
)
def test_show_logging_syslog_1(run_command, cli_arguments0, expected0, cli_arguments1, expected1):
    runner = CliRunner()
    runner.invoke(show.cli.commands["logging"], cli_arguments0)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected0, display_cmd=False, shell=True)
    runner.invoke(show.cli.commands["logging"], cli_arguments1)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND_LIST + expected1, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.exists', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments0,expected0",
        [
            ([], 'cat /var/log.tmpfs/syslog'),
            (['xcvrd'], "cat /var/log.tmpfs/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log.tmpfs/syslog | tail -10'),
        ]
)
@pytest.mark.parametrize(
        "cli_arguments1,expected1",
        [
            (['-f'], ['tail', '-F', '/var/log.tmpfs/syslog']),
        ]
)
def test_show_logging_tmpfs(run_command, cli_arguments0, expected0, cli_arguments1, expected1):
    runner = CliRunner()
    runner.invoke(show.cli.commands["logging"], cli_arguments0)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected0, display_cmd=False, shell=True)
    runner.invoke(show.cli.commands["logging"], cli_arguments1)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND_LIST + expected1, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.isfile', MagicMock(return_value=True))
@patch('os.path.exists', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments0,expected0",
        [
            ([], 'cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog'),
            (['xcvrd'], "cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog | tail -10'),
        ]
)
@pytest.mark.parametrize(
        "cli_arguments1,expected1",
        [
            (['-f'], ['tail', '-F', '/var/log.tmpfs/syslog']),
        ]
)
def test_show_logging_tmpfs_syslog_1(run_command, cli_arguments0, expected0, cli_arguments1, expected1):
    runner = CliRunner()
    runner.invoke(show.cli.commands["logging"], cli_arguments0)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected0, display_cmd=False, shell=True)
    runner.invoke(show.cli.commands["logging"], cli_arguments1)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND_LIST + expected1, display_cmd=False)

def side_effect_subprocess_popen(*args, **kwargs):
    mock = MagicMock()
    if ' '.join(args[0]) == "uptime":
        mock.stdout.read.return_value = "05:58:07 up 25 days"
    elif ' '.join(args[0]).startswith("sudo docker images"):
        mock.stdout.read.return_value = "REPOSITORY   TAG"
    return mock

@patch('sonic_py_common.device_info.get_sonic_version_info', MagicMock(return_value={
        "build_version": "release-1.1-7d94c0c28",
        "sonic_os_version": "11",
        "debian_version": "11.6",
        "kernel_version": "5.10",
        "commit_id": "7d94c0c28",
        "build_date": "Wed Feb 15 06:17:08 UTC 2023",
        "built_by": "AzDevOps"}))
@patch('sonic_py_common.device_info.get_platform_info', MagicMock(return_value={
        "platform": "x86_64-kvm_x86_64-r0",
        "hwsku": "Force10-S6000",
        "asic_type": "vs",
        "asic_count": 1}))
@patch('sonic_py_common.device_info.get_chassis_info', MagicMock(return_value={
        "serial": "N/A",
        "model": "N/A",
        "revision": "N/A"}))
@patch('subprocess.Popen', MagicMock(side_effect=side_effect_subprocess_popen))
def test_show_version():
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["version"])
    assert "SONiC OS Version: 11" in result.output

class TestShowAcl(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_rule(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['acl'].commands['rule'], ['SNMP_ACL', 'RULE_1', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['acl-loader', 'show', 'rule', 'SNMP_ACL', 'RULE_1'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_table(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['acl'].commands['table'], ['EVERFLOW', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['acl-loader', 'show', 'table', 'EVERFLOW'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowChassis(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_system_ports(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['chassis'].commands['system-ports'], ['Linecard1|asic0|Ethernet0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['voqutil', '-c', 'system_ports', '-i', 'Linecard1|asic0|Ethernet0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_system_neighbors(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['chassis'].commands['system-neighbors'], ['10.0.0.0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['voqutil', '-c', 'system_neighbors', '-a', '10.0.0.0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_system_lags(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['chassis'].commands['system-lags'], ['-l', 'Linecard6' , '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['voqutil', '-c', 'system_lags', '-n', 'asic0', '-l', 'Linecard6'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowFabric(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_port(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['fabric'].commands['counters'].commands['port'], ['-n', 'asic0', '-e'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(["fabricstat", '-n', 'asic0', '-e'])

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_queue(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['fabric'].commands['counters'].commands['queue'], ['-n', 'asic0'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(["fabricstat", '-q', '-n', 'asic0'])

    def teardown(self):
        print('TEAR DOWN')


class TestShowFlowCounters(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_flowcnt_trap_stats(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['flowcnt-trap'].commands['stats'], ['-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['flow_counters_stat', '-t', 'trap', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_flowcnt_route_stats(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['flowcnt-route'].commands['stats'], ['-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['flow_counters_stat', '-t', 'route', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_flowcnt_route_stats_pattern(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['flowcnt-route'].commands['stats'].commands['pattern'], ['2001::/64', '--vrf', 'Vrf_1', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['flow_counters_stat', '-t', 'route', '--prefix_pattern', '2001::/64', '--vrf', 'Vrf_1', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_flowcnt_route_stats_route(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['flowcnt-route'].commands['stats'].commands['route'], ['2001::/64', '--vrf', 'Vrf_1', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['flow_counters_stat', '-t', 'route', '--prefix', '2001::/64', '--vrf', 'Vrf_1', '-n', 'asic0'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowInterfaces(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_description(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['description'], ['Ethernet0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['intfutil', '-c', 'description', '-i', 'Ethernet0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_status(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['status'], ['Ethernet0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['intfutil', '-c', 'status', '-i', 'Ethernet0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_tpid(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['tpid'], ['Ethernet0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['intfutil', '-c', 'tpid', '-i', 'Ethernet0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_transceiver_lpmode(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['transceiver'].commands['lpmode'], ['Ethernet0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'sfputil', 'show', 'lpmode', '-p', 'Ethernet0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_transceiver_error_status(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['transceiver'].commands['error-status'], ['Ethernet0', '-hw', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'sfputil', 'show', 'error-status', '-p', 'Ethernet0', '-hw', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_counters(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['counters'], ['-i', 'Ethernet0', '-p', '3', '-a', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['portstat', '-a', '-p', '3', '-i', 'Ethernet0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_counters_error(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['counters'].commands['errors'], ['-p', '3', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['portstat', '-e', '-p', '3', '-s', 'all'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_counters_rates(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['counters'].commands['rates'], ['-p', '3', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['portstat', '-R', '-p', '3', '-s', 'all'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_counters_detailed(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['counters'].commands['detailed'], ['Ethernet0', '-p', '3', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['portstat', '-l', '-p', '3', '-i', 'Ethernet0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_autoneg_status(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['autoneg'].commands['status'], ['Ethernet0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['intfutil', '-c', 'autoneg', '-i', 'Ethernet0', '-n', 'asic0'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    @patch.object(click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_link_training_status(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['interfaces'].commands['link-training'].commands['status'], ['Ethernet0', '-n', 'asic0', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['intfutil', '-c', 'link_training', '-i', 'Ethernet0', '-n', 'asic0'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowIp(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_ip_interfaces(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ip'].commands['interfaces'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'ipintutil', '-a', 'ipv4', '-d', 'all'])

    @patch('utilities_common.cli.run_command')
    def test_ipv6_interfaces(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ipv6'].commands['interfaces'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'ipintutil', '-a', 'ipv6', '-d', 'all'])

    def teardown(self):
        print('TEAR DOWN')


class TestShowVxlan(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_counters(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['vxlan'].commands['counters'], ['-p', '3', 'tunnel1', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['tunnelstat', '-T', 'vxlan', '-p', '3', '-i', 'tunnel1'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowNat(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_statistics(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['statistics'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natshow', '-s'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_translations(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['translations'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natshow', '-t'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_translations_count(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['translations'].commands['count'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natshow', '-c'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_config(self, mock_run_command):
        expected_calls = [
            call(['sudo', 'natconfig', '-g'], display_cmd=True),
            call(['sudo', 'natconfig', '-s'], display_cmd=True),
            call(['sudo', 'natconfig', '-p'], display_cmd=True),
            call(['sudo', 'natconfig', '-b'], display_cmd=True),
            call(['sudo', 'natconfig', '-z'], display_cmd=True),
        ]

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['config'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == expected_nat_config_output
        assert mock_run_command.call_args_list == expected_calls

    @patch('utilities_common.cli.run_command')
    def test_config_static(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['config'].commands['static'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natconfig', '-s'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_config_pool(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['config'].commands['pool'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natconfig', '-p'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_config_bindings(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['config'].commands['bindings'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natconfig', '-b'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_config_globalvalues(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['config'].commands['globalvalues'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natconfig', '-g'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_config_zones(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['nat'].commands['config'].commands['zones'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'natconfig', '-z'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowProcesses(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_summary(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['processes'].commands['summary'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['ps', '-eo', 'pid,ppid,cmd,%mem,%cpu'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_cpu(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['processes'].commands['cpu'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['top', '-bn', '1', '-o', '%CPU'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_memory(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['processes'].commands['memory'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['top', '-bn', '1', '-o', '%MEM'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')


class TestShowPlatform(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_syseeprom(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['platform'].commands['syseeprom'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'decode-syseeprom', '-d'], display_cmd=True)

    @mock.patch('sonic_py_common.device_info.get_platform_json_data')
    @patch('utilities_common.cli.run_command')
    def test_ssdhealth(self, mock_run_command, mock_plat_json):
        mock_plat_json.return_value = {
            "chassis": {
                 "name": "mock_platform"
            }
        }
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['platform'].commands['ssdhealth'], ['--verbose', '--vendor'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'ssdutil', '-v', '-e'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_pcieinfo(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['platform'].commands['pcieinfo'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'pcieutil', 'show'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_pcieinfo_check(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['platform'].commands['pcieinfo'], ['--verbose', '-c'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'pcieutil', 'check'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_temporature(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['platform'].commands['temperature'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['tempershow'])

    @patch('subprocess.check_call')
    def test_firmware(self, mock_check_call):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['platform'].commands['firmware'])
        assert result.exit_code == 0
        mock_check_call.assert_called_with(["sudo", "fwutil", "show"])

    def teardown(self):
        print('TEAR DOWN')

class TestShowQuagga(object):
    def setup(self):
        print('SETUP')

    @patch('show.main.run_command')
    @patch('show.main.get_routing_stack', MagicMock(return_value='quagga'))
    def test_show_ip_bgp(self, mock_run_command):
        from show.bgp_quagga_v4 import bgp
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["ip"].commands['bgp'].commands['summary'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', "show ip bgp summary"], return_cmd=True)

        result = runner.invoke(show.cli.commands["ip"].commands['bgp'].commands['neighbors'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', "show ip bgp neighbor"])

        result = runner.invoke(show.cli.commands["ip"].commands['bgp'].commands['neighbors'], ['0.0.0.0', 'routes'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', "show ip bgp neighbor 0.0.0.0 routes"])

    @patch('show.main.run_command')
    @patch('show.main.get_routing_stack', MagicMock(return_value='quagga'))
    def test_show_ipv6_bgp(self, mock_run_command):
        from show.bgp_quagga_v6 import bgp
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["ipv6"].commands['bgp'].commands['summary'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', "show ipv6 bgp summary"], return_cmd=True)

        result = runner.invoke(show.cli.commands["ipv6"].commands['bgp'].commands['neighbors'], ['0.0.0.0', 'routes'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', "show ipv6 bgp neighbor 0.0.0.0 routes"])

    def teardown(self):
        print('TEAR DOWN')


class TestShow(object):
    def setup(self):
        print('SETUP')

    @patch('show.main.run_command')
    def test_show_arp(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["arp"], ['0.0.0.0', '-if', 'Ethernet0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['nbrshow', '-4', '-ip', '0.0.0.0', '-if', 'Ethernet0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ndp(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ndp"], ['0.0.0.0', '-if', 'Ethernet0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['nbrshow', '-6', '-ip', '0.0.0.0', '-if', 'Ethernet0'], display_cmd=True)

    @patch('show.main.run_command')
    @patch('show.main.is_mgmt_vrf_enabled', MagicMock(return_value=True))
    def test_show_mgmt_vrf_routes(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["mgmt-vrf"], ['routes'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['ip', 'route', 'show', 'table', '5000'])

    @patch('show.main.run_command')
    @patch('show.main.is_mgmt_vrf_enabled', MagicMock(return_value=True))
    def test_show_mgmt_vrf(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["mgmt-vrf"])
        assert result.exit_code == 0
        assert mock_run_command.call_args_list == [
            call(['ip', '-d', 'link', 'show', 'mgmt']),
            call(['ip', 'link', 'show', 'vrf', 'mgmt'])
        ]

    @patch('show.main.run_command')
    def test_show_pfc_priority(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["pfc"].commands['priority'], ['Ethernet0'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['pfc', 'show', 'priority', 'Ethernet0'])

    @patch('show.main.run_command')
    def test_show_pfc_asymmetric(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["pfc"].commands['asymmetric'], ['Ethernet0'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['pfc', 'show', 'asymmetric', 'Ethernet0'])

    @patch('show.main.run_command')
    def test_show_pfcwd_config(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["pfcwd"].commands['config'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['pfcwd', 'show', 'config', '-d', 'all'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_pfcwd_stats(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["pfcwd"].commands['stats'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['pfcwd', 'show', 'stats', '-d', 'all'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_watermark_telemetry_interval(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["watermark"].commands['telemetry'].commands['interval'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['watermarkcfg', '--show-interval'])

    @patch('show.main.run_command')
    def test_show_route_map(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["route-map"], ['BGP', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', 'show route-map BGP'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ip_prefix_list(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ip'].commands["prefix-list"], ['0.0.0.0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', 'show ip prefix-list 0.0.0.0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ip_protocol(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ip'].commands["protocol"], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', 'show ip protocol'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ip_fib(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ip'].commands["fib"], ['0.0.0.0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['fibshow', '-4', '-ip', '0.0.0.0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ipv6_prefix_list(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ipv6'].commands["prefix-list"], ['0.0.0.0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', 'show ipv6 prefix-list 0.0.0.0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ipv6_protocol(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ipv6'].commands["protocol"], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', constants.RVTYSH_COMMAND, '-c', 'show ipv6 protocol'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_ipv6_fib(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ipv6'].commands["fib"], ['0.0.0.0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['fibshow', '-6', '-ip', '0.0.0.0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_lldp_neighbors(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['lldp'].commands["neighbors"], ['Ethernet0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'lldpshow', '-d', '-p' ,'Ethernet0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_lldp_table(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['lldp'].commands["table"], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'lldpshow'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_environment(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['environment'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'sensors'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_users(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['users'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['who'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_runningconfiguration_acl(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['runningconfiguration'].commands['acl'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sonic-cfggen', '-d', '--var-json', 'ACL_RULE'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_runningconfiguration_ports(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['runningconfiguration'].commands['ports'], ['Ethernet0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sonic-cfggen', '-d', '--var-json', 'PORT', '--key', 'Ethernet0'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_runningconfiguration_interfaces(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['runningconfiguration'].commands['interfaces'], ['Ethernet0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sonic-cfggen', '-d', '--var-json', 'INTERFACE', '--key', 'Ethernet0'], display_cmd=True)

    @patch('show.main.run_command')
    @patch('show.main.getstatusoutput_noshell_pipe', MagicMock(return_value=(0, 'quagga')))
    def test_show_startupconfiguration_bgp_quagga(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['startupconfiguration'].commands['bgp'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'docker', 'exec', 'bgp', 'cat', '/etc/quagga/bgpd.conf'], display_cmd=True)

    @patch('show.main.run_command')
    @patch('show.main.getstatusoutput_noshell_pipe', MagicMock(return_value=(0, 'frr')))
    def test_show_startupconfiguration_bgp_frr(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['startupconfiguration'].commands['bgp'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'docker', 'exec', 'bgp', 'cat', '/etc/frr/bgpd.conf'], display_cmd=True)

    @patch('show.main.run_command')
    @patch('show.main.getstatusoutput_noshell_pipe', MagicMock(return_value=(0, 'gobgp')))
    def test_show_startupconfiguration_bgp_gobgp(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['startupconfiguration'].commands['bgp'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'docker', 'exec', 'bgp', 'cat', '/etc/gpbgp/bgpd.conf'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_uptime(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['uptime'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['uptime', '-p'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_clock(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['clock'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['date'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_timezone(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands['clock'].commands['timezones'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(
            ['timedatectl', 'list-timezones'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_system_memory(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['system-memory'], ['--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['free', '-m'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_mirror_session(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['mirror_session'], ['SPAN', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['acl-loader', 'show', 'session', 'SPAN'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_policer(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['policer'], ['policer0', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['acl-loader', 'show', 'policer', 'policer0'], display_cmd=True)

    @patch('subprocess.Popen')
    def test_show_boot(self, mock_subprocess_popen):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['boot'])
        assert result.exit_code == 0
        mock_subprocess_popen.assert_called_with(["sudo", "sonic-installer", "list"], stdout=subprocess.PIPE, text=True)

    @patch('show.main.run_command')
    def test_show_mmu(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['mmu'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['mmuconfig', '-l'])

    @patch('show.main.run_command')
    def test_show_lines(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['line'], ['--brief', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['consutil', 'show', '-b'], display_cmd=True)

    @patch('show.main.run_command')
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_show_ztp(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ztp'], ['status', '--verbose'])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['ztp', 'status', '--verbose'], display_cmd=True)

    @patch('show.main.run_command')
    def test_show_banner(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['banner'])
        assert result.exit_code == 0

    @patch('show.main.run_command')
    def test_show_ntp(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ntp'])
        assert result.exit_code == 0
        expected_calls = [call(['chronyc', '-n', 'tracking'], display_cmd=False),
                          call(['chronyc', '-n', 'sources'], display_cmd=False)]
        mock_run_command.assert_has_calls(expected_calls)

    @patch('show.main.is_mgmt_vrf_enabled', MagicMock(return_value=True))
    @patch('show.main.run_command')
    def test_show_ntp_mgmt_vrf(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['ntp'])
        assert result.exit_code == 0
        expected_calls = [call(['sudo', 'ip', 'vrf', 'exec', 'mgmt', 'chronyc', '-n', 'tracking'], display_cmd=False),
                          call(['sudo', 'ip', 'vrf', 'exec', 'mgmt', 'chronyc', '-n', 'sources'], display_cmd=False)]
        mock_run_command.assert_has_calls(expected_calls)

    def teardown(self):
        print('TEAR DOWN')


class TestShowRunningconfiguration(object):
    @classmethod
    def setup_class(cls):
        print('SETUP')
        os.environ['UTILITIES_UNIT_TESTING'] = '1'

    @patch('show.main.run_command')
    @patch('builtins.open', mock_open(
        read_data=open('tests/syslog_input/rsyslog.conf').read()))
    def test_rc_syslog(self, mock_rc):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands['runningconfiguration'].commands['syslog'])
        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '[1.1.1.1]' in result.output

    @patch('builtins.open', mock_open(
        read_data=open('tests/chrony.conf').read()))
    def test_ntp(self):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands['runningconfiguration'].commands['ntp'])
        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '10.1.1.1' in result.output
        assert '10.22.1.12' in result.output

    @classmethod
    def teardown_class(cls):
        print('TEARDOWN')


class TestShowSRv6Counters(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_srv6_stats(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['stats'], ['--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['srv6stat'], display_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_srv6_stats_with_sid(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['stats'], ['1000:2:30::/48', '--verbose'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['srv6stat', '-s', '1000:2:30::/48'], display_cmd=True)

    def teardown(self):
        print('TEAR DOWN')
