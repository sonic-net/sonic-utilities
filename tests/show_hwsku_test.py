import os
import sys
from unittest.mock import patch

from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import show.show_hwsku as show_hwsku  # noqa: E402


class TestShowHwskuHelpers:
    @patch('utilities_common.hwsku.device_info.get_platform')
    def test_get_available_hwskus(self, mock_platform, tmp_path):
        """Test getting available HWSKUs successfully"""
        platform = tmp_path / 'x86_64-vendor_switch-r0'
        for name in ('Vendor-Switch-32x400G', 'Vendor-Switch-64x200G'):
            (platform / name).mkdir(parents=True)
            (platform / name / 'port_config.ini').touch()
        (platform / 'pddf').mkdir()
        (platform / 'file.txt').touch()
        mock_platform.return_value = platform.name

        with patch('utilities_common.hwsku.HOST_DEVICE_PATH', str(tmp_path)), \
                patch('sonic_py_common.device_info.HOST_DEVICE_PATH', str(tmp_path)), \
                patch('sonic_py_common.device_info.CONTAINER_PLATFORM_PATH', str(tmp_path / 'absent')):
            result = show_hwsku.get_available_hwskus()

        assert sorted(result) == ['Vendor-Switch-32x400G', 'Vendor-Switch-64x200G']

    @patch('utilities_common.hwsku.os.listdir')
    @patch('utilities_common.hwsku.device_info.get_platform')
    def test_get_available_hwskus_no_platform(self, mock_platform, mock_listdir):
        """Test get_available_hwskus when platform cannot be determined"""
        mock_platform.return_value = None

        result = show_hwsku.get_available_hwskus()

        assert result == []
        mock_listdir.assert_not_called()

    @patch('utilities_common.hwsku.os.path.isdir')
    @patch('utilities_common.hwsku.device_info.get_platform')
    def test_get_available_hwskus_platform_path_not_exists(self, mock_platform, mock_isdir):
        """Test get_available_hwskus when platform path doesn't exist"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_isdir.return_value = False

        result = show_hwsku.get_available_hwskus()

        assert result == []

    @patch('utilities_common.hwsku.os.listdir')
    @patch('utilities_common.hwsku.os.path.isdir')
    @patch('utilities_common.hwsku.device_info.get_platform')
    def test_get_available_hwskus_oserror(self, mock_platform, mock_isdir, mock_listdir):
        """Test get_available_hwskus handles OSError gracefully"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_isdir.return_value = True
        mock_listdir.side_effect = OSError("Permission denied")

        result = show_hwsku.get_available_hwskus()

        assert result == []


class TestShowHwskuProfilesCommand:
    @patch('show.show_hwsku.device_info.get_hwsku')
    @patch('show.show_hwsku.get_available_hwskus')
    @patch('show.show_hwsku.device_info.get_platform')
    def test_profiles_success(self, mock_platform, mock_hwskus, mock_current_hwsku):
        """Test show hwsku profiles command with successful output"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G', 'Vendor-Switch-256x200G']
        mock_current_hwsku.return_value = 'Vendor-Switch'

        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles'])

        assert result.exit_code == 0
        assert 'Platform: x86_64-vendor_switch-r0' in result.output
        assert 'Available HWSKU Profiles:' in result.output
        assert '* Vendor-Switch (current)' in result.output
        assert '- Vendor-Switch-128x400G' in result.output
        assert '- Vendor-Switch-256x200G' in result.output

    @patch('show.show_hwsku.device_info.get_platform')
    def test_profiles_no_platform(self, mock_platform):
        """Test show hwsku profiles when platform cannot be determined"""
        mock_platform.return_value = None

        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles'])

        assert result.exit_code == 0
        assert 'Error: Unable to determine platform' in result.output

    @patch('show.show_hwsku.get_available_hwskus')
    @patch('show.show_hwsku.device_info.get_platform')
    def test_profiles_no_hwskus(self, mock_platform, mock_hwskus):
        """Test show hwsku profiles when no HWSKUs are found"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_hwskus.return_value = []

        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles'])

        assert result.exit_code == 0
        assert "No HWSKUs found for platform 'x86_64-vendor_switch-r0'" in result.output

    @patch('show.show_hwsku.device_info.get_hwsku')
    @patch('show.show_hwsku.get_available_hwskus')
    @patch('show.show_hwsku.device_info.get_platform')
    def test_profiles_no_current_hwsku(self, mock_platform, mock_hwskus, mock_current_hwsku):
        """Test show hwsku profiles when current HWSKU cannot be determined"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G']
        mock_current_hwsku.return_value = None

        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles'])

        assert result.exit_code == 0
        assert 'Platform: x86_64-vendor_switch-r0' in result.output
        assert 'Available HWSKU Profiles:' in result.output
        # All should be listed without current marker
        assert '- Vendor-Switch' in result.output
        assert '- Vendor-Switch-128x400G' in result.output
        assert '(current)' not in result.output

    @patch('show.show_hwsku.device_info.get_hwsku')
    @patch('show.show_hwsku.get_available_hwskus')
    @patch('show.show_hwsku.device_info.get_platform')
    def test_profiles_sorted_output(self, mock_platform, mock_hwskus, mock_current_hwsku):
        """Test that profiles are displayed in sorted order"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        # Return unsorted list
        mock_hwskus.return_value = ['Vendor-Switch-256x200G', 'Vendor-Switch', 'Vendor-Switch-128x400G']
        mock_current_hwsku.return_value = 'Vendor-Switch'

        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles'])

        assert result.exit_code == 0

        # Check that they appear in sorted order in the output
        output_lines = result.output.split('\n')
        hwsku_lines = [
            line for line in output_lines if line.strip().startswith(('-', '*'))
        ]

        # Should be in alphabetical order
        assert len(hwsku_lines) == 3
        assert 'Vendor-Switch' in hwsku_lines[0]
        assert 'Vendor-Switch-128x400G' in hwsku_lines[1]
        assert 'Vendor-Switch-256x200G' in hwsku_lines[2]

    @patch('show.show_hwsku.device_info.get_hwsku')
    @patch('show.show_hwsku.get_available_hwskus')
    @patch('show.show_hwsku.device_info.get_platform')
    def test_profiles_current_hwsku_not_in_available(self, mock_platform, mock_hwskus, mock_current_hwsku):
        """Test when current HWSKU is not in the available list (edge case)"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G']
        mock_current_hwsku.return_value = 'Vendor-Switch-OLD'  # Not in available list

        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles'])

        assert result.exit_code == 0
        assert 'Platform: x86_64-vendor_switch-r0' in result.output
        # All should be listed without current marker since current is not in list
        assert '- Vendor-Switch' in result.output
        assert '- Vendor-Switch-128x400G' in result.output
        assert '(current)' not in result.output

    def test_hwsku_group_help(self):
        """Test that the hwsku group shows help correctly"""
        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['--help'])

        assert result.exit_code == 0
        assert 'Show hardware SKU information' in result.output
        assert 'profiles' in result.output

    def test_profiles_help(self):
        """Test that the profiles command shows help correctly"""
        runner = CliRunner()
        result = runner.invoke(show_hwsku.hwsku, ['profiles', '--help'])

        assert result.exit_code == 0
        assert 'Show available hardware SKU profiles' in result.output
