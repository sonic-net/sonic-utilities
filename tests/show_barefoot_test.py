import json
import click
import pytest
from click.testing import CliRunner
import show.plugins.barefoot as show
from unittest.mock import call, patch, mock_open, MagicMock


class TestShowBarefoot(object):
    def setup(self):
        print('SETUP')

    @patch('subprocess.run')
    def test_default_profile(self, mock_run):
        mock_run.return_value.returncode = 1
        runner = CliRunner()
        result = runner.invoke(show.profile, [])
        assert result.exit_code == 0
        assert result.output == 'Current profile: default\n'
        mock_run.assert_called_once_with(['docker', 'exec', '-it', 'syncd', 'test', '-h', '/opt/bfn/install'])

    @patch('show.plugins.barefoot.getstatusoutput_noshell_pipe')
    @patch('show.plugins.barefoot.device_info.get_path_to_hwsku_dir', MagicMock(return_value='/usr/share/sonic/hwsku_dir'))
    @patch('subprocess.run')
    def test_nondefault_profile(self, mock_run, mock_cmd):
        mock_run.return_value.returncode = 0
        chip_list = [{'chip_family': 'TOFINO'}]
        mock_open_args = mock_open(read_data=json.dumps({'chip_list': chip_list}))
        expected_calls = [
            call(
                ['docker', 'exec', '-it', 'syncd', 'readlink', '/opt/bfn/install'], 
                ['sed', 's/install_\\\\\\(.\\*\\\\\\)_profile/\\\\1/']
            ),

            call(
                ['docker', 'exec', '-it', 'syncd', 'find', '/opt/bfn', '-mindepth', '1',\
                 '-maxdepth', '1', '-type', 'd', '-name', r'install_\*_profile', r'\! -name install_y\*_profile'],
                ["sed", r's%/opt/bfn/install_\\\(.\*\\\)_profile%\\1%']
            )
        ]

        with patch("builtins.open", mock_open_args) as mock_open_file:
            runner = CliRunner()
            result = runner.invoke(show.profile)
            assert result.exit_code == 0

        mock_run.assert_called_once_with(['docker', 'exec', '-it', 'syncd', 'test', '-h', '/opt/bfn/install'])
        mock_open_file.assert_called_once_with('/usr/share/sonic/hwsku_dir/switch-tna-sai.conf')
        assert mock_cmd.call_args_list == expected_calls

    def teardown(self):
        print('TEARDOWN')

