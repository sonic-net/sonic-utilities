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


def test_sonic_connector_retries_only_when_requested(
        monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    connection = mock.Mock()
    db_factory = mock.Mock(side_effect=[RuntimeError("unavailable"), connection])
    monkeypatch.setattr(connector, "DBConnector", db_factory)
    sleep = mock.Mock()
    monkeypatch.setattr(connector.time, "sleep", sleep)

    db = connector.BrokerSonicV2Connector()
    db.connect("CONFIG_DB", retry_on=True)

    assert db.get_redis_client("CONFIG_DB") is connection
    assert db_factory.call_count == 2
    sleep.assert_called_once_with(connector.CONNECT_RETRY_SECONDS)

    db_factory.reset_mock(side_effect=True)
    sleep.reset_mock()
    db_factory.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        db.connect("STATE_DB", retry_on=False)
    db_factory.assert_called_once_with(
        4, "/run/broker/redis.sock", connector.BROKER_TIMEOUT_MS)
    sleep.assert_not_called()


def test_sonic_connector_reads_hashes_and_keys(monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    connection = mock.Mock()
    connection.hget.side_effect = ["value", None, "None"]
    connection.hgetall.return_value = [("field", "value"), ("empty", "None")]
    connection.keys.return_value = ["a", "b"]
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    monkeypatch.setattr(connector, "DBConnector", mock.Mock(return_value=connection))

    db = connector.BrokerSonicV2Connector()
    db.connect("CONFIG_DB")

    assert db.get("CONFIG_DB", "key", "field") == "value"
    assert db.get("CONFIG_DB", "key", "missing") is None
    assert db.get("CONFIG_DB", "key", "sentinel") is None
    assert db.get_all("CONFIG_DB", "key") == {"field": "value", "empty": ""}
    assert db.keys("CONFIG_DB", "FEATURE|*") == ["a", "b"]
    connection.keys.assert_called_once_with("FEATURE|*")
    assert db.keys("CONFIG_DB") == ["a", "b"]
    connection.keys.assert_called_with("*")
    assert db.get_redis_client("CONFIG_DB") is connection
    with pytest.raises(RuntimeError, match="blocking"):
        db.get("CONFIG_DB", "key", "field", blocking=True)
    with pytest.raises(RuntimeError, match="blocking"):
        db.get_all("CONFIG_DB", "key", blocking=True)
    with pytest.raises(RuntimeError, match="blocking"):
        db.keys("CONFIG_DB", blocking=True)


def test_sonic_connector_reconnects_and_replays_failed_read(
        monkeypatch, broker_config):
    monkeypatch.setattr(connector, "load_instance_config", lambda _instance: broker_config)
    monkeypatch.setattr(connector.SonicDBConfig, "getDbId", mock.Mock(return_value=4))
    first = mock.Mock()
    first.hget.side_effect = RuntimeError("connection lost")
    second = mock.Mock()
    second.hget.return_value = "value"
    monkeypatch.setattr(
        connector, "DBConnector", mock.Mock(side_effect=[first, second]))

    db = connector.BrokerSonicV2Connector()
    db.connect("CONFIG_DB", retry_on=False)

    assert db.get("CONFIG_DB", "key", "field") == "value"
    first.hget.assert_called_once_with("key", "field")
    second.hget.assert_called_once_with("key", "field")
    assert db.get_redis_client("CONFIG_DB") is second


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


def test_config_connector_connects_and_waits_for_initialization(
        monkeypatch, config_db):
    db, inner = config_db
    inner._get_string.side_effect = [None, "", "1"]
    sleep = mock.Mock()
    monkeypatch.setattr(connector.time, "sleep", sleep)

    db.connect()

    inner.connect.assert_called_once_with("CONFIG_DB", retry_on=False)
    assert inner._get_string.call_args_list == [
        mock.call("CONFIG_DB", connector.ConfigDBConnector.INIT_INDICATOR),
        mock.call("CONFIG_DB", connector.ConfigDBConnector.INIT_INDICATOR),
        mock.call("CONFIG_DB", connector.ConfigDBConnector.INIT_INDICATOR),
    ]
    assert sleep.call_args_list == [
        mock.call(connector.CONFIG_DB_INIT_POLL_SECONDS),
        mock.call(connector.CONFIG_DB_INIT_POLL_SECONDS),
    ]
    db.close()
    inner.close.assert_called_once_with()


def test_config_connector_passes_retry_option(config_db):
    db, inner = config_db
    inner._get_string.return_value = "1"

    db.connect(retry_on=True)

    inner.connect.assert_called_once_with("CONFIG_DB", retry_on=True)
    inner._get_string.assert_called_once_with(
        "CONFIG_DB", connector.ConfigDBConnector.INIT_INDICATOR)


def test_config_connector_can_skip_initialization_wait(config_db):
    db, inner = config_db
    db.connect(wait_for_init=False)
    inner._get_string.assert_not_called()


def test_config_connector_reads_entries_keys_and_table(config_db):
    db, inner = config_db
    inner._get_hash.side_effect = [
        {"field": "value", "members@": "a,b", "NULL": "ignored"},
        {"state": "enabled"},
        {"state": "disabled"},
    ]
    inner.keys.side_effect = [
        ["FEATURE|bgp", "FEATURE|teamd|asic0"],
        ["FEATURE|bgp", "FEATURE|teamd|asic0"],
        ["FEATURE|teamd", "OTHER|ignored", "FEATURE|bgp"],
    ]

    assert db.get_entry("feature", "bgp") == {
        "field": "value", "members": ["a", "b"]}
    assert db.get_keys("FEATURE") == ["bgp", ("teamd", "asic0")]
    assert db.get_keys("feature", split=False) == [
        ("FEATURE", "bgp"), ("FEATURE", "teamd", "asic0")]
    table = db.get_table("feature")
    assert table == {
        "bgp": {"state": "enabled"},
        "teamd": {"state": "disabled"},
    }
    assert list(table) == ["bgp", "teamd"]
    assert db.KEY_SEPARATOR == "|"
    assert db.TABLE_NAME_SEPARATOR == "|"
    assert db.serialize_key(("a", "b")) == "a|b"
    assert db.serialize_key(7) == "7"
    assert db.deserialize_key("a") == "a"
    assert db.deserialize_key("a|b") == ("a", "b")


def test_config_connector_preserves_literal_none_values(config_db):
    db, inner = config_db
    inner._get_hash.return_value = {"value": "None"}

    assert db.get_entry("FEATURE", "bgp") == {"value": "None"}
