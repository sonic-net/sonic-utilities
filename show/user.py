import click
import tabulate
import os
from swsscommon.swsscommon import ConfigDBConnector
import utilities_common.cli as clicommon

# Constants
LOCAL_USER_TABLE = "LOCAL_USER"
LOCAL_ROLE_SECURITY_POLICY_TABLE = "LOCAL_ROLE_SECURITY_POLICY"


@click.group()
def user():
    """Show user information"""
    pass


@click.command()
@clicommon.pass_db
def show_users(db):
    """Show all configured users"""
    
    config_db = ConfigDBConnector()
    config_db.connect()
    
    users = config_db.get_table(LOCAL_USER_TABLE)
    
    if not users:
        click.echo("No users configured")
        return

    # Show password hashes only if running with sudo
    show_passwords = os.geteuid() == 0

    if show_passwords:
        headers = ['Username', 'Role', 'Enabled', 'Password Hash', 'SSH Keys']
    else:
        headers = ['Username', 'Role', 'Enabled', 'SSH Keys']

    table_data = []
    
    for username, user_data in users.items():
        role = user_data.get('role', 'N/A')
        enabled = user_data.get('enabled', True)
        ssh_keys = user_data.get('ssh_keys', '')

        # Handle SSH keys (stored as comma-separated string)
        if ssh_keys:
            ssh_key_count = len(ssh_keys.split(','))
        else:
            ssh_key_count = 0

        ssh_key_display = f"{ssh_key_count} key(s)" if ssh_key_count > 0 else "None"

        if show_passwords:
            password_hash = user_data.get('password_hash', '!')
            # Truncate long hashes for display
            display_hash = password_hash[:20] + "..." if len(password_hash) > 20 else password_hash

            table_data.append([
                username,
                role,
                'Yes' if enabled else 'No',
                display_hash,
                ssh_key_display
            ])
        else:
            table_data.append([
                username,
                role,
                'Yes' if enabled else 'No',
                ssh_key_display
            ])
    
    click.echo(tabulate.tabulate(table_data, headers=headers, tablefmt='grid'))


@click.command()
@click.argument('username', required=False)
@clicommon.pass_db
def show_user_details(db, username):
    """Show detailed information for a specific user or all users"""
    
    config_db = ConfigDBConnector()
    config_db.connect()
    
    users = config_db.get_table(LOCAL_USER_TABLE)
    
    if not users:
        click.echo("No users configured")
        return
    
    if username:
        # Show specific user
        if username not in users:
            click.echo(f"User '{username}' not found")
            return
        
        user_data = users[username]
        click.echo(f"User: {username}")
        click.echo(f"  Role: {user_data.get('role', 'N/A')}")
        click.echo(f"  Enabled: {'Yes' if user_data.get('enabled', True) else 'No'}")

        # Show password hash only if running with sudo
        if os.geteuid() == 0:
            password_hash = user_data.get('password_hash', '!')
            click.echo(f"  Password Hash: {password_hash}")

        ssh_keys = user_data.get('ssh_keys', '')
        if ssh_keys:
            # Handle comma-separated SSH keys
            key_list = ssh_keys.split(',')
            click.echo(f"  SSH Keys ({len(key_list)}):")
            for i, key in enumerate(key_list, 1):
                # Show first 50 characters of the key for readability
                key_preview = key.strip()[:50] + "..." if len(key.strip()) > 50 else key.strip()
                click.echo(f"    {i}. {key_preview}")
        else:
            click.echo("  SSH Keys: None")
    else:
        # Show all users with details
        for username, user_data in users.items():
            click.echo(f"User: {username}")
            click.echo(f"  Role: {user_data.get('role', 'N/A')}")
            click.echo(f"  Enabled: {'Yes' if user_data.get('enabled', True) else 'No'}")

            # Show password hash only if running with sudo
            if os.geteuid() == 0:
                password_hash = user_data.get('password_hash', '!')
                click.echo(f"  Password Hash: {password_hash}")

            ssh_keys = user_data.get('ssh_keys', '')
            if ssh_keys:
                # Handle comma-separated SSH keys
                key_list = ssh_keys.split(',')
                click.echo(f"  SSH Keys ({len(key_list)}):")
                for i, key in enumerate(key_list, 1):
                    key_preview = key.strip()[:50] + "..." if len(key.strip()) > 50 else key.strip()
                    click.echo(f"    {i}. {key_preview}")
            else:
                click.echo("  SSH Keys: None")
            click.echo()


@click.command()
@click.argument('role', type=click.Choice(['administrator', 'operator']), required=False)
@clicommon.pass_db
def show_security_policy(db, role):
    """Show security policies for roles"""
    
    config_db = ConfigDBConnector()
    config_db.connect()
    
    policies = config_db.get_table(LOCAL_ROLE_SECURITY_POLICY_TABLE)
    
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
        if not policies:
            click.echo("No security policies configured")
            return
        
        headers = ['Role', 'Max Login Attempts']
        table_data = []
        
        for role_name, policy_data in policies.items():
            max_attempts = policy_data.get('max_login_attempts', 'N/A')
            table_data.append([role_name, max_attempts])
        
        click.echo(tabulate.tabulate(table_data, headers=headers, tablefmt='grid'))


# Add commands to the user group
user.add_command(show_users, name='list')
user.add_command(show_user_details, name='details')
user.add_command(show_security_policy, name='security-policy')
