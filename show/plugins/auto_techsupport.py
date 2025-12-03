"""
Auto-generated show CLI plugin.
Manually Edited to add show cli for "show auto_techsupport history"
"""

import click
import tabulate
import natsort
import utilities_common.cli as clicommon


def format_attr_value(entry, attr):
    """ Helper that formats attribute to be presented in the table output.

    Args:
        entry (Dict[str, str]): CONFIG DB entry configuration.
        attr (Dict): Attribute metadata.

    Returns:
        str: fomatted attribute value.
    """

    if attr["is-leaf-list"]:
        return "\n".join(entry.get(attr["name"], []))
    return entry.get(attr["name"], "N/A")


def format_group_value(entry, attrs):
    """ Helper that formats grouped attribute to be presented in the table output.

    Args:
        entry (Dict[str, str]): CONFIG DB entry configuration.
        attrs (List[Dict]): Attributes metadata that belongs to the same group.

    Returns:
        str: fomatted group attributes.
    """

    data = []
    for attr in attrs:
        if entry.get(attr["name"]):
            data.append((attr["name"] + ":", format_attr_value(entry, attr)))
    return tabulate.tabulate(data, tablefmt="plain")


@click.group(name="auto-techsupport",
             cls=clicommon.AliasedGroup)
def AUTO_TECHSUPPORT():
    """ AUTO_TECHSUPPORT part of config_db.json """

    pass


@AUTO_TECHSUPPORT.command(name="global")
@clicommon.pass_db
def AUTO_TECHSUPPORT_GLOBAL(db):
    """  """

    header = [
        "STATE",
        "RATE LIMIT INTERVAL (sec)",
        "MAX TECHSUPPORT LIMIT (%)",
        "MAX CORE LIMIT (%)",
        "AVAILABLE MEM THRESHOLD (%)",
        "MIN AVAILABLE MEM (Kb)",
        "SINCE",
    ]

    body = []
    table = db.cfgdb.get_table("AUTO_TECHSUPPORT")
    entry = table.get("GLOBAL", {})
    row = [
        format_attr_value(
            entry,
            {'name': 'state', 'description': 'Knob to make techsupport invocation event-driven based on core-dump generation', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'rate_limit_interval', 'description': 'Minimum time in seconds between two successive techsupport invocations. Configure 0 to explicitly disable', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'max_techsupport_limit', 'description': 'Max Limit in percentage for the cummulative size of ts dumps. No cleanup is performed if the value isn\'t configured or is 0.0', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'max_core_limit', 'description': 'Max Limit in percentage for the cummulative size of core dumps. No cleanup is performed if the value isn\'t congiured or is 0.0', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'available_mem_threshold', 'description': 'Memory threshold; 0 to disable techsupport invocation on memory usage threshold crossing.', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'min_available_mem', 'description': 'Minimum Free memory (in MB) that should be available for the techsupport execution to start', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'since', 'description': "Only collect the logs & core-dumps generated since the time provided. A default value of '2 days ago' is used if this value is not set explicitly or a non-valid string is provided", 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
    ]

    body.append(row)
    click.echo(tabulate.tabulate(body, header, numalign="left"))


@AUTO_TECHSUPPORT.command(name="history")
@clicommon.pass_db
def AUTO_TECHSUPPORT_history(db):
    keys = db.db.keys("STATE_DB", "AUTO_TECHSUPPORT_DUMP_INFO|*")
    header = ["TECHSUPPORT DUMP", "TRIGGERED BY", "EVENT TYPE", "CORE DUMP"]
    body = []
    for key in keys:
        dump = key.split("|")[-1]
        fv_pairs = db.db.get_all("STATE_DB", key)
        core_dump = fv_pairs.get("core_dump", "")
        container = fv_pairs.get("container_name", "")
        event_type = fv_pairs.get("event_type", "")
        body.append([dump, container, event_type, core_dump])
    click.echo(tabulate.tabulate(body, header, numalign="left"))


@click.group(name="auto-techsupport-feature",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def AUTO_TECHSUPPORT_FEATURE(db):
    """  [Callable command group] """

    header = [
        "FEATURE NAME",
        "STATE",
        "RATE LIMIT INTERVAL (sec)",
        "AVAILABLE MEM THRESHOLD (%)",
    ]

    body = []

    table = db.cfgdb.get_table("AUTO_TECHSUPPORT_FEATURE")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {'name': 'state', 'description': 'Enable auto techsupport invocation on the processes running inside this feature', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'rate_limit_interval', 'description': 'Rate limit interval for the corresponding feature. Configure 0 to explicitly disable', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'available_mem_threshold', 'description': 'Memory threshold; 0 to disable techsupport invocation on memory usage threshold crossing.', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
            ),
        ]
        body.append(row)
    click.echo(tabulate.tabulate(body, header, numalign="left"))


def register(cli):
    cli_node = AUTO_TECHSUPPORT
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(AUTO_TECHSUPPORT)
    cli_node = AUTO_TECHSUPPORT_FEATURE
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(AUTO_TECHSUPPORT_FEATURE)
    cli_node = AUTO_TECHSUPPORT_history
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(AUTO_TECHSUPPORT_history)
