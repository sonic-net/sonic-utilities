import click
import ipaddress
import tabulate
import json
import utilities_common.cli as clicommon

from utilities_common.bgp import (
    CFG_BGP_DEVICE_GLOBAL,
    BGP_DEVICE_GLOBAL_KEY,
    CFG_BGP_AGGREGATE_ADDRESS,
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


#
# BGP aggregate-address show helper ------------------------------------------------------------------------------------
#


def show_aggregate_address(db, af):
    """ Show BGP aggregate addresses filtered by address family.

    Args:
        db: Database object.
        af (str): Address family - "ipv4" or "ipv6".
    """

    header = [
        "Prefix",
        "State",
        "Option Flags",
        "Aggregate Address Prefix List",
        "Contributing Address Prefix List",
    ]
    body = []

    cfg_table = db.cfgdb.get_table(CFG_BGP_AGGREGATE_ADDRESS)

    if not cfg_table:
        click.echo("Flags: A - As Set, B - BBR Required, S - Summary Only\n")
        click.echo(tabulate.tabulate(body, header))
        return

    # Try to get state DB entries for state information
    state_table = {}
    try:
        state_db = db.db
        state_db.connect(state_db.STATE_DB, False)
        keys = state_db.keys(state_db.STATE_DB, f"{CFG_BGP_AGGREGATE_ADDRESS}|*")
        if keys:
            for key in keys:
                entry_key = key.split("|", 1)[1]
                state_table[entry_key] = state_db.get_all(state_db.STATE_DB, key)
    except Exception as exec:
        click.echo(f"Warning:failed to read BGP aggregate state from STATE_DB: {exec}\n", err=True)

    for prefix in sorted(cfg_table.keys(),
                         key=lambda p: (
                             ipaddress.ip_network(p, strict=False).version,
                             ipaddress.ip_network(p, strict=False),
                             p)):
        # Filter by address family
        try:
            net = ipaddress.ip_network(prefix, strict=False)
        except ValueError:
            continue

        if af == "ipv4" and net.version != 4:
            continue
        if af == "ipv6" and net.version != 6:
            continue

        entry = cfg_table[prefix]

        # Determine state from state DB
        state_entry = state_table.get(prefix, {})
        state = state_entry.get("state", "N/A")
        state = state.capitalize() if state != "N/A" else state

        # Build option flags
        flags = []
        if entry.get("as-set", "false") == "true":
            flags.append("A")
        if entry.get("bbr-required", "false") == "true":
            flags.append("B")
        if entry.get("summary-only", "false") == "true":
            flags.append("S")
        flags_str = ",".join(flags) if flags else ""

        agg_prefix_list = entry.get("aggregate-address-prefix-list", "")
        contrib_prefix_list = entry.get("contributing-address-prefix-list", "")

        body.append([prefix, state, flags_str, agg_prefix_list, contrib_prefix_list])

    click.echo("Flags: A - As Set, B - BBR Required, S - Summary Only\n")
    click.echo(tabulate.tabulate(body, header))
