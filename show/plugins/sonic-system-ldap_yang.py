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


@click.group(name="ldap-server",
             cls=clicommon.AliasedGroup,
             invoke_without_command=True)
@clicommon.pass_db
def LDAP_SERVER(db):
    """  [Callable command group] """

    header = ["HOSTNAME", "PRIORITY"]

    body = []

    table = db.cfgdb.get_table("LDAP_SERVER")
    for key in natsort.natsorted(table):
        entry = table[key]
        if not isinstance(key, tuple):
            key = (key,)

        row = [*key] + [
            format_attr_value(
                entry,
                {'name': 'priority', 'description': 'Server priority',
                 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}),
                 ]

        body.append(row)

    click.echo(tabulate.tabulate(body, header))


@click.group(name="ldap",
             cls=clicommon.AliasedGroup)
def LDAP():
    """  """

    pass


@LDAP.command(name="global")
@clicommon.pass_db
def LDAP_global(db):
    """  """

    header = [
        "BIND DN",
        "BIND PASSWORD",
        "BIND TIMEOUT",
        "VERSION",
        "BASE DN",
        "PORT",
        "TIMEOUT",
        ]

    body = []

    table = db.cfgdb.get_table("LDAP")
    entry = table.get("global", {})
    row = [
        format_attr_value(
            entry,
            {'name': 'bind_dn', 'description': 'LDAP global bind dn', 'is-leaf-list': False,
             'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {
                'name': 'bind_password', 'description': 'Shared secret used for encrypting the communication',
                'is-leaf-list': False, 'is-mandatory': False, 'group': ''
            }
        ),
        format_attr_value(
            entry,
            {'name': 'bind_timeout', 'description': 'Ldap bind timeout', 'is-leaf-list': False,
             'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'version', 'description': 'Ldap version', 'is-leaf-list': False,
             'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'base_dn', 'description': 'Ldap user base dn', 'is-leaf-list': False,
             'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'port', 'description': 'TCP port to communicate with LDAP server',
             'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
        ),
        format_attr_value(
            entry,
            {'name': 'timeout', 'description': 'Ldap timeout duration in sec', 'is-leaf-list': False,
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
    cli_node = LDAP_SERVER
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(LDAP_SERVER)
    cli_node = LDAP
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(LDAP)
