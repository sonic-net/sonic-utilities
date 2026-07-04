"""Operational display commands for the device-local diagnosis daemon."""

import json

import click
from tabulate import tabulate

import utilities_common.cli as clicommon


DLDD_CONFIG_TABLE = "DLDD_CONFIG"
DLDD_CONFIG_KEY = "global"
DLDD_STATUS_KEY = "DLDD_STATUS|process_state"
FAULT_INFO_PATTERN = "FAULT_INFO|*"
HEARTBEAT_TTL_SECONDS = 120

CONFIG_FIELDS = (
    ("Individual max failure threshold", "individual_max_failure_threshold"),
    ("Broken rules max threshold", "broken_rules_max_threshold"),
    ("Redis monitor polling interval", "redis_monitor_polling_interval"),
    ("File monitor polling interval", "file_monitor_polling_interval"),
    ("Common monitor polling interval", "common_monitor_polling_interval"),
    ("Source unavailable grace period", "source_unavailable_grace_period"),
    ("Source recovery samples", "source_recovery_samples"),
    ("Inactive fault retention period", "inactive_fault_retention_period"),
    ("Fault evidence ack timeout", "fault_evidence_ack_timeout"),
    ("Active fault recheck interval", "active_fault_recheck_interval"),
    ("Rules inbox settle time", "rules_inbox_settle_time"),
)

STATUS_FIELDS = (
    ("State", "state"),
    ("Reason", "reason"),
    ("Running schema", "running_schema"),
    ("Active rules file", "active_rules_file"),
    ("Active rules checksum", "active_rules_checksum"),
    ("Active rules source", "active_rules_source"),
    ("Activation result", "activation_result"),
    ("Activation fallback used", "activation_fallback_used"),
    ("Previous active rules checksum", "previous_active_rules_checksum"),
    ("Local action default timeout", "local_action_default_timeout"),
)


def _json_value(value, default):
    expected_type = type(default)
    if isinstance(value, expected_type):
        return value
    if not value:
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, expected_type) else default


