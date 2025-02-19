import sys
import click
import os
from utilities_common.cli import AbbreviationGroup, pass_db
from ipaddress import ip_address, AddressValueError
import re
#
# 'kdump' group ('sudo config kdump ...')
#

@click.group(cls=AbbreviationGroup, name="kdump")
def kdump():
    """Configure the KDUMP mechanism"""
    pass

def check_kdump_table_existence(kdump_table):
    """Checks whether the 'KDUMP' table is configured in Config DB.

    Args:
      kdump_table: A dictionary represents the key-value pair in sub-table
      of 'KDUMP'.

    Returns:
      None.
    """
    if not kdump_table:
        click.echo("Unable to retrieve 'KDUMP' table from Config DB.")
        sys.exit(1)

    if "config" not in kdump_table:
        click.echo("Unable to retrieve key 'config' from KDUMP table.")
        sys.exit(2)


def echo_reboot_warning():
    """Prints the warning message about reboot requirements."""
    click.echo("KDUMP configuration changes may require a reboot to take effect.")
    click.echo("Save SONiC configuration using 'config save' before issuing the reboot command.")
#
# 'disable' command ('sudo config kdump disable')
#


@kdump.command(name="disable", help="Disable the KDUMP mechanism")
@pass_db
def kdump_disable(db):
    """Disable the KDUMP mechanism"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    db.cfgdb.mod_entry("KDUMP", "config", {"enabled": "false"})
    echo_reboot_warning()

#
# 'enable' command ('sudo config kdump enable')
#


@kdump.command(name="enable", help="Enable the KDUMP mechanism")
@pass_db
def kdump_enable(db):
    """Enable the KDUMP mechanism"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    db.cfgdb.mod_entry("KDUMP", "config", {"enabled": "true"})
    echo_reboot_warning()

#
# 'memory' command ('sudo config kdump memory ...')
#


@kdump.command(name="memory", help="Configure the memory for KDUMP mechanism")
@click.argument('kdump_memory', metavar='<kdump_memory>', required=True)
@pass_db
def kdump_memory(db, kdump_memory):
    """Reserve memory for kdump capture kernel"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    db.cfgdb.mod_entry("KDUMP", "config", {"memory": kdump_memory})
    echo_reboot_warning()

#
# 'num_dumps' command ('sudo config kdump num_dumps ...')
#


@kdump.command(name="num_dumps", help="Configure the maximum dump files of KDUMP mechanism")
@click.argument('kdump_num_dumps', metavar='<kdump_num_dumps>', required=True, type=int)
@pass_db
def kdump_num_dumps(db, kdump_num_dumps):
    """Set maximum number of dump files for kdump"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    db.cfgdb.mod_entry("KDUMP", "config", {"num_dumps": kdump_num_dumps})
    echo_reboot_warning()


