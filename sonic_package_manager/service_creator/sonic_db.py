#!/usr/bin/env python

import contextlib
import json
import os

from swsscommon import swsscommon

from config.config_mgmt import sonic_cfggen

from sonic_package_manager.service_creator import ETC_SONIC_PATH
from sonic_package_manager.service_creator.utils import in_chroot

CONFIG_DB = 'CONFIG_DB'
INIT_CFG_JSON = os.path.join(ETC_SONIC_PATH, 'init_cfg.json')


class PersistentConfigDbConnector:
    """ This class implements swsscommon.ConfigDBConnector methods for persistent DBs (JSON files).
    For method description refer to swsscommon.ConfigDBConnector.
    """

    def __init__(self, filepath):
        self._filepath = filepath

    def get_config(self):
        with open(self._filepath) as stream:
            config = json.load(stream)
        config = sonic_cfggen.FormatConverter.to_deserialized(config)
        return config

    def get_entry(self, table, key):
        table = table.upper()
        table_data = self.get_table(table)
        return table_data.get(key, {})

    def get_table(self, table):
        table = table.upper()
        config = self.get_config()
        return config.get(table, {})

    def set_entry(self, table, key, data):
        table = table.upper()
        config = self.get_config()
        if data is None:
            self._del_key(config, table, key)
        else:
            table_data = config.setdefault(table, {})
            table_data[key] = data
        self._write_config(config)

    def mod_entry(self, table, key, data):
        table = table.upper()
        config = self.get_config()
        if data is None:
            self._del_key(config, table, key)
        else:
            table_data = config.setdefault(table, {})
            curr_data = table_data.setdefault(key, {})
            curr_data.update(data)
        self._write_config(config)

    def mod_config(self, config):
        for table_name in config:
            table_data = config[table_name]
            if table_data is None:
                self._del_table(config, table_name)
                continue
            for key in table_data:
                self.mod_entry(table_name, key, table_data[key])

    def _del_table(self, config, table):
        with contextlib.suppress(KeyError):
            config.pop(table)

    def _del_key(self, config, table, key):
        with contextlib.suppress(KeyError):
            config[table].pop(key)

        if table in config and not config[table]:
            self._del_table(config, table)

    def _write_config(self, config):
        config = sonic_cfggen.FormatConverter.to_serialized(config)
        with open(self._filepath, 'w') as stream:
            json.dump(config, stream, indent=4)


class SonicDB:
    """ Store different DB access objects for
    running DB and also for persistent and initial
    configs. """

    _running_db_conn = None

    @classmethod
    def get_connectors(cls):
        """ Yields available DBs connectors. """

        initial_db_conn = cls.get_initial_db_connector()
        running_db_conn = cls.get_running_db_connector()

        yield initial_db_conn
        if running_db_conn is not None:
            yield running_db_conn

    @classmethod
    def get_running_db_connector(cls):
        """ Returns running DB connector. """

        # In chroot we can connect to a running
        # DB via TCP socket, we should ignore this case.
        if in_chroot():
            return None

        if cls._running_db_conn is None:
            try:
                cls._running_db_conn = swsscommon.ConfigDBConnector()
                cls._running_db_conn.connect()
            except RuntimeError:
                # Failed to connect to DB.
                cls._running_db_conn = None

        return cls._running_db_conn

    @classmethod
    def get_initial_db_connector(cls):
        """ Returns initial DB connector. """

        return PersistentConfigDbConnector(INIT_CFG_JSON)
