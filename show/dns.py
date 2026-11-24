import click
import utilities_common.cli as clicommon
from natsort import natsorted
from tabulate import tabulate

from utilities_common.redis_transport import cli_uses_unix_socket
from swsscommon.swsscommon import ConfigDBConnector
from utilities_common.cli import pass_db


# 'dns' group ("show dns ...")
@click.group(cls=clicommon.AliasedGroup)
@click.pass_context
def dns(ctx):
    """Show details of the static DNS configuration """
    config_db = ConfigDBConnector(use_unix_socket_path=cli_uses_unix_socket())
    config_db.connect()
    ctx.obj = {'db': config_db}


# 'nameserver' subcommand ("show dns nameserver")
@dns.command()
@click.pass_context
def nameserver(ctx):
    """ Show static DNS configuration """
    header = ["Nameserver"]
    db = ctx.obj['db']

    nameservers = db.get_table('DNS_NAMESERVER')

    click.echo(tabulate([(ns,) for ns in nameservers.keys()], header, tablefmt='simple', stralign='right'))
