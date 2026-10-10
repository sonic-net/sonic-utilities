"""Explicit client connectors for the local Redis read broker.

These connectors always use the named broker Unix socket.  They never retry
through TCP or through the private Redis socket.
"""

from swsscommon.swsscommon import ConfigDBConnector, DBConnector, SonicDBConfig

from redis_read_broker.config import load_instance_config


BROKER_TIMEOUT_MS = 5000
SCAN_COUNT = 512
MAX_SCAN_KEYS = 100000


class BrokerSonicV2Connector(object):
    def __init__(self, instance="default", namespace=""):
        broker_config = load_instance_config(instance)
        self.instance = instance
        self.namespace = namespace or ""
        if self.namespace != broker_config.namespace:
            raise RuntimeError("broker instance does not match the requested namespace")
        self.socket_path = broker_config.broker_socket
        self._connections = {}
        self._db_list = list(broker_config.database_names)
        for db_name in self._db_list:
            setattr(self, db_name, db_name)

    def connect(self, db_name, retry_on=True):
        del retry_on
        if db_name not in self._db_list:
            raise RuntimeError("database is not configured")
        db_id = SonicDBConfig.getDbId(db_name, self.namespace)
        # This overload accepts a numeric DB ID and a Unix socket path.  It
        # cannot fall back to the hostname and port from database metadata.
        self._connections[db_name] = DBConnector(
            db_id, self.socket_path, BROKER_TIMEOUT_MS)

    def close(self, db_name=None):
        if db_name is None:
            self._connections.clear()
        else:
            self._connections.pop(db_name, None)

    def get_db_list(self):
        return tuple(self._db_list)

    def get_dbid(self, db_name):
        return SonicDBConfig.getDbId(db_name, self.namespace)

    def get_db_separator(self, db_name):
        return SonicDBConfig.getSeparator(db_name, self.namespace)

    def exists(self, db_name, key):
        return self._connection(db_name).exists(key)

    def get_all(self, db_name, key, blocking=False):
        if blocking:
            raise RuntimeError("blocking reads are not supported by the read broker")
        return dict(self._connection(db_name).hgetall(key))

    def keys(self, db_name, pattern):
        """Use bounded SCAN calls instead of Redis KEYS."""

        connection = self._connection(db_name)
        cursor = 0
        keys = []
        while True:
            cursor, batch = connection.scan(cursor, pattern, SCAN_COUNT)
            keys.extend(batch)
            if len(keys) > MAX_SCAN_KEYS:
                raise RuntimeError("read broker scan key limit exceeded")
            cursor = int(cursor)
            if cursor == 0:
                return keys

    def _connection(self, db_name):
        try:
            return self._connections[db_name]
        except KeyError:
            raise RuntimeError("database is not connected")


class BrokerConfigDBConnector(object):
    """Read-only ConfigDB view backed by an explicit broker connector."""

    def __init__(self, instance="default", namespace=""):
        self._db = BrokerSonicV2Connector(instance=instance, namespace=namespace)
        self.namespace = namespace or ""
        self.db_name = "CONFIG_DB"
        self._separator = SonicDBConfig.getSeparator(self.db_name, self.namespace)

    @property
    def KEY_SEPARATOR(self):
        return self._separator

    @property
    def TABLE_NAME_SEPARATOR(self):
        return self._separator

    def connect(self, wait_for_init=True, retry_on=False):
        del retry_on
        self._db.connect(self.db_name, retry_on=False)
        if (wait_for_init and
                not self._db.exists(self.db_name, ConfigDBConnector.INIT_INDICATOR)):
            raise RuntimeError("CONFIG_DB is not initialized")

    def close(self):
        self._db.close()

    def get_entry(self, table, key):
        redis_key = self._table_key(table, self.serialize_key(key))
        return self.raw_to_typed(self._db.get_all(self.db_name, redis_key))

    def get_keys(self, table, split=True):
        prefix = self._table_key(table, "")
        keys = []
        for redis_key in self._db.keys(self.db_name, prefix + "*"):
            row = redis_key[len(prefix):]
            keys.append(self.deserialize_key(row) if split else row)
        return keys

    def get_table(self, table):
        result = {}
        prefix = self._table_key(table, "")
        for redis_key in self._db.keys(self.db_name, prefix + "*"):
            if not redis_key.startswith(prefix):
                continue
            row = self.deserialize_key(redis_key[len(prefix):])
            result[row] = self.raw_to_typed(
                self._db.get_all(self.db_name, redis_key))
        return result

    def _table_key(self, table, key):
        return "{}{}{}".format(table, self.TABLE_NAME_SEPARATOR, key)

    def serialize_key(self, key):
        if isinstance(key, tuple):
            return self.KEY_SEPARATOR.join(key)
        return str(key)

    def deserialize_key(self, key):
        tokens = key.split(self.KEY_SEPARATOR)
        return tuple(tokens) if len(tokens) > 1 else key

    @staticmethod
    def raw_to_typed(raw_data):
        typed_data = {}
        for key, value in raw_data.items():
            if key == "NULL":
                continue
            if key.endswith("@"):
                typed_data[key[:-1]] = value.split(",")
            else:
                typed_data[key] = value
        return typed_data
