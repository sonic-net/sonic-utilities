#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with PSU Controller in PDDF mode in SONiC
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

# This is our main entrypoint - the main 'pddf_psuutil' command
@click.group()
def cli():
    """pddf_psuutil - Command line utility for providing PSU status for a platform using PDDF"""

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
    click.echo("PDDF psuutil version {0}".format(VERSION))


# 'numpsus' subcommand
@cli.command()
def numpsus():
    """Display number of supported PSUs on device"""
    num_psus = platform_chassis.get_num_psus()
    click.echo(str(num_psus))


# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of the PSU (1-based)")
def status(index):
    """Display PSU status"""
    psu_list = []
    if (index < 0):
        psu_list = platform_chassis.get_all_psus()
        default_index = 0
    else:
        psu_list = platform_chassis.get_psu(index-1)
        default_index = index-1

    header = ['PSU', 'Status']
    status_table = []

    for idx, psu in enumerate(psu_list, default_index):
        psu_name = helper.try_get(psu.get_name, "PSU {}".format(idx+1))
        status = 'NOT PRESENT'
        if psu.get_presence():
            oper_status = helper.try_get(psu.get_powergood_status, 'UNKNOWN')
            if oper_status is True:
                status = 'OK'
            elif oper_status is False:
                status = 'NOT OK'
            else:
                status = oper_status

        status_table.append([psu_name, status])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt='simple'))


# 'mfrinfo' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of the PSU (1-based)")
def mfrinfo(index):
    """Display PSU manufacturer info"""
    psu_list = []
    if (index < 0):
        psu_list = platform_chassis.get_all_psus()
        default_index = 0
    else:
        psu_list = platform_chassis.get_psu(index-1)
        default_index = index-1

    header = ['PSU', 'Status', 'Manufacturer ID', 'Model', 'Serial', 'Fan Airflow Direction']
    mfrinfo_table = []

    for idx, psu in enumerate(psu_list, default_index):
        psu_name = helper.try_get(psu.get_name, "PSU {}".format(idx+1))
        status = 'NOT PRESENT'
        model_name = 'N/A'
        mfr_id = 'N/A'
        serial_num = 'N/A'
        airflow_dir = 'N/A'
        if psu.get_presence():
            oper_status = helper.try_get(psu.get_powergood_status, 'UNKNOWN')
            if oper_status is True:
                status = 'OK'
            elif oper_status is False:
                status = 'NOT OK'
            else:
                status = oper_status

            model_name = helper.try_get(psu.get_model, 'N/A')
            mfr_id = helper.try_get(psu.get_mfr_id, 'N/A')
            serial_num = helper.try_get(psu.get_serial, 'N/A')
            airflow_dir = helper.try_get(psu._fan_list[0].get_direction, 'N/A')

        mfrinfo_table.append([psu_name, status, mfr_id, model_name, serial_num, airflow_dir])

    if mfrinfo_table:
        click.echo(tabulate(mfrinfo_table, header, tablefmt='simple'))


# 'seninfo' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
def seninfo(index):
    """Display PSU sensor info"""
    psu_list = []
    if (index < 0):
        psu_list = platform_chassis.get_all_psus()
        default_index = 0
    else:
        psu_list = platform_chassis.get_psu(index-1)
        default_index = index-1

    header = ['PSU', 'Status', 'Output Voltage (V)', 'Output Current (A)',
              'Output Power (W)', 'Temperature1 (C)', 'Fan1 Speed (RPM)']
    seninfo_table = []

    for idx, psu in enumerate(psu_list, default_index):
        psu_name = helper.try_get(psu.get_name, "PSU {}".format(idx+1))
        status = 'NOT PRESENT'
        v_out = 'N/A'
        i_out = 'N/A'
        p_out = 'N/A'
        temp1 = 'N/A'
        fan1_rpm = 'N/A'

        if psu.get_presence():
            oper_status = helper.try_get(psu.get_powergood_status, 'UNKNOWN')
            if oper_status is True:
                status = 'OK'
            elif oper_status is False:
                status = 'NOT OK'
            else:
                status = oper_status

            v_out = helper.try_get(psu.get_voltage, 'N/A')
            i_out = helper.try_get(psu.get_current, 'N/A')
            p_out = helper.try_get(psu.get_power, 'N/A')
            temp1 = helper.try_get(psu.get_temperature, 'N/A')
            fan1_rpm = helper.try_get(psu._fan_list[0].get_speed_rpm, 'N/A')

        seninfo_table.append([psu_name, status, v_out, i_out, p_out, temp1, fan1_rpm])

    if seninfo_table:
        click.echo(tabulate(seninfo_table, header, tablefmt='simple', floatfmt='.2f'))


@cli.group()
def debug():
    """pddf_psuutil debug commands"""
    pass


@debug.command()
def dump_sysfs():
    """Dump all PSU related SysFS paths"""
    psu_list = platform_chassis.get_all_psus()
    for psu in psu_list:
        status = psu.dump_sysfs()

        if status:
            for i in status:
                click.echo(i)


if __name__ == '__main__':
    cli()
