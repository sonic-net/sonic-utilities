#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with PSU in SONiC
#

import os
import sys

import click
import sonic_platform
from sonic_py_common import logger
from tabulate import tabulate


VERSION = '2.0'

SYSLOG_IDENTIFIER = "psuutil"

ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_NOT_IMPLEMENTED = 3

# Global platform-specific Chassis class instance
platform_chassis = None

# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)


# ==================== Methods for initialization ====================

# Instantiate platform-specific Chassis class
def load_platform_chassis():
    global platform_chassis

    # Load new platform api class
    try:
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
    except Exception as e:
        log.log_error("Failed to instantiate Chassis due to {}".format(repr(e)))

    if not platform_chassis:
        return False

    return True


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """psuutil - Command line utility for providing PSU status"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERROR_PERMISSIONS)

    # Load platform-specific Chassis class
    if not load_platform_chassis():
        sys.exit(ERROR_CHASSIS_LOAD)


# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("psuutil version {0}".format(VERSION))


# 'numpsus' subcommand
@cli.command()
def numpsus():
    """Display number of supported PSUs on device"""
    num_psus = platform_chassis.get_num_psus()
    click.echo(str(num_psus))


# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help='Index of the PSU')
def status(index):
    """Display PSU status"""
    header = ['PSU',  'Model', 'Serial', 'HW Rev', 'Voltage (V)', 'Current (A)', 'Power (W)', 'Power Warn-supp Thres (W)', 'Power Crit Thres (W)', 'Status', 'LED']
    status_table = []

    psu_list = platform_chassis.get_all_psus()

    for psu in psu_list:
        psu_name = psu.get_name()
        status = 'NOT PRESENT'
        model = 'N/A'
        serial = 'N/A'
        revision = 'N/A'
        voltage = 'N/A'
        current = 'N/A'
        power = 'N/A'
        led_color = 'N/A'
        power_critical_threshold = 'N/A'
        power_warning_suppress_threshold = 'N/A'

        if psu.get_presence():
            try:
                status = 'OK' if psu.get_powergood_status() else 'NOT OK'
                if psu.get_powergood_status():
                    power = psu.get_power()
                    try:
                        power_critical_threshold = psu.get_psu_power_critical_threshold()
                        power_warning_suppress_threshold = psu.get_psu_power_warning_suppress_threshold()
                    except NotImplementedError:
                        pass
                    if power_critical_threshold is None:
                        power_critical_threshold = 'N/A'
                    if power_warning_suppress_threshold is None:
                        power_warning_suppress_threshold = 'N/A'
                    status = 'OK'
            except NotImplementedError:
                status = 'UNKNOWN'

            try:
                model = psu.get_model()
            except NotImplementedError:
                pass

            try:
                serial = psu.get_serial()
            except NotImplementedError:
                pass

            try:
                revision = psu.get_revision()
            except NotImplementedError:
                pass

            try:
                voltage = psu.get_voltage()
            except NotImplementedError:
                pass

            try:
                current = psu.get_current()
            except NotImplementedError:
                pass

            try:
                power = psu.get_power()
            except NotImplementedError:
                pass

            try:
                led_color = psu.get_status_led()
            except NotImplementedError:
                pass

        status_table.append([psu_name, model, serial, revision, voltage, current, power, power_warning_suppress_threshold, power_critical_threshold, status, led_color])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt='simple', floatfmt='.2f'))


if __name__ == '__main__':
    cli()
