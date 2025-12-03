import pytest
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
