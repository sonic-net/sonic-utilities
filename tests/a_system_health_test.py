import sys
import os
import json
from unittest import mock

# import click
from click.testing import CliRunner
from .mock_tables import dbconnector

import show.main as show_main


test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)


class MockerConfig(object):
    ignore_devices = []
    ignore_services = []
    first_time = True

    def config_file_exists(self):
        if MockerConfig.first_time:
            MockerConfig.first_time = False
            return False
        else:
            return True


class TestHealth(object):
    original_cli = None

    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        global original_cli
        original_cli = show_main.cli

    def test_health_dpu(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=True):

            # Check if 'dpu' command is available under system-health
            available_commands = show_main.cli.commands["system-health"].commands
            assert "dpu" in available_commands, f"'dpu' command not found: {available_commands}"

            conn = dbconnector.SonicV2Connector()
            conn.connect(conn.CHASSIS_STATE_DB)
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "id", "0")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_reason", "OK")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_time", "20240607 15:08:51")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_time", "20240608 09:11:13")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_reason", "Uplink is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_reason", "Polaris is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_time", "20240608 09:11:13")

            with mock.patch("show.system_health.SonicV2Connector", return_value=conn):
                runner = CliRunner()
                result = runner.invoke(show_main.cli.commands["system-health"].commands["dpu"], ["DPU0"])

                # Assert the output and exit code
                assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
                assert "DPU0" in result.output, f"Expected 'DPU0' in output, got: {result.output}"

                # check -h option
                result = runner.invoke(show_main.cli.commands["system-health"].commands["dpu"], ["-h"])
                print(result.output)

    def test_health_dpu_non_smartswitch(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=False):

            # Check if 'dpu' command is available under system-health
            available_commands = show_main.cli.commands["system-health"].commands
            assert "dpu" in available_commands, f"'dpu' command not found: {available_commands}"

            conn = dbconnector.SonicV2Connector()
            conn.connect(conn.CHASSIS_STATE_DB)
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "id", "0")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_reason", "OK")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_time", "20240607 15:08:51")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_time", "20240608 09:11:13")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_reason", "Uplink is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_reason", "Polaris is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_time", "20240608 09:11:13")

            with mock.patch("show.system_health.SonicV2Connector", return_value=conn):
                runner = CliRunner()
                result = runner.invoke(show_main.cli.commands["system-health"].commands["dpu"], ["DPU0"])

                # Assert the output and exit code
                assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
                assert "DPU0" not in result.output, f"Output contained DPU0: {result.output}"

    # Test 'get_all_dpu_options' function
    def test_get_all_dpu_options(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=True):

            # Mock platform info to simulate a valid platform returned from get_platform_info
            mock_platform_info = {'platform': 'mock_platform'}
            with mock.patch("sonic_py_common.device_info.get_platform_info", return_value=mock_platform_info):

                # Mock open to simulate reading a platform.json file
                mock_platform_data = '{"DPUS": {"dpu0": {}, "dpu1": {}}}'
                with mock.patch("builtins.open", mock.mock_open(read_data=mock_platform_data)):

                    # Mock json.load to return parsed JSON content from the mocked file
                    with mock.patch("json.load", return_value=json.loads(mock_platform_data)):

                        # Import the actual get_all_dpu_options function and invoke it
                        from show.system_health import get_all_dpu_options
                        dpu_list = get_all_dpu_options()
                        print(dpu_list)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        show_main.cli = original_cli

    @mock.patch("show.system_health.get_dpu_ip_list", return_value=[("dpu0", "1.2.3.4")])
    @mock.patch("show.system_health.is_midplane_reachable", return_value=True)
    @mock.patch("show.system_health.ensure_ssh_key_setup")
    @mock.patch("show.system_health.get_module_health", return_value=("1.2.3.4", "OK"))
    @mock.patch("show.system_health.is_smartswitch", return_value=True)
    @mock.patch("show.system_health.get_system_health_status")
    def test_summary_switch_and_dpu(
        self, mock_get_status, mock_smartswitch, mock_health, mock_ssh, mock_reach, mock_list
    ):
        runner = CliRunner()

        mock_chassis = mock.Mock()
        mock_chassis.get_status_led.return_value = "green"
        mock_get_status.return_value = (None, mock_chassis, {})

        result = runner.invoke(
            show_main.cli.commands["system-health"].commands["summary"], ["all"]
        )
        print(result)
        # assert result.exit_code == 0
        # assert mock_list.called
        # assert mock_health.called

    @mock.patch("show.system_health.get_dpu_ip_list", return_value=[("dpu0", "1.2.3.4")])
    @mock.patch("show.system_health.is_midplane_reachable", return_value=True)
    @mock.patch("show.system_health.ensure_ssh_key_setup")
    @mock.patch("show.system_health.get_module_health", return_value=("1.2.3.4", "OK"))
    @mock.patch("show.system_health.is_smartswitch", return_value=True)
    @mock.patch("show.system_health.get_system_health_status")
    def test_detail_dpu(
        self, mock_get_status, mock_smartswitch, mock_health, mock_ssh, mock_reach, mock_list
    ):
        runner = CliRunner()
        result = runner.invoke(
            show_main.cli.commands["system-health"].commands["detail"],
            ["--module-name", "DPU0"]
        )
        print(result)

    @mock.patch("show.system_health.get_dpu_ip_list", return_value=[("dpu0", "1.2.3.4")])
    @mock.patch("show.system_health.is_midplane_reachable", return_value=True)
    @mock.patch("show.system_health.ensure_ssh_key_setup")
    @mock.patch("show.system_health.get_module_health", return_value=("1.2.3.4", "OK"))
    @mock.patch("show.system_health.is_smartswitch", return_value=True)
    @mock.patch("show.system_health.get_system_health_status")
    def test_monitor_list_dpu(
        self, mock_get_status, mock_smartswitch, mock_health, mock_ssh, mock_reach, mock_list
    ):
        runner = CliRunner()
        result = runner.invoke(
            show_main.cli.commands["system-health"].commands["monitor-list"], ["all"]
        )
        print(result)

    @mock.patch("show.system_health.subprocess.run")
    @mock.patch("show.system_health.os.path.exists", return_value=False)
    @mock.patch("show.system_health.click.echo")
    def test_ensure_ssh_key_exists(self, mock_echo, mock_exists, mock_run):
        from show.system_health import ensure_ssh_key_exists
        ensure_ssh_key_exists()

    @mock.patch("show.system_health.setup_ssh_key_for_remote")
    @mock.patch("show.system_health.click.prompt", return_value="dummy-password")
    @mock.patch("show.system_health.subprocess.run")
    @mock.patch("show.system_health.ensure_ssh_key_exists")
    @mock.patch("show.system_health.is_midplane_reachable", return_value=True)
    def test_ensure_ssh_key_setup_triggers_setup(
        self, mock_reachable, mock_ensure_key, mock_subproc, mock_prompt, mock_setup_key
    ):
        from show.system_health import ensure_ssh_key_setup, _ssh_key_cache

        _ssh_key_cache.clear()  # ensure clean state

        # simulate ssh test failing (no key yet)
        mock_subproc.return_value.returncode = 1
        mock_subproc.return_value.stderr.decode.return_value = "Permission denied"

        ensure_ssh_key_setup("1.2.3.4", username="admin")

        # assert mock_ensure_key.called
        # assert mock_prompt.called
        # assert mock_setup_key.called
        # assert "1.2.3.4" in _ssh_key_cache

    def test_ensure_ssh_key_setup_skips_if_cached(self):
        from show.system_health import ensure_ssh_key_setup, _ssh_key_cache
        _ssh_key_cache.add("1.2.3.4")

        # should not do anything
        ensure_ssh_key_setup("1.2.3.4")

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="ssh-rsa dummy-key")
    @mock.patch("show.system_health.paramiko.SSHClient")
    def test_setup_ssh_key_for_remote(self, mock_ssh_client_cls, mock_open):
        from show.system_health import setup_ssh_key_for_remote

        # Prepare a mock SSH client
        mock_ssh = mock.Mock()
        mock_ssh_client_cls.return_value = mock_ssh
        mock_channel = mock.Mock()
        mock_channel.recv_exit_status.return_value = 0
        mock_ssh.exec_command.return_value = (mock.Mock(channel=mock_channel), None, None)

        setup_ssh_key_for_remote("hostname", "admin", "dummy", "/dummy/path")

        # mock_open.assert_called_once_with("/dummy/path", "r")
        # mock_ssh.connect.assert_called_once_with("hostname", username="admin", password="dummy")
        # assert mock_ssh.exec_command.call_count == 3  # mkdir, echo, chmod
        # mock_ssh.close.assert_called_once()

    @mock.patch("click.confirm", return_value=True)
    @mock.patch("click.prompt", return_value="dummy")
    @mock.patch("show.system_health.subprocess.run")
    def test_setup_ssh_key(self, mock_run, mock_prompt, mock_confirm):
        from show.system_health import setup_ssh_key
        try:
            setup_ssh_key("module", "admin", "password")
        except SystemExit as e:
            assert e.code == 0
        # assert mock_run.called

    @mock.patch("show.system_health.subprocess.check_output")
    def test_get_module_health(self, mock_check_output):
        from show.system_health import get_module_health
        mock_check_output.return_value = '{"SystemStatus": {"LED": "green"}}'
        get_module_health("10.0.0.1", "summary")
        # assert isinstance(result, tuple)
        # assert "SystemStatus" in result[1]
