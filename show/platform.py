import os
import subprocess
import sys

import click
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

    keys = ["serial", "model", "revision"]

    def try_get(platform, attr, fallback):
        try:
            if platform["chassis"] is None:
                import sonic_platform
                platform["chassis"] = sonic_platform.platform.Platform().get_chassis()
            return getattr(platform["chassis"], "get_{}".format(attr))()
        except Exception:
            return 'N/A'

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
def temperature():
    """Show device temperature information"""
    cmd = ['tempershow']
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
