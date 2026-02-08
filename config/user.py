import click
import getpass
import re
import time
import grp
import subprocess
from .validated_config_db_connector import ValidatedConfigDBConnector
from jsonpatch import JsonPatchConflict
import utilities_common.cli as clicommon

# Constants
LOCAL_USER_TABLE = "LOCAL_USER"
LOCAL_ROLE_SECURITY_POLICY_TABLE = "LOCAL_ROLE_SECURITY_POLICY"
DEVICE_METADATA_TABLE = "DEVICE_METADATA"
DEVICE_METADATA_LOCALHOST_KEY = "localhost"
LOCAL_USER_MANAGEMENT_FIELD = "local_user_management"

# System users to exclude from import
SYSTEM_USERS = {'root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 'mail',
                'news', 'uucp', 'proxy', 'www-data', 'backup', 'list', 'irc', 'gnats',
                'nobody', '_apt', 'systemd-network', 'systemd-resolve', 'messagebus',
                'systemd-timesync', 'sshd', 'redis', 'ntp', 'frr', 'snmp'}

# Administrator groups
ADMIN_GROUPS = {'sudo', 'docker', 'redis', 'admin'}


def validate_username(username):
    """Validate username according to YANG model constraints"""
    if not re.match(r'^[a-z_][a-z0-9_-]*[$]?$', username):
        return False, ("Invalid username. Must start with a lowercase letter or underscore, "
                       "followed by lowercase letters, numbers, underscores, or hyphens.")

    if len(username) < 1 or len(username) > 32:
        return False, "Username must be between 1 and 32 characters."

    if username == 'root':
        return False, "Username cannot be 'root'."

    return True, ""


def validate_password_hash(password_hash):
    """Validate password hash"""
    if password_hash.startswith('!'):
        return False, "Password hash cannot start with '!'. Use the 'enabled' attribute to disable user accounts."

    return True, ""


def get_config_db(db):
    """Get a connected ValidatedConfigDBConnector instance"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()
    return config_db


def handle_password_input(username, password_hash, password_prompt, db, is_new_user=True):
    """Handle password input and validation for user operations

    Args:
        username: Username for the operation
        password_hash: Pre-hashed password (if provided)
        password_prompt: Whether to prompt for password
        db: Database connection
        is_new_user: Whether this is for a new user (affects prompt text)

    Returns:
        tuple: (password_hash, success) where success is True if operation should continue
    """
    # Handle password conflicts
    if password_prompt and password_hash:
        click.echo("Error: Cannot specify both --password-hash and --password-prompt")
        return None, False

    if password_prompt:
        prompt_text = (f"Enter password for user {username}: " if is_new_user
                       else f"Enter new password for user {username}: ")
        password = getpass.getpass(prompt_text)
        confirm_password = getpass.getpass("Confirm password: ")

        try:
            if password != confirm_password:
                click.echo("Error: Passwords do not match")
                return None, False

            # Check for empty password
            if not password or password.strip() == "":
                click.echo("Error: Password cannot be empty")
                time.sleep(3)  # Security delay to prevent rapid brute-force attempts
                return None, False

            # Validate password against hardening policies
            policies = get_password_hardening_policies(db)
            valid, error_msg = validate_password_against_policies(password, username, policies)
            if not valid:
                click.echo(f"Error: {error_msg}")
                time.sleep(3)  # Security delay to prevent rapid brute-force attempts
                return None, False

            password_hash = hash_password(password)
            if not password_hash:
                click.echo("Error: Failed to generate password hash")
                return None, False
        finally:
            # Always clear passwords from memory
            password = None
            confirm_password = None

    # Validate password hash if provided
    if password_hash and password_hash != '!':
        valid, error_msg = validate_password_hash(password_hash)
        if not valid:
            click.echo(f"Error: {error_msg}")
            time.sleep(3)  # Security delay to prevent rapid brute-force attempts
            return None, False

    return password_hash, True


def handle_ssh_key_modifications(user_data, add_ssh_key, remove_ssh_key, replace_ssh_keys):
    """Handle SSH key modifications for user data

    Args:
        user_data: Current user data dict
        add_ssh_key: SSH keys to add
        remove_ssh_key: SSH keys to remove
        replace_ssh_keys: SSH keys to replace all existing keys with

    Returns:
        list: Updated SSH keys list
    """
    if replace_ssh_keys:
        # Replace all SSH keys
        return list(replace_ssh_keys)
    else:
        # Get existing SSH keys
        existing_keys = set(user_data.get('ssh_keys', []))

        # Add new keys
        if add_ssh_key:
            existing_keys.update(add_ssh_key)

        # Remove specified keys
        if remove_ssh_key:
            existing_keys.difference_update(remove_ssh_key)

        # Return modified key list
        return list(existing_keys)


def update_user_in_db(config_db, username, user_data, operation="modified"):
    """Update user in CONFIG_DB with error handling

    Args:
        config_db: Database connection
        username: Username to update
        user_data: User data to set
        operation: Operation description for error message (e.g., "added", "modified")

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config_db.set_entry(LOCAL_USER_TABLE, username, user_data)
        return True
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to {operation.rstrip('d')} user. {e}")
        return False


