"""Tests for DLDD configuration and operational display commands."""

import json
from unittest.mock import Mock, call

import pytest
from click.testing import CliRunner

from config.dldd import dldd as config_dldd
from show.dldd import dldd as show_dldd
from utilities_common.db import Db
from utilities_common.dldd import DLDD_CONFIG_FIELDS


def _db():
    db = object.__new__(Db)
    db.cfgdb = Mock()
    db.db = Mock()
    db.db.STATE_DB = "STATE_DB"
    return db


def _invoke_ok(command, arguments, **kwargs):
    result = CliRunner().invoke(command, arguments, **kwargs)
    assert result.exit_code == 0, result.output
    return result


def _assert_output(output, present=(), absent=()):
    for value in present:
        assert value in output
    for value in absent:
        assert value not in output


@pytest.mark.parametrize(
    "arguments,field,value",
    (
        (("threshold", "individual-max-failure", "15"), "individual_max_failure_threshold", "15"),
        (("threshold", "broken-rules-max", "8"), "broken_rules_max_threshold", "8"),
        (("polling-interval", "redis", "30"), "redis_monitor_polling_interval", "30"),
        (("polling-interval", "file", "120"), "file_monitor_polling_interval", "120"),
        (("polling-interval", "common", "60"), "common_monitor_polling_interval", "60"),
        (("source-unavailable-grace-period", "300"), "source_unavailable_grace_period", "300"),
        (("source-recovery-samples", "2"), "source_recovery_samples", "2"),
        (("inactive-fault-retention-period", "3600"), "inactive_fault_retention_period", "3600"),
        (("fault-evidence-ack-timeout", "120"), "fault_evidence_ack_timeout", "120"),
        (("active-fault-recheck-interval", "60"), "active_fault_recheck_interval", "60"),
        (("rules-inbox-settle-time", "30"), "rules_inbox_settle_time", "30"),
    ),
)
def test_config_commands_update_global_entry(arguments, field, value):
    db = _db()

    result = _invoke_ok(config_dldd, arguments, obj=db)

    db.cfgdb.mod_entry.assert_called_once_with(
        "DLDD_CONFIG",
        "global",
        {field: value},
    )
    assert field in result.output


@pytest.mark.parametrize(
    "arguments",
    (
        ("threshold", "individual-max-failure", "-1"),
        ("threshold", "broken-rules-max", "4294967296"),
        ("polling-interval", "redis", "0"),
        ("source-recovery-samples", "0"),
    ),
)
def test_config_commands_reject_invalid_values(arguments):
    db = _db()

    result = CliRunner().invoke(config_dldd, arguments, obj=db)

    assert result.exit_code != 0
    db.cfgdb.mod_entry.assert_not_called()


@pytest.mark.parametrize(
    "arguments,user_input,expected_command",
    (
        pytest.param(
            ("clear-state", "-y"),
            None,
            ["/usr/local/bin/dldd", "clear-state"],
            id="confirmed-safe-cleanup",
        ),
        pytest.param(
            ("clear-state", "--all"),
            "y\n",
            ["/usr/local/bin/dldd", "clear-state", "--all"],
            id="confirmed-full-cleanup",
        ),
        pytest.param(
            ("clear-state",),
            "n\n",
            None,
            id="operator-rejects-cleanup",
        ),
    ),
)
def test_clear_state_confirmation_and_scope(
    monkeypatch, arguments, user_input, expected_command
):
    run_command = Mock()
    monkeypatch.setattr("config.dldd.clicommon.run_command", run_command)

    result = _invoke_ok(
        config_dldd,
        arguments,
        input=user_input,
    )

    if expected_command is None:
        assert result.output.endswith("Aborted.\n")
        run_command.assert_not_called()
    else:
        run_command.assert_called_once_with(expected_command)


def test_show_config_displays_all_operator_fields():
    db = _db()
    db.cfgdb.get_table.return_value = {
        "global": {
            "individual_max_failure_threshold": "15",
            "redis_monitor_polling_interval": "30",
        }
    }
    db.db.get_all.return_value = {
        "individual_max_failure_threshold": "15",
        "redis_monitor_polling_interval": "30",
        "rules_inbox_settle_time": "45",
    }

    result = _invoke_ok(show_dldd, ("config",), obj=db)

    for description, field, unused_minimum in DLDD_CONFIG_FIELDS:
        assert description in result.output
        assert field in result.output
    assert "15" in result.output
    assert "redis_monitor_polling_interval" in result.output
    assert "Rules inbox settle time" in result.output
    assert "not set" in result.output
    assert "Effective value" in result.output
    assert "45" in result.output
    assert "unavailable" in result.output
    db.db.get_all.assert_called_once_with("STATE_DB", "DLDD_STATUS|process_state")


