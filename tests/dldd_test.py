"""Tests for DLDD configuration and operational display commands."""

import json
import sys
import types
from unittest.mock import Mock, call

import pytest
from click.testing import CliRunner

from config.dldd import dldd as config_dldd
from show.dldd import (
    _compact,
    _fault_document,
    _heartbeat_age,
    _int_value,
    _json_value,
    _state_redis_client,
    _timestamp_value,
    dldd as show_dldd,
)
from utilities_common.db import Db
from utilities_common.dldd import DLDD_CONFIG_FIELDS, is_dldd_fault


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
    "value,expected",
    (
        (1745614266.999, 1745614266),
        ("1745614266.999", 1745614266),
        (-1.1, -2),
        (1745614266, 1745614266),
        (None, ""),
        ("", ""),
        ("not-a-timestamp", "not-a-timestamp"),
    ),
)
def test_timestamp_value_displays_whole_epoch_seconds(value, expected):
    assert _timestamp_value(value) == expected


def test_wire_value_helpers_preserve_scalars_and_normalize_fault_fields():
    assert _compact("already-readable") == "already-readable"
    assert _int_value("not-an-integer", default=7) == 7
    assert _timestamp_value(True) is True

    document = _fault_document(
        "FAULT_INFO|SENSOR0|SYMPTOM_ABNORMAL",
        {"source_stale": "yes"},
    )
    assert document == {
        "redis_key": "FAULT_INFO|SENSOR0|SYMPTOM_ABNORMAL",
        "source_stale": True,
    }

    document = _fault_document(
        "FAULT_INFO|UNKNOWN|SYMPTOM_ABNORMAL",
        {
            "local_action_state": json.dumps({
                "state": "IDLE",
                "correlation_key": "internal-only-key",
            }),
        },
    )
    assert document["local_action_state"] == {"state": "IDLE"}


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

    result = CliRunner().invoke(
        config_dldd,
        arguments,
        input=user_input,
    )

    assert result.exit_code == 0, result.output
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

    result = CliRunner().invoke(show_dldd, ("config",), obj=db)

    assert result.exit_code == 0, result.output
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
                "rule_instance_id": "1000001@PSU0",
                "rule": "PSU_OV_FAULT",
                "rule_id": 1000001,
                "version": "1.0.0",
                "component_name": "PSU0",
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
                "rule_instance_id": "1000001@PSU0",
                "rule_id": 1000001,
                "rule": "PSU_OV_FAULT",
                "event_id": 1,
                "component_type": "PSU",
                "component_name": "PSU0",
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
                    "wait_until": 1745614300.0,
                    "last_error": "",
                },
            }
        ]),
        "service_diagnostics": json.dumps([
            {
                "rule_instance_id": "1000001@PSU0",
                "monitor": "redis",
                "rule_id": 1000001,
                "component_name": "PSU0",
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
    assert "Correlation key" not in result.output
    assert "1000001:1:PSU0:SYMPTOM_OVER_THRESHOLD:psu" not in result.output
    assert "query_error: source unavailable" in result.output
    assert "Source status" in result.output
    assert "redis:STATE_DB:PSU_INFO" in result.output
    assert "producer unavailable" in result.output
    assert "FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD" in result.output
    assert "Affected rules" in result.output
    assert "Primary-owned fault work" in result.output
    assert "Rule instance" in result.output
    assert "1000001@PSU0" in result.output
    assert "inflight-key-that-must-not-be-rendered" not in result.output
    assert "WAITING_FOR_RECHECK" in result.output
    assert "action-1" in result.output
    assert "Local action work" in result.output
    assert "Started" in result.output
    assert "local_action_wait" in result.output
    assert "Service diagnostics" in result.output
    assert "primary ownership lease expired" in result.output
    assert "1745614200.0" not in result.output


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


@pytest.mark.parametrize("ttl", (None, -1))
def test_heartbeat_age_reports_unavailable_for_nonexpiring_status(ttl):
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = ttl

    assert _heartbeat_age(db) == "unavailable"


def test_heartbeat_age_handles_state_db_failure():
    db = _db()
    db.db.get_redis_client.side_effect = RuntimeError("STATE_DB unavailable")

    assert _heartbeat_age(db) == "unavailable"


@pytest.mark.parametrize(
    "socket_path,expected_arguments",
    (
        ("/var/run/redis/redis.sock", {
            "unix_socket_path": "/var/run/redis/redis.sock",
            "db": 6,
        }),
        ("", {"host": "127.0.0.1", "port": 6379, "db": 6}),
    ),
)
def test_state_redis_client_supports_socket_and_tcp_database_config(
    monkeypatch, socket_path, expected_arguments
):
    redis_constructor = Mock(return_value=object())
    monkeypatch.setitem(
        sys.modules,
        "redis",
        types.SimpleNamespace(Redis=redis_constructor),
    )

    from swsscommon import swsscommon

    monkeypatch.setattr(
        swsscommon.SonicDBConfig,
        "getDbId",
        staticmethod(lambda unused_database, unused_key: 6),
        raising=False,
    )
    monkeypatch.setattr(
        swsscommon.SonicDBConfig,
        "getDbSock",
        staticmethod(lambda unused_database, unused_key: socket_path),
        raising=False,
    )
    monkeypatch.setattr(
        swsscommon.SonicDBConfig,
        "getDbHostname",
        staticmethod(lambda unused_database, unused_key: "127.0.0.1"),
        raising=False,
    )
    monkeypatch.setattr(
        swsscommon.SonicDBConfig,
        "getDbPort",
        staticmethod(lambda unused_database, unused_key: 6379),
        raising=False,
    )

    _state_redis_client()

    redis_constructor.assert_called_once_with(**expected_arguments)


def test_show_status_handles_empty_optional_diagnostics():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 120
    db.db.get_all.return_value = {"state": "RUNNING"}

    result = CliRunner().invoke(show_dldd, ("status",), obj=db)

    assert result.exit_code == 0, result.output
    assert "RUNNING" in result.output
    assert "Broken rules" not in result.output
    assert "Source status" not in result.output
    assert "Primary-owned fault work" not in result.output
    assert "Service diagnostics" not in result.output
    assert "Async collection pool" not in result.output


def test_show_status_displays_compact_async_pool_metrics():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 120
    db.db.get_all.return_value = {
        "state": "RUNNING",
        "async_pool_workers": "8",
        "async_pool_busy": "2",
        "async_pool_queued": "3",
        "async_pool_avg_queue_latency_ms": "0.25",
        "async_pool_avg_execution_time_ms": "1.75",
        "async_pool_avg_utilization_percent": "12.5",
    }

    result = CliRunner().invoke(show_dldd, ("status",), obj=db)

    assert result.exit_code == 0, result.output
    assert "Async collection pool" in result.output
    assert "Workers" in result.output
    assert "Busy" in result.output
    assert "Queued" in result.output
    assert "Avg queue latency (ms)" in result.output
    assert "Avg execution time (ms)" in result.output
    assert "Avg utilization (%)" in result.output
    assert "8" in result.output
    assert "2" in result.output
    assert "3" in result.output
    assert "0.25" in result.output
    assert "1.75" in result.output
    assert "12.5" in result.output


def test_show_status_ignores_malformed_inflight_entries_without_actions():
    db = _db()
    db.db.get_redis_client.return_value.ttl.return_value = 120
    db.db.get_all.return_value = {
        "state": "RUNNING",
        "inflight_fault_evidence": json.dumps([
            "not-an-evidence-object",
            {
                "rule_instance_id": "1000001@PSU0",
                "rule_id": 1000001,
                "component_type": "PSU",
                "component_name": "PSU0",
                "state": "IN_FLIGHT",
                "local_action_state": "[]",
            },
        ]),
    }

    result = CliRunner().invoke(show_dldd, ("status",), obj=db)

    assert result.exit_code == 0, result.output
    assert "Primary-owned fault work" in result.output
    assert "PSU0" in result.output
    assert "Local action work" not in result.output


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
                    "rule_instance_id": "1000002@FAN0",
                    "event_id": 2,
                    "component_name": "FAN0",
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


def test_show_rules_default_reads_only_small_summary_hashes():
    db = _db()
    _use_state_entries(db, _rule_status_entries())

    result = CliRunner().invoke(show_dldd, ("rules",), obj=db)

    assert result.exit_code == 0, result.output
    assert "PSU_OV_FAULT" in result.output
    assert "FAN_SPEED_FAULT" in result.output
    requested = [item.args[1] for item in db.db.get_all.call_args_list]
    assert "DLDD_RULE_STATUS|rule|PSU_OV_FAULT" in requested
    assert "DLDD_RULE_STATUS|rule|FAN_SPEED_FAULT" in requested
    assert not any(key.startswith("DLDD_RULE_DETAIL|rule|") for key in requested)


def test_show_rules_filters_health_component_and_no_active_fault():
    db = _db()
    _use_state_entries(db, _rule_status_entries())

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
    assert "1745614200.0" not in result.output
    assert "PSU_OV_FAULT" not in result.output
    assert db.db.get_all.call_args_list == [
        call("STATE_DB", "DLDD_STATUS|process_state"),
        call("STATE_DB", "DLDD_RULE_STATUS|active"),
        call("STATE_DB", "DLDD_RULE_STATUS|rule|PSU_OV_FAULT"),
        call("STATE_DB", "DLDD_RULE_STATUS|rule|FAN_SPEED_FAULT"),
        call("STATE_DB", "DLDD_RULE_DETAIL|rule|FAN_SPEED_FAULT"),
    ]


def test_show_rules_filters_active_fault_and_displays_detail():
    db = _db()
    _use_state_entries(
        db, _rule_status_entries(detail_truncated="true")
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
    assert "async" in result.output
    assert "60.0 (monitor_default)" in result.output
    assert "1000001@PSU0" in result.output
    assert "Correlation key" not in result.output
    assert "1000001:1:PSU0:redis" not in result.output
    assert "detail was truncated" in result.output
    assert "1745614266.0" not in result.output


def test_show_rules_rejects_stale_generation_snapshot():
    db = _db()
    entries = _rule_status_entries(checksum="sha256:old")
    entries["DLDD_STATUS|process_state"] = {
        "active_rules_checksum": "sha256:current"
    }
    _use_state_entries(db, entries)

    result = CliRunner().invoke(show_dldd, ("rules",), obj=db)

    assert result.exit_code == 0, result.output
    assert "does not match the active rules generation" in result.output
    assert "PSU_OV_FAULT" not in result.output


def test_show_rules_rejects_malformed_rule_key_without_exception():
    db = _db()
    entries = _rule_status_entries()
    entries["DLDD_RULE_STATUS|active"].update({
        "rule_keys": '[{"not": "a key"}]',
        "rule_count": "1",
    })
    _use_state_entries(db, entries)

    result = CliRunner().invoke(show_dldd, ("rules",), obj=db)

    assert result.exit_code == 0, result.output
    assert "index is incomplete or malformed" in result.output


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
    db = _db()
    _use_state_entries(db, entries)

    result = CliRunner().invoke(show_dldd, ("rules",), obj=db)

    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_show_rules_rejects_missing_rule_summary():
    db = _db()
    entries = _rule_status_entries()
    entries.pop("DLDD_RULE_STATUS|rule|PSU_OV_FAULT")
    _use_state_entries(db, entries)

    result = CliRunner().invoke(show_dldd, ("rules",), obj=db)

    assert result.exit_code == 0, result.output
    assert "rule status is incomplete for the active generation" in result.output


def test_show_rules_accepts_direct_summary_component_match():
    db = _db()
    _use_state_entries(db, _rule_status_entries())

    result = CliRunner().invoke(
        show_dldd,
        ("rules", "--component", "FAN"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "FAN_SPEED_FAULT" in result.output
    assert "PSU_OV_FAULT" not in result.output


def test_show_rules_reuses_detail_and_reports_omitted_items():
    db = _db()
    _use_state_entries(db, _rule_status_entries())

    result = CliRunner().invoke(
        show_dldd,
        ("rules", "--component", "FAN0", "--detail"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "FAN_SPEED_FAULT" in result.output
    assert "3 additional work item(s) omitted" in result.output
    assert "detail was truncated" not in result.output
    detail_reads = [
        request
        for request in db.db.get_all.call_args_list
        if request.args[1] == "DLDD_RULE_DETAIL|rule|FAN_SPEED_FAULT"
    ]
    assert len(detail_reads) == 1


@pytest.mark.parametrize("failure_mode", ("invalid-key", "stale-detail"))
def test_show_rules_rejects_unusable_detail_during_component_filter(
    failure_mode,
):
    db = _db()
    entries = _rule_status_entries()
    summary_key = "DLDD_RULE_STATUS|rule|FAN_SPEED_FAULT"
    if failure_mode == "invalid-key":
        entries[summary_key]["detail_key"] = "NOT_A_DLDD_DETAIL_KEY"
    else:
        detail_key = entries[summary_key]["detail_key"]
        entries[detail_key]["active_rules_checksum"] = "sha256:stale"
    _use_state_entries(db, entries)

    result = CliRunner().invoke(
        show_dldd,
        ("rules", "--component", "FAN0"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "rule detail is incomplete for the active generation" in result.output


def test_show_rules_filters_component_absent_from_detail():
    db = _db()
    _use_state_entries(db, _rule_status_entries())

    result = CliRunner().invoke(
        show_dldd,
        ("rules", "--component", "NOT_PRESENT"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "PSU_OV_FAULT" not in result.output
    assert "FAN_SPEED_FAULT" not in result.output


def test_show_rules_rejects_unusable_detail_in_detail_view():
    db = _db()
    entries = _rule_status_entries()
    entries["DLDD_RULE_STATUS|rule|PSU_OV_FAULT"]["detail_key"] = "bad-key"
    _use_state_entries(db, entries)

    result = CliRunner().invoke(show_dldd, ("rules", "--detail"), obj=db)

    assert result.exit_code == 0, result.output
    assert "rule detail is incomplete for the active generation" in result.output


def test_show_faults_displays_and_filters_records():
    db = _db()
    db.db.keys.return_value = [
        b"FAULT_INFO|PSU0|SYMPTOM_OVER_THRESHOLD",
        b"FAULT_INFO|FAN0|SYMPTOM_ABNORMAL",
    ]
    db.db.get_all.side_effect = (
        {
            "producer": "dldd",
            "rule_id": "2000001",
            "schema_version": "0.0.1",
            "active_rules_checksum": "sha256:test",
            "component_type": "FAN",
            "component_name": "FAN0",
            "component_serial_number": "FAN-SERIAL",
            "symptom": "SYMPTOM_ABNORMAL",
            "status": "INACTIVE",
            "severity": "WARNING",
            "rule": "FAN_FAULT",
            "occurrences": "1",
            "last_detection_time": "1745614200.0",
            "reason": "DSE instance was authoritatively removed",
            "description": "Fan recovered",
        },
        {
            "producer": "dldd",
            "rule_id": "1000001",
            "schema_version": "0.0.1",
            "active_rules_checksum": "sha256:test",
            "component_type": "PSU",
            "component_name": "PSU0",
            "component_serial_number": "PSU-SERIAL",
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
    assert "DSE instance was authoritatively removed" not in result.output
    assert "1745614266.0" not in result.output


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
                "condition": {"type": "comparison", "value": 21000.0},
            }
        ]),
        "repair_actions": json.dumps([{"action": "ACTION_REPLACE"}]),
        "actions_taken": "[]",
        "local_action_state": json.dumps({
            "state": "IDLE",
            "correlation_key": "legacy-action-internal-key",
        }),
        "healthz_artifact": json.dumps({"state": "COMPLETED"}),
        "remote_action_time_window": "3600",
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

    result = CliRunner().invoke(
        show_dldd, ("faults", "--detail"), obj=db
    )

    assert result.exit_code == 0, result.output
    assert "Fault SENSOR0 / SYMPTOM_OVER_THRESHOLD" in result.output
    assert "Component serial number" in result.output
    assert "SERIAL0" in result.output
    assert "Events" in result.output
    assert '"value_read": "30000"' in result.output
    assert "Local action state" in result.output
    assert "Reason" in result.output
    assert "1745614266.8" not in result.output


def test_show_faults_displays_inactive_transition_reason():
    fault = _detailed_fault_row()
    fault.update({
        "status": "INACTIVE",
        "reason": "authoritative DSE expansion removed instance SENSOR0",
    })
    db = _db_with_single_fault(fault)

    result = CliRunner().invoke(
        show_dldd, ("faults", "--status", "INACTIVE"), obj=db
    )

    assert result.exit_code == 0, result.output
    assert "INACTIVE" in result.output
    assert "authoritative DSE expansion removed instance SENSOR0" in result.output


def test_show_faults_json_emits_structured_documents():
    db = _db_with_single_fault(_detailed_fault_row())

    result = CliRunner().invoke(
        show_dldd, ("faults", "--json"), obj=db
    )

    assert result.exit_code == 0, result.output
    documents = json.loads(result.output)
    assert len(documents) == 1
    fault = documents[0]
    assert fault["component_type"] == "CURRENT_SENSOR"
    assert fault["component_name"] == "SENSOR0"
    assert fault["component_serial_number"] == "SERIAL0"
    assert fault["rule_id"] == 1000001
    assert fault["origin_time"] == 1745614200
    assert fault["last_detection_time"] == 1745614266
    assert fault["reason"] == ""
    assert fault["events"][0]["value_read"] == "30000"
    assert fault["local_action_state"] == {
        "state": "IDLE",
        "rule_instance_id": "1000001@SENSOR0",
    }
    assert "correlation_key" not in fault
    assert "correlation_key" not in fault["local_action_state"]
    assert "component_info" not in fault


def test_show_faults_ignores_rows_owned_by_other_agents():
    db = _db_with_single_fault(
        {
            "producer": "another-agent",
            "rule": "FOREIGN_RULE",
            "rule_id": "1000001",
            "schema_version": "0.0.1",
            "active_rules_checksum": "sha256:foreign",
            "component_type": "FOREIGN",
            "component_name": "foreign-component",
            "symptom": "foreign-symptom",
            "status": "ACTIVE",
            "description": "foreign fault",
        },
        key=b"FAULT_INFO|foreign-component|foreign-symptom",
    )

    result = CliRunner().invoke(show_dldd, ("faults",), obj=db)

    assert result.exit_code == 0, result.output
    assert "foreign-component" not in result.output
    assert "foreign-symptom" not in result.output
    assert "foreign fault" not in result.output


def test_fault_ownership_uses_explicit_producer_marker():
    assert is_dldd_fault({"producer": "dldd"})
    assert is_dldd_fault({b"producer": b"dldd"})
    assert not is_dldd_fault({"producer": "another-agent"})
    assert not is_dldd_fault({
        "rule": "LOOKALIKE",
        "rule_id": "1000001",
        "schema_version": "0.0.1",
        "active_rules_checksum": "sha256:lookalike",
    })


def test_show_faults_handles_empty_table():
    db = _db()
    db.db.keys.return_value = None

    result = CliRunner().invoke(show_dldd, ("faults",), obj=db)

    assert result.exit_code == 0, result.output
    assert "Component" in result.output
    assert "Symptom" in result.output


def test_show_faults_applies_status_filter_independently_of_component():
    db = _db_with_single_fault(_detailed_fault_row())

    result = CliRunner().invoke(
        show_dldd,
        ("faults", "--status", "INACTIVE"),
        obj=db,
    )

    assert result.exit_code == 0, result.output
    assert "SENSOR0" not in result.output
