import os
import sys
import textwrap
from unittest import mock

import pytest
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)
import show.main as show


@pytest.fixture(scope='class')
def config_env():
    os.environ["UTILITIES_UNIT_TESTING"] = "1"

    yield

    os.environ["UTILITIES_UNIT_TESTING"] = "0"


@pytest.mark.usefixtures('config_env')
class TestShowPlatform(object):
    TEST_PLATFORM = "x86_64-mlnx_msn2700-r0"
    TEST_HWSKU = "Mellanox-SN2700"
    TEST_ASIC_TYPE = "mellanox"
    TEST_ASIC_COUNT = 1
    TEST_SERIAL = "MT1822K07815"
    TEST_MODEL = "MSN2700-CS2FO"
    TEST_REV = "A1"

    # Test 'show platform summary'
    def test_summary(self):
        expected_output = """\
            Platform: {}
            HwSKU: {}
            ASIC: {}
            ASIC Count: {}
            Serial Number: {}
            Model Number: {}
            Hardware Revision: {}
            """.format(self.TEST_PLATFORM, self.TEST_HWSKU, self.TEST_ASIC_TYPE, self.TEST_ASIC_COUNT, self.TEST_SERIAL, self.TEST_MODEL, self.TEST_REV)

        with mock.patch("sonic_py_common.device_info.get_platform_info",
                return_value={"platform": self.TEST_PLATFORM, "hwsku": self.TEST_HWSKU, "asic_type": self.TEST_ASIC_TYPE, "asic_count": self.TEST_ASIC_COUNT}):
            with mock.patch("show.platform.get_chassis_info",
                            return_value={"serial": self.TEST_SERIAL, "model": self.TEST_MODEL, "revision": self.TEST_REV}):
                result = CliRunner().invoke(show.cli.commands["platform"].commands["summary"], [])
                assert result.output == textwrap.dedent(expected_output)


class TestShowPlatformPsu(object):
    """
        Note: `show platform psustatus` simply calls the `psushow` utility and
        passes a variety of options. Here we test that the utility is called
        with the appropriate option(s). The functionality of the underlying
        `psushow` utility is expected to be tested by a separate suite of unit tests
    """
    def test_all_psus(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], [])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with(['psushow', '-s'], display_cmd=False)

    def test_all_psus_json(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--json'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with(['psushow', '-s', '-j'], display_cmd=False)

    def test_single_psu(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--index=1'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with(['psushow', '-s', '-i', '1'], display_cmd=False)

    def test_single_psu_json(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--index=1', '--json'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with(['psushow', '-s', '-i', '1', '-j'], display_cmd=False)

    def test_verbose(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--verbose'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with(['psushow', '-s'], display_cmd=True)


class TestShowPlatformSsdhealth(object):
    # Test 'show platform ssdhealth'
    @mock.patch('utilities_common.cli.run_command')
    def test_ssdhealth(self, mock_run_command):
        result = CliRunner().invoke(show.cli.commands['platform'].commands['ssdhealth'], ["/dev/nvme0n1", '--verbose'])
        assert result.exit_code == 0, result.output
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with(['sudo', 'ssdutil', '-d', '/dev/nvme0n1', '-v'], display_cmd=True)

    @mock.patch('utilities_common.cli.run_command')
    @mock.patch('sonic_py_common.device_info.get_platform_json_data')
    def test_ssdhealth_default_device(self, mock_plat_json, mock_run_command):
        mock_plat_json.return_value = {
            "chassis": {
                 "name": "mock_platform"
            }
        }

        CliRunner().invoke(show.cli.commands['platform'].commands['ssdhealth'], ['--verbose'])
        mock_run_command.assert_called_with(['sudo', 'ssdutil', '-v'], display_cmd=True)

        mock_plat_json.return_value = {
            "chassis": {
                "name": "mock_platform2",
                "disk":  {
                    "device": "/dev/nvme0n1"
                }
            }
        }
        CliRunner().invoke(show.cli.commands['platform'].commands['ssdhealth'], ['--verbose'])
        mock_plat_json.assert_called_with()
        mock_run_command.assert_called_with(['sudo', 'ssdutil', '-d', '/dev/nvme0n1', '-v'], display_cmd=True)
