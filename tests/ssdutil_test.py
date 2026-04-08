import os
import pytest
import sys
import argparse
from unittest.mock import patch, MagicMock
import sonic_platform_base  # noqa: F401


tests_path = os.path.dirname(os.path.abspath(__file__))
mocked_libs_path = os.path.join(tests_path, "mocked_libs")


@pytest.fixture(scope="function")
def load_ssdutil_with_mocked_libs(monkeypatch):
    """Fixture to load ssdutil with mocked psutil and blkinfo modules.

    Loads the ssdutil module with internal fake/mocked psutil and blkinfo modules.
    The test case needs to import ssdutil to access the loaded module.
    """
    with monkeypatch.context() as temp_mp:
        # Temporary monkeypatch out existing psutil and blkinfo, and patch in path to the mocked
        # implementations, while loading ssdutil.
        temp_mp.delitem(sys.modules, 'psutil', raising=False)
        temp_mp.delitem(sys.modules, 'blkinfo', raising=False)
        temp_mp.syspath_prepend(mocked_libs_path)
        # Long-lived monkeypatch of ssdutil module with the mocked psutil and blkinfo modules.
        monkeypatch.delitem(sys.modules, 'ssdutil.main', raising=False)
        import ssdutil.main  # noqa
    yield


sys.modules['sonic_platform'] = MagicMock()
sys.modules['sonic_platform_base.sonic_ssd.ssd_generic'] = MagicMock()


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

    @patch('os.geteuid', MagicMock(return_value=0))
    @patch('os.stat', MagicMock(st_rdev=2049))
    @patch('os.major', MagicMock(return_value=8))
    def test_get_default_disk(self, load_ssdutil_with_mocked_libs):
        import ssdutil.main as ssdutil  # See load_ssdutil_with_mocked_libs fixture.

        (default_device, disk_type) = ssdutil.get_default_disk()

        assert default_device == "/dev/sdx"
        assert disk_type == 'usb'

    @patch('os.geteuid', MagicMock(return_value=0))
    @patch('os.stat', MagicMock(st_rdev=2049))
    @patch('os.major', MagicMock(return_value=8))
    @patch('ssdutil.main.psutil.disk_partitions', MagicMock(return_value=None))
    def test_get_default_disk_none_partitions(self, load_ssdutil_with_mocked_libs):
        import ssdutil.main as ssdutil  # See load_ssdutil_with_mocked_libs fixture.

        (default_device, disk_type) = ssdutil.get_default_disk()

        assert default_device == "/dev/sda"
        assert disk_type is None

    def test_is_number_valueerror(self, load_ssdutil_with_mocked_libs):
        import ssdutil.main as ssdutil  # See load_ssdutil_with_mocked_libs fixture.

        outcome = ssdutil.is_number("nope")
        assert outcome is False

    @patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', MagicMock(return_value=("test_path", "")))  # noqa: E501
    @patch('os.geteuid', MagicMock(return_value=0))
    @patch('os.stat', MagicMock(st_rdev=2049))
    @patch('os.major', MagicMock(return_value=8))
    def test_sonic_storage_path(self, load_ssdutil_with_mocked_libs):
        import ssdutil.main as ssdutil  # See load_ssdutil_with_mocked_libs fixture.

        with patch('argparse.ArgumentParser.parse_args', MagicMock()) as mock_args:  # noqa: E501
            sys.modules['sonic_platform_base.sonic_storage.ssd'] = MagicMock(return_value=Ssd())  # noqa: E501
            mock_args.return_value = argparse.Namespace(device='/dev/sda', verbose=True, vendor=True)  # noqa: E501
            ssdutil.ssdutil()
