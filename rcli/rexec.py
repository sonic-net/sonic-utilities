import os
import click
import paramiko
import sys

from .linecard import Linecard
from rcli import utils as rcli_utils
from sonic_py_common import device_info

@click.command()
@click.argument('linecard_names', nargs=-1, type=str, required=True)
@click.option('-c', '--command', type=str, required=True)
@click.option('-u', '--username', type=str, default=None, help="Username for login")
def cli(linecard_names, command, username):
    """
    Executes a command on one or many linecards

    :param linecard_names: A list of linecard names to execute the command on, 
        use `all` to execute on all linecards.
    :param command: The command to execute on the linecard(s)
    :param username: The username to use to login to the linecard(s)
    """
    if not device_info.is_chassis():
        click.echo("This commmand is only supported Chassis")
        sys.exit(1)

    if not username:
        username = os.getlogin()
    password = rcli_utils.get_password(username)

    if list(linecard_names) == ["all"]:
        # Get all linecard names using autocompletion helper
        module_names = sorted(rcli_utils.get_all_linecards(None, None, ""))
    else:
        module_names = linecard_names

    linecards = []
    # Iterate through each linecard, check if the login was successful
    for module_name in module_names:
        linecard = Linecard(module_name, username, password)
        if not linecard.connection:
            click.echo(f"Failed to connect to {module_name} with username {username}")
            sys.exit(1)
        linecards.append(linecard)

    for linecard in linecards:
        if linecard.connection:
            click.echo(f"======== {linecard.module_name}|{linecard.hostname} output: ========")
            click.echo(linecard.execute_cmd(command))


if __name__ == "__main__":
    cli(prog_name='rexec')
