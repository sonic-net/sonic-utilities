import os
import sys

import click
from tabulate import tabulate
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector
from natsort import natsorted
from utilities_common.chassis import is_smartswitch, get_all_dpu_options

DPU_STATE = 'DPU_STATE'
CHASSIS_SERVER = 'redis_chassis.server'
CHASSIS_SERVER_PORT = 6380
CHASSIS_STATE_DB = 13


def get_system_health_status():
    if os.environ.get("UTILITIES_UNIT_TESTING") == "1":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        sys.path.insert(0, modules_path)
        from tests.system_health_test import MockerManager
        from tests.system_health_test import MockerChassis
        HealthCheckerManager = MockerManager
        Chassis = MockerChassis
    else:
        if os.geteuid():
            click.echo("Root privileges are required for this operation")
            exit(1)
        from health_checker.manager import HealthCheckerManager
        from sonic_platform.chassis import Chassis


    manager = HealthCheckerManager()
    if not manager.config.config_file_exists():
        click.echo("System health configuration file not found, exit...")
        exit(1)

    chassis = Chassis()
    stat = manager.check(chassis)
    chassis.initizalize_system_led()

    return manager, chassis, stat

def display_system_health_summary(stat, led):
    click.echo("System status summary\n\n  System status LED  " + led)
    services_list = []
    fs_list = []
    device_list =[]
    for category, elements in stat.items():
        for element in elements:
            if elements[element]['status'] != "OK":
                if category == 'Services':
                    if 'Accessible' in elements[element]['message']:
                        fs_list.append(element)
                    else:
                        services_list.append(element)
                else:
                    device_list.append(elements[element]['message'])
    if services_list or fs_list:
        click.echo("  Services:\n    Status: Not OK")
    else:
        click.echo("  Services:\n    Status: OK")
    if services_list:
        click.echo("    Not Running: " + ', '.join(services_list))
    if fs_list:
        click.echo("    Not Accessible: " + ', '.join(fs_list))
    if device_list:
        click.echo("  Hardware:\n    Status: Not OK")
        device_list.reverse()
        click.echo("    Reasons: " + device_list[0])
        if len(device_list) > 1:
            click.echo('\n'.join(("\t     " + x) for x in device_list[1:]))
    else:
        click.echo("  Hardware:\n    Status: OK")

def display_monitor_list(stat):
    click.echo('\nSystem services and devices monitor list\n')
    header = ['Name', 'Status', 'Type']
    table = []
    for elements in stat.values():
        for element in sorted(elements.items(), key=lambda x: x[1]['status']):
            entry = []
            entry.append(element[0])
            entry.append(element[1]['status'])
            entry.append(element[1]['type'])
            table.append(entry)
    click.echo(tabulate(table, header))


def display_ignore_list(manager):
    header = ['Name', 'Status', 'Type']
    click.echo('\nSystem services and devices ignore list\n')
    table = []
    if manager.config.ignore_services:
        for element in manager.config.ignore_services:
            entry = []
            entry.append(element)
            entry.append("Ignored")
            entry.append("Service")
            table.append(entry)
    if manager.config.ignore_devices:
        for element in manager.config.ignore_devices:
            entry = []
            entry.append(element)
            entry.append("Ignored")
            entry.append("Device")
            table.append(entry)
    click.echo(tabulate(table, header))

#
# 'system-health' command ("show system-health")
#
@click.group(name='system-health', cls=clicommon.AliasedGroup)
def system_health():
    """Show system-health information"""
    return

@system_health.command()
def summary():
    """Show system-health summary information"""
    _, chassis, stat = get_system_health_status()
    display_system_health_summary(stat, chassis.get_status_led())


@system_health.command()
def detail():
    """Show system-health detail information"""
    manager, chassis, stat = get_system_health_status()
    display_system_health_summary(stat, chassis.get_status_led())
    display_monitor_list(stat)
    display_ignore_list(manager)


@system_health.command()
def monitor_list():
    """Show system-health monitored services and devices name list"""
    _, _, stat = get_system_health_status()
    display_monitor_list(stat)


@system_health.group('sysready-status',invoke_without_command=True)
@click.pass_context
def sysready_status(ctx):
    """Show system-health system ready status"""

    if ctx.invoked_subcommand is None:
        try:
            cmd = ["sysreadyshow"]
            clicommon.run_command(cmd, display_cmd=False)
        except Exception as e:
            click.echo("Exception: {}".format(str(e)))


@sysready_status.command('brief')
def sysready_status_brief():
    try:
        cmd = ["sysreadyshow", "--brief"]
        clicommon.run_command(cmd, display_cmd=False)
    except Exception as e:
        click.echo("Exception: {}".format(str(e)))


@sysready_status.command('detail')
def sysready_status_detail():
    try:
        cmd = ["sysreadyshow", "--detail"]
        clicommon.run_command(cmd, display_cmd=False)
    except Exception as e:
        click.echo("Exception: {}".format(str(e)))


def show_dpu_state(module_name):
    chassis_state_db = SonicV2Connector(host=CHASSIS_SERVER, port=CHASSIS_SERVER_PORT)
    chassis_state_db.connect(chassis_state_db.CHASSIS_STATE_DB)
    key = 'DPU_STATE|'
    suffix = '*' if not module_name or not module_name.startswith("DPU") else module_name
    key = key + suffix
    keys = chassis_state_db.keys(chassis_state_db.CHASSIS_STATE_DB, key)
    if not keys:
        click.echo("DPU_STATE table is not present for module:{} in DB".format(module_name))
        return

    table = []
    for dbkey in natsorted(keys):
        key_list = dbkey.split('|')
        if len(key_list) != 2:  # error data in DB, log it and ignore
            continue
        state_info = chassis_state_db.get_all(chassis_state_db.CHASSIS_STATE_DB, dbkey)
        # Determine operational status
        midplanedown = False
        up_cnt = 0
        for key, value in state_info.items():
            if key.endswith('_state'):
                if value.lower() == 'up':
                    up_cnt = up_cnt + 1
                if 'midplane' in key and value.lower() == 'down':
                    midplanedown = True

        if midplanedown:
            oper_status = "Offline"
        elif up_cnt == 3:
            oper_status = "Online"
        else:
            oper_status = "Partial Online"

        for dpustates in range(3):
            if dpustates == 0:
                row = [key_list[1], oper_status, "", "", "", ""]
            else:
                row = ["", "", "", "", "", ""]
            for key, value in state_info.items():
                if key == "id":
                    continue
                if dpustates == 0 and 'midplane' in key:
                    populate_row(row, key, value, table)
                elif dpustates == 1 and 'control' in key:
                    populate_row(row, key, value, table)
                elif dpustates == 2 and 'data' in key:
                    populate_row(row, key, value, table)

    headers = ["Name", "Oper-Status", "State-Detail", "State-Value", "Time", "Reason"]
    click.echo(tabulate(table, headers=headers))


def populate_row(row, key, value, table):
    if key.endswith('_state'):
        row[2] = key
        row[3] = value
        if "up" in row[3]:
            row[5] = ""
        table.append(row)
    elif key.endswith('_time'):
        row[4] = value
    elif key.endswith('_reason'):
        if "up" not in row[3]:
            row[5] = value


@system_health.command()
@click.argument('module_name',
                required=True,
                type=click.Choice(get_all_dpu_options(), case_sensitive=False) if is_smartswitch() else None
                )
def dpu(module_name):
    """Show system-health dpu information"""
    if not is_smartswitch():
        return
    show_dpu_state(module_name)
