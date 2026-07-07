"""Configuration commands for the device-local diagnosis daemon."""

import click

import utilities_common.cli as clicommon


DLDD_CONFIG_TABLE = "DLDD_CONFIG"
DLDD_CONFIG_KEY = "global"

UINT32_MAX = (1 << 32) - 1
NON_NEGATIVE_INTEGER = click.IntRange(min=0, max=UINT32_MAX)
POSITIVE_INTEGER = click.IntRange(min=1, max=UINT32_MAX)

POLLING_INTERVAL_FIELDS = {
    "redis": "redis_monitor_polling_interval",
    "file": "file_monitor_polling_interval",
    "common": "common_monitor_polling_interval",
}


def _set_config(db, field, value):
    """Update one DLDD setting without replacing other operator settings."""
    db.cfgdb.mod_entry(
        DLDD_CONFIG_TABLE,
        DLDD_CONFIG_KEY,
        {field: str(value)},
    )
    click.echo("DLDD configuration '{}' set to '{}'".format(field, value))


@click.group(cls=clicommon.AbbreviationGroup)
def dldd():
    """Configure device-local diagnosis."""
    pass


@dldd.group(cls=clicommon.AbbreviationGroup)
def threshold():
    """Configure DLDD failure thresholds."""
    pass


@threshold.command("individual-max-failure")
@click.argument("count", type=NON_NEGATIVE_INTEGER)
@clicommon.pass_db
def individual_max_failure(db, count):
    """Set consecutive failures tolerated for an individual rule/key."""
    _set_config(db, "individual_max_failure_threshold", count)


@threshold.command("broken-rules-max")
@click.argument("count", type=NON_NEGATIVE_INTEGER)
@clicommon.pass_db
def broken_rules_max(db, count):
    """Set the broken-rule count tolerated before service failure."""
    _set_config(db, "broken_rules_max_threshold", count)


@dldd.command("polling-interval")
@click.argument(
    "monitor",
    type=click.Choice(tuple(POLLING_INTERVAL_FIELDS), case_sensitive=False),
)
@click.argument("seconds", type=POSITIVE_INTEGER)
@clicommon.pass_db
def polling_interval(db, monitor, seconds):
    """Set a redis, file, or common monitor polling interval in seconds."""
    _set_config(db, POLLING_INTERVAL_FIELDS[monitor.lower()], seconds)


@dldd.command("source-unavailable-grace-period")
@click.argument("seconds", type=NON_NEGATIVE_INTEGER)
@clicommon.pass_db
def source_unavailable_grace_period(db, seconds):
    """Set source-unavailability grace time in seconds."""
    _set_config(db, "source_unavailable_grace_period", seconds)


@dldd.command("source-recovery-samples")
@click.argument("count", type=POSITIVE_INTEGER)
@clicommon.pass_db
def source_recovery_samples(db, count):
    """Set successful samples required to recover a source."""
    _set_config(db, "source_recovery_samples", count)


@dldd.command("inactive-fault-retention-period")
@click.argument("seconds", type=NON_NEGATIVE_INTEGER)
@clicommon.pass_db
def inactive_fault_retention_period(db, seconds):
    """Set inactive-fault retention time in seconds."""
    _set_config(db, "inactive_fault_retention_period", seconds)


@dldd.command("fault-evidence-ack-timeout")
@click.argument("seconds", type=POSITIVE_INTEGER)
@clicommon.pass_db
def fault_evidence_ack_timeout(db, seconds):
    """Set the initial fault-evidence acknowledgement timeout in seconds."""
    _set_config(db, "fault_evidence_ack_timeout", seconds)


@dldd.command("active-fault-recheck-interval")
@click.argument("seconds", type=POSITIVE_INTEGER)
@clicommon.pass_db
def active_fault_recheck_interval(db, seconds):
    """Set the active-fault recheck interval in seconds."""
    _set_config(db, "active_fault_recheck_interval", seconds)


@dldd.command("rules-inbox-settle-time")
@click.argument("seconds", type=POSITIVE_INTEGER)
@clicommon.pass_db
def rules_inbox_settle_time(db, seconds):
    """Set the rules-inbox stability window in seconds."""
    _set_config(db, "rules_inbox_settle_time", seconds)


@dldd.command("clear-state")
@click.option(
    "--all",
    "clear_all",
    is_flag=True,
    help=(
        "Also remove DLDD-owned FAULT_INFO rows and diagnostic artifacts. "
        "Rules and configuration are preserved."
    ),
)
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation prompt.")
def clear_state(clear_all, yes):
    """Stop DLDD, clear daemon-owned runtime state, and restart if active."""

    scope = "all DLDD runtime state, faults, and artifacts" if clear_all else (
        "DLDD persisted state and status telemetry"
    )
    if not yes and not click.confirm("Clear {}?".format(scope)):
        click.echo("Aborted.")
        return
    command = ["/usr/local/bin/dldd", "clear-state"]
    if clear_all:
        command.append("--all")
    clicommon.run_command(command)
