import click
import os
import getpass
from swsscommon.swsscommon import ConfigDBConnector
import utilities_common.cli as clicommon

# Constants
LOCAL_USER_TABLE = "LOCAL_USER"
LOCAL_ROLE_SECURITY_POLICY_TABLE = "LOCAL_ROLE_SECURITY_POLICY"


def get_user_database(config_db=None):
    """Get connected ConfigDBConnector and user table data"""
    if config_db is None:
        config_db = ConfigDBConnector()
        config_db.connect()
    users = config_db.get_table(LOCAL_USER_TABLE)
    return users


def get_security_policies(config_db=None):
    """Get security policies from CONFIG_DB"""
    if config_db is None:
        config_db = ConfigDBConnector()
        config_db.connect()
    return config_db.get_table(LOCAL_ROLE_SECURITY_POLICY_TABLE)


def can_view_passwords():
    """Check if current user can view password hashes"""
    # Root user can always view passwords
    if os.geteuid() == 0:
        return True

    # Check if current user has administrator role in SONiC user management
    current_username = getpass.getuser()
    users = get_user_database()

    user_data = users.get(current_username)
    return user_data and user_data.get('role') == 'administrator'


def format_ssh_keys_count(ssh_keys):
    """Format SSH keys for count display"""
    if not ssh_keys:
        return "None"

    # Handle both array format (real system) and string format (test system)
    if isinstance(ssh_keys, list):
        ssh_key_count = len(ssh_keys)
    elif isinstance(ssh_keys, str):
        # Check if it's a string representation of an array (from mock Redis)
        if ssh_keys.startswith('[') and ssh_keys.endswith(']'):
            if ssh_keys == '[]':
                ssh_key_count = 0
            else:
                # Count items in array string representation
                inner = ssh_keys[1:-1].strip()
                if not inner:
                    ssh_key_count = 0
                else:
                    # Count items by splitting on comma (handles quoted strings)
                    ssh_key_count = len([item.strip() for item in inner.split(',') if item.strip()])
        else:
            # Split by comma and filter out empty strings (regular string format)
            ssh_key_count = len([key.strip() for key in ssh_keys.split(',') if key.strip()])
    else:
        ssh_key_count = 0

    return f"({ssh_key_count})" if ssh_key_count > 0 else "None"


def format_ssh_keys_detailed(ssh_keys):
    """Format SSH keys for detailed display with previews"""
    if not ssh_keys:
        return "  SSH Keys: None"

    # Handle both array format (real system) and string format (test system)
    if isinstance(ssh_keys, list):
        key_list = ssh_keys
    elif isinstance(ssh_keys, str):
        # Check if it's a string representation of an array (from mock Redis)
        if ssh_keys.startswith('[') and ssh_keys.endswith(']'):
            if ssh_keys == '[]':
                key_list = []
            else:
                # Parse array string representation (simplified approach)
                inner = ssh_keys[1:-1].strip()
                if not inner:
                    key_list = []
                else:
                    # Split on comma and clean up quotes
                    items = [item.strip() for item in inner.split(',') if item.strip()]
                    key_list = []
                    for item in items:
                        # Remove surrounding quotes if present
                        item = item.strip()
                        if ((item.startswith("'") and item.endswith("'")) or
                                (item.startswith('"') and item.endswith('"'))):
                            item = item[1:-1]
                        key_list.append(item)
        else:
            # Split by comma and filter out empty strings (regular string format)
            key_list = [key.strip() for key in ssh_keys.split(',') if key.strip()]
    else:
        return "  SSH Keys: None"

    if not key_list:
        return "  SSH Keys: None"

    result = [f"  SSH Keys ({len(key_list)}):"]

    for i, key in enumerate(key_list, 1):
        result.append(f"    {i}. {key.strip()}")

    return "\n".join(result)


def display_user_details(username, user_data):
    """Display detailed information for a single user"""
    click.echo(f"User: {username}")
    click.echo(f"  Role: {user_data.get('role', 'N/A')}")
    click.echo(f"  Enabled: {'Yes' if user_data.get('enabled', True) else 'No'}")

    # Show password hash only if user has administrator privileges
    if can_view_passwords():
        password_hash = user_data.get('password_hash', '!')
        click.echo(f"  Password Hash: {password_hash}")

    # Display SSH keys
    ssh_keys = user_data.get('ssh_keys', [])
    click.echo(format_ssh_keys_detailed(ssh_keys))


@click.group()
def user():
    """Show user information"""
    pass


@click.command(name='list')
@clicommon.pass_db
def show_users(db):
    """Show all configured users"""

    users = get_user_database(db.cfgdb)

    if not users:
        click.echo("No users configured")
        return

    # Show password hashes only if user has administrator privileges
    show_passwords = can_view_passwords()

    click.echo("Users:")
    for username, user_data in users.items():
        role = user_data.get('role', 'N/A')
        enabled = user_data.get('enabled', True)
        ssh_keys = user_data.get('ssh_keys', [])

        click.echo(f"  Username: {username}")
        click.echo(f"    Role: {role}")
        click.echo(f"    Enabled: {'Yes' if enabled else 'No'}")

        if show_passwords:
            password_hash = user_data.get('password_hash', '!')
            click.echo(f"    Password Hash: {password_hash}")

        # Display SSH key count for summary view
        ssh_key_count = format_ssh_keys_count(ssh_keys)
        if ssh_key_count == "None":
            click.echo(f"    SSH Keys: {ssh_key_count}")
        else:
            click.echo(f"    SSH Keys {ssh_key_count}")
        click.echo()  # Empty line between users


@click.command(name='details')
@click.argument('username', required=False)
@clicommon.pass_db
def show_user_details(db, username):
    """Show detailed information for a specific user or all users"""

    users = get_user_database(db.cfgdb)

    if not users:
        click.echo("No users configured")
        return

    if username:
        # Show specific user
        if username not in users:
            click.echo(f"User '{username}' not found")
            return

        user_data = users[username]
        display_user_details(username, user_data)
    else:
        # Show all users with details
        for username, user_data in users.items():
            display_user_details(username, user_data)
            click.echo()


@click.command(name='security-policy')
@click.argument('role', type=click.Choice(['administrator', 'operator']), required=False)
@clicommon.pass_db
def show_security_policy(db, role):
    """Show security policies for roles"""

    policies = get_security_policies(db.cfgdb)
    if not policies:
        click.echo("No security policies configured")
        return

    if role:
        # Show specific role policy
        if role not in policies:
            click.echo(f"No security policy configured for role '{role}'")
            return

        policy_data = policies[role]
        click.echo(f"Security policy for role '{role}':")
        for key, value in policy_data.items():
            click.echo(f"  {key}: {value}")
    else:
        # Show all policies
        click.echo("Security policies:")
        for role_name, policy_data in policies.items():
            click.echo(f"  Role: {role_name}")
            for key, value in policy_data.items():
                click.echo(f"    {key}: {value}")
            click.echo()


# Add commands to the user group
user.add_command(show_users)
user.add_command(show_user_details)
user.add_command(show_security_policy)
