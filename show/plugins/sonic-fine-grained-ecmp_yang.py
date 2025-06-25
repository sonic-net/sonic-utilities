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
        str: formatted attribute value.
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
        str: formatted group attributes.
    """

    data = []
    for attr in attrs:
        if entry.get(attr["name"]):
            data.append((attr["name"] + ":", format_attr_value(entry, attr)))
    return tabulate.tabulate(data, tablefmt="plain")


@click.group(name="fg-nhg",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def FG_NHG(db):
    """  [Callable command group] """

    header = [
        "NAME",
        "BUCKET SIZE",
        "MATCH MODE",
        "MAX NEXT HOPS",
        ]

    body = []

    table = db.cfgdb.get_table("FG_NHG")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {'name': 'bucket_size', 'description': 'total hash bucket size desired, recommended value of Lowest Common\
                  Multiple of 1..max-next-hops', 'is-leaf-list': False, 'is-mandatory': True, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'match_mode', 'description': 'The filtering method used to identify when to use Fine Grained vs \
                  regular route handling. \
                    -- nexthop-based filters on nexthop IPs only. \
                    -- route-based filters on both prefix and nexthop IPs. \
                    -- prefix-based filters on prefix only.', 'is-leaf-list': False, 'is-mandatory': True, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'max_next_hops', 'description': 'Applicable only for match_mode = prefix-based. Maximum number \
                  of nexthops that will be\nreceived in route updates for any of the prefixes that match FG_NHG_PREFIX \
                  for this FG_NHG.', 'is-leaf-list': False, 'is-mandatory': True, 'group': ''}
            ),
        ]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


@click.group(name="fg-nhg-prefix",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def FG_NHG_PREFIX(db):
    """  [Callable command group] """

    header = [
        "IP PREFIX",
        "FG NHG"
    ]

    body = []

    table = db.cfgdb.get_table("FG_NHG_PREFIX")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {'name': 'FG_NHG', 'description': 'Fine Grained next-hop group name', 'is-leaf-list': False,
                 'is-mandatory': True, 'group': ''}
            ),
        ]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


@click.group(name="fg-nhg-member",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def FG_NHG_MEMBER(db):
    """  [Callable command group] """

    header = [
        "NEXT HOP IP",
        "FG NHG",
        "BANK",
        "LINK"
    ]

    body = []

    table = db.cfgdb.get_table("FG_NHG_MEMBER")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {'name': 'FG_NHG', 'description': 'Fine Grained next-hop group name', 'is-leaf-list': False,
                 'is-mandatory': True, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'bank', 'description': 'An index which specifies a bank/group in which the \
                  redistribution is performed', 'is-leaf-list': False, 'is-mandatory': True, 'group': ''}
            ),
            format_attr_value(
                entry,
                {'name': 'link', 'description': "Link associated with next-hop-ip, if configured, enables \
                  next-hop withdrawal/addition per link's operational state changes",
                 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
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
    cli_nodes = [FG_NHG, FG_NHG_PREFIX, FG_NHG_MEMBER]
    for cli_node in cli_nodes:
        if cli_node.name in cli.commands:
            raise Exception(f"{cli_node.name} already exists in CLI")
        cli.add_command(cli_node)
