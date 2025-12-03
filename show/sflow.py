import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector
from tabulate import tabulate


#
# 'sflow group ("show sflow ...")
#
@click.group(invoke_without_command=True)
@clicommon.pass_db
@click.pass_context
def sflow(ctx, db):
    """Show sFlow related information"""
    if ctx.invoked_subcommand is None:
        show_sflow_global(db.cfgdb)


#
# 'interface' command ("show sflow interface ...")
#
@sflow.command('interface')
@clicommon.pass_db
def sflow_interface(db):
    """Show sFlow interface information"""
    show_sflow_interface(db.cfgdb)


def sflow_appDB_connect():
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.APPL_DB, False)
    return db


def show_sflow_interface(config_db):
    sess_db = sflow_appDB_connect()
    if not sess_db:
        click.echo("sflow AppDB error")
        return

    port_tbl = config_db.get_table('PORT')
    if not port_tbl:
        click.echo("No ports configured")
        return

    click.echo("\nsFlow interface configurations")
    header = ['Interface', 'Admin State', 'Sampling Rate', 'Sampling Direction']
    body = []
    for pname in natsorted(list(port_tbl.keys())):
        intf_key = 'SFLOW_SESSION_TABLE:' + pname
        sess_info = sess_db.get_all(sess_db.APPL_DB, intf_key)
        if (sess_info is None or sess_info.get('admin_state') is None or
            sess_info.get('sample_rate') is None):
            continue
        body_info = [pname]
        body_info.append(sess_info.get('admin_state'))
        body_info.append(sess_info.get('sample_rate'))
        body_info.append(sess_info.get('sample_direction'))
        body.append(body_info)
    click.echo(tabulate(body, header, tablefmt='grid'))


def show_sflow_global(config_db):
    sflow_info = config_db.get_table('SFLOW')
    global_admin_state = 'down'
    global_sample_dir = 'rx'
    if sflow_info:
        global_admin_state = sflow_info['global']['admin_state']
        if ('sample_direction' in sflow_info['global']):
            global_sample_dir = sflow_info['global']['sample_direction']

    click.echo("\nsFlow Global Information:")
    click.echo("  sFlow Admin State:".ljust(30) + "{}".format(global_admin_state))
    click.echo("  sFlow Sample Direction:".ljust(30) + "{}".format(global_sample_dir))

    click.echo("  sFlow Polling Interval:".ljust(30), nl=False)
    if (sflow_info and 'polling_interval' in sflow_info['global']):
        click.echo("{}".format(sflow_info['global']['polling_interval']))
    else:
        click.echo("default")

    click.echo("  sFlow AgentID:".ljust(30), nl=False)
    if (sflow_info and 'agent_id' in sflow_info['global']):
        click.echo("{}".format(sflow_info['global']['agent_id']))
    else:
        click.echo("default")

    sflow_info = config_db.get_table('SFLOW_COLLECTOR')
    click.echo("\n  {} Collectors configured:".format(len(sflow_info)))
    for collector_name in sorted(list(sflow_info.keys())):
        vrf_name = (sflow_info[collector_name]['collector_vrf']
                    if 'collector_vrf' in sflow_info[collector_name] else 'default')
        click.echo("    Name: {}".format(collector_name).ljust(30) +
                   "IP addr: {} ".format(sflow_info[collector_name]['collector_ip']).ljust(25) +
                   "UDP port: {}".format(sflow_info[collector_name]['collector_port']).ljust(17) +
                   "VRF: {}".format(vrf_name))