def _detailed_status_state():
    return {
        "state": "DEGRADED",
        "reason": "one rule degraded",
        "running_schema": "0.0.1",
        "active_rules_file": "/var/lib/sonic/dldd/rules/dld_rules.active.yaml",
        "active_rules_checksum": "sha256:1234",
        "active_rules_source": "inbox",
        "activation_result": "PASSED",
        "activation_fallback_used": "false",
        "previous_active_rules_checksum": "sha256:old",
        "local_action_default_timeout": "45",
        "async_pool_workers": "8",
        "async_pool_busy": "2",
        "async_pool_queued": "3",
        "broken_rules": json.dumps([
            {
                "rule_instance_id": "1000001@PSU0",
                "rule": "PSU_OV_FAULT",
                "version": "1.0.0",
                "correlation_key": "1000001:1:PSU0:SYMPTOM_OVER_THRESHOLD:psu",
                "state": "DEGRADED",
                "failure_count": 3,
                "last_attempt": 1745614200.0,
                "reason": "query_error: source unavailable",
            }
        ]),
        "source_status": json.dumps([
            {
                "source": "redis:STATE_DB:PSU_INFO",
                "state": "UNAVAILABLE",
                "failure_count": 2,
                "affected_rules": [1000001],
                "stale_faults": ["FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD"],
                "reason": "producer unavailable",
            }
        ]),
        "inflight_fault_evidence": json.dumps([
            {
                "rule_instance_id": "1000001@PSU0",
                "rule_id": 1000001,
                "rule": "PSU_OV_FAULT",
                "event_id": 1,
                "component_type": "PSU",
                "correlation_key": "inflight-key-that-must-not-be-rendered",
                "state": "HELD_BY_PRIMARY",
                "owning_monitor": "redis",
                "hold_deadline": 1745614300.0,
                "since": 1745614201.0,
                "reason": "local_action_wait",
                "local_action_state": {
                    "state": "WAITING_FOR_RECHECK",
                    "worker_id": "action-1",
                    "started_at": 1745614202.0,
                },
            }
        ]),
        "service_diagnostics": json.dumps([
            {
                "rule_instance_id": "1000001@PSU0",
                "monitor": "redis",
                "rule_id": 1000001,
                "correlation_key": "1000001:1:PSU0:SYMPTOM_OVER_THRESHOLD:psu",
                "state": "IN_FLIGHT",
                "reason": "primary ownership lease expired",
            }
        ]),
    }


def test_show_status_is_compact_by_default():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 109
    db.db.get_all.return_value = _detailed_status_state()

    result = _invoke_ok(show_dldd, ("status",), obj=db)

    assert len(result.output.splitlines()) == 3
    _assert_output(
        result.output,
        present=("State", "Heartbeat age", "Activation", "Rules source",
                 "DEGRADED", "11 seconds (approximate)", "PASSED", "inbox"),
        absent=("one rule degraded", "Running schema", "Active rules checksum",
                "Reason", "PSU_OV_FAULT", "redis:STATE_DB:PSU_INFO",
                "1000001@PSU0", "primary ownership lease expired"),
    )
    for value in ("DEGRADED", "11 seconds (approximate)", "PASSED", "inbox"):
        assert result.output.count(value) == 1


def test_show_status_detail_displays_service_and_diagnostics():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 109
    db.db.get_all.return_value = _detailed_status_state()

    result = _invoke_ok(show_dldd, ("status", "--detail"), obj=db)

    db.db.get_all.assert_called_once_with("STATE_DB", "DLDD_STATUS|process_state")
    db.db.get_redis_client.assert_called_once_with("STATE_DB")
    db.db.get_redis_client.return_value.ttl.assert_called_once_with("DLDD_STATUS|process_state")
    _assert_output(
        result.output,
        present=(
            "DEGRADED", "11 seconds (approximate)", "0.0.1", "sha256:1234",
            "Async collection pool", "Broken rules", "PSU_OV_FAULT",
            "Source status", "redis:STATE_DB:PSU_INFO",
            "Primary-owned fault work", "1000001@PSU0", "Local action work",
            "WAITING_FOR_RECHECK", "Service diagnostics",
            "primary ownership lease expired",
        ),
        absent=("Correlation key", "inflight-key-that-must-not-be-rendered",
                "1745614200.0"),
    )


