#!/usr/bin/env python3
#
# Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES.
# Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import mock
from unittest import TestCase
from click.testing import CliRunner
from utilities_common import util_base
import config.main as config
import config.plugins as plugins
from config.plugins.nvidia_bluefield import (
    get_sai_profile_value,
    rotate_dump_files,
    get_location_details,
    run_nasa_cli,
    cleanup_dump_files,
    get_packet_debug_mode,
    get_sai_debug_mode
)


GET_CMD_OUTPUT_ENABLED = b"""\
---------- NASA CLI ----------
Open conection to NASA Service
NASA service is up as expected, using running service
Welcome to the NASA CLI.   Type help or press tab to list commands.
nasa_cli> get_sai_debug_modez
RC: SAI_STATUS_SUCCESS (0x0)
filename: /tmp/config_record.bin
"""

GET_CMD_OUTPUT_DISABLED = b"""\
---------- NASA CLI ----------
Open conection to NASA Service
NASA service is up as expected, using running service
Welcome to the NASA CLI.   Type help or press tab to list commands.
nasa_cli> get_packet_debug_mode
RC: SAI_STATUS_ITEM_NOT_FOUND (-0x7)
"""

ASIC_TYPE_NVDA_BF = {"asic_type": "nvidia-bluefield"}


class TestNvidiaBluefieldSdk(TestCase):
    def setUp(self):
        self.docker_client = mock.MagicMock()
        self.container = mock.MagicMock()
        self.docker_client.containers.get.return_value = self.container
        self.runner = CliRunner()

    def test_get_sai_profile_value_success(self):
        self.container.exec_run.return_value = (0, b"SAI_DUMP_STORE_PATH=/var/log/bluefield/\nSAI_DUMP_STORE_AMOUNT=5")
        result = get_sai_profile_value("SAI_DUMP_STORE_PATH", self.docker_client)
        self.assertEqual(result, "/var/log/bluefield/")
        # Test getting count
        result = get_sai_profile_value("SAI_DUMP_STORE_AMOUNT", self.docker_client)
        self.assertEqual(result, "5")

    def test_get_sai_profile_value_not_found(self):
        self.container.exec_run.return_value = (0, b"OTHER_KEY=value")
        result = get_sai_profile_value("SAI_DUMP_STORE_PATH", self.docker_client)
        self.assertEqual(result, "")

    def test_get_sai_profile_value_error(self):
        self.container.exec_run.return_value = (1, b"Error")
        result = get_sai_profile_value("SAI_DUMP_STORE_PATH", self.docker_client)
        self.assertEqual(result, "")

    @mock.patch('os.path.join')
    @mock.patch('os.remove')
    @mock.patch('config.plugins.nvidia_bluefield.get_stats')
    def test_rotate_dump_files(self, mock_get_stats, mock_remove, mock_join):
        # Mock the filesystem stats
        mock_get_stats.return_value = (
            [(0, 100, '/var/log/file1'), (0, 200, '/var/log/file2')],
            600
        )
        rotate_dump_files("/var/log", 2)
        mock_remove.assert_called_once_with('/var/log/file2')

    @mock.patch('pathlib.Path.exists')
    def test_get_location_details_success(self, mock_exists):
        mock_exists.return_value = True
        with mock.patch('config.plugins.nvidia_bluefield.get_sai_profile_value') as mock_get:
            mock_get.side_effect = ["/var/log", "5"]
            path, count = get_location_details(self.docker_client)
            self.assertEqual(path, "/var/log")
            self.assertEqual(count, 5)

    @mock.patch('pathlib.Path.exists')
    def test_get_location_details_invalid_path(self, mock_exists):
        mock_exists.return_value = False
        path, count = get_location_details(self.docker_client)
        self.assertIsNone(path)
        self.assertIsNone(count)

    @mock.patch('pathlib.Path.exists')
    def test_get_location_details_invalid_count(self, mock_exists):
        mock_exists.return_value = True
        with mock.patch('config.plugins.nvidia_bluefield.get_sai_profile_value') as mock_get:
            mock_get.side_effect = ["/var/log", "invalid"]
            path, count = get_location_details(self.docker_client)
            self.assertIsNone(count)

    def test_nasa_cli(self):
        self.container.exec_run = mock.MagicMock()
        self.container.exec_run.return_value = (0, b"")
        run_nasa_cli("get_packet_debug_mode", self.docker_client)
        self.container.exec_run.assert_has_calls([
            mock.call('sh -c \'echo -n "get_packet_debug_mode\nquit\n" > /tmp/nasa_cli_cmd.txt\''),
            mock.call('/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt'),
        ])

    @mock.patch('pathlib.Path.mkdir')
    @mock.patch('config.plugins.nvidia_bluefield.rotate_dump_files')
    def test_cleanup_dump_files(self, m_rotate_dump_files, m_mkdir):
        cleanup_dump_files("/var/log", 2, "test_dir")
        m_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        m_rotate_dump_files.assert_called_once_with("/var/log/test_dir", 2)

    def test_debug_mode_enabled(self):
        self.container.exec_run = mock.MagicMock()
        self.container.exec_run.return_value = (0, GET_CMD_OUTPUT_ENABLED)
        status, filename = get_sai_debug_mode(self.docker_client)
        assert status == 'enabled'
        assert filename == '/tmp/config_record.bin'
        self.container.exec_run.assert_has_calls([
            mock.call('sh -c \'echo -n "get_sai_debug_mode\nquit\n" > /tmp/nasa_cli_cmd.txt\''),
            mock.call('/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt'),
        ])

    def test_debug_mode_disabled(self):
        self.container.exec_run = mock.MagicMock()
        self.container.exec_run.return_value = (0, GET_CMD_OUTPUT_DISABLED)
        status, filename = get_packet_debug_mode(self.docker_client)
        assert status == 'disabled'
        assert filename is None
        self.container.exec_run.assert_has_calls([
            mock.call('sh -c \'echo -n "get_packet_debug_mode\nquit\n" > /tmp/nasa_cli_cmd.txt\''),
            mock.call('/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt'),
        ])

    def test_debug_mode_disabled_error(self):
        self.container.exec_run = mock.MagicMock()
        self.container.exec_run.return_value = (1, b"Random error")
        status, filename = get_packet_debug_mode(self.docker_client)
        assert status == 'disabled'
        assert filename is None


