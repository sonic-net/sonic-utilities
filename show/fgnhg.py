from collections import OrderedDict
import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate


@click.group(cls=clicommon.AliasedGroup)
def fgnhg():
    """Show FGNHG information"""
    pass


def parse_fg_route_key(key):
    """Parse FG_ROUTE_TABLE key into (vrf, prefix).

    2-part key: FG_ROUTE_TABLE|<prefix> -> ('default', <prefix>)
    3-part key: FG_ROUTE_TABLE|<vrf>|<prefix> -> (<vrf>, <prefix>)
    """
    parts = key.split("|")
    if len(parts) == 3:
        return parts[1], parts[2]
    return 'default', parts[1]


def format_bank_output(bank_ids):
    """Format hash bucket IDs for display."""
    displayed_banks = []
    for bankid in bank_ids:
        if len(str(bankid)) == 1:
            displayed_banks.append(str(bankid) + "  ")
        elif len(str(bankid)) == 2:
            displayed_banks.append(str(bankid) + " ")
        elif len(str(bankid)) == 3:
            displayed_banks.append(str(bankid))
    bank_output = ""
    for i in range(0, len(displayed_banks), 8):
        bank_output = bank_output + " ".join(displayed_banks[i:i+8]) + "\n"
    bank_output = bank_output + "\n"
    return bank_output


