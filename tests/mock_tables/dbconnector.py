# MONKEY PATCH!!!
import json
import os
import sys
import re
import ipaddress
from unittest import mock

import mockredis
import redis
import swsssdk
from sonic_py_common import multi_asic
from swsssdk import SonicDBConfig, SonicV2Connector, ConfigDBConnector, ConfigDBPipeConnector
from swsscommon import swsscommon


topo = None
dedicated_dbs = {}

def clean_up_config():
    # Set SonicDBConfig variables to initial state
    # so that it can be loaded with single or multiple
    # namespaces before the test begins.
    SonicDBConfig._sonic_db_config = {}
    SonicDBConfig._sonic_db_global_config_init = False
    SonicDBConfig._sonic_db_config_init = False

def load_namespace_config():
    # To support multi asic testing
    # SonicDBConfig load_sonic_global_db_config
    # is invoked to load multiple namespaces
    clean_up_config()
    SonicDBConfig.load_sonic_global_db_config(
        global_db_file_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'database_global.json'))

def load_database_config():
    # Load local database_config.json for single namespace test scenario
    clean_up_config()
    SonicDBConfig.load_sonic_db_config(
        sonic_db_file_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'database_config.json'))


_old_connect_SonicV2Connector = SonicV2Connector.connect

def connect_SonicV2Connector(self, db_name, retry_on=True):
    # add topo to kwargs for testing different topology
    self.dbintf.redis_kwargs['topo'] = topo
    # add the namespace to kwargs for testing multi asic
    self.dbintf.redis_kwargs['namespace'] = self.namespace
    # Mock DB filename for unit-test
    global dedicated_dbs
    if dedicated_dbs and dedicated_dbs.get(db_name):
        self.dbintf.redis_kwargs['db_name'] = dedicated_dbs[db_name]
    else:
        self.dbintf.redis_kwargs['db_name'] = db_name
    self.dbintf.redis_kwargs['decode_responses'] = True
    _old_connect_SonicV2Connector(self, db_name, retry_on)

def _subscribe_keyspace_notification(self, db_name, client):
    pass

def mock_close(self, db_name):
    pass

def config_set(self, *args):
    pass


