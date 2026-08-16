import json
import click
from swsscommon.swsscommon import SonicV2Connector
from tabulate import tabulate


#
# 'l3_admit' command ("show l3-admit")
#
@click.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def l3_admit(verbose):
    """Show l3 admit info"""
    appDB = SonicV2Connector(host='127.0.0.1')

    if appDB is None:
        click.echo('Failed to connect to the application database.')
        return -1

    db = appDB.APPL_DB
    appDB.connect(db)

    def rule_cmp(rule):
        """Sort by dest mac in ascending order"""
        rule_json = rule.split(':', 2)[2]
        rule_values = json.loads(rule_json)
        return rule_values['match/dst_mac']

    rules = appDB.keys(db, 'P4RT_TABLE:FIXED_L3_ADMIT_TABLE*')
    rules = sorted(rules, key=rule_cmp)

    table = [('Dest Mac', 'Mask', 'Ingress Port')]
    for rule in rules:
        rule_json = rule.split(':', 2)[2]
        rule_values = json.loads(rule_json)
        dst_mac, _, mask = rule_values['match/dst_mac'].partition('&')
        port = rule_values.get('match/in_port', '<any>')
        table.append([dst_mac, mask, port])

    click.echo(tabulate(table, headers='firstrow'))
