
import pytest
import sys
import logging
import json
import sonic_py_common.multi_asic as multi_asic
import sonic_py_common.device_info as device_info
sys.path.append("scripts")  # noqa: E402
import chassis_db_consistency_checker  # noqa: E402


@pytest.fixture
def mock_run_redis_dump(monkeypatch):
    def _mock(cmd_args):
        # Return a fake redis-dump output based on command args
        if "SAI_OBJECT_TYPE_LAG" in str(cmd_args):
            # Simulate ASIC DB output
            return {
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b27": {
                    "expireat": 1764524951.6364665,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "262"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b28": {
                    "expireat": 1764524951.6364777,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "263"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b29": {
                    "expireat": 1764524951.636488,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "264"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b2a": {
                    "expireat": 1764524951.6364946,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "265"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b2b": {
                    "expireat": 1764524951.636469,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "266"
                    }
                }
            }
        elif "SYSTEM_LAG_ID_TABLE" in str(cmd_args):
            # Simulate Chassis DB output
            return {
                "SYSTEM_LAG_ID_TABLE": {
                    "expireat": 1764524950.7635868,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "sonic-lc1-1|asic0|PortChannel112": "262",
                        "sonic-lc1-1|asic0|PortChannel116": "263",
                        "sonic-lc2-1|asic0|PortChannel100": "264",
                        "sonic-lc3-1|asic0|PortChannel149": "265",
                        "sonic-lc3-1|asic0|PortChannel150": "266",
                    }
                }
            }
        return {}
    monkeypatch.setattr(chassis_db_consistency_checker, "run_redis_dump", _mock)


@pytest.fixture
def run_redis_dump_empty(monkeypatch):
    def _mock(cmd_args):
        return {}
    monkeypatch.setattr(chassis_db_consistency_checker, "run_redis_dump", _mock)


@pytest.fixture
def mock_run_redis_dump_mismatch(monkeypatch):
    def _mock(cmd_args):
        # Return a fake redis-dump output based on command args
        if "SAI_OBJECT_TYPE_LAG" in str(cmd_args):
            # Simulate ASIC DB output
            return {
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b27": {
                    "expireat": 1764524951.6364665,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "262"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b28": {
                    "expireat": 1764524951.6364777,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "263"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b29": {
                    "expireat": 1764524951.636488,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "264"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b2a": {
                    "expireat": 1764524951.6364946,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "265"
                    }
                },
                "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x102000000000b2b": {
                    "expireat": 1764524951.636469,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "266"
                    }
                }
            }
        elif "SYSTEM_LAG_ID_TABLE" in str(cmd_args):
            # Simulate Chassis DB output
            return {
                "SYSTEM_LAG_ID_TABLE": {
                    "expireat": 1764524950.7635868,
                    "ttl": -0.001,
                    "type": "hash",
                    "value": {
                        "sonic-lc1-1|asic0|PortChannel112": "262",
                        "sonic-lc1-1|asic0|PortChannel116": "263"
                    }
                }
            }
        return {}
    monkeypatch.setattr(chassis_db_consistency_checker, "run_redis_dump", _mock)


@pytest.fixture
def mock_multi_asic(monkeypatch):
    monkeypatch.setattr(multi_asic, "get_namespace_list", lambda: ["asic0", "asic1"])


@pytest.fixture
def mock_single_asic(monkeypatch):
    monkeypatch.setattr(multi_asic, "get_namespace_list", lambda: [multi_asic.DEFAULT_NAMESPACE])


@pytest.fixture
def mock_device_info(monkeypatch):
    monkeypatch.setattr(device_info, "is_voq_chassis", lambda: True)
    monkeypatch.setattr(device_info, "is_supervisor", lambda: False)


@pytest.fixture
def mock_device_info_no_voq(monkeypatch):
    monkeypatch.setattr(device_info, "is_voq_chassis", lambda: False)


@pytest.fixture
def mock_device_info_supervisor(monkeypatch):
    monkeypatch.setattr(device_info, "is_voq_chassis", lambda: True)
    monkeypatch.setattr(device_info, "is_supervisor", lambda: True)


