import click

from utilities_common.cli import AbbreviationGroup, pass_db
import utilities_common.cli as clicommon


WATCHDOG_TABLE = "WATCHDOG"
WATCHDOG_KEY = "config"
WATCHDOG_CONTROL = "/usr/local/bin/watchdog-control.sh"


@click.group(cls=AbbreviationGroup, name="watchdog")
def watchdog():
    """Configure Linux watchdog service"""
    pass


def apply_watchdog_config():
    clicommon.run_command([WATCHDOG_CONTROL], display_cmd=False)


def update_watchdog_config(db, data):
    db.cfgdb.mod_entry(WATCHDOG_TABLE, WATCHDOG_KEY, data)
    apply_watchdog_config()


@watchdog.command(name="enable", help="Enable Linux watchdog service")
@pass_db
def watchdog_enable(db):
    """Enable Linux watchdog service"""
    update_watchdog_config(db, {"enabled": "true"})
    click.echo("Linux watchdog service enabled.")


@watchdog.command(name="disable", help="Disable Linux watchdog service")
@pass_db
def watchdog_disable(db):
    """Disable Linux watchdog service"""
    update_watchdog_config(db, {"enabled": "false"})
    click.echo("Linux watchdog service disabled.")


@watchdog.command(name="identity", help="Configure watchdog identity")
@click.argument("identity", metavar="<name>", required=True)
@pass_db
def watchdog_identity(db, identity):
    """Configure watchdog identity to match /sys/class/watchdog/*/identity"""
    update_watchdog_config(db, {"identity": identity})
    click.echo("Linux watchdog identity configured.")


@watchdog.command(name="timeout", help="Configure watchdog timeout in seconds")
@click.argument("timeout", metavar="<timeout>", required=True, type=click.IntRange(min=1))
@pass_db
def watchdog_timeout(db, timeout):
    """Configure watchdog timeout in seconds"""
    update_watchdog_config(db, {"timeout": str(timeout)})
    click.echo("Linux watchdog timeout configured.")
