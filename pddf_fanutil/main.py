#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with FAN Controller in PDDF mode in SONiC
#

try:
    import sys
    import os
    import click
    from tabulate import tabulate
    from utilities_common.util_base import UtilHelper
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '2.0'

ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_NOT_IMPLEMENTED = 3
ERROR_PDDF_NOT_SUPPORTED = 4

# Global platform-specific chassis class instance
platform_chassis = None

# Load the helper class
helper = UtilHelper()

# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'pddf_fanutil' command
@click.group()
def cli():
    """pddf_fanutil - Command line utility for providing FAN information"""

    global platform_chassis

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERROR_PERMISSIONS)

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(ERROR_PDDF_NOT_SUPPORTED)

    # Load platform-specific chassis 2.0 api class
    platform_chassis = helper.load_platform_chassis()
    if not platform_chassis:
        sys.exit(ERROR_CHASSIS_LOAD)


# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF fanutil version {0}".format(VERSION))


# 'numfans' subcommand
@cli.command()
def numfans():
    """Display number of FANs installed on device"""
    num_fans = platform_chassis.get_num_fans()
    click.echo(num_fans)


# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of FAN (1-based)")
def status(index):
    """Display FAN status"""
    fan_list = []
    if (index < 0):
        fan_list = platform_chassis.get_all_fans()
        default_index = 0
    else:
        fan_list = platform_chassis.get_fan(index-1)
        default_index = index-1

    header = ['FAN', 'Status']
    status_table = []

    for idx, fan in enumerate(fan_list, default_index):
        fan_name = helper.try_get(fan.get_name, "Fan {}".format(idx+1))
        status = 'NOT PRESENT'
        if fan.get_presence():
            oper_status = helper.try_get(fan.get_status, 'UNKNOWN')
            if oper_status is True:
                status = 'OK'
            elif oper_status is False:
                status = 'NOT OK'
            else:
                status = oper_status

        status_table.append([fan_name, status])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))


# 'direction' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of FAN (1-based)")
def direction(index):
    """Display FAN airflow direction"""
    fan_list = []
    if (index < 0):
        fan_list = platform_chassis.get_all_fans()
        default_index = 0
    else:
        fan_list = platform_chassis.get_fan(index-1)
        default_index = index-1

    header = ['FAN', 'Direction']
    dir_table = []

    for idx, fan in enumerate(fan_list, default_index):
        fan_name = helper.try_get(fan.get_name, "Fan {}".format(idx+1))
        direction = helper.try_get(fan.get_direction, 'N/A')
        dir_table.append([fan_name, direction.capitalize()])

    if dir_table:
        click.echo(tabulate(dir_table, header, tablefmt="simple"))


# 'speed' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of FAN (1-based)")
def getspeed(index):
    """Display FAN speed in RPM"""
    fan_list = []
    if (index < 0):
        fan_list = platform_chassis.get_all_fans()
        default_index = 0
    else:
        fan_list = platform_chassis.get_fan(index-1)
        default_index = index-1

    header = ['FAN', 'SPEED (RPM)']
    speed_table = []

    for idx, fan in enumerate(fan_list, default_index):
        fan_name = helper.try_get(fan.get_name, "Fan {}".format(idx+1))
        rpm = helper.try_get(fan.get_speed_rpm, 'N/A')
        speed_table.append([fan_name, rpm])

    if speed_table:
        click.echo(tabulate(speed_table, header, tablefmt="simple"))


# 'setspeed' subcommand
@cli.command()
@click.argument('speed', type=int)
def setspeed(speed):
    """Set FAN speed in percentage"""
    if speed is None:
        click.echo("speed value is required")
        raise click.Abort()

    fan_list = platform_chassis.get_all_fans()
    for idx, fan in enumerate(fan_list):
        try:
            status = fan.set_speed(speed)
        except NotImplementedError:
            click.echo("Set speed API not implemented")
            sys.exit(0)

        if not status:
            click.echo("Failed")
            sys.exit(1)

    click.echo("Successful")


@cli.group()
def debug():
    """pddf_fanutil debug commands"""
    pass


@debug.command()
def dump_sysfs():
    """Dump all Fan related SysFS paths"""
    fan_list = platform_chassis.get_all_fans()
    for idx, fan in enumerate(fan_list):
        status = fan.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)


if __name__ == '__main__':
    cli()
