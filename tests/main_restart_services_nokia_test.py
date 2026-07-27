"""
Unit tests for Nokia 7215 / USB management restart helpers in config.main
"""
import builtins
import json
import subprocess
from unittest import mock
from unittest.mock import patch, mock_open

from config.main import (
    get_device_name,
    get_mgmt_interface,
    reset_mgmt_interface_if_usb_not_running,
    _restart_services,
)


def _open_mock_operstate(read_data):
    """Patch only /operstate reads; delegate other opens to the real builtin."""

    def _side_effect(path, *args, **kwargs):
        path_str = path if isinstance(path, str) else str(path)
        if path_str.replace("\\", "/").rstrip("/").endswith("operstate"):
            return mock_open(read_data=read_data)()
        return builtins.open(path, *args, **kwargs)

    return _side_effect


class TestGetDeviceName(object):
    def test_reads_onie_platform(self):
        content = "foo=1\nonie_platform=armhf-nokia_ixs7215_52x-r0\n"
        with patch("builtins.open", mock_open(read_data=content)):
            assert get_device_name() == "armhf-nokia_ixs7215_52x-r0"

    def test_missing_file_returns_none(self):
        with patch("builtins.open", side_effect=OSError("no file")):
            assert get_device_name() is None

    def test_no_onie_line_returns_none(self):
        with patch("builtins.open", mock_open(read_data="foo=bar\n")):
            assert get_device_name() is None


class TestGetMgmtInterface(object):
    def test_parses_first_mgmt_key(self):
        cfg = {"MGMT_INTERFACE": {"eth0|10.0.0.1/24": {}}}
        with patch("builtins.open", mock_open(read_data=json.dumps(cfg))):
            assert get_mgmt_interface() == "eth0"

    def test_empty_mgmt_returns_none(self):
        cfg = {"MGMT_INTERFACE": {}}
        with patch("builtins.open", mock_open(read_data=json.dumps(cfg))):
            assert get_mgmt_interface() is None

    def test_invalid_json_returns_none(self):
        with patch("builtins.open", mock_open(read_data="not json")):
            assert get_mgmt_interface() is None


class TestResetMgmtInterfaceIfUsbNotRunning(object):
    @patch("config.main.subprocess.run")
    @patch("config.main.get_mgmt_interface", return_value=None)
    def test_no_iface_no_subprocess(self, _gm, _sub):
        reset_mgmt_interface_if_usb_not_running()
        _sub.assert_not_called()

    @patch("config.main.subprocess.run")
    @patch("config.main.os.path.realpath", return_value="/sys/devices/platform/eth")
    @patch("config.main.get_mgmt_interface", return_value="eth0")
    def test_skips_non_usb_device(self, _gm, _rp, _sub):
        reset_mgmt_interface_if_usb_not_running()
        _sub.assert_not_called()

    @patch("config.main.subprocess.run")
    @patch("builtins.open", side_effect=_open_mock_operstate("up\n"))
    @patch("config.main.os.path.realpath", return_value="/sys/bus/usb/devices/usb1")
    @patch("config.main.get_mgmt_interface", return_value="eth0")
    def test_skips_when_operstate_up(self, _gm, _rp, _op, _sub):
        reset_mgmt_interface_if_usb_not_running()
        _sub.assert_not_called()

    @patch("config.main.subprocess.run")
    @patch("config.main.click.echo")
    @patch("builtins.open", side_effect=_open_mock_operstate("down\n"))
    @patch("config.main.os.path.realpath", return_value="/sys/bus/usb/devices/usb1")
    @patch("config.main.get_mgmt_interface", return_value="eth0")
    def test_runs_ip_link_when_usb_and_not_up(self, _gm, _rp, _op, _echo, sub):
        reset_mgmt_interface_if_usb_not_running()
        sub.assert_any_call(["ip", "link", "set", "eth0", "down"], check=True)
        sub.assert_any_call(["ip", "link", "set", "eth0", "up"], check=True)

    @patch("config.main.log.log_warning")
    @patch(
        "config.main.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["ip"]),
    )
    @patch("config.main.click.echo")
    @patch("builtins.open", side_effect=_open_mock_operstate("down\n"))
    @patch("config.main.os.path.realpath", return_value="/sys/bus/usb/devices/usb1")
    @patch("config.main.get_mgmt_interface", return_value="eth0")
    def test_logs_warning_on_subprocess_failure(
        self, _gm, _rp, _op, _echo, _sub, log_warning
    ):
        reset_mgmt_interface_if_usb_not_running()
        log_warning.assert_called_once()
        assert "eth0" in str(log_warning.call_args)


class TestRestartServicesNokiaExtension(object):
    @patch("config.main.reset_mgmt_interface_if_usb_not_running")
    @patch("config.main.get_device_name", return_value=None)
    @patch("config.main.clicommon.run_command")
    @patch("config.main.subprocess.check_call")
    @patch("config.main.wait_service_restart_finish")
    @patch("config.main.get_service_finish_timestamp", return_value=0)
    @patch("config.main.click.echo")
    @patch("config.main._wait_for_monit_service_monitored")
    def test_always_calls_usb_mgmt_reset(
        self,
        _monit,
        _echo,
        _gst,
        _wsrf,
        _check,
        run_cmd,
        get_dev,
        reset_usb,
    ):
        _restart_services()
        reset_usb.assert_called_once()
        get_dev.assert_called()

    @patch("config.main.reset_mgmt_interface_if_usb_not_running")
    @patch("config.main.time.sleep", autospec=True)
    @patch("config.main.get_device_name", return_value="armhf-nokia_ixs7215_52x-r0")
    @patch("config.main.clicommon.run_command")
    @patch("config.main.subprocess.check_call")
    @patch("config.main.wait_service_restart_finish")
    @patch("config.main.get_service_finish_timestamp", return_value=0)
    @patch("config.main.click.echo")
    @patch("config.main._wait_for_monit_service_monitored")
    def test_nokia7215_runs_swss_syncd_restart(
        self,
        _monit,
        echo,
        _gst,
        _wsrf,
        _check,
        run_cmd,
        get_dev,
        _sleep,
        reset_usb,
    ):
        _restart_services()
        reset_usb.assert_called_once()
        stop_swss = mock.call(["sudo", "systemctl", "stop", "swss"])
        stop_syncd = mock.call(["sudo", "systemctl", "stop", "syncd"])
        assert stop_swss in run_cmd.call_args_list
        assert stop_syncd in run_cmd.call_args_list
        restart_swss = mock.call(["sudo", "systemctl", "restart", "swss"])
        assert restart_swss in run_cmd.call_args_list
        echo.assert_any_call(
            "ARMHF/Nokia-7215: force restart swss and syncd"
        )
