import os
from click.testing import CliRunner
import paramiko
from rcli import rexec
from rcli import rshell
from rcli import linecard
from rcli import utils as rcli_utils
import sys
from io import BytesIO, StringIO
from unittest import mock
import select
import socket
import termios

MULTI_LC_REXEC_OUTPUT = '''======== LINE-CARD0|sonic-lc1 output: ========
hello world
======== LINE-CARD2|sonic-lc3 output: ========
hello world
'''
REXEC_HELP = '''Usage: cli [OPTIONS] LINECARD_NAMES...

  Executes a command on one or many linecards

  :param linecard_names: A list of linecard names to execute the command on,
  use `all` to execute on all linecards. :param command: The command to
  execute on the linecard(s) :param username: The username to use to login to
  the linecard(s)

Options:
  -c, --command TEXT   [required]
  -u, --username TEXT  Username for login
  --help               Show this message and exit.
'''


def mock_exec_command():

    mock_stdout = BytesIO(b"""hello world""")
    mock_stderr = BytesIO()
    return '', mock_stdout, None


def mock_exec_error_cmd():
    mock_stdout = BytesIO()
    mock_stderr = BytesIO(b"""Command not found""")
    return '', mock_stdout, mock_stderr


def mock_connection_channel():
    c = mock.MagicMock(return_value="channel")
    c.get_pty = mock.MagicMock(return_value='')
    c.invoke_shell = mock.MagicMock()
    c.recv = mock.MagicMock(side_effect=['abcd', ''])
    return c


def mock_connection_channel_with_timeout():
    c = mock.MagicMock(return_value="channel")
    c.get_pty = mock.MagicMock(return_value='')
    c.invoke_shell = mock.MagicMock()
    c.recv = mock.MagicMock(
        side_effect=['abcd', socket.timeout(10, 'timeout')])
    return c


def mock_paramiko_connection(channel):
    # Create a mock to return for connection.
    conn = mock.MagicMock()
    # create a mock return for transport
    t = mock.MagicMock()
    t.open_session = mock.MagicMock(return_value=channel)
    conn.get_transport = mock.MagicMock(return_value=t)
    conn.connect = mock.MagicMock()
    conn.close = mock.MagicMock()
    return conn


