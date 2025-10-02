#!/usr/sbin/env python

import click
import time
import re
import subprocess
import utilities_common.cli as clicommon
from utilities_common.chassis import is_smartswitch, get_all_dpus
from datetime import datetime, timedelta

TIMEOUT_SECS = 10
TRANSITION_TIMEOUT = timedelta(seconds=240)  # 4 minutes


class StateDBHelper:
    def __init__(self, sonic_db):
        self.db = sonic_db

    def get_entry(self, table, key):
        """Fetch all fields from table|key."""
        redis_key = f"{table}|{key}"
        return self.db.get_all("STATE_DB", redis_key) or {}

    def set_entry(self, table, key, entry):
        """Set multiple fields to table|key."""
        redis_key = f"{table}|{key}"
        for field, value in entry.items():
            self.db.set("STATE_DB", redis_key, field, value)

#
# 'chassis_modules' group ('config chassis_modules ...')
#
@click.group(cls=clicommon.AliasedGroup)
def chassis():
    """Configure chassis commands group"""
    pass

@chassis.group()
def modules():
    """Configure chassis modules"""
    pass


def ensure_statedb_connected(db):
    if not hasattr(db, 'statedb'):
        chassisdb = db.db
        chassisdb.connect("STATE_DB")
        db.statedb = StateDBHelper(chassisdb)

def get_config_module_state(db, chassis_module_name):
    config_db = db.cfgdb
    fvs = config_db.get_entry('CHASSIS_MODULE', chassis_module_name)
    if not fvs:
        if is_smartswitch():
            return 'down'
        else:
            return 'up'
    else:
        return fvs['admin_status']


def get_state_transition_in_progress(db, chassis_module_name):
    ensure_statedb_connected(db)
    fvs = db.statedb.get_entry('CHASSIS_MODULE_TABLE', chassis_module_name)
    value = fvs.get('state_transition_in_progress', 'False') if fvs else 'False'
    return value


def set_state_transition_in_progress(db, chassis_module_name, value):
    ensure_statedb_connected(db)
    state_db = db.statedb
    entry = state_db.get_entry('CHASSIS_MODULE_TABLE', chassis_module_name) or {}
    entry['state_transition_in_progress'] = value
    if value == 'True':
        entry['transition_start_time'] = datetime.utcnow().isoformat()
    else:
        entry.pop('transition_start_time', None)
    state_db.set_entry('CHASSIS_MODULE_TABLE', chassis_module_name, entry)


def is_transition_timed_out(db, chassis_module_name):
    ensure_statedb_connected(db)
    state_db = db.statedb
    fvs = state_db.get_entry('CHASSIS_MODULE_TABLE', chassis_module_name)
    if not fvs:
        return False
    start_time_str = fvs.get('transition_start_time')
    if not start_time_str:
        return False
    try:
        start_time = datetime.fromisoformat(start_time_str)
    except ValueError:
        return False
    return datetime.utcnow() - start_time > TRANSITION_TIMEOUT

#
# Name: check_config_module_state_with_timeout
# return: True: timeout, False: not timeout
#
def check_config_module_state_with_timeout(ctx, db, chassis_module_name, state):
    counter = 0
    while get_config_module_state(db, chassis_module_name) != state:
        time.sleep(1)
        counter += 1
        if counter >= TIMEOUT_SECS:
            ctx.fail("get_config_module_state {} timeout".format(chassis_module_name))
            return True
    return False


def get_asic_list_from_db(chassisdb, chassis_module_name):
    asic_list = []
    asics_keys_list = chassisdb.keys("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE*")
    for asic_key in asics_keys_list:
        name = chassisdb.get("CHASSIS_STATE_DB", asic_key, "name")
        if name == chassis_module_name:
            asic_id = int(re.search(r"(\d+)$", asic_key).group())
            asic_list.append(asic_id)
    return asic_list


#
# Syntax: fabric_module_set_admin_status <chassis_module_name> <'up'/'down'>
#
def fabric_module_set_admin_status(db, chassis_module_name, state):
    chassisdb = db.db
    chassisdb.connect("CHASSIS_STATE_DB")
    asic_list = get_asic_list_from_db(chassisdb, chassis_module_name)

    if len(asic_list) == 0:
        return

    if state == "down":
        for asic in asic_list:
            click.echo("Stop swss@{} and peer services".format(asic))
            clicommon.run_command(['sudo', 'systemctl', 'stop', 'swss@{}.service'.format(asic)])

        is_active = subprocess.call(["systemctl", "is-active", "--quiet", "swss@{}.service".format(asic)])

        if is_active == 0:  # zero active,  non-zero, inactive
            click.echo("Stop swss@{} and peer services failed".format(asic))
            return

        click.echo("Delete related CAHSSIS_FABRIC_ASIC_TABLE entries")

        for asic in asic_list:
            chassisdb.delete("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic" + str(asic))

        # Start the services in case of the users just execute issue command "systemctl stop swss@/syncd@"
        # without bring down the hardware
        for asic in asic_list:
            # To address systemd service restart limit by resetting the count
            clicommon.run_command(['sudo', 'systemctl', 'reset-failed', 'swss@{}.service'.format(asic)])
            click.echo("Start swss@{} and peer services".format(asic))
            clicommon.run_command(['sudo', 'systemctl', 'start', 'swss@{}.service'.format(asic)])
    elif state == "up":
        for asic in asic_list:
            click.echo("Start swss@{} and peer services".format(asic))
            clicommon.run_command(['sudo', 'systemctl', 'start', 'swss@{}.service'.format(asic)])

