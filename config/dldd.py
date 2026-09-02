"""Configuration commands for the device-local diagnosis daemon."""

import click

import utilities_common.cli as clicommon
from utilities_common.dldd import (
    DLDD_CONFIG_FIELD_MINIMUMS,
    DLDD_CONFIG_KEY,
    DLDD_CONFIG_TABLE,
    UINT32_MAX,
)

POLLING_INTERVAL_FIELDS = {
    "redis": "redis_monitor_polling_interval",
    "file": "file_monitor_polling_interval",
    "common": "common_monitor_polling_interval",
}


def _config_integer(field):
    return click.IntRange(
        min=DLDD_CONFIG_FIELD_MINIMUMS[field],
        max=UINT32_MAX,
    )


def _set_config(db, field, value):
    """Update one DLDD setting without replacing other operator settings."""
    db.cfgdb.mod_entry(
        DLDD_CONFIG_TABLE,
        DLDD_CONFIG_KEY,
        {field: str(value)},
    )
    click.echo("DLDD configuration '{}' set to '{}'".format(field, value))


def _setting_callback(field, argument_name):
    if argument_name == "count":
        def callback(db, count):
            _set_config(db, field, count)
    else:
        def callback(db, seconds):
            _set_config(db, field, seconds)
    return callback


def _register_settings(group, settings):
    """Register declarative single-field DLDD configuration commands."""
    for symbol, command_name, field, argument_name, help_text in settings:
        callback = _setting_callback(field, argument_name)
        callback.__name__ = symbol
        callback.__qualname__ = symbol
        callback.__doc__ = help_text
        command = group.command(command_name)(
            click.argument(argument_name, type=_config_integer(field))(
                clicommon.pass_db(callback)
            )
        )
        globals()[symbol] = command


@click.group(cls=clicommon.AbbreviationGroup)
def dldd():
    """Configure device-local diagnosis."""
    pass


@dldd.group(cls=clicommon.AbbreviationGroup)
def threshold():
    """Configure DLDD failure thresholds."""
    pass


_register_settings(
    threshold,
    (
        ("individual_max_failure", "individual-max-failure",
         "individual_max_failure_threshold", "count",
         "Set consecutive failures tolerated for an individual rule/key."),
        ("broken_rules_max", "broken-rules-max", "broken_rules_max_threshold",
         "count", "Set the broken-rule count tolerated before service failure."),
    ),
)


@dldd.command("polling-interval")
@click.argument(
    "monitor",
    type=click.Choice(tuple(POLLING_INTERVAL_FIELDS), case_sensitive=False),
)
@click.argument(
    "seconds", type=_config_integer("redis_monitor_polling_interval")
)
@clicommon.pass_db
def polling_interval(db, monitor, seconds):
    """Set a redis, file, or common monitor polling interval in seconds."""
    _set_config(db, POLLING_INTERVAL_FIELDS[monitor.lower()], seconds)


_register_settings(
    dldd,
    (
        ("source_unavailable_grace_period", "source-unavailable-grace-period",
         "source_unavailable_grace_period", "seconds",
         "Set source-unavailability grace time in seconds."),
        ("source_recovery_samples", "source-recovery-samples",
         "source_recovery_samples", "count",
         "Set successful samples required to recover a source."),
        ("inactive_fault_retention_period", "inactive-fault-retention-period",
         "inactive_fault_retention_period", "seconds",
         "Set inactive-fault retention time in seconds."),
        ("fault_evidence_ack_timeout", "fault-evidence-ack-timeout",
         "fault_evidence_ack_timeout", "seconds",
         "Set the initial fault-evidence acknowledgement timeout in seconds."),
        ("active_fault_recheck_interval", "active-fault-recheck-interval",
         "active_fault_recheck_interval", "seconds",
         "Set the active-fault recheck interval in seconds."),
        ("rules_inbox_settle_time", "rules-inbox-settle-time",
         "rules_inbox_settle_time", "seconds",
         "Set the rules-inbox stability window in seconds."),
    ),
)


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
