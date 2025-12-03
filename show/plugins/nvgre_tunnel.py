"""
Auto-generated show CLI plugin for NVGRE Tunnel feature.
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
    return tabulate.tabulate(data, tablefmt="plain", numalign="left")


@click.group(
    name="nvgre-tunnel",
    cls=clicommon.AliasedGroup,
    invoke_without_command=True)
@clicommon.pass_db
def NVGRE_TUNNEL(db):
    """  [Callable command group] """

    header = [ "TUNNEL NAME", "SRC IP" ]

    body = []

    table = db.cfgdb.get_table("NVGRE_TUNNEL")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

            row = [*key] + [
                format_attr_value(
                    entry,
                    {
                        'name': 'src_ip',
                        'description': 'Source IP address',
                        'is-leaf-list': False,
                        'is-mandatory': True,
                        'group': ''
                    }
                )
            ]

        body.append(row)

    click.echo(tabulate.tabulate(body, header, numalign="left"))


@click.group(
    name="nvgre-tunnel-map",
    cls=clicommon.AliasedGroup,
    invoke_without_command=True)
@clicommon.pass_db
def NVGRE_TUNNEL_MAP(db):
    """  [Callable command group] """

    header = [
        "TUNNEL NAME",
        "TUNNEL MAP NAME",
        "VLAN ID",
        "VSID"
    ]

    body = []

    table = db.cfgdb.get_table("NVGRE_TUNNEL_MAP")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {
                    'name': 'vlan_id',
                    'description': 'VLAN identifier',
                    'is-leaf-list': False,
                    'is-mandatory': True,
                    'group': ''
                }
            ),
            format_attr_value(
                entry,
                {
                    'name': 'vsid',
                    'description': 'Virtual Subnet Identifier',
                    'is-leaf-list': False,
                    'is-mandatory': True,
                    'group': ''
                }
            )
        ]

        body.append(row)

    click.echo(tabulate.tabulate(body, header, numalign="left"))


def register(cli):
    """ Register new CLI nodes in root CLI.

    Args:
        cli (click.core.Command): Root CLI node.
    Raises:
        Exception: when root CLI already has a command
                   we are trying to register.
    """
    cli_node = NVGRE_TUNNEL
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(NVGRE_TUNNEL)
    cli_node = NVGRE_TUNNEL_MAP
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(NVGRE_TUNNEL_MAP)

