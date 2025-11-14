import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector


def check_portchannel_name_member_port_exists(portchannel_name, port_name):
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.STATE_DB)
    KEY = 'LAG_TABLE|' + portchannel_name
    if not db.exists(db.STATE_DB, KEY):
        return False
    if port_name:
        MKEY = 'LAG_MEMBER_TABLE|' + portchannel_name + '|' + port_name
        if not db.exists(db.STATE_DB, MKEY):
            return False
    return True


@click.group()
def portchannel():
    """Clear portchannel lacp stats counters"""
    pass


@click.command('statistics')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=False)
@click.argument('port_name', metavar='<port_name>', required=False)
def statistics(portchannel_name, port_name):
    """clearing statistics"""
    if portchannel_name and port_name is None:
        valid = check_portchannel_name_member_port_exists(portchannel_name, None)
        if not valid:
            click.echo("No such portchannel interface : {}". format(portchannel_name))
            return
        command = 'sudo teamdctl ' + portchannel_name + ' clear statistics'
        try:
            clicommon.run_command(command, shell=True)
            click.echo("Cleared stats counter for LAG : {}". format(portchannel_name))
        except Exception as e:
            click.echo("Warning: Could not clear stats for {} {}". format(portchannel_name, str(e)))
    elif portchannel_name and port_name:
        valid = check_portchannel_name_member_port_exists(portchannel_name, port_name)
        if not valid:
            click.echo(f"No such portchannel or portchannel member interface : {portchannel_name} {port_name}")
            return
        command = 'sudo teamdctl ' + portchannel_name + ' clear statistics port ' + port_name
        try:
            clicommon.run_command(command, shell=True)
            click.echo("Cleared stats counter for LAG : {} LAG_MEMBER : {}". format(portchannel_name, port_name))
        except Exception as e:
            click.echo("Warning: Could not clear stats for {} {} {}". format(portchannel_name, port_name, str(e)))
    elif portchannel_name is None and port_name is None:
        db = SonicV2Connector(host='127.0.0.1')
        db.connect(db.STATE_DB)
        lag_keys = db.keys(db.STATE_DB, 'LAG_TABLE|*')
        cleared = True
        for lag_key in natsorted(lag_keys):
            lag_name = lag_key.split('|')[-1]
            command = 'sudo teamdctl ' + lag_name + ' clear statistics'
            try:
                clicommon.run_command(command, shell=True)
            except Exception as e:
                cleared = False
                click.echo("Warning: Could not clear stats for {} {}". format(lag_name, str(e)))
        if cleared:
            click.echo("Cleared stats counter for all LAGs")


portchannel.add_command(statistics)