def test_show_status_handles_missing_state():
    db = _db()
    db.db.get_all.return_value = {}

    result = _invoke_ok(show_dldd, ("status",), obj=db)

    assert result.output == "DLDD status is unavailable in STATE_DB.\n"


def _rule_status_rows():
    return [
        {
            "rule_id": 1000001,
            "rule": "PSU_OV_FAULT",
            "version": "1.0.0",
            "component": "PSU",
            "health": "OK",
            "work_items_healthy": 1,
            "work_items_total": 1,
            "work_items_omitted": 0,
            "active_faults": 1,
            "last_attempt": 1745614266.0,
            "last_success": 1745614266.0,
            "failure_count": 0,
            "reason": "",
            "work_items": [
                {
                    "rule_instance_id": "1000001@PSU0",
                    "event_id": 1,
                    "component_name": "PSU0",
                    "source_type": "redis",
                    "monitor": "redis",
                    "async": True,
                    "state": "READY",
                    "sampling_interval": 60.0,
                    "interval_source": "monitor_default",
                    "active_fault": True,
                    "last_attempt": 1745614266.0,
                    "last_success": 1745614266.0,
                    "next_due": 1745614326.0,
                    "failure_count": 0,
                    "source_id": "redis:PSU_INFO",
                    "correlation_key": "1000001:1:PSU0:redis",
                }
            ],
        },
        {
            "rule_id": 1000002,
            "rule": "FAN_SPEED_FAULT",
            "version": "2.0.0",
            "component": "FAN",
            "health": "DEGRADED",
            "work_items_healthy": 0,
            "work_items_total": 1,
            "active_faults": 0,
            "last_attempt": 1745614200.0,
            "last_success": 1745614100.0,
            "failure_count": 3,
            "reason": "source unavailable",
            "work_items": [
                {
                    "rule_instance_id": "1000002@FAN0",
                    "component_name": "FAN0",
                }
            ],
        },
    ]


def _rule_status_entries(
    checksum="sha256:test", detail_truncated="false"
):
    entries = {
        "DLDD_STATUS|process_state": {
            "active_rules_checksum": checksum,
        }
    }
    rule_keys = []
    for rule in _rule_status_rows():
        status_key = "DLDD_RULE_STATUS|rule|{}".format(rule["rule"])
        detail_key = "DLDD_RULE_DETAIL|rule|{}".format(rule["rule"])
        summary = dict(rule)
        work_items = summary.pop("work_items")
        summary.update({
            "active_rules_checksum": checksum,
            "detail_key": detail_key,
        })
        entries[status_key] = summary
        entries[detail_key] = {
            "active_rules_checksum": checksum,
            "rule_id": rule["rule_id"],
            "rule": rule["rule"],
            "work_items": json.dumps(work_items),
        }
        rule_keys.append(status_key)
    entries["DLDD_RULE_STATUS|active"] = {
        "active_rules_checksum": checksum,
        "rule_keys": json.dumps(rule_keys),
        "rule_count": str(len(rule_keys)),
        "detail_truncated": detail_truncated,
    }
    return entries


def _use_state_entries(db, entries):
    db.db.get_all.side_effect = lambda unused_database, key: entries.get(
        key, {}
    )


def _invoke_rules(entries, arguments=("rules",)):
    db = _db()
    _use_state_entries(db, entries)
    return db, _invoke_ok(show_dldd, arguments, obj=db)


def test_show_rules_default_reads_only_small_summary_hashes():
    db, result = _invoke_rules(_rule_status_entries())

    _assert_output(
        result.output,
        present=("Rule ID", "Rule", "Component", "Health", "Active faults",
                 "PSU_OV_FAULT", "FAN_SPEED_FAULT"),
        absent=("Version", "Work items", "Last attempt", "Last success",
                "Failure streak", "Reason"),
    )
    requested = [item.args[1] for item in db.db.get_all.call_args_list]
    assert "DLDD_RULE_STATUS|rule|PSU_OV_FAULT" in requested
    assert "DLDD_RULE_STATUS|rule|FAN_SPEED_FAULT" in requested
    assert not any(key.startswith("DLDD_RULE_DETAIL|rule|") for key in requested)


