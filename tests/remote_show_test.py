import mock
import subprocess
from io import BytesIO
from click.testing import CliRunner


def mock_rexec_command(*args):
    mock_stdout = BytesIO(b"""hello world""")
    print(mock_stdout.getvalue().decode())
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_stdout, stderr=BytesIO())


def mock_rexec_error_cmd(*args):
    mock_stderr = BytesIO(b"""Error""")
    print(mock_stderr.getvalue().decode())
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=BytesIO(), stderr=mock_stderr)


MULTI_LC_REXEC_OUTPUT = '''Since the current device is a chassis supervisor, this command will be executed remotely on all linecards
hello world
'''

MULTI_LC_ERR_OUTPUT = '''Since the current device is a chassis supervisor, this command will be executed remotely on all linecards
Error
'''


class TestRexecInterfacesStatus(object):
    @classmethod
    def setup_class(cls):
        pass

    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("sys.argv", ["show", "interfaces", "status"])
    def test_show_interfaces_status_rexec(self):
        import show.main as show
        runner = CliRunner()

        _old_subprocess_run = subprocess.run
        subprocess.run = mock_rexec_command
        result = runner.invoke(show.cli.commands["interfaces"].commands["status"])
        print(result.output)
        subprocess.run = _old_subprocess_run
        assert result.exit_code == 0
        assert MULTI_LC_REXEC_OUTPUT == result.output

    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("sys.argv", ["show", "interfaces", "status"])
    def test_show_interfaces_status_error_rexec(self):
        import show.main as show
        runner = CliRunner()

        _old_subprocess_run = subprocess.run
        subprocess.run = mock_rexec_error_cmd
        result = runner.invoke(show.cli.commands["interfaces"].commands["status"])
        print(result.output)
        subprocess.run = _old_subprocess_run
        assert result.exit_code == 1
        assert MULTI_LC_ERR_OUTPUT == result.output

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces.clicommon.run_command")
    @mock.patch("show.interfaces.subprocess.run", side_effect=mock_rexec_command)
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces._get_local_supervisor_name", mock.MagicMock(return_value="SUPERVISOR0"))
    @mock.patch("sys.argv", ["show", "interfaces", "status"])
    def test_packet_chassis_status_includes_supervisor_and_linecards(
            self, mock_run, mock_run_command):
        import show.main as show
        runner = CliRunner()
        status_command = show.cli.commands["interfaces"].commands["status"]
        display_param = next(param for param in status_command.params
                             if param.name == "display")
        original_default = display_param.default
        display_param.default = "frontend"

        try:
            result = runner.invoke(status_command)
        finally:
            display_param.default = original_default

        assert result.exit_code == 0
        assert "======== SUPERVISOR0 output: ========\n" in result.output
        assert result.output.index("hello world") < result.output.index("SUPERVISOR0")
        assert "Use -d all to display internal interfaces.\n" in result.output
        mock_run_command.assert_called_once_with(
            ["intfutil", "-c", "status", "-d", "frontend"], display_cmd=False)
        mock_run.assert_called_once_with(
            ["rexec", "all", "-c", "show interfaces status"])

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces.clicommon.run_command")
    @mock.patch("show.interfaces.subprocess.run", side_effect=mock_rexec_command)
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces._get_local_supervisor_name", mock.MagicMock(return_value="SUPERVISOR0"))
    @mock.patch("sys.argv", ["show", "interfaces", "status", "-d", "all"])
    def test_packet_chassis_status_all_includes_internal_interfaces(
            self, mock_run, mock_run_command):
        import show.main as show
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["status"], ["--display", "all"])

        assert result.exit_code == 0
        assert "======== SUPERVISOR0 output: ========\n" in result.output
        assert result.output.index("hello world") < result.output.index("SUPERVISOR0")
        assert "Use -d all to display internal interfaces." not in result.output
        mock_run_command.assert_called_once_with(
            ["intfutil", "-c", "status", "-d", "all"], display_cmd=False)
        mock_run.assert_called_once_with(
            ["rexec", "all", "-c", "show interfaces status -d all"])

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces.clicommon.run_command")
    @mock.patch("show.interfaces.subprocess.run")
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces._get_local_supervisor_name", mock.MagicMock(return_value="SUPERVISOR1"))
    @mock.patch("sys.argv", ["show", "interfaces", "status"])
    def test_packet_chassis_status_supervisor_location_is_local(
            self, mock_run, mock_run_command):
        import show.main as show
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["status"],
            ["--location", "SUPERVISOR"])

        assert result.exit_code == 0
        assert "======== SUPERVISOR1 output: ========\n" in result.output
        assert "Use -d all to display internal interfaces.\n" in result.output
        mock_run.assert_not_called()
        mock_run_command.assert_called_once_with(
            ["intfutil", "-c", "status", "-d", "frontend"], display_cmd=False)

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces.clicommon.run_command")
    @mock.patch("show.interfaces.subprocess.run")
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces._get_local_supervisor_name", mock.MagicMock(return_value="SUPERVISOR1"))
    @mock.patch("sys.argv", ["show", "interfaces", "status"])
    def test_packet_chassis_status_rejects_nonlocal_supervisor_location(
            self, mock_run, mock_run_command):
        import show.main as show
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["status"],
            ["--location", "SUPERVISOR0"])

        assert result.exit_code == 2
        assert "SUPERVISOR0 is not the local supervisor (SUPERVISOR1)" in result.output
        mock_run.assert_not_called()
        mock_run_command.assert_not_called()

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=False))
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    def test_status_help_hides_location_on_nonpacket_supervisor(self):
        import show.main as show
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["status"], ["--help"])

        assert result.exit_code == 0
        assert "--location" not in result.output
        assert "-l" not in result.output

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=False))
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=False))
    def test_status_rejects_location_on_nonpacket_platform(self):
        import show.main as show
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["status"],
            ["--location", "LINE-CARD1"])

        assert result.exit_code == 2
        assert "is only supported on packet-chassis supervisors" in result.output

    @mock.patch("show.interfaces.device_info.is_packet_chassis", mock.MagicMock(return_value=True))
    @mock.patch("show.interfaces.subprocess.run", side_effect=mock_rexec_command)
    @mock.patch("show.interfaces.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("sys.argv", ["show", "interfaces", "status", "-l", "LINE-CARD0"])
    def test_packet_chassis_status_linecard_location(self, mock_run):
        import show.main as show
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["status"],
            ["--location", "LINE-CARD0"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["rexec", "LINE-CARD0", "-c", "show interfaces status"])

    @mock.patch("show.interfaces.sys.argv",
                ["show", "interfaces", "status", "-lLINE-CARD0"])
    def test_remote_status_command_strips_attached_location_option(self):
        from show.interfaces import _remote_status_command

        assert _remote_status_command() == "show interfaces status"


class TestRexecBgp(object):
    @classmethod
    def setup_class(cls):
        pass

    @mock.patch("sonic_py_common.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("sys.argv", ["show", "ip", "bgp", "summary"])
    def test_show_ip_bgp_rexec(self, setup_bgp_commands):
        show = setup_bgp_commands
        runner = CliRunner()

        _old_subprocess_run = subprocess.run
        subprocess.run = mock_rexec_command
        result = runner.invoke(show.cli.commands["ip"].commands["bgp"], args=["summary"])
        print(result.output)
        subprocess.run = _old_subprocess_run
        assert result.exit_code == 0
        assert MULTI_LC_REXEC_OUTPUT == result.output

    @mock.patch("sonic_py_common.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("sys.argv", ["show", "ip", "bgp", "summary"])
    def test_show_ip_bgp_error_rexec(self, setup_bgp_commands):
        show = setup_bgp_commands
        runner = CliRunner()

        _old_subprocess_run = subprocess.run
        subprocess.run = mock_rexec_error_cmd
        result = runner.invoke(show.cli.commands["ip"].commands["bgp"], args=["summary"])
        print(result.output)
        subprocess.run = _old_subprocess_run
        assert result.exit_code == 1
        assert MULTI_LC_ERR_OUTPUT == result.output

    @mock.patch("sonic_py_common.device_info.is_supervisor", mock.MagicMock(return_value=True))
    @mock.patch("sys.argv", ["show", "ip", "bgp", "network", "10.0.0.0/24"])
    def test_show_ip_bgp_network_rexec(self, setup_bgp_commands):
        show = setup_bgp_commands
        runner = CliRunner()

        _old_subprocess_run = subprocess.run
        subprocess.run = mock_rexec_command
        result = runner.invoke(show.cli.commands["ip"].commands["bgp"], args=["network", "10.0.0.0/24"])
        print(result.output)
        subprocess.run = _old_subprocess_run
        assert result.exit_code == 0
        assert MULTI_LC_REXEC_OUTPUT == result.output
