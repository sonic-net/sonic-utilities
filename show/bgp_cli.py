import click
import tabulate
import json
import utilities_common.cli as clicommon
from sonic_py_common import multi_asic

from utilities_common.bgp import (
    CFG_BGP_DEVICE_GLOBAL,
    BGP_DEVICE_GLOBAL_KEY,
    to_str,
)


#
# BGP helpers ------------------------------------------------------------
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
# BGP CLI ----------------------------------------------------------------
#


@click.group(
    name="bgp",
    cls=clicommon.AliasedGroup
)
def BGP():
    """ Show BGP configuration """

    pass

# BGP device-global


@BGP.command(name="device-global")
@click.option("-j", "--json", "json_format",
              help="Display in JSON format",
              is_flag=True,
              default=False)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL(ctx, db, json_format):
    """ Show BGP device global state """

    body = []
    results = {}

    if multi_asic.is_multi_asic():
        masic = True
        header = ["ASIC ID", "TSA", "W-ECMP"]
        namespaces = multi_asic.get_namespace_list()
    else:
        masic = False
        header = ["TSA", "W-ECMP"]
        namespaces = [multi_asic.DEFAULT_NAMESPACE]

    for ns in namespaces:
        config_db = db.cfgdb_clients[ns]

        table = config_db.get_table(CFG_BGP_DEVICE_GLOBAL)
        entry = table.get(BGP_DEVICE_GLOBAL_KEY, {})

        if not entry:
            click.echo("No configuration is present in CONFIG DB")
            ctx.exit(0)

        if json_format:
            json_output = {
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

            if masic:
                results[ns] = json_output
            else:
                results = json_output
        else:
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
            if masic:
                row.insert(0, ns)

            body.append(row)

    if json_format:
        click.echo(json.dumps(results, indent=4))
    else:
        click.echo(tabulate.tabulate(body, headers=header))
