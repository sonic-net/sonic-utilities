import os
from unittest import mock

import click
import pytest
from click.testing import CliRunner

import config.main as config
import config.bridge_port_protection as policy
import show.main as show
import show.bridge_port_protection as status
from utilities_common.db import Db


@pytest.fixture
def cli(monkeypatch):
    db = Db()
    db.cfgdb.set_entry("PORTCHANNEL", "PortChannel0", {"admin_status": "up"})
    monkeypatch.setattr(policy, "YANG_DIR", os.environ.get("SONIC_YANG_TEST_DIR", policy.YANG_DIR))
    return CliRunner(), db


def configure(cli, key, value=None, interface="PortChannel0"):
    runner, db = cli
    args = [interface, key] + ([] if value is None else ["--", value])
    return runner.invoke(config.config.commands["portchannel"].commands["protection"],
                         args, obj={"db": db.cfgdb})


@pytest.mark.parametrize("key,value,stored", [
    ("protection_mode", "software", "SOFTWARE"),
    ("protection_mode", "SOFTWARE", "SOFTWARE"),
    ("admin_mode", "auto", "AUTO"),
    ("admin_mode", "primary", "PRIMARY"),
    ("admin_mode", "protection", "PROTECTION"),
    ("revertive", "true", "true"),
    ("revertive", "FALSE", "false"),
    ("wait_to_restore_time_ms", "0", "0"),
    ("wait_to_restore_time_ms", "5000", "5000"),
    ("wait_to_restore_time_ms", "4294967295", "4294967295"),
])
def test_valid_policy_and_materialized_defaults(cli, key, value, stored):
    result = configure(cli, key, value)
    assert result.exit_code == 0, result.output
    expected = dict(policy.DEFAULTS)
    expected[key] = stored
    assert cli[1].cfgdb.get_entry(policy.TABLE, "PortChannel0") == expected


def test_exact_interface_syntax_preserves_other_fields(cli, monkeypatch):
    runner, db = cli
    monkeypatch.setattr(policy, "ConfigDBConnector", lambda **kwargs: db.cfgdb)
    monkeypatch.setattr(db.cfgdb, "connect", lambda: None)
    monkeypatch.setattr(policy.multi_asic, "is_multi_asic", lambda: False)
    group = config.config.get_command(click.Context(config.config), "portchannel0")
    for key, value in [("protection_mode", "software"), ("admin_mode", "auto"),
                       ("revertive", "false"), ("wait_to_restore_time_ms", "5000")]:
        result = runner.invoke(group, ["protection", key, value])
        assert result.exit_code == 0, result.output
    assert db.cfgdb.get_entry(policy.TABLE, "PortChannel0") == {
        **policy.DEFAULTS, "wait_to_restore_time_ms": "5000"
    }


@pytest.mark.parametrize("key,value", [
    ("protection_mode", "hardware"), ("admin_mode", "invalid"),
    ("revertive", "yes"), ("wait_to_restore_time_ms", "-1"),
    ("wait_to_restore_time_ms", "4294967296"), ("wait_to_restore_time_ms", "1.5"),
    ("wait_to_restore_time_ms", " 1"), ("wait_to_restore_time_ms", "abc"),
    ("wait_to_restore_time_ms", "1" * 100), ("convergence_mode", "AUTO"),
])
def test_invalid_policy_has_no_write(cli, key, value):
    result = configure(cli, key, value)
    assert result.exit_code != 0
    assert not cli[1].cfgdb.get_entry(policy.TABLE, "PortChannel0")


@pytest.mark.parametrize("interface", ["PortChannel1", "Ethernet0", "PortChannel0.100"])
def test_invalid_or_missing_interface(cli, interface):
    assert configure(cli, "admin_mode", "auto", interface).exit_code != 0
    assert not cli[1].cfgdb.get_table(policy.TABLE)


def test_missing_value(cli):
    result = configure(cli, "admin_mode")
    assert result.exit_code != 0
    assert "A value is required" in result.output


def test_delete_is_idempotent_and_rejects_value(cli):
    assert configure(cli, "admin_mode", "primary").exit_code == 0
    result = configure(cli, "delete", "auto")
    assert result.exit_code != 0
    assert cli[1].cfgdb.get_entry(policy.TABLE, "PortChannel0")
    assert configure(cli, "delete").exit_code == 0
    assert configure(cli, "delete").exit_code == 0
    assert not cli[1].cfgdb.get_entry(policy.TABLE, "PortChannel0")


