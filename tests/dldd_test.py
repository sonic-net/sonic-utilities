"""Tests for DLDD configuration and operational display commands."""

import json
from unittest.mock import Mock, call

import pytest
from click.testing import CliRunner

from config.dldd import dldd as config_dldd
from show.dldd import _heartbeat_age, _json_value, dldd as show_dldd
from utilities_common.db import Db


def _db():
    db = object.__new__(Db)
    db.cfgdb = Mock()
    db.db = Mock()
    db.db.STATE_DB = "STATE_DB"
    return db


@pytest.mark.parametrize(
    "value,default,expected",
    (
        ('[{"rule": "PSU_OV_FAULT"}]', [], [{"rule": "PSU_OV_FAULT"}]),
        ('{"state": "RUNNING"}', {}, {"state": "RUNNING"}),
        ([{"rule": "PSU_OV_FAULT"}], [], [{"rule": "PSU_OV_FAULT"}]),
        ({"state": "RUNNING"}, {}, {"state": "RUNNING"}),
        ("not-json", [], []),
        ('{"wrong": "shape"}', [], []),
        ("[]", {}, {}),
        (None, [], []),
    ),
)
def test_json_value_decodes_only_expected_container_type(value, default, expected):
    assert _json_value(value, default) == expected


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

    result = CliRunner().invoke(config_dldd, arguments, obj=db)

    assert result.exit_code == 0, result.output
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
        ("polling-interval", "other", "60"),
        ("source-recovery-samples", "0"),
        ("fault-evidence-ack-timeout", "0"),
        ("active-fault-recheck-interval", "0"),
        ("rules-inbox-settle-time", "0"),
    ),
)
def test_config_commands_reject_invalid_values(arguments):
    db = _db()

    result = CliRunner().invoke(config_dldd, arguments, obj=db)

    assert result.exit_code != 0
    db.cfgdb.mod_entry.assert_not_called()


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

    result = CliRunner().invoke(show_dldd, ("config",), obj=db)

    assert result.exit_code == 0, result.output
    assert "Individual max failure threshold" in result.output
    assert "individual_max_failure_threshold" in result.output
    assert "15" in result.output
    assert "redis_monitor_polling_interval" in result.output
    assert "Rules inbox settle time" in result.output
    assert "not set" in result.output
    assert "Effective value" in result.output
    assert "45" in result.output
    assert "unavailable" in result.output
    db.db.get_all.assert_called_once_with("STATE_DB", "DLDD_STATUS|process_state")


def test_show_status_displays_service_and_broken_rules():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 109
    db.db.get_all.return_value = {
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
        "broken_rules": json.dumps([
            {
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
                "graceful": False,
                "since": 1745614100.0,
                "grace_deadline": 1745614400.0,
                "last_success": 1745614000.0,
                "affected_rules": [1000001],
                "stale_faults": ["FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD"],
                "reason": "producer unavailable",
            }
        ]),
        "inflight_fault_evidence": json.dumps([
            {
                "correlation_key": "1000001:1:PSU0:SYMPTOM_OVER_THRESHOLD:psu",
                "state": "HELD_BY_PRIMARY",
                "owning_monitor": "redis",
                "hold_deadline": 1745614300.0,
                "since": 1745614201.0,
                "reason": "local_action_wait",
                "local_action_state": {
                    "state": "WAITING_FOR_RECHECK",
                    "worker_id": "action-1",
                    "started_at": 1745614202.0,
                    "wait_until": 1745614300.0,
                    "last_error": "",
                },
            }
        ]),
        "service_diagnostics": json.dumps([
            {
                "monitor": "redis",
                "correlation_key": "1000001:1:PSU0:SYMPTOM_OVER_THRESHOLD:psu",
                "state": "IN_FLIGHT",
                "observed_at": 1745614400.0,
                "reason": "primary ownership lease expired",
            }
        ]),
    }

    result = CliRunner().invoke(show_dldd, ("status",), obj=db)

    assert result.exit_code == 0, result.output
    db.db.get_all.assert_called_once_with("STATE_DB", "DLDD_STATUS|process_state")
    db.db.get_redis_client.assert_called_once_with("STATE_DB")
    db.db.get_redis_client.return_value.ttl.assert_called_once_with("DLDD_STATUS|process_state")
    assert "DEGRADED" in result.output
    assert "11 seconds (approximate)" in result.output
    assert "0.0.1" in result.output
    assert "sha256:1234" in result.output
    assert "Active rules source" in result.output
    assert "inbox" in result.output
    assert "Activation result" in result.output
    assert "PASSED" in result.output
    assert "Activation fallback used" in result.output
    assert "Previous active rules checksum" in result.output
    assert "sha256:old" in result.output
    assert "45" in result.output
    assert "Broken rules" in result.output
    assert "PSU_OV_FAULT" in result.output
    assert "1000001:1:PSU0:SYMPTOM_OVER_THRESHOLD:psu" in result.output
    assert "query_error: source unavailable" in result.output
    assert "Source status" in result.output
    assert "redis:STATE_DB:PSU_INFO" in result.output
    assert "producer unavailable" in result.output
    assert "FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD" in result.output
    assert "Affected rules" in result.output
    assert "In-flight fault evidence" in result.output
    assert "WAITING_FOR_RECHECK" in result.output
    assert "action-1" in result.output
    assert "Action started" in result.output
    assert "local_action_wait" in result.output
    assert "Service diagnostics" in result.output
    assert "primary ownership lease expired" in result.output


