#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with switches over serial via console device
#

try:
    import click
    import os
    import sys
    import utilities_common.cli as clicommon

    from tabulate import tabulate
    from .lib import *
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

@click.group()
@clicommon.pass_db
def consutil(db):
    """consutil - Command-line utility for interacting with switches via console device"""
    config_db = db.cfgdb
    data = config_db.get_entry(CONSOLE_SWITCH_TABLE, FEATURE_KEY)
    if FEATURE_ENABLED_KEY not in data or data[FEATURE_ENABLED_KEY] == "no":
        click.echo("Console switch feature is disabled")
        sys.exit(ERR_DISABLE)

    SysInfoProvider.init_device_prefix()

# 'show' subcommand
@consutil.command()
@clicommon.pass_db
@click.option('--brief', '-b', metavar='<brief_mode>', required=False, is_flag=True)
def show(db, brief):
    """Show all ports and their info include available ttyUSB devices unless specified brief mode"""
    port_provider = ConsolePortProvider(db, brief, refresh=True)
    ports = list(port_provider.get_all())

    # sort ports for table rendering
    ports.sort(key=lambda p: int(p.line_num))

    # set table header style
    header = ["Line", "Baud", "Flow Control", "PID", "Start Time", "Device"]
    body = []
    for port in ports:
        # runtime information
        busy = "*" if port.busy else " "
        pid = port.session_pid if port.session_pid else "-"
        date = port.session_start_date if port.session_start_date else "-"
        baud = port.baud
        flow_control = "Enabled" if port.flow_control else "Disabled"
        body.append([busy+port.line_num, baud if baud else "-", flow_control, pid if pid else "-", date if date else "-", port.remote_device])
    click.echo(tabulate(body, header, stralign='right'))

# 'clear' subcommand
@consutil.command()
@clicommon.pass_db
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True, help="clear by name - if flag is set, interpret target as device name instead")
def clear(db, target, devicename):
    """Clear preexisting connection to line"""
    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERR_CMD)

    # identify the target line
    port_provider = ConsolePortProvider(db, configured_only=False)
    try:
        target_port = port_provider.get(target, use_device=devicename)
    except LineNotFoundError:
        click.echo("Target [{}] does not exist".format(target))
        sys.exit(ERR_DEV)

    if not target_port.clear_session():
        click.echo("No process is connected to line " + target_port.line_num)
    else:
        click.echo("Cleared line")

# 'connect' subcommand
@consutil.command()
@clicommon.pass_db
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True, help="connect by name - if flag is set, interpret target as device name instead")
def connect(db, target, devicename):
    """Connect to switch via console device - TARGET is line number or device name of switch"""
    # identify the target line
    port_provider = ConsolePortProvider(db, configured_only=False)
    try:
        target_port = port_provider.get(target, use_device=devicename)
    except LineNotFoundError:
        click.echo("Cannot connect: target [{}] does not exist".format(target))
        sys.exit(ERR_DEV)

    line_num = target_port.line_num

    # connect
    try:
        session = target_port.connect()
    except LineBusyError:
        click.echo("Cannot connect: line [{}] is busy".format(line_num))
        sys.exit(ERR_BUSY)
    except InvalidConfigurationError as cfg_err:
        click.echo("Cannot connect: {}".format(cfg_err.message))
        sys.exit(ERR_CFG)
    except ConnectionFailedError:
        click.echo("Cannot connect: unable to open picocom process")
        sys.exit(ERR_DEV)

    # interact
    click.echo("Successful connection to line [{}]\nPress ^A ^X to disconnect".format(line_num))
    session.interact()

if __name__ == '__main__':
    consutil()