@pytest.mark.parametrize("adhoc", [True, False])
@pytest.mark.parametrize("entry", [{}, {"NULL": "NULL"}, dict(policy.DEFAULTS)])
def test_portchannel_delete_requires_protection_removal(cli, monkeypatch, adhoc, entry):
    runner, db = cli
    monkeypatch.setattr(config, "ADHOC_VALIDATION", adhoc)
    # Exercise the dependency check independently of YANG/GCU backend writes.
    monkeypatch.setattr(config, "ValidatedConfigDBConnector", lambda connector: connector)
    db.cfgdb.set_entry(policy.TABLE, "PortChannel0", entry)
    before = dict(db.cfgdb.get_table("PORTCHANNEL"))
    command = config.config.commands["portchannel"].commands["del"]
    result = runner.invoke(command, ["PortChannel0"], obj={"db": db.cfgdb})
    assert result.exit_code != 0, result.output
    assert "Remove protection configuration" in result.output
    assert db.cfgdb.get_table("PORTCHANNEL") == before
    assert "PortChannel0" in db.cfgdb.get_table(policy.TABLE)

    assert configure(cli, "delete").exit_code == 0
    # A different protected PortChannel must not block this deletion.
    db.cfgdb.set_entry(policy.TABLE, "PortChannel1", {})
    result = runner.invoke(command, ["PortChannel0"], obj={"db": db.cfgdb})
    assert result.exit_code == 0, result.output
    assert "PortChannel0" not in db.cfgdb.get_table("PORTCHANNEL")
    assert "PortChannel1" in db.cfgdb.get_table(policy.TABLE)


def test_yang_validation_rejects_stale_unknown_field(cli):
    cli[1].cfgdb.set_entry(policy.TABLE, "PortChannel0", {"convergence_mode": "AUTO"})
    result = configure(cli, "admin_mode", "auto")
    assert result.exit_code != 0
    assert "Failed to configure" in result.output
    assert cli[1].cfgdb.get_entry(policy.TABLE, "PortChannel0") == {"convergence_mode": "AUTO"}


def test_missing_yang_model_fails_closed(cli, monkeypatch):
    validator = mock.Mock(tablesWithOutYang={policy.TABLE: {}})
    monkeypatch.setattr(policy.sonic_yang, "SonicYang", lambda *args, **kwargs: validator)
    result = configure(cli, "admin_mode", "auto")
    assert result.exit_code != 0
    assert "Install the bridge-port protection YANG model" in result.output
    assert not cli[1].cfgdb.get_entry(policy.TABLE, "PortChannel0")


def test_save_failure_is_reported(cli, monkeypatch):
    monkeypatch.setattr(cli[1].cfgdb, "set_entry", mock.Mock(side_effect=RuntimeError("write failed")))
    result = configure(cli, "admin_mode", "auto")
    assert result.exit_code != 0
    assert "write failed" in result.output


def test_dynamic_group_preserves_existing_commands_and_rejects_unknown():
    ctx = click.Context(config.config)
    assert config.config.get_command(ctx, "portchannel") is config.config.commands["portchannel"]
    assert config.config.get_command(ctx, "unknown-command") is None


def test_dynamic_group_requires_namespace_on_multi_asic(cli, monkeypatch):
    monkeypatch.setattr(policy.multi_asic, "is_multi_asic", lambda: True)
    result = cli[0].invoke(policy.interface_group("portchannel0"), ["protection", "admin_mode", "auto"])
    assert result.exit_code != 0
    assert "Specify --namespace" in result.output


def test_dynamic_group_uses_explicit_namespace(cli, monkeypatch):
    monkeypatch.setattr(policy.multi_asic, "is_multi_asic", lambda: True)
    monkeypatch.setattr(policy.multi_asic_util, "multi_asic_ns_choices", lambda: ["asic0"])
    connector = mock.Mock(return_value=cli[1].cfgdb)
    monkeypatch.setattr(policy, "ConfigDBConnector", connector)
    monkeypatch.setattr(cli[1].cfgdb, "connect", lambda: None)
    result = cli[0].invoke(policy.interface_group("portchannel0"),
                           ["--namespace", "asic0", "protection", "admin_mode", "auto"])
    assert result.exit_code == 0, result.output
    connector.assert_called_once_with(use_unix_socket_path=True, namespace="asic0")


