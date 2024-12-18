import click
import tabulate
import json
import utilities_common.cli as clicommon

from utilities_common.bgp import (
    CFG_BGP_DEVICE_GLOBAL,
    BGP_DEVICE_GLOBAL_KEY,
    to_str,
)


#
# BGP helpers ---------------------------------------------------------------------------------------------------------
#


def format_attr_value(entry, attr):
    """ Helper that formats attribute to be presented in the table output.

    Args:
        entry (Dict[str, str]): CONFIG DB entry configuration.
        attr (Dict): Attribute metadata.

    Returns:
        str: formatted attribute value.
    """

    if attr["is-leaf-list"]:
        value = entry.get(attr["name"], [])
        return "\n".join(value) if value else "N/A"
    return entry.get(attr["name"], "N/A")


#
# BGP CLI -------------------------------------------------------------------------------------------------------------
#


@click.group(
    name="bgp",
    cls=clicommon.AliasedGroup
)
def BGP():
    """ Show BGP configuration """

    pass


#
# BGP device-global ---------------------------------------------------------------------------------------------------
#


@BGP.command(
    name="device-global"
)
@click.option(
    "-j", "--json", "json_format",
    help="Display in JSON format",
    is_flag=True,
    default=False
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL(ctx, db, json_format):
    """ Show BGP device global state """

    header = [
        "TSA",
        "W-ECMP",
    ]
    body = []

    table = db.cfgdb.get_table(CFG_BGP_DEVICE_GLOBAL)
    entry = table.get(BGP_DEVICE_GLOBAL_KEY, {})

    if not entry:
        click.echo("No configuration is present in CONFIG DB")
        ctx.exit(0)

    if json_format:
        json_dict = {
            "tsa": to_str(
                format_attr_value(
                    entry,
                    {
                        'name': 'tsa_enabled',
                        'is-leaf-list': False
                    }
                )
            ),
            "w-ecmp": to_str(
                format_attr_value(
                    entry,
                    {
                        'name': 'wcmp_enabled',
                        'is-leaf-list': False
                    }
                )
            )
        }
        click.echo(json.dumps(json_dict, indent=4))
        ctx.exit(0)

    row = [
        to_str(
            format_attr_value(
                entry,
                {
                    'name': 'tsa_enabled',
                    'is-leaf-list': False
                }
            )
        ),
        to_str(
            format_attr_value(
                entry,
                {
                    'name': 'wcmp_enabled',
                    'is-leaf-list': False
                }
            )
        )
    ]
    body.append(row)

    click.echo(tabulate.tabulate(body, header))