class TestNvidiaBluefieldCliSdk(TestCase):

    @mock.patch('docker.from_env')
    @mock.patch('os.mknod')
    @mock.patch('config.plugins.nvidia_bluefield.get_packet_debug_mode', return_value=('', ''))
    @mock.patch('config.plugins.nvidia_bluefield.run_in_syncd', return_value=(0, b""))
    @mock.patch('config.plugins.nvidia_bluefield.cleanup_dump_files')
    @mock.patch('config.plugins.nvidia_bluefield.get_location_details', return_value=("/var/log/bluefield/", 5))
    @mock.patch('sonic_py_common.device_info.get_sonic_version_info', return_value=ASIC_TYPE_NVDA_BF)
    def test_packet_drop_cli(
        self,
        m_device_info,
        m_get_location_details,
        m_cleanup_dump_files,
        m_run_in_syncd,
        m_current,
        m_mknod,
        m_docker
    ):
        helper = util_base.UtilHelper()
        helper.load_and_register_plugins(plugins, config.config)
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["platform"].commands["nvidia-bluefield"].commands["sdk"],
            ["packet-drop", "enabled"]
        )
        f_name = m_mknod.call_args.args[0]
        assert f_name.startswith("/var/log/bluefield/packet-drop/pkt_dump_record_")
        assert result.exit_code == 0
        assert "Packet drop recording enabled" in result.output
        assert m_run_in_syncd.call_count == 2
        cmd_create = m_run_in_syncd.call_args_list[0].args[0]
        cmd_run = m_run_in_syncd.call_args_list[1].args[0]
        set_cmd_prefix = 'set_packet_debug_mode on filepath /var/log/bluefield/packet-drop/pkt_dump_record_'
        assert set_cmd_prefix in cmd_create
        assert '/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt' in cmd_run

        m_run_in_syncd.reset_mock()

        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["platform"].commands["nvidia-bluefield"].commands["sdk"],
            ["packet-drop", "disabled"]
        )
        assert m_run_in_syncd.call_count == 2
        cmd_create = m_run_in_syncd.call_args_list[0].args[0]
        cmd_run = m_run_in_syncd.call_args_list[1].args[0]
        assert 'set_packet_debug_mode' in cmd_create
        assert '/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt' in cmd_run
        assert result.exit_code == 0
        assert "Packet drop recording disabled" in result.output

    @mock.patch('docker.from_env')
    @mock.patch('os.mknod')
    @mock.patch('config.plugins.nvidia_bluefield.get_sai_debug_mode', return_value=('', ''))
    @mock.patch('config.plugins.nvidia_bluefield.run_in_syncd', return_value=(0, b""))
    @mock.patch('config.plugins.nvidia_bluefield.cleanup_dump_files')
    @mock.patch('config.plugins.nvidia_bluefield.get_location_details', return_value=("/var/log/bluefield/", 5))
    @mock.patch('sonic_py_common.device_info.get_sonic_version_info', return_value=ASIC_TYPE_NVDA_BF)
    def test_config_record_cli(
        self,
        m_device_info,
        m_get_location_details,
        m_cleanup_dump_files,
        m_run_in_syncd,
        m_current,
        m_mknod,
        m_docker
    ):
        helper = util_base.UtilHelper()
        helper.load_and_register_plugins(plugins, config.config)
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["platform"].commands["nvidia-bluefield"].commands["sdk"],
            ["config-record", "enabled"]
        )
        f_name = m_mknod.call_args.args[0]
        assert f_name.startswith("/var/log/bluefield/config-record/cfg_record_")
        assert result.exit_code == 0
        assert "Config recording enabled" in result.output
        assert m_run_in_syncd.call_count == 2
        cmd_create = m_run_in_syncd.call_args_list[0].args[0]
        cmd_run = m_run_in_syncd.call_args_list[1].args[0]
        assert 'set_sai_debug_mode on filepath /var/log/bluefield/config-record/cfg_record_' in cmd_create
        assert '/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt' in cmd_run

        m_run_in_syncd.reset_mock()

        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["platform"].commands["nvidia-bluefield"].commands["sdk"],
            ["config-record", "disabled"]
        )
        assert m_run_in_syncd.call_count == 2
        cmd_create = m_run_in_syncd.call_args_list[0].args[0]
        cmd_run = m_run_in_syncd.call_args_list[1].args[0]
        assert 'set_sai_debug_mode' in cmd_create
        assert '/usr/sbin/cli/nasa_cli.py -u --exit_on_failure -l /tmp/nasa_cli_cmd.txt' in cmd_run
        assert result.exit_code == 0
        assert "Config recording disabled" in result.output
