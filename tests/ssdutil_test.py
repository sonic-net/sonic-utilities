import sys
import argparse
from unittest.mock import patch, MagicMock
import sonic_platform_base  # noqa: F401

sys.modules['sonic_platform'] = MagicMock()
sys.modules['sonic_platform_base.sonic_ssd.ssd_generic'] = MagicMock()

import ssdutil.main as ssdutil  # noqa: E402


class Ssd():

    def get_model(self):
        return 'SkyNet'

    def get_firmware(self):
        return 'ABC'

    def get_serial(self):
        return 'T1000'

    def get_health(self):
        return 5

    def get_temperature(self):
        return 3000

    def get_vendor_output(self):
        return 'SONiC Test'


class TestSsdutil:

    @patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', MagicMock(return_value=("test_path", "")))  # noqa: E501
    @patch('os.geteuid', MagicMock(return_value=0))
    def test_sonic_storage_path(self):

        with patch('argparse.ArgumentParser.parse_args', MagicMock()) as mock_args:  # noqa: E501
            sys.modules['sonic_platform_base.sonic_storage.ssd'] = MagicMock(return_value=Ssd())  # noqa: E501
            mock_args.return_value = argparse.Namespace(device='/dev/sda', verbose=True, vendor=True)  # noqa: E501
            ssdutil.ssdutil()
