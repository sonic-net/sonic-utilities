from unicodedata import name
import click

import tabulate
from natsort import natsorted

import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic
from syslog_util import common as syslog_common


SYSLOG_TABLE = "SYSLOG_SERVER"

SYSLOG_SOURCE = "source"
SYSLOG_PORT = "port"
SYSLOG_VRF = "vrf"

#
# Syslog helpers ------------------------------------------------------------------------------------------------------
#

def format(header, body):
    return tabulate.tabulate(body, header, tablefmt="simple", numalign="left", stralign="left")

#
# Syslog CLI ----------------------------------------------------------------------------------------------------------
#

@click.group(
    name='syslog',
    cls=clicommon.AliasedGroup,
    invoke_without_command=True
)
@click.pass_context
@clicommon.pass_db
def syslog(db, ctx):
    """ Show syslog server configuration """

    if ctx.invoked_subcommand is not None:
        return

    header = [
        "SERVER IP",
        "SOURCE IP",
        "PORT",
        "VRF",
    ]
    body = []

    table = db.cfgdb.get_table(SYSLOG_TABLE)
    for key in natsorted(table):
        entry = table[key]
        row = [key] + [
            entry.get(SYSLOG_SOURCE, "N/A"),
            entry.get(SYSLOG_PORT, "N/A"),
            entry.get(SYSLOG_VRF, "N/A"),
        ]
        body.append(row)

    click.echo(format(header, body))

@syslog.command(
    name='rate-limit-host'
)
@clicommon.pass_db
def rate_limit_host(db):
    """ Show syslog rate limit configuration for host """

    header = [
        "INTERVAL",
        "BURST",
    ]
    body = []
    entry = db.cfgdb.get_entry(syslog_common.SYSLOG_CONFIG_TABLE, syslog_common.SYSLOG_CONFIG_GLOBAL_KEY)
    if entry:
        body.append([entry.get(syslog_common.SYSLOG_RATE_LIMIT_INTERVAL, 'N/A'),
                    entry.get(syslog_common.SYSLOG_RATE_LIMIT_BURST, 'N/A')])
    else:
        body.append('N/A', 'N/A')

    click.echo(format(header, body))


@syslog.command(
    name='rate-limit-container'
)
@click.argument('service_name', metavar='<service_name>', required=False)
@click.option('--namespace', '-n', 'namespace', default=None, 
              type=click.Choice(multi_asic_util.multi_asic_ns_choices() + ['default']), 
              show_default=True, help='Namespace name or all')
@clicommon.pass_db
def rate_limit_container(db, service_name, namespace):
    """ Show syslog rate limit configuration for containers """

    header = [
        "SERVICE",
        "INTERVAL",
        "BURST",
    ]
    
    # Feature configuration in global DB
    features = db.cfgdb.get_table(syslog_common.FEATURE_TABLE)
    if service_name:
        syslog_common.service_validator(features, service_name)
        
    global_feature_data, per_ns_feature_data = syslog_common.extract_feature_data(features)
    if not namespace:
        # for all namespaces
        is_first = True
        for namespace, cfg_db in natsorted(db.cfgdb_clients.items()):
            if is_first:
                is_first = False
            else:
                # add a new blank line between each namespace
                click.echo('\n')
                
            if namespace == multi_asic.DEFAULT_NAMESPACE:
                if service_name and service_name not in global_feature_data:
                    continue
                echo_rate_limit_config(header, cfg_db, service_name, global_feature_data)
            else:
                if service_name and service_name not in per_ns_feature_data:
                    continue
                echo_rate_limit_config(header, cfg_db, service_name, per_ns_feature_data, namespace)
    elif namespace == 'default':
        # for default/global namespace only
        echo_rate_limit_config(header, db.cfgdb, service_name, global_feature_data)
    else:
        # for a specific namespace
        echo_rate_limit_config(header, db.cfgdb_clients[namespace], service_name, per_ns_feature_data, namespace)
    

def echo_rate_limit_config(header, db, service_name, features, namespace=None):
    """Echo rate limit configuration

    Args:
        header (list): CLI headers
        db (object): Db object
        service_name (str): Nullable service name to be printed.
        features (dict): Feature data got from CONFIG DB
        namespace (str, optional): Namespace provided by user. Defaults to None.
    """
    body = []
    if service_name:
        syslog_common.service_validator(features, service_name)
        service_list = [service_name]
    else:
        service_list = features.keys()
    
    syslog_configs = db.get_table(syslog_common.SYSLOG_CONFIG_FEATURE_TABLE)
    for service in natsorted(service_list):
        if service in syslog_configs:
            entry = syslog_configs[service]
            body.append([service,
                        entry.get(syslog_common.SYSLOG_RATE_LIMIT_INTERVAL, 'N/A'),
                        entry.get(syslog_common.SYSLOG_RATE_LIMIT_BURST, 'N/A')])
        else:
            body.append([service, 'N/A', 'N/A'])
    
    if namespace:
        click.echo(f'Namespace {namespace}:')
    
    if body:
        click.echo(format(header, body))
    else:
        click.echo('N/A')
