import click
import json
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector
from natsort import natsorted
from tabulate import tabulate

COPP_INIT_CFG_JSON_FILE = "/etc/sonic/copp_cfg.json"

##############################################################################
# CoPP show commands
# show copp configuration
# show copp configuration detailed --trapid <trap_id>
# show copp configuration detailed --group <group>
# ############################################################################


def get_copp_trap_hw_status(trap_id, state_db):
    """Get CoPP Trap operational status"""

    state_db_data = state_db.get_all(state_db.STATE_DB, f"COPP_TRAP_TABLE|{trap_id}")
    hw_status = state_db_data.get("hw_status", "not-installed") \
        if state_db_data else "not-installed"

    return hw_status


def print_single_copp_entry(entry, trap_id=None, group=None):
    """Print single copp entry"""

    if not trap_id:
        click.echo("Trap Id(s).................. {}".format(",".join(entry.get("trap_ids", {}))))
    else:
        click.echo("Trap Group.................. {}".format(group))

    click.echo("Trap Action................. {}".format(entry.get("trap_action", "")))
    click.echo("Trap Priority............... {}".format(entry.get("trap_priority", "")))
    click.echo("Queue....................... {}".format(entry.get("queue", "")))
    click.echo("CBS......................... {}".format(entry.get("cbs", "")))
    click.echo("CIR......................... {}".format(entry.get("cir", "")))
    click.echo("Meter Type.................. {}".format(entry.get("meter_type", "")))
    mode = entry.get("mode", "")
    click.echo("Mode........................ {}".format(mode))

    if mode in ['sr_tcm', 'tr_tcm']:
        click.echo("Yellow Action............... {}".format(entry.get("yellow_action", "forward")))

    click.echo("Green Action................ {}".format(entry.get("green_action", "forward")))
    click.echo("Red Action.................. {}".format(entry.get("red_action", "")))

    if trap_id:
        state_db = SonicV2Connector()
        state_db.connect(state_db.STATE_DB)
        hw_status = get_copp_trap_hw_status(trap_id, state_db)
        click.echo("HW Status................... {}".format(hw_status))


def merge_copp_entries(config_db, json_data, db_keys, table_name, input_key=None, is_group=False):
    """
    Merge CoPP entries (groups or traps) from CONFIG_DB and copp_cfg.json.

    Args:
        config_db: CONFIG_DB connector.
        json_data: JSON data from copp_cfg.json.
        db_keys: List of keys from CONFIG_DB.
        table_name: Key in the JSON data (e.g., "COPP_GROUP" or "COPP_TRAP").
        input_key: Specific key to filter (e.g., input_group or input_trap).
        is_group: Boolean indicating whether the entry is a group (True) or a trap (False).

    Returns:
        A dictionary of merged entries.
    """

    merged_entries = {}
    json_entries = json_data.get(table_name, {})

    # Merge entries from copp_cfg.json
    for json_entry, json_entry_data in json_entries.items():

        # Strip leading and trailing spaces from the entry key and its nested fields
        json_entry = json_entry.strip()
        json_entry_data = {k.strip(): v.strip() for k, v in json_entry_data.items()}

        # For groups, filter by input_key (input_group)
        if is_group and input_key and json_entry != input_key:
            continue

        # For traps, skip if input_key (input_trap) is not in trap_ids
        if not is_group and input_key:
            trap_ids = json_entry_data.get("trap_ids", "").split(",")
            if not any(trap_id.strip() == input_key for trap_id in trap_ids):
                continue

        # Ignore entries with "NULL" keys
        if "NULL" in json_entry_data:
            continue

        merged_entries[json_entry] = json_entry_data

        if json_entry in db_keys:
            db_entry = config_db.get_all(config_db.CONFIG_DB, f'{table_name}|{json_entry}')
            if "NULL" in db_entry:
                del merged_entries[json_entry]
                continue
            for json_field in json_entry_data:
                if json_field in db_entry:
                    merged_entries[json_entry][json_field] = db_entry[json_field]

            # Add keys from db_entry that are not in json_entry_data
            merged_entries[json_entry].update({db_field: db_entry[db_field]
                                               for db_field in db_entry if db_field not in merged_entries[json_entry]})

    # Include entries from CONFIG_DB that are not in copp_cfg.json
    for db_entry_key in db_keys:
        # For groups, filter by input_key (input_group)
        if is_group and input_key and db_entry_key != input_key:
            continue

        # For traps, skip if input_key (input_trap) is not in trap_ids
        if not is_group and input_key:
            db_entry = config_db.get_all(config_db.CONFIG_DB, f'{table_name}|{db_entry_key}')
            if input_key not in db_entry.get("trap_ids", "").split(","):
                continue

        if db_entry_key not in merged_entries:
            db_entry = config_db.get_all(config_db.CONFIG_DB, f'{table_name}|{db_entry_key}')
            if "NULL" not in db_entry:
                merged_entries[db_entry_key] = db_entry

    return merged_entries


