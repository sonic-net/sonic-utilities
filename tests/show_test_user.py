#!/usr/bin/env python3

import unittest
import unittest.mock as mock
import sys
import os
from click.testing import CliRunner

# Add the show directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'show'))

# Mock the dependencies before importing
sys.modules['swsscommon'] = mock.MagicMock()
sys.modules['swsscommon.swsscommon'] = mock.MagicMock()
sys.modules['utilities_common'] = mock.MagicMock()
sys.modules['utilities_common.cli'] = mock.MagicMock()

# Import the show user module
try:
    import user as show_user
except ImportError:
    # If direct import fails, try importing from show package
    from show import user as show_user


class TestShowUserCLI(unittest.TestCase):
    """Test cases for show user CLI commands"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.mock_db = mock.MagicMock()
        self.mock_config_db = mock.MagicMock()
        
        # Mock the database connection
        self.mock_db.cfgdb = self.mock_config_db
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_all(self, mock_connector_class):
        """Test showing all users"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector

        # Mock user data
        mock_users = {
            'admin': {
                'role': 'administrator',
                'enabled': 'true'
            },
            'operator1': {
                'role': 'operator',
                'enabled': 'false'
            }
        }
        mock_connector.get_table.return_value = mock_users

        result = self.runner.invoke(show_user.show_users, [], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('admin', result.output)
        self.assertIn('administrator', result.output)
        self.assertIn('operator1', result.output)
        self.assertIn('operator', result.output)
        # Password hashes should not be shown in regular mode
        self.assertNotIn('$6$', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_specific(self, mock_connector_class):
        """Test showing specific user"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock user data
        mock_user_data = {
            'role': 'administrator',
            'enabled': 'true',
            'ssh_keys': 'ssh-rsa AAAAB3...'
        }
        mock_connector.get_entry.return_value = mock_user_data
        
        result = self.runner.invoke(show_user.show_user_details, ['admin'], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('admin', result.output)
        self.assertIn('administrator', result.output)
        self.assertIn('enabled', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_not_found(self, mock_connector_class):
        """Test showing non-existent user"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = None
        
        result = self.runner.invoke(show_user.show_user_details, ['nonexistent'], obj=self.mock_db)
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('User not found', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_with_sudo(self, mock_connector_class):
        """Test showing users with sudo (should show password hashes)"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock user data with password hash
        mock_users = {
            'admin': {
                'role': 'administrator',
                'password_hash': '$6$salt$hash123',
                'enabled': 'true'
            }
        }
        mock_connector.get_table.return_value = mock_users
        
        # Mock os.geteuid to simulate running with sudo
        with mock.patch('os.geteuid', return_value=0):
            result = self.runner.invoke(show_user.show_users, [], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('admin', result.output)
        self.assertIn('$6$salt$hash123', result.output)  # Password hash should be shown
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_security_policy_all(self, mock_connector_class):
        """Test showing all security policies"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock security policy data
        mock_policies = {
            'administrator': {
                'max_login_attempts': '5'
            },
            'operator': {
                'max_login_attempts': '3'
            }
        }
        mock_connector.get_table.return_value = mock_policies
        
        result = self.runner.invoke(show_user.show_security_policy, [], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)
        self.assertIn('operator', result.output)
        self.assertIn('max_login_attempts', result.output)
        self.assertIn('5', result.output)
        self.assertIn('3', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_security_policy_specific(self, mock_connector_class):
        """Test showing specific role security policy"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock security policy data
        mock_policy_data = {
            'max_login_attempts': '5'
        }
        mock_connector.get_entry.return_value = mock_policy_data
        
        result = self.runner.invoke(show_user.show_security_policy, ['administrator'], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)
        self.assertIn('max_login_attempts', result.output)
        self.assertIn('5', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_security_policy_not_found(self, mock_connector_class):
        """Test showing non-existent security policy"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = None
        
        result = self.runner.invoke(show_user.show_security_policy, ['nonexistent'], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('No security policy configured', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_empty_table(self, mock_connector_class):
        """Test showing users when no users are configured"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {}
        
        result = self.runner.invoke(show_user.show_users, [], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('No users configured', result.output)
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_with_ssh_keys(self, mock_connector_class):
        """Test showing user with SSH keys"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock user data with SSH keys
        mock_user_data = {
            'role': 'operator',
            'enabled': 'true',
            'ssh_keys': 'ssh-rsa AAAAB3NzaC1yc2E... key1,ssh-rsa AAAAB3NzaC1yc2E... key2'
        }
        mock_connector.get_entry.return_value = mock_user_data
        
        result = self.runner.invoke(show_user.show_user_details, ['testuser'], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('testuser', result.output)
        self.assertIn('SSH Keys: 2', result.output)  # Should show count of SSH keys
    
    @mock.patch('show_user.ConfigDBConnector')
    def test_show_user_disabled(self, mock_connector_class):
        """Test showing disabled user"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock disabled user data
        mock_user_data = {
            'role': 'operator',
            'enabled': 'false'
        }
        mock_connector.get_entry.return_value = mock_user_data
        
        result = self.runner.invoke(show_user.show_user_details, ['disableduser'], obj=self.mock_db)
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('disableduser', result.output)
        self.assertIn('disabled', result.output)


if __name__ == '__main__':
    unittest.main()
