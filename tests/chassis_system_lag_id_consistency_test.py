import json

import click
import pytest
from click.testing import CliRunner

from show.main import cli

REASON_NOT_ON_SUPERVISOR = "Not supported on supervisor (VOQ chassis linecards only)"
STATUS_ERROR = "error"
STATUS_FAILED = "failed"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_OK = "ok"

EMPTY_LAG_IDS = {"lag_id_count": 0, "missing_in_asic_db": [], "extra_in_asic_db": []}
EMPTY_LAG_MEMBERS = {
    "member_count": 0,
    "missing_in_asic_db": [],
    "extra_in_asic_db": [],
    "status_mismatch": [],
    "invalid_port_id": [],
    "unresolved": [],
    "incomplete_attrs": [],
}


def _asics_ok(lag_id_only):
    asic0 = {
        "lag_ids": {"lag_id_count": 5, "missing_in_asic_db": [], "extra_in_asic_db": []},
    }
    asic1 = {
        "lag_ids": {"lag_id_count": 5, "missing_in_asic_db": [], "extra_in_asic_db": []},
    }
    if not lag_id_only:
        asic0["lag_members"] = {
            "member_count": 2,
            "missing_in_asic_db": [],
            "extra_in_asic_db": [],
            "status_mismatch": [],
            "invalid_port_id": [],
            "unresolved": [],
            "incomplete_attrs": [],
        }
        asic1["lag_members"] = EMPTY_LAG_MEMBERS
    return {"asic0": asic0, "asic1": asic1}


def _asics_failed(lag_id_only):
    asic0 = {
        "lag_ids": {
            "lag_id_count": 19,
            "missing_in_asic_db": ["175"],
            "extra_in_asic_db": ["171"],
        },
    }
    if not lag_id_only:
        asic0["lag_members"] = {
            "member_count": 2,
            "missing_in_asic_db": ["lag:port1"],
            "extra_in_asic_db": [],
            "status_mismatch": [
                {
                    "member": "lag:port2",
                    "chassis_status": "enabled",
                    "ingress_disable": "true",
                    "egress_disable": "true",
                }
            ],
            "invalid_port_id": [],
            "unresolved": [],
            "incomplete_attrs": [],
        }
    return {"asic0": asic0}


@pytest.fixture
def mock_consistency_ok(monkeypatch):
    monkeypatch.setattr(
        "show.chassis_modules._run_system_lag_consistency_checker",
        lambda lag_id_only=False: {
            "status": STATUS_OK,
            "lag_id_only": lag_id_only,
            "chassis_lag_id_count": 5,
            "chassis_lag_member_count": 0 if lag_id_only else 2,
            "asics": _asics_ok(lag_id_only),
        },
    )


@pytest.fixture
def mock_consistency_failed(monkeypatch):
    monkeypatch.setattr(
        "show.chassis_modules._run_system_lag_consistency_checker",
        lambda lag_id_only=False: {
            "status": STATUS_FAILED,
            "lag_id_only": lag_id_only,
            "chassis_lag_id_count": 5,
            "chassis_lag_member_count": 0 if lag_id_only else 2,
            "asics": _asics_failed(lag_id_only),
        },
    )


@pytest.fixture
def mock_consistency_not_applicable(monkeypatch):
    monkeypatch.setattr(
        "show.chassis_modules._run_system_lag_consistency_checker",
        lambda lag_id_only=False: {
            "status": STATUS_NOT_APPLICABLE,
            "reason": REASON_NOT_ON_SUPERVISOR,
            "lag_id_only": lag_id_only,
            "chassis_lag_id_count": 0,
            "chassis_lag_member_count": 0,
            "asics": {},
        },
    )


@pytest.fixture
def mock_consistency_error(monkeypatch):
    monkeypatch.setattr(
        "show.chassis_modules._run_system_lag_consistency_checker",
        lambda lag_id_only=False: {
            "status": STATUS_ERROR,
            "reason": "No SYSTEM_LAG_ID_TABLE found in chassis_db",
            "lag_id_only": lag_id_only,
            "chassis_lag_id_count": 0,
            "chassis_lag_member_count": 0,
            "asics": {},
        },
    )


