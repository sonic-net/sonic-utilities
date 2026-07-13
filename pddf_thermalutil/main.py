#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with Thermal sensors in PDDF mode in SONiC
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

# This is our main entrypoint - the main 'thermalutil' command
@click.group()
def cli():
    """pddf_thermalutil - Command line utility for providing Temp Sensors information"""

    global platform_chassis

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load platform-specific chassis 2.0 api class
    platform_chassis = helper.load_platform_chassis()
    if not platform_chassis:
        sys.exit(ERROR_CHASSIS_LOAD)


# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF thermalutil version {0}".format(VERSION))


# 'numthermals' subcommand
@cli.command()
def numthermals():
    """Display number of Thermal Sensors installed """
    num_thermals = platform_chassis.get_num_thermals()
    click.echo(num_thermals)


# 'gettemp' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of Temp Sensor (1-based)")
def gettemp(index):
    """Display Temperature values of thermal sensors"""
    thermal_list = []
    if (index < 0):
        thermal_list = platform_chassis.get_all_thermals()
        default_index = 0
    else:
        thermal_list = platform_chassis.get_thermal(index-1)
        default_index = index-1

    header = []
    temp_table = []
    has_label = False

    for idx, thermal in enumerate(thermal_list, default_index):
        thermal_name = helper.try_get(thermal.get_name, "TEMP{}".format(idx+1))
        # TODO: Provide a wrapper API implementation for the below function
        try:
            temp = thermal.get_temperature()
            if temp is not None:
                value = "temp1\t %+.1f C (" % temp
            else:
                value = "N/A ("

            high = thermal.get_high_threshold()
            if high is not None:
                value += "high = %+.1f C" % high
            else:
                value += "high = N/A"

            crit = thermal.get_high_critical_threshold()
            if crit is not None:
                value += ", crit = %+.1f C" % crit
            else:
                value += ", crit = N/A"

            value += ")"

            label = thermal.get_temp_label()

        except NotImplementedError:
            value = "N/A"
            label = None

        if label is not None:
            has_label = True

        # Always store as 3-column row [name, label, value]
        # label will be None for sensors without labels
        temp_table.append([thermal_name, label, value])

    if temp_table:
        if has_label:
            # Use 3-column header - sensors without labels will show empty in label column
            header = ['Temp Sensor', 'Label', 'Value']
        else:
            # Use 2-column header and remove label column from all rows
            header = ['Temp Sensor', 'Value']
            temp_table = [[row[0], row[2]] for row in temp_table]
        click.echo(tabulate(temp_table, header, tablefmt="simple"))


@cli.group()
def debug():
    """pddf_thermalutil debug commands"""
    pass


@debug.command()
def dump_sysfs():
    """Dump all Temp Sensor related SysFS paths"""
    thermal_list = platform_chassis.get_all_thermals()
    for idx, thermal in enumerate(thermal_list):
        status = thermal.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)


if __name__ == '__main__':
    cli()
