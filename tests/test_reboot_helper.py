import os
import sys
import unittest
from unittest.mock import patch, MagicMock

import pytest
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

reboot_helper_path = os.path.join(scripts_path, 'reboot_helper.py')
reboot_helper = load_module_from_source('reboot_helper', reboot_helper_path)

class TestRebootHelper(unittest.TestCase):

    @patch('reboot_helper.syslog.syslog')
    def test_log_err(self, mock_syslog):
        reboot_helper.log_err('Test error message')
        mock_syslog.assert_called_with(reboot_helper.syslog.LOG_ERR, 'Test error message')

    @patch('reboot_helper.syslog.syslog')
    def test_log_info(self, mock_syslog):
        reboot_helper.log_info('Test info message')
        mock_syslog.assert_called_with(reboot_helper.syslog.LOG_INFO, 'Test info message')

    @patch('reboot_helper.syslog.syslog')
    def test_log_debug(self, mock_syslog):
        reboot_helper.log_debug('Test debug message')
        mock_syslog.assert_called_with(reboot_helper.syslog.LOG_DEBUG, 'Test debug message')

    @patch('reboot_helper.sonic_platform.platform.Platform')
    def test_load_platform_chassis_success(self, mock_platform):
        mock_chassis = MagicMock()
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        self.assertTrue(reboot_helper.load_platform_chassis())
        self.assertEqual(reboot_helper.platform_chassis, mock_chassis)

    @patch('reboot_helper.sonic_platform.platform.Platform')
    def test_load_platform_chassis_failure(self, mock_platform):
        mock_platform.return_value.get_chassis.side_effect = Exception('Load failed')
        self.assertFalse(reboot_helper.load_platform_chassis())

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules')
    def test_reboot_module_success(self, mock_get_all_modules, mock_load_platform_chassis):
        mock_module = MagicMock()
        mock_module.get_name.return_value = 'test_module'
        mock_get_all_modules.return_value = [mock_module]
        self.assertTrue(reboot_helper.reboot_module('test_module'))
        mock_module.reboot.assert_called_once()

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules')
    def test_reboot_module_not_implemented_failure(self, mock_get_all_modules, mock_load_platform_chassis):
        mock_module = MagicMock()
        mock_module.get_name.return_value = 'test_module'
        mock_module.reboot.side_effect = NotImplementedError
        mock_get_all_modules.return_value = [mock_module]
        self.assertFalse(reboot_helper.reboot_module('test_module'))

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules')
    def test_reboot_module_general_exception(self, mock_get_all_modules, mock_load_platform_chassis):
        mock_module = MagicMock()
        mock_module.get_name.return_value = 'test_module'
        mock_module.reboot.side_effect = Exception('Reboot failed')
        mock_get_all_modules.return_value = [mock_module]
        self.assertFalse(reboot_helper.reboot_module('test_module'))

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules', side_effect=Exception('Failed to get modules'))
    def test_reboot_module_exception(self, mock_get_all_modules, mock_load_platform_chassis):
        self.assertFalse(reboot_helper.reboot_module('test_module'))

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.is_smartswitch', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules')
    def test_is_dpu_success(self, mock_get_all_modules, mock_is_smartswitch, mock_load_platform_chassis):
        mock_module = MagicMock()
        mock_module.get_name.return_value = 'DPU test_module'
        mock_get_all_modules.return_value = [mock_module]
        self.assertTrue(reboot_helper.is_dpu())

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.is_smartswitch', return_value=False)
    def test_is_dpu_failure(self, mock_is_smartswitch, mock_load_platform_chassis):
        self.assertFalse(reboot_helper.is_dpu())

    @patch('reboot_helper.load_platform_chassis', return_value=False)
    def test_is_dpu_load_platform_chassis_failure(self, mock_load_platform_chassis):
        self.assertFalse(reboot_helper.is_dpu())

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules')
    def test_reboot_module_not_found(self, mock_get_all_modules, mock_load_platform_chassis):
        mock_get_all_modules.return_value = []
        self.assertFalse(reboot_helper.reboot_module('non_existent_module'))

    @patch('reboot_helper.load_platform_chassis', return_value=True)
    @patch('reboot_helper.platform_chassis.get_all_modules')
    def test_reboot_module_name_mismatch(self, mock_get_all_modules, mock_load_platform_chassis):
        mock_module = MagicMock()
        mock_module.get_name.return_value = 'another_module'
        mock_get_all_modules.return_value = [mock_module]
        self.assertFalse(reboot_helper.reboot_module('test_module'))

if __name__ == '__main__':
    unittest.main()