def test_show_rules_filters_health_component_and_no_active_fault():
    for component in ("FAN", "FAN0"):
        db, result = _invoke_rules(
            _rule_status_entries(),
            ("rules", "--health", "degraded", "--component", component,
             "--no-active-fault"),
        )
        _assert_output(
            result.output,
            present=("FAN_SPEED_FAULT", "DEGRADED"),
            absent=("Work items", "0/1", "source unavailable",
                    "1745614200.0", "PSU_OV_FAULT"),
        )
        requested = [item.args[1] for item in db.db.get_all.call_args_list]
        assert "DLDD_RULE_DETAIL|rule|PSU_OV_FAULT" not in requested
        if component == "FAN0":
            assert requested.count("DLDD_RULE_DETAIL|rule|FAN_SPEED_FAULT") == 1


def test_show_rules_filters_active_fault_and_displays_detail():
    _, result = _invoke_rules(
        _rule_status_entries(detail_truncated="true"),
        ("rules", "--active-fault", "--detail"),
    )

    assert "PSU_OV_FAULT" in result.output
    assert "FAN_SPEED_FAULT" not in result.output
    assert "Version" in result.output
    assert "Work items" in result.output
    assert "Failure streak" in result.output
    assert "Rule PSU_OV_FAULT (1000001) work items" in result.output
    assert "PSU0" in result.output
    assert "async" in result.output
    assert "60.0 (monitor_default)" in result.output
    assert "1000001@PSU0" in result.output
    assert "Correlation key" not in result.output
    assert "1000001:1:PSU0:redis" not in result.output
    assert "detail was truncated" in result.output
    assert "1745614266.0" not in result.output


def test_show_rules_rejects_stale_generation_snapshot():
    entries = _rule_status_entries(checksum="sha256:old")
    entries["DLDD_STATUS|process_state"] = {
        "active_rules_checksum": "sha256:current"
    }
    _, result = _invoke_rules(entries)

    assert "does not match the active rules generation" in result.output
    assert "PSU_OV_FAULT" not in result.output


def test_show_rules_rejects_stale_detail_generation():
    entries = _rule_status_entries()
    entries["DLDD_RULE_DETAIL|rule|FAN_SPEED_FAULT"][
        "active_rules_checksum"
    ] = "sha256:old"

    _, result = _invoke_rules(entries, ("rules", "--component", "FAN0"))

    assert "rule detail is incomplete for the active generation" in result.output
    assert "FAN_SPEED_FAULT" not in result.output


@pytest.mark.parametrize(
    "entries,expected",
    (
        ({}, "DLDD status is unavailable in STATE_DB."),
        (
            {"DLDD_STATUS|process_state": {"active_rules_checksum": "sha256:test"}},
            "DLDD rule status is unavailable in STATE_DB.",
        ),
    ),
)
def test_show_rules_handles_missing_process_or_rule_status(entries, expected):
    _, result = _invoke_rules(entries)

    assert expected in result.output


def test_show_faults_displays_and_filters_records():
    db = _db()
    db.db.keys.return_value = [
        b"FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD",
        b"FAULT_INFO|FAN0|SYMPTOM_ABNORMAL",
    ]
    db.db.get_all.side_effect = (
        {
            "producer": "dldd",
            "component_name": "FAN0",
            "symptom": "SYMPTOM_ABNORMAL",
            "status": "INACTIVE",
            "severity": "WARNING",
            "last_detection_time": "1745614200.0",
        },
        {
            "producer": "dldd",
            "component_name": "PSU0",
            "symptom": "SYMPTOM_OVER_THRESHOLD",
            "status": "ACTIVE",
            "severity": "CRITICAL",
            "rule": "PSU_OV_FAULT",
            "occurrences": "2",
            "last_detection_time": "1745614266.0",
            "description": "PSU output over voltage",
        },
    )

    result = _invoke_ok(
        show_dldd,
        ("faults", "--status", "ACTIVE", "--component", "PSU0"),
        obj=db,
    )

    db.db.keys.assert_called_once_with("STATE_DB", "FAULT_INFO|*")
    assert db.db.get_all.call_args_list == [
        call("STATE_DB", "FAULT_INFO|FAN0|SYMPTOM_ABNORMAL"),
        call("STATE_DB", "FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD"),
    ]
    _assert_output(
        result.output,
        present=("Component", "Symptom", "Status", "Severity", "Last detection",
                 "PSU0", "SYMPTOM_OVER_THRESHOLD", "ACTIVE", "CRITICAL"),
        absent=("Rule", "Occurrences", "Reason", "Description", "PSU_OV_FAULT",
                "PSU output over voltage", "FAN0", "1745614266.0"),
    )


