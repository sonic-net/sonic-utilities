import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector
from collections import defaultdict
from natsort import natsorted
from tabulate import tabulate


#
# 'lacp' group ("show lacp")
#
@click.group(cls=clicommon.AliasedGroup)
def lacp():
    """Show lacp debug info"""
    pass


# 'info' subcommand ("show lacp info")
@lacp.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def info(verbose):
    """Show lacp debug info"""
    stateDB = SonicV2Connector(host='127.0.0.1')

    if stateDB is None:
        click.echo('Failed to connect to the state database.')
        return -1

    db = stateDB.STATE_DB
    stateDB.connect(db)

    lag_members = natsorted(stateDB.keys(db, 'LAG_MEMBER_TABLE|*'))

    table = defaultdict(list)

    for member in lag_members:
        _, trunk, port = member.split('|')
        lag_info = stateDB.get_all(db, member)

        trunk_state = stateDB.get(db, f'LAG_TABLE|{trunk}', 'oper_status')
        link_state = 'up' if lag_info['link.up'] == 'true' else 'down'

        table['Trunk'].append(f'{trunk} ({trunk_state})')
        table['Member Port'].append(f'{port} ({link_state})')

        is_active = stateDB.get(db, f'LAG_TABLE|{trunk}', 'runner.active')
        mode = 'Active' if is_active == 'true' else 'Passive'
        table['Mode'].append(mode)

        priority = stateDB.get(db, f'LAG_TABLE|{trunk}', 'runner.sys_prio')
        table['Priority'].append(priority)

        actor_id = (f"{lag_info['runner.actor_lacpdu_info.system']} "
                    f"({lag_info['runner.actor_lacpdu_info.key']})")
        partner_id = (f"{lag_info['runner.partner_lacpdu_info.system']} "
                      f"({lag_info['runner.partner_lacpdu_info.key']})")

        table['Actor System id (key)'].append(actor_id)
        table['Partner System id (key)'].append(partner_id)

        table['Speed (Mbps)'].append(lag_info['link.speed'])

    click.echo(tabulate(table, headers='keys', numalign='center'))

    return 0


# 'status' subcommand ("show lacp status")
@lacp.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def status(verbose):
    """Show lacp status info"""
    stateDB = SonicV2Connector(host='127.0.0.1')

    if stateDB is None:
        click.echo('Failed to connect to the state database.')
        return -1

    db = stateDB.STATE_DB
    stateDB.connect(db)

    lag_members = natsorted(stateDB.keys(db, 'LAG_MEMBER_TABLE|*'))

    table = defaultdict(list)

    for member in lag_members:
        _, trunk, port = member.split('|')
        lag_info = stateDB.get_all(db, member)

        for role in ['actor', 'partner']:
            if role == 'actor':
                table['Trunk'].append(trunk)
                table['Member Port'].append(port)
            else:
                table['Trunk'].append('')
                table['Member Port'].append('')

            table['Role'].append(role.capitalize())

            # get state info from status code
            status_code = int(lag_info[f'runner.{role}_lacpdu_info.state'])

            bit = 0x80
            fields = ['Exp', 'Def', 'Dist', 'Col', 'Sync', 'Aggr', 'Timeout', 'Mode']

            for field in fields:
                is_selected = status_code & bit

                if field == 'Sync':
                    state = 'In-Sync' if is_selected else 'Out-of-Sync'
                elif field == 'Timeout':
                    state = '90s' if is_selected else '3s'
                elif field == 'Mode':
                    state = 'Active' if is_selected else 'Passive'
                else:
                    state = 'Yes' if is_selected else 'No'

                table[field].append(state)
                bit >>= 1

    click.echo(tabulate(table, headers='keys', stralign='center'))
    click.echo('\nValues: expired/defaulted/distributing/collecting/sync/'
               'aggregating/timeout/mode')


# 'counters' subcommand ("show lacp counters")
@lacp.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def counters(verbose):
    """Show lacp packet counters"""
    stateDB = SonicV2Connector(host='127.0.0.1')

    if stateDB is None:
        click.echo('Failed to connect to the state database.')
        return -1

    db = stateDB.STATE_DB
    stateDB.connect(db)

    lag_members = natsorted(stateDB.keys(db, 'LAG_MEMBER_TABLE|*'))

    table = defaultdict(list)

    for member in lag_members:
        _, trunk, port = member.split('|')
        lag_info = stateDB.get_all(db, member)
        table['Trunk'].append(trunk)
        table['Member Port'].append(port)
        table['LACP Tx'].append(lag_info['runner.counters.lacp-out-packets'])
        table['LACP Rx'].append(lag_info['runner.counters.lacp-in-packets'])
        table['Rx Errors'].append(lag_info['runner.counters.lacp-rx-errors'])

    click.echo(tabulate(table, headers='keys'))
