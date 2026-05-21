import itertools
import os
import sys

import click
from tabulate import tabulate

import utilities_common.cli as clicommon
from swsscommon.swsscommon import ConfigDBConnector

#
# 'kdump' group (show kdump ...)
#
@click.group(cls=clicommon.AliasedGroup, name="kdump")
def kdump():
    """Show kdump configuration, dump files and dmesg logs"""
    pass


def get_kdump_config(field_name):
    """Fetches the configuration of Kdump from `CONFIG_DB`.

    Args:
      field_name: A string contains the field name in the sub-table of 'config'.

    Returns:
      field_value: If field name was found, then returns the corresponding value.
                   Otherwise, returns "Unknown".
    """
    field_value = "Unknown"
    config_db = ConfigDBConnector()
    config_db.connect()
    kdump_table = config_db.get_table("KDUMP")
    if kdump_table and "config" in kdump_table and field_name in kdump_table["config"]:
        field_value = kdump_table["config"][field_name]

    return field_value


def get_kdump_oper_mode():
    """Fetches the operational mode of Kdump from the execution result of command
    `/usr/sbin/kdump-config status`.

    Args:
      None.

    Returns:
      admin_mode: If Kdump is ready, returns "Ready"; If Kdump is not ready,
                  returns "Not Ready";
    """
    oper_mode = "Not Ready"
    command_stdout, _ = clicommon.run_command(['/usr/sbin/kdump-config', 'status'], return_cmd=True)

    for line in command_stdout.splitlines():
        if ": ready to kdump" in line:
            oper_mode = "Ready"
            break

    return oper_mode


#
# 'config' subcommand (show kdump config)
#
@kdump.command(name="config", short_help="Show the configuration of Linux kernel dump")
def config():
    admin_mode = "Disabled"
    admin_enabled = get_kdump_config("enabled")
    if admin_enabled == "true":
        admin_mode = "Enabled"

    oper_mode = get_kdump_oper_mode()

    click.echo("Kdump administrative mode: {}".format(admin_mode))
    if admin_mode == "Enabled" and oper_mode == "Not Ready":
        click.echo("Kdump operational mode: Ready after reboot")
    else:
        click.echo("Kdump operational mode: {}".format(oper_mode))

    mem_config = get_kdump_config("memory")
    click.echo("Kdump memory reservation: {}".format(mem_config))

    num_files_config = get_kdump_config("num_dumps")
    click.echo("Maximum number of Kdump files: {}".format(num_files_config))

    # remote SSH configs
    if get_kdump_config("remote") == "true":
        ssh_conn_str = get_kdump_config("ssh_string")
        click.echo("Kdump ssh connection string: {}".format(ssh_conn_str))

        ssh_prv_key = get_kdump_config("ssh_path")
        click.echo("Kdump private key path: {}".format(ssh_prv_key))

    else:
        click.echo("Kdump ssh connection string and ssh_path not found")


def get_kdump_core_files():
    """Retrieves the kernel core dump files from directory '/var/crash/'.

    Args:
      None.

    Returns:
      cmd_message: A string contains the information showing the execution result
                   of 'find' command.
      dump_file_list: A list contains kernel core dump files.
    """
    find_core_dump_files = ['find', '/var/crash', '-name', 'kdump.*']
    dump_file_list = []
    cmd_message = None

    command_stdout, _ = clicommon.run_command(find_core_dump_files, return_cmd=True)

    dump_file_list = command_stdout.splitlines()
    if not dump_file_list:
        cmd_message = "No kernel core dump file available!"

    return cmd_message, dump_file_list


def get_kdump_dmesg_files():
    """Retrieves the kernel dmesg files from directory '/var/crash/'.

    Args:
      None.

    Returns:
      cmd_message: A string contains the information showing the execution result
                   of 'find' command.
      dmesg_file_list: A list contains kernel dmesg files.
    """
    find_dmesg_files = ['find', '/var/crash', '-name', 'dmesg.*']
    dmesg_file_list = []
    cmd_message = None

    command_stdout, _ = clicommon.run_command(find_dmesg_files, return_cmd=True)

    dmesg_file_list = command_stdout.splitlines()
    if not dmesg_file_list:
        cmd_message = "No kernel dmesg file available!"

    return cmd_message, dmesg_file_list


#
# 'files' subcommand (show kdump files)
#
@kdump.command(name="files", short_help="Show kernel core dump and dmesg files")
def files():
    core_file_result = []
    dmesg_file_result = []
    body = []

    cmd_message, core_file_result = get_kdump_core_files()
    if not core_file_result:
        core_file_result.append(cmd_message)

    cmd_message, dmesg_file_result = get_kdump_dmesg_files()
    if not dmesg_file_result:
        dmesg_file_result.append(cmd_message)

    core_file_result.sort(reverse=True)
    dmesg_file_result.sort(reverse=True)

    header = ["Kernel core dump files", "Kernel dmesg files"]

    for (core_file, dmesg_file) in itertools.zip_longest(core_file_result, dmesg_file_result, fillvalue=""):
        body.append([core_file, dmesg_file])

    click.echo(tabulate(body, header, stralign="center"))


#
# 'logging' subcommand (show kdump logging)
#
@kdump.command(name="logging", short_help="Show last 10 lines of latest kernel dmesg file")
@click.argument('filename', required=False)
@click.option('-l', '--lines', default=10, show_default=True)
def logging(filename, lines):
    cmd = ['sudo', 'tail', '-'+str(lines)]

    if filename:
        timestamp = filename.strip().split(".")[-1]
        file_path = "/var/crash/{}/{}".format(timestamp, filename)
        if os.path.isfile(file_path):
            cmd += [str(file_path)]
        else:
            click.echo("Invalid filename: '{}'!".format(filename))
            sys.exit(1)
    else:
        cmd_message, dmesg_file_result = get_kdump_dmesg_files()
        if len(dmesg_file_result) == 0:
            click.echo(cmd_message)
            sys.exit(2)

        dmesg_file_result.sort(reverse=True)
        cmd += [str(dmesg_file_result[0])]

    clicommon.run_command(cmd)