def get_password_hardening_policies(db):
    """Get password hardening policies from CONFIG_DB"""
    config_db = get_config_db(db)

    policies = config_db.get_entry("PASSW_HARDENING", "POLICIES")
    if not policies:
        return None

    # Convert string boolean values to actual booleans
    bool_fields = ['reject_user_passw_match', 'lower_class', 'upper_class', 'digits_class', 'special_class']
    for field in bool_fields:
        if field in policies:
            if isinstance(policies[field], str):
                policies[field] = policies[field].lower() in ('true', '1', 'yes', 'on')

    # Convert numeric fields
    numeric_fields = ['len_min', 'history_cnt', 'expiration', 'expiration_warning']
    for field in numeric_fields:
        if field in policies:
            try:
                policies[field] = int(policies[field])
            except (ValueError, TypeError):
                pass

    return policies


def validate_password_against_policies(password, username, policies):
    """Validate password against password hardening policies"""
    if not policies or policies.get('state') != 'enabled':
        return True, ""

    errors = []

    # Check minimum length
    if 'len_min' in policies:
        min_len = policies['len_min']
        if len(password) < min_len:
            errors.append(f"Password must be at least {min_len} characters long")

    # Check character class requirements
    if policies.get('lower_class', False):
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

    if policies.get('upper_class', False):
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

    if policies.get('digits_class', False):
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

    if policies.get('special_class', False):
        # Define special characters (common set used by pam_pwquality)
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")

    # Check username matching
    if policies.get('reject_user_passw_match', False):
        if username.lower() in password.lower():
            errors.append("Password cannot contain the username")

    if errors:
        return False, "; ".join(errors)

    return True, ""


def hash_password(password):
    """Hash a password using mkpasswd (from whois package)"""
    try:
        result = subprocess.run(['mkpasswd', '--stdin'],
                                input=password, text=True,
                                capture_output=True, check=True)
        return result.stdout.strip()
    except FileNotFoundError:
        click.echo("Error: mkpasswd command not found. Please ensure the 'whois' package is installed.")
        return None
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: mkpasswd failed: {e}")
        return None


def check_admin_constraint(db, username, enabled):
    """Check that at least one administrator remains enabled"""
    config_db = get_config_db(db)

    users = config_db.get_table(LOCAL_USER_TABLE)
    admin_count = 0

    for user, data in users.items():
        if data.get('role') == 'administrator':
            user_enabled = data.get('enabled', True)
            if user == username:
                user_enabled = enabled
            if user_enabled:
                admin_count += 1

    return admin_count >= 1


def is_feature_enabled(db):
    """Check if local user management is enabled in DEVICE_METADATA"""
    config_db = get_config_db(db)

    device_metadata = config_db.get_table(DEVICE_METADATA_TABLE)
    localhost_data = device_metadata.get(DEVICE_METADATA_LOCALHOST_KEY, {})
    return localhost_data.get(LOCAL_USER_MANAGEMENT_FIELD) == 'enabled'