def _compact(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _state_entry(db, key):
    return db.db.get_all(db.db.STATE_DB, key) or {}


def _state_redis_client():
    """Return a redis-py client for commands absent from DBConnector."""
    import redis
    from swsscommon import swsscommon

    database = "STATE_DB"
    database_key = swsscommon.SonicDBKey()
    database_id = swsscommon.SonicDBConfig.getDbId(database, database_key)
    socket_path = swsscommon.SonicDBConfig.getDbSock(database, database_key)
    if socket_path:
        return redis.Redis(unix_socket_path=socket_path, db=database_id)
    return redis.Redis(
        host=swsscommon.SonicDBConfig.getDbHostname(database, database_key),
        port=swsscommon.SonicDBConfig.getDbPort(database, database_key),
        db=database_id,
    )


def _is_dldd_fault(fault):
    """Return whether a shared FAULT_INFO row is owned by DLDD."""
    try:
        rule_id = int(fault.get("rule_id", 0))
    except (TypeError, ValueError):
        return False
    return bool(
        rule_id
        and fault.get("rule")
        and fault.get("schema_version")
        and fault.get("active_rules_checksum")
    )


def _heartbeat_age(db):
    """Return an approximate age based on the status key's specified TTL."""
    try:
        redis_client = db.db.get_redis_client(db.db.STATE_DB)
        ttl_method = getattr(redis_client, "ttl", None)
        if not callable(ttl_method):
            ttl_method = _state_redis_client().ttl
        ttl = ttl_method(DLDD_STATUS_KEY)
    except Exception:
        return "unavailable"

    if ttl is None or ttl < 0:
        return "unavailable"
    return "{} seconds (approximate)".format(max(0, HEARTBEAT_TTL_SECONDS - ttl))


@click.group(cls=clicommon.AbbreviationGroup)
def dldd():
    """Show device-local diagnosis state."""
    pass


@dldd.command("config")
@clicommon.pass_db
def config(db):
    """Show configured overrides and the effective runtime configuration."""
    config_table = db.cfgdb.get_table(DLDD_CONFIG_TABLE) or {}
    configured = config_table.get(DLDD_CONFIG_KEY, {})
    effective = _state_entry(db, DLDD_STATUS_KEY)

    rows = [
        (
            description,
            field,
            configured.get(field, "not set"),
            effective.get(field, "unavailable"),
        )
        for description, field in CONFIG_FIELDS
    ]
    click.echo(tabulate(
        rows,
        headers=(
            "Setting",
            "CONFIG_DB field",
            "Configured value",
            "Effective value",
        ),
        tablefmt="simple",
        disable_numparse=True,
    ))


@dldd.command("status")
@clicommon.pass_db
def status(db):
    """Show DLDD service state and runtime diagnostics."""
    process_state = _state_entry(db, DLDD_STATUS_KEY)
    if not process_state:
        click.echo("DLDD status is unavailable in STATE_DB.")
        return

    rows = [
        (description, process_state.get(field, ""))
        for description, field in STATUS_FIELDS
    ]
    rows.insert(1, ("Heartbeat age", _heartbeat_age(db)))
    click.echo(tabulate(
        rows,
        headers=("Field", "Value"),
        tablefmt="simple",
        disable_numparse=True,
    ))

    broken_rules = _json_value(process_state.get("broken_rules"), [])
    if broken_rules:
        click.echo("\nBroken rules")
        rule_rows = [
            (
                rule.get("rule", ""),
                rule.get("version", ""),
                rule.get("correlation_key", ""),
                rule.get("state", ""),
                rule.get("failure_count", ""),
                rule.get("last_attempt", ""),
                rule.get("reason", ""),
            )
            for rule in broken_rules
            if isinstance(rule, dict)
        ]
        click.echo(tabulate(
            rule_rows,
            headers=(
                "Rule",
                "Version",
                "Correlation key",
                "State",
                "Failures",
                "Last attempt",
                "Reason",
            ),
            tablefmt="simple",
            disable_numparse=True,
        ))

    source_status = _json_value(process_state.get("source_status"), [])
    if source_status:
        click.echo("\nSource status")
        source_rows = [
            (
                source.get("source", ""),
                source.get("state", ""),
                source.get("failure_count", ""),
                source.get("graceful", ""),
                source.get("since", ""),
                source.get("grace_deadline", ""),
                source.get("last_success", ""),
                _compact(source.get("affected_rules", [])),
                _compact(source.get("stale_faults", [])),
                source.get("reason", ""),
            )
            for source in source_status
            if isinstance(source, dict)
        ]
        click.echo(tabulate(
            source_rows,
            headers=(
                "Source",
                "State",
                "Failures",
                "Graceful",
                "Since",
                "Grace deadline",
                "Last success",
                "Affected rules",
                "Stale faults",
                "Reason",
            ),
            tablefmt="simple",
            disable_numparse=True,
        ))

    inflight = _json_value(process_state.get("inflight_fault_evidence"), [])
    if inflight:
        click.echo("\nIn-flight fault evidence")
        inflight_rows = []
        for evidence in inflight:
            if not isinstance(evidence, dict):
                continue
            action_state = _json_value(evidence.get("local_action_state"), {})
            inflight_rows.append((
                evidence.get("correlation_key", ""),
                evidence.get("state", ""),
                evidence.get("owning_monitor", ""),
                evidence.get("since", ""),
                evidence.get("hold_deadline", ""),
                action_state.get("state", "") if isinstance(action_state, dict) else "",
                action_state.get("worker_id", "") if isinstance(action_state, dict) else "",
                action_state.get("started_at", "") if isinstance(action_state, dict) else "",
                action_state.get("completed_at", "") if isinstance(action_state, dict) else "",
                action_state.get("wait_until", "") if isinstance(action_state, dict) else "",
                action_state.get("last_error", "") if isinstance(action_state, dict) else "",
                evidence.get("reason", ""),
            ))
        click.echo(tabulate(
            inflight_rows,
            headers=(
                "Correlation key",
                "State",
                "Monitor",
                "Since",
                "Hold deadline",
                "Local action",
                "Worker",
                "Action started",
                "Action completed",
                "Wait until",
                "Action error",
                "Reason",
            ),
            tablefmt="simple",
            disable_numparse=True,
        ))

    diagnostics = _json_value(process_state.get("service_diagnostics"), [])
    if diagnostics:
        click.echo("\nService diagnostics")
        diagnostic_rows = [
            (
                diagnostic.get("monitor", ""),
                diagnostic.get("correlation_key", ""),
                diagnostic.get("rule_id", ""),
                diagnostic.get("component", ""),
                diagnostic.get("state", ""),
                diagnostic.get("observed_at", ""),
                diagnostic.get("reason", ""),
            )
            for diagnostic in diagnostics
            if isinstance(diagnostic, dict)
        ]
        click.echo(tabulate(
            diagnostic_rows,
            headers=(
                "Monitor",
                "Correlation key",
                "Rule ID",
                "Component",
                "State",
                "Observed at",
                "Reason",
            ),
            tablefmt="simple",
            disable_numparse=True,
        ))


@dldd.command("faults")
@click.option(
    "status_filter",
    "--status",
    type=click.Choice(("ACTIVE", "INACTIVE", "UNSPECIFIED"), case_sensitive=False),
    help="Limit output to one fault status.",
)
@click.option("component_filter", "--component", help="Limit output to one component name.")
@clicommon.pass_db
def faults(db, status_filter, component_filter):
    """Show active and retained inactive DLDD faults."""
    keys = sorted(db.db.keys(db.db.STATE_DB, FAULT_INFO_PATTERN) or [])
    rows = []

    for key in keys:
        if isinstance(key, bytes):
            key = key.decode("utf-8", "replace")
        fault = _state_entry(db, key)
        if not _is_dldd_fault(fault):
            continue
        component_info = _json_value(fault.get("component_info"), {})
        component = component_info.get("name", "") if isinstance(component_info, dict) else ""
        symptom = fault.get("symptom", "")
        fault_status = fault.get("status", "")

        if component_filter and component != component_filter:
            continue
        if status_filter and fault_status.upper() != status_filter.upper():
            continue

        rows.append((
            component,
            symptom,
            fault_status,
            fault.get("severity", ""),
            fault.get("rule", ""),
            fault.get("occurrences", ""),
            fault.get("last_detection_time", ""),
            fault.get("description", ""),
        ))

    click.echo(tabulate(
        rows,
        headers=(
            "Component",
            "Symptom",
            "Status",
            "Severity",
            "Rule",
            "Occurrences",
            "Last detection",
            "Description",
        ),
        tablefmt="simple",
        disable_numparse=True,
    ))
