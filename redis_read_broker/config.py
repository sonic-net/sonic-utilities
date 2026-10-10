"""Root-controlled mapping from one broker instance to one Redis socket."""

import json
import os
import re
import stat

from swsscommon import swsscommon

from utilities_common.general import load_db_config


CONFIG_DIRECTORY = "/etc/sonic/redis-read-broker"
RUNTIME_DIRECTORY_PREFIX = "/run/sonic-redis-read-broker-"
MAX_CONFIG_BYTES = 65536
_INSTANCE_NAME = re.compile(r"[A-Za-z0-9_.]+\Z")
_DATABASE_NAME = re.compile(r"[A-Z][A-Z0-9_]+\Z")


class BrokerConfigError(Exception):
    pass


class BrokerConfig(object):
    __slots__ = (
        "instance", "namespace", "database", "database_names",
        "database_ids", "upstream_socket", "broker_socket",
        "skipped_databases",
    )

    def __init__(self, instance, namespace, database, database_names,
                 database_ids, upstream_socket, broker_socket,
                 skipped_databases):
        self.instance = instance
        self.namespace = namespace
        self.database = database
        self.database_names = tuple(database_names)
        self.database_ids = tuple(database_ids)
        self.upstream_socket = upstream_socket
        self.broker_socket = broker_socket
        self.skipped_databases = tuple(skipped_databases)


def validate_instance_name(instance):
    if not isinstance(instance, str) or not _INSTANCE_NAME.match(instance):
        raise BrokerConfigError(
            "instance must contain only letters, digits, period, or underscore")
    return instance


def broker_socket_path(instance):
    validate_instance_name(instance)
    return "{}{}/redis.sock".format(RUNTIME_DIRECTORY_PREFIX, instance)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BrokerConfigError("duplicate configuration key")
        result[key] = value
    return result


def _read_config(instance):
    validate_instance_name(instance)
    directory_stat = os.stat(CONFIG_DIRECTORY, follow_symlinks=False)
    if (not stat.S_ISDIR(directory_stat.st_mode) or
            directory_stat.st_uid != 0 or
            directory_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
        raise BrokerConfigError("configuration directory is not root controlled")

    path = os.path.join(CONFIG_DIRECTORY, instance + ".json")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        file_stat = os.fstat(fd)
        if (not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != 0 or
                file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
            raise BrokerConfigError("configuration file is not root controlled")
        if file_stat.st_size > MAX_CONFIG_BYTES:
            raise BrokerConfigError("configuration file is too large")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
    finally:
        os.close(fd)

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except BrokerConfigError:
        raise
    except (UnicodeDecodeError, ValueError):
        raise BrokerConfigError("configuration file is not valid JSON")


def _validate_document(document):
    if not isinstance(document, dict):
        raise BrokerConfigError("configuration must be an object")
    expected = frozenset(("namespace", "database", "allowed_databases"))
    if set(document) != expected:
        raise BrokerConfigError("configuration fields do not match the schema")

    namespace = document["namespace"]
    database = document["database"]
    allowed = document["allowed_databases"]
    if not isinstance(namespace, str) or len(namespace) > 128 or "\x00" in namespace:
        raise BrokerConfigError("invalid namespace")
    if not isinstance(database, str) or not _DATABASE_NAME.match(database):
        raise BrokerConfigError("invalid representative database")
    if (not isinstance(allowed, list) or not allowed or len(allowed) > 64 or
            any(not isinstance(name, str) or not _DATABASE_NAME.match(name)
                for name in allowed)):
        raise BrokerConfigError("invalid allowed database list")
    if len(set(allowed)) != len(allowed) or database not in allowed:
        raise BrokerConfigError(
            "allowed databases must be unique and include the representative database")
    return namespace, database, allowed


def load_instance_config(instance):
    """Resolve an instance without accepting any endpoint from the caller."""

    namespace, database, allowed = _validate_document(_read_config(instance))
    load_db_config()

    try:
        configured_names = set(swsscommon.SonicDBConfig.getDbList(namespace))
        if database not in configured_names:
            raise BrokerConfigError("representative database is not configured")
        upstream = swsscommon.SonicDBConfig.getDbSock(database, namespace)
    except BrokerConfigError:
        raise
    except Exception:
        raise BrokerConfigError("database metadata could not be resolved")

    if (not isinstance(upstream, str) or not os.path.isabs(upstream) or
            "\x00" in upstream or len(upstream.encode("utf-8")) > 103):
        raise BrokerConfigError("database does not have a usable local Unix socket")

    database_names = []
    database_ids = []
    skipped = []
    for name in allowed:
        if name not in configured_names:
            skipped.append(name)
            continue
        try:
            socket_path = swsscommon.SonicDBConfig.getDbSock(name, namespace)
            db_id = swsscommon.SonicDBConfig.getDbId(name, namespace)
        except Exception:
            raise BrokerConfigError("allowed database metadata could not be resolved")
        if socket_path != upstream:
            skipped.append(name)
            continue
        if db_id in database_ids:
            raise BrokerConfigError("allowed databases share a logical database ID")
        database_names.append(name)
        database_ids.append(db_id)

    if database not in database_names:
        raise BrokerConfigError("representative database mapping is inconsistent")

    return BrokerConfig(
        instance=instance,
        namespace=namespace,
        database=database,
        database_names=database_names,
        database_ids=database_ids,
        upstream_socket=upstream,
        broker_socket=broker_socket_path(instance),
        skipped_databases=skipped,
    )
