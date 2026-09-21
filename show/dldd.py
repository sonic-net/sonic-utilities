"""Operational display commands for the device-local diagnosis daemon."""

import json
import math
from typing import Any, Tuple

import click
from tabulate import tabulate

import utilities_common.cli as clicommon
from utilities_common.dldd import (
    DLDD_CONFIG_FIELDS,
    DLDD_CONFIG_KEY,
    DLDD_CONFIG_TABLE,
    DLDD_STATUS_KEY,
    is_dldd_fault,
)


FAULT_INFO_PATTERN = "FAULT_INFO|*"
HEARTBEAT_TTL_SECONDS = 120

FAULT_NESTED_FIELDS: Tuple[Tuple[str, str, Any], ...] = (
    ("events", "Events", []),
    ("repair_actions", "Repair actions", []),
    ("actions_taken", "Actions taken", []),
    ("local_action_state", "Local action state", {}),
    ("healthz_artifact", "Healthz artifact", {}),
)

STATUS_FIELDS = (
    ("State", "state"),
    ("Reason", "reason"),
    ("Running schema", "running_schema"),
    ("Active rules file", "active_rules_file"),
    ("Active rules checksum", "active_rules_checksum"),
    ("Active rules source", "active_rules_source"),
    ("Activation result", "activation_result"),
    ("Loaded rules", "rule_count"),
    ("Active faults", "active_fault_count"),
    ("Rule exceptions", "rule_exception_count"),
    ("Source exceptions", "source_exception_count"),
    ("Work in progress", "inflight_count"),
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


def _sanitize_output(value):
    """Recursively remove internal correlation keys from operator output."""
    if isinstance(value, dict):
        return {
            key: _sanitize_output(item)
            for key, item in value.items()
            if key not in ("correlation_key", b"correlation_key")
        }
    if isinstance(value, list):
        return [_sanitize_output(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_output(item) for item in value)
    return value


def _compact(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            _sanitize_output(value),
            sort_keys=True,
            separators=(",", ":"),
        )
    return value


def _rule_instance(record):
    """Return only the public rule-instance identity supplied by the producer."""
    return record.get("rule_instance_id", "")


def _bool_value(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _timestamp_value(value):
    """Display a timestamp as whole Unix epoch seconds."""
    if value in (None, "") or isinstance(value, bool):
        return "" if value in (None, "") else value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return math.floor(number) if math.isfinite(number) else value


def _int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _decode_key(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _fault_document(key, fault):
    document = dict(fault, redis_key=key)
    document.setdefault("component_name", document.pop("component", ""))
    for field, _unused_title, default in FAULT_NESTED_FIELDS:
        if field in document:
            document[field] = _json_value(document[field], default)
    for fields, transform in (
        (("origin_time", "last_detection_time"), _timestamp_value),
        (("rule_id", "occurrences", "remote_action_time_window"), _int_value),
        (("source_stale",), _bool_value),
    ):
        for field in fields:
            if field in document:
                document[field] = transform(document[field])
    return _sanitize_output(document)


def _state_entry(db, key):
    return db.db.get_all(db.db.STATE_DB, key) or {}


def _print_table(rows, headers):
    click.echo(tabulate(
        rows,
        headers=headers,
        tablefmt="simple",
        disable_numparse=True,
    ))


def _record_field(field, default="", transform=None):
    """Build a DLDD table accessor for one record field."""
    def read(record):
        value = record.get(field, default)
        return transform(value) if transform else value

    return read


def _record_value(record, accessor):
    return accessor(record) if callable(accessor) else record.get(accessor, "")


def _print_record_table(records, columns):
    """Render mapping records using one explicit DLDD output contract."""
    rows = [
        tuple(_record_value(record, accessor) for unused_header, accessor in columns)
        for record in records
        if isinstance(record, dict)
    ]
    headers = tuple(header for header, unused_accessor in columns)
    _print_table(rows, headers)


def _detail_option(help_text):
    return click.option("detail", "--detail", is_flag=True, help=help_text)


BROKEN_RULE_COLUMNS = (
    ("Rule instance", _rule_instance),
    ("Rule", "rule"),
    ("Version", "version"),
    ("State", "state"),
    ("Failures", "failure_count"),
    ("Last attempt", _record_field("last_attempt", transform=_timestamp_value)),
    ("Reason", "reason"),
)

SOURCE_STATUS_COLUMNS = (
    ("Source", "source"),
    ("State", "state"),
    ("Failures", "failure_count"),
    ("Graceful", "graceful"),
    ("Since", _record_field("since", transform=_timestamp_value)),
    ("Grace deadline", _record_field("grace_deadline", transform=_timestamp_value)),
    ("Last success", _record_field("last_success", transform=_timestamp_value)),
    ("Affected rules", _record_field("affected_rules", [], _compact)),
    ("Stale faults", _record_field("stale_faults", [], _compact)),
    ("Reason", "reason"),
)

FAULT_COLUMNS = (
    ("Component", "component_name"),
    ("Symptom", "symptom"),
    ("Status", "status"),
    ("Severity", "severity"),
    ("Rule", "rule"),
    ("Occurrences", "occurrences"),
    ("Last detection", "last_detection_time"),
    ("Reason", "reason"),
    ("Description", "description"),
)

FAULT_SUMMARY_COLUMNS = (
    ("Component", "component_name"),
    ("Symptom", "symptom"),
    ("Status", "status"),
    ("Severity", "severity"),
    ("Last detection", "last_detection_time"),
)

FAULT_DETAIL_FIELDS = (
    ("Redis key", "redis_key"),
    ("Producer", "producer"),
    ("Component type", "component_type"),
    ("Component name", "component_name"),
    ("Component serial number", "component_serial_number"),
    ("Rule", "rule"),
    ("Rule ID", "rule_id"),
    ("Rule version", "rule_version"),
    ("Schema version", "schema_version"),
    ("Active rules checksum", "active_rules_checksum"),
    ("Error type", "error_type"),
    ("Severity", "severity"),
    ("Symptom", "symptom"),
    ("Status", "status"),
    ("Origin time", "origin_time"),
    ("Last detection time", "last_detection_time"),
    ("Occurrences", "occurrences"),
    ("Remote action time window", "remote_action_time_window"),
    ("Source stale", _record_field("source_stale", False)),
    ("Reason", "reason"),
    ("Description", "description"),
)


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

    if not isinstance(ttl, int) or ttl < 0:
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
    effective = _json_value(
        _state_entry(db, DLDD_STATUS_KEY).get("effective_config"), {}
    )

    rows = [
        (
            description,
            field,
            configured.get(field, "not set"),
            effective.get(field, "unavailable"),
        )
        for description, field, unused_minimum in DLDD_CONFIG_FIELDS
    ]
    _print_table(
        rows,
        (
            "Setting",
            "CONFIG_DB field",
            "Configured value",
            "Effective value",
        ),
    )


@dldd.command("status")
@_detail_option("Show generation metadata and runtime diagnostic tables.")
@clicommon.pass_db
def status(db, detail):
    """Show compact DLDD service health."""
    process_state = _state_entry(db, DLDD_STATUS_KEY)
    if not process_state:
        click.echo("DLDD status is unavailable in STATE_DB.")
        return

    heartbeat_age = _heartbeat_age(db)
    if not detail:
        _print_table([(
            process_state.get("state", ""), heartbeat_age,
            process_state.get("rule_count", ""),
            process_state.get("active_fault_count", ""),
            process_state.get("rule_exception_count", ""),
            process_state.get("source_exception_count", ""),
        )], (
            "State", "Heartbeat age", "Rules", "Faults", "Rule errors",
            "Source errors",
        ))
        return

    rows = [
        (description, process_state.get(field, ""))
        for description, field in STATUS_FIELDS
    ]
    rows.insert(1, ("Heartbeat age", heartbeat_age))
    _print_table(rows, ("Field", "Value"))

    broken_rules = _json_value(process_state.get("broken_rules"), [])
    if broken_rules:
        click.echo("\nBroken rules")
        _print_record_table(broken_rules, BROKEN_RULE_COLUMNS)

    source_status = _json_value(process_state.get("source_status"), [])
    if source_status:
        click.echo("\nSource status")
        _print_record_table(source_status, SOURCE_STATUS_COLUMNS)


@dldd.command("rules")
@clicommon.pass_db
def rules(db):
    """Show the active rule count and exceptional rules."""

    process_state = _state_entry(db, DLDD_STATUS_KEY)
    if not process_state:
        click.echo("DLDD status is unavailable in STATE_DB.")
        return
    broken = _json_value(process_state.get("broken_rules"), [])
    click.echo("Loaded rules: {}".format(process_state.get("rule_count", 0)))
    if not broken:
        click.echo("No rule exceptions.")
        return
    _print_record_table(broken, BROKEN_RULE_COLUMNS)


@dldd.command("faults")
@click.option(
    "status_filter",
    "--status",
    type=click.Choice(("ACTIVE", "INACTIVE", "UNSPECIFIED"), case_sensitive=False),
    help="Limit output to one fault status.",
)
@click.option("component_filter", "--component", help="Limit output to one component name.")
@_detail_option("Show complete scalar metadata and decoded nested fields.")
@click.option(
    "json_output",
    "--json",
    is_flag=True,
    help="Emit selected faults as structured JSON.",
)
@clicommon.pass_db
def faults(db, status_filter, component_filter, detail, json_output):
    """Show active and retained inactive DLDD faults."""
    keys = sorted(db.db.keys(db.db.STATE_DB, FAULT_INFO_PATTERN) or [])
    faults = []

    for key in keys:
        key = _decode_key(key)
        fault = _state_entry(db, key)
        if not is_dldd_fault(fault):
            continue
        fault = _fault_document(key, fault)
        component = fault.get("component_name", "")
        fault_status = fault.get("status", "")

        if component_filter and component != component_filter:
            continue
        if status_filter and fault_status.upper() != status_filter.upper():
            continue
        faults.append(fault)

    if json_output:
        click.echo(json.dumps(faults, sort_keys=True, indent=2))
        return

    _print_record_table(
        faults,
        FAULT_COLUMNS if detail else FAULT_SUMMARY_COLUMNS,
    )

    if not detail:
        return
    for fault in faults:
        click.echo(
            "\nFault {} / {}".format(
                fault.get("component_name", ""),
                fault.get("symptom", ""),
            )
        )
        scalar_rows = [
            (label, _record_value(fault, accessor))
            for label, accessor in FAULT_DETAIL_FIELDS
        ]
        _print_table(scalar_rows, ("Field", "Value"))
        for field, title, default in FAULT_NESTED_FIELDS:
            click.echo("\n{}".format(title))
            click.echo(json.dumps(
                fault.get(field, default),
                sort_keys=True,
                indent=2,
            ))
