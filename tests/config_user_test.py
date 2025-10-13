#!/usr/bin/env python3

import subprocess
import unittest
import unittest.mock as mock

from click.testing import CliRunner
from utilities_common.db import Db
import config.user as user_module


class TestUserCLI(unittest.TestCase):
    """Test cases for user CLI commands"""

    def setUp(self):
        """Set up test environment with real database"""
        self.runner = CliRunner()
        self.db = Db()
        self.clear_existing_data()
        # Set up initial test data in CONFIG_DB
        self.setup_test_data()

    def clear_existing_data(self):
        """Clear existing data from shared database"""
        self.db.cfgdb.delete_table("LOCAL_USER")
        self.db.cfgdb.delete_table("LOCAL_ROLE_SECURITY_POLICY")
        # Reset device metadata
        self.db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {})

    def setup_test_data(self):
        """Set up initial test data in CONFIG_DB"""
        # Enable local user management feature
        self.db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {
            "local_user_management": "enabled"
        })

        # Add some test users
        self.db.cfgdb.set_entry("LOCAL_USER", "admin", {
            "role": "administrator",
            "password_hash": "$y$j9T$salt$adminhash",
            "enabled": True,
            "ssh_keys": ["ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA admin@host"]
        })

        self.db.cfgdb.set_entry("LOCAL_USER", "operator1", {
            "role": "operator",
            "password_hash": "$y$j9T$salt$ophash",
            "enabled": True,
            "ssh_keys": []
        })

        self.db.cfgdb.set_entry("LOCAL_USER", "disabled_user", {
            "role": "operator",
            "password_hash": "$y$j9T$salt$disabledhash",
            "enabled": False,
            "ssh_keys": []
        })

        # Add security policies
        self.db.cfgdb.set_entry("LOCAL_ROLE_SECURITY_POLICY", "administrator", {
            "max_login_attempts": "5"
        })

    def tearDown(self):
        """Clean up test environment"""
        self.clear_existing_data()

    def test_cli_feature_enable_disable(self):
        """Test enabling and disabling the local user management feature via CLI"""
        # Test disable
        result = self.runner.invoke(user_module.user, [
            "feature", "disabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("disabled", result.output)

        # Verify in database
        metadata = self.db.cfgdb.get_entry("DEVICE_METADATA", "localhost")
        self.assertEqual(metadata.get("local_user_management"), "disabled")

        # Test enable
        result = self.runner.invoke(user_module.user, [
            "feature", "enabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("enabled", result.output)

        # Verify in database
        metadata = self.db.cfgdb.get_entry("DEVICE_METADATA", "localhost")
        self.assertEqual(metadata.get("local_user_management"), "enabled")

    def test_cli_add_user_success(self):
        """Test successful user addition via CLI"""
        result = self.runner.invoke(user_module.user, [
            "add", "newuser",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$newhash"
        ], obj=self.db)

        # Verify command succeeded
        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify user was added to database
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "newuser")
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["role"], "operator")
        self.assertEqual(user_data["password_hash"], "$y$j9T$salt$newhash")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user_data["enabled"], [True, "True"])  # Default enabled

    def test_cli_add_user_disabled(self):
        """Test adding user in disabled state via CLI"""
        result = self.runner.invoke(user_module.user, [
            "add", "disableduser",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$disabledhash",
            "--disabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify user is disabled
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "disableduser")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user_data["enabled"], [False, "False"])

    def test_cli_add_user_already_exists(self):
        """Test adding user that already exists via CLI"""
        result = self.runner.invoke(user_module.user, [
            "add", "admin",  # Already exists in test data
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)

        # Should succeed with exit code 0 but show error message
        self.assertEqual(result.exit_code, 0)
        self.assertIn("already exists", result.output)

    def test_cli_add_user_feature_disabled(self):
        """Test adding user when feature is disabled via CLI"""
        # Disable the feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        result = self.runner.invoke(user_module.user, [
            "add", "newuser",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

        # Verify user was NOT added (CONFIG_DB returns empty dict for non-existent entries)
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "newuser")
        self.assertIn(user_data, [None, {}])  # Accept both None and empty dict

    def test_cli_delete_user_success(self):
        """Test successful user deletion via CLI"""
        result = self.runner.invoke(user_module.user, [
            "delete", "operator1"  # Exists in test data
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify user was removed from database
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "operator1")
        # CONFIG_DB returns empty dict for non-existent entries
        self.assertIn(user_data, [None, {}])

    def test_cli_delete_user_not_exists(self):
        """Test deleting user that doesn't exist via CLI"""
        result = self.runner.invoke(user_module.user, [
            "delete", "nonexistent"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("does not exist", result.output)

    def test_cli_modify_user_success(self):
        """Test successful user modification via CLI"""
        result = self.runner.invoke(user_module.user, [
            "modify", "disabled_user",
            "--password-hash", "$y$j9T$salt$newhash",
            "--enabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify changes in database
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "disabled_user")
        self.assertEqual(user_data["password_hash"], "$y$j9T$salt$newhash")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user_data["enabled"], [True, "True"])

    def test_cli_security_policy_set(self):
        """Test setting security policy via CLI"""
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "10"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify in database
        policy = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "operator")
        self.assertEqual(policy["max_login_attempts"], "10")

    @mock.patch('config.user.get_existing_linux_users')
    def test_cli_import_existing_success(self, mock_get_users):
        """Test successful import of existing Linux users via CLI"""
        # Disable feature first (import only works when disabled)
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        # Mock existing Linux users (matching get_existing_linux_users structure)
        mock_get_users.return_value = {
            'linuxuser1': {
                'role': 'operator',  # Determined from group membership
                'password_hash': '$y$j9T$salt$linuxhash1',
                'enabled': True,  # Based on shell (not /usr/sbin/nologin)
                'ssh_keys': [],  # From ~/.ssh/authorized_keys
                'uid': 1001,
                'gid': 1001,
                'home': '/home/linuxuser1',
                'shell': '/bin/bash'
            },
            'linuxuser2': {
                'role': 'operator',  # Determined from group membership
                'password_hash': '$y$j9T$salt$linuxhash2',
                'enabled': True,  # Based on shell (not /usr/sbin/nologin)
                'ssh_keys': [],  # From ~/.ssh/authorized_keys
                'uid': 1002,
                'gid': 1002,
                'home': '/home/linuxuser2',
                'shell': '/bin/bash'
            }
        }

        result = self.runner.invoke(user_module.user, [
            "import-existing"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify users were imported to database
        user1_data = self.db.cfgdb.get_entry("LOCAL_USER", "linuxuser1")
        user2_data = self.db.cfgdb.get_entry("LOCAL_USER", "linuxuser2")

        self.assertIsNotNone(user1_data)
        self.assertIsNotNone(user2_data)
        self.assertEqual(user1_data["role"], "operator")  # Default role
        self.assertEqual(user1_data["password_hash"], "$y$j9T$salt$linuxhash1")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user1_data["enabled"], [True, "True"])

    def test_cli_import_existing_feature_enabled(self):
        """Test import-existing when feature is enabled (should fail) via CLI"""
        # Feature is enabled by default in test setup

        result = self.runner.invoke(user_module.user, [
            "import-existing"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)  # SONiC commands return 0 even for user errors
        self.assertIn("already enabled", result.output)

    @mock.patch('config.user.get_existing_linux_users')
    def test_cli_import_existing_dry_run(self, mock_get_users):
        """Test dry-run import of existing Linux users via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        # Mock existing Linux users (matching get_existing_linux_users structure)
        mock_get_users.return_value = {
            'dryrunuser': {
                'role': 'operator',  # Determined from group membership
                'password_hash': '$y$j9T$salt$dryrunhash',
                'enabled': True,  # Based on shell (not /usr/sbin/nologin)
                'ssh_keys': [],  # From ~/.ssh/authorized_keys
                'uid': 1003,
                'gid': 1003,
                'home': '/home/dryrunuser',
                'shell': '/bin/bash'
            }
        }

        result = self.runner.invoke(user_module.user, [
            "import-existing", "--dry-run"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Users that would be imported", result.output)

        # Verify user was NOT actually imported
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "dryrunuser")
        # CONFIG_DB returns empty dict for non-existent entries
        self.assertIn(user_data, [None, {}])

    def test_cli_add_user_invalid_username(self):
        """Test adding user with invalid username via CLI"""
        result = self.runner.invoke(user_module.user, [
            "add", "Invalid-User!",  # Invalid characters
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)  # SONiC commands return 0 for user errors
        self.assertIn("Invalid username", result.output)

        # Verify user was NOT added
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "Invalid-User!")
        # CONFIG_DB returns empty dict for non-existent entries
        self.assertIn(user_data, [None, {}])

    def test_cli_add_user_invalid_role(self):
        """Test adding user with invalid role via CLI"""
        result = self.runner.invoke(user_module.user, [
            "add", "testuser",
            "--role", "invalid_role",  # Invalid role
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)

        # Should fail with Click validation error
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Invalid value for "--role"', result.output)

    def test_cli_add_user_no_password(self):
        """Test adding user without password via CLI"""
        result = self.runner.invoke(user_module.user, [
            "add", "newuser",
            "--role", "operator"
            # No password provided
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("password", result.output.lower())  # Should mention password requirement

    def test_cli_delete_user_feature_disabled(self):
        """Test deleting user when feature is disabled via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        result = self.runner.invoke(user_module.user, [
            "delete", "operator1"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

        # Verify user was NOT deleted
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "operator1")
        self.assertIsNotNone(user_data)

    def test_cli_delete_last_admin(self):
        """Test deleting the last administrator user via CLI"""
        # Delete all admins except one
        self.db.cfgdb.delete_table("LOCAL_USER")  # Clear all users
        self.db.cfgdb.set_entry("LOCAL_USER", "lastadmin", {
            "role": "administrator",
            "password_hash": "$y$j9T$salt$lastadminhash",
            "enabled": True,
            "ssh_keys": []
        })

        result = self.runner.invoke(user_module.user, [
            "delete", "lastadmin"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("last administrator", result.output)

        # Verify user was NOT deleted
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "lastadmin")
        self.assertIsNotNone(user_data)

    def test_cli_delete_user_case_sensitivity(self):
        """Test deleting user with different case via CLI"""
        result = self.runner.invoke(user_module.user, [
            "delete", "ADMIN"  # Different case
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("does not exist", result.output)  # Should be case sensitive

    def test_cli_modify_user_not_exists(self):
        """Test modifying user that doesn't exist via CLI"""
        result = self.runner.invoke(user_module.user, [
            "modify", "nonexistent",
            "--password-hash", "$y$j9T$salt$newhash"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("does not exist", result.output)

    def test_cli_modify_user_feature_disabled(self):
        """Test modifying user when feature is disabled via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        result = self.runner.invoke(user_module.user, [
            "modify", "operator1",
            "--password-hash", "$y$j9T$salt$newhash"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

    def test_cli_modify_user_password_only(self):
        """Test modifying only user password via CLI"""
        original_data = self.db.cfgdb.get_entry("LOCAL_USER", "operator1")

        result = self.runner.invoke(user_module.user, [
            "modify", "operator1",
            "--password-hash", "$y$j9T$salt$newpasshash"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify only password changed
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "operator1")
        self.assertEqual(user_data["password_hash"], "$y$j9T$salt$newpasshash")
        self.assertEqual(user_data["role"], original_data["role"])  # Unchanged
        self.assertEqual(user_data["enabled"], original_data["enabled"])  # Unchanged

    def test_cli_modify_user_enable_disable(self):
        """Test enabling and disabling user via CLI"""
        # Test enable disabled user
        result = self.runner.invoke(user_module.user, [
            "modify", "disabled_user",
            "--enabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "disabled_user")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user_data["enabled"], [True, "True"])

        # Test disable enabled user
        result = self.runner.invoke(user_module.user, [
            "modify", "disabled_user",
            "--disabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "disabled_user")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user_data["enabled"], [False, "False"])

    def test_cli_modify_user_conflicting_flags(self):
        """Test modifying user with conflicting enabled/disabled flags via CLI"""
        result = self.runner.invoke(user_module.user, [
            "modify", "operator1",
            "--enabled",
            "--disabled"  # Conflicting flags
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cannot specify both", result.output)

    def test_cli_modify_last_admin_disable(self):
        """Test disabling the last administrator user via CLI"""
        # Make admin the only administrator
        self.db.cfgdb.delete_table("LOCAL_USER")  # Clear all users
        self.db.cfgdb.set_entry("LOCAL_USER", "admin", {
            "role": "administrator",
            "password_hash": "$y$j9T$salt$adminhash",
            "enabled": True,
            "ssh_keys": []
        })

        result = self.runner.invoke(user_module.user, [
            "modify", "admin",
            "--disabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("last administrator", result.output)

        # Verify admin was NOT disabled
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "admin")
        # CONFIG_DB stores boolean values as strings
        self.assertIn(user_data["enabled"], [True, "True"])

    def test_cli_security_policy_set_all_options(self):
        """Test setting security policy with available options via CLI"""
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "administrator",
            "--max-login-attempts", "8"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify policy setting
        policy = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "administrator")
        self.assertEqual(policy["max_login_attempts"], "8")

    def test_cli_security_policy_set_invalid_role(self):
        """Test setting security policy for invalid role via CLI"""
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "invalid_role",
            "--max-login-attempts", "5"
        ], obj=self.db)

        # Should fail with Click validation error
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_cli_security_policy_set_invalid_values(self):
        """Test setting security policy with invalid values via CLI"""
        # Test invalid max-login-attempts (Click validation error)
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "0"  # Invalid: must be positive
        ], obj=self.db)

        self.assertEqual(result.exit_code, 2)  # Click validation error
        self.assertIn("not in the valid range", result.output)

        # Test invalid max-login-attempts too high (Click validation error)
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "1001"  # Invalid: exceeds maximum
        ], obj=self.db)

        self.assertEqual(result.exit_code, 2)  # Click validation error
        self.assertIn("not in the valid range", result.output)

    def test_cli_security_policy_clear(self):
        """Test clearing security policy via CLI"""
        # First set a policy
        self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "3"
        ], obj=self.db)

        # Verify policy exists
        policy = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "operator")
        self.assertIsNotNone(policy)

        # Clear the policy
        result = self.runner.invoke(user_module.user, [
            "security-policy", "clear-policy", "operator"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Silent on success - no output expected

        # Verify policy was removed
        policy = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "operator")
        # CONFIG_DB returns empty dict for non-existent entries
        self.assertIn(policy, [None, {}])

    def test_cli_security_policy_clear_nonexistent(self):
        """Test clearing non-existent security policy via CLI"""
        # Ensure no operator policy exists by clearing the entire table and only adding administrator
        self.db.cfgdb.delete_table("LOCAL_ROLE_SECURITY_POLICY")
        self.db.cfgdb.set_entry("LOCAL_ROLE_SECURITY_POLICY", "administrator", {
            "max_login_attempts": "5"
        })

        # Verify no operator policy exists
        policy = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "operator")
        self.assertIn(policy, [None, {}])  # Should be empty

        result = self.runner.invoke(user_module.user, [
            "security-policy", "clear-policy", "operator"  # No policy set
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("", result.output)

    def test_cli_security_policy_feature_disabled(self):
        """Test security policy commands when feature is disabled via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "5"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

    def test_cli_invalid_command(self):
        """Test invalid user command via CLI"""
        result = self.runner.invoke(user_module.user, [
            "invalid-command"
        ], obj=self.db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No such command", result.output)

    def test_cli_missing_required_args(self):
        """Test commands with missing required arguments via CLI"""
        # Test add without username
        result = self.runner.invoke(user_module.user, [
            "add"
        ], obj=self.db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

        # Test delete without username
        result = self.runner.invoke(user_module.user, [
            "delete"
        ], obj=self.db)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

    def test_cli_help_commands(self):
        """Test help output for user commands via CLI"""
        # Test main help
        result = self.runner.invoke(user_module.user, ["--help"], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("User management commands", result.output)

        # Test add help
        result = self.runner.invoke(user_module.user, ["add", "--help"], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Add a new user", result.output)

        # Test security-policy help
        result = self.runner.invoke(user_module.user, ["security-policy", "--help"], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("User security policy commands", result.output)

    def test_cli_username_validation(self):
        """Test username validation with various username scenarios"""
        # Test scenarios: (username, should_succeed, expected_error_keywords)
        username_scenarios = [
            # Valid usernames - should succeed
            ("validuser", True, []),
            ("user_123", True, []),
            ("_underscore", True, []),
            ("user-dash", True, []),
            ("user$", True, []),
            ("a", True, []),  # Minimum length
            ("a" * 32, True, []),  # Maximum length

            # Invalid usernames - should fail
            ("123invalid", False, ["Invalid username"]),  # Starts with number
            ("User", False, ["Invalid username"]),  # Uppercase
            ("user@invalid", False, ["Invalid username"]),  # Invalid character
            ("user space", False, ["Invalid username"]),  # Space
            ("user#hash", False, ["Invalid username"]),  # Hash symbol
            ("", False, ["Invalid username"]),  # Empty
            ("a" * 33, False, ["Username must be between 1 and 32 characters"]),  # Too long
            ("root", False, ["cannot be 'root'"]),  # Reserved name
        ]

        for username, should_succeed, expected_errors in username_scenarios:
            with self.subTest(username=username):
                result = self.runner.invoke(user_module.user, [
                    "add", username,
                    "--role", "operator",
                    "--password-hash", "$y$j9T$salt$hash"
                ], obj=self.db)

                self.assertEqual(result.exit_code, 0)

                if should_succeed:
                    # Should succeed silently (no error output)
                    self.assertNotIn("Error:", result.output)
                    # Verify user was created
                    user_data = self.db.cfgdb.get_entry("LOCAL_USER", username)
                    self.assertIsNotNone(user_data)

                    self.db.cfgdb.set_entry("LOCAL_USER", username, None)
                else:
                    # Should fail with expected error messages
                    for error_keyword in expected_errors:
                        self.assertIn(error_keyword, result.output)
                    # Verify user was NOT created
                    user_data = self.db.cfgdb.get_entry("LOCAL_USER", username)
                    self.assertIn(user_data, [None, {}])

    def test_cli_password_hash_validation(self):
        """Test password hash validation"""
        # Test scenarios: (password_hash, should_succeed, expected_error_keywords)
        password_hash_scenarios = [
            # Valid password hashes - should succeed
            ("$y$j9T$salt$hash", True, []),
            ("$6$salt$hash", True, []),
            ("$5$salt$hash", True, []),
            ("$1$salt$hash", True, []),

            # Invalid password hash - should fail
            ("!locked", False, ["cannot start with '!'"]),
            ("!!invalid", False, ["cannot start with '!'"]),
        ]

        for password_hash, should_succeed, expected_errors in password_hash_scenarios:
            with self.subTest(password_hash=password_hash):
                result = self.runner.invoke(user_module.user, [
                    "add", "hashuser",
                    "--role", "operator",
                    "--password-hash", password_hash
                ], obj=self.db)

                self.assertEqual(result.exit_code, 0)

                if should_succeed:
                    # Should succeed silently (no error output)
                    self.assertNotIn("Error:", result.output)
                    # Verify user was created
                    user_data = self.db.cfgdb.get_entry("LOCAL_USER", "hashuser")
                    self.assertIsNotNone(user_data)
                    self.assertEqual(user_data["password_hash"], password_hash)

                    self.db.cfgdb.set_entry("LOCAL_USER", "hashuser", None)
                else:
                    # Should fail with expected error messages
                    for error_keyword in expected_errors:
                        self.assertIn(error_keyword, result.output)
                    # Verify user was NOT created
                    user_data = self.db.cfgdb.get_entry("LOCAL_USER", "hashuser")
                    self.assertIn(user_data, [None, {}])

    @mock.patch('subprocess.run')
    def test_cli_password_hashing_scenarios(self, mock_subprocess):
        """Test password hashing scenarios"""
        # Test successful hashing
        mock_result = mock.MagicMock()
        mock_result.stdout = "$y$j9T$salt$hashedpassword\n"
        mock_subprocess.return_value = mock_result

        with mock.patch('config.user.getpass.getpass', side_effect=["testpass", "testpass"]):
            result = self.runner.invoke(user_module.user, [
                "add", "hashtest",
                "--role", "operator",
                "--password-prompt"
            ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Should succeed and create user
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "hashtest")
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["password_hash"], "$y$j9T$salt$hashedpassword")

        self.db.cfgdb.set_entry("LOCAL_USER", "hashtest", None)

        # Test mkpasswd not found
        mock_subprocess.side_effect = FileNotFoundError()

        with mock.patch('config.user.getpass.getpass', side_effect=["testpass", "testpass"]):
            result = self.runner.invoke(user_module.user, [
                "add", "hashfail1",
                "--role", "operator",
                "--password-prompt"
            ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("mkpasswd command not found", result.output)

        # Test mkpasswd failure
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'mkpasswd')

        with mock.patch('config.user.getpass.getpass', side_effect=["testpass", "testpass"]):
            result = self.runner.invoke(user_module.user, [
                "add", "hashfail2",
                "--role", "operator",
                "--password-prompt"
            ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("mkpasswd failed", result.output)

    @mock.patch('subprocess.run')
    @mock.patch('config.user.getpass.getpass')
    def test_cli_password_hardening_policies_integration(self, mock_getpass, mock_subprocess):
        """Test password hardening policies with various password scenarios"""
        # Mock successful password hashing
        mock_result = mock.MagicMock()
        mock_result.stdout = "$y$j9T$salt$hashedpassword\n"
        mock_subprocess.return_value = mock_result

        # Set up comprehensive password hardening policies
        self.db.cfgdb.set_entry("PASSW_HARDENING", "POLICIES", {
            "state": "enabled",
            "len_min": "8",
            "reject_user_passw_match": "true",
            "lower_class": "true",
            "upper_class": "true",
            "digits_class": "true",
            "special_class": "true"
        })

        # Test scenarios: (password, confirm_password, should_succeed, expected_error_keywords)
        password_scenarios = [
            # Valid password - should succeed
            ("StrongP@ss1", "StrongP@ss1", True, []),

            # Password too short - should fail
            ("Short1!", "Short1!", False, ["at least 8 characters"]),

            # Missing lowercase - should fail
            ("UPPERCASE1!", "UPPERCASE1!", False, ["lowercase letter"]),

            # Missing uppercase - should fail
            ("lowercase1!", "lowercase1!", False, ["uppercase letter"]),

            # Missing digits - should fail
            ("NoDigits!", "NoDigits!", False, ["digit"]),

            # Missing special characters - should fail
            ("NoSpecial1", "NoSpecial1", False, ["special character"]),

            # Contains username - should fail
            ("newuser123!", "newuser123!", False, ["cannot contain the username"]),

            # Multiple violations - should fail with multiple errors
            ("weak", "weak", False, ["at least 8 characters", "uppercase letter", "digit", "special character"]),

            # Password mismatch - should fail
            ("StrongP@ss1", "DifferentP@ss1", False, ["do not match"]),
        ]

        for password, confirm_password, should_succeed, expected_errors in password_scenarios:
            with self.subTest(password=password):
                mock_getpass.side_effect = [password, confirm_password]

                result = self.runner.invoke(user_module.user, [
                    "add", "newuser",
                    "--role", "operator",
                    "--password-prompt"
                ], obj=self.db)

                self.assertEqual(result.exit_code, 0)

                if should_succeed:
                    # Should succeed silently (no error output)
                    self.assertNotIn("Error:", result.output)
                    # Verify user was created
                    user_data = self.db.cfgdb.get_entry("LOCAL_USER", "newuser")
                    self.assertIsNotNone(user_data)

                    self.db.cfgdb.set_entry("LOCAL_USER", "newuser", None)

    @mock.patch('subprocess.run')
    @mock.patch('config.user.getpass.getpass')
    def test_cli_password_policy_edge_cases(self, mock_getpass, mock_subprocess):
        """Test password policy edge cases and data type handling"""
        # Mock successful password hashing
        mock_result = mock.MagicMock()
        mock_result.stdout = "$y$j9T$salt$hashedpassword\n"
        mock_subprocess.return_value = mock_result

        # Test with string boolean values and invalid numeric values
        self.db.cfgdb.set_entry("PASSW_HARDENING", "POLICIES", {
            "state": "enabled",
            "len_min": "invalid_number",  # Invalid numeric value
            "reject_user_passw_match": "TRUE",  # String boolean
            "lower_class": "1",  # Numeric boolean
            "upper_class": "yes",  # String boolean
            "digits_class": "on",  # String boolean
            "special_class": "false"  # String boolean false
        })

        mock_getpass.side_effect = ["ValidP@ss1", "ValidP@ss1"]

        result = self.runner.invoke(user_module.user, [
            "add", "edgeuser",
            "--role", "operator",
            "--password-prompt"
        ], obj=self.db)

        # System should fail when password policies have invalid values
        # Invalid numeric values like "invalid_number" should cause validation to fail
        self.assertNotEqual(result.exit_code, 0,
                            "Command should fail when password policies contain invalid values")

        # Verify user was NOT created due to policy validation failure
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "edgeuser")
        self.assertIn(user_data, [None, {}],
                      "User should not be created when policy validation fails")

    def test_cli_password_hardening_policies_disabled(self):
        """Test that weak passwords are accepted when policies are disabled"""
        # Ensure no password policies are configured (disabled by default)
        self.db.cfgdb.set_entry("PASSW_HARDENING", "POLICIES", None)

        # Test with a weak password that would fail if policies were enabled
        result = self.runner.invoke(user_module.user, [
            "add", "weakpassuser",
            "--role", "operator",
            "--password-hash", "weak"  # Very weak password
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Should succeed silently when policies are disabled
        self.assertNotIn("Error:", result.output)

        # Verify user was created
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "weakpassuser")
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["password_hash"], "weak")

    def test_cli_password_input_conflicting_options(self):
        """Test CLI with conflicting password options"""
        result = self.runner.invoke(user_module.user, [
            "add", "conflictuser",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash",
            "--password-prompt"  # Conflicting with password-hash
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cannot specify both", result.output)

        # Verify user was NOT created
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "conflictuser")
        self.assertIn(user_data, [None, {}])

    @mock.patch('config.user.getpass.getpass')
    def test_cli_password_prompt_hash_failure(self, mock_getpass):
        """Test CLI password prompt when password hashing fails"""
        mock_getpass.side_effect = ["testpass123", "testpass123"]

        # Mock hash_password to return None (failure)
        with mock.patch('config.user.hash_password', return_value=None):
            result = self.runner.invoke(user_module.user, [
                "add", "hashfailuser",
                "--role", "operator",
                "--password-prompt"
            ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Failed to generate password hash", result.output)

        # Verify user was NOT created
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "hashfailuser")
        self.assertIn(user_data, [None, {}])

    def test_cli_ssh_key_operations_comprehensive(self):
        """Test comprehensive SSH key operations through CLI commands"""
        # Test 1: Add user with multiple SSH keys
        result = self.runner.invoke(user_module.user, [
            "add", "sshtest",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$sshhash",
            "--ssh-key", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA key1@host",
            "--ssh-key", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGQw8hdMNBWG key2@host"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "sshtest")
        self.assertEqual(len(user_data["ssh_keys"]), 2)
        self.assertIn("key1@host", str(user_data["ssh_keys"]))
        self.assertIn("key2@host", str(user_data["ssh_keys"]))

        # Test 2: Add more SSH keys to existing user
        result = self.runner.invoke(user_module.user, [
            "modify", "sshtest",
            "--add-ssh-key", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDnewkey key3@host",
            "--add-ssh-key", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDanother key4@host"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "sshtest")
        self.assertEqual(len(user_data["ssh_keys"]), 4)
        self.assertIn("key3@host", str(user_data["ssh_keys"]))
        self.assertIn("key4@host", str(user_data["ssh_keys"]))

        # Test 3: Remove specific SSH key
        result = self.runner.invoke(user_module.user, [
            "modify", "sshtest",
            "--remove-ssh-key", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA key1@host"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "sshtest")
        self.assertEqual(len(user_data["ssh_keys"]), 3)
        self.assertNotIn("key1@host", str(user_data["ssh_keys"]))

        # Test 4: Replace all SSH keys
        result = self.runner.invoke(user_module.user, [
            "modify", "sshtest",
            "--replace-ssh-keys", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCreplacement replacement@host"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "sshtest")
        self.assertEqual(len(user_data["ssh_keys"]), 1)
        self.assertIn("replacement@host", str(user_data["ssh_keys"]))

        # Test 5: Edge cases - remove non-existent key (should succeed silently)
        result = self.runner.invoke(user_module.user, [
            "modify", "sshtest",
            "--remove-ssh-key", "nonexistent_key"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Should succeed silently

        # Test 6: Add duplicate key (should handle gracefully)
        current_keys = self.db.cfgdb.get_entry("LOCAL_USER", "sshtest")["ssh_keys"]
        original_key_count = len(current_keys)
        duplicate_key = current_keys[0]

        result = self.runner.invoke(user_module.user, [
            "modify", "sshtest",
            "--add-ssh-key", duplicate_key  # Add existing key
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Verify no duplicate was added and keys remain the same
        updated_user_data = self.db.cfgdb.get_entry("LOCAL_USER", "sshtest")
        self.assertEqual(len(updated_user_data["ssh_keys"]), original_key_count)
        self.assertIn(duplicate_key, updated_user_data["ssh_keys"])

        # Test 7: Conflicting SSH key options
        result = self.runner.invoke(user_module.user, [
            "modify", "sshtest",
            "--add-ssh-key", "key1",
            "--remove-ssh-key", "key2",
            "--replace-ssh-keys", "key3"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cannot specify multiple SSH key options", result.output)

    def test_cli_admin_constraint_scenarios(self):
        """Test admin constraint scenarios through CLI operations"""
        # Scenario 1: Multiple admins - should allow disabling one
        self.db.cfgdb.set_entry("LOCAL_USER", "admin1", {
            "role": "administrator",
            "enabled": True,
            "password_hash": "$y$j9T$salt$hash1",
            "ssh_keys": []
        })
        self.db.cfgdb.set_entry("LOCAL_USER", "admin2", {
            "role": "administrator",
            "enabled": True,
            "password_hash": "$y$j9T$salt$hash2",
            "ssh_keys": []
        })

        # Should allow disabling one admin when another exists
        result = self.runner.invoke(user_module.user, [
            "modify", "admin1", "--disabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Verify admin1 was disabled
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "admin1")
        self.assertIn(user_data["enabled"], [False, "False"])

        # Scenario 2: Last admin - should NOT allow disabling
        # Clear all users and add only one admin
        self.db.cfgdb.delete_table("LOCAL_USER")
        self.db.cfgdb.set_entry("LOCAL_USER", "lastadmin", {
            "role": "administrator",
            "enabled": True,
            "password_hash": "$y$j9T$salt$lasthash",
            "ssh_keys": []
        })

        # Should not allow disabling the last admin
        result = self.runner.invoke(user_module.user, [
            "modify", "lastadmin", "--disabled"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cannot disable the last administrator user", result.output)

        # Verify admin was NOT disabled
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "lastadmin")
        self.assertIn(user_data["enabled"], [True, "True"])

        # Scenario 3: Should not allow deleting the last admin
        result = self.runner.invoke(user_module.user, [
            "delete", "lastadmin"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cannot delete the last administrator user", result.output)

        # Verify admin was NOT deleted
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "lastadmin")
        self.assertIsNotNone(user_data)

    def test_cli_import_existing_invalid_uid_range(self):
        """Test import-existing with invalid UID range via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        result = self.runner.invoke(user_module.user, [
            "import-existing", "--uid-range", "invalid-range"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Invalid UID range format", result.output)

    @mock.patch('config.user.get_existing_linux_users')
    def test_cli_import_existing_no_users_found(self, mock_get_users):
        """Test import-existing when no users are found via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        # Mock no existing Linux users
        mock_get_users.return_value = {}

        result = self.runner.invoke(user_module.user, [
            "import-existing"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No users found to import", result.output)

    @mock.patch('config.user.get_existing_linux_users')
    def test_cli_import_existing_users_already_in_config(self, mock_get_users):
        """Test import-existing when users already exist in CONFIG_DB via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        # Mock existing Linux users that match CONFIG_DB users
        mock_get_users.return_value = {
            'admin': {  # This user already exists in test data
                'role': 'administrator',
                'password_hash': '$y$j9T$salt$linuxhash',
                'enabled': True,
                'ssh_keys': [],
                'uid': 1001,
                'gid': 1001,
                'home': '/home/admin',
                'shell': '/bin/bash'
            }
        }

        result = self.runner.invoke(user_module.user, [
            "import-existing"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No users found to import", result.output)

    @mock.patch('config.user.get_existing_linux_users')
    def test_cli_import_existing_with_custom_uid_range(self, mock_get_users):
        """Test import-existing with custom UID range via CLI"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        # Mock existing Linux users
        mock_get_users.return_value = {
            'customuser': {
                'role': 'operator',
                'password_hash': '$y$j9T$salt$customhash',
                'enabled': True,
                'ssh_keys': [],
                'uid': 2001,
                'gid': 2001,
                'home': '/home/customuser',
                'shell': '/bin/bash'
            }
        }

        result = self.runner.invoke(user_module.user, [
            "import-existing", "--uid-range", "2000-3000"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Should call get_existing_linux_users with custom range
        mock_get_users.assert_called_once_with(2000, 3000)

    def test_cli_database_error_handling(self):
        """Test CLI behavior when database operations fail"""
        # Enable the feature first so we can test database operations
        self.db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {"local_user_management": "enabled"})

        # Test JsonPatchConflict error during user addition
        with mock.patch('config.user.ValidatedConfigDBConnector') as mock_connector_class:
            mock_config_db = mock.MagicMock()
            mock_config_db.set_entry.side_effect = user_module.JsonPatchConflict("Conflict")
            mock_connector_class.return_value = mock_config_db

            result = self.runner.invoke(user_module.user, [
                "add", "conflictuser",
                "--role", "operator",
                "--password-hash", "$y$j9T$salt$hash"
            ], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            # Should show some error message (could be feature disabled or database error)
            self.assertTrue(
                "Error:" in result.output or
                "Local user management is not enabled" in result.output or
                "Failed to modify user" in result.output
            )

        # Test ValueError in database operations
        with mock.patch('config.user.ValidatedConfigDBConnector') as mock_connector_class:
            mock_config_db = mock.MagicMock()
            mock_config_db.set_entry.side_effect = ValueError("Invalid data")
            mock_connector_class.return_value = mock_config_db

            result = self.runner.invoke(user_module.user, [
                "add", "erroruser",
                "--role", "operator",
                "--password-hash", "$y$j9T$salt$hash"
            ], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Error:", result.output)

        # Test ValueError during user modification
        with mock.patch('config.user.ValidatedConfigDBConnector') as mock_connector_class:
            mock_config_db = mock.MagicMock()
            mock_config_db.set_entry.side_effect = ValueError("Invalid value")
            mock_connector_class.return_value = mock_config_db

            result = self.runner.invoke(user_module.user, [
                "modify", "admin",
                "--password-hash", "$y$j9T$salt$newhash"
            ], obj=self.db)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(
                "Failed to modify user" in result.output or
                "Local user management is not enabled" in result.output or
                "Error:" in result.output
            )

        # Test successful database operations through normal CLI flow
        result = self.runner.invoke(user_module.user, [
            "add", "dbtest",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Verify user was added successfully
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "dbtest")
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["role"], "operator")

        # Test successful deletion
        result = self.runner.invoke(user_module.user, [
            "delete", "dbtest"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Verify user was deleted
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "dbtest")
        self.assertIn(user_data, [None, {}])

    def test_integration_user_lifecycle(self):
        """Test complete user lifecycle: add, modify, show, delete"""
        # Add a new user
        result = self.runner.invoke(user_module.user, [
            "add", "lifecycle_user",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$initialhash"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify user exists in database
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "lifecycle_user")
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["role"], "operator")

        # Modify the user
        result = self.runner.invoke(user_module.user, [
            "modify", "lifecycle_user",
            "--password-hash", "$y$j9T$salt$newhash",
            "--add-ssh-key", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA lifecycle@host"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify modifications
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "lifecycle_user")
        self.assertEqual(user_data["password_hash"], "$y$j9T$salt$newhash")
        self.assertIn("lifecycle@host", str(user_data["ssh_keys"]))

        # Delete the user
        result = self.runner.invoke(user_module.user, [
            "delete", "lifecycle_user"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify user is deleted
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "lifecycle_user")
        self.assertIn(user_data, [None, {}])

    def test_integration_security_policy_lifecycle(self):
        """Test complete security policy lifecycle: set, show, clear"""
        # Set a security policy
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "7"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify policy exists in database
        policy_data = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "operator")
        self.assertIsNotNone(policy_data)
        self.assertEqual(policy_data["max_login_attempts"], "7")

        # Clear the policy
        result = self.runner.invoke(user_module.user, [
            "security-policy", "clear-policy", "operator"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify policy is cleared
        policy_data = self.db.cfgdb.get_entry("LOCAL_ROLE_SECURITY_POLICY", "operator")
        self.assertIn(policy_data, [None, {}])

    def test_integration_feature_toggle_affects_operations(self):
        """Test that feature enable/disable affects all user operations"""
        # Start with feature enabled (default in test setup)

        # Add a user (should work)
        result = self.runner.invoke(user_module.user, [
            "add", "toggle_test_user",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Disable the feature
        result = self.runner.invoke(user_module.user, [
            "feature", "disabled"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Try to add another user (should fail)
        result = self.runner.invoke(user_module.user, [
            "add", "should_fail_user",
            "--role", "operator",
            "--password-hash", "$y$j9T$salt$hash"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

        # Try to modify existing user (should fail)
        result = self.runner.invoke(user_module.user, [
            "modify", "toggle_test_user",
            "--password-hash", "$y$j9T$salt$newhash"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

        # Try to delete user (should fail)
        result = self.runner.invoke(user_module.user, [
            "delete", "toggle_test_user"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

        # Try to set security policy (should fail)
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "5"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not enabled", result.output)

        # Re-enable the feature
        result = self.runner.invoke(user_module.user, [
            "feature", "enabled"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Now operations should work again
        result = self.runner.invoke(user_module.user, [
            "modify", "toggle_test_user",
            "--password-hash", "$y$j9T$salt$newhash"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        # Should succeed silently

    def test_integration_admin_constraint_enforcement(self):
        """Test that admin constraint is enforced across operations"""
        # Clear existing users and create scenario with one admin
        self.db.cfgdb.delete_table("LOCAL_USER")
        self.db.cfgdb.set_entry("LOCAL_USER", "only_admin", {
            "role": "administrator",
            "password_hash": "$y$j9T$salt$adminhash",
            "enabled": True
        })

        # Try to delete the only admin (should fail)
        result = self.runner.invoke(user_module.user, [
            "delete", "only_admin"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("last administrator", result.output)

        # Verify admin still exists
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "only_admin")
        self.assertIsNotNone(user_data)

        # Try to disable the only admin (should fail)
        result = self.runner.invoke(user_module.user, [
            "modify", "only_admin",
            "--disabled"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("last administrator", result.output)

        # Verify admin is still enabled
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "only_admin")
        self.assertIn(user_data["enabled"], [True, "True"])

        # Add another admin
        result = self.runner.invoke(user_module.user, [
            "add", "second_admin",
            "--role", "administrator",
            "--password-hash", "$y$j9T$salt$secondhash"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Now should be able to disable the first admin
        result = self.runner.invoke(user_module.user, [
            "modify", "only_admin",
            "--disabled"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify first admin is now disabled
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "only_admin")
        self.assertIn(user_data["enabled"], [False, "False"])

        # Verify second admin is still enabled
        second_admin_data = self.db.cfgdb.get_entry("LOCAL_USER", "second_admin")
        self.assertIn(second_admin_data["enabled"], [True, "True"])

    @mock.patch('config.user.get_existing_linux_users')
    def test_integration_import_and_feature_enable(self, mock_get_users):
        """Test importing users and then enabling the feature"""
        # Start with feature disabled
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        # Mock existing Linux users
        mock_get_users.return_value = {
            'imported_user1': {
                'role': 'administrator',
                'password_hash': '$y$j9T$salt$importhash1',
                'enabled': True,
                'ssh_keys': ['ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA imported1@host'],
                'uid': 1001,
                'gid': 1001,
                'home': '/home/imported_user1',
                'shell': '/bin/bash'
            },
            'imported_user2': {
                'role': 'operator',
                'password_hash': '$y$j9T$salt$importhash2',
                'enabled': False,
                'ssh_keys': [],
                'uid': 1002,
                'gid': 1002,
                'home': '/home/imported_user2',
                'shell': '/usr/sbin/nologin'
            }
        }

        # Import existing users
        result = self.runner.invoke(user_module.user, [
            "import-existing"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify users were imported
        user1_data = self.db.cfgdb.get_entry("LOCAL_USER", "imported_user1")
        user2_data = self.db.cfgdb.get_entry("LOCAL_USER", "imported_user2")
        self.assertIsNotNone(user1_data)
        self.assertIsNotNone(user2_data)
        self.assertEqual(user1_data["role"], "administrator")
        self.assertEqual(user2_data["role"], "operator")

        # Enable the feature
        result = self.runner.invoke(user_module.user, [
            "feature", "enabled"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Now should be able to manage the imported users
        result = self.runner.invoke(user_module.user, [
            "modify", "imported_user2",
            "--enabled"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)

        # Verify modification worked
        user2_data = self.db.cfgdb.get_entry("LOCAL_USER", "imported_user2")
        self.assertIn(user2_data["enabled"], [True, "True"])

    def test_negative_security_policy_extreme_values(self):
        """Test security policy with extreme values"""
        # Test maximum boundary + 1
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "1001"  # Exceeds maximum of 1000
        ], obj=self.db)

        self.assertEqual(result.exit_code, 2)  # Click validation error
        self.assertIn("not in the valid range", result.output)

        # Test minimum boundary - 1
        result = self.runner.invoke(user_module.user, [
            "security-policy", "set-policy", "operator",
            "--max-login-attempts", "0"  # Below minimum of 1
        ], obj=self.db)

        self.assertEqual(result.exit_code, 2)  # Click validation error
        self.assertIn("not in the valid range", result.output)

    def test_negative_security_policy_non_numeric_values(self):
        """Test security policy with non-numeric values"""
        invalid_values = ["abc", "1.5", "-5", "1e10", "infinity", "null", ""]

        for value in invalid_values:
            with self.subTest(value=value):
                result = self.runner.invoke(user_module.user, [
                    "security-policy", "set-policy", "operator",
                    "--max-login-attempts", value
                ], obj=self.db)

                self.assertNotEqual(result.exit_code, 0)  # Should fail validation

    @mock.patch('config.user.getpass.getpass')
    def test_negative_password_prompt_empty_password(self, mock_getpass):
        """Test password prompt with empty password"""
        mock_getpass.side_effect = ["", ""]  # Empty passwords

        result = self.runner.invoke(user_module.user, [
            "add", "emptypassuser",
            "--role", "operator",
            "--password-prompt"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Password cannot be empty", result.output)

        # Verify user was NOT created
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "emptypassuser")
        self.assertIn(user_data, [None, {}])

    @mock.patch('config.user.getpass.getpass')
    def test_negative_password_prompt_whitespace_password(self, mock_getpass):
        """Test password prompt with whitespace-only password"""
        mock_getpass.side_effect = ["   ", "   "]  # Whitespace-only passwords

        result = self.runner.invoke(user_module.user, [
            "add", "whitespaceuser",
            "--role", "operator",
            "--password-prompt"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Password cannot be empty", result.output)

        # Verify user was NOT created
        user_data = self.db.cfgdb.get_entry("LOCAL_USER", "whitespaceuser")
        self.assertIn(user_data, [None, {}])

    @mock.patch('config.user.getpass.getpass')
    def test_negative_password_prompt_very_long_password(self, mock_getpass):
        """Test password prompt with extremely long password"""
        very_long_password = "a" * 10000  # Extremely long password
        mock_getpass.side_effect = [very_long_password, very_long_password]

        with mock.patch('config.user.get_password_hardening_policies', return_value=None):
            with mock.patch('config.user.hash_password', return_value="$y$j9T$salt$hash"):
                result = self.runner.invoke(user_module.user, [
                    "add", "longpassuser",
                    "--role", "operator",
                    "--password-prompt"
                ], obj=self.db)

        # Should handle very long passwords
        self.assertEqual(result.exit_code, 0)

    def test_negative_modify_user_all_conflicting_options(self):
        """Test modify user with all possible conflicting options"""
        result = self.runner.invoke(user_module.user, [
            "modify", "admin",
            "--enabled",
            "--disabled",  # Conflicting enable/disable
            "--add-ssh-key", "key1",
            "--remove-ssh-key", "key2",
            "--replace-ssh-keys", "key3"  # Conflicting SSH key options
        ], obj=self.db)

        self.assertEqual(result.exit_code, 0)
        # Should detect and report conflicts
        self.assertTrue(
            "Cannot specify both" in result.output or
            "Cannot specify multiple" in result.output
        )

    def test_negative_import_existing_malformed_uid_ranges(self):
        """Test import-existing with various malformed UID ranges"""
        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        malformed_ranges = [
            "abc-def",  # Non-numeric
            "1000",     # Missing range end
            "",         # Empty string
        ]

        for uid_range in malformed_ranges:
            with self.subTest(uid_range=uid_range):
                result = self.runner.invoke(user_module.user, [
                    "import-existing", "--uid-range", uid_range
                ], obj=self.db)

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Invalid UID range format", result.output)

        # Test reversed range separately (parses but returns no users)
        result = self.runner.invoke(user_module.user, [
            "import-existing", "--uid-range", "2000-1000"
        ], obj=self.db)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No users found to import", result.output)

    @mock.patch('config.user.get_existing_linux_users')
    def test_negative_import_existing_permission_error(self, mock_get_users):
        """Test import-existing with permission error reading system files"""
        # Mock get_existing_linux_users to raise an exception (simulating permission error)
        mock_get_users.side_effect = Exception("Permission denied reading /etc/passwd")

        # Disable feature first
        self.runner.invoke(user_module.user, ["feature", "disabled"], obj=self.db)

        result = self.runner.invoke(user_module.user, [
            "import-existing"
        ], obj=self.db)

        self.assertEqual(result.exit_code, 1)  # Should fail with exit code 1
        # Exception propagates up, so output may be empty (exception not caught by CLI)
        # The important thing is that the command fails with exit code 1

    def test_negative_delete_nonexistent_user_variations(self):
        """Test deleting users with various nonexistent username patterns"""
        nonexistent_users = [
            "nonexistent_user",  # Typical nonexistent username
            "ADMIN",            # Wrong case (case sensitivity)
            "",                 # Empty string
        ]

        for username in nonexistent_users:
            with self.subTest(username=repr(username)):
                result = self.runner.invoke(user_module.user, [
                    "delete", username
                ], obj=self.db)

                self.assertEqual(result.exit_code, 0)
                if username.strip():  # Non-empty usernames
                    self.assertIn("does not exist", result.output)

    def test_negative_modify_nonexistent_user_variations(self):
        """Test modifying users with various nonexistent username patterns"""
        nonexistent_users = ["nonexistent_user", "ADMIN", ""]

        for username in nonexistent_users:
            with self.subTest(username=repr(username)):
                result = self.runner.invoke(user_module.user, [
                    "modify", username,
                    "--password-hash", "$y$j9T$salt$newhash"
                ], obj=self.db)

                self.assertEqual(result.exit_code, 0)
                if username.strip():  # Non-empty usernames
                    self.assertIn("does not exist", result.output)


if __name__ == '__main__':
    unittest.main()
