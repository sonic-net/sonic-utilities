#!/usr/bin/env python3

import unittest
import unittest.mock as mock
import sys
import os
import tempfile
import pwd
import grp
from click.testing import CliRunner

# Add the config directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

# Mock the dependencies before importing
sys.modules['swsscommon'] = mock.MagicMock()
sys.modules['swsscommon.swsscommon'] = mock.MagicMock()
sys.modules['jsonpatch'] = mock.MagicMock()
sys.modules['jsonpointer'] = mock.MagicMock()
sys.modules['utilities_common'] = mock.MagicMock()
sys.modules['utilities_common.cli'] = mock.MagicMock()

# Import the user module
import user


class TestUserCLI(unittest.TestCase):
    """Test cases for user CLI commands"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.mock_db = mock.MagicMock()
        self.mock_config_db = mock.MagicMock()
        
        # Mock the database connection
        self.mock_db.cfgdb = self.mock_config_db
    
    def test_validate_username_valid(self):
        """Test username validation with valid usernames"""
        valid_usernames = [
            'testuser',
            'test_user',
            'test-user',
            '_testuser',
            'user123',
            'a'
        ]
        
        for username in valid_usernames:
            valid, error = user.validate_username(username)
            self.assertTrue(valid, f"Username '{username}' should be valid but got error: {error}")
    
    def test_validate_username_invalid(self):
        """Test username validation with invalid usernames"""
        invalid_usernames = [
            'TestUser',      # Uppercase
            '1testuser',     # Starts with number
            'root',          # Reserved name
            '',              # Empty
            'a' * 33,        # Too long
            'test user',     # Space
            'test@user',     # Special character
        ]
        
        for username in invalid_usernames:
            valid, error = user.validate_username(username)
            self.assertFalse(valid, f"Username '{username}' should be invalid")
            self.assertIsInstance(error, str)
            self.assertGreater(len(error), 0)
    
    def test_validate_password_hash_valid(self):
        """Test password hash validation with valid hashes"""
        valid_hashes = [
            '$6$salt$hash',
            '$5$salt$hash',
            '$1$salt$hash',
            '!',  # Disabled password
        ]
        
        for password_hash in valid_hashes:
            if password_hash != '!':  # Skip the disabled password case
                valid, error = user.validate_password_hash(password_hash)
                self.assertTrue(valid, f"Password hash '{password_hash}' should be valid but got error: {error}")
    
    def test_validate_password_hash_invalid(self):
        """Test password hash validation with invalid hashes"""
        invalid_hashes = [
            '!$6$salt$hash',  # Starts with !
            '!disabled',      # Starts with !
        ]
        
        for password_hash in invalid_hashes:
            valid, error = user.validate_password_hash(password_hash)
            self.assertFalse(valid, f"Password hash '{password_hash}' should be invalid")
            self.assertIsInstance(error, str)
            self.assertGreater(len(error), 0)
    
    @mock.patch('user.crypt.crypt')
    @mock.patch('user.crypt.mksalt')
    def test_hash_password(self, mock_mksalt, mock_crypt):
        """Test password hashing"""
        mock_mksalt.return_value = 'salt'
        mock_crypt.return_value = '$6$salt$hash'
        
        result = user.hash_password('testpassword')
        
        self.assertEqual(result, '$6$salt$hash')
        mock_mksalt.assert_called_once()
        mock_crypt.assert_called_once_with('testpassword', 'salt')
    
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_check_admin_constraint_pass(self, mock_connector_class):
        """Test admin constraint check when constraint is satisfied"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock existing users with multiple admins
        mock_users = {
            'admin1': {'role': 'administrator', 'enabled': True},
            'admin2': {'role': 'administrator', 'enabled': True},
            'user1': {'role': 'operator', 'enabled': True}
        }
        mock_connector.get_table.return_value = mock_users
        
        result = user.check_admin_constraint(self.mock_db, 'admin1', False)
        
        self.assertTrue(result)  # Should pass because admin2 is still enabled
    
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_check_admin_constraint_fail(self, mock_connector_class):
        """Test admin constraint check when constraint is violated"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        
        # Mock existing users with only one admin
        mock_users = {
            'admin1': {'role': 'administrator', 'enabled': True},
            'user1': {'role': 'operator', 'enabled': True}
        }
        mock_connector.get_table.return_value = mock_users
        
        result = user.check_admin_constraint(self.mock_db, 'admin1', False)
        
        self.assertFalse(result)  # Should fail because no admins would remain

    def test_is_feature_enabled_true(self):
        """Test feature enabled check when feature is enabled"""
        mock_device_metadata = {
            user.DEVICE_METADATA_LOCALHOST_KEY: {user.LOCAL_USER_MANAGEMENT_FIELD: 'enabled'}
        }

        with mock.patch('user.ValidatedConfigDBConnector') as mock_connector_class:
            mock_connector = mock.MagicMock()
            mock_connector_class.return_value = mock_connector
            mock_connector.get_table.return_value = mock_device_metadata

            result = user.is_feature_enabled(self.mock_db)
            self.assertTrue(result)

    def test_is_feature_enabled_false(self):
        """Test feature enabled check when feature is disabled"""
        mock_device_metadata = {
            user.DEVICE_METADATA_LOCALHOST_KEY: {user.LOCAL_USER_MANAGEMENT_FIELD: 'disabled'}
        }

        with mock.patch('user.ValidatedConfigDBConnector') as mock_connector_class:
            mock_connector = mock.MagicMock()
            mock_connector_class.return_value = mock_connector
            mock_connector.get_table.return_value = mock_device_metadata

            result = user.is_feature_enabled(self.mock_db)
            self.assertFalse(result)

    def test_is_feature_enabled_missing(self):
        """Test feature enabled check when feature is not configured"""
        mock_device_metadata = {}

        with mock.patch('user.ValidatedConfigDBConnector') as mock_connector_class:
            mock_connector = mock.MagicMock()
            mock_connector_class.return_value = mock_connector
            mock_connector.get_table.return_value = mock_device_metadata

            result = user.is_feature_enabled(self.mock_db)
            self.assertFalse(result)

    @mock.patch('user.ValidatedConfigDBConnector')
    def test_feature_enable_success(self, mock_connector_class):
        """Test successful feature enablement"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {user.DEVICE_METADATA_LOCALHOST_KEY: {}}

        result = self.runner.invoke(user.feature, ['enabled'], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        # Check that set_entry was called with the correct parameters
        call_args = mock_connector.set_entry.call_args
        self.assertEqual(call_args[0][0], user.DEVICE_METADATA_TABLE)
        self.assertEqual(call_args[0][1], user.DEVICE_METADATA_LOCALHOST_KEY)
        self.assertEqual(call_args[0][2][user.LOCAL_USER_MANAGEMENT_FIELD], 'enabled')
        self.assertIn("Local user management enabled", result.output)

    @mock.patch('user.ValidatedConfigDBConnector')
    def test_feature_disable_success(self, mock_connector_class):
        """Test successful feature disablement"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {user.DEVICE_METADATA_LOCALHOST_KEY: {}}

        result = self.runner.invoke(user.feature, ['disabled'], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        # Check that set_entry was called with the correct parameters
        call_args = mock_connector.set_entry.call_args
        self.assertEqual(call_args[0][0], user.DEVICE_METADATA_TABLE)
        self.assertEqual(call_args[0][1], user.DEVICE_METADATA_LOCALHOST_KEY)
        self.assertEqual(call_args[0][2][user.LOCAL_USER_MANAGEMENT_FIELD], 'disabled')
        self.assertIn("Local user management disabled", result.output)

    @mock.patch('user.ValidatedConfigDBConnector')
    def test_feature_enable_db_error(self, mock_connector_class):
        """Test feature enablement with database error"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {user.DEVICE_METADATA_LOCALHOST_KEY: {}}
        mock_connector.set_entry.side_effect = ValueError("Database error")

        result = self.runner.invoke(user.feature, ['enabled'], obj=self.mock_db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Error: Failed to enabled local user management", result.output)

    @mock.patch('user.get_existing_linux_users')
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_import_existing_feature_disabled(self, mock_connector_class, mock_feature_enabled, mock_get_users):
        """Test import-existing when feature is disabled"""
        mock_feature_enabled.return_value = False

        result = self.runner.invoke(user.import_existing, [], obj=self.mock_db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Local user management is not enabled", result.output)

    @mock.patch('user.get_existing_linux_users')
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_import_existing_dry_run(self, mock_connector_class, mock_feature_enabled, mock_get_users):
        """Test import-existing with dry-run flag"""
        mock_feature_enabled.return_value = True
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {}  # No existing users in CONFIG_DB

        mock_get_users.return_value = {
            'testuser1': {
                'role': 'administrator',
                'enabled': True,
                'ssh_keys': ['ssh-rsa AAAAB3...']
            },
            'testuser2': {
                'role': 'operator',
                'enabled': False,
                'ssh_keys': []
            }
        }

        result = self.runner.invoke(user.import_existing, ['--dry-run'], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Users that would be imported:", result.output)
        self.assertIn("testuser1: role=administrator", result.output)
        self.assertIn("testuser2: role=operator", result.output)
        # Should not actually import anything
        mock_connector.set_entry.assert_not_called()

    @mock.patch('user.get_existing_linux_users')
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_import_existing_success(self, mock_connector_class, mock_feature_enabled, mock_get_users):
        """Test successful import of existing users"""
        mock_feature_enabled.return_value = True
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {}  # No existing users in CONFIG_DB

        mock_get_users.return_value = {
            'testuser1': {
                'role': 'administrator',
                'password_hash': '$6$salt$hash1',
                'enabled': True,
                'ssh_keys': ['ssh-rsa AAAAB3...']
            }
        }

        result = self.runner.invoke(user.import_existing, [], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Imported user: testuser1", result.output)
        self.assertIn("Successfully imported 1 users", result.output)

        # Verify the user was added to CONFIG_DB
        mock_connector.set_entry.assert_called_with(
            user.LOCAL_USER_TABLE,
            'testuser1',
            {
                'role': 'administrator',
                'password_hash': '$6$salt$hash1',
                'enabled': True,
                'ssh_keys': 'ssh-rsa AAAAB3...'
            }
        )

    @mock.patch('user.get_existing_linux_users')
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_import_existing_no_users(self, mock_connector_class, mock_feature_enabled, mock_get_users):
        """Test import-existing when no users to import"""
        mock_feature_enabled.return_value = True
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {}

        mock_get_users.return_value = {}  # No users found

        result = self.runner.invoke(user.import_existing, [], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No users found to import", result.output)

    @mock.patch('user.get_existing_linux_users')
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_import_existing_skip_existing(self, mock_connector_class, mock_feature_enabled, mock_get_users):
        """Test import-existing skips users already in CONFIG_DB"""
        mock_feature_enabled.return_value = True
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_table.return_value = {'testuser1': {}}  # User already exists

        mock_get_users.return_value = {
            'testuser1': {'role': 'administrator', 'enabled': True, 'ssh_keys': []},
            'testuser2': {'role': 'operator', 'enabled': True, 'ssh_keys': []}
        }

        result = self.runner.invoke(user.import_existing, [], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Successfully imported 1 users", result.output)
        # Should only import testuser2, not testuser1
        mock_connector.set_entry.assert_called_once()
    
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    @mock.patch('user.validate_username')
    def test_add_user_success(self, mock_validate, mock_connector_class, mock_feature_enabled):
        """Test successful user addition"""
        mock_feature_enabled.return_value = True
        mock_validate.return_value = (True, "")
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = None  # User doesn't exist

        result = self.runner.invoke(user.add, [
            'testuser',
            '--role', 'administrator',
            '--password-hash', '$6$salt$hash'
        ], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        mock_connector.set_entry.assert_called_with(
            user.LOCAL_USER_TABLE,
            'testuser',
            {
                'role': 'administrator',
                'password_hash': '$6$salt$hash',
                'enabled': True
            }
        )

    @mock.patch('user.is_feature_enabled')
    def test_add_user_feature_disabled(self, mock_feature_enabled):
        """Test user addition when feature is disabled"""
        mock_feature_enabled.return_value = False

        result = self.runner.invoke(user.add, [
            'testuser',
            '--role', 'administrator',
            '--password-hash', '$6$salt$hash'
        ], obj=self.mock_db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Local user management is not enabled", result.output)
    
    @mock.patch('user.ValidatedConfigDBConnector')
    @mock.patch('user.validate_username')
    def test_add_user_already_exists(self, mock_validate, mock_connector_class):
        """Test user addition when user already exists"""
        mock_validate.return_value = (True, "")
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = {'role': 'operator'}  # User exists
        
        result = self.runner.invoke(user.add, [
            'testuser',
            '--role', 'administrator',
            '--password-hash', '$6$salt$hash'
        ], obj=self.mock_db)
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already exists", result.output)
    
    @mock.patch('user.validate_username')
    def test_add_user_invalid_username(self, mock_validate):
        """Test user addition with invalid username"""
        mock_validate.return_value = (False, "Invalid username")
        
        result = self.runner.invoke(user.add, [
            'InvalidUser',
            '--role', 'administrator',
            '--password-hash', '$6$salt$hash'
        ], obj=self.mock_db)
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid username", result.output)
    
    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_delete_user_success(self, mock_connector_class, mock_feature_enabled):
        """Test successful user deletion"""
        mock_feature_enabled.return_value = True
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = {'role': 'operator'}  # User exists

        with mock.patch('user.check_admin_constraint', return_value=True):
            result = self.runner.invoke(user.delete, ['testuser'], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        # Verify the delete operation was called
        mock_connector.set_entry.assert_called_with(user.LOCAL_USER_TABLE, 'testuser', None)
    
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_delete_user_not_exists(self, mock_connector_class):
        """Test user deletion when user doesn't exist"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = None  # User doesn't exist
        
        result = self.runner.invoke(user.delete, ['testuser'], obj=self.mock_db)
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("does not exist", result.output)
    
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_delete_last_admin(self, mock_connector_class):
        """Test deletion of last administrator user"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = {'role': 'administrator'}  # Admin user
        
        with mock.patch('user.check_admin_constraint', return_value=False):
            result = self.runner.invoke(user.delete, ['admin'], obj=self.mock_db)
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Cannot delete the last administrator", result.output)
    
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_modify_user_success(self, mock_connector_class):
        """Test successful user modification"""
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector
        mock_connector.get_entry.return_value = {
            'role': 'operator',
            'password_hash': '$6$old$hash',
            'enabled': True
        }
        
        result = self.runner.invoke(user.modify, [
            'testuser',
            '--password-hash', '$6$new$hash',
            '--enabled'
        ], obj=self.mock_db)
        
        # Verify the modify operation was called
        mock_connector.set_entry.assert_called_once()
        call_args = mock_connector.set_entry.call_args
        self.assertEqual(call_args[0][0], user.LOCAL_USER_TABLE)
        self.assertEqual(call_args[0][1], 'testuser')
        self.assertEqual(call_args[0][2]['password_hash'], '$6$new$hash')

    @mock.patch('user.is_feature_enabled')
    @mock.patch('user.ValidatedConfigDBConnector')
    def test_set_security_policy(self, mock_connector_class, mock_feature_enabled):
        """Test setting security policy"""
        mock_feature_enabled.return_value = True
        mock_connector = mock.MagicMock()
        mock_connector_class.return_value = mock_connector

        result = self.runner.invoke(user.set_policy, [
            'administrator',
            '--max-login-attempts', '10'
        ], obj=self.mock_db)

        self.assertEqual(result.exit_code, 0)
        # Verify the policy was set
        mock_connector.set_entry.assert_called_with(
            user.LOCAL_ROLE_SECURITY_POLICY_TABLE,
            'administrator',
            {'max_login_attempts': 10}
        )

    @mock.patch('builtins.open', mock.mock_open(read_data='testuser:x:1001:1001:Test User:/home/testuser:/bin/bash\nroot:x:0:0:root:/root:/bin/bash\n'))
    @mock.patch('grp.getgrall')
    @mock.patch('grp.getgrgid')
    def test_get_existing_linux_users(self, mock_getgrgid, mock_getgrall):
        """Test getting existing Linux users"""
        # Mock group data
        mock_group = mock.MagicMock()
        mock_group.gr_name = 'sudo'
        mock_group.gr_mem = ['testuser']
        mock_getgrall.return_value = [mock_group]

        mock_primary_group = mock.MagicMock()
        mock_primary_group.gr_name = 'testuser'
        mock_getgrgid.return_value = mock_primary_group

        # Mock shadow file
        shadow_data = 'testuser:$6$salt$hash:18000:0:99999:7:::\nroot:*:18000:0:99999:7:::\n'

        with mock.patch('builtins.open', mock.mock_open()) as mock_file:
            mock_file.side_effect = [
                mock.mock_open(read_data='testuser:x:1001:1001:Test User:/home/testuser:/bin/bash\nroot:x:0:0:root:/root:/bin/bash\n').return_value,
                mock.mock_open(read_data=shadow_data).return_value
            ]

            users = user.get_existing_linux_users(1000, 2000)

        self.assertIn('testuser', users)
        self.assertEqual(users['testuser']['role'], 'administrator')  # Has sudo group
        self.assertEqual(users['testuser']['password_hash'], '$6$salt$hash')
        self.assertTrue(users['testuser']['enabled'])  # Shell is /bin/bash
        self.assertNotIn('root', users)  # System user should be excluded

    @mock.patch('user.is_feature_enabled')
    def test_add_user_with_ssh_keys(self, mock_feature_enabled):
        """Test adding user with SSH keys"""
        mock_feature_enabled.return_value = True

        with mock.patch('user.ValidatedConfigDBConnector') as mock_connector_class, \
             mock.patch('user.validate_username', return_value=(True, "")):

            mock_connector = mock.MagicMock()
            mock_connector_class.return_value = mock_connector
            mock_connector.get_entry.return_value = None  # User doesn't exist

            result = self.runner.invoke(user.add, [
                'testuser',
                '--role', 'operator',
                '--ssh-key', 'ssh-rsa AAAAB3NzaC1yc2E... key1',
                '--ssh-key', 'ssh-rsa AAAAB3NzaC1yc2E... key2'
            ], obj=self.mock_db)

            self.assertEqual(result.exit_code, 0)

            # Verify user was created with SSH keys
            call_args = mock_connector.set_entry.call_args
            user_data = call_args[0][2]
            self.assertIn('ssh_keys', user_data)
            self.assertEqual(len(user_data['ssh_keys']), 2)

    @mock.patch('user.is_feature_enabled')
    @mock.patch('getpass.getpass')
    def test_add_user_with_password_prompt(self, mock_getpass, mock_feature_enabled):
        """Test adding user with password prompt"""
        mock_feature_enabled.return_value = True
        mock_getpass.side_effect = ['testpassword', 'testpassword']  # Password and confirmation

        with mock.patch('user.ValidatedConfigDBConnector') as mock_connector_class, \
             mock.patch('user.validate_username', return_value=(True, "")), \
             mock.patch('user.hash_password', return_value='$6$salt$hashedpassword'):

            mock_connector = mock.MagicMock()
            mock_connector_class.return_value = mock_connector
            mock_connector.get_entry.return_value = None  # User doesn't exist

            result = self.runner.invoke(user.add, [
                'testuser',
                '--role', 'operator',
                '--password-prompt'
            ], obj=self.mock_db)

            self.assertEqual(result.exit_code, 0)

            # Verify password was hashed and stored
            call_args = mock_connector.set_entry.call_args
            user_data = call_args[0][2]
            self.assertEqual(user_data['password_hash'], '$6$salt$hashedpassword')

    @mock.patch('user.is_feature_enabled')
    @mock.patch('getpass.getpass')
    def test_add_user_password_mismatch(self, mock_getpass, mock_feature_enabled):
        """Test adding user with mismatched password confirmation"""
        mock_feature_enabled.return_value = True
        mock_getpass.side_effect = ['password1', 'password2']  # Mismatched passwords

        result = self.runner.invoke(user.add, [
            'testuser',
            '--role', 'operator',
            '--password-prompt'
        ], obj=self.mock_db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Passwords do not match", result.output)

    def test_validate_password_hash_invalid(self):
        """Test password hash validation with invalid hash"""
        valid, error = user.validate_password_hash('!$6$salt$hash')
        self.assertFalse(valid)
        self.assertIn("cannot start with '!'", error)

    def test_validate_password_against_policies_disabled(self):
        """Test password validation when policies are disabled"""
        policies = {'state': 'disabled'}
        valid, error = user.validate_password_against_policies('weak', 'testuser', policies)
        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_validate_password_against_policies_no_policies(self):
        """Test password validation when no policies are set"""
        valid, error = user.validate_password_against_policies('weak', 'testuser', None)
        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_validate_password_against_policies_length(self):
        """Test password validation for minimum length"""
        policies = {'state': 'enabled', 'len_min': 8}

        # Valid password
        valid, error = user.validate_password_against_policies('password123', 'testuser', policies)
        self.assertTrue(valid)

        # Invalid password (too short)
        valid, error = user.validate_password_against_policies('short', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("at least 8 characters", error)

    def test_validate_password_against_policies_character_classes(self):
        """Test password validation for character class requirements"""
        policies = {
            'state': 'enabled',
            'lower_class': True,
            'upper_class': True,
            'digits_class': True,
            'special_class': True
        }

        # Valid password with all character classes
        valid, error = user.validate_password_against_policies('Password123!', 'testuser', policies)
        self.assertTrue(valid)

        # Missing lowercase
        valid, error = user.validate_password_against_policies('PASSWORD123!', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("lowercase letter", error)

        # Missing uppercase
        valid, error = user.validate_password_against_policies('password123!', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("uppercase letter", error)

        # Missing digit
        valid, error = user.validate_password_against_policies('Password!', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("digit", error)

        # Missing special character
        valid, error = user.validate_password_against_policies('Password123', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("special character", error)

    def test_validate_password_against_policies_username_match(self):
        """Test password validation for username matching"""
        policies = {'state': 'enabled', 'reject_user_passw_match': True}

        # Valid password (no username match)
        valid, error = user.validate_password_against_policies('mypassword123', 'testuser', policies)
        self.assertTrue(valid)

        # Invalid password (contains username)
        valid, error = user.validate_password_against_policies('testuser123', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("cannot contain the username", error)

        # Invalid password (contains username case insensitive)
        valid, error = user.validate_password_against_policies('MyTESTUSER123', 'testuser', policies)
        self.assertFalse(valid)
        self.assertIn("cannot contain the username", error)

    def test_get_password_hardening_policies(self):
        """Test getting password hardening policies from CONFIG_DB"""
        # Mock the database
        db = Db()

        # Test when no policies exist
        policies = user.get_password_hardening_policies(db)
        self.assertIsNone(policies)

        # Test with policies configured
        db.cfgdb.set_entry("PASSW_HARDENING", "POLICIES", {
            'state': 'enabled',
            'len_min': '8',
            'lower_class': 'true',
            'upper_class': 'false',
            'digits_class': '1',
            'special_class': '0',
            'reject_user_passw_match': 'True'
        })

        policies = user.get_password_hardening_policies(db)
        self.assertIsNotNone(policies)
        self.assertEqual(policies['state'], 'enabled')
        self.assertEqual(policies['len_min'], 8)
        self.assertTrue(policies['lower_class'])
        self.assertFalse(policies['upper_class'])
        self.assertTrue(policies['digits_class'])
        self.assertFalse(policies['special_class'])
        self.assertTrue(policies['reject_user_passw_match'])

    def test_validate_password_hash_valid(self):
        """Test password hash validation with valid hash"""
        valid, error = user.validate_password_hash('$6$salt$hash')
        self.assertTrue(valid)
        self.assertEqual(error, "")


if __name__ == '__main__':
    unittest.main()