def get_existing_linux_users(uid_min=1000, uid_max=60000):
    """Get existing Linux users in specified UID range"""
    users = {}

    # Read /etc/passwd
    try:
        with open('/etc/passwd', 'r') as f:
            passwd_lines = f.readlines()
    except (IOError, OSError) as e:
        click.echo(f"Error reading /etc/passwd: {e}")
        return users

    # Read /etc/shadow once for all users
    shadow_passwords = {}
    try:
        with open('/etc/shadow', 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    shadow_passwords[parts[0]] = parts[1]
    except (IOError, OSError):
        # Shadow file may not be readable, continue with default password hash
        pass

    # Process each user
    for line in passwd_lines:
        parts = line.strip().split(':')
        if len(parts) < 7:
            continue

        username = parts[0]
        try:
            uid = int(parts[2])
            gid = int(parts[3])
        except ValueError:
            continue

        home = parts[5]
        shell = parts[6]

        # Skip system users and users outside UID range
        if username in SYSTEM_USERS or not (uid_min <= uid <= uid_max):
            continue

        # Get user groups (with error handling for individual users)
        user_groups = set()
        try:
            # Get all groups the user is a member of
            for group in grp.getgrall():
                if username in group.gr_mem:
                    user_groups.add(group.gr_name)

            # Add primary group
            primary_group = grp.getgrgid(gid)
            user_groups.add(primary_group.gr_name)
        except (KeyError, OSError):
            # If we can't get group info, default to operator role
            pass

        # Determine role
        role = 'administrator' if user_groups & ADMIN_GROUPS else 'operator'

        # Get password hash from shadow file
        password_hash = shadow_passwords.get(username, '!')

        # Get SSH keys
        ssh_keys = []
        auth_keys_file = f"{home}/.ssh/authorized_keys"
        try:
            with open(auth_keys_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ssh_keys.append(line)
        except (IOError, OSError):
            # SSH keys file may not exist or be readable
            pass

        users[username] = {
            'role': role,
            'password_hash': password_hash,
            'enabled': shell != '/usr/sbin/nologin',
            'ssh_keys': ssh_keys,
            'uid': uid,
            'gid': gid,
            'home': home,
            'shell': shell
        }

    return users


@click.group()
def user():
    """User management commands"""
    pass


@click.command()
@click.argument('state', type=click.Choice(['enabled', 'disabled']))
@clicommon.pass_db
def feature(db, state):
    """Enable or disable local user management"""
    config_db = get_config_db(db)

    # Get current DEVICE_METADATA localhost entry
    device_metadata = config_db.get_table(DEVICE_METADATA_TABLE)
    localhost_data = device_metadata.get(DEVICE_METADATA_LOCALHOST_KEY, {})

    # Update the local_user_management field
    localhost_data[LOCAL_USER_MANAGEMENT_FIELD] = state

    try:
        config_db.set_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_LOCALHOST_KEY, localhost_data)
        click.echo(f"Local user management {state}")
    except (ValueError, JsonPatchConflict):
        click.echo(f"Error: Failed to {state[:-1]} local user management")


@click.command()
@click.option('--dry-run', is_flag=True, help='Show what would be imported without making changes')
@click.option('--uid-range', help='UID range to import (e.g., 1000-60000)', default='1000-60000')
@clicommon.pass_db
def import_existing(db, dry_run, uid_range):
    """Import existing Linux users into CONFIG_DB LOCAL_USER table

    Note: This command should be run BEFORE enabling the local user management feature
    to ensure a clean transition from system users to managed users.
    """

    if is_feature_enabled(db):
        click.echo("Error: Local user management is already enabled")
        click.echo("Import existing users before enabling the feature for safer operation")
        return

    # Parse UID range
    try:
        uid_min, uid_max = map(int, uid_range.split('-'))
    except ValueError:
        click.echo("Error: Invalid UID range format. Use format: min-max (e.g., 1000-60000)")
        return

    # Get existing Linux users
    linux_users = get_existing_linux_users(uid_min, uid_max)

    # Get existing CONFIG_DB users
    config_db = get_config_db(db)
    config_users = set(config_db.get_table(LOCAL_USER_TABLE).keys())

    # Find users to import (not already in CONFIG_DB)
    users_to_import = {k: v for k, v in linux_users.items() if k not in config_users}

    if not users_to_import:
        click.echo("No users found to import")
        return

    if dry_run:
        click.echo("Users that would be imported:")
        for username, user_data in users_to_import.items():
            ssh_key_count = len(user_data['ssh_keys'])
            click.echo(f"  {username}: role={user_data['role']}, "
                       f"enabled={user_data['enabled']}, ssh_keys={ssh_key_count}")
        return

    # Import users
    imported_count = 0
    for username, user_data in users_to_import.items():
        try:
            import_data = {
                'role': user_data['role'],
                'password_hash': user_data['password_hash'],
                'enabled': user_data['enabled']
            }

            if user_data['ssh_keys']:
                import_data['ssh_keys'] = user_data['ssh_keys']

            config_db.set_entry(LOCAL_USER_TABLE, username, import_data)
            imported_count += 1
            click.echo(f"Imported user: {username}")

        except Exception as e:
            click.echo(f"Failed to import user {username}: {e}")


@click.command()
@click.argument('username')
@click.option('--role', type=click.Choice(['administrator', 'operator']), required=True,
              help='User role (administrator or operator)')
@click.option('--password-hash', help='Pre-hashed password')
@click.option('--password-prompt', is_flag=True, help='Prompt for password interactively')
@click.option('--ssh-key', multiple=True, help='SSH public key (can be specified multiple times)')
@click.option('--disabled', is_flag=True, help='Create user in disabled state')
@clicommon.pass_db
def add(db, username, role, password_hash, password_prompt, ssh_key, disabled):
    """Add a new user"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    # Validate username
    valid, error_msg = validate_username(username)
    if not valid:
        click.echo(f"Error: {error_msg}")
        return

    # Check if user already exists
    config_db = get_config_db(db)

    existing_user = config_db.get_entry(LOCAL_USER_TABLE, username)
    if existing_user:
        click.echo(f"Error: User '{username}' already exists in CONFIG_DB")
        click.echo(f"To modify an existing user, use: config user modify {username} [options]")
        return

    # Handle password input and validation
    password_hash, success = handle_password_input(username, password_hash,
                                                   password_prompt, db, is_new_user=True)
    if not success:
        return

    if not password_hash:
        click.echo("Error: Failed to generate password hash")
        return

    # Prepare user data
    user_data = {
        'role': role,
        'password_hash': password_hash,
        'enabled': not disabled
    }

    if ssh_key:
        user_data['ssh_keys'] = list(ssh_key)

    # Add user to CONFIG_DB
    update_user_in_db(config_db, username, user_data, "added")


@click.command()
@click.argument('username')
@clicommon.pass_db
def delete(db, username):
    """Delete a user"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    config_db = get_config_db(db)

    # Check if user exists
    user_data = config_db.get_entry(LOCAL_USER_TABLE, username)
    if not user_data:
        click.echo(f"Error: User '{username}' does not exist")
        return

    # Check admin constraint
    if user_data.get('role') == 'administrator':
        if not check_admin_constraint(db, username, False):
            click.echo("Error: Cannot delete the last administrator user")
            return

    # Delete user
    update_user_in_db(config_db, username, None, "deleted")


@click.command()
@click.argument('username')
@click.option('--password-hash', help='New pre-hashed password')
@click.option('--password-prompt', is_flag=True, help='Prompt for new password interactively')
@click.option('--add-ssh-key', multiple=True, help='Add SSH public key (can be specified multiple times)')
@click.option('--remove-ssh-key', multiple=True, help='Remove SSH public key (can be specified multiple times)')
@click.option('--replace-ssh-keys', multiple=True, help='Replace all SSH keys with specified keys')
@click.option('--enabled', 'enabled_flag', is_flag=True, help='Enable the user account')
@click.option('--disabled', 'disabled_flag', is_flag=True, help='Disable the user account')
@clicommon.pass_db
def modify(db, username, password_hash, password_prompt, add_ssh_key, remove_ssh_key,
           replace_ssh_keys, enabled_flag, disabled_flag):
    """Modify an existing user"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    config_db = get_config_db(db)

    # Check if user exists
    user_data = config_db.get_entry(LOCAL_USER_TABLE, username)
    if not user_data:
        click.echo(f"Error: User '{username}' does not exist")
        return

    # Validate that both --enabled and --disabled are not specified together
    if enabled_flag and disabled_flag:
        click.echo("Error: Cannot specify both --enabled and --disabled together")
        return

    # Validate SSH key options - only one type should be specified
    ssh_options_count = sum([bool(add_ssh_key), bool(remove_ssh_key), bool(replace_ssh_keys)])
    if ssh_options_count > 1:
        click.echo("Error: Cannot specify multiple SSH key options "
                   "(--add-ssh-key, --remove-ssh-key, --replace-ssh-keys) together")
        return

    # Handle password input and validation (only if password options are provided)
    if password_prompt or password_hash:
        password_hash, success = handle_password_input(username, password_hash,
                                                       password_prompt, db, is_new_user=False)
        if not success:
            return

    # Check admin constraint if modifying enabled status of an administrator
    if (enabled_flag or disabled_flag) and user_data.get('role') == 'administrator':
        # Calculate the final enabled state after modification
        final_enabled_state = True if enabled_flag else False if disabled_flag else user_data.get('enabled', True)

        if not check_admin_constraint(db, username, final_enabled_state):
            click.echo("Error: Cannot disable the last administrator user")
            return

    # Update user data - start with existing data and only modify specified fields
    updated_data = user_data.copy()

    # Update password if specified
    if password_hash:
        updated_data['password_hash'] = password_hash

    # Handle SSH key modifications (only if SSH key changes were requested)
    if add_ssh_key or remove_ssh_key or replace_ssh_keys:
        ssh_keys_result = handle_ssh_key_modifications(user_data, add_ssh_key,
                                                       remove_ssh_key, replace_ssh_keys)
        if ssh_keys_result:
            # Only set ssh_keys field if there are actual keys
            updated_data['ssh_keys'] = ssh_keys_result
        elif 'ssh_keys' in updated_data:
            # Remove ssh_keys field if result is empty (all keys were removed)
            del updated_data['ssh_keys']

    # Update enabled status if specified
    if enabled_flag:
        updated_data['enabled'] = True
    elif disabled_flag:
        updated_data['enabled'] = False

    # Update user in CONFIG_DB
    update_user_in_db(config_db, username, updated_data, "modified")


@click.group()
def security_policy():
    """User security policy commands"""
    pass


@click.command()
@click.argument('role', type=click.Choice(['administrator', 'operator']))
@click.option('--max-login-attempts', type=click.IntRange(1, 1000), required=True,
              help='Maximum number of failed login attempts before account lockout')
@clicommon.pass_db
def set_policy(db, role, max_login_attempts):
    """Set security policy for a role"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    config_db = get_config_db(db)

    policy_data = {
        'max_login_attempts': max_login_attempts
    }

    try:
        config_db.set_entry(LOCAL_ROLE_SECURITY_POLICY_TABLE, role, policy_data)
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to set security policy. {e}")


@click.command()
@click.argument('role', type=click.Choice(['administrator', 'operator']))
@clicommon.pass_db
def clear_policy(db, role):
    """Clear security policy for a role"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    config_db = get_config_db(db)

    # Check if policy exists
    existing_policy = config_db.get_entry(LOCAL_ROLE_SECURITY_POLICY_TABLE, role)
    if not existing_policy or existing_policy == {}:
        return

    try:
        config_db.set_entry(LOCAL_ROLE_SECURITY_POLICY_TABLE, role, None)
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to clear security policy. {e}")


# Add security policy commands
security_policy.add_command(set_policy)
security_policy.add_command(clear_policy)

# Add commands to the user group
user.add_command(feature)
user.add_command(import_existing, name='import-existing')
user.add_command(add)
user.add_command(delete)
user.add_command(modify)
user.add_command(security_policy, name='security-policy')