def test_extract_lag_ids_from_asic_db():
    db_output = {
        "SAI_OBJECT_TYPE_LAG:1": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "100"}},
        "SAI_OBJECT_TYPE_LAG:2": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "200"}},
        "SAI_OBJECT_TYPE_LAG:3": {"value": {}},
        "OTHER_KEY": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "999"}}
    }
    lag_ids = chassis_db_consistency_checker.extract_lag_ids_from_asic_db(
        db_output, "SAI_OBJECT_TYPE_LAG", "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID"
    )
    assert lag_ids == {"100", "200"}


def test_extract_table_ids_from_chassis_db():
    table_output = {"PortChannel1": "100", "hostname|asic0|PortChannel2": "200"}
    ids = chassis_db_consistency_checker.extract_table_ids_from_chassis_db(table_output)
    assert ids == {"100", "200"}


def test_extract_table_ids_from_chassis_db_skips_none():
    table_output = {"PortChannel1": "100", "PortChannel2": None}
    ids = chassis_db_consistency_checker.extract_table_ids_from_chassis_db(table_output)
    assert ids == {"100"}


def test_extract_table_ids_from_chassis_db_normalizes_integers():
    table_output = {"PortChannel1": "262", "PortChannel2": 262}
    ids = chassis_db_consistency_checker.extract_table_ids_from_chassis_db(table_output)
    assert ids == {"262"}


def test_parse_chassis_lag_member_dump_prefixed_keys():
    dump_output = {
        "SYSTEM_LAG_MEMBER_TABLE|lagA:host|asic0|port1": {
            "value": {"status": "disabled"},
        },
        "SYSTEM_LAG_MEMBER_TABLE|lagA:host|asic0|port2": {
            "value": {"status": "enabled"},
        },
    }
    member_table = chassis_db_consistency_checker.parse_chassis_lag_member_dump(dump_output)
    assert member_table == {
        "lagA:host|asic0|port1": {"status": "disabled"},
        "lagA:host|asic0|port2": {"status": "enabled"},
    }


def test_normalize_member_port_alias():
    lag_alias = "ixre-egl-board211|asic0|PortChannel102"
    assert chassis_db_consistency_checker.normalize_member_port_alias(
        lag_alias, "Ethernet0"
    ) == "ixre-egl-board211|asic0|Ethernet0"
    assert chassis_db_consistency_checker.normalize_member_port_alias(
        lag_alias, "ixre-egl-board211|asic0|Ethernet0"
    ) == "ixre-egl-board211|asic0|Ethernet0"


def test_extract_lag_ids_from_asic_db_normalizes_integers():
    db_output = {
        "SAI_OBJECT_TYPE_LAG:1": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": 262}},
        "SAI_OBJECT_TYPE_LAG:2": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "263"}},
    }
    lag_ids = chassis_db_consistency_checker.extract_lag_ids_from_asic_db(
        db_output, "SAI_OBJECT_TYPE_LAG", "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID"
    )
    assert lag_ids == {"262", "263"}


def test_bidirectional_set_diff_member_keys():
    chassis_members = {"lag:port1": "enabled", "lag:port2": "disabled"}
    asic_members = {"lag:port1": {}, "lag:port3": {}}
    missing, extra = chassis_db_consistency_checker.bidirectional_set_diff(
        set(chassis_members.keys()), set(asic_members.keys())
    )
    assert missing == {"lag:port2"}
    assert extra == {"lag:port3"}


def test_member_disable_matches_status():
    assert chassis_db_consistency_checker.member_disable_matches_status("true", "true", "disabled")
    assert chassis_db_consistency_checker.member_disable_matches_status("false", "false", "disabled")
    assert chassis_db_consistency_checker.member_disable_matches_status("false", "false", "enabled")
    assert not chassis_db_consistency_checker.member_disable_matches_status(
        "true", "false", "disabled"
    )
    assert not chassis_db_consistency_checker.member_disable_matches_status(
        "true", "false", "enabled"
    )
    assert not chassis_db_consistency_checker.member_disable_matches_status(
        "false", "true", "enabled"
    )


def test_bidirectional_set_diff_lag_ids():
    missing, extra = chassis_db_consistency_checker.bidirectional_set_diff(
        {"100", "175"}, {"100", "171"}
    )
    assert missing == {"175"}
    assert extra == {"171"}


