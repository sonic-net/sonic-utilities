import json
import stat
from types import SimpleNamespace
from unittest import mock

import pytest

from redis_read_broker import config


@pytest.mark.parametrize("name", ["default", "asic0", "line.card_1", "A9"])
def test_validates_instance_names(name):
    assert config.validate_instance_name(name) == name
    assert config.broker_socket_path(name).endswith("-{}/redis.sock".format(name))


@pytest.mark.parametrize("name", [None, "", "../bad", "bad-name", "bad/name", "name\n"])
def test_rejects_invalid_instance_names(name):
    with pytest.raises(config.BrokerConfigError):
        config.validate_instance_name(name)


def test_rejects_duplicate_json_keys():
    with pytest.raises(config.BrokerConfigError, match="duplicate"):
        config._reject_duplicate_keys([("a", 1), ("a", 2)])


def _root_directory_stat(mode=stat.S_IFDIR | 0o755):
    return SimpleNamespace(st_mode=mode, st_uid=0)


def _root_file_stat(size, mode=stat.S_IFREG | 0o644):
    return SimpleNamespace(st_mode=mode, st_uid=0, st_size=size)


def test_reads_root_controlled_config(tmp_path, monkeypatch):
    document = {
        "namespace": "",
        "database": "CONFIG_DB",
        "allowed_databases": ["CONFIG_DB"],
    }
    path = tmp_path / "default.json"
    raw = json.dumps(document).encode()
    path.write_bytes(raw)
    monkeypatch.setattr(config, "CONFIG_DIRECTORY", str(tmp_path))

    with mock.patch.object(config.os, "stat", return_value=_root_directory_stat()), \
            mock.patch.object(config.os, "fstat", return_value=_root_file_stat(len(raw))):
        assert config._read_config("default") == document


def test_rejects_unsafe_config_directory(monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIRECTORY", "/unsafe")
    unsafe = SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_uid=0)
    with mock.patch.object(config.os, "stat", return_value=unsafe):
        with pytest.raises(config.BrokerConfigError, match="directory"):
            config._read_config("default")


def test_rejects_unsafe_or_large_config_file(tmp_path, monkeypatch):
    path = tmp_path / "default.json"
    path.write_text("{}")
    monkeypatch.setattr(config, "CONFIG_DIRECTORY", str(tmp_path))

    with mock.patch.object(config.os, "stat", return_value=_root_directory_stat()), \
            mock.patch.object(config.os, "fstat", return_value=_root_file_stat(2, stat.S_IFREG | 0o666)):
        with pytest.raises(config.BrokerConfigError, match="file"):
            config._read_config("default")

    with mock.patch.object(config.os, "stat", return_value=_root_directory_stat()), \
            mock.patch.object(config.os, "fstat", return_value=_root_file_stat(config.MAX_CONFIG_BYTES + 1)):
        with pytest.raises(config.BrokerConfigError, match="large"):
            config._read_config("default")


@pytest.mark.parametrize("raw", [b"not-json", b"{\"a\": 1, \"a\": 2}", b"\xff"])
def test_rejects_invalid_config_json(tmp_path, monkeypatch, raw):
    path = tmp_path / "default.json"
    path.write_bytes(raw)
    monkeypatch.setattr(config, "CONFIG_DIRECTORY", str(tmp_path))

    with mock.patch.object(config.os, "stat", return_value=_root_directory_stat()), \
            mock.patch.object(config.os, "fstat", return_value=_root_file_stat(len(raw))):
        with pytest.raises(config.BrokerConfigError):
            config._read_config("default")


def test_validates_config_document():
    document = {
        "namespace": "asic0",
        "database": "CONFIG_DB",
        "allowed_databases": ["CONFIG_DB", "STATE_DB"],
    }
    assert config._validate_document(document) == (
        "asic0", "CONFIG_DB", ["CONFIG_DB", "STATE_DB"])


