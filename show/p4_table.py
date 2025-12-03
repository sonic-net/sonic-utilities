import json
import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector
from tabulate import tabulate


#
# 'p4_table' command ("show p4-table")
#
@click.command()
@click.argument('table_name', required=False)
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def p4_table(table_name, verbose):
    """Display all P4RT tables"""
    appDB = SonicV2Connector(use_unix_socket_path=True)

    if appDB is None:
        click.echo('Failed to connect to the application database.')
        return -1

    db = appDB.APPL_DB
    appDB.connect(db)

    if table_name is None:
        table_name = ''

    keys = appDB.keys(db, f'P4RT_TABLE:{table_name}*')
    db_info = {}

    for k in keys:
        db_info[k] = appDB.get_all(db, k)

    click.echo(json.dumps(db_info, indent=4))