def test_extract_asic_lag_members_incomplete_attrs():
    lag_member_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0x1": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": "oid:lag1",
                "SAI_LAG_MEMBER_ATTR_PORT_ID": None,
            }
        }
    }
    members, unresolved, invalid_port_id, incomplete_attrs = (
        chassis_db_consistency_checker.extract_asic_lag_members(
            lag_member_db_output, {}, {}, set(), {}
        )
    )
    assert members == {}
    assert unresolved == []
    assert invalid_port_id == []
    assert len(incomplete_attrs) == 1
    assert incomplete_attrs[0]["port_oid"] is None


def test_extract_asic_lag_members_invalid_port_id_not_counted_as_member():
    lag_member_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0x1": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": "oid:lag1",
                "SAI_LAG_MEMBER_ATTR_PORT_ID": "oid:badport",
                "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE": "false",
                "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE": "false",
            }
        }
    }
    members, unresolved, invalid_port_id, incomplete_attrs = (
        chassis_db_consistency_checker.extract_asic_lag_members(
            lag_member_db_output,
            {"oid:lag1": "host|asic0|PortChannel1"},
            {"oid:badport": "Ethernet0"},
            set(),
            {},
        )
    )
    assert members == {}
    assert unresolved == []
    assert invalid_port_id == [
        {"member": "host|asic0|PortChannel1:host|asic0|Ethernet0", "port_id": "oid:badport"},
    ]
    assert incomplete_attrs == []


def test_member_missing_excludes_invalid_port_id():
    chassis_members = {
        "lag:host|asic0|Ethernet0": "enabled",
    }
    asic_members = {}
    invalid_port_id = [
        {"member": "lag:host|asic0|Ethernet0", "port_id": "oid:badport"},
    ]
    member_missing, member_extra = chassis_db_consistency_checker.bidirectional_set_diff(
        set(chassis_members.keys()), set(asic_members.keys())
    )
    invalid_member_keys = {item["member"] for item in invalid_port_id}
    member_missing -= invalid_member_keys
    member_extra -= invalid_member_keys
    assert member_missing == set()
    assert member_extra == set()
    member_result = {
        "missing_in_asic_db": [],
        "extra_in_asic_db": [],
        "status_mismatch": [],
        "invalid_port_id": [],
        "unresolved": [],
        "incomplete_attrs": [{"lag_member_oid": "oid:0x1"}],
    }
    assert chassis_db_consistency_checker.member_diff_has_mismatch(member_result)


def test_check_asic_namespace_lag_id_diff(mock_run_redis_dump, mock_multi_asic):
    chassis_table = chassis_db_consistency_checker.get_chassis_lag_db_table()
    lag_ids_in_chassis_db = {"262", "264"}
    result = chassis_db_consistency_checker.check_asic_namespace(
        "asic0", lag_ids_in_chassis_db, chassis_table, {}
    )
    assert result["lag_ids"]["missing_in_asic_db"] == []
    assert result["lag_ids"]["extra_in_asic_db"] == ["263", "265", "266"]


def test_get_lag_id_consistency_result_ok(mock_run_redis_dump, mock_multi_asic, mock_device_info):
    result = chassis_db_consistency_checker.get_lag_id_consistency_result()
    assert result["status"] == chassis_db_consistency_checker.STATUS_OK
    assert result["lag_id_only"] is True
    assert result["chassis_lag_id_count"] == 5
    assert result["chassis_lag_member_count"] == 0
    assert result["asics"]["asic0"]["lag_ids"]["missing_in_asic_db"] == []
    assert result["asics"]["asic0"]["lag_ids"]["extra_in_asic_db"] == []


def test_get_lag_id_consistency_result_not_applicable(mock_device_info_supervisor):
    result = chassis_db_consistency_checker.get_lag_id_consistency_result()
    assert result["status"] == chassis_db_consistency_checker.STATUS_NOT_APPLICABLE
    assert "supervisor" in result["reason"].lower()


def test_json_output(monkeypatch, mock_run_redis_dump, mock_multi_asic, mock_device_info, capsys):
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py", "--json"])
    rc = chassis_db_consistency_checker.main()
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["status"] == chassis_db_consistency_checker.STATUS_OK
    assert payload["lag_id_only"] is False