@pytest.mark.parametrize("document", [
    [],
    {},
    {"namespace": "", "database": "CONFIG_DB", "allowed_databases": ["CONFIG_DB"], "extra": 1},
    {"namespace": None, "database": "CONFIG_DB", "allowed_databases": ["CONFIG_DB"]},
    {"namespace": "x\x00", "database": "CONFIG_DB", "allowed_databases": ["CONFIG_DB"]},
    {"namespace": "", "database": "bad", "allowed_databases": ["CONFIG_DB"]},
    {"namespace": "", "database": "CONFIG_DB", "allowed_databases": []},
    {"namespace": "", "database": "CONFIG_DB", "allowed_databases": ["bad"]},
    {"namespace": "", "database": "CONFIG_DB", "allowed_databases": ["CONFIG_DB", "CONFIG_DB"]},
    {"namespace": "", "database": "CONFIG_DB", "allowed_databases": ["STATE_DB"]},
])
def test_rejects_invalid_config_documents(document):
    with pytest.raises(config.BrokerConfigError):
        config._validate_document(document)


class FakeSonicDBConfig(object):
    sockets = {
        "CONFIG_DB": "/var/run/redis/redis.sock",
        "STATE_DB": "/var/run/redis/redis.sock",
        "APPL_DB": "/other/redis.sock",
    }
    ids = {"CONFIG_DB": 4, "STATE_DB": 6, "APPL_DB": 0}

    @classmethod
    def getDbList(cls, _namespace):
        return list(cls.sockets)

    @classmethod
    def getDbSock(cls, name, _namespace):
        return cls.sockets[name]

    @classmethod
    def getDbId(cls, name, _namespace):
        return cls.ids[name]


def test_loads_database_mapping_and_skips_other_endpoints(monkeypatch):
    monkeypatch.setattr(config, "_read_config", lambda _instance: {
        "namespace": "",
        "database": "CONFIG_DB",
        "allowed_databases": ["CONFIG_DB", "STATE_DB", "APPL_DB", "CHASSIS_APP_DB"],
    })
    load = mock.Mock()
    monkeypatch.setattr(config, "load_db_config", load)
    monkeypatch.setattr(config.swsscommon, "SonicDBConfig", FakeSonicDBConfig)

    result = config.load_instance_config("default")

    load.assert_called_once_with()
    assert result.database_names == ("CONFIG_DB", "STATE_DB")
    assert result.database_ids == (4, 6)
    assert result.skipped_databases == ("APPL_DB", "CHASSIS_APP_DB")
    assert result.upstream_socket == "/var/run/redis/redis.sock"


def test_rejects_unusable_upstream_socket(monkeypatch):
    monkeypatch.setattr(config, "_read_config", lambda _instance: {
        "namespace": "", "database": "CONFIG_DB", "allowed_databases": ["CONFIG_DB"]})
    monkeypatch.setattr(config, "load_db_config", lambda: None)
    fake = mock.Mock()
    fake.getDbList.return_value = ["CONFIG_DB"]
    fake.getDbSock.return_value = "127.0.0.1"
    monkeypatch.setattr(config.swsscommon, "SonicDBConfig", fake)

    with pytest.raises(config.BrokerConfigError, match="Unix socket"):
        config.load_instance_config("default")


def test_rejects_missing_representative_database(monkeypatch):
    monkeypatch.setattr(config, "_read_config", lambda _instance: {
        "namespace": "", "database": "CONFIG_DB", "allowed_databases": ["CONFIG_DB"]})
    monkeypatch.setattr(config, "load_db_config", lambda: None)
    fake = mock.Mock()
    fake.getDbList.return_value = ["STATE_DB"]
    monkeypatch.setattr(config.swsscommon, "SonicDBConfig", fake)

    with pytest.raises(config.BrokerConfigError, match="not configured"):
        config.load_instance_config("default")


def test_rejects_duplicate_database_ids(monkeypatch):
    monkeypatch.setattr(config, "_read_config", lambda _instance: {
        "namespace": "", "database": "CONFIG_DB",
        "allowed_databases": ["CONFIG_DB", "STATE_DB"]})
    monkeypatch.setattr(config, "load_db_config", lambda: None)
    fake = mock.Mock()
    fake.getDbList.return_value = ["CONFIG_DB", "STATE_DB"]
    fake.getDbSock.return_value = "/var/run/redis.sock"
    fake.getDbId.return_value = 4
    monkeypatch.setattr(config.swsscommon, "SonicDBConfig", fake)

    with pytest.raises(config.BrokerConfigError, match="logical database ID"):
        config.load_instance_config("default")