@kdump.command(name="remote", help="Configure the remote enable/disable for KDUMP mechanism")
@click.argument('action', metavar='<enable/disable>', required=True, type=click.STRING)  # Corrected this line
@pass_db
def remote(db, action):
    """Enable or disable remote kdump feature"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    # Get the current status of the remote feature as string
    current_status = kdump_table["config"].get("remote", "false").lower()

    if action.lower() == 'enable':
        if current_status == "true":
            click.echo("Remote kdump feature is already enabled.")
        else:
            db.cfgdb.mod_entry("KDUMP", "config", {"remote": "true"})
            click.echo("Remote kdump feature enabled.")
            echo_reboot_warning()
    elif action.lower() == 'disable':
        if current_status == "false":
            click.echo("Remote kdump feature is already disabled.")
        else:
            db.cfgdb.mod_entry("KDUMP", "config", {"remote": "false"})
            click.echo("Remote kdump feature disabled.")
            echo_reboot_warning()
    else:
        click.echo("Invalid action. Use 'enable' or 'disable'.")


@kdump.group(name="add", help="Add configuration items to KDUMP")
def add():
    """Group of commands to add configuration items to KDUMP"""
    pass


@add.command(name="ssh_string", help="Add an SSH string to the KDUMP configuration")
@click.argument('ssh_string', metavar='<ssh_key>', required=True)
@pass_db
def add_ssh_key(db, ssh_string):
    """Add an SSH string to KDUMP configuration"""

    def is_valid_ssh_key(ssh_string):
        """Validate the SSH key format"""
        # Check if it contains username and hostname/IP (format: username@host)
        if "@" not in ssh_string:
            return "Invalid format. SSH key must be in 'username@host' format."

        username, host = ssh_string.split("@", 1)

        # Validate username
        if not username or not username.isalnum():
            return "Invalid username. Ensure it contains only alphanumeric characters."

        # Validate host (IP or hostname)
        try:
            # Check if it's a valid IP address
            ip_address(host)
        except AddressValueError:
            # If not an IP, validate hostname
            hostname_regex = r'^[a-zA-Z0-9.-]+$'
            if not re.match(hostname_regex, host) or host.startswith('-') or host.endswith('-'):
                return "Invalid host. Must be a valid IP or hostname."

        return None  # Validation successful

    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)
    current_status = kdump_table["config"].get("remote", "false").lower()

    if current_status == 'false':
        click.echo("Remote feature is not enabled. Please enable the remote feature first.")
        return

    # Validate SSH key
    validation_error = is_valid_ssh_key(ssh_string)
    if validation_error:
        click.echo(f"Error: {validation_error}")
        return

    # Add or update the 'ssh_key' entry in the KDUMP table
    db.cfgdb.mod_entry("KDUMP", "config", {"ssh_string": ssh_string})
    click.echo(f"SSH string added to KDUMP configuration: {ssh_string}")


@add.command(name="ssh_path", help="Add an SSH path to the KDUMP configuration")
@click.argument('ssh_path', metavar='<ssh_path>', required=True)
@pass_db
def add_ssh_path(db, ssh_path):
    """Add an SSH path to KDUMP configuration"""

    def is_valid_ssh_path(ssh_path):
        """Validate the SSH path"""
        # Check if the path is absolute
        if not os.path.isabs(ssh_path):
            return "Invalid path. SSH path must be an absolute path."

        # (Optional) Check if the path exists on the system
        if not os.path.exists(ssh_path):
            return f"Invalid path. The path '{ssh_path}' does not exist."

        return None  # Validation successful

    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)
    current_status = kdump_table["config"].get("remote", "false").lower()
    if current_status == 'false':
        click.echo("Remote feature is not enabled. Please enable the remote feature first.")
        return

    # Validate SSH path
    validation_error = is_valid_ssh_path(ssh_path)
    if validation_error:
        click.echo(f"Error: {validation_error}")
        return

    # Add or update the 'ssh_path' entry in the KDUMP table
    db.cfgdb.mod_entry("KDUMP", "config", {"ssh_path": ssh_path})
    click.echo(f"SSH path added to KDUMP configuration: {ssh_path}")


@kdump.group(name="remove", help="remove configuration items to KDUMP")
def remove():
    """Group of commands to remove configuration items to KDUMP"""
    pass


@remove.command(name="ssh_string", help="Remove the SSH string from the KDUMP configuration")
@pass_db
def remove_ssh_string(db):
    """Remove the SSH string from KDUMP configuration"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    # Check if ssh_string exists
    if "ssh_string" in kdump_table["config"]:
        db.cfgdb.mod_entry("KDUMP", "config", {"ssh_string": None})
        click.echo("SSH string removed from KDUMP configuration.")
    else:
        click.echo("SSH string not found in KDUMP configuration.")


@remove.command(name="ssh_path", help="Remove the SSH path from the KDUMP configuration")
@pass_db
def remove_ssh_path(db):
    """Remove the SSH path from KDUMP configuration"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    # Check if ssh_string exists
    if "ssh_path" in kdump_table["config"]:
        db.cfgdb.mod_entry("KDUMP", "config", {"ssh_path": None})
        click.echo("SSH path removed from KDUMP configuration.")
    else:
        click.echo("SSH path not found in KDUMP configuration.")