def _detailed_fault_row():
    return {
        "producer": "dldd",
        "rule": "CURRENT_HIGH",
        "rule_id": "1000001",
        "rule_version": "1.0.0",
        "schema_version": "0.0.1",
        "active_rules_checksum": "sha256:test",
        "correlation_key": "legacy-top-level-internal-key",
        "component_type": "CURRENT_SENSOR",
        "component_name": "SENSOR0",
        "component_serial_number": "SERIAL0",
        "error_type": "POWER",
        "events": json.dumps([
            {
                "id": 1,
                "value_read": "30000",
                "correlation_key": "event-internal-key",
                "condition": {
                    "type": "comparison",
                    "value": 21000.0,
                    "correlation_key": "condition-internal-key",
                },
            }
        ]),
        "local_action_state": json.dumps({
            "state": "IDLE",
            "rule_instance_id": "1000001@SENSOR0",
            "correlation_key": "legacy-action-internal-key",
        }),
        "severity": "WARNING",
        "symptom": "SYMPTOM_OVER_THRESHOLD",
        "status": "ACTIVE",
        "origin_time": "1745614200.9",
        "last_detection_time": "1745614266.8",
        "occurrences": "1",
        "reason": "",
        "description": "Current is high",
    }


def _db_with_single_fault(
    row, key=b"FAULT_INFO|SENSOR0|SYMPTOM_OVER_THRESHOLD"
):
    db = _db()
    db.db.keys.return_value = [key]
    db.db.get_all.return_value = row
    return db


def test_show_faults_detail_decodes_nested_fields():
    db = _db_with_single_fault(_detailed_fault_row())

    result = _invoke_ok(
        show_dldd, ("faults", "--detail"), obj=db
    )

    _assert_output(
        result.output,
        present=("Fault SENSOR0 / SYMPTOM_OVER_THRESHOLD", "Producer", "dldd",
                 "Component serial number", "SERIAL0", "Events",
                 '"value_read": "30000"', "Local action state"),
        absent=("1745614266.8", "correlation_key"),
    )


def test_show_faults_json_emits_structured_documents():
    db = _db_with_single_fault(_detailed_fault_row())

    result = _invoke_ok(
        show_dldd, ("faults", "--json"), obj=db
    )

    documents = json.loads(result.output)
    assert len(documents) == 1
    fault = documents[0]
    assert (fault["component_type"], fault["component_name"], fault["rule_id"]) == (
        "CURRENT_SENSOR", "SENSOR0", 1000001,
    )
    assert (fault["origin_time"], fault["last_detection_time"]) == (
        1745614200, 1745614266,
    )
    assert fault["events"][0]["value_read"] == "30000"
    assert fault["local_action_state"] == {
        "state": "IDLE",
        "rule_instance_id": "1000001@SENSOR0",
    }
    assert "correlation_key" not in json.dumps(fault)
    assert "component_info" not in fault


def test_show_faults_ignores_rows_owned_by_other_agents():
    fault = _detailed_fault_row()
    fault["producer"] = "another-agent"
    db = _db_with_single_fault(fault)

    result = _invoke_ok(show_dldd, ("faults",), obj=db)

    assert "SENSOR0" not in result.output
    assert "SYMPTOM_OVER_THRESHOLD" not in result.output
    assert "Current is high" not in result.output


def test_show_faults_handles_empty_table():
    db = _db()
    db.db.keys.return_value = None

    result = _invoke_ok(show_dldd, ("faults",), obj=db)

    assert "Component" in result.output
    assert "Symptom" in result.output
