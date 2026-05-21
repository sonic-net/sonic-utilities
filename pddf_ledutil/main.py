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


# This is our main entrypoint - the main 'pddf_ledutil' command
@click.group()
def cli():
    """pddf_ledutil - Command line utility for providing System LED information"""

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
    click.echo("PDDF ledutil version {0}".format(VERSION))


# 'getstatusled' subcommand
@cli.command()
@click.argument('device_name', type=click.STRING)
def getstatusled(device_name):
    if device_name is None:
        click.echo("device_name is required")
        raise click.Abort()

    outputs = platform_chassis.get_system_led(device_name)
    click.echo(outputs)


# 'setstatusled' subcommand
@cli.command()
@click.argument('device_name', type=click.STRING)
@click.argument('color', type=click.STRING)
def setstatusled(device_name, color):
    if device_name is None:
        click.echo("device_name is required")
        raise click.Abort()

    outputs = platform_chassis.set_system_led(device_name, color)
    click.echo(outputs)


if __name__ == '__main__':
    cli()