def test_show_status_handles_missing_state():
    db = _db()
    db.db.get_all.return_value = {}

    result = CliRunner().invoke(show_dldd, ("status",), obj=db)

    assert result.exit_code == 0, result.output
    assert result.output == "DLDD status is unavailable in STATE_DB.\n"


def test_heartbeat_age_uses_redis_client_when_dbconnector_has_no_ttl(monkeypatch):
    class DBConnector(object):
        pass

    db = _db()
    db.db.get_redis_client.return_value = DBConnector()
    redis_client = Mock()
    redis_client.ttl.return_value = 90
    monkeypatch.setattr(
        "show.dldd._state_redis_client", lambda: redis_client
    )

    assert _heartbeat_age(db) == "30 seconds (approximate)"
    redis_client.ttl.assert_called_once_with("DLDD_STATUS|process_state")


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
                    "event_id": 1,
                    "component": "PSU0",
                    "source_type": "redis",
                    "monitor": "redis",
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
                    "reason": "",
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
            "work_items_omitted": 3,
            "active_faults": 0,
            "last_attempt": 1745614200.0,
            "last_success": 1745614100.0,
            "failure_count": 3,
            "reason": "source unavailable",
            "work_items": [
                {
                    "event_id": 2,
                    "component": "FAN0",
                    "source_type": "i2c",
                    "monitor": "common",
                    "state": "DEGRADED",
                    "sampling_interval": 10.0,
                    "interval_source": "event",
                    "active_fault": False,
                    "last_attempt": 1745614200.0,
                    "last_success": 1745614100.0,
                    "next_due": 1745614210.0,
                    "failure_count": 3,
                    "source_id": "i2c:fan0",
                    "correlation_key": "1000002:2:FAN0:i2c",
                    "reason": "source unavailable",
                }
            ],
        },
    ]


