import chassis_lag_id_checker
import pytest
import sys
import logging

import sonic_py_common.multi_asic as multi_asic
import sonic_py_common.device_info as device_info

sys.path.append("scripts")


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
                "sonic-lc1-1|asic0|PortChannel112": "262",
                "sonic-lc1-1|asic0|PortChannel116": "263",
                "sonic-lc3-1|asic0|PortChannel149": "265",
                "sonic-lc3-1|asic0|PortChannel150": "266",
            }
        return {}
    monkeypatch.setattr(chassis_lag_id_checker, "run_redis_dump", _mock)


@pytest.fixture
def mock_multi_asic(monkeypatch):
    monkeypatch.setattr(multi_asic, "DEFAULT_NAMESPACE", "default")
    monkeypatch.setattr(multi_asic, "get_namespace_list", lambda: ["asic0", "asic1"])


@pytest.fixture
def mock_device_info(monkeypatch):
    monkeypatch.setattr(device_info, "is_voq_chassis", lambda: True)
    monkeypatch.setattr(device_info, "is_supervisor", lambda: False)


def test_extract_lag_ids_from_asic_db():
    db_output = {
        "SAI_OBJECT_TYPE_LAG:1": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "100"}},
        "SAI_OBJECT_TYPE_LAG:2": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "200"}},
        "OTHER_KEY": {"value": {"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID": "999"}}
    }
    lag_ids = chassis_lag_id_checker.extract_lag_ids_from_asic_db(
        db_output, "SAI_OBJECT_TYPE_LAG", "SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID"
    )
    assert "100" in lag_ids
    assert "200" in lag_ids


def test_extract_table_ids_from_chassis_db():
    table_output = {"PortChannel1": "100", "hostname|asic0|PortChannel2": "200"}
    ids = chassis_lag_id_checker.extract_table_ids_from_chassis_db(table_output)
    assert ids == {"100", "200"}


def test_get_lag_key_mismatches():
    chassis_db_table = {"hostname|asic0|PortChannel1": "100",
                        "hostname|asic0|PortChannel2": "200", "PortChannel3": "300"}
    diff = {"300"}
    mismatches = chassis_lag_id_checker.get_lag_key_mismatches(chassis_db_table, diff)
    assert mismatches == ["hostname|asic0|PortChannel3"]


def test_compare_lag_ids(mock_run_redis_dump, mock_multi_asic):
    lag_ids_in_chassis_db = {"100", "200", "300"}
    diff = chassis_lag_id_checker.compare_lag_ids(lag_ids_in_chassis_db, "default")
    assert diff == {"300"}


def test_check_lag_id_sync(mock_run_redis_dump, mock_multi_asic):
    diff_summary = chassis_lag_id_checker.check_lag_id_sync()
    assert "localhost" in diff_summary
    assert diff_summary["localhost"] == ["hostname|asic0|PortChannel3"]


def test_main_no_mismatch(monkeypatch, mock_run_redis_dump, mock_multi_asic, mock_device_info):
    # Patch check_lag_id_sync to return no mismatches
    monkeypatch.setattr(chassis_lag_id_checker, "check_lag_id_sync", lambda: {"localhost": []})
    monkeypatch.setattr(logging, "info", lambda msg: None)
    chassis_lag_id_checker.main()


def test_main_with_mismatch(monkeypatch, mock_run_redis_dump, mock_multi_asic, mock_device_info):
    # Patch check_lag_id_sync to return mismatches
    monkeypatch.setattr(chassis_lag_id_checker, "check_lag_id_sync", lambda: {
                        "asic0": ["hostname|asic0|PortChannel3"]})
    monkeypatch.setattr(logging, "critical", lambda msg, *args, **kwargs: None)
    with pytest.raises(SystemExit) as e:
        chassis_lag_id_checker.main()
    assert e.value.code == 1
