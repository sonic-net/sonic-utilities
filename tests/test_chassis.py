import pytest
import subprocess
from unittest import mock
from utilities_common import chassis


class TestChassis:
    @pytest.fixture
    def mock_device_info(self):
        with mock.patch('utilities_common.chassis.device_info') as mock_device_info:
            yield mock_device_info

    def test_is_smartswitch(self, mock_device_info):
        mock_device_info.is_smartswitch = mock.Mock(return_value=True)
        assert chassis.is_smartswitch() == True  # noqa: E712

        mock_device_info.is_smartswitch = mock.Mock(return_value=False)
        assert chassis.is_smartswitch() == False  # noqa: E712

    def test_is_dpu(self, mock_device_info):
        mock_device_info.is_dpu = mock.Mock(return_value=True)
        assert chassis.is_dpu() == True  # noqa: E712

        mock_device_info.is_dpu = mock.Mock(return_value=False)
        assert chassis.is_dpu() == False  # noqa: E712

    def test_get_num_dpus(self, mock_device_info):
        mock_device_info.get_num_dpus = mock.Mock(return_value=4)
        assert chassis.get_num_dpus() == 4

        del mock_device_info.get_num_dpus
        assert chassis.get_num_dpus() == 0  # noqa: E712

    @mock.patch('utilities_common.chassis.subprocess.check_output')
    def test_is_midplane_reachable(self, mock_check_output):
        mock_check_output.return_value = b'PING response'
        assert chassis.is_midplane_reachable('192.168.0.1') is True

        mock_check_output.side_effect = subprocess.CalledProcessError(1, 'ping')
        assert chassis.is_midplane_reachable('192.168.0.2') is False

    def test_get_dpu_ip_list(self, mock_device_info):
        platform_json = {
            "DHCP_SERVER_IPV4_PORT": {
                "bridge-midplane|dpu0": {"ips": ["169.254.200.1"]},
                "bridge-midplane|dpu1": {"ips": ["169.254.200.2"]}
            }
        }
        mock_device_info.get_platform_json_data.return_value = platform_json

        # Test with specific DPU list
        result = chassis.get_dpu_ip_list(["dpu0"])
        assert result == [("dpu0", "169.254.200.1")]

        # Test with "all"
        result = chassis.get_dpu_ip_list("all")
        assert result == [
            ("dpu0", "169.254.200.1"),
            ("dpu1", "169.254.200.2")
        ]

        # Test with missing platform data
        mock_device_info.get_platform_json_data.return_value = None
        result = chassis.get_dpu_ip_list("all")
        assert result == []
