"""
Auto-generated show CLI plugin.


"""

import click
import tabulate
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


@click.group(name="passw-hardening",
             cls=clicommon.AliasedGroup)
def PASSW_HARDENING():
    """ PASSWORD HARDENING part of config_db.json """

    pass



@PASSW_HARDENING.command(name="policies")
@clicommon.pass_db
def PASSW_HARDENING_POLICIES(db):
    """  """

    header = [

"STATE",
"EXPIRATION",
"EXPIRATION WARNING",
"HISTORY CNT",
"LEN MIN",
"REJECT USER PASSW MATCH",
"LOWER CLASS",
"UPPER CLASS",
"DIGITS CLASS",
"SPECIAL CLASS",

]

    body = []

    table = db.cfgdb.get_table("PASSW_HARDENING")
    entry = table.get("POLICIES", {})
    row = [
    format_attr_value(
        entry,
        {'name': 'state', 'description': 'state of the feature', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'expiration', 'description': 'expiration time (days unit)', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'expiration_warning', 'description': 'expiration warning time (days unit)', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'history_cnt', 'description': 'num of old password that the system will recorded', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'len_min', 'description': 'password min length', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'reject_user_passw_match', 'description': 'username password match', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'lower_class', 'description': 'password lower chars policy', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'upper_class', 'description': 'password upper chars policy', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'digits_class', 'description': 'password digits chars policy', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
    ),
    format_attr_value(
        entry,
        {'name': 'special_class', 'description': 'password special chars policy', 'is-leaf-list': False, 'is-mandatory': False, 'group': ''}
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
    cli_node = PASSW_HARDENING
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(PASSW_HARDENING)
