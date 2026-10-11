from sonic_py_common import multi_asic, device_info
from swsscommon.swsscommon import ConfigDBConnector, ConfigDBPipeConnector, SonicV2Connector, SonicDBConfig
from utilities_common import constants
from utilities_common.multi_asic import multi_asic_ns_choices


class Db(object):
    def __init__(self):
        self.cfgdb_clients = {}
        self.db_clients = {}
        self.cfgdb = ConfigDBConnector()
        self.cfgdb.connect()
        self.cfgdb_pipe = ConfigDBPipeConnector()
        self.cfgdb_pipe.connect()
        self.db = SonicV2Connector(host="127.0.0.1")

        # Skip connecting to chassis databases in line cards
        self.db_list = list(self.db.get_db_list())
        if not device_info.is_supervisor():
            try:
                self.db_list.remove('CHASSIS_APP_DB')
                self.db_list.remove('CHASSIS_STATE_DB')
            except Exception:
                pass

        for db_id in self.db_list:
            self.db.connect(db_id)

        self.cfgdb_clients[constants.DEFAULT_NAMESPACE] = self.cfgdb
        self.db_clients[constants.DEFAULT_NAMESPACE] = self.db

        if multi_asic.is_multi_asic():
            if not SonicDBConfig.isGlobalInit():
                SonicDBConfig.initializeGlobalConfig()
            self.ns_list = multi_asic_ns_choices()
            for ns in self.ns_list:
                self.cfgdb_clients[ns] = (
                    multi_asic.connect_config_db_for_ns(ns)
                )
                self.db_clients[ns] = multi_asic.connect_to_all_dbs_for_ns(ns)

    def get_data(self, table, key):
        data = self.cfgdb.get_table(table)
        return data[key] if key in data else None
