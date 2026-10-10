from types import SimpleNamespace
from unittest import mock

import pytest

from utilities_common import redis_read_broker as connector


@pytest.fixture
def broker_config():
    return SimpleNamespace(
        namespace="",
        broker_socket="/run/broker/redis.sock",
        database_names=("CONFIG_DB", "STATE_DB"),
    )


def test_sonic_connector_uses_only_broker_socket(monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    db_connection = mock.Mock()
    db_factory = mock.Mock(return_value=db_connection)
    monkeypatch.setattr(connector, "DBConnector", db_factory)

    db = connector.BrokerSonicV2Connector()
    db.connect("CONFIG_DB")

    db_factory.assert_called_once_with(4, "/run/broker/redis.sock", connector.BROKER_TIMEOUT_MS)
    assert db.CONFIG_DB == "CONFIG_DB"
    assert db.get_db_list() == ("CONFIG_DB", "STATE_DB")
    assert db.exists("CONFIG_DB", "key") == db_connection.exists.return_value
    db_connection.exists.assert_called_once_with("key")


def test_sonic_connector_rejects_namespace_and_unknown_database(monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)

    with pytest.raises(RuntimeError, match="namespace"):
        connector.BrokerSonicV2Connector(namespace="asic0")

    db = connector.BrokerSonicV2Connector()
    with pytest.raises(RuntimeError, match="not configured"):
        db.connect("APPL_DB")
    with pytest.raises(RuntimeError, match="not connected"):
        db.exists("CONFIG_DB", "key")


def test_sonic_connector_reads_hashes_and_bounded_scans(monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    connection = mock.Mock()
    connection.hgetall.return_value = [("field", "value")]
    connection.scan.side_effect = [(1, ["a"]), (0, ["b"])]
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    monkeypatch.setattr(connector, "DBConnector", mock.Mock(return_value=connection))

    db = connector.BrokerSonicV2Connector()
    db.connect("CONFIG_DB")

    assert db.get_all("CONFIG_DB", "key") == {"field": "value"}
    assert db.keys("CONFIG_DB", "FEATURE|*") == ["a", "b"]
    assert connection.scan.call_args_list == [
        mock.call(0, "FEATURE|*", connector.SCAN_COUNT),
        mock.call(1, "FEATURE|*", connector.SCAN_COUNT),
    ]
    with pytest.raises(RuntimeError, match="blocking"):
        db.get_all("CONFIG_DB", "key", blocking=True)


def test_sonic_connector_enforces_scan_limit(monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    connection = mock.Mock()
    connection.scan.return_value = (1, ["key"] * 3)
    monkeypatch.setattr(connector, "MAX_SCAN_KEYS", 2)
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    monkeypatch.setattr(connector, "DBConnector", mock.Mock(return_value=connection))
    db = connector.BrokerSonicV2Connector()
    db.connect("CONFIG_DB")

    with pytest.raises(RuntimeError, match="key limit"):
        db.keys("CONFIG_DB", "*")


def test_sonic_connector_metadata_and_close(monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    monkeypatch.setattr(connector.SonicDBConfig, "getSeparator", mock.Mock(return_value="|"))
    monkeypatch.setattr(connector, "DBConnector", mock.Mock())
    db = connector.BrokerSonicV2Connector()

    assert db.get_dbid("CONFIG_DB") == 4
    assert db.get_db_separator("CONFIG_DB") == "|"
    db.connect("CONFIG_DB")
    db.close("CONFIG_DB")
    assert db._connections == {}
    db.connect("STATE_DB")
    db.close()
    assert db._connections == {}


@pytest.fixture
def config_db(monkeypatch):
    inner = mock.Mock()
    monkeypatch.setattr(connector, "BrokerSonicV2Connector", mock.Mock(return_value=inner))
    monkeypatch.setattr(connector.SonicDBConfig, "getSeparator", mock.Mock(return_value="|"))
    return connector.BrokerConfigDBConnector(), inner


def test_config_connector_connects_and_checks_initialization(config_db):
    db, inner = config_db
    inner.exists.return_value = True

    db.connect()

    inner.connect.assert_called_once_with("CONFIG_DB", retry_on=False)
    inner.exists.assert_called_once_with(
        "CONFIG_DB", connector.ConfigDBConnector.INIT_INDICATOR)
    db.close()
    inner.close.assert_called_once_with()


def test_config_connector_rejects_uninitialized_database(config_db):
    db, inner = config_db
    inner.exists.return_value = False

    with pytest.raises(RuntimeError, match="not initialized"):
        db.connect()

    inner.reset_mock()
    db.connect(wait_for_init=False)
    inner.exists.assert_not_called()


def test_config_connector_reads_entries_keys_and_table(config_db):
    db, inner = config_db
    inner.get_all.side_effect = [
        {"field": "value", "members@": "a,b", "NULL": "ignored"},
        {"state": "enabled"},
        {"state": "disabled"},
    ]
    inner.keys.side_effect = [
        ["FEATURE|bgp", "FEATURE|teamd|asic0"],
        ["FEATURE|bgp", "OTHER|ignored", "FEATURE|teamd"],
    ]

    assert db.get_entry("FEATURE", "bgp") == {
        "field": "value", "members": ["a", "b"]}
    assert db.get_keys("FEATURE") == ["bgp", ("teamd", "asic0")]
    assert db.get_table("FEATURE") == {
        "bgp": {"state": "enabled"},
        "teamd": {"state": "disabled"},
    }
    assert db.KEY_SEPARATOR == "|"
    assert db.TABLE_NAME_SEPARATOR == "|"
    assert db.serialize_key(("a", "b")) == "a|b"
    assert db.serialize_key(7) == "7"
    assert db.deserialize_key("a") == "a"
    assert db.deserialize_key("a|b") == ("a", "b")
