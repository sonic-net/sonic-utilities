import click

from utilities_common.cli import AbbreviationGroup, pass_db
from .validated_config_db_connector import ValidatedConfigDBConnector

from .utils import log

# DB Field names
KUBE_SERVER_TABLE_NAME = "KUBERNETES_MASTER"
KUBE_SERVER_TABLE_KEY = "SERVER"
KUBE_SERVER_IP = "ip"
KUBE_SERVER_PORT = "port"
KUBE_SERVER_DISABLE = "disable"
KUBE_SERVER_INSECURE = "insecure"

KUBE_STATE_SERVER_CONNECTED = "connected"
KUBE_STATE_SERVER_REACHABLE = "server_reachability"
KUBE_STATE_SERVER_IP = "server_ip"
KUBE_STATE_SERVER_TS = "last_update_ts"

KUBE_LABEL_TABLE = "KUBE_LABELS"
KUBE_LABEL_SET_KEY = "SET"

def _update_kube_server(db, field, val):
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    db_data = config_db.get_entry(KUBE_SERVER_TABLE_NAME, KUBE_SERVER_TABLE_KEY)
    def_data = {
        KUBE_SERVER_IP: "",
        KUBE_SERVER_PORT: "6443",
        KUBE_SERVER_INSECURE: "True",
        KUBE_SERVER_DISABLE: "False"
    }
    ctx = click.get_current_context()
    for f in def_data:
        if db_data and f in db_data:
            if f == field and db_data[f] != val:
                try: 
                    config_db.mod_entry(KUBE_SERVER_TABLE_NAME, KUBE_SERVER_TABLE_KEY, {field: val})
                except ValueError as e:
                    ctx.fail("Invalid ConfigDB. Error: {}".format(e))
                log.log_info("modify kubernetes server entry {}={}".format(field,val))
        else:
            # Missing field. Set to default or given value
            v = val if f == field else def_data[f]
            try:
                config_db.mod_entry(KUBE_SERVER_TABLE_NAME, KUBE_SERVER_TABLE_KEY, {f: v})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
            log.log_info("set kubernetes server entry {}={}".format(f,v))


def _label_node(dbconn, name, val=None):
    set_key = "{}|{}".format(KUBE_LABEL_TABLE, KUBE_LABEL_SET_KEY)
    client = dbconn.get_redis_client(dbconn.STATE_DB)
    client.hset(set_key, name, val if val else "false")


@click.group(cls=AbbreviationGroup)
def kubernetes():
    """kubernetes command line"""
    pass


# cmd kubernetes server
@kubernetes.group()
def server():
    """ Server configuration """
    pass


# cmd kubernetes server IP
@server.command()
@click.argument('vip', required=True)
@pass_db
def ip(db, vip):
    """Specify a kubernetes cluster VIP"""

    _update_kube_server(db, KUBE_SERVER_IP, vip)


# cmd kubernetes server Port
@server.command()
@click.argument('portval', required=True)
@pass_db
def port(db, portval):
    """Specify a kubernetes Service port"""
    val = int(portval)
    if (val <= 0) or (val >= (64 << 10)):
        click.echo('Invalid port value %s' % portval)
        sys.exit(1)
    _update_kube_server(db, KUBE_SERVER_PORT, portval)


# cmd kubernetes server insecure
@server.command()
@click.argument('option', type=click.Choice(["on", "off"]))
@pass_db
def insecure(db, option):
    """Specify a kubernetes cluster VIP access as insecure or not"""
    _update_kube_server(db, 'insecure', option == "on")


# cmd kubernetes server disable
@server.command()
@click.argument('option', type=click.Choice(["on", "off"]))
@pass_db
def disable(db, option):
    """Specify a kubernetes cluster VIP access is disabled or not"""
    _update_kube_server(db, 'disable', option == "on")


# cmd kubernetes label
@kubernetes.group()
def label():
    """ label configuration """
    pass


# cmd kubernetes label add <key> <val>
@label.command()
@click.argument('key', required=True)
@click.argument('val', required=True)
@pass_db
def add(db, key, val):
    """Add a label to this node"""
    _label_node(db.db, key, val)


# cmd kubernetes label drop <key>
@label.command()
@click.argument('key', required=True)
@pass_db
def drop(db, key):
    """Drop a label from this node"""
    _label_node(db.db, key)