@fgnhg.command()
@click.argument('arg1', required=False)
@click.argument('arg2', required=False)
def active_hops(arg1, arg2):
    """Show active next hops. Usage:
    show fgnhg active-hops                   - show all
    show fgnhg active-hops <nhg>             - filter by NHG name
    show fgnhg active-hops <vrf> <prefix>    - filter by VRF/VNET and prefix
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)  # Make one attempt only STATE_DB
    TABLE_NAME_SEPARATOR = '|'
    fg_prefix = 'FG_ROUTE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(fg_prefix, '*')
    table_keys = []
    t_dict = {}
    header = ["VNET/VRF", "FG NHG Prefix", "Active Next Hops"]
    table = []
    output_dict = {}
    ctx = click.get_current_context()
    try:
        table_keys = sorted(state_db.keys(state_db.STATE_DB, _hash))
    except Exception as e:
        ctx.fail("FG_ROUTE_TABLE does not exist!")
    if table_keys is None:
        ctx.fail("FG_ROUTE_TABLE does not exist!")

    if arg1 is not None and arg2 is not None:
        # 2-arg mode: filter by VRF/VNET + prefix
        vrf_filter = arg1
        prefix_filter = arg2
        lookup_key = f"FG_ROUTE_TABLE|{vrf_filter}|{prefix_filter}"
        if lookup_key not in table_keys:
            ctx.fail(f"No FG_ROUTE_TABLE entry found for VRF '{vrf_filter}' prefix '{prefix_filter}'")
        t_dict = state_db.get_all(state_db.STATE_DB, lookup_key)
        vals = sorted(set([val for val in t_dict.values()]))
        nhops = [nh_ip.split("@")[0] for nh_ip in vals]
        formatted_nhps = '\n'.join(nhops)
        table.append([vrf_filter, prefix_filter, formatted_nhps])
        click.echo(tabulate(table, header, tablefmt="simple"))
    elif arg1 is None:
        # 0-arg mode: show all
        for nhg_prefix in table_keys:
            t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
            vals = sorted(set([val for val in t_dict.values()]))
            for nh_ip in vals:
                if nhg_prefix in output_dict:
                    output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                else:
                    output_dict[nhg_prefix] = [nh_ip.split("@")[0]]
            vrf, prefix_report = parse_fg_route_key(nhg_prefix)
            formatted_nhps = '\n'.join(output_dict[nhg_prefix])
            table.append([vrf, prefix_report, formatted_nhps])

        click.echo(tabulate(table, header, tablefmt="simple"))
    else:
        # 1-arg mode: filter by NHG name
        nhg = arg1
        nhip_prefix_map = {}
        try:
            fg_nhg_member_table = config_db.get_table('FG_NHG_MEMBER')
        except Exception as e:
            ctx.fail("FG_NHG_MEMBER entries not present in config_db")
        alias_list = []
        nexthop_alias = {}
        output_list = []
        for nexthop, nexthop_metadata in fg_nhg_member_table.items():
            alias_list.append(nexthop_metadata['FG_NHG'])
            nexthop_alias[nexthop] = nexthop_metadata['FG_NHG']
        if nhg not in alias_list:
            ctx.fail("Please provide a valid NHG alias")
        else:
            for nhg_prefix in table_keys:
                t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
                vals = sorted(set([val for val in t_dict.values()]))
                for nh_ip in vals:
                    nhip_prefix_map[nh_ip.split("@")[0]] = nhg_prefix

                    if nh_ip.split("@")[0] in nexthop_alias:
                        if nexthop_alias[nh_ip.split("@")[0]] == nhg:
                            output_list.append(nh_ip.split("@")[0])
                    else:
                        ctx.fail("state_db and config_db have FGNHG prefix config mismatch. Check device config!")
                output_list = sorted(output_list)
            if not output_list:
                ctx.fail("FG_ROUTE table likely does not contain the required entries")
            matched_key = nhip_prefix_map[output_list[0]]
            vrf, prefix_report = parse_fg_route_key(matched_key)
            formatted_output_list = '\n'.join(output_list)
            table.append([vrf, prefix_report, formatted_output_list])
            click.echo(tabulate(table, header, tablefmt="simple"))


@fgnhg.command()
@click.argument('arg1', required=False)
@click.argument('arg2', required=False)
def hash_view(arg1, arg2):
    """Show hash bucket view. Usage:
    show fgnhg hash-view                   - show all
    show fgnhg hash-view <nhg>             - filter by NHG name
    show fgnhg hash-view <vrf> <prefix>    - filter by VRF/VNET and prefix
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)  # Make one attempt only STATE_DB
    TABLE_NAME_SEPARATOR = '|'
    fg_prefix = 'FG_ROUTE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(fg_prefix, '*')
    table_keys = []
    t_dict = {}
    header = ["VNET/VRF", "FG NHG Prefix", "Next Hop", "Hash buckets"]
    table = []
    output_dict = {}
    bank_dict = {}
    ctx = click.get_current_context()
    try:
        table_keys = sorted(state_db.keys(state_db.STATE_DB, _hash))
    except Exception as e:
        ctx.fail("FG_ROUTE_TABLE does not exist!")
    if table_keys is None:
        ctx.fail("FG_ROUTE_TABLE does not exist!")

    if arg1 is not None and arg2 is not None:
        # 2-arg mode: filter by VRF/VNET + prefix
        vrf_filter = arg1
        prefix_filter = arg2
        lookup_key = f"FG_ROUTE_TABLE|{vrf_filter}|{prefix_filter}"
        if lookup_key not in table_keys:
            ctx.fail(f"No FG_ROUTE_TABLE entry found for VRF '{vrf_filter}' prefix '{prefix_filter}'")
        t_dict = state_db.get_all(state_db.STATE_DB, lookup_key)
        vals = sorted(set([val for val in t_dict.values()]))
        bank_dict = {}
        for nh_ip in vals:
            bank_ids = sorted([int(k) for k, v in t_dict.items() if v == nh_ip])
            bank_ids = [str(x) for x in bank_ids]
            bank_dict[nh_ip.split("@")[0]] = bank_ids
        bank_dict = OrderedDict(sorted(bank_dict.items()))
        for nhip, val in bank_dict.items():
            bank_output = format_bank_output(val)
            table.append([vrf_filter, prefix_filter, nhip, bank_output])
        click.echo(tabulate(table, header, tablefmt="simple"))
    elif arg1 is None:
        # 0-arg mode: show all
        for nhg_prefix in table_keys:
            bank_dict = {}
            t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
            vals = sorted(set([val for val in t_dict.values()]))
            for nh_ip in vals:
                bank_ids = sorted([int(k) for k, v in t_dict.items() if v == nh_ip])
                bank_ids = [str(x) for x in bank_ids]
                if nhg_prefix in output_dict:
                    output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                else:
                    output_dict[nhg_prefix] = [nh_ip.split("@")[0]]
                bank_dict[nh_ip.split("@")[0]] = bank_ids
            bank_dict = OrderedDict(sorted(bank_dict.items()))
            vrf, prefix_report = parse_fg_route_key(nhg_prefix)
            for nhip, val in bank_dict.items():
                bank_output = format_bank_output(val)
                table.append([vrf, prefix_report, nhip, bank_output])
        click.echo(tabulate(table, header, tablefmt="simple"))
    else:
        # 1-arg mode: filter by NHG name
        nhg = arg1
        try:
            fg_nhg_member_table = config_db.get_table('FG_NHG_MEMBER')
        except Exception as e:
            ctx.fail("FG_NHG_MEMBER entries not present in config_db")
        alias_list = []
        nexthop_alias = {}
        for nexthop, nexthop_metadata in fg_nhg_member_table.items():
            alias_list.append(nexthop_metadata['FG_NHG'])
            nexthop_alias[nexthop] = nexthop_metadata['FG_NHG']
        if nhg not in alias_list:
            ctx.fail("Please provide a valid NHG alias")
        else:
            nhip_prefix_map = {}
            for nhg_prefix in table_keys:
                bank_dict = {}
                t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
                vals = sorted(set([val for val in t_dict.values()]))
                for nh_ip in vals:
                    bank_ids = sorted([int(k) for k, v in t_dict.items() if v == nh_ip])
                    nhip_prefix_map[nh_ip.split("@")[0]] = nhg_prefix
                    bank_ids = [str(x) for x in bank_ids]
                    if nhg_prefix in output_dict:
                        output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                    else:
                        output_dict[nhg_prefix] = [nh_ip.split("@")[0]]
                    bank_dict[nh_ip.split("@")[0]] = bank_ids
                bank_dict = OrderedDict(sorted(bank_dict.items()))
                output_bank_dict = {}
                for nexthop, banks in bank_dict.items():
                    if nexthop in nexthop_alias:
                        if nexthop_alias[nexthop] == nhg:
                            output_bank_dict[nexthop] = banks
                    else:
                        ctx.fail("state_db and config_db have FGNHG prefix config mismatch. Check device config!")
                matched_key = nhip_prefix_map[list(bank_dict.keys())[0]]
                vrf, prefix_report = parse_fg_route_key(matched_key)
                output_bank_dict = OrderedDict(sorted(output_bank_dict.items()))
                for nhip, val in output_bank_dict.items():
                    bank_output = format_bank_output(bank_dict[nhip])
                    table.append([vrf, prefix_report, nhip, bank_output])
            click.echo(tabulate(table, header, tablefmt="simple"))
