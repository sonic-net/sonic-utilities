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


class TestRexecBgp(object):
    @classmethod
    def setup_class(cls):
        pass

    @mock.patch("sonic_py_common.device_info.is_supervisor", mock.MagicMock(return_value=True))
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
