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
        "effective_config": json.dumps({
            "individual_max_failure_threshold": 15,
            "redis_monitor_polling_interval": 30,
            "rules_inbox_settle_time": 45,
        }),
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
        "rule_count": "12",
        "active_fault_count": "2",
        "rule_exception_count": "1",
        "source_exception_count": "1",
        "inflight_count": "0",
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
    }


def test_show_status_is_compact_by_default():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 109
    db.db.get_all.return_value = _detailed_status_state()

    result = _invoke_ok(show_dldd, ("status",), obj=db)

    assert len(result.output.splitlines()) == 3
    _assert_output(
        result.output,
        present=("State", "Heartbeat age", "Rules", "Faults", "Rule errors",
                 "Source errors", "DEGRADED", "11 seconds (approximate)",
                 "12", "2"),
        absent=("one rule degraded", "Running schema", "Active rules checksum",
                "Reason", "PSU_OV_FAULT", "redis:STATE_DB:PSU_INFO",
                "1000001@PSU0", "primary ownership lease expired"),
    )
    assert result.output.count("DEGRADED") == 1


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
            "Broken rules", "PSU_OV_FAULT", "Source status",
            "redis:STATE_DB:PSU_INFO", "1000001@PSU0",
        ),
        absent=("Correlation key", "Async collection pool", "Local action work",
                "1745614200.0"),
    )


def test_show_status_handles_missing_state():
    db = _db()
    db.db.get_all.return_value = {}

    result = _invoke_ok(show_dldd, ("status",), obj=db)

    assert result.output == "DLDD status is unavailable in STATE_DB.\n"


def test_show_rules_displays_count_and_only_exceptions():
    db = _db()
    db.db.get_all.return_value = _detailed_status_state()

    result = _invoke_ok(show_dldd, ("rules",), obj=db)

    _assert_output(
        result.output,
        present=("Loaded rules: 12", "PSU_OV_FAULT", "query_error"),
        absent=("Work items", "Correlation key", "DLDD_RULE_DETAIL"),
    )


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
