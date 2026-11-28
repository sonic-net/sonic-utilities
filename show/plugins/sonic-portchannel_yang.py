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


@click.group(name="portchannel",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def PORTCHANNEL(db):
    """ Configuration entry for a PortChannel aggregate interface [Callable command group] """

    header = [
"NAME",
"MIN LINKS",
"MODE",
"DESCRIPTION",
"MTU",
"ADMIN STATUS",
"LACP KEY",
"TPID",
"FALLBACK",
"FALLBACK TIMEOUT",
"FAST RATE",
]

    body = []

    table = db.cfgdb.get_table("PORTCHANNEL")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
    format_attr_value(
        entry,
        {'name': 'min_links', 'description': 'Minimum number of active member links required for the PortChannel to be operationally up', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'mode', 'description': 'PortChannel SwitchPort Mode possible values are routed|access|trunk. Default value for mode is routed.', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'description', 'description': 'User-defined description for the PortChannel interface', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'mtu', 'description': 'Maximum transmission unit size in bytes', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'admin_status', 'description': 'Administrative state of the PortChannel interface', 'is-leaf-list': False, 'is-mandatory': True}
    ),
    format_attr_value(
        entry,
        {'name': 'lacp_key', 'description': "LACP aggregation key; 'auto' derives it from the PortChannel name, or specify a value from 1 to 65535", 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'tpid', 'description': 'This leaf describes the possible TPID value that can be configured\nto the specified portchannel if the HW supports TPID configuration. The possible\nvalues are 0x8100, 0x9100, 0x9200, 0x88a8, and 0x88A8', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'fallback', 'description': 'Enable LACP fallback feature', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'fallback_timeout', 'description': 'LACP fallback timeout in seconds; applies only when fallback is enabled.', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'fast_rate', 'description': 'Enable LACP fast rate', 'is-leaf-list': False, 'is-mandatory': False}
    ),
]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


@click.group(name="portchannel-member",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def PORTCHANNEL_MEMBER(db):
    """ Association of a physical port as a member of a PortChannel [Callable command group] """

    header = [
"NAME",
"PORT",
]

    body = []

    table = db.cfgdb.get_table("PORTCHANNEL_MEMBER")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


@click.group(name="portchannel-interface",
             cls=clicommon.AliasedGroup)
def PORTCHANNEL_INTERFACE():
    """ PortChannel interface L3 configuration including VRF binding and IP addressing """

    pass


@PORTCHANNEL_INTERFACE.group(name="portchannel-interface-list",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def PORTCHANNEL_INTERFACE_LIST(db):
    """ L3 configuration entry for a PortChannel interface [Callable command group] """

    header = [
"NAME",
"VRF NAME",
"LOOPBACK ACTION",
"NAT ZONE",
"MPLS",
"IPV6 USE LINK LOCAL ONLY",
"MAC ADDR",
]

    body = []

    table = db.cfgdb.get_table("PORTCHANNEL_INTERFACE")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
    format_attr_value(
        entry,
        {'name': 'vrf_name', 'description': 'VRF instance to which this PortChannel interface is bound', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'loopback_action', 'description': 'Packet action when a packet ingress and gets routed on the same IP interface', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'nat_zone', 'description': 'NAT Zone for the portchannel interface', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'mpls', 'description': 'Enable/disable MPLS routing for the portchannel interface', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'ipv6_use_link_local_only', 'description': 'Enable/Disable IPv6 link local address on portchannel interface', 'is-leaf-list': False, 'is-mandatory': False}
    ),
    format_attr_value(
        entry,
        {'name': 'mac_addr', 'description': 'Assign administrator-provided MAC address to Interface', 'is-leaf-list': False, 'is-mandatory': False}
    ),
]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


@PORTCHANNEL_INTERFACE.group(name="portchannel-interface-ipprefix-list",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def PORTCHANNEL_INTERFACE_IPPREFIX_LIST(db):
    """ IP address prefix assignment for a PortChannel interface [Callable command group] """

    header = [
"NAME",
"IP PREFIX",
]

    body = []

    table = db.cfgdb.get_table("PORTCHANNEL_INTERFACE")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
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
    cli_node = PORTCHANNEL
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(PORTCHANNEL)
    cli_node = PORTCHANNEL_MEMBER
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(PORTCHANNEL_MEMBER)
    cli_node = PORTCHANNEL_INTERFACE
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(PORTCHANNEL_INTERFACE)
