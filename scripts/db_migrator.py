#!/usr/bin/env python3

import os
import argparse
import json
import sys
import traceback
import re

from sonic_py_common import device_info, logger
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from minigraph import parse_xml
from utilities_common.helper import update_config
from utilities_common.general import load_db_config

INIT_CFG_FILE = '/etc/sonic/init_cfg.json'
MINIGRAPH_FILE = '/etc/sonic/minigraph.xml'
GOLDEN_CFG_FILE = '/etc/sonic/golden_config_db.json'

# mock the redis for unit test purposes #
try:
    if os.environ["UTILITIES_UNIT_TESTING"] == "2":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        tests_path = os.path.join(modules_path, "tests")
        mocked_db_path = os.path.join(tests_path, "db_migrator_input")
        sys.path.insert(0, modules_path)
        sys.path.insert(0, tests_path)
        INIT_CFG_FILE = os.path.join(mocked_db_path, "init_cfg.json")
        MINIGRAPH_FILE = os.path.join(mocked_db_path, "minigraph.xml")
        GOLDEN_CFG_FILE = os.path.join(mocked_db_path, "golden_config_db.json")
except KeyError:
    pass

SYSLOG_IDENTIFIER = 'db_migrator'
DEFAULT_NAMESPACE = ''


# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)