def _invoke_consistency(args=None):
    runner = CliRunner()
    return runner.invoke(
        cli.commands["chassis"].commands["system-lag-consistency"],
        args or [],
    )


def test_show_chassis_system_lag_consistency_ok(mock_consistency_ok):
    result = _invoke_consistency()
    assert result.exit_code == 0
    assert "System LAG consistency: OK" in result.output
    assert "SYSTEM_LAG_ID_TABLE:      5 lag IDs" in result.output
    assert "SYSTEM_LAG_MEMBER_TABLE:  2 lag members" in result.output
    assert "ASIC namespace: asic0" in result.output
    assert "Lag IDs in ASIC_DB:      5 (0 mismatches)" in result.output
    assert "All ASIC namespaces are in sync with chassis_db." in result.output


def test_show_chassis_system_lag_consistency_failed(mock_consistency_failed):
    result = _invoke_consistency()
    assert result.exit_code == 0
    assert "System LAG consistency: FAILED" in result.output
    assert "One or more ASIC namespaces are out of sync with chassis_db." in result.output
    assert "Lag IDs missing in ASIC_DB (in CHASSIS_DB - SYSTEM_LAG_ID_TABLE):" in result.output
    assert "    175" in result.output
    assert "Lag IDs extra in ASIC_DB (not in CHASSIS_DB - SYSTEM_LAG_ID_TABLE):" in result.output
    assert "    171" in result.output
    assert "Lag members missing in ASIC_DB (in CHASSIS_DB - SYSTEM_LAG_MEMBER_TABLE):" in result.output
    assert "    lag : port1" in result.output
    assert "Lag member status mismatch:" in result.output
    assert "lag:port2" in result.output


def test_show_chassis_system_lag_consistency_not_applicable(mock_consistency_not_applicable):
    result = _invoke_consistency()
    assert result.exit_code == 0
    assert "System LAG consistency: not applicable" in result.output
    assert "Not supported on supervisor" in result.output


def test_show_chassis_system_lag_consistency_error(mock_consistency_error):
    result = _invoke_consistency()
    assert result.exit_code == 0
    assert "System LAG consistency: error" in result.output
    assert "No SYSTEM_LAG_ID_TABLE found in chassis_db" in result.output


def test_show_chassis_system_lag_consistency_json(mock_consistency_ok):
    result = _invoke_consistency(["--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == STATUS_OK
    assert payload["chassis_lag_id_count"] == 5
    assert payload["chassis_lag_member_count"] == 2
    assert payload["lag_id_only"] is False


def test_show_chassis_system_lag_consistency_lag_id_only(mock_consistency_ok):
    result = _invoke_consistency(["--lag-id-only"])
    assert result.exit_code == 0
    assert "Mode: LAG ID only (lag members not checked)" in result.output
    assert "SYSTEM_LAG_MEMBER_TABLE" not in result.output
    assert "Lag members in ASIC_DB" not in result.output
    assert "ASIC namespace: asic0" in result.output
    assert "Lag IDs in ASIC_DB:      5 (0 mismatches)" in result.output


def test_show_chassis_system_lag_consistency_lag_id_only_json(mock_consistency_ok):
    result = _invoke_consistency(["--lag-id-only", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["lag_id_only"] is True
    assert payload["chassis_lag_member_count"] == 0
    assert "lag_members" not in payload["asics"]["asic0"]


def test_show_chassis_system_lag_consistency_lag_id_only_skips_member_output(
    mock_consistency_failed,
):
    result = _invoke_consistency(["--lag-id-only"])
    assert result.exit_code == 0
    assert "Lag IDs missing in ASIC_DB (in CHASSIS_DB - SYSTEM_LAG_ID_TABLE):" in result.output
    assert "    175" in result.output
    assert "Lag members missing in ASIC_DB" not in result.output
    assert "Lag member status mismatch" not in result.output


def test_show_chassis_system_lag_consistency_checker_failure(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise click.ClickException("checker subprocess failed")

    monkeypatch.setattr(
        "show.chassis_modules._run_system_lag_consistency_checker",
        _raise,
    )
    result = _invoke_consistency()
    assert result.exit_code != 0
    assert "checker subprocess failed" in result.output
