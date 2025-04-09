import sys
import os
import json
from unittest import mock

# import click
from click.testing import CliRunner
from .mock_tables import dbconnector

import show.main as show

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
        original_cli = show.cli

    def test_health_dpu(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=True):

            # Check if 'dpu' command is available under system-health
            available_commands = show.cli.commands["system-health"].commands
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
                result = runner.invoke(show.cli.commands["system-health"].commands["dpu"], ["DPU0"])

                # Assert the output and exit code
                assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
                assert "DPU0" in result.output, f"Expected 'DPU0' in output, got: {result.output}"

                # check -h option
                result = runner.invoke(show.cli.commands["system-health"].commands["dpu"], ["-h"])
                print(result.output)

    def test_health_dpu_non_smartswitch(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=False):

            # Check if 'dpu' command is available under system-health
            available_commands = show.cli.commands["system-health"].commands
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
                result = runner.invoke(show.cli.commands["system-health"].commands["dpu"], ["DPU0"])

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
        show.cli = original_cli

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

        # mock chassis.get_status_led()
        mock_chassis = mock.Mock()
        mock_chassis.get_status_led.return_value = "green"
        mock_get_status.return_value = (None, mock_chassis, {})

        result = runner.invoke(
            show.cli.commands["system-health"].commands["summary"], ["all"]
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
            show.cli.commands["system-health"].commands["detail"],
            ["--module-name", "DPU0"]
        )
        print(result)
        # assert result.exit_code == 0
        # assert mock_health.called
        # assert mock_list.called

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
            show.cli.commands["system-health"].commands["monitor-list"], ["all"]
        )
        print(result)
        # assert result.exit_code == 0
        # assert mock_list.called
        # assert mock_health.called


class TestSystemHealthSSH(object):

    @mock.patch("show.system_health.subprocess.run")
    @mock.patch("show.system_health.os.path.exists", return_value=False)
    @mock.patch("show.system_health.click.echo")
    def test_ensure_ssh_key_exists_generates_key(mock_echo, mock_exists, mock_run):
        from show.system_health import ensure_ssh_key_exists
        # from show.system_health import ensure_ssh_key_exists, DEFAULT_KEY_PATH

        ensure_ssh_key_exists()

        # mock_echo.assert_called_with("SSH key not found. Generating...")
        # mock_run.assert_called_once_with(
        #     ["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", DEFAULT_KEY_PATH],
        #     check=True, stdout=mock.ANY, stderr=mock.ANY
        # )
