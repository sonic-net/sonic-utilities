"""
Auto-generated show CLI plugin.
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


@click.group(name="dhcpv4-relay",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def DHCPV4_RELAY(db):
    """  [Callable command group] """

    header = [
        "NAME",
        "SERVER VRF",
        "SOURCE INTERFACE",
        "LINK SELECTION",
        "VRF SELECTION",
        "SERVER ID OVERRIDE",
        "AGENT RELAY MODE",
        "MAX HOP COUNT",
        "DHCPV4 SERVERS",
        ]

    body = []

    table = db.cfgdb.get_table("DHCPV4_RELAY")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {'name': 'server_vrf', 'description': 'Server VRF', 'is-leaf-list': False,
                 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'source_interface', 'description': 'Used to determine the source IP address of the \
                  relayed packet', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'link_selection', 'description': 'Enable link selection', 'is-leaf-list': False,
                 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'vrf_selection', 'description': 'Enable VRF selection', 'is-leaf-list': False,
                 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'server_id_override', 'description': 'Enable server id override', 'is-leaf-list': False,
                 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'agent_relay_mode', 'description': 'How to forward packets that already have a relay option',
                 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'max_hop_count', 'description': 'Maximum hop count for relayed packets', 'is-leaf-list': False,
                 'is-mandatory': False, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'dhcpv4_servers', 'description': 'Server IPv4 address list', 'is-leaf-list': True,
                 'is-mandatory': False, 'group': ''}
            ),
        ]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


def register(cli):
    """ Register new CLI nodes in root CLI.

    Args:
        cli (click.core.Command): Root CLI node.
    Raises:
        Exception: when root CLI already has a command
                   we are trying to register.
    """
    cli_node = DHCPV4_RELAY
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(DHCPV4_RELAY)