class DBMigrator():
    def __init__(self, namespace, socket=None):
        """
        Version string format (202305 and above):
            version_<branch>_<build>
              branch: master, 202311, 202305, etc.
              build:  sequentially increase with leading 0 to make it 2 digits.
                      because the minor number has been removed to make it different
                      from the old format, adding a leading 0 to make sure that we
                      have double digit version number spaces.
        Version string format (before 202305):
           version_<major>_<minor>_<build>
              major: starting from 1, sequentially incrementing in master
                     branch.
              minor: in github branches, minor version stays in 0. This minor
                     version creates space for private branches derived from
                     github public branches. These private branches shall use
                     none-zero values.
              build: sequentially increase within a minor version domain.
        """
        self.CURRENT_VERSION = 'version_202405_01'

        self.TABLE_NAME      = 'VERSIONS'
        self.TABLE_KEY       = 'DATABASE'
        self.TABLE_FIELD     = 'VERSION'

        # Generate config_src_data from minigraph and golden config
        self.generate_config_src(namespace)

        db_kwargs = {}
        if socket:
            db_kwargs['unix_socket_path'] = socket

        if namespace is None:
            self.configDB = ConfigDBConnector(**db_kwargs)
        else:
            self.configDB = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace, **db_kwargs)
        self.configDB.db_connect('CONFIG_DB')

        if namespace is None:
            self.appDB = ConfigDBConnector(**db_kwargs)
        else:
            self.appDB = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace, **db_kwargs)
        self.appDB.db_connect('APPL_DB')

        self.stateDB = SonicV2Connector(host='127.0.0.1')
        if self.stateDB is not None:
            self.stateDB.connect(self.stateDB.STATE_DB)

        self.loglevelDB = SonicV2Connector(host='127.0.0.1')
        if self.loglevelDB is not None:
            self.loglevelDB.connect(self.loglevelDB.LOGLEVEL_DB)

        version_info = device_info.get_sonic_version_info()
        self.asic_type = version_info.get('asic_type')
        if not self.asic_type:
            log.log_error("ASIC type information not obtained. DB migration will not be reliable")

        self.hwsku = device_info.get_localhost_info('hwsku', self.configDB)
        if not self.hwsku:
            log.log_error("HWSKU information not obtained. DB migration will not be reliable")

        if self.asic_type == "mellanox":
            from mellanox_buffer_migrator import MellanoxBufferMigrator
            self.mellanox_buffer_migrator = MellanoxBufferMigrator(self.configDB, self.appDB, self.stateDB)

    def generate_config_src(self, ns):
        '''
        Generate config_src_data from minigraph and golden config
        This method uses golden_config_data and minigraph_data as local variables,
        which means they are not accessible or modifiable from outside this method.
        This way, this method ensures that these variables are not changed unintentionally.
        Args:
            ns: namespace
        Returns:
        '''
        # load config data from golden_config_db.json
        golden_config_data = None
        try:
            if os.path.isfile(GOLDEN_CFG_FILE):
                with open(GOLDEN_CFG_FILE) as f:
                    golden_data = json.load(f)
                    if ns is None:
                        golden_config_data = golden_data
                    else:
                        if ns == DEFAULT_NAMESPACE:
                            config_namespace = "localhost"
                        else:
                            config_namespace = ns
                        golden_config_data = golden_data[config_namespace]
        except Exception as e:
            log.log_error('Caught exception while trying to load golden config: ' + str(e))
            pass
        # load config data from minigraph to get the default/hardcoded values from minigraph.py
        minigraph_data = None
        try:
            if os.path.isfile(MINIGRAPH_FILE):
                minigraph_data = parse_xml(MINIGRAPH_FILE)
        except Exception as e:
            log.log_error('Caught exception while trying to parse minigraph: ' + str(e))
            pass
        # When both golden config and minigraph exists, override minigraph config with golden config
        # config_src_data is the source of truth for config data
        # this is to avoid duplicating the hardcoded these values in db_migrator
        self.config_src_data = None
        if minigraph_data:
            # Shallow copy for better performance
            self.config_src_data = minigraph_data
            if golden_config_data:
                # Shallow copy for better performance
                self.config_src_data = update_config(minigraph_data, golden_config_data, False)
        elif golden_config_data:
            # Shallow copy for better performance
            self.config_src_data = golden_config_data

    def migrate_pfc_wd_table(self):
        '''
        Migrate all data entries from table PFC_WD_TABLE to PFC_WD
        '''
        data = self.configDB.get_table('PFC_WD_TABLE')
        for key in data:
            self.configDB.set_entry('PFC_WD', key, data[key])
        self.configDB.delete_table('PFC_WD_TABLE')

    def is_ip_prefix_in_key(self, key):
        '''
        Function to check if IP address is present in the key. If it
        is present, then the key would be a tuple or else, it shall be
        be string
        '''
        return (isinstance(key, tuple))

    def migrate_interface_table(self):
        '''
        Migrate all data from existing INTERFACE table with IP Prefix
        to have an additional ONE entry without IP Prefix. For. e.g, for an entry
        "Vlan1000|192.168.0.1/21": {}", this function shall add an entry without
        IP prefix as ""Vlan1000": {}". This is for VRF compatibility.
        '''
        if_db = []
        if_tables = {
                     'INTERFACE',
                     'PORTCHANNEL_INTERFACE',
                     'VLAN_INTERFACE',
                     'LOOPBACK_INTERFACE'
                    }
        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data:
                if not self.is_ip_prefix_in_key(key):
                    if_db.append(key)
                    continue

        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data:
                if not self.is_ip_prefix_in_key(key) or key[0] in if_db:
                    continue
                log.log_info('Migrating interface table for ' + key[0])
                self.configDB.set_entry(table, key[0], data[key])
                if_db.append(key[0])

    def migrate_mgmt_ports_on_s6100(self):
        '''
        During warm-reboot, add back two 10G management ports which got removed from 6100
        to ensure no change in bcm.config from older image
        '''
        if device_info.is_warm_restart_enabled('swss') == False:
            log.log_notice("Skip migration on {}, warm-reboot flag not set".format(self.hwsku))
            return True

        entries = {}
        entries['Ethernet64'] = {'alias': 'tenGigE1/1', 'description': 'tenGigE1/1', 'index': '64', 'lanes': '129', 'mtu': '9100', 'pfc_asym': 'off', 'speed': '10000'}
        entries['Ethernet65'] = {'alias': 'tenGigE1/2', 'description': 'tenGigE1/2', 'index': '65', 'lanes': '131', 'mtu': '9100', 'pfc_asym': 'off', 'speed': '10000'}
        added_ports = 0
        for portName in entries.keys():
            if self.configDB.get_entry('PORT', portName):
                log.log_notice("Skipping migration for port {} - entry exists".format(portName))
                continue

            log.log_notice("Migrating port {} to configDB for warm-reboot on {}".format(portName, self.hwsku))
            self.configDB.set_entry('PORT', portName, entries[portName])

            #Copy port to APPL_DB
            key = 'PORT_TABLE:' + portName
            for field, value in entries[portName].items():
                self.appDB.set(self.appDB.APPL_DB, key, field, value)
            self.appDB.set(self.appDB.APPL_DB, key, 'admin_status', 'down')
            log.log_notice("Copied port {} to appdb".format(key))
            added_ports += 1

        #Update port count in APPL_DB
        portCount = self.appDB.get(self.appDB.APPL_DB, 'PORT_TABLE:PortConfigDone', 'count')
        if portCount != '':
            total_count = int(portCount) + added_ports
            self.appDB.set(self.appDB.APPL_DB, 'PORT_TABLE:PortConfigDone', 'count', str(total_count))
            log.log_notice("Port count updated from {} to : {}".format(portCount, self.appDB.get(self.appDB.APPL_DB, 'PORT_TABLE:PortConfigDone', 'count')))
        return True

    def migrate_intf_table(self):
        '''
        Migrate all data from existing INTF table in APP DB during warmboot with IP Prefix
        to have an additional ONE entry without IP Prefix. For. e.g, for an entry
        "Vlan1000:192.168.0.1/21": {}", this function shall add an entry without
        IP prefix as ""Vlan1000": {}". This also migrates 'lo' to 'Loopback0' interface
        '''
        if self.appDB is None:
            return

        # Get Lo interface corresponding to IP(v4/v6) address from CONFIG_DB.
        configdb_data = self.configDB.get_keys('LOOPBACK_INTERFACE')
        lo_addr_to_int = dict()
        for int_data in configdb_data:
            if type(int_data) == tuple and len(int_data) > 1:
                intf_name = int_data[0]
                intf_addr = int_data[1]
                lo_addr_to_int.update({intf_addr: intf_name})

        lo_data = self.appDB.keys(self.appDB.APPL_DB, "INTF_TABLE:*")
        if lo_data is None:
            return

        if_db = []
        for lo_row in lo_data:
            # Example of lo_row: 'INTF_TABLE:lo:10.1.0.32/32'
            # Delete the old row with name as 'lo'. A new row with name as Loopback will be added
            lo_name_appdb = lo_row.split(":")[1]
            if lo_name_appdb == "lo":
                self.appDB.delete(self.appDB.APPL_DB, lo_row)
                lo_addr = lo_row.split('INTF_TABLE:lo:')[1]
                lo_name_configdb = lo_addr_to_int.get(lo_addr)
                if lo_name_configdb is None or lo_name_configdb == '':
                    # an unlikely case where a Loopback address is present in APPLDB, but
                    # there is no corresponding interface for this address in CONFIGDB:
                    # Default to legacy implementation: hardcode interface name as Loopback0
                    lo_new_row = lo_row.replace(lo_name_appdb, "Loopback0")
                else:
                    lo_new_row = lo_row.replace(lo_name_appdb, lo_name_configdb)
                self.appDB.set(self.appDB.APPL_DB, lo_new_row, 'NULL', 'NULL')

            if '/' not in lo_row:
                if_db.append(lo_row.split(":")[1])
                continue

        data = self.appDB.keys(self.appDB.APPL_DB, "INTF_TABLE:*")
        for key in data:
            if_name = key.split(":")[1]
            if if_name in if_db:
                continue
            log.log_info('Migrating intf table for ' + if_name)
            table = "INTF_TABLE:" + if_name
            self.appDB.set(self.appDB.APPL_DB, table, 'NULL', 'NULL')
            if_db.append(if_name)

    def migrate_copp_table(self):
        '''
        Delete the existing COPP table
        '''
        if self.appDB is None:
            return

        keys = self.appDB.keys(self.appDB.APPL_DB, "COPP_TABLE:*")
        if keys is None:
            return
        for copp_key in keys:
            self.appDB.delete(self.appDB.APPL_DB, copp_key)

    def migrate_feature_table(self):
        '''
        Combine CONTAINER_FEATURE and FEATURE tables into FEATURE table.
        '''
        feature_table = self.configDB.get_table('FEATURE')
        for feature, config in feature_table.items():
            state = config.get('status')
            if state is not None:
                config['state'] = state
                config.pop('status')
                self.configDB.set_entry('FEATURE', feature, config)

        container_feature_table = self.configDB.get_table('CONTAINER_FEATURE')
        for feature, config in container_feature_table.items():
            self.configDB.mod_entry('FEATURE', feature, config)
            self.configDB.set_entry('CONTAINER_FEATURE', feature, None)

    def migrate_config_db_buffer_tables_for_dynamic_calculation(self, speed_list, cable_len_list, default_dynamic_th, abandon_method, append_item_method):
        '''
        Migrate buffer tables to dynamic calculation mode
        parameters
        @speed_list - list of speed supported
        @cable_len_list - list of cable length supported
        @default_dynamic_th - default dynamic th
        @abandon_method - a function which is called to abandon the migration and keep the current configuration
                          if the current one doesn't match the default one
        @append_item_method - a function which is called to append an item to the list of pending commit items
                              any update to buffer configuration will be pended and won't be applied until
                              all configuration is checked and aligns with the default one
        1. Buffer profiles for lossless PGs in BUFFER_PROFILE table will be removed
           if their names have the convention of pg_lossless_<speed>_<cable_length>_profile
           where the speed and cable_length belongs speed_list and cable_len_list respectively
           and the dynamic_th is equal to default_dynamic_th
        2. Insert tables required for dynamic buffer calculation
           - DEFAULT_LOSSLESS_BUFFER_PARAMETER|AZURE: {'default_dynamic_th': default_dynamic_th}
           - LOSSLESS_TRAFFIC_PATTERN|AZURE: {'mtu': '1024', 'small_packet_percentage': '100'}
        3. For lossless dynamic PGs, remove the explicit referencing buffer profiles
           Before: BUFFER_PG|<port>|3-4: {'profile': 'BUFFER_PROFILE|pg_lossless_<speed>_<cable_length>_profile'}
           After:  BUFFER_PG|<port>|3-4: {'profile': 'NULL'}
        '''
        # Migrate BUFFER_PROFILEs, removing dynamically generated profiles
        dynamic_profile = self.configDB.get_table('BUFFER_PROFILE')
        profile_pattern = 'pg_lossless_([1-9][0-9]*000)_([1-9][0-9]*m)_profile'
        for name, info in dynamic_profile.items():
            m = re.search(profile_pattern, name)
            if not m:
                continue
            speed = m.group(1)
            cable_length = m.group(2)
            if speed in speed_list and cable_length in cable_len_list:
                append_item_method(('BUFFER_PROFILE', name, None))
                log.log_info("Lossless profile {} has been removed".format(name))

        # Migrate BUFFER_PGs, removing the explicit designated profiles
        buffer_pgs = self.configDB.get_table('BUFFER_PG')
        ports = self.configDB.get_table('PORT')
        all_cable_lengths = self.configDB.get_table('CABLE_LENGTH')
        if not buffer_pgs or not ports or not all_cable_lengths:
            log.log_notice("At lease one of tables BUFFER_PG, PORT and CABLE_LENGTH hasn't been defined, skip following migration")
            abandon_method()
            return True

        cable_lengths = all_cable_lengths[list(all_cable_lengths.keys())[0]]
        for name, profile in buffer_pgs.items():
            # do the db migration
            try:
                port, pg = name
                profile_name = profile['profile'][1:-1].split('|')[1]
                if pg == '0':
                    if profile_name != 'ingress_lossy_profile':
                        log.log_notice("BUFFER_PG table entry {} has non default profile {} configured".format(name, profile_name))
                        abandon_method()
                        return True
                    else:
                        continue
                elif pg != '3-4':
                    log.log_notice("BUFFER_PG table entry {} isn't default PG(0 or 3-4)".format(name))
                    abandon_method()
                    return True
                m = re.search(profile_pattern, profile_name)
                if not m:
                    log.log_notice("BUFFER_PG table entry {} has non-default profile name {}".format(name, profile_name))
                    abandon_method()
                    return True
                speed = m.group(1)
                cable_length = m.group(2)

                if speed == ports[port]['speed'] and cable_length == cable_lengths[port]:
                    append_item_method(('BUFFER_PG', name, {'profile': 'NULL'}))
                else:
                    log.log_notice("Lossless PG profile {} for port {} doesn't match its speed {} or cable length {}, keep using traditional buffer calculation mode".format(
                        profile_name, port, speed, cable_length))
                    abandon_method()
                    return True
            except Exception:
                log.log_notice("Exception occured during parsing the profiles")
                abandon_method()
                return True

        # Insert other tables required for dynamic buffer calculation
        metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        metadata['buffer_model'] = 'dynamic'
        append_item_method(('DEVICE_METADATA', 'localhost', metadata))
        append_item_method(('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', {'default_dynamic_th': default_dynamic_th}))
        append_item_method(('LOSSLESS_TRAFFIC_PATTERN', 'AZURE', {'mtu': '1024', 'small_packet_percentage': '100'}))

        return True

    def prepare_dynamic_buffer_for_warm_reboot(self, buffer_pools=None, buffer_profiles=None, buffer_pgs=None):
        '''
        This is the very first warm reboot of buffermgrd (dynamic) if the system reboot from old image by warm-reboot
        In this case steps need to be taken to get buffermgrd prepared (for warm reboot)
        During warm reboot, buffer tables should be installed in the first place.
        However, it isn't able to achieve that when system is warm-rebooted from an old image
        without dynamic buffer supported, because the buffer info wasn't in the APPL_DB in the old image.
        The solution is to copy that info from CONFIG_DB into APPL_DB in db_migrator.
        During warm-reboot, db_migrator adjusts buffer info in CONFIG_DB by removing some fields
        according to requirement from dynamic buffer calculation.
        The buffer info before that adjustment needs to be copied to APPL_DB.
        1. set WARM_RESTART_TABLE|buffermgrd as {restore_count: 0}
        2. Copy the following tables from CONFIG_DB into APPL_DB in case of warm reboot
           The separator in fields that reference objects in other table needs to be updated from '|' to ':'
           - BUFFER_POOL
           - BUFFER_PROFILE, separator updated for field 'pool'
           - BUFFER_PG, separator updated for field 'profile'
           - BUFFER_QUEUE, separator updated for field 'profile
           - BUFFER_PORT_INGRESS_PROFILE_LIST, separator updated for field 'profile_list'
           - BUFFER_PORT_EGRESS_PROFILE_LIST, separator updated for field 'profile_list'
        '''
        warmreboot_state = self.stateDB.get(self.stateDB.STATE_DB, 'WARM_RESTART_ENABLE_TABLE|system', 'enable')
        mmu_size = self.stateDB.get(self.stateDB.STATE_DB, 'BUFFER_MAX_PARAM_TABLE|global', 'mmu_size')
        if warmreboot_state == 'true' and not mmu_size:
            log.log_notice("This is the very first run of buffermgrd (dynamic), prepare info required from warm reboot")
        else:
            return True

        buffer_table_list = [
            ('BUFFER_POOL', buffer_pools, None),
            ('BUFFER_PROFILE', buffer_profiles, 'pool'),
            ('BUFFER_PG', buffer_pgs, 'profile'),
            ('BUFFER_QUEUE', None, 'profile'),
            ('BUFFER_PORT_INGRESS_PROFILE_LIST', None, 'profile_list'),
            ('BUFFER_PORT_EGRESS_PROFILE_LIST', None, 'profile_list')
        ]

        for pair in buffer_table_list:
            keys_copied = []
            keys_ignored = []
            table_name, entries, reference_field_name = pair
            app_table_name = table_name + "_TABLE"
            if not entries:
                entries = self.configDB.get_table(table_name)
            for key, items in entries.items():
                # copy items to appl db
                if reference_field_name:
                    confdb_ref = items.get(reference_field_name)
                    if not confdb_ref or confdb_ref == "NULL":
                        keys_ignored.append(key)
                        continue
                    items_referenced = confdb_ref.split(',')
                    appdb_ref = ""
                    first_item = True
                    for item in items_referenced:
                        if first_item:
                            first_item = False
                        else:
                            appdb_ref += ','
                        subitems = item.split('|')
                        first_key = True
                        for subitem in subitems:
                            if first_key:
                                appdb_ref += subitem + '_TABLE'
                                first_key = False
                            else:
                                appdb_ref += ':' + subitem

                    items[reference_field_name] = appdb_ref
                keys_copied.append(key)
                if type(key) is tuple:
                    appl_db_key = app_table_name + ':' + ':'.join(key)
                else:
                    appl_db_key = app_table_name + ':' + key
                for field, data in items.items():
                    self.appDB.set(self.appDB.APPL_DB, appl_db_key, field, data)

            if keys_copied:
                log.log_info("The following items in table {} in CONFIG_DB have been copied to APPL_DB: {}".format(table_name, keys_copied))
            if keys_ignored:
                log.log_info("The following items in table {} in CONFIG_DB have been ignored: {}".format(table_name, keys_copied))

        return True

    def migrate_config_db_port_table_for_auto_neg(self):
        table_name = 'PORT'
        port_table = self.configDB.get_table(table_name)
        for key, value in port_table.items():
            if 'autoneg' in value:
                if value['autoneg'] == '1':
                    self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, key), 'autoneg', 'on')
                    if 'speed' in value and 'adv_speeds' not in value:
                        self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, key), 'adv_speeds', value['speed'])
                elif value['autoneg'] == '0':
                    self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, key), 'autoneg', 'off')
    

    def migrate_config_db_switchport_mode(self):
        port_table = self.configDB.get_table('PORT')
        portchannel_table = self.configDB.get_table('PORTCHANNEL')
        vlan_member_table = self.configDB.get_table('VLAN_MEMBER')

        vlan_member_keys= []
        for _,key in vlan_member_table:
            vlan_member_keys.append(key) 

        for p_key, p_value in port_table.items():
            if 'mode' in p_value:
                self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format("PORT", p_key), 'mode', p_value['mode'])
            else:
                if p_key in vlan_member_keys:
                    p_value["mode"] = "trunk"
                    self.configDB.set_entry("PORT", p_key, p_value)
                else:
                    p_value["mode"] = "routed"
                    self.configDB.set_entry("PORT", p_key, p_value)

        for pc_key, pc_value in portchannel_table.items():
            if 'mode' in pc_value:
                self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format("PORTCHANNEL", pc_key), 'mode', pc_value['mode'])
            else:
                if pc_key in vlan_member_keys:
                    pc_value["mode"] = "trunk"
                    self.configDB.set_entry("PORTCHANNEL", pc_key, pc_value)
                else:
                    pc_value["mode"] = "routed"
                    self.configDB.set_entry("PORTCHANNEL", pc_key, pc_value)


    def migrate_qos_db_fieldval_reference_remove(self, table_list, db, db_num, db_delimeter):
        for pair in table_list:
            table_name, fields_list = pair
            qos_table = db.get_table(table_name)
            for key, value in qos_table.items():
                if type(key) is tuple:
                    db_key = table_name + db_delimeter + db_delimeter.join(key)
                else:
                    db_key = table_name + db_delimeter + key

                for field in fields_list:
                    if field in value:
                        fieldVal = value.get(field)
                        if not fieldVal or fieldVal == "NULL":
                            continue
                        newFiledVal = ""
                        # Check for ABNF format presence and convert ABNF to string
                        if "[" in fieldVal and db_delimeter in fieldVal and "]" in fieldVal:
                            log.log_info("Found ABNF format field value in table {} key {} field {} val {}".format(table_name, db_key, field, fieldVal))
                            value_list = fieldVal.split(",")
                            for item in value_list:
                                if "[" != item[0] or db_delimeter not in item or "]" != item[-1]:
                                    continue
                                newFiledVal = newFiledVal + item[1:-1].split(db_delimeter)[1] + ','
                            newFiledVal = newFiledVal[:-1]
                            db.set(db_num, db_key, field, newFiledVal)
                            log.log_info("Modified ABNF format field value to string in table {} key {} field {} val {}".format(table_name, db_key, field, newFiledVal))
        return True

    def migrate_qos_fieldval_reference_format(self):
        '''
        This is to change for first time to remove field refernces of ABNF format
        in APPL DB for warm boot.
        i.e "[Tabale_name:name]" to string in APPL_DB. Reasons for doing this
         - To consistent with all other SoNIC CONFIG_DB/APPL_DB tables and fields
         - References in DB is not required, this will be taken care by YANG model leafref.
        '''
        qos_app_table_list = [
            ('BUFFER_PG_TABLE', ['profile']),
            ('BUFFER_QUEUE_TABLE', ['profile']),
            ('BUFFER_PROFILE_TABLE', ['pool']),
            ('BUFFER_PORT_INGRESS_PROFILE_LIST_TABLE', ['profile_list']),
            ('BUFFER_PORT_EGRESS_PROFILE_LIST_TABLE', ['profile_list'])
        ]

        log.log_info("Remove APPL_DB QOS tables field reference ABNF format")
        self.migrate_qos_db_fieldval_reference_remove(qos_app_table_list, self.appDB, self.appDB.APPL_DB, ':')

        qos_table_list = [
            ('QUEUE', ['scheduler', 'wred_profile']),
            ('PORT_QOS_MAP', ['dscp_to_tc_map', 'dot1p_to_tc_map',
                              'pfc_to_queue_map', 'tc_to_pg_map',
                              'tc_to_queue_map', 'pfc_to_pg_map']),
            ('BUFFER_PG', ['profile']),
            ('BUFFER_QUEUE', ['profile']),
            ('BUFFER_PROFILE', ['pool']),
            ('BUFFER_PORT_INGRESS_PROFILE_LIST', ['profile_list']),
            ('BUFFER_PORT_EGRESS_PROFILE_LIST', ['profile_list'])
        ]
        log.log_info("Remove CONFIG_DB QOS tables field reference ABNF format")
        self.migrate_qos_db_fieldval_reference_remove(qos_table_list, self.configDB, self.configDB.CONFIG_DB, '|')
        return True

    def migrate_vxlan_config(self):
        log.log_notice('Migrate VXLAN table config')
        # Collect VXLAN data from config DB
        vxlan_data = self.configDB.keys(self.configDB.CONFIG_DB, "VXLAN_TUNNEL*")
        if not vxlan_data:
            # do nothing if vxlan entries are not present in configdb
            return
        for vxlan_table in vxlan_data:
            vxlan_map_mapping = self.configDB.get_all(self.configDB.CONFIG_DB, vxlan_table)
            tunnel_keys = vxlan_table.split(self.configDB.KEY_SEPARATOR)
            tunnel_keys[0] = tunnel_keys[0] + "_TABLE"
            vxlan_table = self.appDB.get_db_separator(self.appDB.APPL_DB).join(tunnel_keys)
            for field, value in vxlan_map_mapping.items():
                # add entries from configdb to appdb only when they are missing
                if not self.appDB.hexists(self.appDB.APPL_DB, vxlan_table, field):
                    log.log_notice('Copying vxlan entries from configdb to appdb: updated {} with {}:{}'.format(
                        vxlan_table, field, value))
                    self.appDB.set(self.appDB.APPL_DB, vxlan_table, field, value)

    def migrate_restapi(self):
        # RESTAPI - add missing key
        if not self.config_src_data or 'RESTAPI' not in self.config_src_data:
            return
        restapi_data = self.config_src_data['RESTAPI']
        log.log_notice('Migrate RESTAPI configuration')
        config = self.configDB.get_entry('RESTAPI', 'config')
        if not config:
            self.configDB.set_entry("RESTAPI", "config", restapi_data.get("config"))
        certs = self.configDB.get_entry('RESTAPI', 'certs')
        if not certs:
            self.configDB.set_entry("RESTAPI", "certs", restapi_data.get("certs"))

    def migrate_telemetry(self):
        # TELEMETRY - add missing key
        if not self.config_src_data or 'TELEMETRY' not in self.config_src_data:
            return
        telemetry_data = self.config_src_data['TELEMETRY']
        log.log_notice('Migrate TELEMETRY configuration')
        gnmi = self.configDB.get_entry('TELEMETRY', 'gnmi')
        if not gnmi:
            self.configDB.set_entry("TELEMETRY", "gnmi", telemetry_data.get("gnmi"))
        certs = self.configDB.get_entry('TELEMETRY', 'certs')
        if not certs:
            self.configDB.set_entry("TELEMETRY", "certs", telemetry_data.get("certs"))

    def migrate_gnmi(self):
        # If there's GNMI table in CONFIG_DB, no need to migrate
        gnmi = self.configDB.get_entry('GNMI', 'gnmi')
        certs = self.configDB.get_entry('GNMI', 'certs')
        if gnmi and certs:
            return
        if self.config_src_data:
            if 'GNMI' in self.config_src_data:
                # If there's GNMI in minigraph or golden config, copy configuration from config_src_data
                gnmi_data = self.config_src_data['GNMI']
                log.log_notice('Migrate GNMI configuration')
                if 'gnmi' in gnmi_data:
                    self.configDB.set_entry("GNMI", "gnmi", gnmi_data.get('gnmi'))
                if 'certs' in gnmi_data:
                    self.configDB.set_entry("GNMI", "certs", gnmi_data.get('certs'))
        else:
            # If there's no minigraph or golden config, copy configuration from CONFIG_DB TELEMETRY table
            gnmi = self.configDB.get_entry('TELEMETRY', 'gnmi')
            if gnmi:
                self.configDB.set_entry("GNMI", "gnmi", gnmi)
            certs = self.configDB.get_entry('TELEMETRY', 'certs')
            if certs:
                self.configDB.set_entry("GNMI", "certs", certs)

    def migrate_console_switch(self):
        # CONSOLE_SWITCH - add missing key
        if not self.config_src_data or 'CONSOLE_SWITCH' not in self.config_src_data:
            return
        console_switch_data = self.config_src_data['CONSOLE_SWITCH']
        log.log_notice('Migrate CONSOLE_SWITCH configuration')
        console_mgmt = self.configDB.get_entry('CONSOLE_SWITCH', 'console_mgmt')
        if not console_mgmt:
            self.configDB.set_entry("CONSOLE_SWITCH", "console_mgmt",
                console_switch_data.get("console_mgmt"))

    def migrate_device_metadata(self):
        # DEVICE_METADATA - synchronous_mode entry
        if not self.config_src_data or 'DEVICE_METADATA' not in self.config_src_data:
            return
        log.log_notice('Migrate DEVICE_METADATA missing configuration')
        metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        device_metadata_data = self.config_src_data["DEVICE_METADATA"]["localhost"]
        if 'synchronous_mode' not in metadata:
            metadata['synchronous_mode'] = device_metadata_data.get("synchronous_mode")
            self.configDB.set_entry('DEVICE_METADATA', 'localhost', metadata)

    def migrate_port_qos_map_global(self):
        """
        Generate dscp_to_tc_map for switch.
        """
        asics_require_global_dscp_to_tc_map = ["broadcom"]
        if self.asic_type not in asics_require_global_dscp_to_tc_map:
            return
        dscp_to_tc_map_table_names = self.configDB.get_keys('DSCP_TO_TC_MAP')
        if len(dscp_to_tc_map_table_names) == 0:
            return

        qos_maps = self.configDB.get_table('PORT_QOS_MAP')
        if 'global' not in qos_maps.keys():
            # We are unlikely to have more than 1 DSCP_TO_TC_MAP in previous versions
            self.configDB.set_entry('PORT_QOS_MAP', 'global', {"dscp_to_tc_map": dscp_to_tc_map_table_names[0]})
            log.log_info("Created entry for global DSCP_TO_TC_MAP {}".format(dscp_to_tc_map_table_names[0]))

    def migrate_feature_timer(self):
        '''
        Migrate feature 'has_timer' field to 'delayed'
        '''
        feature_table = self.configDB.get_table('FEATURE')
        for feature, config in feature_table.items():
            state = config.get('has_timer')
            if state is not None:
                config['delayed'] = state
                config.pop('has_timer')
                self.configDB.set_entry('FEATURE', feature, config)


    def migrate_dns_nameserver(self):
        """
        Handle DNS_NAMESERVER table migration. Migrations handled:
        If there's no DNS_NAMESERVER in config_DB, load DNS_NAMESERVER from minigraph
        """
        if not self.config_src_data or 'DNS_NAMESERVER' not in self.config_src_data:
            return
        dns_table = self.configDB.get_table('DNS_NAMESERVER')
        if not dns_table:
            for addr, config in self.config_src_data['DNS_NAMESERVER'].items():
                self.configDB.set_entry('DNS_NAMESERVER', addr, config)

    def migrate_routing_config_mode(self):
        # DEVICE_METADATA - synchronous_mode entry
        if not self.config_src_data or 'DEVICE_METADATA' not in self.config_src_data:
            return
        device_metadata_old = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        device_metadata_new = self.config_src_data['DEVICE_METADATA']['localhost']
        # overwrite the routing-config-mode as per minigraph parser
        # Criteria for update:
        # if config mode is missing in base OS or if base and target modes are not same
        #  Eg. in 201811 mode is "unified", and in newer branches mode is "separated"
        if ('docker_routing_config_mode' not in device_metadata_old and 'docker_routing_config_mode' in device_metadata_new) or \
        (device_metadata_old.get('docker_routing_config_mode') != device_metadata_new.get('docker_routing_config_mode')):
            device_metadata_old['docker_routing_config_mode'] = device_metadata_new.get('docker_routing_config_mode')
            self.configDB.set_entry('DEVICE_METADATA', 'localhost', device_metadata_old)

    def update_edgezone_aggregator_config(self):
        """
        Update cable length configuration in ConfigDB for T0 neighbor interfaces
        connected to EdgeZone Aggregator devices, while resetting the port values to trigger a buffer change
        1. Find a list of all interfaces connected to an EdgeZone Aggregator device.
        2. If all the cable lengths are the same, do nothing and return.
        3. If there are different cable lengths, update CABLE_LENGTH values for these interfaces with a constant value of 40m.
        """
        device_neighbor_metadata = self.configDB.get_table("DEVICE_NEIGHBOR_METADATA")
        device_neighbors = self.configDB.get_table("DEVICE_NEIGHBOR")
        cable_length = self.configDB.get_table("CABLE_LENGTH")
        port_table = self.configDB.get_table("PORT")
        edgezone_aggregator_devs = []
        edgezone_aggregator_intfs = []
        EDGEZONE_AGG_CABLE_LENGTH = "40m"
        for k, v in device_neighbor_metadata.items():
            if v.get("type") == "EdgeZoneAggregator":
                    edgezone_aggregator_devs.append(k)

        if len(edgezone_aggregator_devs) == 0:
            return

        for intf, intf_info in device_neighbors.items():
            if intf_info.get("name") in edgezone_aggregator_devs:
                edgezone_aggregator_intfs.append(intf)

        cable_length_table = self.configDB.get_entry("CABLE_LENGTH", "AZURE")
        first_cable_intf = next(iter(cable_length_table))
        first_cable_length = cable_length_table[first_cable_intf]
        index = 0

        for intf, length in cable_length_table.items():
            index += 1
            if first_cable_length != length:
                break
            elif index == len(cable_length_table):
                # All cable lengths are the same, nothing to modify
                return

        for intf, length in cable_length_table.items():
            if intf in edgezone_aggregator_intfs:
                # Set new cable length values
                self.configDB.set(self.configDB.CONFIG_DB, "CABLE_LENGTH|AZURE", intf, EDGEZONE_AGG_CABLE_LENGTH)

    def migrate_config_db_flex_counter_delay_status(self):
        """
        Migrate "FLEX_COUNTER_TABLE|*": { "value": { "FLEX_COUNTER_DELAY_STATUS": "false" } }
        Set FLEX_COUNTER_DELAY_STATUS true in case of fast-reboot
        """

        flex_counter_objects = self.configDB.get_keys('FLEX_COUNTER_TABLE')
        for obj in flex_counter_objects:
            flex_counter = self.configDB.get_entry('FLEX_COUNTER_TABLE', obj)
            delay_status = flex_counter.get('FLEX_COUNTER_DELAY_STATUS')
            if delay_status is None or delay_status == 'false':
                flex_counter['FLEX_COUNTER_DELAY_STATUS'] = 'true'
                self.configDB.mod_entry('FLEX_COUNTER_TABLE', obj, flex_counter)

    def migrate_sflow_table(self):
        """
        Migrate "SFLOW_TABLE" and "SFLOW_SESSION_TABLE" to update default sample_direction
        """

        sflow_tbl = self.configDB.get_table('SFLOW')
        for k, v in sflow_tbl.items():
            if 'sample_direction' not in v:
                v['sample_direction'] = 'rx'
                self.configDB.set_entry('SFLOW', k, v)

        sflow_sess_tbl = self.configDB.get_table('SFLOW_SESSION')
        for k, v in sflow_sess_tbl.items():
            if 'sample_direction' not in v:
                v['sample_direction'] = 'rx'
                self.configDB.set_entry('SFLOW_SESSION', k, v)

        sflow_table = self.appDB.get_table("SFLOW_TABLE")
        for key, value in sflow_table.items():
            if 'sample_direction' not in value:
                sflow_key = "SFLOW_TABLE:{}".format(key)
                self.appDB.set(self.appDB.APPL_DB, sflow_key, 'sample_direction','rx')

        sflow_sess_table = self.appDB.get_table("SFLOW_SESSION_TABLE")
        for key, value in sflow_sess_table.items():
            if 'sample_direction' not in value:
                sflow_key = "SFLOW_SESSION_TABLE:{}".format(key)
                self.appDB.set(self.appDB.APPL_DB, sflow_key, 'sample_direction','rx')

    def version_unknown(self):
        """
        version_unknown tracks all SONiC versions that doesn't have a version
        string defined in config_DB.
        Nothing can be assumped when migrating from this version to the next
        version.
        Any migration operation needs to test if the DB is in expected format
        before migrating date to the next version.
        """

        log.log_info('Handling version_unknown')

        # NOTE: Uncomment next 3 lines of code when the migration code is in
        #       place. Note that returning specific string is intentional,
        #       here we only intended to migrade to DB version 1.0.1.
        #       If new DB version is added in the future, the incremental
        #       upgrade will take care of the subsequent migrations.
        self.migrate_pfc_wd_table()
        self.migrate_interface_table()
        self.migrate_intf_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_1(self):
        """
        Version 1_0_1.
        """
        log.log_info('Handling version_1_0_1')

        self.migrate_interface_table()
        self.migrate_intf_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_2(self):
        """
        Version 1_0_2.
        """
        log.log_info('Handling version_1_0_2')
        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_2', 'version_1_0_3') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_3')
        else:
            self.set_version('version_1_0_3')
        return 'version_1_0_3'

    def version_1_0_3(self):
        """
        Version 1_0_3.
        """
        log.log_info('Handling version_1_0_3')

        self.migrate_feature_table()

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_3', 'version_1_0_4') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_3', 'version_1_0_4') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_4')
        else:
            self.set_version('version_1_0_4')

        return 'version_1_0_4'

    def version_1_0_4(self):
        """
        Version 1_0_4.
        """
        log.log_info('Handling version_1_0_4')

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_4', 'version_1_0_5') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_4', 'version_1_0_5') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_5')
        else:
            self.set_version('version_1_0_5')

        return 'version_1_0_5'

    def version_1_0_5(self):
        """
        Version 1_0_5.
        """
        log.log_info('Handling version_1_0_5')

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_5', 'version_1_0_6') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_5', 'version_1_0_6') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_6')
        else:
            self.set_version('version_1_0_6')

        return 'version_1_0_6'

    def version_1_0_6(self):
        """
        Version 1_0_6.
        """
        log.log_info('Handling version_1_0_6')
        if self.asic_type == "mellanox":
            speed_list = self.mellanox_buffer_migrator.default_speed_list
            cable_len_list = self.mellanox_buffer_migrator.default_cable_len_list
            buffer_pools = self.configDB.get_table('BUFFER_POOL')
            buffer_profiles = self.configDB.get_table('BUFFER_PROFILE')
            buffer_pgs = self.configDB.get_table('BUFFER_PG')
            abandon_method = self.mellanox_buffer_migrator.mlnx_abandon_pending_buffer_configuration
            append_method = self.mellanox_buffer_migrator.mlnx_append_item_on_pending_configuration_list

            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_6', 'version_2_0_0') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_6', 'version_2_0_0') \
               and (not self.mellanox_buffer_migrator.mlnx_is_buffer_model_dynamic() or \
                    self.migrate_config_db_buffer_tables_for_dynamic_calculation(speed_list, cable_len_list, '0', abandon_method, append_method)) \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration() \
               and self.prepare_dynamic_buffer_for_warm_reboot(buffer_pools, buffer_profiles, buffer_pgs):
                self.set_version('version_2_0_0')
        else:
            self.prepare_dynamic_buffer_for_warm_reboot()

            metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
            metadata['buffer_model'] = 'traditional'
            self.configDB.set_entry('DEVICE_METADATA', 'localhost', metadata)
            log.log_notice('Setting buffer_model to traditional')

            self.set_version('version_2_0_0')

        return 'version_2_0_0'

    def version_2_0_0(self):
        """
        Version 2_0_0
        """
        log.log_info('Handling version_2_0_0')
        self.migrate_port_qos_map_global()
        self.set_version('version_2_0_1')
        return 'version_2_0_1'

    def version_2_0_1(self):
        """
        Handle and migrate missing config that results from cross branch upgrade to
        202012 as target.
        """
        log.log_info('Handling version_2_0_1')
        self.migrate_vxlan_config()
        self.migrate_restapi()
        self.migrate_telemetry()
        self.migrate_console_switch()
        self.migrate_device_metadata()

        self.set_version('version_2_0_2')
        return 'version_2_0_2'

    def version_2_0_2(self):
        """
        Version 2_0_2
        This is the latest version for 202012 branch
        """
        log.log_info('Handling version_2_0_2')
        self.set_version('version_3_0_0')
        return 'version_3_0_0'

    def version_3_0_0(self):
        """
        Version 3_0_0.
        """
        log.log_info('Handling version_3_0_0')
        self.migrate_config_db_port_table_for_auto_neg()
        self.migrate_config_db_switchport_mode()
        self.set_version('version_3_0_1')
        return 'version_3_0_1'

    def version_3_0_1(self):
        """
        Version 3_0_1.
        """
        log.log_info('Handling version_3_0_1')
        warmreboot_state = self.stateDB.get(self.stateDB.STATE_DB, 'WARM_RESTART_ENABLE_TABLE|system', 'enable')

        if warmreboot_state != 'true':
            portchannel_table = self.configDB.get_table('PORTCHANNEL')
            for name, data in portchannel_table.items():
                data['lacp_key'] = 'auto'
                self.configDB.set_entry('PORTCHANNEL', name, data)
        self.migrate_config_db_switchport_mode()
        self.set_version('version_3_0_2')

        return 'version_3_0_2'

    def version_3_0_2(self):
        """
        Version 3_0_2.
        """
        log.log_info('Handling version_3_0_2')
        self.migrate_qos_fieldval_reference_format()
        self.set_version('version_3_0_3')
        return 'version_3_0_3'


    def version_3_0_3(self):
        """
        Version 3_0_3
        """
        log.log_info('Handling version_3_0_3')
        if self.asic_type == "mellanox":
            self.mellanox_buffer_migrator.mlnx_reclaiming_unused_buffer()
        self.set_version('version_3_0_4')
        return 'version_3_0_4'

    def version_3_0_4(self):
        """
        Version 3_0_4
        """
        log.log_info('Handling version_3_0_4')
        # Migrate "pfc_enable" to "pfc_enable" and "pfcwd_sw_enable"
        # 1. pfc_enable means enable pfc on certain queues
        # 2. pfcwd_sw_enable means enable PFC software watchdog on certain queues
        # By default, PFC software watchdog is enabled on all pfc enabled queues.
        qos_maps = self.configDB.get_table('PORT_QOS_MAP')
        for k, v in qos_maps.items():
            if 'pfc_enable' in v:
                v['pfcwd_sw_enable'] = v['pfc_enable']
                self.configDB.set_entry('PORT_QOS_MAP', k, v)
        self.set_version('version_3_0_5')
        return 'version_3_0_5'

    def version_3_0_5(self):
        """
        Version 3_0_5
        """
        log.log_info('Handling version_3_0_5')
        # Removing LOGLEVEL DB and moving it's content to CONFIG DB
        # Removing Jinja2_cache
        warmreboot_state = self.stateDB.get(self.stateDB.STATE_DB, 'WARM_RESTART_ENABLE_TABLE|system', 'enable')
        if warmreboot_state == 'true':
            table_name = "LOGGER"
            loglevel_field = "LOGLEVEL"
            logoutput_field = "LOGOUTPUT"
            keys = self.loglevelDB.keys(self.loglevelDB.LOGLEVEL_DB, "*")
            if keys is not None:
                for key in keys:
                    try:
                        if key != "JINJA2_CACHE":
                            fvs = self.loglevelDB.get_all(self.loglevelDB.LOGLEVEL_DB, key)
                            component = key.split(":")[1]
                            loglevel = fvs[loglevel_field]
                            logoutput = fvs[logoutput_field]
                            self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, component), loglevel_field, loglevel)
                            self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, component), logoutput_field, logoutput)
                    except Exception as err:
                        log.log_warning('Error occured during LOGLEVEL_DB migration for {}. Ignoring key {}'.format(err, key))
                    finally:
                        self.loglevelDB.delete(self.loglevelDB.LOGLEVEL_DB, key)
        self.set_version('version_3_0_6')
        return 'version_3_0_6'

    def version_3_0_6(self):
        """
        Version 3_0_6
        """

        log.log_info('Handling version_3_0_6')
        self.set_version('version_3_0_7')
        return 'version_3_0_7'

    def version_3_0_7(self):
        """
        Version 3_0_7
        This is the latest version for 202205 branch
        """

        log.log_info('Handling version_3_0_7')
        self.set_version('version_4_0_0')
        return 'version_4_0_0'

    def version_4_0_0(self):
        """
        Version 4_0_0.
        """
        log.log_info('Handling version_4_0_0')
        # Update state-db fast-reboot entry to enable if set to enable fast-reboot finalizer when using upgrade with fast-reboot
        # since upgrading from previous version FAST_REBOOT table will be deleted when the timer will expire.
        # reading FAST_REBOOT table can't be done with stateDB.get as it uses hget behind the scenes and the table structure is
        # not using hash and won't work.
        # FAST_REBOOT table exists only if fast-reboot was triggered.
        keys = self.stateDB.keys(self.stateDB.STATE_DB, "FAST_RESTART_ENABLE_TABLE|system")
        if not keys:
            keys = self.stateDB.keys(self.stateDB.STATE_DB, "FAST_REBOOT|system")
            if keys:
                enable_state = 'true'
            else:
                enable_state = 'false'
            self.stateDB.set(self.stateDB.STATE_DB, 'FAST_RESTART_ENABLE_TABLE|system', 'enable', enable_state)
        self.set_version('version_4_0_1')
        return 'version_4_0_1'

    def version_4_0_1(self):
        """
        Version 4_0_1.
        """
        log.log_info('Handling version_4_0_1')

        self.migrate_feature_timer()
        self.set_version('version_4_0_2')
        return 'version_4_0_2'

    def version_4_0_2(self):
        """
        Version 4_0_2.
        """
        log.log_info('Handling version_4_0_2')
        if self.stateDB.keys(self.stateDB.STATE_DB, "FAST_REBOOT|system"):
            self.migrate_config_db_flex_counter_delay_status()

        self.set_version('version_4_0_3')
        return 'version_4_0_3'

    def version_4_0_3(self):
        """
        Version 4_0_3.
        """
        log.log_info('Handling version_4_0_3')
        
        self.set_version('version_202305_01')
        return 'version_202305_01'

    def version_202305_01(self):
        """
        Version 202305_01.
        This is current last erversion for 202305 branch
        """
        log.log_info('Handling version_202305_01')
        self.set_version('version_202311_01')
        return 'version_202311_01'

    def version_202311_01(self):
        """
        Version 202311_01.
        """
        log.log_info('Handling version_202311_01')

        # Updating DNS nameserver
        self.migrate_dns_nameserver()

        self.migrate_sflow_table()
        self.set_version('version_202311_02')
        return 'version_202311_02'

    def version_202311_02(self):
        """
        Version 202311_02.
        """
        log.log_info('Handling version_202311_02')
        # Update GNMI table
        self.migrate_gnmi()

        self.set_version('version_202311_03')
        return 'version_202311_03'

    def version_202311_03(self):
        """
        Version 202311_03.
        This is current last erversion for 202311 branch
        """
        log.log_info('Handling version_202311_03')
        self.set_version('version_202405_01')
        return 'version_202405_01'

    def version_202405_01(self):
        """
        Version 202405_01, this version should be the final version for
        master branch until 202405 branch is created.
        """
        log.log_info('Handling version_202405_01')
        return None

    def get_version(self):
        version = self.configDB.get_entry(self.TABLE_NAME, self.TABLE_KEY)
        if version and version[self.TABLE_FIELD]:
            return version[self.TABLE_FIELD]

        return 'version_unknown'

    def set_version(self, version=None):
        if not version:
            version = self.CURRENT_VERSION
        log.log_info('Setting version to ' + version)
        entry = { self.TABLE_FIELD : version }
        self.configDB.set_entry(self.TABLE_NAME, self.TABLE_KEY, entry)

    def common_migration_ops(self):
        try:
            with open(INIT_CFG_FILE) as f:
                init_db = json.load(f)
        except Exception as e:
            raise Exception(str(e))

        for init_cfg_table, table_val in init_db.items():
            log.log_info("Migrating table {} from INIT_CFG to config_db".format(init_cfg_table))
            for key in table_val:
                curr_cfg = self.configDB.get_entry(init_cfg_table, key)
                init_cfg = table_val[key]

                # Override init config with current config.
                # This will leave new fields from init_config
                # in new_config, but not override existing configuration.
                new_cfg = {**init_cfg, **curr_cfg}
                self.configDB.set_entry(init_cfg_table, key, new_cfg)

        # Avoiding copp table migration is platform specific at the moment as I understood this might cause issues for some
        # vendors, probably Broadcom. This change can be checked with any specific vendor and if this works fine the platform
        # condition can be modified and extend. If no vendor has an issue with not clearing copp tables the condition can be
        # removed together with calling to migrate_copp_table function.
        if self.asic_type != "mellanox":
            self.migrate_copp_table()
        if self.asic_type == "broadcom" and 'Force10-S6100' in str(self.hwsku):
            self.migrate_mgmt_ports_on_s6100()
        else:
            log.log_notice("Asic Type: {}, Hwsku: {}".format(self.asic_type, self.hwsku))

        # Updating edgezone aggregator cable length config for T0 devices
        self.update_edgezone_aggregator_config()
        # update FRR config mode based on minigraph parser on target image
        self.migrate_routing_config_mode()

    def migrate(self):
        version = self.get_version()
        log.log_info('Upgrading from version ' + version)
        while version:
            next_version = getattr(self, version)()
            if next_version == version:
                raise Exception('Version migrate from %s stuck in same version' % version)
            version = next_version
        # Perform common migration ops
        self.common_migration_ops()

def main():
    try:
        parser = argparse.ArgumentParser()

        parser.add_argument('-o',
                            dest='operation',
                            metavar='operation (migrate, set_version, get_version)',
                            type = str,
                            required = False,
                            choices=['migrate', 'set_version', 'get_version'],
                            help = 'operation to perform [default: get_version]',
                            default='get_version')
        parser.add_argument('-s',
                        dest='socket',
                        metavar='unix socket',
                        type = str,
                        required = False,
                        help = 'the unix socket that the desired database listens on',
                        default = None )
        parser.add_argument('-n',
                        dest='namespace',
                        metavar='asic namespace',
                        type = str,
                        required = False,
                        help = 'The asic namespace whose DB instance we need to connect',
                        default = None )
        args = parser.parse_args()
        operation = args.operation
        socket_path = args.socket
        namespace = args.namespace

        load_db_config()

        if socket_path:
            dbmgtr = DBMigrator(namespace, socket=socket_path)
        else:
            dbmgtr = DBMigrator(namespace)

        result = getattr(dbmgtr, operation)()
        if result:
            print(str(result))

    except Exception as e:
        log.log_error('Caught exception: ' + str(e))
        traceback.print_exc()
        print(str(e))
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
