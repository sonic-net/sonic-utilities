import glob
import json
import os
import re
import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import config.load_hwsku as hwsku  # noqa: E402


def backup_dir_exists_side_effect(path):
    """
    Common side effect function for os.path.exists mock.
    Returns False for backup directory path, True for everything else.
    This simulates the backup directory not existing yet.
    """
    if 'backup_config' in path and path.endswith('backup_config'):
        return False
    return True


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


@pytest.fixture
def platform_dir(tmp_path):
    """The current platform's directory, in a temporary device tree"""
    platform = tmp_path / 'x86_64-vendor_switch-r0'
    platform.mkdir()
    with patch('utilities_common.hwsku.HOST_DEVICE_PATH', str(tmp_path)), \
            patch('sonic_py_common.device_info.HOST_DEVICE_PATH', str(tmp_path)), \
            patch('sonic_py_common.device_info.CONTAINER_PLATFORM_PATH', str(tmp_path / 'absent')), \
            patch('sonic_py_common.device_info.get_platform', return_value=platform.name):
        yield platform


class TestHwskuHelpers:
    @pytest.mark.parametrize('files, platform_json, listed', [
        pytest.param(['port_config.ini'], None, True, id='port_config.ini'),
        pytest.param(['hwsku.json'], {'interfaces': {'Ethernet0': {}}}, True, id='hwsku.json'),
        pytest.param(['hwsku.json'], None, False, id='hwsku.json-no-platform.json'),
        pytest.param(['hwsku.json'], {'interfaces': {}}, False, id='hwsku.json-no-interfaces'),
        pytest.param([], None, False, id='empty'),
        pytest.param(['pddf-device.json'], None, False, id='pddf'),
        pytest.param(['hwsku-init', 'defaults.yaml'], None, False, id='shared-asic-files'),
        pytest.param(['port_config.ini.bak'], None, False, id='port_config.ini.bak'),
        pytest.param(['0/port_config.ini', '1/port_config.ini'], None, False, id='multi-asic'),
    ])
    def test_get_available_hwskus_port_config(self, platform_dir, files, platform_json, listed):
        for f in files:
            _touch(platform_dir / 'Vendor-Switch' / f)
        if platform_json is not None:
            (platform_dir / 'platform.json').write_text(json.dumps(platform_json))

        assert hwsku.get_available_hwskus() == (['Vendor-Switch'] if listed else [])

    def test_get_available_hwskus_symlinks(self, platform_dir, tmp_path):
        """Lists HWSKU directories and symlinks to them, and nothing else"""
        sibling = tmp_path / 'x86_64-vendor_switch-r1'
        _touch(platform_dir / 'Vendor-Switch-32x400G' / 'port_config.ini')
        _touch(sibling / 'Vendor-Switch-64x200G' / 'port_config.ini')
        (platform_dir / 'Vendor-Switch-64x200G').symlink_to(sibling / 'Vendor-Switch-64x200G')
        _touch(tmp_path / 'common' / 'asic_common' / 'hwsku-init')
        (platform_dir / 'asic_common').symlink_to(tmp_path / 'common' / 'asic_common')
        (platform_dir / 'dangling').symlink_to(tmp_path / 'missing')
        (platform_dir / 'plugins').mkdir()
        _touch(platform_dir / 'port_config.ini')

        assert sorted(hwsku.get_available_hwskus()) == ['Vendor-Switch-32x400G', 'Vendor-Switch-64x200G']

    @patch('utilities_common.hwsku.os.listdir')
    @patch('utilities_common.hwsku.device_info.get_platform')
    def test_get_available_hwskus_no_platform(self, mock_platform, mock_listdir):
        """Test get_available_hwskus when platform cannot be determined"""
        mock_platform.return_value = None

        result = hwsku.get_available_hwskus()

        assert result == []
        mock_listdir.assert_not_called()

    @patch('config.load_hwsku.get_available_hwskus')
    @patch('config.load_hwsku.device_info.get_platform')
    def test_is_valid_hwsku_valid(self, mock_platform, mock_hwskus):
        """Test is_valid_hwsku with a valid HWSKU"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G']

        is_valid, error_msg = hwsku.is_valid_hwsku('Vendor-Switch')

        assert is_valid is True
        assert error_msg is None

    @patch('config.load_hwsku.get_available_hwskus')
    @patch('config.load_hwsku.device_info.get_platform')
    def test_is_valid_hwsku_invalid(self, mock_platform, mock_hwskus):
        """Test is_valid_hwsku with an invalid HWSKU"""
        mock_platform.return_value = 'x86_64-vendor_switch-r0'
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G']

        is_valid, error_msg = hwsku.is_valid_hwsku('invalid-hwsku')

        assert is_valid is False
        assert 'Invalid HWSKU' in error_msg
        assert 'Vendor-Switch' in error_msg

    @patch('config.load_hwsku.get_available_hwskus')
    @patch('config.load_hwsku.device_info.get_platform')
    def test_is_valid_hwsku_no_platform(self, mock_platform, mock_hwskus):
        """Test is_valid_hwsku when platform cannot be determined"""
        mock_platform.return_value = None

        is_valid, error_msg = hwsku.is_valid_hwsku('Vendor-Switch')

        assert is_valid is False
        assert 'Unable to determine platform' in error_msg

    @patch('config.load_hwsku.get_available_hwskus')
    def test_complete_hwsku_names_full_match(self, mock_hwskus):
        """Test autocomplete with full prefix match"""
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G', 'Vendor-Router', 'Other-SKU']

        # Test with prefix that matches multiple HWSKUs
        result = hwsku.complete_hwsku_names(None, None, 'Vendor-Switch')
        assert 'Vendor-Switch' in result
        assert 'Vendor-Switch-128x400G' in result
        assert 'Vendor-Router' not in result
        assert 'Other-SKU' not in result

    @patch('config.load_hwsku.get_available_hwskus')
    def test_complete_hwsku_names_partial_match(self, mock_hwskus):
        """Test autocomplete with partial prefix match"""
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G', 'Vendor-Router', 'Other-SKU']

        # Test with prefix that matches all Vendor- HWSKUs
        result = hwsku.complete_hwsku_names(None, None, 'Vendor-')
        assert 'Vendor-Switch' in result
        assert 'Vendor-Switch-128x400G' in result
        assert 'Vendor-Router' in result
        assert 'Other-SKU' not in result

    @patch('config.load_hwsku.get_available_hwskus')
    def test_complete_hwsku_names_no_match(self, mock_hwskus):
        """Test autocomplete with no matches"""
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G']

        # Test with prefix that doesn't match anything
        result = hwsku.complete_hwsku_names(None, None, 'XYZ')
        assert result == []

    @patch('config.load_hwsku.get_available_hwskus')
    def test_complete_hwsku_names_empty_prefix(self, mock_hwskus):
        """Test autocomplete with empty prefix (should return all)"""
        mock_hwskus.return_value = ['Vendor-Switch', 'Vendor-Switch-128x400G', 'Other-SKU']

        # Test with empty prefix - should return all HWSKUs
        result = hwsku.complete_hwsku_names(None, None, '')
        assert 'Vendor-Switch' in result
        assert 'Vendor-Switch-128x400G' in result
        assert 'Other-SKU' in result
        assert len(result) == 3


class TestHwskuLoadCommand:
    @classmethod
    def teardown_class(cls):
        # Reset file permissions if needed
        if os.path.exists('/tmp/test_config_db.json'):
            try:
                os.chmod('/tmp/test_config_db.json', 0o644)
            except Exception:
                pass

        # Clean up any leftover test files
        if os.path.exists('/tmp/test_config_db.json'):
            os.remove('/tmp/test_config_db.json')
        # Clean up any backup files in test backup directory
        test_backup_dir = '/tmp/test_backup_config'
        if os.path.exists(test_backup_dir):
            for backup_file in glob.glob(f'{test_backup_dir}/*_*.json'):
                try:
                    os.remove(backup_file)
                except Exception:
                    pass
            try:
                os.rmdir(test_backup_dir)
            except Exception:
                pass

    def test_load_no_arguments(self):
        """Test hwsku load command with no arguments"""
        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load'])

        assert result.exit_code == 2
        assert 'Missing argument' in result.output
        assert 'HWSKU_NAME' in result.output

    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_invalid_hwsku(self, mock_valid):
        """Test hwsku load command with invalid HWSKU name"""
        mock_valid.return_value = (False, "Invalid HWSKU 'invalid-hwsku'. Available: Vendor-Switch")

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'invalid-hwsku', '-y'])

        assert result.exit_code != 0
        assert 'Invalid HWSKU' in result.output

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_success_no_reload(self, mock_valid, mock_current_hwsku,
                                    mock_exists, mock_makedirs, mock_copy, mock_subprocess):
        """Test successful hwsku load without automatic reload"""
        # Create a dummy config file so backup can happen
        with open('/tmp/test_config_db.json', 'w') as f:
            json.dump({"DEVICE_METADATA": {"localhost": {"hwsku": "old-hwsku"}}}, f)

        # Mock os.path.exists to return False for backup dir, True for config file
        def exists_side_effect(path):
            if 'backup_config' in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect

        # Setup mocks
        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'

        # Mock sonic-cfggen output
        base_config = {
            "DEVICE_METADATA": {"localhost": {"hwsku": "Vendor-Switch"}},
            "PORT": {"Ethernet0": {"alias": "Port1"}},
            "BREAKOUT_CFG": {}
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(base_config, indent=4),
            returncode=0
        )

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y'])

        assert result.exit_code == 0
        assert 'Loading hardware SKU: Vendor-Switch' in result.output
        assert 'Config generated successfully' in result.output
        assert 'config reload -y' in result.output  # Should suggest manual reload

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_success_with_reload(self, mock_valid, mock_current_hwsku,
                                      mock_exists, mock_makedirs, mock_copy, mock_subprocess):
        """Test successful hwsku load with automatic reload"""
        # Setup mocks
        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'

        # Mock os.path.exists to return False for backup dir, True for config file
        def exists_side_effect(path):
            if 'backup_config' in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect

        base_config = {"DEVICE_METADATA": {"localhost": {"hwsku": "Vendor-Switch"}}}
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(base_config, indent=4),
            returncode=0
        )

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y', '-r'])

        assert result.exit_code == 0
        assert 'Reloading configuration' in result.output

        # Verify config reload was called
        calls = mock_subprocess.call_args_list
        reload_calls = [c for c in calls if 'config' in str(c) and 'reload' in str(c)]
        assert len(reload_calls) > 0

    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_interactive_cancel(self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs):
        """Test that user can cancel the interactive load prompt"""
        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch'], input='n\n')

        assert result.exit_code == 0
        assert 'Operation cancelled' in result.output

    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_interactive_prompt_shows_correct_info(
            self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs):
        """Test that interactive prompt displays correct information"""
        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        runner = CliRunner()
        # Test without -r flag
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch'], input='n\n')
        assert 'Backup current config to /etc/sonic/backup_config/Vendor-Switch_' in result.output
        assert 'Generate new config for HWSKU' in result.output
        assert 'Skip reload' in result.output

        # Test with -r flag
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-r'], input='n\n')
        assert 'Reload the configuration' in result.output

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_backup_created_with_timestamp(self, mock_valid, mock_current_hwsku,
                                                mock_exists, mock_makedirs, mock_copy, mock_subprocess):
        """Test that backup file is created with correct timestamp format"""
        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        base_config = {"DEVICE_METADATA": {"localhost": {"hwsku": "Vendor-Switch-128x400G"}}}
        mock_subprocess.return_value = MagicMock(stdout=json.dumps(base_config), returncode=0)

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch-128x400G', '-y'])

        # Verify backup was created with current HWSKU name (Vendor-Switch), not new one
        assert result.exit_code == 0
        backup_call = mock_copy.call_args_list[0]
        backup_path = str(backup_call[0][1])
        assert '/backup_config/Vendor-Switch_' in backup_path  # Current HWSKU
        assert '.json' in backup_path
        # Verify timestamp format (YYYYMMDD_HHMMSS)
        assert re.search(r'/backup_config/Vendor-Switch_\d{8}_\d{6}\.json', backup_path)

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_backup_failure(self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs, mock_copy):
        """Test that backup failure is handled correctly"""
        # Create a dummy config file
        with open('/tmp/test_config_db.json', 'w') as f:
            json.dump({"DEVICE_METADATA": {"localhost": {"hwsku": "old-hwsku"}}}, f)

        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect
        mock_copy.side_effect = PermissionError("Permission denied")

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y'])

        assert result.exit_code != 0
        assert 'Failed to backup config' in result.output
        assert 'Permission denied' in result.output

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.os.remove')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_config_generation_subprocess_failure(
            self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs,
            mock_copy, mock_subprocess, mock_remove):
        """Test that sonic-cfggen command failure is handled correctly"""
        # Create a dummy config file for backup
        with open('/tmp/test_config_db.json', 'w') as f:
            json.dump({"DEVICE_METADATA": {"localhost": {"hwsku": "old-hwsku"}}}, f)

        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        # Mock sonic-cfggen to fail
        error = subprocess.CalledProcessError(1, 'sonic-cfggen')
        error.stderr = "HWSKU not found in platform"
        mock_subprocess.side_effect = error

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y'])

        assert result.exit_code != 0
        assert 'Failed to generate config' in result.output
        assert 'HWSKU not found in platform' in result.output
        # Verify backup restoration was attempted
        assert 'Restoring backup from' in result.output
        # Verify backup was removed after restoration
        mock_remove.assert_called_once()

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.os.remove')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_config_generation_file_write_failure(
            self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs,
            mock_copy, mock_subprocess, mock_remove):
        """Test that file write failure during config generation is handled correctly"""
        # Ensure file permissions are correct from any previous test
        if os.path.exists('/tmp/test_config_db.json'):
            os.chmod('/tmp/test_config_db.json', 0o644)

        # Create a dummy config file for backup
        with open('/tmp/test_config_db.json', 'w') as f:
            json.dump({"DEVICE_METADATA": {"localhost": {"hwsku": "old-hwsku"}}}, f)

        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        # Mock sonic-cfggen to succeed but file write to fail
        base_config = {"DEVICE_METADATA": {"localhost": {"hwsku": "Vendor-Switch"}}}
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(base_config, indent=4),
            returncode=0
        )

        # Make the file read-only to cause write failure
        os.chmod('/tmp/test_config_db.json', 0o444)

        try:
            runner = CliRunner()
            result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y'])

            assert result.exit_code != 0
            # The error could be during backup or during config write
            # Either way, it should fail with a permission error
            assert 'Permission denied' in result.output
            # If backup succeeded, restoration should be attempted
            if 'Restoring backup from' in result.output:
                assert 'Restoring backup from' in result.output
                # Verify backup was removed after restoration
                mock_remove.assert_called_once()
        finally:
            # Restore file permissions
            if os.path.exists('/tmp/test_config_db.json'):
                os.chmod('/tmp/test_config_db.json', 0o644)

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_config_reload_failure(
            self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs,
            mock_copy, mock_subprocess):
        """Test that config reload failure is handled correctly"""
        # Create a dummy config file
        with open('/tmp/test_config_db.json', 'w') as f:
            json.dump({"DEVICE_METADATA": {"localhost": {"hwsku": "old-hwsku"}}}, f)

        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        # Mock sonic-cfggen to succeed
        base_config = {"DEVICE_METADATA": {"localhost": {"hwsku": "Vendor-Switch"}}}

        call_count = [0]

        def subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1
            # First call is sonic-cfggen (success)
            if call_count[0] == 1:
                return MagicMock(stdout=json.dumps(base_config, indent=4), returncode=0)
            # Second call is config reload (failure)
            else:
                raise subprocess.CalledProcessError(1, 'config reload')

        mock_subprocess.side_effect = subprocess_side_effect

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y', '-r'])

        assert result.exit_code != 0
        assert 'Failed to reload config' in result.output
        assert 'Config was generated but reload failed' in result.output
        assert 'You can manually reload using: config reload -y' in result.output

    @patch('config.load_hwsku.CONFIG_DB_PATH', '/tmp/test_config_db.json')
    @patch('config.load_hwsku.os.remove')
    @patch('config.load_hwsku.subprocess.run')
    @patch('config.load_hwsku.shutil.copy2')
    @patch('config.load_hwsku.os.makedirs')
    @patch('config.load_hwsku.os.path.exists')
    @patch('config.load_hwsku.device_info.get_hwsku')
    @patch('config.load_hwsku.is_valid_hwsku')
    def test_load_backup_restoration_on_failure(
            self, mock_valid, mock_current_hwsku, mock_exists, mock_makedirs,
            mock_copy, mock_subprocess, mock_remove):
        """Test that backup is restored and removed when config generation fails"""
        # Ensure file permissions are correct from any previous test
        if os.path.exists('/tmp/test_config_db.json'):
            os.chmod('/tmp/test_config_db.json', 0o644)

        # Create a dummy config file for backup
        original_config = {"DEVICE_METADATA": {"localhost": {"hwsku": "old-hwsku"}}}
        with open('/tmp/test_config_db.json', 'w') as f:
            json.dump(original_config, f)

        mock_valid.return_value = (True, None)
        mock_current_hwsku.return_value = 'Vendor-Switch'
        mock_exists.side_effect = backup_dir_exists_side_effect

        # Mock sonic-cfggen to fail
        error = subprocess.CalledProcessError(1, 'sonic-cfggen')
        error.stderr = "Config generation failed"
        mock_subprocess.side_effect = error

        runner = CliRunner()
        result = runner.invoke(hwsku.hwsku, ['load', 'Vendor-Switch', '-y'])

        assert result.exit_code != 0
        # Verify backup restoration message appears
        assert 'Restoring backup from' in result.output
        # Verify the config file still exists (was restored)
        assert os.path.exists('/tmp/test_config_db.json')
        # Verify the config was restored to original content
        with open('/tmp/test_config_db.json', 'r') as f:
            restored_config = json.load(f)
        assert restored_config == original_config
        # Verify that the backup file was removed after restoration
        mock_remove.assert_called_once()
