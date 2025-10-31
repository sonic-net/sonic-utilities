import click
import json
import utilities_common.cli as clicommon
from swsscommon.swsscommon import ConfigDBConnector, SonicV2Connector
from natsort import natsorted
from tabulate import tabulate

CONFIG_DB_MY_SID_TABLE = 'SRV6_MY_SIDS'
CONFIG_DB_MY_LOCATORS_TABLE = 'SRV6_MY_LOCATORS'


@click.group(cls=clicommon.AliasedGroup)
def srv6():
    """Show SRv6 related information"""
    pass


# `show srv6 locators`
@srv6.command()
@click.argument("locator", required=False)
def locators():
    config_db = ConfigDBConnector()
    config_db.connect()
    data = config_db.get_table(CONFIG_DB_MY_LOCATORS_TABLE)

    header = ["Locator", "Prefix", "Block Len", "Node Len", "Func Len"]
    table = []
    for k in natsorted(data.keys()):
        entry = data[k]
        table.append([
            k,
            entry.get("prefix"),
            entry.get("block_len", 32),
            entry.get("node_len", 16),
            entry.get("func_len", 16)
        ])
    click.echo(tabulate(table, header))


# `show srv6 static-sids`
@srv6.command()
@click.argument('sid', required=False)
def static_sids(sid):
    config_db = ConfigDBConnector()
    config_db.connect()
    data = config_db.get_table(CONFIG_DB_MY_SID_TABLE)

    # parse the keys to get the locator for each sid
    sid_dict = dict()
    for k, v in data.items():
        if sid and sid not in k:
            # skip not relevant SIDs
            continue
        if "|" not in k:
            # skip SIDs that does not have locators
            continue

        loc = k.split("|")[0]
        sid_prefix = k.split("|")[1]
        v["locator"] = loc
        sid_dict[sid_prefix] = v

    # query ASIC_DB to check whether the SID is offloaded to the ASIC
    db = SonicV2Connector(host="localhost")
    db.connect(db.ASIC_DB)
    asic_data = db.keys("*SID*")
    asic_sids = set()
    for entry in asic_data:
        # extract ASIC SID entry data
        _, _, json_str = entry.split(":", 2)
        
        # Parse JSON part
        fields = json.loads(json_str)
        sid_ip = fields["sid"]
        block_len = int(fields["locator_block_len"])
        node_len = int(fields["locator_node_len"])
        func_len = int(fields["function_len"])
        sid_prefix = sid_ip + f"/{block_len + node_len + func_len}"
        asic_sids.add(sid_prefix)

    # format and print the sid dictionaries
    header = ["SID", "Locator", "Action", "Decap DSCP Mode", "Decap VRF", "Offloaded"]
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