def test_json_output_lag_id_only(
    monkeypatch, mock_run_redis_dump, mock_multi_asic, mock_device_info, capsys
):
    monkeypatch.setattr(
        sys, "argv", ["chassis_db_consistency_checker.py", "--lag-id-only", "--json"]
    )
    rc = chassis_db_consistency_checker.main()
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["lag_id_only"] is True
    assert payload["chassis_lag_member_count"] == 0


def test_check_no_voq_chassis(monkeypatch, mock_run_redis_dump, mock_device_info_no_voq, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert rc == 0
    assert "Not a voq chassis device. Exiting....." in caplog.text


def test_check_no_supervisor(monkeypatch, mock_run_redis_dump, mock_device_info_supervisor, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert rc == 0
    assert "Not supported on supervisor. Exiting...." in caplog.text


def test_no_mismatch(monkeypatch, mock_run_redis_dump, mock_multi_asic, mock_device_info):
    # Ensure main sees predictable args
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert rc == 0


def test_no_mismatch_single_asic(monkeypatch, mock_run_redis_dump, mock_single_asic, mock_device_info):
    # Ensure main sees predictable args
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert rc == 0


def test_with_mismatch(monkeypatch, mock_run_redis_dump_mismatch, mock_multi_asic, mock_device_info, caplog):
    caplog.set_level(logging.CRITICAL)
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert "LAG IDs in chassis_db missing in asic0 ASIC_DB" not in caplog.text
    assert "LAG IDs in asic0 ASIC_DB missing from chassis_db" in caplog.text
    assert "LAG IDs in asic1 ASIC_DB missing from chassis_db" in caplog.text
    assert "Summary of mismatches" in caplog.text
    assert rc == chassis_db_consistency_checker.RC_ERR


def test_main_json_returns_ok_on_mismatch(
    monkeypatch, mock_run_redis_dump_mismatch, mock_multi_asic, mock_device_info, capsys
):
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py", "--json"])
    rc = chassis_db_consistency_checker.main()
    captured = capsys.readouterr()
    assert rc == chassis_db_consistency_checker.RC_OK
    payload = json.loads(captured.out)
    assert payload["status"] == chassis_db_consistency_checker.STATUS_FAILED


def test_main_sys_exit_nonzero_on_mismatch(
    monkeypatch, mock_run_redis_dump_mismatch, mock_multi_asic, mock_device_info
):
    exit_code = None

    def capture_exit(code):
        nonlocal exit_code
        exit_code = code
        raise SystemExit(code)

    monkeypatch.setattr(chassis_db_consistency_checker.sys, "exit", capture_exit)
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    with pytest.raises(SystemExit):
        chassis_db_consistency_checker.sys.exit(chassis_db_consistency_checker.main())
    assert exit_code == chassis_db_consistency_checker.RC_ERR


def test_with_mismatch_single_asic(monkeypatch, mock_run_redis_dump_mismatch,
                                   mock_single_asic, mock_device_info, caplog):
    caplog.set_level(logging.CRITICAL)
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert "LAG IDs in localhost ASIC_DB missing from chassis_db" in caplog.text
    assert "Summary of mismatches" in caplog.text
    assert rc == chassis_db_consistency_checker.RC_ERR


def test_redis_dump_no_output(monkeypatch, run_redis_dump_empty,
                              mock_multi_asic, mock_device_info, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr(sys, "argv", ["chassis_db_consistency_checker.py"])
    rc = chassis_db_consistency_checker.main()
    assert rc == chassis_db_consistency_checker.RC_ERR
    assert "No SYSTEM_LAG_ID_TABLE found in chassis_db" in caplog.text


def test_run_redis_dump_failure(monkeypatch):
    class FakeCompleted:
        def __init__(self, stdout="", stderr="", returncode=1):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd_args, capture_output=True, text=True):
        return FakeCompleted(stdout="", stderr="error", returncode=1)

    monkeypatch.setattr(chassis_db_consistency_checker.subprocess, "run", fake_run)
    out = chassis_db_consistency_checker.run_redis_dump(["redis-dump", "-d", "1", "-y"])
    assert out == {}  # script logs and returns {}


def test_run_redis_dump(monkeypatch, caplog):
    # Create a fake CompletedProcess-like object
    class FakeCompleted:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    # Define behavior based on args
    def fake_run(cmd_args, capture_output=True, text=True):
        assert capture_output and text
        if "-k" in cmd_args and "*SAI_OBJECT_TYPE_LAG:*" in cmd_args:
            payload = {"SAI_OBJECT_TYPE_LAG:oid:1": {
                "value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "100"}}}
            return FakeCompleted(stdout=json.dumps(payload))
        elif "-k" in cmd_args and "SYSTEM_LAG_ID_TABLE" in cmd_args:
            payload = {"SYSTEM_LAG_ID_TABLE": {"value": {"hostname|asic0|PortChannel1": "100"}}}
            return FakeCompleted(stdout=json.dumps(payload))
        return FakeCompleted(stdout="{}", returncode=0)

    # Patch subprocess.run
    monkeypatch.setattr(chassis_db_consistency_checker.subprocess, "run", fake_run)

    # Now call module functions; they will use the mocked run
    table = chassis_db_consistency_checker.get_chassis_lag_db_table()
    assert table == {"hostname|asic0|PortChannel1": "100"}


@pytest.fixture
def mock_member_consistency(monkeypatch):
    """Mock redis data for lag member consistency checks."""
    lag_alias = "sonic-lc1-1|asic0|PortChannel112"
    lag_id_table = {lag_alias: "262"}
    lag_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0xlag262": {
            "value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "262"},
        },
    }
    port_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0xport1": {"value": {}},
        "ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0xport4": {"value": {}},
    }
    lag_member_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0xmember1": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": "oid:0xlag262",
                "SAI_LAG_MEMBER_ATTR_PORT_ID": "oid:0xport1",
                "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE": "false",
                "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE": "false",
            },
        },
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0xmember4": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": "oid:0xlag262",
                "SAI_LAG_MEMBER_ATTR_PORT_ID": "oid:0xport4",
                "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE": "false",
                "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE": "false",
            },
        },
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0xmember2": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": "oid:0xlag262",
                "SAI_LAG_MEMBER_ATTR_PORT_ID": "oid:0xport2",
                "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE": "true",
                "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE": "true",
            },
        },
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0xmember_incomplete": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": None,
                "SAI_LAG_MEMBER_ATTR_PORT_ID": "oid:0xport1",
            },
        },
    }
    member_table = {
        f"{lag_alias}:sonic-lc1-1|asic0|Ethernet0": {"status": "enabled"},
        f"{lag_alias}:sonic-lc1-1|asic0|Ethernet4": {"status": "disabled"},
        f"{lag_alias}:sonic-lc1-1|asic0|Ethernet8": {"status": "enabled"},
    }

    def _mock(cmd_args):
        cmd = str(cmd_args)
        if "SYSTEM_LAG_ID_TABLE" in cmd:
            return {"SYSTEM_LAG_ID_TABLE": {"value": lag_id_table}}
        if "SYSTEM_LAG_MEMBER_TABLE" in cmd:
            return {"SYSTEM_LAG_MEMBER_TABLE": {"value": member_table}}
        if "SAI_OBJECT_TYPE_LAG:" in cmd:
            return lag_db_output
        if "SAI_OBJECT_TYPE_LAG_MEMBER:" in cmd:
            return lag_member_db_output
        if "SAI_OBJECT_TYPE_PORT:" in cmd:
            return port_db_output
        if "COUNTERS_PORT_NAME_MAP" in cmd:
            return {
                "COUNTERS_PORT_NAME_MAP": {
                    "value": {
                        "sonic-lc1-1|asic0|Ethernet0": "oid:0xport1",
                        "sonic-lc1-1|asic0|Ethernet4": "oid:0xport4",
                        "sonic-lc1-1|asic0|Ethernet2": "oid:0xport2",
                    },
                },
            }
        if "COUNTERS_SYSTEM_PORT_NAME_MAP" in cmd:
            return {"COUNTERS_SYSTEM_PORT_NAME_MAP": {"value": {}}}
        return {}

    monkeypatch.setattr(chassis_db_consistency_checker, "run_redis_dump", _mock)
    monkeypatch.setattr(multi_asic, "get_namespace_list", lambda: ["asic0"])


