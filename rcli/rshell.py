import os
import click
import paramiko
import sys

from .linecard import Linecard
from sonic_py_common import device_info
from rcli import utils as rcli_utils


@click.command()
@click.argument('linecard_name', type=str, autocompletion=rcli_utils.get_all_linecards)
@click.option('-u', '--username', type=str, default=None, help="Username for login")
def cli(linecard_name, username):
    """
    Open interactive shell for one linecard

    :param linecard_name: The name of the linecard to connect to
    """
    if not device_info.is_chassis():
        click.echo("This commmand is only supported Chassis")
        sys.exit(1)

    if not username:
        username = os.getlogin()
    password = rcli_utils.get_password(username)

    try:
        linecard = Linecard(linecard_name, username, password)
        if linecard.connection:
            click.echo(f"Connecting to {linecard.module_name}")
            # If connection was created, connection exists.
            # Otherwise, user will see an error message.
            linecard.start_shell()
            click.echo("Connection Closed")
    except paramiko.ssh_exception.AuthenticationException:
        click.echo(
            f"Login failed on '{linecard.module_name}' with username '{linecard.username}'")


if __name__=="__main__":
    cli(prog_name='rshell')
