# User Management CLI Tests

This document describes the comprehensive test suite for the SONiC User Management CLI commands.

## Test Files

### 1. `config_test_user.py`
Tests for `config user` commands including:

#### Feature Management Tests
- `test_is_feature_enabled_true()` - Feature enabled check
- `test_is_feature_enabled_false()` - Feature disabled check  
- `test_is_feature_enabled_missing()` - Feature not configured
- `test_feature_enable_success()` - Enable feature successfully
- `test_feature_disable_success()` - Disable feature successfully
- `test_feature_enable_db_error()` - Handle database errors

#### Import Existing Users Tests
- `test_import_existing_feature_disabled()` - Import when feature disabled
- `test_import_existing_dry_run()` - Dry run functionality
- `test_import_existing_success()` - Successful import
- `test_import_existing_no_users()` - No users to import
- `test_import_existing_skip_existing()` - Skip users already in CONFIG_DB

#### User Management Tests
- `test_add_user_success()` - Add user successfully
- `test_add_user_feature_disabled()` - Add user when feature disabled
- `test_add_user_with_ssh_keys()` - Add user with SSH keys
- `test_add_user_with_password_prompt()` - Interactive password entry
- `test_add_user_password_mismatch()` - Password confirmation mismatch
- `test_delete_user_success()` - Delete user successfully
- `test_modify_user_success()` - Modify user successfully
- `test_set_security_policy()` - Set security policy

#### Validation Tests
- `test_validate_username()` - Username validation
- `test_validate_password_hash_invalid()` - Invalid password hash
- `test_validate_password_hash_valid()` - Valid password hash
- `test_check_admin_constraint()` - Admin constraint checking
- `test_get_existing_linux_users()` - Linux user discovery

### 2. `show_test_user.py`
Tests for `show user` commands including:

#### User Display Tests
- `test_show_user_all()` - Show all users
- `test_show_user_specific()` - Show specific user
- `test_show_user_not_found()` - Handle non-existent user
- `test_show_user_with_sudo()` - Show password hashes with sudo
- `test_show_user_empty_table()` - Handle empty user table
- `test_show_user_with_ssh_keys()` - Display SSH key count
- `test_show_user_disabled()` - Show disabled user

#### Security Policy Display Tests
- `test_show_user_security_policy_all()` - Show all policies
- `test_show_user_security_policy_specific()` - Show specific policy
- `test_show_user_security_policy_not_found()` - Handle missing policy

## Running Tests

### Run All Tests
```bash
cd src/sonic-utilities/tests
python3 run_user_tests.py
```

### Run Config Tests Only
```bash
python3 run_user_tests.py --config-only
```

### Run Show Tests Only
```bash
python3 run_user_tests.py --show-only
```

### Run Individual Test Files
```bash
python3 -m unittest config_test_user
python3 -m unittest show_test_user
```

### Run Specific Test Methods
```bash
python3 -m unittest config_test_user.TestUserCLI.test_add_user_success
python3 -m unittest show_test_user.TestShowUserCLI.test_show_user_all
```

## Test Coverage

### Config Commands Tested
- `config user feature enabled/disabled`
- `config user import-existing [--dry-run] [--uid-range]`
- `config user add <username> --role <role> [options]`
- `config user delete <username>`
- `config user modify <username> [options]`
- `config user security-policy set <role> --max-login-attempts <num>`
- `config user security-policy show [role]`

### Show Commands Tested
- `show user [username]`
- `show user security-policy [role]`

### Key Features Tested
1. **Feature Flag Management** - Enable/disable LOCAL_USER_MANAGEMENT
2. **User Import** - Import existing Linux users with role detection
3. **User CRUD Operations** - Create, read, update, delete users
4. **Security Policies** - Role-based security configuration
5. **SSH Key Management** - Multiple SSH keys per user
6. **Password Management** - Hash validation and interactive prompts
7. **Admin Constraints** - Ensure at least one admin remains enabled
8. **Privilege Separation** - Password hashes only shown with sudo
9. **Error Handling** - Database errors, validation failures
10. **Table Name Updates** - Uses LOCAL_USER and LOCAL_ROLE_SECURITY_POLICY

### Mock Strategy
Tests use comprehensive mocking of:
- Database connections (`ConfigDBConnector`, `ValidatedConfigDBConnector`)
- System calls (`getpass`, `os.geteuid`)
- File operations (passwd, shadow, authorized_keys)
- Group membership (`grp.getgrall`, `grp.getgrgid`)

### Test Data
Tests include realistic mock data for:
- User configurations with various roles and states
- Security policies with different login attempt limits
- SSH keys in proper format
- Password hashes in crypt format
- Linux system user data

## Integration with CI/CD

These tests should be integrated into the SONiC build pipeline to ensure:
1. User management functionality works correctly
2. New table names are properly used
3. Feature flag behavior is correct
4. CLI commands produce expected output
5. Error conditions are handled gracefully

## Future Enhancements

Potential additional tests:
1. **Performance Tests** - Large user datasets
2. **Concurrency Tests** - Multiple simultaneous operations
3. **Integration Tests** - With actual CONFIG_DB
4. **End-to-End Tests** - Full workflow testing
5. **Security Tests** - Permission validation
6. **Migration Tests** - Upgrade scenarios