def test_get_system_lag_consistency_member_issues(
    monkeypatch, mock_member_consistency, mock_device_info
):
    lag_alias = "sonic-lc1-1|asic0|PortChannel112"
    result = chassis_db_consistency_checker.get_system_lag_consistency_result()
    lag_members = result["asics"]["asic0"]["lag_members"]

    assert result["status"] == chassis_db_consistency_checker.STATUS_FAILED
    assert lag_members["missing_in_asic_db"] == [
        f"{lag_alias}:sonic-lc1-1|asic0|Ethernet8",
    ]
    assert lag_members["extra_in_asic_db"] == []
    assert lag_members["status_mismatch"] == []
    assert lag_members["invalid_port_id"] == [
        {
            "member": f"{lag_alias}:sonic-lc1-1|asic0|Ethernet2",
            "port_id": "oid:0xport2",
        },
    ]
    assert lag_members["member_count"] == 2
    assert lag_members["unresolved"] == []
    assert len(lag_members["incomplete_attrs"]) == 1


def test_get_system_lag_consistency_member_issues_lag_id_only_ok(
    monkeypatch, mock_member_consistency, mock_device_info
):
    result = chassis_db_consistency_checker.get_system_lag_consistency_result(check_members=False)
    assert result["status"] == chassis_db_consistency_checker.STATUS_OK
    assert result["lag_id_only"] is True
    assert result["chassis_lag_member_count"] == 0
    assert "lag_members" not in result["asics"]["asic0"]


