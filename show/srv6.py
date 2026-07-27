import click
import json
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic
from swsscommon.swsscommon import ConfigDBConnector, SonicV2Connector
from natsort import natsorted
from tabulate import tabulate

CONFIG_DB_MY_SID_TABLE = 'SRV6_MY_SIDS'
CONFIG_DB_MY_LOCATORS_TABLE = 'SRV6_MY_LOCATORS'


@click.group(cls=clicommon.AliasedGroup)
def srv6():
    """Show SRv6 related information"""
    pass


def get_locators(namespace, locator):
    config_db = ConfigDBConnector(namespace=namespace)
    config_db.connect()
    data = config_db.get_table(CONFIG_DB_MY_LOCATORS_TABLE)

    table = []
    if locator:
        # filter to show only the requested locator
        if locator in data:
            entry = data[locator]
            table.append([
                locator,
                entry.get("prefix"),
                entry.get("block_len", 32),
                entry.get("node_len", 16),
                entry.get("func_len", 16)
            ])
    else:
        # show all locators
        for k in natsorted(data.keys()):
            entry = data[k]
            table.append([
                k,
                entry.get("prefix"),
                entry.get("block_len", 32),
                entry.get("node_len", 16),
                entry.get("func_len", 16)
            ])
    return table


# `show srv6 locators`
@srv6.command()
@click.argument("locator", required=False)
@multi_asic_util.multi_asic_click_options
def locators(locator, namespace, display):
    header = ["Locator", "Prefix", "Block Len", "Node Len", "Func Len"]
    table = []
    if multi_asic.is_multi_asic() and not namespace:
        namespaces = multi_asic.get_namespace_list()
        for ns in namespaces:
            ns_table = get_locators(ns, locator)
            table.extend(ns_table)
    else:
        # default or single namespace
        table = get_locators(namespace, locator)
    click.echo(tabulate(table, header))


def get_static_sids(namespace, sid):
    config_db = ConfigDBConnector(namespace=namespace)
    config_db.connect()
    data = config_db.get_table(CONFIG_DB_MY_SID_TABLE)

    # parse the keys to get the locator for each sid
    sid_dict = dict()
    for k, v in data.items():
        if sid and sid not in k:
            # skip not relevant SIDs
            continue
        if len(k) < 2:
            # skip SIDs that does not have locators
            click.echo(f"Warning: SID entry {k} is malformed", err=True)
            continue

        loc = k[0]
        sid_prefix = k[1]
        v["locator"] = loc
        sid_dict[sid_prefix] = v

    # query ASIC_DB to check whether the SID is offloaded to the ASIC
    db = SonicV2Connector(namespace=namespace)
    db.connect(db.ASIC_DB)
    asic_data = db.keys(db.ASIC_DB, "*SID*")
    asic_sids = set()
    for entry in asic_data:
        # extract ASIC SID entry data
        try:
            _, _, json_str = entry.split(":", 2)
        except ValueError:
            continue

        # Parse JSON part
        try:
            fields = json.loads(json_str)
        except json.JSONDecodeError:
            continue

        sid_ip = fields["sid"]
        block_len = int(fields["locator_block_len"])
        node_len = int(fields["locator_node_len"])
        func_len = int(fields["function_len"])
        sid_prefix = sid_ip + f"/{block_len + node_len + func_len}"
        asic_sids.add(sid_prefix)

    table = []
    for sid_prefix in natsorted(sid_dict.keys()):
        entry = sid_dict[sid_prefix]
        table.append([
            sid_prefix,
            entry.get("locator"),
            entry.get("action", "N/A"),
            entry.get("decap_dscp_mode", "N/A"),
            entry.get("decap_vrf", "N/A"),
            True if sid_prefix in asic_sids else False
        ])
    return table


# `show srv6 static-sids`
@srv6.command()
@click.argument('sid', required=False)
@multi_asic_util.multi_asic_click_options
def static_sids(sid, namespace, display):
    """Show SRv6 static SIDs"""
    # format and print the sid dictionaries
    header = ["SID", "Locator", "Action", "Decap DSCP Mode", "Decap VRF", "Offloaded"]
    table = []
    if multi_asic.is_multi_asic() and not namespace:
        namespaces = multi_asic.get_namespace_list()
        for ns in namespaces:
            ns_table = get_static_sids(ns, sid)
            table.extend(ns_table)
    else:
        # default or single namespace
        table = get_static_sids(namespace, sid)

    click.echo(tabulate(table, header))


# 'stats' subcommand  ("show srv6 stats")
@srv6.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('sid', required=False)
def stats(verbose, sid):
    """Show SRv6 counter statistic"""
    cmd = ['srv6stat']
    if sid:
        cmd += ['-s', sid]
    clicommon.run_command(cmd, display_cmd=verbose)
