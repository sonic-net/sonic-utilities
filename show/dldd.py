"""Operational display commands for the device-local diagnosis daemon."""

import json
import math

import click
from tabulate import tabulate

import utilities_common.cli as clicommon
from utilities_common.dldd import (
    DLDD_CONFIG_FIELDS,
    DLDD_CONFIG_KEY,
    DLDD_CONFIG_TABLE,
    DLDD_RULE_DETAIL_PREFIX,
    DLDD_RULE_STATUS_KEY,
    DLDD_RULE_STATUS_PREFIX,
    DLDD_STATUS_KEY,
    is_dldd_fault,
)


FAULT_INFO_PATTERN = "FAULT_INFO|*"
HEARTBEAT_TTL_SECONDS = 120

FAULT_NESTED_FIELDS = (
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
    ("Activation fallback used", "activation_fallback_used"),
    ("Previous active rules checksum", "previous_active_rules_checksum"),
    ("Local action default timeout", "local_action_default_timeout"),
)

ASYNC_POOL_FIELDS = (
    ("Workers", "async_pool_workers"),
    ("Busy", "async_pool_busy"),
    ("Queued", "async_pool_queued"),
    ("Avg queue latency (ms)", "async_pool_avg_queue_latency_ms"),
    ("Avg execution time (ms)", "async_pool_avg_execution_time_ms"),
    ("Avg utilization (%)", "async_pool_avg_utilization_percent"),
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
    for field, unused_title, default in FAULT_NESTED_FIELDS:
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


def _component_name(record):
    """Return the canonical component name with the legacy field fallback."""
    return record.get("component_name", record.get("component", ""))


def _work_item_counts(record):
    return "{}/{}".format(
        record.get("work_items_healthy", 0),
        record.get("work_items_total", 0),
    )


def _collection_mode(record):
    return "async" if _bool_value(record.get("async", False)) else "inline"


def _sampling_interval(record):
    return "{} ({})".format(
        record.get("sampling_interval", ""),
        record.get("interval_source", ""),
    )


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

INFLIGHT_COLUMNS = (
    ("Rule instance", _rule_instance),
    ("Rule", "rule"),
    ("Event", "event_id"),
    ("Component type", "component_type"),
    ("State", "state"),
    ("Monitor", "owning_monitor"),
    ("Since", _record_field("since", transform=_timestamp_value)),
    ("Deadline", _record_field("hold_deadline", transform=_timestamp_value)),
    ("Reason", "reason"),
)

DIAGNOSTIC_COLUMNS = (
    ("Rule instance", _rule_instance),
    ("Monitor", "monitor"),
    ("Rule ID", "rule_id"),
    ("Component", _component_name),
    ("State", "state"),
    ("Observed at", _record_field("observed_at", transform=_timestamp_value)),
    ("Reason", "reason"),
)

RULE_COLUMNS = (
    ("Rule ID", "rule_id"),
    ("Rule", "rule"),
    ("Version", "version"),
    ("Component", "component"),
    ("Health", "health"),
    ("Work items", _work_item_counts),
    ("Active faults", _record_field("active_faults", 0)),
    ("Last attempt", _record_field("last_attempt", transform=_timestamp_value)),
    ("Last success", _record_field("last_success", transform=_timestamp_value)),
    ("Failure streak", _record_field("failure_count", 0)),
    ("Reason", "reason"),
)

RULE_SUMMARY_COLUMNS = (
    ("Rule ID", "rule_id"),
    ("Rule", "rule"),
    ("Component", "component"),
    ("Health", "health"),
    ("Active faults", _record_field("active_faults", 0)),
)

RULE_DETAIL_COLUMNS = (
    ("Rule instance", _rule_instance),
    ("Event", "event_id"),
    ("Component", _component_name),
    ("Source type", "source_type"),
    ("Monitor", "monitor"),
    ("Collection", _collection_mode),
    ("State", "state"),
    ("Interval", _sampling_interval),
    ("Active fault", _record_field("active_fault", False)),
    ("Last attempt", _record_field("last_attempt", transform=_timestamp_value)),
    ("Last success", _record_field("last_success", transform=_timestamp_value)),
    ("Next due", _record_field("next_due", transform=_timestamp_value)),
    ("Failures", _record_field("failure_count", 0)),
    ("Source ID", "source_id"),
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
            process_state.get("activation_result", ""),
            process_state.get("active_rules_source", ""),
        )], (
            "State", "Heartbeat age", "Activation", "Rules source",
        ))
        return

    rows = [
        (description, process_state.get(field, ""))
        for description, field in STATUS_FIELDS
    ]
    rows.insert(1, ("Heartbeat age", heartbeat_age))
    _print_table(rows, ("Field", "Value"))

    if any(field in process_state for unused_label, field in ASYNC_POOL_FIELDS):
        click.echo("\nAsync collection pool")
        _print_record_table([process_state], ASYNC_POOL_FIELDS)

    broken_rules = _json_value(process_state.get("broken_rules"), [])
    if broken_rules:
        click.echo("\nBroken rules")
        _print_record_table(broken_rules, BROKEN_RULE_COLUMNS)

    source_status = _json_value(process_state.get("source_status"), [])
    if source_status:
        click.echo("\nSource status")
        _print_record_table(source_status, SOURCE_STATUS_COLUMNS)

    inflight = _json_value(process_state.get("inflight_fault_evidence"), [])
    if inflight:
        click.echo("\nPrimary-owned fault work")
        action_rows = []
        for evidence in inflight:
            if not isinstance(evidence, dict):
                continue
            action_state = _json_value(evidence.get("local_action_state"), {})
            if action_state.get("state"):
                action_rows.append((
                    _rule_instance(evidence),
                    evidence.get("rule", ""),
                    action_state.get("state", ""),
                    action_state.get("worker_id", ""),
                    _timestamp_value(action_state.get("started_at", "")),
                    _timestamp_value(action_state.get("completed_at", "")),
                    _timestamp_value(action_state.get("wait_until", "")),
                    action_state.get("last_error", ""),
                ))
        _print_record_table(inflight, INFLIGHT_COLUMNS)
        if action_rows:
            click.echo("\nLocal action work")
            _print_table(
                action_rows,
                (
                    "Rule instance",
                    "Rule",
                    "State",
                    "Worker",
                    "Started",
                    "Completed",
                    "Wait until",
                    "Error",
                ),
            )

    diagnostics = _json_value(process_state.get("service_diagnostics"), [])
    if diagnostics:
        click.echo("\nService diagnostics")
        _print_record_table(diagnostics, DIAGNOSTIC_COLUMNS)