#
# 'shutdown' subcommand ('config chassis_modules shutdown ...')
#
@modules.command('shutdown')
@clicommon.pass_db
@click.argument('chassis_module_name',
                metavar='<module_name>',
                required=True,
                type=click.Choice(get_all_dpus(), case_sensitive=False) if is_smartswitch() else str
                )
def shutdown_chassis_module(db, chassis_module_name):
    """Chassis-module shutdown of module"""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    if not chassis_module_name.startswith(("SUPERVISOR", "LINE-CARD", "FABRIC-CARD", "DPU")):
        ctx.fail("'module_name' has to begin with 'SUPERVISOR', 'LINE-CARD', 'FABRIC-CARD', or 'DPU'")

    if get_config_module_state(db, chassis_module_name) == 'down':
        click.echo(f"Module {chassis_module_name} is already in down state")
        return

    if is_smartswitch():
        if get_state_transition_in_progress(db, chassis_module_name) == 'True':
            if is_transition_timed_out(db, chassis_module_name):
                set_state_transition_in_progress(db, chassis_module_name, 'False')
                click.echo(f"Previous transition for module {chassis_module_name} timed out. Proceeding with shutdown.")
            else:
                click.echo(f"Module {chassis_module_name} state transition is already in progress")
                return
        else:
            set_state_transition_in_progress(db, chassis_module_name, 'True')

        click.echo(f"Shutting down chassis module {chassis_module_name}")
        fvs = {
            'admin_status': 'down',
        }
        config_db.set_entry('CHASSIS_MODULE', chassis_module_name, fvs)
    else:
        click.echo(f"Shutting down chassis module {chassis_module_name}")
        config_db.set_entry('CHASSIS_MODULE', chassis_module_name, {'admin_status': 'down'})

    if chassis_module_name.startswith("FABRIC-CARD"):
        if not check_config_module_state_with_timeout(ctx, db, chassis_module_name, 'down'):
            fabric_module_set_admin_status(db, chassis_module_name, 'down')

#
# 'startup' subcommand ('config chassis_modules startup ...')
#
@modules.command('startup')
@clicommon.pass_db
@click.argument('chassis_module_name',
                metavar='<module_name>',
                required=True,
                type=click.Choice(get_all_dpus(), case_sensitive=False) if is_smartswitch() else str
                )
def startup_chassis_module(db, chassis_module_name):
    """Chassis-module startup of module"""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    if not chassis_module_name.startswith(("SUPERVISOR", "LINE-CARD", "FABRIC-CARD", "DPU")):
        ctx.fail("'module_name' has to begin with 'SUPERVISOR', 'LINE-CARD', 'FABRIC-CARD', or 'DPU'")
        return

    if get_config_module_state(db, chassis_module_name) == 'up':
        click.echo(f"Module {chassis_module_name} is already set to up state")
        return

    if is_smartswitch():
        if get_state_transition_in_progress(db, chassis_module_name) == 'True':
            if is_transition_timed_out(db, chassis_module_name):
                set_state_transition_in_progress(db, chassis_module_name, 'False')
                click.echo(f"Previous transition for module {chassis_module_name} timed out. Proceeding with startup.")
            else:
                click.echo(f"Module {chassis_module_name} state transition is already in progress")
                return
        else:
            set_state_transition_in_progress(db, chassis_module_name, 'True')

        click.echo(f"Starting up chassis module {chassis_module_name}")
        fvs = {
            'admin_status': 'up',
        }
        config_db.set_entry('CHASSIS_MODULE', chassis_module_name, fvs)
    else:
        click.echo(f"Starting up chassis module {chassis_module_name}")
        config_db.set_entry('CHASSIS_MODULE', chassis_module_name, None)

    if chassis_module_name.startswith("FABRIC-CARD"):
        if not check_config_module_state_with_timeout(ctx, db, chassis_module_name, 'up'):
            fabric_module_set_admin_status(db, chassis_module_name, 'up')