class TestRemoteExec(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import dbconnector
        dbconnector.load_database_config()

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    # @mock.patch.object(linecard.Linecard, '_get_password', mock.MagicMock(return_value='dummmy'))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(paramiko.SSHClient, 'exec_command', mock.MagicMock(return_value=mock_exec_command()))
    def test_rexec_with_module_name(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        result = runner.invoke(rexec.cli, [LINECARD_NAME, "-c", "pwd"])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert "hello world" in result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(paramiko.SSHClient, 'exec_command', mock.MagicMock(return_value=mock_exec_command()))
    def test_rexec_with_hostname(self):
        runner = CliRunner()
        LINECARD_NAME = "sonic-lc1"
        result = runner.invoke(rexec.cli, [LINECARD_NAME, "-c", "pwd"])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert "hello world" in result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(paramiko.SSHClient, 'exec_command', mock.MagicMock(return_value=mock_exec_error_cmd()))
    def test_rexec_error_with_module_name(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        result = runner.invoke(rexec.cli, [LINECARD_NAME, "-c", "pwd"])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert "Command not found" in result.output

    def test_rexec_error(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        result = runner.invoke(
            rexec.cli, [LINECARD_NAME, "-c", "show version"])
        print(result.output)
        assert result.exit_code == 1, result.output
        assert "This commmand is only supported Chassis" in result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(linecard.Linecard, 'execute_cmd', mock.MagicMock(return_value="hello world"))
    def test_rexec_all(self):
        runner = CliRunner()
        LINECARD_NAME = "all"
        result = runner.invoke(
            rexec.cli, [LINECARD_NAME, "-c", "show version"])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert MULTI_LC_REXEC_OUTPUT == result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(linecard.Linecard, 'execute_cmd', mock.MagicMock(return_value="hello world"))
    def test_rexec_invalid_lc(self):
        runner = CliRunner()
        LINECARD_NAME = "sonic-lc-100"
        result = runner.invoke(
            rexec.cli, [LINECARD_NAME, "-c", "show version"])
        print(result.output)
        assert result.exit_code == 1, result.output
        assert "Linecard sonic-lc-100 not found\n" == result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(linecard.Linecard, 'execute_cmd', mock.MagicMock(return_value="hello world"))
    def test_rexec_unreachable_lc(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD1"
        result = runner.invoke(
            rexec.cli, [LINECARD_NAME, "-c", "show version"])
        print(result.output)
        assert result.exit_code == 1, result.output
        assert "Linecard LINE-CARD1 not accessible\n" == result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock())
    @mock.patch.object(linecard.Linecard, 'execute_cmd', mock.MagicMock(return_value="hello world"))
    def test_rexec_help(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD1"
        result = runner.invoke(rexec.cli, ["--help"])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert REXEC_HELP == result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock(side_effect=paramiko.ssh_exception.NoValidConnectionsError({('192.168.0.1',
                                                                                                                                  22): "None"})))
    @mock.patch.object(linecard.Linecard, 'execute_cmd', mock.MagicMock(return_value="hello world"))
    def test_rexec_exception(self):
        runner = CliRunner()
        LINECARD_NAME = "sonic-lc1"
        result = runner.invoke(
            rexec.cli, [LINECARD_NAME, "-c", "show version"])
        print(result.output)
        assert result.exit_code == 1, result.output
        assert "Failed to connect to sonic-lc1 with username admin\n" == result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(paramiko.SSHClient, 'connect', mock.MagicMock(side_effect=paramiko.ssh_exception.NoValidConnectionsError({('192.168.0.1',
                                                                                                                                  22): "None"})))
    def test_rexec_with_user_param(self):
        runner = CliRunner()
        LINECARD_NAME = "all"
        result = runner.invoke(
            rexec.cli, [LINECARD_NAME, "-c", "show version", "-u", "testuser"])
        print(result.output)
        assert result.exit_code == 1, result.output
        assert "Failed to connect to sonic-lc1 with username testuser\n" == result.output


class TestRemoteCLI(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import dbconnector
        dbconnector.load_database_config()

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(linecard.Linecard, '_set_tty_params', mock.MagicMock())
    @mock.patch.object(termios, 'tcsetattr', mock.MagicMock())
    @mock.patch.object(termios, 'tcgetattr', mock.MagicMock(return_value=[]))
    def test_rcli_with_module_name(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        channel = mock_connection_channel()

        with mock.patch('paramiko.SSHClient', mock.MagicMock(return_value=mock_paramiko_connection(channel))), \
                mock.patch('select.select', mock.MagicMock(return_value=([channel], [], []))):
            result = runner.invoke(rshell.cli, [LINECARD_NAME])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert "abcd" in result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(linecard.Linecard, '_set_tty_params', mock.MagicMock())
    @mock.patch.object(termios, 'tcsetattr', mock.MagicMock())
    @mock.patch.object(termios, 'tcgetattr', mock.MagicMock(return_value=[]))
    def test_rcli_with_module_name_2(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        channel = mock_connection_channel()

        with mock.patch('paramiko.SSHClient', mock.MagicMock(return_value=mock_paramiko_connection(channel))), \
                mock.patch('select.select', mock.MagicMock(side_effect=[([], [], []), ([channel], [], []), ([channel], [], [])])):
            result = runner.invoke(rshell.cli, [LINECARD_NAME])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert "Connecting to LINE-CARD0" in result.output

    @mock.patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @mock.patch("os.getlogin", mock.MagicMock(return_value="admin"))
    @mock.patch("rcli.utils.get_password", mock.MagicMock(return_value="dummy"))
    @mock.patch.object(linecard.Linecard, '_set_tty_params', mock.MagicMock())
    @mock.patch.object(termios, 'tcsetattr', mock.MagicMock())
    @mock.patch.object(termios, 'tcgetattr', mock.MagicMock(return_value=[]))
    def test_rcli_with_module_name_3(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        channel = mock_connection_channel_with_timeout()

        with mock.patch('paramiko.SSHClient', mock.MagicMock(return_value=mock_paramiko_connection(channel))), \
                mock.patch('select.select', mock.MagicMock(return_value=([channel], [], []))):
            result = runner.invoke(rshell.cli, [LINECARD_NAME])
        print(result.output)
        assert result.exit_code == 0, result.output
        assert "Connecting to LINE-CARD0" in result.output

    def test_rcli_error(self):
        runner = CliRunner()
        LINECARD_NAME = "LINE-CARD0"
        result = runner.invoke(rshell.cli, [LINECARD_NAME])
        print(result.output)
        assert result.exit_code == 1, result.output
        assert "This commmand is only supported Chassis" in result.output