@dldd.command("rules")
@click.option(
    "health_filter",
    "--health",
    type=click.Choice(
        ("OK", "DEGRADED", "BROKEN", "SUSPENDED"),
        case_sensitive=False,
    ),
    help="Limit output to one rule health state.",
)
@click.option(
    "component_filter",
    "--component",
    help="Limit output to a component type or resolved component name.",
)
@click.option(
    "active_fault_filter",
    "--active-fault/--no-active-fault",
    default=None,
    help="Limit output based on whether the rule has an active fault.",
)
@_detail_option("Show per-event, component, and source work-item state.")
@clicommon.pass_db
def rules(
    db,
    health_filter,
    component_filter,
    active_fault_filter,
    detail,
):
    """Show active rules and their operational health."""

    process_state = _state_entry(db, DLDD_STATUS_KEY)
    if not process_state:
        click.echo("DLDD status is unavailable in STATE_DB.")
        return
    snapshot = _state_entry(db, DLDD_RULE_STATUS_KEY)
    if not snapshot:
        click.echo("DLDD rule status is unavailable in STATE_DB.")
        return
    checksum = process_state.get("active_rules_checksum", "")
    if snapshot.get("active_rules_checksum", "") != checksum:
        click.echo(
            "DLDD rule status does not match the active rules generation."
        )
        return

    rule_keys = [
        _decode_key(key)
        for key in _json_value(snapshot.get("rule_keys"), [])
    ]
    invalid_rule_key = any(
        not isinstance(key, str)
        or not key.startswith(DLDD_RULE_STATUS_PREFIX)
        or key == DLDD_RULE_STATUS_KEY
        for key in rule_keys
    )
    if (
        invalid_rule_key
        or len(rule_keys) != _int_value(snapshot.get("rule_count"), -1)
        or len(rule_keys) != len(set(rule_keys))
    ):
        click.echo("DLDD rule status index is incomplete or malformed.")
        return

    summaries = []
    for key in rule_keys:
        rule = _state_entry(db, key)
        if (
            not rule
            or rule.get("active_rules_checksum", "") != checksum
        ):
            click.echo(
                "DLDD rule status is incomplete for the active generation."
            )
            return
        summaries.append(rule)

    detail_cache = {}

    def work_items(rule):
        detail_key = _decode_key(rule.get("detail_key", ""))
        if detail_key in detail_cache:
            return detail_cache[detail_key]
        if (
            not isinstance(detail_key, str)
            or not detail_key.startswith(DLDD_RULE_DETAIL_PREFIX)
        ):
            return None
        detail = _state_entry(db, detail_key)
        if (
            not detail
            or detail.get("active_rules_checksum", "") != checksum
        ):
            return None
        items = _json_value(detail.get("work_items"), [])
        detail_cache[detail_key] = items
        return items

    selected = []
    for rule in summaries:
        health = str(rule.get("health", "")).upper()
        if health_filter and health != health_filter.upper():
            continue
        if component_filter:
            if str(rule.get("component", "")) != component_filter:
                items = work_items(rule)
                if items is None:
                    click.echo(
                        "DLDD rule detail is incomplete for the active generation."
                    )
                    return
                components = {
                    str(_component_name(item))
                    for item in items
                    if isinstance(item, dict)
                }
                if component_filter not in components:
                    continue
        has_active_fault = _int_value(rule.get("active_faults", 0)) > 0
        if (
            active_fault_filter is not None
            and has_active_fault != active_fault_filter
        ):
            continue
        selected.append(rule)

    selected.sort(
        key=lambda rule: (
            not str(rule.get("rule_id", "")).isdigit(),
            _int_value(rule.get("rule_id")),
            str(rule.get("rule", "")),
        )
    )
    _print_record_table(
        selected,
        RULE_COLUMNS if detail else RULE_SUMMARY_COLUMNS,
    )

    if not detail:
        return
    for rule in selected:
        click.echo(
            "\nRule {} ({}) work items".format(
                rule.get("rule", ""), rule.get("rule_id", "")
            )
        )
        rule_work_items = work_items(rule)
        if rule_work_items is None:
            click.echo(
                "DLDD rule detail is incomplete for the active generation."
            )
            return
        _print_record_table(rule_work_items, RULE_DETAIL_COLUMNS)
        omitted = _int_value(rule.get("work_items_omitted", 0))
        if omitted:
            click.echo(
                (
                    "{} additional work item(s) omitted from the bounded "
                    "status snapshot."
                ).format(omitted)
            )
    if _bool_value(snapshot.get("detail_truncated", False)):
        click.echo(
            "\nRule work-item detail was truncated by the daemon's publication limit."
        )


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
