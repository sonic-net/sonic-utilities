import click
from tabulate import tabulate

from utilities_common.cli import AbbreviationGroup, pass_db

REDIS_KUBE_TABLE = 'KUBERNETES_MASTER'
REDIS_KUBE_KEY = 'SERVER'

KUBE_LABEL_TABLE = "KUBE_LABELS"
KUBE_LABEL_SET_KEY = "SET"


def _print_entry(data, fields):
    header = []
    body = []

    for (h, f, d) in fields:
        header.append(h)
        body.append(data[f] if f in data else d)

    click.echo(tabulate([body,], header, disable_numparse=True)) 


#
# kubernetes group ("show kubernetes ...")
#
@click.group(cls=AbbreviationGroup, name='kubernetes', invoke_without_command=False)
def kubernetes():
    pass


# cmd kubernetes server
@kubernetes.group()
def server():
    """ Server configuration """
    pass


@server.command()
@pass_db
def config(db):
    """Show kube configuration"""

    server_cfg_fields = [
            # (<header name>, <field name>, <default val>)
            ("ip", "ip" "", False),
            ("port", "port", "6443"),
            ("insecure", "insecure", "True"),
            ("disable","disable", "False")
            ]

    kube_fvs = db.cfgdb.get_entry(REDIS_KUBE_TABLE, REDIS_KUBE_KEY)
    if kube_fvs:
        _print_entry(kube_fvs, server_cfg_fields)
    else:
        print("Kubernetes server is not configured")


@server.command()
@pass_db
def status(db):
    """Show kube configuration"""
    server_state_fields = [
            # (<header name>, <field name>,  <default val>)
            ("ip", "ip" "", False),
            ("port", "port", "6443"),
            ("connected", "connected", ""),
            ("update-time", "update_time", "")
            ]


    kube_fvs = db.db.get_all(db.db.STATE_DB,
            "{}|{}".format(REDIS_KUBE_TABLE, REDIS_KUBE_KEY))
    if kube_fvs:
        _print_entry(kube_fvs, server_state_fields)
    else:
        print("Kubernetes server has no status info")


@kubernetes.command()
@pass_db
def labels(db):
    header = ["name", "value"]

    body = []
    labels = db.db.get_all(db.db.STATE_DB,
            "{}|{}".format(KUBE_LABEL_TABLE, KUBE_LABEL_SET_KEY))
    if labels:
        for (n,v) in labels.items():
            body.append([n, v])
    click.echo(tabulate(body, header, disable_numparse=True)) 

