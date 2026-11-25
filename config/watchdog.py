import json

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
    previous = db.cfgdb.get_entry(WATCHDOG_TABLE, WATCHDOG_KEY) or {}
    candidate = dict(previous)
    candidate.update(data)
    if data.get("enabled") != "false":
        clicommon.run_command(
            [WATCHDOG_CONTROL, "--validate", json.dumps(candidate)], display_cmd=False
        )
    db.cfgdb.mod_entry(WATCHDOG_TABLE, WATCHDOG_KEY, data)
    try:
        apply_watchdog_config()
    except SystemExit:
        # Restore the previous configuration and make a best effort to restore
        # its runtime state if hardware programming or service startup failed.
        db.cfgdb.set_entry(WATCHDOG_TABLE, WATCHDOG_KEY, previous or None)
        clicommon.run_command([WATCHDOG_CONTROL], display_cmd=False, ignore_error=True)
        raise


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


@watchdog.command(name="timeout", help="Configure total watchdog timeout until final expiry")
@click.argument("timeout", metavar="<timeout>", required=True, type=click.IntRange(min=1, max=2147483647))
@click.option("--pretimeout", type=click.IntRange(min=0, max=2147483647),
              help="Also configure the interval before final expiry, in the same update.")
@pass_db
def watchdog_timeout(db, timeout, pretimeout):
    """Configure the total timeout from the last keepalive to final expiry."""
    data = {"timeout": str(timeout)}
    if pretimeout is not None:
        data["pretimeout"] = str(pretimeout)
    update_watchdog_config(db, data)
    click.echo("Linux watchdog timeout configured.")


@watchdog.command(name="pretimeout", help="Configure the interval between the early event and final expiry")
@click.argument("pretimeout", metavar="<pretimeout>", required=True,
                type=click.IntRange(min=0, max=2147483647))
@pass_db
def watchdog_pretimeout(db, pretimeout):
    """Configure pretimeout in seconds; zero disables the early event."""
    update_watchdog_config(db, {"pretimeout": str(pretimeout)})
    click.echo("Linux watchdog pretimeout configured.")