def merge_copp_config(config_db, input_trap=None, input_group=None):
    """Merge copp configuration"""

    copp_group_table = f"COPP_GROUP|{input_group}" if input_group else "COPP_GROUP|*"
    copp_trap_table = "COPP_TRAP|*"

    cfg_db_grp_keys = config_db.keys(config_db.CONFIG_DB, copp_group_table) or []
    cfg_db_trap_keys = config_db.keys(config_db.CONFIG_DB, copp_trap_table) or []

    # Remove 'COPP_GROUP|' and 'COPP_TRAP|' from the keys
    cfg_db_grp_keys = [key.replace('COPP_GROUP|', '') for key in cfg_db_grp_keys]
    cfg_db_trap_keys = [key.replace('COPP_TRAP|', '') for key in cfg_db_trap_keys]

    json_data = {}
    try:
        # Read the JSON data from the file
        with open(COPP_INIT_CFG_JSON_FILE, 'r') as file:
            json_data = json.load(file)
    except FileNotFoundError:
        click.echo(f"WARNING: CoPP CFG file: '{COPP_INIT_CFG_JSON_FILE}' not found.")

    # Merge CoPP groups and traps
    merged_group = merge_copp_entries(config_db,
                                      json_data,
                                      cfg_db_grp_keys,
                                      "COPP_GROUP",
                                      input_group,
                                      is_group=True)
    merged_traps = merge_copp_entries(config_db,
                                      json_data,
                                      cfg_db_trap_keys,
                                      "COPP_TRAP",
                                      input_trap,
                                      is_group=False)

    # Merge trap_ids from merged_traps to merged_group
    for trap_key, trap_data in merged_traps.items():
        trap_ids_list = trap_data.get("trap_ids", "").split(",")
        trap_ids_list = [trap_id.strip() for trap_id in trap_ids_list if trap_id.strip()]
        trap_group = trap_data.get("trap_group", "")

        # Make sure the trap_group exists in merged_group
        if trap_group not in merged_group:
            continue

        # Add trap_ids to merged_group[trap_group]
        merged_group[trap_group].setdefault("trap_ids", []).extend(trap_ids_list)

    return merged_group, merged_traps


@click.group(cls=clicommon.AliasedGroup)
@clicommon.pass_db
def copp(_db):
    """Show copp configuration"""
    pass


@copp.group(invoke_without_command=True)
@click.pass_context
@clicommon.pass_db
def configuration(_db, ctx):
    """Show copp configuration"""

    if ctx.invoked_subcommand is not None:
        return

    header = ["TrapId", "Trap Group", "Action", "CBS", "CIR", "Meter Type", "Mode", "HW Status"]

    config_db = _db.cfgdb

    merged_group, merged_traps = merge_copp_config(config_db)
    if not merged_group or not merged_traps:
        return

    state_db = SonicV2Connector()
    state_db.connect(state_db.STATE_DB)

    # Extract all trap_ids and trap_group from merged_traps
    rows = []
    for trap, trap_data in merged_traps.items():
        trap_ids = trap_data.get("trap_ids", "").split(",")
        trap_group = trap_data.get("trap_group", "")
        action = merged_group[trap_group].get("trap_action", "")
        cbs = merged_group[trap_group].get("cbs", "")
        cir = merged_group[trap_group].get("cir", "")
        meter_type = merged_group[trap_group].get("meter_type", "")
        mode = merged_group[trap_group].get("mode", "")

        for trap_id in trap_ids:
            trap_id = trap_id.strip()
            hw_status = get_copp_trap_hw_status(trap_id, state_db)
            rows.append([trap_id, trap_group, action, cbs, cir, meter_type, mode, hw_status])

    body = natsorted(rows)
    click.echo(tabulate(body, header))


@configuration.command()
@click.option('-t', '--trapid', help="Trap id text")
@click.option('-g', '--group', help="Trap group text")
@clicommon.pass_db
def detailed(_db, trapid, group):
    """Show copp configuration detailed"""

    # Validation to ensure at least one argument is provided
    if not trapid and not group:
        click.echo("Either trapid or group must be provided.")
        return

    if trapid and group:
        click.echo("Either trapid or group must be provided, but not both.")
        return

    config_db = _db.cfgdb
    merged_groups, merged_traps = merge_copp_config(config_db, trapid, group)
    if not merged_groups or not merged_traps:
        return

    if group:
        copp_group = merged_groups.get(group, {})
    else:
        for _, trap_data in merged_traps.items():
            trap_ids_list = trap_data.get("trap_ids", "").split(",")
            if trapid in trap_ids_list:
                group = trap_data.get("trap_group")
                break

        copp_group = merged_groups.get(group, {})

    if len(copp_group) == 0:
        return

    print_single_copp_entry(copp_group, trapid, group)