@pytest.fixture
def mock_member_unresolved(monkeypatch):
    lag_alias = "sonic-lc1-1|asic0|PortChannel112"
    lag_id_table = {lag_alias: "262"}
    lag_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0xlag262": {
            "value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "262"},
        },
    }
    lag_member_db_output = {
        "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:0xmember_unknown": {
            "value": {
                "SAI_LAG_MEMBER_ATTR_LAG_ID": "oid:0xlag262",
                "SAI_LAG_MEMBER_ATTR_PORT_ID": "oid:0xport_missing",
                "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE": "false",
                "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE": "false",
            },
        },
    }
    member_table = {
        f"{lag_alias}:sonic-lc1-1|asic0|Ethernet8": {"status": "enabled"},
    }

    def _mock(cmd_args):
        cmd = str(cmd_args)
        if "SYSTEM_LAG_ID_TABLE" in cmd:
            return {"SYSTEM_LAG_ID_TABLE": {"value": lag_id_table}}
        if "SYSTEM_LAG_MEMBER_TABLE" in cmd:
            return {"SYSTEM_LAG_MEMBER_TABLE": {"value": member_table}}
        if "SAI_OBJECT_TYPE_LAG:" in cmd:
            return lag_db_output
        if "SAI_OBJECT_TYPE_LAG_MEMBER:" in cmd:
            return lag_member_db_output
        if "SAI_OBJECT_TYPE_PORT:" in cmd:
            return {}
        if "COUNTERS_PORT_NAME_MAP" in cmd:
            return {"COUNTERS_PORT_NAME_MAP": {"value": {}}}
        if "COUNTERS_SYSTEM_PORT_NAME_MAP" in cmd:
            return {"COUNTERS_SYSTEM_PORT_NAME_MAP": {"value": {}}}
        return {}

    monkeypatch.setattr(chassis_db_consistency_checker, "run_redis_dump", _mock)
    monkeypatch.setattr(multi_asic, "get_namespace_list", lambda: ["asic0"])


def test_get_system_lag_consistency_unresolved_member(
    mock_member_unresolved, mock_device_info
):
    lag_alias = "sonic-lc1-1|asic0|PortChannel112"
    member_key = f"{lag_alias}:sonic-lc1-1|asic0|Ethernet8"
    result = chassis_db_consistency_checker.get_system_lag_consistency_result()
    lag_members = result["asics"]["asic0"]["lag_members"]

    assert result["status"] == chassis_db_consistency_checker.STATUS_FAILED
    assert lag_members["missing_in_asic_db"] == [member_key]
    assert lag_members["extra_in_asic_db"] == []
    assert lag_members["unresolved"] == [
        {
            "lag_oid": "oid:0xlag262",
            "port_oid": "oid:0xport_missing",
            "system_port_aggregate_id": "262",
        },
    ]