class MockPubSub:
    class MessageList:
        """A custom subscriptable class to hold messages in a list-like format"""
        def __init__(self, channel):
            self._data = []
            self._channel = channel

        def __getitem__(self, index):
            return self._data[index]

        def __setitem__(self, index, value):
            self._data[index] = value

        def append(self, msg):
            print(f"Message published to {self._channel}: ", msg)
            self._data.append(msg)

    def __init__(self, namespace):
        # Initialize channels required for testing
        self.messages = self.MessageList('WATERMARK_CLEAR_REQUEST')
        self.channels = {'WATERMARK_CLEAR_REQUEST': self.messages}
        self.namespace = namespace

    def __getitem__(self, key):
        print("Channel:", key, "accessed in namespace:", self.namespace)
        return self.channels[key]

    def get_message(self):
        return None

    def psubscribe(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self

    def listen(self):
        return []

    def punsubscribe(self, *args, **kwargs):
        pass

    def clear(self):
        pass

INPUT_DIR = os.path.dirname(os.path.abspath(__file__))


class SwssSyncClient(mockredis.MockRedis):
    def __init__(self, *args, **kwargs):
        super(SwssSyncClient, self).__init__(strict=True, *args, **kwargs)
        # Namespace is added in kwargs specifically for unit-test
        # to identify the file path to load the db json files.
        topo = kwargs.pop('topo')
        namespace = kwargs.pop('namespace')
        db_name = kwargs.pop('db_name')
        self.decode_responses = kwargs.pop('decode_responses', False) == True
        fname = db_name.lower() + ".json"
        self.pubsub = MockPubSub(namespace)

        if namespace is not None and namespace is not multi_asic.DEFAULT_NAMESPACE:
            fname = os.path.join(INPUT_DIR, namespace, fname)
        elif topo is not None:
            fname = os.path.join(INPUT_DIR, topo, fname)
        else:
            fname = os.path.join(INPUT_DIR, fname)

        if os.path.exists(fname):
            with open(fname) as f:
                js = json.load(f)
                for k, v in js.items():
                    if 'expireat' in v and 'ttl' in v and 'type' in v and 'value' in v:
                        # database is in redis-dump format
                        if v['type'] == 'hash':
                            # ignore other types for now since sonic has hset keys only in the db
                            for attr, value in v['value'].items():
                                self.hset(k, attr, value)
                    else:
                        for attr, value in v.items():
                            self.hset(k, attr, value)

    # Patch mockredis/mockredis/client.py
    # The offical implementation assume decode_responses=False
    def _common_scan(self, values_function, cursor='0', match=None, count=10, key=None):
        """
        Common scanning skeleton.

        :param key: optional function used to identify what 'match' is applied to
        """
        if count is None:
            count = 10
        cursor = int(cursor)
        count = int(count)
        if not count:
            raise ValueError('if specified, count must be > 0: %s' % count)

        values = values_function()
        if cursor + count >= len(values):
            # we reached the end, back to zero
            result_cursor = 0
        else:
            result_cursor = cursor + count

        values = values[cursor:cursor+count]

        if match is not None:
            if self.decode_responses:
                regex = re.compile('^' + re.escape(self._encode(match)).replace('\\*', '.*') + '$')
            else:
                regex = re.compile(b'^' + re.escape(self._encode(match)).replace(b'\\*', b'.*') + b'$')
            if not key:
                key = lambda v: v
            values = [v for v in values if regex.match(key(v))]

        return [result_cursor, values]

    # Patch mockredis/mockredis/client.py
    # The offical implementation assume decode_responses=False
    # Here we detect the option and decode after doing encode
    def _encode(self, value):
        "Return a bytestring representation of the value. Taken from redis-py connection.py"

        value = super(SwssSyncClient, self)._encode(value)

        if self.decode_responses:
            return value.decode('utf-8')

    # Patch mockredis/mockredis/client.py
    # The official implementation will filter out keys with a slash '/'
    # ref: https://github.com/locationlabs/mockredis/blob/master/mockredis/client.py
    def keys(self, pattern='*'):
        """Emulate keys."""
        import fnmatch
        import re

        # Make regex out of glob styled pattern.
        regex = fnmatch.translate(pattern)
        regex = re.compile(regex)

        # Find every key that matches the pattern
        return [key for key in self.redis if regex.match(key)]


class PortCounter:
    pass


class CounterTable:
    def __init__(self, db):
        self.db = db

    def get(self, counter, name):
        if isinstance(counter, PortCounter):
            name_map = "COUNTERS_PORT_NAME_MAP"
        else:
            return False, ()

        key = self.db.hget(name_map, name)
        return True, tuple(self.db.get("COUNTERS:" + key).items())


class DBConnector:

    def __init__(self, *args):

        self.data = None
        ip_to_asic = {
            "192.168.3.10": "asic0",
            "192.168.3.11": "asic1",
            "192.168.5.1": "asic2",
            "192.168.6.1": "asic3"
        }

        redis_kwargs = {}

        # Check if IP is being used to connect to redis
        if len(args) == 4:
            try:
                ip = args[1]
                ipaddress.ip_address(args[1])
                redis_kwargs['namespace'] = ip_to_asic[ip] if ip is not None else ip
            except ValueError:
                redis_kwargs['namespace'] = args[3]

        redis_kwargs['db_name'] = 'counters_db'
        redis_kwargs['topo'] = None
        redis_kwargs['unix_socket_path'] = None
        redis_kwargs['decode_responses'] = True
        self.swsssyncclient = SwssSyncClient(**redis_kwargs)

    def hgetall(self, key):
        return self.swsssyncclient.hgetall(key)

    def hget(self, key, attr):
        return self.swsssyncclient.hget(key, attr)


swsscommon.DBConnector = DBConnector
swsssdk.interface.DBInterface._subscribe_keyspace_notification = _subscribe_keyspace_notification
swsssdk.interface.DBInterface.close = mock_close
mockredis.MockRedis.config_set = config_set
redis.StrictRedis = SwssSyncClient
SonicV2Connector.connect = connect_SonicV2Connector
swsscommon.SonicV2Connector = SonicV2Connector
swsscommon.ConfigDBConnector = ConfigDBConnector
swsscommon.ConfigDBPipeConnector = ConfigDBPipeConnector
swsscommon.CounterTable = CounterTable
swsscommon.PortCounter = PortCounter
