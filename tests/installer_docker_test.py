import sys
import pytest
import subprocess
import sonic_installer.main as sonic_installer
import sonic_installer.common as sonic_installer_common

from click.testing import CliRunner
from unittest.mock import patch, MagicMock, Mock

SUCCESS = 0

@patch("sonic_installer.main.subprocess.Popen")
def test_get_container_image_id(mock_popen):
    image_tag = 'abcde'

    mock_proc = MagicMock()
    attrs = {"communicate.return_value": ("output", "error")}
    mock_proc.configure_mock(**attrs)
    mock_popen.return_value = mock_proc

    expected_call = ["docker", "images", "--format", '{{.ID}}', image_tag]
    sonic_installer.get_container_image_id(image_tag)
    mock_popen.assert_called_with(expected_call, stdout=subprocess.PIPE, text=True)

@patch("sonic_installer.main.subprocess.Popen")
def test_get_container_image_id_all(mock_popen):
    image_name = 'abcde'

    mock_proc = MagicMock()
    attrs = {"communicate.return_value": ("output", "error")}
    mock_proc.configure_mock(**attrs)
    mock_popen.return_value = mock_proc

    expected_call = ["docker", "images", "--format", '{{.ID}}', image_name]
    sonic_installer.get_container_image_id_all(image_name)
    mock_popen.assert_called_with(expected_call, stdout=subprocess.PIPE, text=True)

@patch('sonic_installer.main.get_container_image_name', MagicMock(return_value='docker-fpm-frr'))
@patch('sonic_installer.main.get_container_image_id_all', MagicMock(return_value=['1', '2']))
@patch('sonic_installer.main.get_container_image_id', MagicMock(return_value=['1']))
@patch('sonic_installer.main.get_docker_tag_name', MagicMock(return_value='some_tag'))
@patch('sonic_installer.main.echo_and_log', MagicMock())
@patch('sonic_installer.main.run_command')
def test_rollback_docker_basic(mock_run_cmd):
    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['rollback-docker'], ['-y', 'bgp']
        )

    assert result.exit_code == SUCCESS
    expect_docker_tag_command = ['docker', 'tag', 'docker-fpm-frr:some_tag', 'docker-fpm-frr:latest']
    mock_run_cmd.assert_called_with(expect_docker_tag_command)

    mock_run_cmd.reset()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['rollback-docker'], ['-y', 'snmp']
        )

    assert result.exit_code == SUCCESS
    mock_run_cmd.assert_any_call(['systemctl', 'restart', 'snmp'])


@patch('sonic_installer.main.get_container_image_name', MagicMock(return_value='docker-fpm-frr'))
@patch('sonic_installer.main.get_container_image_id_all', MagicMock(return_value=['1']))
def test_rollback_docker_no_extra_image():
    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['rollback-docker'], ['-y', 'bgp']
        )
    assert result.exit_code != SUCCESS


@pytest.mark.parametrize("container", ['bgp', 'swss', 'teamd', 'pmon'])
@patch('sonic_installer.main.get_container_image_name', MagicMock(return_value='docker-fpm-frr'))
@patch('sonic_installer.main.get_container_image_id', MagicMock(return_value='1'))
@patch('sonic_installer.main.get_container_image_id_all', MagicMock(return_value=['1', '2']))
@patch('sonic_installer.main.validate_url_or_abort', MagicMock())
@patch('sonic_installer.main.urlretrieve', MagicMock())
@patch('os.path.isfile', MagicMock(return_value=True))
@patch('sonic_installer.main.get_docker_tag_name', MagicMock(return_value='some_tag'))
@patch('sonic_installer.main.run_command', MagicMock())
@patch("sonic_installer.main.subprocess.Popen")
@patch('sonic_installer.main.hget_warm_restart_table')
def test_upgrade_docker_basic(mock_hget, mock_popen, container):
    def mock_hget_impl(db_name, table_name, warm_app_name, key):
        if table_name == 'WARM_RESTART_ENABLE_TABLE':
            return "false"
        elif table_name == 'WARM_RESTART_TABLE':
            return 'reconciled'

    mock_hget.side_effect = mock_hget_impl
    mock_proc = MagicMock()
    mock_proc.communicate = MagicMock(return_value=(None, None))
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc

    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['upgrade-docker'],
            ['-y', '--cleanup_image', '--warm', container, 'http://']
        )

    print(result.output)
    assert result.exit_code == SUCCESS


@patch('sonic_installer.main.get_container_image_name', MagicMock(return_value='docker-fpm-frr'))
@patch('sonic_installer.main.get_container_image_id', MagicMock(return_value=['1']))
@patch('sonic_installer.main.validate_url_or_abort', MagicMock())
@patch('sonic_installer.main.urlretrieve', MagicMock(side_effect=Exception('download failed')))
def test_upgrade_docker_download_fail():
    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['upgrade-docker'],
            ['-y', '--cleanup_image', '--warm', 'bgp', 'http://']
        )
    assert 'download failed' in result.output
    assert result.exit_code != SUCCESS


@patch('sonic_installer.main.get_container_image_name', MagicMock(return_value='docker-fpm-frr'))
@patch('sonic_installer.main.get_container_image_id', MagicMock(return_value=['1']))
@patch('sonic_installer.main.validate_url_or_abort', MagicMock())
@patch('sonic_installer.main.urlretrieve', MagicMock(side_effect=Exception('download failed')))
def test_upgrade_docker_image_not_exist():
    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['upgrade-docker'],
            ['-y', '--cleanup_image', '--warm', 'bgp', 'invalid_url']
        )
    assert 'does not exist' in result.output
    assert result.exit_code != SUCCESS


@patch('sonic_installer.main.get_container_image_name', MagicMock(return_value='docker-fpm-frr'))
@patch('sonic_installer.main.get_container_image_id', MagicMock(return_value=['1']))
@patch('sonic_installer.main.validate_url_or_abort', MagicMock())
@patch('sonic_installer.main.urlretrieve', MagicMock())
@patch('os.path.isfile', MagicMock(return_value=True))
@patch('sonic_installer.main.get_docker_tag_name', MagicMock(return_value='some_tag'))
@patch('sonic_installer.main.run_command', MagicMock())
@patch('sonic_installer.main.hget_warm_restart_table', MagicMock(return_value='false'))
@patch("sonic_installer.main.subprocess.Popen")
def test_upgrade_docker_image_swss_check_failed(mock_popen):
    mock_proc = MagicMock()
    mock_proc.communicate = MagicMock(return_value=(None, None))
    mock_proc.returncode = 1
    mock_popen.return_value = mock_proc
    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['upgrade-docker'],
            ['-y', '--cleanup_image', '--warm', 'swss', 'http://']
        )
    assert 'RESTARTCHECK failed' in result.output
    assert result.exit_code != SUCCESS
