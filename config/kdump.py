import sys
import click
import os
from utilities_common.cli import AbbreviationGroup, pass_db
from ipaddress import ip_address, AddressValueError
import re


def is_valid_ssh_string(ssh_string):
    if '@' not in ssh_string:
        return False
    name, ip = ssh_string.split('@', 1)
    try:
        ip_address.ip_address(ip)
    except ValueError:
        return False
    return True


def is_valid_path(path):
    # You can make this stricter as needed (checking existence or just syntax)
    return bool(path.strip()) and path.startswith("/")


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

#
# 'remote' command ('sudo config kdump remote enable/disable')
#


@kdump.group(name="remote", help="Enable or disable remote KDUMP configuration")
def kdump_remote():
    pass

#
# 'remote' command ('sudo config kdump remote enable ...')
#


@kdump_remote.command(name="enable", help="Enable remote KDUMP configuration")
@pass_db
def remote_enable(db):
    """Enable remote KDUMP"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    current_val = kdump_table.get("config", {}).get("remote", "false").lower()

    if current_val == "true":
        click.echo("Remote KDUMP is already enabled.")
    else:
        db.cfgdb.mod_entry("KDUMP", "config", {"remote": "true"})
        click.echo("Remote KDUMP has been enabled.")
        echo_reboot_warning()

#
# 'remote' command ('sudo config kdump remote disable ...')
#

@kdump_remote.command(name="disable", help="Disable remote KDUMP configuration")
@pass_db
def remote_disable(db):
    """Disable remote KDUMP"""
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    current_val = kdump_table.get("config", {}).get("remote", "false").lower()

    if current_val == "false":
        click.echo("Remote KDUMP is already disabled.")
    else:
        db.cfgdb.mod_entry("KDUMP", "config", {"remote": "false"})
        click.echo("Remote KDUMP has been disabled.")
        echo_reboot_warning()


# ------------------ Add group ------------------

@kdump.group(name="add", help="Add kdump configuration parameters")
def kdump_add():
    pass

#
# 'ssh_string' command ('sudo config kdump add ssh_string ...')
#


@kdump_add.command(name="ssh_string", help="Add SSH string in the format user@ip")
@click.argument('ssh_string', metavar='<user@ip>', required=True)
@pass_db
def add_ssh_string(db, ssh_string):
    if not is_valid_ssh_string(ssh_string):
        click.echo(f"Error: Invalid SSH string '{ssh_string}'. Must be in format user@<valid_ip>")
        return

    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)
    db.cfgdb.mod_entry("KDUMP", "config", {"ssh_string": ssh_string})
    click.echo(f"SSH string set to '{ssh_string}' successfully.")

#
# 'ssh_path' command ('sudo config kdump add ssh_path ...')
#


@kdump_add.command(name="ssh_path", help="Add SSH path (must be an absolute path)")
@click.argument('ssh_path', metavar='<ssh_path>', required=True)
@pass_db
def add_ssh_path(db, ssh_path):
    if not is_valid_path(ssh_path):
        click.echo(f"Error: Invalid path '{ssh_path}'. Must be an absolute path (starts with '/')")
        return

    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)
    db.cfgdb.mod_entry("KDUMP", "config", {"ssh_path": ssh_path})
    click.echo(f"SSH path set to '{ssh_path}' successfully.")

# ------------------ Remove group ------------------

@kdump.group(name="remove", help="Remove kdump configuration parameters")
def kdump_remove():
    pass

#
# 'ssh_string' remove command ('sudo config kdump remove ssh_string ...')
#


@kdump_remove.command(name="ssh_string", help="Remove SSH string")
@pass_db
def remove_ssh_string(db):
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    current_val = kdump_table.get("config", {}).get("ssh_string", "")
    if not current_val:
        click.echo("No SSH string is currently set. Nothing to remove.")
        return

    db.cfgdb.mod_entry("KDUMP", "config", {"ssh_string": ""})
    click.echo("SSH string removed successfully.")

#
# 'ssh_path' remove command ('sudo config kdump remove ssh_path ...')
#


@kdump_remove.command(name="ssh-path", help="Remove SSH path")
@pass_db
def remove_ssh_path(db):
    kdump_table = db.cfgdb.get_table("KDUMP")
    check_kdump_table_existence(kdump_table)

    current_val = kdump_table.get("config", {}).get("ssh_path", "")
    if not current_val:
        click.echo("No SSH path is currently set. Nothing to remove.")
        return

    db.cfgdb.mod_entry("KDUMP", "config", {"ssh_path": ""})
    click.echo("SSH path removed successfully.")