def state_client(entries):
    conn = mock.Mock(STATE_DB="STATE_DB")
    conn.keys.return_value = [status.TABLE + "|" + name for name in entries]
    conn.get_all.side_effect = lambda db, key: entries[key.split("|", 1)[1]]
    return conn


def show_rows(cli, entries, args=None):
    cli[1].db_clients = {"": state_client(entries)}
    return cli[0].invoke(show.cli.commands["bridge-port-protection"], args or [], obj=cli[1])


def test_show_intent_and_path_are_distinct(cli, monkeypatch):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    result = show_rows(cli, {
        "PortChannel10": {"protection_state": "PROTECTION", "admin_mode": "AUTO"},
        "PortChannel2": {"admin_mode": "PRIMARY"},
    })
    assert result.exit_code == 0, result.output
    assert "INTERFACE" in result.output and "ADMIN_MODE" in result.output
    assert "—" in result.output and "PRIMARY" in result.output
    assert "PROTECTION" in result.output and "AUTO" in result.output
    assert result.output.index("PortChannel2") < result.output.index("PortChannel10")


def test_show_single_interface_and_missing_state(cli, monkeypatch):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    entries = {"PortChannel0": {"admin_mode": "AUTO"}, "PortChannel1": {"admin_mode": "PROTECTION"}}
    result = show_rows(cli, entries, ["portchannel0"])
    assert result.exit_code == 0 and "PortChannel0" in result.output
    assert "PortChannel1" not in result.output and "—" in result.output
    result = show_rows(cli, entries, ["PortChannel2"])
    assert result.exit_code == 0 and "No bridge-port protection state available for PortChannel2." in result.output


def test_show_empty_and_deleted_rows(cli, monkeypatch):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    result = show_rows(cli, {"PortChannel0": {}})
    assert result.exit_code == 0
    assert "No bridge-port protection state available." in result.output


@pytest.mark.parametrize("namespace", [None, "asic0"])
def test_show_multi_asic(cli, monkeypatch, namespace):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: True)
    monkeypatch.setattr(status.multi_asic, "get_front_end_namespaces", lambda: ["asic0", "asic1"])
    monkeypatch.setattr(status.multi_asic_util.multi_asic, "is_multi_asic", lambda: True)
    monkeypatch.setattr(status.multi_asic_util.multi_asic, "get_namespace_list", lambda: ["asic0", "asic1"])
    cli[1].db_clients = {
        "": state_client({"PortChannel9": {"admin_mode": "AUTO"}}),
        "asic0": state_client({"PortChannel0": {"admin_mode": "AUTO"}}),
        "asic1": state_client({"PortChannel0": {"admin_mode": "PRIMARY"}}),
    }
    args = [] if namespace is None else ["--namespace", namespace]
    result = cli[0].invoke(show.cli.commands["bridge-port-protection"], args, obj=cli[1])
    assert result.exit_code == 0, result.output
    assert "NAMESPACE" in result.output and "asic0" in result.output
    assert "PortChannel9" not in result.output
    assert ("asic1" in result.output) == (namespace is None)


@pytest.mark.parametrize("verbose", [False, True])
def test_software_show_uses_hld_columns_only(cli, monkeypatch, verbose):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    entry = {
        "protection_state": "PROTECTION", "protection_type": "sw_protection",
        "admin_mode": "AUTO", "reconciliation_state": "STEADY",
        "last_resync_ts": "2026-10-12T21:00:00Z",
        # Older writer diagnostics must not extend the HLD show contract.
        "programmed_sai_admin_mode": "PROTECTION", "last_event": "stale_event",
        "last_event_ts": "2026-10-07T12:00:00Z", "revertive": "false",
        "wait_to_restore_time_ms": "5000", "wtr_state": "WAIT_TO_RESTORE",
    }
    args = ["portchannel0"] + (["--verbose"] if verbose else [])
    result = show_rows(cli, {"PortChannel0": entry}, args)
    assert result.exit_code == 0, result.output
    for value in ["PROTECTION", "sw_protection", "AUTO", "STEADY", entry["last_resync_ts"]]:
        assert value in result.output
    for header in ["CONVERGENCE", "ADMIN_MODE", "LAST_ARBITRATION", "LAST_RESYNC"]:
        assert header in result.output
    for extra in ["PROGRAMMED_SAI_ADMIN_MODE", "LAST_EVENT", "REVERTIVE", "WAIT_TO_RESTORE_TIME_MS", "stale_event", "5000"]:
        assert extra not in result.output
    assert "n/a" in result.output
    assert ("T_RECONCILE_ARMED_AT" in result.output) == verbose
    assert ("LAST_CACHE_UPDATE" in result.output) == verbose


