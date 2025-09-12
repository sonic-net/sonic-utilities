import click
import getpass
import crypt
import re
import pwd
import grp
from swsscommon.swsscommon import ConfigDBConnector
from .validated_config_db_connector import ValidatedConfigDBConnector
from jsonpatch import JsonPatchConflict
from jsonpointer import JsonPointerException
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
        return False, "Invalid username. Must start with a lowercase letter or underscore, followed by lowercase letters, numbers, underscores, or hyphens."

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


def get_password_hardening_policies(db):
    """Get password hardening policies from CONFIG_DB"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

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
    """Hash a password using the system's preferred method"""
    import subprocess

    # Try using mkpasswd (most reliable - uses system default)
    try:
        result = subprocess.run(['mkpasswd', '--stdin'],
                              input=password, text=True,
                              capture_output=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback: Try using openssl with SHA-512
    try:
        result = subprocess.run(['openssl', 'passwd', '-6', password],
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Final fallback to Python's crypt with SHA-512
    return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))


def check_admin_constraint(db, username, enabled):
    """Check that at least one administrator remains enabled"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

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
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

    device_metadata = config_db.get_table(DEVICE_METADATA_TABLE)
    localhost_data = device_metadata.get(DEVICE_METADATA_LOCALHOST_KEY, {})
    return localhost_data.get(LOCAL_USER_MANAGEMENT_FIELD) == 'enabled'


def get_existing_linux_users(uid_min=1000, uid_max=60000):
    """Get existing Linux users in specified UID range"""
    users = {}

    try:
        with open('/etc/passwd', 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 7:
                    username = parts[0]
                    uid = int(parts[2])
                    gid = int(parts[3])
                    home = parts[5]
                    shell = parts[6]

                    # Skip system users and users outside UID range
                    if (username not in SYSTEM_USERS and
                        uid_min <= uid <= uid_max):

                        # Determine role based on group membership
                        user_groups = set()
                        try:
                            for group in grp.getgrall():
                                if username in group.gr_mem:
                                    user_groups.add(group.gr_name)

                            # Check primary group
                            primary_group = grp.getgrgid(gid)
                            user_groups.add(primary_group.gr_name)
                        except:
                            pass

                        # Determine role
                        role = 'administrator' if user_groups & ADMIN_GROUPS else 'operator'

                        # Get password hash
                        password_hash = '!'
                        try:
                            with open('/etc/shadow', 'r') as shadow_f:
                                for shadow_line in shadow_f:
                                    shadow_parts = shadow_line.strip().split(':')
                                    if len(shadow_parts) >= 2 and shadow_parts[0] == username:
                                        password_hash = shadow_parts[1]
                                        break
                        except:
                            pass

                        # Get SSH keys
                        ssh_keys = []
                        try:
                            auth_keys_file = f"{home}/.ssh/authorized_keys"
                            with open(auth_keys_file, 'r') as keys_f:
                                for key_line in keys_f:
                                    key_line = key_line.strip()
                                    if key_line and not key_line.startswith('#'):
                                        ssh_keys.append(key_line)
                        except:
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

    except Exception as e:
        click.echo(f"Error reading system users: {e}")

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
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

    try:
        # Get current DEVICE_METADATA localhost entry
        device_metadata = config_db.get_table(DEVICE_METADATA_TABLE)
        localhost_data = device_metadata.get(DEVICE_METADATA_LOCALHOST_KEY, {})

        # Update the local_user_management field
        localhost_data[LOCAL_USER_MANAGEMENT_FIELD] = state
        config_db.set_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_LOCALHOST_KEY, localhost_data)

        click.echo(f"Local user management {state}")
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to {state} local user management. {e}")


@click.command()
@click.option('--dry-run', is_flag=True, help='Show what would be imported without making changes')
@click.option('--uid-range', help='UID range to import (e.g., 1000-60000)', default='1000-60000')
@clicommon.pass_db
def import_existing(db, dry_run, uid_range):
    """Import existing Linux users into CONFIG_DB LOCAL_USER table"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
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
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()
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
                import_data['ssh_keys'] = ','.join(user_data['ssh_keys'])

            config_db.set_entry(LOCAL_USER_TABLE, username, import_data)
            imported_count += 1
            click.echo(f"Imported user: {username}")

        except Exception as e:
            click.echo(f"Failed to import user {username}: {e}")

    click.echo(f"Successfully imported {imported_count} users")


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
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

    existing_user = config_db.get_entry(LOCAL_USER_TABLE, username)
    if existing_user:
        click.echo(f"Error: User '{username}' already exists")
        return
    
    # Handle password
    if password_prompt and password_hash:
        click.echo("Error: Cannot specify both --password-hash and --password-prompt")
        return
    
    if password_prompt:
        password = getpass.getpass(f"Enter password for user {username}: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if password != confirm_password:
            click.echo("Error: Passwords do not match")
            return

        # Validate password against hardening policies
        policies = get_password_hardening_policies(db)
        valid, error_msg = validate_password_against_policies(password, username, policies)
        if not valid:
            click.echo(f"Error: {error_msg}")
            return

        password_hash = hash_password(password)
        # Clear password from memory
        password = None
        confirm_password = None
    
    if not password_hash:
        password_hash = '!'  # Disabled password login
    
    # Validate password hash
    if password_hash != '!':
        valid, error_msg = validate_password_hash(password_hash)
        if not valid:
            click.echo(f"Error: {error_msg}")
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
    try:
        config_db.set_entry(LOCAL_USER_TABLE, username, user_data)
        click.echo(f"User '{username}' added successfully")
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to add user. {e}")


@click.command()
@click.argument('username')
@clicommon.pass_db
def delete(db, username):
    """Delete a user"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

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
    try:
        config_db.set_entry(LOCAL_USER_TABLE, username, None)
        click.echo(f"User '{username}' deleted successfully")
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to delete user. {e}")


@click.command()
@click.argument('username')
@click.option('--password-hash', help='New pre-hashed password')
@click.option('--password-prompt', is_flag=True, help='Prompt for new password interactively')
@click.option('--ssh-key', multiple=True, help='SSH public key (replaces existing keys)')
@click.option('--enabled', 'enable_flag', flag_value=True, help='Enable the user account')
@click.option('--disabled', 'enable_flag', flag_value=False, help='Disable the user account')
@clicommon.pass_db
def modify(db, username, password_hash, password_prompt, ssh_key, enable_flag):
    """Modify an existing user"""

    if not is_feature_enabled(db):
        click.echo("Error: Local user management is not enabled")
        return

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

    # Check if user exists
    user_data = config_db.get_entry(LOCAL_USER_TABLE, username)
    if not user_data:
        click.echo(f"Error: User '{username}' does not exist")
        return
    
    # Handle password
    if password_prompt and password_hash:
        click.echo("Error: Cannot specify both --password-hash and --password-prompt")
        return
    
    if password_prompt:
        password = getpass.getpass(f"Enter new password for user {username}: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if password != confirm_password:
            click.echo("Error: Passwords do not match")
            return

        # Validate password against hardening policies
        policies = get_password_hardening_policies(db)
        valid, error_msg = validate_password_against_policies(password, username, policies)
        if not valid:
            click.echo(f"Error: {error_msg}")
            return

        password_hash = hash_password(password)
        # Clear password from memory
        password = None
        confirm_password = None
    
    # Validate password hash if provided
    if password_hash and password_hash != '!':
        valid, error_msg = validate_password_hash(password_hash)
        if not valid:
            click.echo(f"Error: {error_msg}")
            return
    
    # Check admin constraint if disabling
    if enable_flag is False and user_data.get('role') == 'administrator':
        if not check_admin_constraint(db, username, False):
            click.echo("Error: Cannot disable the last administrator user")
            return
    
    # Update user data
    updated_data = user_data.copy()
    
    if password_hash:
        updated_data['password_hash'] = password_hash
    
    if ssh_key:
        updated_data['ssh_keys'] = list(ssh_key)
    
    if enable_flag is not None:
        updated_data['enabled'] = enable_flag
    
    # Update user in CONFIG_DB
    try:
        config_db.set_entry(LOCAL_USER_TABLE, username, updated_data)
        click.echo(f"User '{username}' modified successfully")
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to modify user. {e}")


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

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

    policy_data = {
        'max_login_attempts': max_login_attempts
    }

    try:
        config_db.set_entry(LOCAL_ROLE_SECURITY_POLICY_TABLE, role, policy_data)
        click.echo(f"Security policy for role '{role}' set successfully")
    except (ValueError, JsonPatchConflict) as e:
        click.echo(f"Error: Failed to set security policy. {e}")


@click.command()
@click.argument('role', type=click.Choice(['administrator', 'operator']), required=False)
@clicommon.pass_db
def show_policy(db, role):
    """Show security policies"""

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.connect()

    if role:
        # Show specific role policy
        policy_data = config_db.get_entry(LOCAL_ROLE_SECURITY_POLICY_TABLE, role)
        if policy_data:
            click.echo(f"Security policy for role '{role}':")
            for key, value in policy_data.items():
                click.echo(f"  {key}: {value}")
        else:
            click.echo(f"No security policy configured for role '{role}'")
    else:
        # Show all policies
        policies = config_db.get_table(LOCAL_ROLE_SECURITY_POLICY_TABLE)
        if policies:
            click.echo("Security policies:")
            for role, policy_data in policies.items():
                click.echo(f"  Role: {role}")
                for key, value in policy_data.items():
                    click.echo(f"    {key}: {value}")
        else:
            click.echo("No security policies configured")


# Add security policy commands
security_policy.add_command(set_policy)
security_policy.add_command(show_policy)

# Add commands to the user group
user.add_command(feature)
user.add_command(import_existing, name='import-existing')
user.add_command(add)
user.add_command(delete)
user.add_command(modify)
user.add_command(security_policy)
