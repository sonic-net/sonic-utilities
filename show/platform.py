import os
import json
import subprocess
import sys

import click
from tabulate import tabulate
import utilities_common.cli as clicommon
from sonic_py_common import device_info

#
# Helper functions
#

def get_chassis_info():
    """
    Attempts to retrieve chassis information from CHASSIS_INFO table in STATE_DB if this table does
    not exist then we assume pmon has crashed and will attempt to call the platform API directly. If this
    call fails we simply return N/A.
    """

    keys = ["serial", "model", "revision", "switch_host_serial"]

    def try_get(platform, attr, fallback):
        try:
            if platform["chassis"] is None:
                import sonic_platform
                platform["chassis"] = sonic_platform.platform.Platform().get_chassis()
            if attr == "switch_host_serial" and platform["chassis"].is_bmc() is False:
                return fallback
            return getattr(platform["chassis"], "get_{}".format(attr))()
        except Exception:
            return fallback

    chassis_info = device_info.get_chassis_info()

    if all(v is None for k, v in chassis_info.items()):
        platform_cache = {"chassis": None}
        chassis_info = {k:try_get(platform_cache, k, "N/A") for k in keys}

    return chassis_info


#
# 'platform' group ("show platform ...")
#

@click.group(cls=clicommon.AliasedGroup)
def platform():
    """Show platform-specific hardware info"""
    pass


# 'summary' subcommand ("show platform summary")
@platform.command()
@click.option('--json', is_flag=True, help="Output in JSON format")
def summary(json):
    """Show hardware platform information"""
    platform_info = device_info.get_platform_info()
    chassis_info = get_chassis_info()

    if json:
        click.echo(clicommon.json_dump({**platform_info, **chassis_info}))
    else:
        click.echo("Platform: {}".format(platform_info['platform']))
        click.echo("HwSKU: {}".format(platform_info['hwsku']))
        click.echo("ASIC: {}".format(platform_info['asic_type']))
        click.echo("ASIC Count: {}".format(platform_info['asic_count']))
        click.echo("Serial Number: {}".format(chassis_info['serial']))
        click.echo("Model Number: {}".format(chassis_info['model']))
        click.echo("Hardware Revision: {}".format(chassis_info['revision']))
        switch_type = platform_info.get('switch_type')
        if switch_type:
            click.echo("Switch Type: {}".format(switch_type))


# 'bmc' subcommand ("show platform bmc")
@platform.group()
def bmc():
    """Show BMC information"""
    pass


# 'summary' subcommand ("show platform bmc summary")
@bmc.command(name='summary')
@click.option('--json', is_flag=True, help="Output in JSON format")
def bmc_summary(json):
    """Show BMC summary information"""
    try:
        import sonic_platform
        chassis = sonic_platform.platform.Platform().get_chassis()
        bmc = chassis.get_bmc()

        if bmc is None:
            click.echo("BMC is not available on this platform")
            return

        eeprom_info = bmc.get_eeprom()
        if not eeprom_info:
            click.echo("Failed to retrieve BMC EEPROM information")
            return

        # Extract the required fields
        manufacturer = eeprom_info.get('Manufacturer', 'N/A')
        model = eeprom_info.get('Model', 'N/A')
        part_number = eeprom_info.get('PartNumber', 'N/A')
        power_state = eeprom_info.get('PowerState', 'N/A')
        serial_number = eeprom_info.get('SerialNumber', 'N/A')
        bmc_version = bmc.get_version()

        if json:
            bmc_summary = {
                'Manufacturer': manufacturer,
                'Model': model,
                'PartNumber': part_number,
                'SerialNumber': serial_number,
                'PowerState': power_state,
                'FirmwareVersion': bmc_version
            }
            click.echo(clicommon.json_dump(bmc_summary))
        else:
            click.echo(f"Manufacturer: {manufacturer}")
            click.echo(f"Model: {model}")
            click.echo(f"PartNumber: {part_number}")
            click.echo(f"SerialNumber: {serial_number}")
            click.echo(f"PowerState: {power_state}")
            click.echo(f"FirmwareVersion: {bmc_version}")

    except Exception as e:
        click.echo(f"Error retrieving BMC information: {str(e)}")


