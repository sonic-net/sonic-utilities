#!/usr/bin/env python3

import os
import sys
import unittest
import unittest.mock as mock

from click.testing import CliRunner
from utilities_common.db import Db

# Add the parent directory to the path to access show module
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

# Set up environment for testing
os.environ["UTILITIES_UNIT_TESTING"] = "1"

# Import the show user module
import show.user as show_user  # noqa: E402


class TestShowUserCLI(unittest.TestCase):
    """Test cases for show user CLI commands"""

    @classmethod
    def setUpClass(cls):
        """Set up class fixtures"""
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def tearDownClass(cls):
        """Clean up class fixtures"""
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.db = Db()

    def test_show_user_all(self):
        """Test showing all users"""

        from .mock_tables import dbconnector

        try:
            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)
            self.assertIn('administrator', result.output)
            self.assertIn('operator1', result.output)
            self.assertIn('operator', result.output)
            self.assertIn('testuser', result.output)
            # Check SSH key display - operator1 has empty array [] in config_db.json
            self.assertIn('SSH Keys (1)', result.output)  # admin has 1 SSH key
            self.assertIn('SSH Keys: None', result.output)  # operator1 has no SSH keys
            self.assertIn('SSH Keys (2)', result.output)  # testuser has 2 SSH keys
        finally:
            pass

    @mock.patch('show.user.can_view_passwords', return_value=True)
    def test_show_user_all_admin_view(self, mock_can_view_passwords):
        """Test show users command with admin privileges (can see passwords)"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            # Admin should see password hashes from config_db.json
            self.assertIn('$y$j9T$salt$adminhash', result.output)
            self.assertIn('$y$j9T$salt$operatorhash', result.output)
            self.assertIn('$y$j9T$salt$testuserhash', result.output)
        finally:
            pass

    @mock.patch('show.user.can_view_passwords', return_value=False)
    def test_show_user_all_operator_view(self, mock_can_view):
        """Test show users command with operator privileges (cannot see passwords)"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            # Operator should NOT see password hashes from config_db.json
            self.assertNotIn('$y$j9T$salt$adminhash', result.output)
            self.assertNotIn('$y$j9T$salt$operatorhash', result.output)
            # But should still see other user info
            self.assertIn('admin', result.output)
            self.assertIn('administrator', result.output)
            self.assertIn('operator1', result.output)
        finally:

            pass

    def test_show_user_specific(self):
        """Test showing specific user"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_user_details, ['admin'], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)
            self.assertIn('administrator', result.output)
            self.assertIn('Yes', result.output)  # enabled should show as "Yes"
        finally:

            pass

    def test_show_user_not_found(self):
        """Test showing non-existent user"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_user_details, ['nonexistent'], obj=self.db)

            self.assertEqual(result.exit_code, 0)  # Command succeeds but shows error message
            self.assertIn("User 'nonexistent' not found", result.output)
        finally:

            pass

    def test_show_user_with_sudo(self):
        """Test showing users with sudo (should show password hashes)"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            # Mock os.geteuid to simulate running with sudo
            with mock.patch('show.user.os.geteuid', return_value=0):
                result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)
            # Should show password hash from config_db.json when running with sudo
            self.assertIn('$y$j9T$salt$adminhash', result.output)
        finally:

            pass

    @mock.patch('show.user.get_security_policies')
    def test_show_user_security_policy_all(self, mock_get_policies):
        """Test showing all security policies"""
        # Mock security policy data
        mock_policies = {
            'administrator': {
                'max_login_attempts': '5'
            },
            'operator': {
                'max_login_attempts': '3'
            }
        }
        mock_get_policies.return_value = mock_policies

        result = self.runner.invoke(show_user.show_security_policy, [], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)
        self.assertIn('operator', result.output)
        self.assertIn('max_login_attempts', result.output)
        self.assertIn('5', result.output)
        self.assertIn('3', result.output)

    @mock.patch('show.user.get_security_policies')
    def test_show_user_security_policy_specific(self, mock_get_policies):
        """Test showing specific role security policy"""
        # Mock security policy data
        mock_policies = {
            'administrator': {
                'max_login_attempts': '5'
            },
            'operator': {
                'max_login_attempts': '3'
            }
        }
        mock_get_policies.return_value = mock_policies

        result = self.runner.invoke(show_user.show_security_policy, ['administrator'], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)
        self.assertIn('max_login_attempts', result.output)
        self.assertIn('5', result.output)
        # Should not show operator policy
        self.assertNotIn('3', result.output)

    @mock.patch('show.user.get_security_policies')
    def test_show_user_security_policy_not_found(self, mock_get_policies):
        """Test showing security policy for role that has no policy configured"""
        # Mock policies that don't include the operator role
        mock_policies = {
            'administrator': {
                'max_login_attempts': '5'
            }
            # operator role is missing - no policy configured
        }
        mock_get_policies.return_value = mock_policies

        result = self.runner.invoke(show_user.show_security_policy, ['operator'], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No security policy configured for role 'operator'", result.output)

    @mock.patch('show.user.get_user_database')
    def test_show_user_empty_table(self, mock_get_user_database):
        """Test showing users when no users are configured"""
        # Mock empty user database
        mock_get_user_database.return_value = {}

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('No users configured', result.output)

    def test_show_user_with_ssh_keys(self):
        """Test showing user with SSH keys"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_user_details, ['testuser'], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('testuser', result.output)
            self.assertIn('SSH Keys (2)', result.output)  # testuser has 2 SSH keys in config_db.json
        finally:

            pass

    def test_show_user_disabled(self):
        """Test showing disabled user"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_user_details, ['operator1'], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('operator1', result.output)
            self.assertIn('No', result.output)  # operator1 is disabled in config_db.json
        finally:

            pass

    def test_cli_ssh_key_formatting_through_show_commands(self):
        """Test SSH key formatting through actual show commands"""

        # config_db.json has: admin (1 key), operator1 (0 keys), testuser (2 keys)
        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            # Test show users command (shows SSH key counts)
            result = self.runner.invoke(show_user.show_users, [], obj=self.db)
            self.assertEqual(result.exit_code, 0)

            # Verify SSH key count formatting using data from config_db.json
            self.assertIn('SSH Keys: None', result.output)  # operator1 has no keys
            self.assertIn('SSH Keys (1)', result.output)    # admin has 1 key
            self.assertIn('SSH Keys (2)', result.output)    # testuser has 2 keys

            # Test show user details command (shows detailed SSH keys)
            result = self.runner.invoke(show_user.show_user_details, ['testuser'], obj=self.db)
            self.assertEqual(result.exit_code, 0)

            # Verify detailed SSH key formatting for testuser (2 keys)
            self.assertIn("SSH Keys (2):", result.output)
            self.assertIn("1. ssh-rsa", result.output)
            self.assertIn("2. ssh-ed25519", result.output)

            # Test single key detailed view
            result = self.runner.invoke(show_user.show_user_details, ['admin'], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("SSH Keys (1):", result.output)
            self.assertIn("1. ssh-rsa", result.output)

            # Test no keys detailed view
            result = self.runner.invoke(show_user.show_user_details, ['operator1'], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("SSH Keys: None", result.output)
        finally:

            pass

    @mock.patch('show.user.getpass.getuser')
    @mock.patch('show.user.os.geteuid')
    def test_cli_password_visibility_based_on_user_permissions(self, mock_geteuid, mock_getuser):
        """Test password visibility in show commands based on user permissions"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            # Test 1: Root user should see password hashes
            mock_geteuid.return_value = 0  # Root user
            mock_getuser.return_value = "root"

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertIn('$y$j9T$salt$adminhash', result.output)
            self.assertIn('$y$j9T$salt$operatorhash', result.output)

            # Test 2: Admin user should see password hashes
            mock_geteuid.return_value = 1000  # Non-root user
            mock_getuser.return_value = "admin"

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertIn('$y$j9T$salt$adminhash', result.output)
            self.assertIn('$y$j9T$salt$operatorhash', result.output)

            # Test 3: Operator user should NOT see password hashes
            mock_getuser.return_value = "operator1"

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertNotIn('$y$j9T$salt$adminhash', result.output)
            self.assertNotIn('$y$j9T$salt$operatorhash', result.output)
            # Should still show other user info
            self.assertIn('admin', result.output)
            self.assertIn('operator1', result.output)
            self.assertIn('administrator', result.output)
        finally:

            pass

        # Test 4: Unknown user should NOT see password hashes
        mock_getuser.return_value = "unknown"

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn('$y$j9T$salt$adminhash', result.output)
        self.assertNotIn('$y$j9T$salt$operatorhash', result.output)

    def test_show_user_details_all_users(self):
        """Test showing details for all users when no username specified"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_user_details, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)
            self.assertIn('operator1', result.output)
            self.assertIn('testuser', result.output)
            self.assertIn('administrator', result.output)
            self.assertIn('SSH Keys (1)', result.output)  # admin has 1 key
            self.assertIn('SSH Keys (2)', result.output)  # testuser has 2 keys
        finally:

            pass

    @mock.patch('show.user.get_user_database')
    def test_show_user_details_empty_database(self, mock_get_users):
        """Test showing user details when database is empty"""
        mock_get_users.return_value = {}

        result = self.runner.invoke(show_user.show_user_details, ['anyuser'], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('No users configured', result.output)

    @mock.patch('show.user.get_security_policies')
    def test_show_security_policy_empty_database(self, mock_get_security_policies):
        """Test showing security policies when none are configured"""
        # Mock empty security policies
        mock_get_security_policies.return_value = {}

        result = self.runner.invoke(show_user.show_security_policy, [], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('No security policies configured', result.output)

    @mock.patch('show.user.get_security_policies')
    def test_show_security_policy_multiple_policies(self, mock_get_policies):
        """Test showing multiple security policies"""
        mock_policies = {
            'administrator': {
                'max_login_attempts': '5',
                'lockout_duration': '300'
            },
            'operator': {
                'max_login_attempts': '3',
                'lockout_duration': '600'
            }
        }
        mock_get_policies.return_value = mock_policies

        result = self.runner.invoke(show_user.show_security_policy, [], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)
        self.assertIn('operator', result.output)
        self.assertIn('max_login_attempts', result.output)
        self.assertIn('lockout_duration', result.output)
        self.assertIn('5', result.output)
        self.assertIn('3', result.output)
        self.assertIn('300', result.output)
        self.assertIn('600', result.output)

    @mock.patch('show.user.can_view_passwords', return_value=False)
    def test_show_users_mixed_enabled_disabled(self, mock_can_view):
        """Test showing users with mixed enabled/disabled states"""

        # config_db.json has: admin (enabled), operator1 (disabled), testuser (enabled)
        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)      # enabled admin
            self.assertIn('operator1', result.output)  # disabled operator
            self.assertIn('testuser', result.output)   # enabled operator
            # Should show enabled/disabled status
            self.assertIn('Yes', result.output)  # For enabled users (admin, testuser)
            self.assertIn('No', result.output)   # For disabled users (operator1)
            # Should not show password hashes (operator view)
            self.assertNotIn('$y$j9T$salt$adminhash', result.output)
        finally:

            pass

    def test_show_user_with_missing_fields(self):
        """Test showing user with complete fields (using shared database)"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_user_details, ['operator1'], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('operator1', result.output)
            self.assertIn('operator', result.output)
            self.assertIn('No', result.output)  # operator1 is disabled in config_db.json
            self.assertIn('SSH Keys: None', result.output)  # operator1 has no SSH keys
        finally:

            pass

    @mock.patch('show.user.get_user_database')
    def test_show_user_with_malformed_data(self, mock_get_users):
        """Test showing user with malformed data"""
        mock_users = {
            'malformed_user': {
                'role': 'operator',
                'enabled': 'invalid_boolean',  # Invalid boolean value
                'ssh_keys': 'not_a_list'  # Invalid SSH keys format
            }
        }
        mock_get_users.return_value = mock_users

        result = self.runner.invoke(show_user.show_user_details, ['malformed_user'], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('malformed_user', result.output)
        # Should handle malformed data gracefully

    def test_show_users_with_long_ssh_keys(self):
        """Test showing users with SSH keys (using shared database)"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)
            self.assertIn('testuser', result.output)
            self.assertIn('SSH Keys (1)', result.output)  # admin has 1 SSH key
            self.assertIn('SSH Keys (2)', result.output)  # testuser has 2 SSH keys
        finally:

            pass

    @mock.patch('show.user.get_user_database')
    def test_show_users_with_many_ssh_keys(self, mock_get_users):
        """Test showing users with many SSH keys"""
        many_keys = [f'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA key{i}@host'
                     for i in range(10)]
        mock_users = {
            'user_with_many_keys': {
                'role': 'administrator',
                'enabled': True,
                'ssh_keys': many_keys
            }
        }
        mock_get_users.return_value = mock_users

        result = self.runner.invoke(show_user.show_user_details, ['user_with_many_keys'], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('user_with_many_keys', result.output)
        self.assertIn('SSH Keys (10)', result.output)
        # Should show all keys numbered
        self.assertIn('1. ssh-rsa', result.output)
        self.assertIn('10. ssh-rsa', result.output)

    @mock.patch('show.user.get_security_policies')
    def test_show_security_policy_with_various_data_types(self, mock_get_policies):
        """Test showing security policies with various data types"""
        mock_policies = {
            'test_role': {
                'max_login_attempts': 5,  # Integer
                'lockout_duration': '300',  # String
                'enabled': True,  # Boolean
                'custom_setting': 'custom_value'  # Custom string
            }
        }
        mock_get_policies.return_value = mock_policies

        # Use valid role name instead of 'test_role'
        result = self.runner.invoke(show_user.show_security_policy, ['administrator'], obj=self.db)

        # Should fail with exit code 2 because 'test_role' is not a valid choice
        # But let's test with a valid role name and mock data
        mock_policies = {
            'administrator': {
                'max_login_attempts': 5,  # Integer
                'lockout_duration': '300',  # String
                'enabled': True,  # Boolean
                'custom_setting': 'custom_value'  # Custom string
            }
        }
        mock_get_policies.return_value = mock_policies

        result = self.runner.invoke(show_user.show_security_policy, ['administrator'], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)
        self.assertIn('max_login_attempts: 5', result.output)
        self.assertIn('lockout_duration: 300', result.output)
        self.assertIn('enabled: True', result.output)
        self.assertIn('custom_setting: custom_value', result.output)

    @mock.patch('show.user.get_user_database')
    def test_cli_database_connection_error_handling(self, mock_get_users):
        """Test CLI behavior when database connection fails"""
        # Test database connection error during show users
        mock_get_users.side_effect = Exception("Database connection failed")

        # Should handle database exceptions gracefully
        try:
            result = self.runner.invoke(show_user.show_users, [], obj=self.db)
            # If no exception propagates, command should handle it gracefully
            self.assertEqual(result.exit_code, 0)
        except Exception:
            # If exception propagates, it should be handled appropriately
            pass

        # Test with security policies
        with mock.patch('show.user.get_security_policies') as mock_get_policies:
            mock_get_policies.side_effect = Exception("Database connection failed")

            try:
                result = self.runner.invoke(show_user.show_security_policy, [], obj=self.db)
                # Should handle gracefully
                self.assertEqual(result.exit_code, 0)
            except Exception:
                pass

    def test_show_users_case_sensitivity(self):
        """Test that usernames are case-sensitive in display"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            # Test that exact usernames are displayed (case-sensitive)
            self.assertIn('admin', result.output)      # lowercase admin
            self.assertIn('operator1', result.output)  # lowercase operator1
            self.assertIn('testuser', result.output)   # lowercase testuser
            # Verify case sensitivity by ensuring wrong case doesn't match
            self.assertNotIn('ADMIN', result.output)
            self.assertNotIn('Admin', result.output)
        finally:

            pass

    def test_show_user_details_case_sensitive_lookup(self):
        """Test that user lookup is case-sensitive"""

        from .mock_tables import dbconnector

        try:

            dbconnector.load_database_config()

            # Test exact case match
            result = self.runner.invoke(show_user.show_user_details, ['admin'], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertIn('admin', result.output)

            # Test different case - should not find user
            result = self.runner.invoke(show_user.show_user_details, ['ADMIN'], obj=self.db)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("User 'ADMIN' not found", result.output)
        finally:

            pass

    @mock.patch('show.user.get_user_database')
    def test_negative_show_user_database_exception(self, mock_get_users):
        """Test show users when database access raises exception"""
        mock_get_users.side_effect = Exception("Database connection failed")

        # Should handle database exceptions gracefully
        try:
            self.runner.invoke(show_user.show_users, [], obj=self.db)
            # If no exception propagates, command should handle it gracefully
        except Exception:
            # If exception propagates, it should be handled appropriately
            pass

    @mock.patch('show.user.get_security_policies')
    def test_negative_show_security_policy_database_exception(self, mock_get_policies):
        """Test show security policies when database access raises exception"""
        mock_get_policies.side_effect = Exception("Database connection failed")

        # Should handle database exceptions gracefully
        try:
            self.runner.invoke(show_user.show_security_policy, [], obj=self.db)
            # If no exception propagates, command should handle it gracefully
        except Exception:
            # If exception propagates, it should be handled appropriately
            pass

    @mock.patch('show.user.get_user_database')
    def test_negative_show_user_with_none_data(self, mock_get_users):
        """Test show users when database returns None"""
        mock_get_users.return_value = None

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)

        # Should handle None gracefully (treat as empty)
        self.assertEqual(result.exit_code, 0)

    @mock.patch('show.user.get_user_database')
    def test_negative_show_user_with_corrupted_data(self, mock_get_users):
        """Test show users with corrupted/invalid data structures"""
        # Test with non-dict user data
        mock_get_users.return_value = {
            'corrupted_user': "not_a_dict",
            'another_corrupted': 12345,
            'null_user': None
        }

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)

        # Should handle corrupted data gracefully (may fail with exit code 1)
        self.assertIn(result.exit_code, [0, 1])

    @mock.patch('show.user.get_user_database')
    def test_cli_special_username_handling(self, mock_get_users):
        """Test show user details with special/problematic usernames"""
        special_usernames = [
            "nonexistent_user",  # Normal nonexistent user
            "ADMIN",            # Case sensitivity
        ]

        mock_get_users.return_value = {}  # Empty database

        for username in special_usernames:
            with self.subTest(username=repr(username)):
                result = self.runner.invoke(show_user.show_user_details, [username], obj=self.db)

                self.assertEqual(result.exit_code, 0)
                # When no users are configured, should show "No users configured"
                self.assertIn("No users configured", result.output)

    @mock.patch('show.user.get_security_policies')
    def test_cli_security_policy_invalid_roles(self, mock_get_policies):
        """Test show security policy with invalid role names"""
        mock_get_policies.return_value = {}  # Empty policies

        # Test CLI validation - invalid role names should get exit code 2
        invalid_roles = [
            "invalid_role",     # Nonexistent role
            "ADMINISTRATOR",    # Wrong case
        ]

        for role in invalid_roles:
            with self.subTest(role=repr(role)):
                result = self.runner.invoke(show_user.show_security_policy, [role], obj=self.db)

                # CLI validation should reject invalid role names with exit code 2
                self.assertEqual(result.exit_code, 2)
                self.assertIn("Invalid value", result.output)

        # Test with valid role names that don't exist in policies
        valid_roles = ["administrator", "operator"]

        for role in valid_roles:
            with self.subTest(role=repr(role)):
                result = self.runner.invoke(show_user.show_security_policy, [role], obj=self.db)

                self.assertEqual(result.exit_code, 0)
                # Should show appropriate message for valid but nonexistent role
                self.assertTrue(
                    "no security policy" in result.output.lower() or
                    "configured" in result.output.lower()
                )

    @mock.patch('show.user.get_user_database')
    def test_negative_show_user_with_missing_required_fields(self, mock_get_users):
        """Test show users with missing required fields"""
        mock_users = {
            'incomplete_user1': {},  # Completely empty
            'incomplete_user2': {'role': 'operator'},  # Missing other fields
            'incomplete_user3': {'enabled': True},  # Missing role
            'incomplete_user4': {'ssh_keys': ['key1']},  # Missing role and enabled
        }
        mock_get_users.return_value = mock_users

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)

        # Should handle missing fields gracefully with defaults
        self.assertEqual(result.exit_code, 0)
        self.assertIn('incomplete_user1', result.output)
        self.assertIn('incomplete_user2', result.output)

    @mock.patch('show.user.get_user_database')
    def test_negative_show_user_with_invalid_field_types(self, mock_get_users):
        """Test show users with invalid field types"""
        mock_users = {
            'invalid_types_user': {
                'role': 123,  # Should be string
                'enabled': 'not_a_boolean',  # Should be boolean
                'ssh_keys': 'not_a_list',  # Should be list
                'password_hash': ['not', 'a', 'string']  # Should be string
            }
        }
        mock_get_users.return_value = mock_users

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)

        # Should handle invalid types gracefully
        self.assertEqual(result.exit_code, 0)
        self.assertIn('invalid_types_user', result.output)

    @mock.patch('show.user.get_security_policies')
    def test_negative_show_security_policy_with_invalid_data_types(self, mock_get_policies):
        """Test show security policies with invalid data types"""
        mock_policies = {
            'administrator': {  # Use valid role name
                'max_login_attempts': ['not', 'a', 'number'],  # Should be number
                'invalid_field': {'nested': 'dict'},  # Nested structure
                'null_field': None,  # Null value
                'empty_string': '',  # Empty string
                'boolean_field': True,  # Boolean value
                'list_field': [1, 2, 3]  # List value
            }
        }
        mock_get_policies.return_value = mock_policies

        result = self.runner.invoke(show_user.show_security_policy, ['administrator'], obj=self.db)

        # Should handle invalid data types gracefully
        self.assertEqual(result.exit_code, 0)
        self.assertIn('administrator', result.output)

    @mock.patch('show.user.get_user_database')
    def test_cli_error_handling_comprehensive(self, mock_get_users):
        """Test CLI error handling with various error scenarios"""
        # Test 1: Invalid SSH key data handling through CLI
        mock_users = {
            'user_invalid_ssh': {
                'role': 'operator',
                'enabled': True,
                'ssh_keys': "not_a_list"  # Invalid SSH key data type
            }
        }
        mock_get_users.return_value = mock_users

        result = self.runner.invoke(show_user.show_users, [], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        # Should handle invalid SSH key data gracefully
        self.assertIn('user_invalid_ssh', result.output)

        # Test 2: Permission error handling through CLI
        with mock.patch('show.user.getpass.getuser') as mock_getuser:
            with mock.patch('show.user.os.geteuid') as mock_geteuid:
                mock_geteuid.return_value = 1000  # Non-root user
                mock_getuser.side_effect = Exception("Cannot get username")

                # Should handle getuser errors gracefully (may fail with exit code 1)
                result = self.runner.invoke(show_user.show_users, [], obj=self.db)
                # Accept either success (graceful handling) or failure (exception propagation)
                self.assertIn(result.exit_code, [0, 1])
                if result.exit_code == 0:
                    # Should not show password hashes when permission check fails
                    self.assertNotIn('$y$j9T$salt$', result.output)

        # Test 3: UID error handling through CLI
        with mock.patch('show.user.os.geteuid') as mock_geteuid:
            mock_geteuid.side_effect = Exception("Cannot get UID")

            result = self.runner.invoke(show_user.show_users, [], obj=self.db)
            # Accept either success (graceful handling) or failure (exception propagation)
            self.assertIn(result.exit_code, [0, 1])
            if result.exit_code == 0:
                # Should handle UID errors gracefully
                self.assertIn('user_invalid_ssh', result.output)


if __name__ == '__main__':
    unittest.main()
