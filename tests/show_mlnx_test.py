import sys
import click
import pytest
import show.plugins.mlnx as show
from unittest.mock import call, patch, mock_open, MagicMock


class TestShowMlnx(object):
    def setup(self):
        print('SETUP')

    @patch('click.style')
    def test_run_command(self, mock_click):
        cmd0 = ['echo', 'test']
        out, err = show.run_command(cmd0, display_cmd=True)

        assert mock_click.call_args_list == [call('Running command: ', fg='cyan'), call(' '.join(cmd0), fg='green')]
        assert out == 'test\n'

        cmd1 = [sys.executable, "-c", "import sys; sys.exit(6)"]
        with pytest.raises(SystemExit) as e:
            show.run_command(cmd1)
        assert e.value.code == 6

    @patch('builtins.open', mock_open(read_data=show.ENV_VARIABLE_SX_SNIFFER))
    @patch('show.plugins.mlnx.run_command')
    def test_sniffer_status_get_enable(self, mock_runcmd):
        expected_calls = [
            call(["docker", "exec", show.CONTAINER_NAME, "bash", "-c", 'touch {}'.format(show.SNIFFER_CONF_FILE)]),
            call(['docker', 'cp', show.SNIFFER_CONF_FILE_IN_CONTAINER, show.TMP_SNIFFER_CONF_FILE]),
            call(['rm', '-rf', show.TMP_SNIFFER_CONF_FILE])
        ]

        output = show.sniffer_status_get(show.ENV_VARIABLE_SX_SNIFFER)
        assert mock_runcmd.call_args_list == expected_calls
        assert output

    @patch('builtins.open', mock_open(read_data='not_enable'))
    @patch('show.plugins.mlnx.run_command')
    def test_sniffer_status_get_disable(self, mock_runcmd):
        expected_calls = [
            call(["docker", "exec", show.CONTAINER_NAME, "bash", "-c", 'touch {}'.format(show.SNIFFER_CONF_FILE)]),
            call(['docker', 'cp', show.SNIFFER_CONF_FILE_IN_CONTAINER, show.TMP_SNIFFER_CONF_FILE]),
            call(['rm', '-rf', show.TMP_SNIFFER_CONF_FILE])
        ]

        output = show.sniffer_status_get(show.ENV_VARIABLE_SX_SNIFFER)
        assert mock_runcmd.call_args_list == expected_calls
        assert not output

    @patch('show.plugins.mlnx.run_command')
    def test_is_issu_status_enabled_systemexit(self, mock_runcmd):
        mock_runcmd.return_value = ('key0=value0\n', '')
        expected_calls = ['docker', 'exec', show.CONTAINER_NAME, 'cat', r'/{}/sai.profile'.format(show.HWSKU_PATH)]

        with pytest.raises(SystemExit) as e:
            show.is_issu_status_enabled()
        assert e.value.code == 1
        mock_runcmd.assert_called_with(expected_calls, print_to_console=False)

    @pytest.mark.parametrize("status", [True, False])
    @patch('show.plugins.mlnx.run_command')
    def test_is_issue_status_enabled(self, mock_runcmd, status):
        def mock_return(*args, **kwargs):
            cmd = ' '.join(args[0])
            if cmd == f"docker exec {show.CONTAINER_NAME} cat /{show.HWSKU_PATH}/sai.profile":
                return ('SAI_INIT_CONFIG_FILE=/usr/share/sonic/hwsku/sai.xml\n', '')
            elif cmd == f"docker exec {show.CONTAINER_NAME} cat {show.HWSKU_PATH}sai.xml":
                return (f"""<?xml version="1.0"?>
                <root>
                    <platform_info>
                        <issu-enabled>{int(status)}</issu-enabled>
                    </platform_info>
                </root>
                """, '')
            else:
                return ('', '')

        mock_runcmd.side_effect = mock_return
        result = show.is_issu_status_enabled()
        assert result is status

    @pytest.mark.parametrize("status", [True, False])
    @patch('show.plugins.mlnx.multi_asic.get_num_asics', return_value=4)
    @patch('show.plugins.mlnx.run_command')
    def test_is_issue_status_enabled_multi_asic(self, mock_runcmd, mock_get_numasics, status):
        def mock_return(*args, **kwargs):
            cmd = ' '.join(args[0])
            if (
                cmd == f"docker exec {show.CONTAINER_NAME}0 cat /{show.HWSKU_PATH}/sai.profile" or
                cmd == f"docker exec {show.CONTAINER_NAME}1 cat /{show.HWSKU_PATH}/sai.profile" or
                cmd == f"docker exec {show.CONTAINER_NAME}2 cat /{show.HWSKU_PATH}/sai.profile" or
                cmd == f"docker exec {show.CONTAINER_NAME}3 cat /{show.HWSKU_PATH}/sai.profile"
            ):
                return ('SAI_INIT_CONFIG_FILE=/usr/share/sonic/hwsku/sai.xml\n', '')
            elif (
                cmd == f"docker exec {show.CONTAINER_NAME}0 cat {show.HWSKU_PATH}sai.xml" or
                cmd == f"docker exec {show.CONTAINER_NAME}1 cat {show.HWSKU_PATH}sai.xml" or
                cmd == f"docker exec {show.CONTAINER_NAME}2 cat {show.HWSKU_PATH}sai.xml" or
                cmd == f"docker exec {show.CONTAINER_NAME}3 cat {show.HWSKU_PATH}sai.xml"
            ):
                return (f"""<?xml version="1.0"?>
                <root>
                    <platform_info>
                        <issu-enabled>{int(status)}</issu-enabled>
                    </platform_info>
                </root>
                """, '')
            else:
                return ('', '')

        mock_runcmd.side_effect = mock_return
        result = show.is_issu_status_enabled()
        assert result is status

    def teardown(self):
        print('TEARDOWN')