def test_verbose_handles_older_rows_and_missing_interface(cli, monkeypatch):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    entries = {"PortChannel0": {"admin_mode": "AUTO"}}
    result = show_rows(cli, entries, ["--verbose"])
    assert result.exit_code == 0, result.output
    assert "—" in result.output and "LAST_RESYNC" in result.output
    assert "UNKNOWN" not in result.output and "LAST_EVENT" not in result.output
    result = show_rows(cli, entries, ["PortChannel1", "--verbose"])
    assert result.exit_code == 0 and "No bridge-port protection state" in result.output


def test_verbose_multi_asic_separates_same_interface(cli, monkeypatch):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: True)
    monkeypatch.setattr(status.multi_asic, "get_front_end_namespaces", lambda: ["asic0", "asic1"])
    cli[1].db_clients = {
        "": state_client({"PortChannel9": {"admin_mode": "AUTO"}}),
        "asic0": state_client({"PortChannel0": {"reconciliation_state": "STEADY"}}),
        "asic1": state_client({"PortChannel0": {"reconciliation_state": "INCONSISTENT"}}),
    }
    result = cli[0].invoke(show.cli.commands["bridge-port-protection"], ["--verbose"], obj=cli[1])
    assert result.exit_code == 0, result.output
    assert result.output.count("PortChannel0") == 2
    assert "asic0" in result.output and "asic1" in result.output
    assert "STEADY" in result.output and "INCONSISTENT" in result.output
    assert "PortChannel9" not in result.output


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("convergence,outcome,source", [
    ("enabled", "none", "none"), ("enabled", "matched", "cache"),
    ("enabled", "corrective_override", "sai_get"), ("enabled", "failed", "cache"),
    ("disabled", "none", "none"), ("disabled", "corrective_override", "sai_get"),
])
def test_hld_hardware_arbitration_and_verbose_fields(cli, monkeypatch, verbose, convergence, outcome, source):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    entry = {"protection_state": "PROTECTION", "protection_type": "hw_protection",
             "admin_mode": "AUTO", "reconciliation_state": "CONVERGING",
             "convergence_mode": convergence, "last_arbitration_outcome": outcome,
             "last_arbitration_source": source, "last_arbitration_ts": "2026-10-12T21:01:02Z",
             "t_reconcile_armed_at": "2026-10-12T21:01:00Z",
             "last_cache_update_ts": "2026-10-12T21:01:03Z", "last_resync_ts": "2026-10-12T21:00:00Z"}
    result = show_rows(cli, {"PortChannel0": entry}, ["--verbose"] if verbose else [])
    assert result.exit_code == 0, result.output
    assert "CONVERGING" in result.output and entry["last_resync_ts"] in result.output
    if convergence == "disabled": assert "n/a" in result.output and "corrective_override" not in result.output
    elif outcome == "none": assert "none" in result.output and entry["last_arbitration_ts"] not in result.output
    else: assert f"{outcome} ({source}) @ {entry['last_arbitration_ts']}" in result.output
    if verbose:
        assert "T_RECONCILE_ARMED_AT" in result.output
        assert "LAST_ARBITRATION_SOURCE" in result.output and "LAST_CACHE_UPDATE" in result.output
        assert entry["last_cache_update_ts"] in result.output
        assert (entry["t_reconcile_armed_at"] in result.output) == (convergence == "enabled")


@pytest.mark.parametrize("path", [None, "UNKNOWN", "NOT_APPLICABLE", "invalid"])
@pytest.mark.parametrize("health", ["PENDING", "ERROR", "CONVERGING"])
def test_legacy_software_rows_do_not_expose_non_hld_state_values(cli, monkeypatch, path, health):
    monkeypatch.setattr(status.multi_asic, "is_multi_asic", lambda: False)
    entry = {"protection_type": "sw_protection", "admin_mode": "AUTO", "reconciliation_state": health}
    if path is not None: entry["protection_state"] = path
    result = show_rows(cli, {"PortChannel0": entry}, ["--verbose"])
    assert result.exit_code == 0, result.output
    assert "—" in result.output and "INCONSISTENT" in result.output
    assert health not in result.output
    for invalid in ["UNKNOWN", "NOT_APPLICABLE", "PENDING", "ERROR"]:
        assert invalid not in result.output