# 'eeprom' subcommand ("show platform bmc eeprom")
@bmc.command()
@click.option('--json', is_flag=True, help="Output in JSON format")
def eeprom(json):
    """Show BMC EEPROM information"""
    try:
        import sonic_platform
        chassis = sonic_platform.platform.Platform().get_chassis()
        bmc = chassis.get_bmc()

        if bmc is None:
            click.echo("BMC is not available on this platform")
            return

        # Get BMC EEPROM information
        eeprom_info = bmc.get_eeprom()

        if not eeprom_info:
            click.echo("Failed to retrieve BMC EEPROM information")
            return

        # Extract the required fields
        manufacturer = eeprom_info.get('Manufacturer', 'N/A')
        model = eeprom_info.get('Model', 'N/A')
        part_number = eeprom_info.get('PartNumber', 'N/A')
        power_state = eeprom_info.get('PowerState', 'N/A')
        serial_number = eeprom_info.get('SerialNumber', 'N/A')

        if json:
            bmc_eeprom = {
                'Manufacturer': manufacturer,
                'Model': model,
                'PartNumber': part_number,
                'PowerState': power_state,
                'SerialNumber': serial_number
            }
            click.echo(clicommon.json_dump(bmc_eeprom))
        else:
            click.echo(f"Manufacturer: {manufacturer}")
            click.echo(f"Model: {model}")
            click.echo(f"PartNumber: {part_number}")
            click.echo(f"PowerState: {power_state}")
            click.echo(f"SerialNumber: {serial_number}")

    except Exception as e:
        click.echo(f"Error retrieving BMC EEPROM information: {str(e)}")


# 'syseeprom' subcommand ("show platform syseeprom")
@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def syseeprom(verbose):
    """Show system EEPROM information"""
    cmd = ['sudo', 'decode-syseeprom', '-d']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'psustatus' subcommand ("show platform psustatus")
@platform.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
@click.option('--json', is_flag=True, help="Output in JSON format")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def psustatus(index, json, verbose):
    """Show PSU status information"""
    cmd = ['psushow', '-s']

    if index >= 0:
        cmd += ['-i', str(index)]

    if json:
        cmd += ["-j"]

    clicommon.run_command(cmd, display_cmd=verbose)


# 'ssdhealth' subcommand ("show platform ssdhealth [--verbose/--vendor]")
@platform.command()
@click.argument('device', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--vendor', is_flag=True, help="Enable vendor specific output")
def ssdhealth(device, verbose, vendor):
    """Show SSD Health information"""
    if not device:
        platform_data = device_info.get_platform_json_data()
        # Check if there is any default disk for this platform
        # {
        #     "chassis": {
        #         ..........
        #         "disk": {
        #             "device" : "/dev/nvme0n1"
        #         }
        #     }
        # }
        if platform_data:
            device = platform_data.get("chassis", {}).get("disk", {}).get("device", None)

    # if device argument is not provided ssdutil will display the health of the disk containing
    # the /host partition. In sonic this is the primary storage device.
    if device:
        cmd = ['sudo', 'ssdutil', '-d', str(device)]
    else:
        cmd = ['sudo', 'ssdutil']

    options = ["-v"] if verbose else []
    options += ["-e"] if vendor else []
    clicommon.run_command(cmd + options, display_cmd=verbose)


@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('-c', '--check', is_flag=True, help="Check the platfome pcie device")
def pcieinfo(check, verbose):
    """Show Device PCIe Info"""
    cmd = ['sudo', 'pcieutil', 'show']
    if check:
        cmd = ['sudo', 'pcieutil', 'check']
    clicommon.run_command(cmd, display_cmd=verbose)


# 'fan' subcommand ("show platform fan")
@platform.command()
def fan():
    """Show fan status information"""
    cmd = ['fanshow']
    clicommon.run_command(cmd)


# 'temperature' subcommand ("show platform temperature")
@platform.command()
@click.option('-j', '--json', 'output_json', is_flag=True, help="Output in JSON format")
def temperature(output_json):
    """Show device temperature information"""
    cmd = ['tempershow']
    if output_json:
        output, _ = clicommon.run_command(cmd+["-j"], return_cmd=True)
        try:
            data = json.loads(output)
            click.echo(clicommon.json_dump(data))
        except json.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON output: {e}", err=True)
    else:
        clicommon.run_command(cmd)

# 'voltage' subcommand ("show platform voltage")
@platform.command()
def voltage():
    """Show device voltage information"""
    cmd = ["sensorshow", "-t", "voltage"]
    clicommon.run_command(cmd)


# 'current' subcommand ("show platform current")
@platform.command()
def current():
    """Show device current information"""
    cmd = ["sensorshow", "-t", "current"]
    clicommon.run_command(cmd)


# 'firmware' subcommand ("show platform firmware")
@platform.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True
    ),
    add_help_option=False
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def firmware(args):
    """Show firmware information"""
    cmd = ["sudo", "fwutil", "show"] + list(args)

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


LEAK_CONTROL_POLICY_TABLE = 'LEAK_CONTROL_POLICY'
LEAK_CONTROL_POLICY_KEY = 'config'
RACK_MANAGER_ALERT_TABLE = 'RACK_MANAGER_ALERT'
LEAK_PROFILE_TABLE = 'LEAK_PROFILE'
LIQUID_COOLING_INFO_TABLE = 'LIQUID_COOLING_INFO'