def test_show_rules_filters_health_component_and_no_active_fault():
    db = _db()
    db.db.get_all.side_effect = (
        {"active_rules_checksum": "sha256:test"},
        {
            "active_rules_checksum": "sha256:test",
            "rules": json.dumps(_rule_status_rows()),
            "detail_truncated": "false",
        },
    )

    result = CliRunner().invoke(
        show_dldd,
        (
            "rules",
            "--health",
            "degraded",
            "--component",
            "FAN0",
            "--no-active-fault",
        ),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "FAN_SPEED_FAULT" in result.output
    assert "DEGRADED" in result.output
    assert "0/1" in result.output
    assert "source unavailable" in result.output
    assert "PSU_OV_FAULT" not in result.output
    assert db.db.get_all.call_args_list == [
        call("STATE_DB", "DLDD_STATUS|process_state"),
        call("STATE_DB", "DLDD_RULE_STATUS|active"),
    ]


def test_show_rules_filters_active_fault_and_displays_detail():
    db = _db()
    db.db.get_all.side_effect = (
        {"active_rules_checksum": "sha256:test"},
        {
            "active_rules_checksum": "sha256:test",
            "rules": json.dumps(_rule_status_rows()),
            "detail_truncated": "true",
        },
    )

    result = CliRunner().invoke(
        show_dldd,
        ("rules", "--active-fault", "--detail"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "PSU_OV_FAULT" in result.output
    assert "FAN_SPEED_FAULT" not in result.output
    assert "Rule PSU_OV_FAULT (1000001) work items" in result.output
    assert "PSU0" in result.output
    assert "60.0 (monitor_default)" in result.output
    assert "1000001:1:PSU0:redis" in result.output
    assert "detail was truncated" in result.output


def test_show_rules_rejects_stale_generation_snapshot():
    db = _db()
    db.db.get_all.side_effect = (
        {"active_rules_checksum": "sha256:current"},
        {
            "active_rules_checksum": "sha256:old",
            "rules": json.dumps(_rule_status_rows()),
        },
    )

    result = CliRunner().invoke(show_dldd, ("rules",), obj=db)

    assert result.exit_code == 0, result.output
    assert "does not match the active rules generation" in result.output
    assert "PSU_OV_FAULT" not in result.output


def test_show_faults_displays_and_filters_records():
    db = _db()
    db.db.keys.return_value = [
        b"FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD",
        b"FAULT_INFO|FAN0|SYMPTOM_ABNORMAL",
    ]
    db.db.get_all.side_effect = (
        {
            "rule_id": "2000001",
            "schema_version": "0.0.1",
            "active_rules_checksum": "sha256:test",
            "component_info": json.dumps({"name": "FAN0"}),
            "symptom": "SYMPTOM_ABNORMAL",
            "status": "INACTIVE",
            "severity": "WARNING",
            "rule": "FAN_FAULT",
            "occurrences": "1",
            "last_detection_time": "1745614200.0",
            "description": "Fan recovered",
        },
        {
            "rule_id": "1000001",
            "schema_version": "0.0.1",
            "active_rules_checksum": "sha256:test",
            "component_info": json.dumps({"name": "PSU0"}),
            "symptom": "SYMPTOM_OVER_THRESHOLD",
            "status": "ACTIVE",
            "severity": "CRITICAL",
            "rule": "PSU_OV_FAULT",
            "occurrences": "2",
            "last_detection_time": "1745614266.0",
            "description": "PSU output over voltage",
        },
    )

    result = CliRunner().invoke(
        show_dldd,
        ("faults", "--status", "ACTIVE", "--component", "PSU0"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    db.db.keys.assert_called_once_with("STATE_DB", "FAULT_INFO|*")
    assert db.db.get_all.call_args_list == [
        call("STATE_DB", "FAULT_INFO|FAN0|SYMPTOM_ABNORMAL"),
        call("STATE_DB", "FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD"),
    ]
    assert "PSU0" in result.output
    assert "PSU_OV_FAULT" in result.output
    assert "PSU output over voltage" in result.output
    assert "FAN0" not in result.output


def test_show_faults_ignores_rows_owned_by_other_agents():
    db = _db()
    db.db.keys.return_value = [b"FAULT_INFO|foreign-component|foreign-symptom"]
    db.db.get_all.return_value = {
        "component_info": json.dumps({"name": "foreign-component"}),
        "symptom": "foreign-symptom",
        "status": "ACTIVE",
        "description": "foreign fault",
    }

    result = CliRunner().invoke(show_dldd, ("faults",), obj=db)

    assert result.exit_code == 0, result.output
    assert "foreign-component" not in result.output
    assert "foreign-symptom" not in result.output
    assert "foreign fault" not in result.output


def test_show_faults_handles_empty_table():
    db = _db()
    db.db.keys.return_value = None

    result = CliRunner().invoke(show_dldd, ("faults",), obj=db)

    assert result.exit_code == 0, result.output
    assert "Component" in result.output
    assert "Symptom" in result.output
