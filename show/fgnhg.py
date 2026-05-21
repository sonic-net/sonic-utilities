from collections import OrderedDict
import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate


@click.group(cls=clicommon.AliasedGroup)
def fgnhg():
    """Show FGNHG information"""
    pass

@fgnhg.command()
@click.argument('nhg', required=False)
def active_hops(nhg):
    config_db = ConfigDBConnector()
    config_db.connect()
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)  # Make one attempt only STATE_DB
    TABLE_NAME_SEPARATOR = '|'
    prefix = 'FG_ROUTE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    table_keys = []
    t_dict = {}
    header = ["FG NHG Prefix", "Active Next Hops"]
    table = []
    output_dict = {}
    ctx = click.get_current_context()
    try:
        table_keys = sorted(state_db.keys(state_db.STATE_DB, _hash))
    except Exception as e:
        ctx.fail("FG_ROUTE_TABLE does not exist!")
    if table_keys is None:
        ctx.fail("FG_ROUTE_TABLE does not exist!")
    if nhg is None:
        for nhg_prefix in table_keys:
            t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
            vals = sorted(set([val for val in t_dict.values()]))
            for nh_ip in vals:
                if nhg_prefix in output_dict:
                    output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                else:
                    output_dict[nhg_prefix] = [nh_ip.split("@")[0]]
            nhg_prefix_report = (nhg_prefix.split("|")[1])
            formatted_nhps = ','.replace(',', '\n').join(output_dict[nhg_prefix])
            table.append([nhg_prefix_report, formatted_nhps])

        click.echo(tabulate(table, header, tablefmt="simple"))
    else:
        nhip_prefix_map = {}
        header = ["FG NHG Prefix", "Active Next Hops"]
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
                        ctx.fail("state_db and config_db have FGNHG prefix config mismatch. Check device config!");
                output_list = sorted(output_list)
            if not output_list:
                ctx.fail("FG_ROUTE table likely does not contain the required entries")
            nhg_prefix_report = nhip_prefix_map[output_list[0]].split("|")[1]
            formatted_output_list = ','.replace(',', '\n').join(output_list)
            table.append([nhg_prefix_report, formatted_output_list])
            click.echo(tabulate(table, header, tablefmt="simple"))

@fgnhg.command()
@click.argument('nhg', required=False)
def hash_view(nhg):
    config_db = ConfigDBConnector()
    config_db.connect()
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)  # Make one attempt only STATE_DB
    TABLE_NAME_SEPARATOR = '|'
    prefix = 'FG_ROUTE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    table_keys = []
    t_dict = {}
    header = ["FG NHG Prefix", "Next Hop", "Hash buckets"]
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
    if nhg is None:
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
            nhg_prefix_report = (nhg_prefix.split("|")[1])
            for nhip, val in bank_dict.items():
                displayed_banks = []
                bank_output = ""
                formatted_banks = (bank_dict[nhip])
                for bankid in formatted_banks:
                    if (len(str(bankid)) == 1):
                        displayed_banks.append(str(bankid) + "  ")

                    if (len(str(bankid)) == 2):
                        displayed_banks.append(str(bankid) + " ")

                    if (len(str(bankid)) == 3):
                        displayed_banks.append(str(bankid))
                for i in range (0, len(displayed_banks), 8):
                    bank_output = bank_output + " ".join(displayed_banks[i:i+8]) + "\n" 
                bank_output = bank_output + "\n"
                table.append([nhg_prefix_report, nhip, bank_output])
        click.echo(tabulate(table, header, tablefmt="simple"))
    else:
        header = ["FG NHG Prefix", "Next Hop", "Hash buckets"]
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
                        ctx.fail("state_db and config_db have FGNHG prefix config mismatch. Check device config!");
                nhg_prefix_report = nhip_prefix_map[list(bank_dict.keys())[0]].split("|")[1]
                output_bank_dict = OrderedDict(sorted(output_bank_dict.items())) 
                for nhip, val in output_bank_dict.items():
                    bank_output = ""
                    displayed_banks = []
                    formatted_banks = (bank_dict[nhip])
                    for bankid in formatted_banks:
                        if (len(str(bankid)) == 1):
                            displayed_banks.append(str(bankid) + "  ")

                        if (len(str(bankid)) == 2):
                            displayed_banks.append(str(bankid) + " ")

                        if (len(str(bankid)) == 3):
                            displayed_banks.append(str(bankid))
                    for i in range (0, len(displayed_banks), 8):
                        bank_output = bank_output + " ".join(displayed_banks[i:i+8]) + "\n" 
                    table.append([nhg_prefix_report, nhip, bank_output])
            click.echo(tabulate(table, header, tablefmt="simple"))