def _get_state_db():
    from swsscommon.swsscommon import SonicV2Connector
    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)
    return state_db


# 'leak' group ("show platform leak ...")
@platform.group()
def leak():
    """Show liquid cooling leak information"""
    pass


@leak.command('control-policy')
def leak_control_policy():
    """Show leak control policy configuration"""
    try:
        from utilities_common.db import Db
        db = Db()
        entry = db.cfgdb.get_entry(LEAK_CONTROL_POLICY_TABLE, LEAK_CONTROL_POLICY_KEY)
        click.echo(" system_leak_policy              : {}".format(entry.get('system_leak_policy', 'enabled')))
        critical_action = entry.get('system_critical_leak_action', 'power_off')
        click.echo(" system_critical_leak_action     : {}".format(critical_action))
        click.echo(" system_minor_leak_action        : {}".format(entry.get('system_minor_leak_action', 'syslog_only')))
        click.echo(" rack_mgr_leak_policy            : {}".format(entry.get('rack_mgr_leak_policy', 'enabled')))
        rack_critical_action = entry.get('rack_mgr_critical_alert_action', 'syslog_only')
        click.echo(" rack_mgr_critical_alert_action  : {}".format(rack_critical_action))
        rack_minor_action = entry.get('rack_mgr_minor_alert_action', 'syslog_only')
        click.echo(" rack_mgr_minor_alert_action     : {}".format(rack_minor_action))
    except Exception as e:
        click.echo(f"Error: Failed to retrieve leak control policy: {e}", err=True)


@leak.group('rack-manager')
def leak_rack_manager():
    """Show rack-manager leak information"""
    pass


@leak_rack_manager.command('alerts')
def leak_rack_manager_alerts():
    """Show rack-manager alerts"""
    try:
        state_db = _get_state_db()
        keys = state_db.keys(state_db.STATE_DB, f"{RACK_MANAGER_ALERT_TABLE}|*") or []
        header = ['Alert', 'Severity', 'Timestamp']
        rows = []
        for key in sorted(keys):
            alert_name = key.split('|', 1)[1]
            data = state_db.get_all(state_db.STATE_DB, key) or {}
            severity = data.get('severity', data.get('leak', 'N/A'))
            timestamp = data.get('timestamp', 'N/A')
            rows.append((alert_name, severity, timestamp))
        if rows:
            click.echo(tabulate(rows, header, tablefmt='simple'))
        else:
            click.echo("No rack-manager alerts found")
    except Exception as e:
        click.echo(f"Error: Failed to retrieve rack-manager leak alerts: {e}", err=True)


@leak.command('profiles')
def leak_profiles():
    """Show leak sensor profiles"""
    try:
        from utilities_common.db import Db
        db = Db()
        keys = db.cfgdb.get_keys(LEAK_PROFILE_TABLE) or []
        header = ['Sensor-Type', 'Max-Minor-Duration-Sec']
        rows = []
        for sensor_type in sorted(keys):
            entry = db.cfgdb.get_entry(LEAK_PROFILE_TABLE, sensor_type)
            max_dur = entry.get('max_minor_duration_sec', 'N/A')
            rows.append((sensor_type, max_dur))
        if rows:
            click.echo(tabulate(rows, header, tablefmt='simple'))
        else:
            click.echo("No leak profiles found")
    except Exception as e:
        click.echo(f"Error: Failed to retrieve leak sensor profiles: {e}", err=True)


@leak.command('status')
def leak_status():
    """Show leak sensor status"""
    try:
        state_db = _get_state_db()
        keys = state_db.keys(state_db.STATE_DB, f"{LIQUID_COOLING_INFO_TABLE}|*") or []
        header = ['Name', 'Leak', 'Leak-sensor-status', 'leak-sensor-type', 'leak-severity']
        rows = []
        for key in sorted(keys):
            data = state_db.get_all(state_db.STATE_DB, key) or {}
            name = data.get('name', key.split('|', 1)[1])
            leaking = data.get('leaking', 'N/A')
            sensor_status = data.get('leak_sensor_status', 'N/A')
            sensor_type = data.get('type', 'N/A')
            severity = data.get('leak_severity', 'N/A') if leaking.upper() in ('YES', 'TRUE') else 'NA'
            rows.append((name, leaking, sensor_status, sensor_type, severity))
        if rows:
            click.echo(tabulate(rows, header, tablefmt='simple'))
        else:
            click.echo("No leak sensor data found")
    except Exception as e:
        click.echo(f"Error: Failed to retrieve leak sensor status: {e}", err=True)
