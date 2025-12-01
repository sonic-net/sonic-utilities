
import pytest
import sys
import logging
import json
import sonic_py_common.multi_asic as multi_asic
import sonic_py_common.device_info as device_info
sys.path.append("scripts")  # noqa: E402
import chassis_lag_id_checker  # noqa: E402

MULTI_ASIC_MISMATCH_LOGS = """CRITICAL root:chassis_lag_id_checker.py:160 Mismatched LAG keys in asic0: ['264', '265', '266']
CRITICAL root:chassis_lag_id_checker.py:160 Mismatched LAG keys in asic1: ['264', '265', '266']
CRITICAL root:chassis_lag_id_checker.py:164 Summary of mismatches:
{
    "asic0": [
        "264",
        "265",
        "266"
    ],
    "asic1": [
        "264",
        "265",
        "266"
    ]
}
"""
SINGLE_ASIC_MISMATCH_LOGS = """
CRITICAL root:chassis_lag_id_checker.py:160 Mismatched LAG keys in localhost: ['264', '265', '266']
CRITICAL root:chassis_lag_id_checker.py:164 Summary of mismatches:
{
    "localhost": [
        "264",
        "265",
        "266"
    ]
}"""


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
    monkeypatch.setattr(chassis_lag_id_checker, "run_redis_dump", _mock)


@pytest.fixture
def run_redis_dump_empty(monkeypatch):
    def _mock(cmd_args):
        return {}
    monkeypatch.setattr(chassis_lag_id_checker, "run_redis_dump", _mock)


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
    monkeypatch.setattr(chassis_lag_id_checker, "run_redis_dump", _mock)


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


def test_compare_lag_ids(mock_run_redis_dump, mock_multi_asic):
    lag_ids_in_chassis_db = {"262", "264"}
    diff = chassis_lag_id_checker.compare_lag_ids(lag_ids_in_chassis_db, "asic0")
    assert diff == {'263', '265', '266'}


def test_check_lag_id_sync(mock_run_redis_dump, mock_multi_asic):
    rc, diff_summary = chassis_lag_id_checker.check_lag_id_sync()
    assert rc == 0
    assert {'asic0': [], 'asic1': []} == diff_summary


def test_check_no_voq_chassis(monkeypatch, mock_run_redis_dump, mock_device_info_no_voq, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    assert rc == 0
    assert caplog.text.strip() == "INFO     root:chassis_lag_id_checker.py:146 Not a voq chassis device. Exiting....."


def test_check_no_supervisor(monkeypatch, mock_run_redis_dump, mock_device_info_supervisor, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    assert rc == 0
    assert caplog.text.strip() == "INFO     root:chassis_lag_id_checker.py:150 Not supported on supervisor. Exiting...."


def test_no_mismatch(monkeypatch, mock_run_redis_dump, mock_multi_asic, mock_device_info):
    # Ensure main sees predictable args
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    assert rc == 0


def test_no_mismatch_single_asic(monkeypatch, mock_run_redis_dump, mock_single_asic, mock_device_info):
    # Ensure main sees predictable args
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    assert rc == 0


def test_with_mismatch(monkeypatch, mock_run_redis_dump_mismatch, mock_multi_asic, mock_device_info, caplog):
    caplog.set_level(logging.CRITICAL)
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    assert caplog.text.strip() == MULTI_ASIC_MISMATCH_LOGS.strip()
    assert rc == -1


def test_with_mismatch_single_asic(monkeypatch, mock_run_redis_dump_mismatch,
                                   mock_single_asic, mock_device_info, caplog):
    caplog.set_level(logging.CRITICAL)
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    # The following line is within 120 columns
    assert caplog.text.strip() == SINGLE_ASIC_MISMATCH_LOGS.strip()
    assert rc == -1


def test_redis_dump_no_output(monkeypatch, run_redis_dump_empty,
                              mock_multi_asic, mock_device_info, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr(sys, "argv", ["chassis_lag_id_checker.py"])
    rc = chassis_lag_id_checker.main()
    assert rc == -1
    expected_msg = (
        "ERROR    root:chassis_lag_id_checker.py:103 "
        "No SYSTEM_LAG_ID_TABLE found in chassis_db"
    )
    assert caplog.text.strip() == expected_msg


def test_run_redis_dump_failure(monkeypatch):
    class FakeCompleted:
        def __init__(self, stdout="", stderr="", returncode=1):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd_args, capture_output=True, text=True):
        return FakeCompleted(stdout="", stderr="error", returncode=1)

    monkeypatch.setattr(chassis_lag_id_checker.subprocess, "run", fake_run)
    out = chassis_lag_id_checker.run_redis_dump(["redis-dump", "-d", "1", "-y"])
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
    monkeypatch.setattr(chassis_lag_id_checker.subprocess, "run", fake_run)

    # Now call script functions; they will use the mocked run
    table = chassis_lag_id_checker.get_chassis_lag_db_table()
    assert table == {"hostname|asic0|PortChannel1": "100"}
