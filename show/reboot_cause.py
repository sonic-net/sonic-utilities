import json
import os
import sys

import click
from tabulate import tabulate
from swsscommon.swsscommon import SonicV2Connector
import utilities_common.cli as clicommon
from utilities_common.chassis import is_smartswitch, get_all_dpu_options

CHASSIS_SERVER_PORT = 6380

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
def fetch_data_from_db(module_name, fetch_history=False, use_chassis_db=False):
    if module_name is None:
        prefix = 'REBOOT_CAUSE|2'
    elif "DPU" in module_name:
        prefix = 'REBOOT_CAUSE|' + module_name
    else:
        prefix = 'REBOOT_CAUSE|'

    try:
        if use_chassis_db:
            rdb = SonicV2Connector(host='redis_chassis.server', port=CHASSIS_SERVER_PORT)
            rdb.connect(rdb.CHASSIS_STATE_DB)
            table_keys = rdb.keys(rdb.CHASSIS_STATE_DB, prefix+'*')
        else:
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
        if use_chassis_db:
            entry = rdb.get_all(rdb.CHASSIS_STATE_DB, tk)
        else:
            entry = rdb.get_all(rdb.STATE_DB, tk)

        if module_name is not None:
            if 'device' in entry:
                if module_name != entry['device'] and module_name != "all":
                    continue
                if entry['device'] in d and not fetch_history:
                    append = False
                    continue
                elif entry['device'] not in d or (entry['device'] in d and fetch_history):
                    if entry['device'] not in d:
                        d.append(entry['device'])
                        append = True
                r.append(entry['device'])
            elif "DPU" in tk:
                # Extract the module name after "REBOOT_CAUSE|"
                r.append(tk.split('|')[1])
            else:
                r.append("NPU")

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
            if module_name is None or module_name == 'all' or \
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

    r.append("NPU")
    r.append(reboot_gen_time if reboot_gen_time else "")
    r.append(reboot_cause if reboot_cause else "")
    r.append(reboot_time if reboot_time else "")
    r.append(reboot_user if reboot_user else "")
    table.append(r)

    table += fetch_data_from_db(module_name, fetch_history=False, use_chassis_db=True)
    return table


# Function to fetch reboot cause history data from database REBOOT_CAUSE table
def fetch_reboot_cause_history_from_db(module_name):
    if module_name == "all":
        # Combine data from both Redis containers for "all" modules
        data_switch = fetch_data_from_db(module_name, fetch_history=True, use_chassis_db=False)
        data_dpu = fetch_data_from_db(module_name, fetch_history=True, use_chassis_db=True)
        return data_switch + data_dpu
    elif module_name is None:
        return fetch_data_from_db(module_name, fetch_history=True, use_chassis_db=False)
    else:
        return fetch_data_from_db(module_name, fetch_history=True, use_chassis_db=True)

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


# 'history' command within 'reboot-cause'
@reboot_cause.command()
@click.argument(
        'module_name',
        required=False,
        type=click.Choice(get_all_dpu_options(), case_sensitive=False) if is_smartswitch() else None
        )
def history(module_name=None):
    """Show history of reboot-cause"""
    if not is_smartswitch() and module_name:
        click.echo("module option is supported only for smartswitch platform")
        return
    reboot_cause_history = fetch_reboot_cause_history_from_db(module_name)
    if is_smartswitch() and module_name:
        header = ['Device', 'Name', 'Cause', 'Time', 'User', 'Comment']
    else:
        header = ['Name', 'Cause', 'Time', 'User', 'Comment']

    if reboot_cause_history:
        click.echo(tabulate(reboot_cause_history, header, numalign="left"))
