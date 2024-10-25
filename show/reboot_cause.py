import json
import os
import sys

import click
from tabulate import tabulate
from swsscommon.swsscommon import SonicV2Connector
from sonic_py_common import device_info
import utilities_common.cli as clicommon


PREVIOUS_REBOOT_CAUSE_FILE_PATH = "/host/reboot-cause/previous-reboot-cause.json"

def read_reboot_cause_file():
    reboot_cause_dict = {}

    if os.path.exists(PREVIOUS_REBOOT_CAUSE_FILE_PATH):
        with open(PREVIOUS_REBOOT_CAUSE_FILE_PATH) as prev_reboot_cause_file:
            try:
                reboot_cause_dict = json.load(prev_reboot_cause_file)
            except json.JSONDecodeError as err:
                click.echo("Failed to load JSON file '{}'!".format(PREVIOUS_REBOOT_CAUSE_FILE_PATH), err=True)

    return reboot_cause_dict


# Function to fetch reboot cause data from database
def fetch_data_from_db(module_name, fetch_history=False):
    if module_name is None:
        prefix = 'REBOOT_CAUSE|2'
    elif "DPU" in module_name:
        prefix = 'REBOOT_CAUSE|' + module_name
    else:
        prefix = 'REBOOT_CAUSE|'

    try:
        rdb = SonicV2Connector(host='127.0.0.1')
        rdb.connect(rdb.STATE_DB, False)   # Make one attempt only
        table_keys = rdb.keys(rdb.STATE_DB, prefix+'*')
    except Exception:
        return []

    if table_keys is not None:
        table_keys.sort(reverse=True)

    table = []
    d = []
    for tk in table_keys:
        r = []
        append = False
        entry = rdb.get_all(rdb.STATE_DB, tk)

        if module_name is not None:
            if 'device' in entry:
                if module_name != entry['device'] and module_name != "all":
                    continue
                if entry['device'] in d and not history:
                    append = False
                    continue
                elif not entry['device'] in d or entry['device'] in d and history:
                    if not entry['device'] in d:
                        d.append(entry['device'])
                        append = True
            r.append(entry['device'] if 'device' in entry else "SWITCH")

        name = tk.split('|')[-1]
        if "|" in name:
            name = name[:name.rindex('|')] + ''
        r.append(name)
        r.append(entry['cause'] if 'cause' in entry else "")
        r.append(entry['time'] if 'time' in entry else "")
        r.append(entry['user'] if 'user' in entry else "")
        if append and not fetch_history:
            table.append(r)
        elif fetch_history:
            r.append(entry['comment'] if 'comment' in entry else "")
            if module_name is None or module_name == 'all' or module_name.startswith('SWITCH') or \
               'device' in entry and module_name == entry['device']:
                table.append(r)

    return table


# Wrapper-function to fetch reboot cause data from database
def fetch_reboot_cause_from_db(module_name):
    table = []
    r = []

    # Read the previous reboot cause
    reboot_cause_dict = read_reboot_cause_file()
    reboot_gen_time = reboot_cause_dict.get("gen_time", "N/A")
    reboot_cause = reboot_cause_dict.get("cause", "Unknown")
    reboot_time = reboot_cause_dict.get("time", "N/A")
    reboot_user = reboot_cause_dict.get("user", "N/A")

    r.append("SWITCH")
    r.append(reboot_gen_time if reboot_gen_time else "")
    r.append(reboot_cause if reboot_cause else "")
    r.append(reboot_time if reboot_time else "")
    r.append(reboot_user if reboot_user else "")
    table.append(r)

    table += fetch_data_from_db(module_name, fetch_history=False)
    return table


# Function to fetch reboot cause history data from database
def fetch_reboot_cause_history_from_db(module_name):
    return fetch_data_from_db(module_name, fetch_history=True)

#
# 'reboot-cause' group ("show reboot-cause")
#
@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def reboot_cause(ctx):
    """Show cause of most recent reboot"""
    if ctx.invoked_subcommand is None:
        reboot_cause_str = ""

        # Read the previous reboot cause
        reboot_cause_dict = read_reboot_cause_file()

        reboot_cause = reboot_cause_dict.get("cause", "Unknown")
        reboot_user = reboot_cause_dict.get("user", "N/A")
        reboot_time = reboot_cause_dict.get("time", "N/A")

        if reboot_user != "N/A":
            reboot_cause_str = "User issued '{}' command".format(reboot_cause)
        else:
            reboot_cause_str = reboot_cause

        if reboot_user != "N/A" or reboot_time != "N/A":
            reboot_cause_str += " ["

            if reboot_user != "N/A":
                reboot_cause_str += "User: {}".format(reboot_user)
                if reboot_time != "N/A":
                    reboot_cause_str += ", "

            if reboot_time != "N/A":
                reboot_cause_str += "Time: {}".format(reboot_time)

            reboot_cause_str += "]"

        click.echo(reboot_cause_str)


def is_smartswitch():
    return hasattr(device_info, 'is_smartswitch') and device_info.is_smartswitch()


# 'all' command within 'reboot-cause'
@reboot_cause.command()
def all():
    if not is_smartswitch():
        return
    """Show cause of most recent reboot"""
    reboot_cause_data = fetch_reboot_cause_from_db("all")
    header = ['Device', 'Name', 'Cause', 'Time', 'User']
    if reboot_cause_data:
        click.echo(tabulate(reboot_cause_data, header, numalign="left"))


# utility to get options
def get_all_dpus():
    dpu_list = []

    if not is_smartswitch():
        return dpu_list

    # Load platform.json
    platform_info = device_info.get_platform_info()
    platform = platform_info['platform']
    platform_file = os.path.join("/usr/share/sonic/device", platform, "platform.json")
    try:
        with open(platform_file, 'r') as platform_json:
            config_data = json.load(platform_json)

            # Extract DPUs dictionary
            dpus = config_data.get("DPUS", {})

            # Convert DPU names to uppercase and append to the list
            dpu_list = [dpu.upper() for dpu in dpus.keys()]

    except FileNotFoundError:
        print("Error: platform.json not found")
    except json.JSONDecodeError:
        print("Error: Failed to parse platform.json")

    # Add 'all' and 'SWITCH' to the list
    dpu_list += ['all', 'SWITCH']

    return dpu_list


# 'history' command within 'reboot-cause'
@reboot_cause.command()
@click.argument(
        'module_name',
        required=False,
        type=click.Choice(get_all_dpus(), case_sensitive=False) if is_smartswitch() else None
        )
def history(module_name=None):
    """Show history of reboot-cause"""
    if not is_smartswitch() and module_name:
        return
    reboot_cause_history = fetch_reboot_cause_history_from_db(module_name)
    if is_smartswitch() and module_name:
        header = ['Device', 'Name', 'Cause', 'Time', 'User', 'Comment']
    else:
        header = ['Name', 'Cause', 'Time', 'User', 'Comment']

    if reboot_cause_history:
        click.echo(tabulate(reboot_cause_history, header, numalign="left"))
