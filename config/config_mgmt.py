'''
config_mgmt.py provides classes for configuration validation and for Dynamic
Port Breakout.
'''

import os
import re
import shutil
import syslog
import tempfile
import yang as ly
from json import load
from sys import flags
from time import sleep as tsleep

import sonic_yang
from jsondiff import diff
from sonic_py_common import port_util
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from utilities_common.general import load_module_from_source


# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')

# Globals
YANG_DIR = "/usr/local/yang-models"
CONFIG_DB_JSON_FILE = '/etc/sonic/confib_db.json'
# TODO: Find a place for it on sonic switch.
DEFAULT_CONFIG_DB_JSON_FILE = '/etc/sonic/port_breakout_config_db.json'

class ConfigMgmt():
    '''
    Class to handle config managment for SONIC, this class will use sonic_yang
    to verify config for the commands which are capable of change in config DB.
    '''

    def __init__(self, source="configDB", debug=False, allowTablesWithoutYang=True,
                 sonicYangOptions=0, configdb=None):
        '''
        Initialise the class, --read the config, --load in data tree.

        Parameters:
            source (str): source for input config, default configDb else file.
            debug (bool): verbose mode.
            allowTablesWithoutYang (bool): allow tables without yang model in
                config or not.
            configdb: configdb to work on.

        Returns:
            void
        '''
        try:
            self.configdbJsonIn = None
            self.configdbJsonOut = None
            self.source = source
            self.allowTablesWithoutYang = allowTablesWithoutYang
            self.sonicYangOptions = sonicYangOptions
            self.configdb = configdb

            # logging vars
            self.SYSLOG_IDENTIFIER = "ConfigMgmt"
            self.DEBUG = debug

            self.__init_sonic_yang()

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise Exception('ConfigMgmt Class creation failed')

        return

    def __init_sonic_yang(self):
        self.sy = sonic_yang.SonicYang(YANG_DIR, debug=self.DEBUG, sonic_yang_options=self.sonicYangOptions)
        # load yang models
        self.sy.loadYangModel()
        # load jIn from config DB or from config DB json file.
        if self.source.lower() == 'configdb':
            self.readConfigDB()
        # treat any other source as file input
        else:
            self.readConfigDBJson(self.source)
        # this will crop config, xlate and load.
        self.sy.loadData(self.configdbJsonIn)

        # Raise if tables without YANG models are not allowed but exist.
        if not self.allowTablesWithoutYang and len(self.sy.tablesWithOutYang):
            raise Exception('Config has tables without YANG models')

    def __del__(self):
        pass

    def tablesWithOutYang(self):
        '''
        Return tables loaded in config for which YANG model does not exist.

        Parameters:
            void

        Returns:
            tablesWithoutYang (list): list of tables.
        '''
        return self.sy.tablesWithOutYang

    def loadData(self, configdbJson):
        '''
        Explicit function to load config data in Yang Data Tree.

        Parameters:
            configdbJson (dict): dict similar to configDb.

        Returns:
            void
        '''
        self.sy.loadData(configdbJson)
        # Raise if tables without YANG models are not allowed but exist.
        if not self.allowTablesWithoutYang and len(self.sy.tablesWithOutYang):
            raise Exception('Config has tables without YANG models')

        return

    def validateConfigData(self):
        '''
        Validate current config data Tree.

        Parameters:
            void

        Returns:
            bool
        '''
        try:
            self.sy.validate_data_tree()
        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR,
                msg='Data Validation Failed')
            return False

        self.sysLog(msg='Data Validation successful', doPrint=True)
        return True

    def sysLog(self, logLevel=syslog.LOG_INFO, msg=None, doPrint=False):
        '''
        Log the msg in syslog file.

        Parameters:
            debug : syslog level
            msg (str): msg to be logged.

        Returns:
            void
        '''
        # log debug only if enabled
        if self.DEBUG == False and logLevel == syslog.LOG_DEBUG:
            return
        # always print < Info level msg with doPrint flag
        if doPrint == True and (logLevel < syslog.LOG_INFO or flags.interactive != 0):
            print("{}".format(msg))
        syslog.openlog(self.SYSLOG_IDENTIFIER)
        syslog.syslog(logLevel, msg)
        syslog.closelog()

        return

    def readConfigDBJson(self, source=CONFIG_DB_JSON_FILE):
        '''
        Read the config from a Config File.

        Parameters:
            source(str): config file name.

        Returns:
            (void)
        '''
        self.sysLog(msg='Reading data from {}'.format(source))
        self.configdbJsonIn = readJsonFile(source)
        #self.sysLog(msg=type(self.configdbJsonIn))
        if not self.configdbJsonIn:
            raise Exception("Can not load config from config DB json file")
        self.sysLog(msg='Reading Input {}'.format(self.configdbJsonIn))

        return

    """
        Get config from redis config DB
    """
    def readConfigDB(self):
        '''
        Read the config in Config DB. Assign it in self.configdbJsonIn.

        Parameters:
            (void)

        Returns:
            (void)
        '''
        self.sysLog(doPrint=True, msg='Reading data from Redis configDb')
        # Read from config DB on sonic switch
        data = dict()
        if self.configdb is None:
            configdb = ConfigDBConnector()
            configdb.connect()
        else:
            configdb = self.configdb
        sonic_cfggen.deep_update(data, sonic_cfggen.FormatConverter.db_to_output(configdb.get_config()))
        self.configdbJsonIn = sonic_cfggen.FormatConverter.to_serialized(data)
        self.sysLog(syslog.LOG_DEBUG, 'Reading Input from ConfigDB {}'.\
            format(self.configdbJsonIn))

        return

    def writeConfigDB(self, jDiff):
        '''
        Write the diff in Config DB.

        Parameters:
            jDiff (dict): config to push in config DB.

        Returns:
            void
        '''
        self.sysLog(doPrint=True, msg='Writing in Config DB')
        data = dict()
        if self.configdb is None:
            configdb = ConfigDBConnector()
            configdb.connect(False)
        else:
            configdb = self.configdb
        sonic_cfggen.deep_update(data, sonic_cfggen.FormatConverter.to_deserialized(jDiff))
        self.sysLog(msg="Write in DB: {}".format(data))
        configdb.mod_config(sonic_cfggen.FormatConverter.output_to_db(data))

        return

    def add_module(self, yang_module_str):
        """
        Validate and add new YANG module to the system.

        Parameters:
            yang_module_str (str): YANG module in string representation.

        Returns:
            None
        """

        module_name = self.get_module_name(yang_module_str)
        module_path = os.path.join(YANG_DIR, '{}.yang'.format(module_name))
        if os.path.exists(module_path):
            raise Exception('{} already exists'.format(module_name))
        with open(module_path, 'w') as module_file:
            module_file.write(yang_module_str)
        try:
            self.__init_sonic_yang()
        except Exception:
            os.remove(module_path)
            raise

    def remove_module(self, module_name):
        """
        Remove YANG module from the system and validate.

        Parameters:
            module_name (str): YANG module name.

        Returns:
            None
        """

        module_path = os.path.join(YANG_DIR, '{}.yang'.format(module_name))
        if not os.path.exists(module_path):
            return
        temp = tempfile.NamedTemporaryFile(delete=False)
        try:
            shutil.move(module_path, temp.name)
            self.__init_sonic_yang()
        except Exception:
            shutil.move(temp.name, module_path)
            raise

    @staticmethod
    def get_module_name(yang_module_str):
        """
        Read yangs module name from yang_module_str

        Parameters:
            yang_module_str(str): YANG module string.

        Returns:
            str: Module name
        """

        # Instantiate new context since parse_module_mem() loads the module into context.
        sy = sonic_yang.SonicYang(YANG_DIR)
        module = sy.ctx.parse_module_mem(yang_module_str, ly.LYS_IN_YANG)
        return module.name()


# End of Class ConfigMgmt

class ConfigMgmtDPB(ConfigMgmt):
    '''
        Config MGMT class for Dynamic Port Breakout(DPB). This is derived from
        ConfigMgmt.
    '''

    def __init__(self, source="configDB", debug=False, allowTablesWithoutYang=True):
        '''
        Initialise the class

        Parameters:
            source (str): source for input config, default configDb else file.
            debug (bool): verbose mode.
            allowTablesWithoutYang (bool): allow tables without yang model in
                config or not.

        Returns:
            void
        '''
        try:
            ConfigMgmt.__init__(self, source=source, debug=debug, \
                allowTablesWithoutYang=allowTablesWithoutYang)
            self.oidKey = 'ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x'

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise Exception('ConfigMgmtDPB Class creation failed')

        return

    def __del__(self):
        pass

    def _checkKeyinAsicDB(self, key, db):
        '''
        Check if a key exists in ASIC DB or not.

        Parameters:
            db (SonicV2Connector): database.
            key (str): key in ASIC DB, with table Seperator if applicable.

        Returns:
            (bool): True, if given key is present.
        '''
        self.sysLog(msg='Check Key in Asic DB: {}'.format(key))
        try:
            # chk key in ASIC DB
            if db.exists('ASIC_DB', key):
                return True
        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise(e)

        return False

    def _checkNoPortsInAsicDb(self, db, ports, portMap):
        '''
        Check ASIC DB for PORTs in port List

        Parameters:
            db (SonicV2Connector): database.
            ports (list): List of ports
            portMap (dict): port to OID map.

        Returns:
            (bool): True, if all ports are not present.
        '''
        try:
            # connect to ASIC DB,
            db.connect(db.ASIC_DB)
            for port in ports:
                key = self.oidKey + portMap[port]
                if self._checkKeyinAsicDB(key, db) == True:
                    return False

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            return False

        return True

    def _verifyPortShutdown(self, db, ports, timeout):
        self.sysLog(doPrint=True, msg="Verify Port shutdown from State DB, Wait...")

        db.connect(db.STATE_DB)
        for waitTime in range(timeout):
            retry = False
            for intf in ports:
                _hash = "PORT_TABLE|{}".format(intf)
                port_status = db.get(db.STATE_DB, _hash, "admin_status")
                if port_status != 'down':
                    retry = True
                    continue
            if retry:
                tsleep(1)
            else:
                break

        if waitTime + 1 == timeout:
            for intf in ports:
                _hash = "PORT_TABLE|{}".format(intf)
                port_status = db.get(db.STATE_DB, _hash, "admin_status")
                if port_status != 'down':
                    self.sysLog(syslog.LOG_CRIT, "Fail to shutdown port {}".format(intf))


    def _verifyAsicDB(self, db, ports, portMap, timeout):
        '''
        Verify in the Asic DB that port are deleted, Keep on trying till timeout
        period.

        Parameters:
            db (SonicV2Connector): database.
            ports (list): port list to check in ASIC DB.
            portMap (dict): oid<->port map.
            timeout (int): timeout period

        Returns:
            (bool)
        '''
        self.sysLog(doPrint=True, msg="Verify Port Deletion from Asic DB, Wait...")
        try:
            for waitTime in range(timeout):
                self.sysLog(logLevel=syslog.LOG_DEBUG, msg='Check Asic DB: {} \
                    try'.format(waitTime+1))
                # checkNoPortsInAsicDb will return True if all ports are not
                # present in ASIC DB
                if self._checkNoPortsInAsicDb(db, ports, portMap):
                    break
                tsleep(1)

            # raise if timer expired
            if waitTime + 1 == timeout:
                self.sysLog(syslog.LOG_CRIT, "!!!  Critical Failure, Ports \
                    are not Deleted from ASIC DB, Bail Out  !!!", doPrint=True)
                raise Exception("Ports are present in ASIC DB after {} secs".format(timeout))

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise e

        return True

    def breakOutPort(self, delPorts=list(), portJson=dict(), force=False, \
            loadDefConfig=True):
        '''
        This is the main function for port breakout. Exposed to caller.

        Parameters:
            delPorts (list): ports to be deleted.
            portJson (dict): Config DB json Part of all Ports, generated from
                platform.json.
            force (bool): if false return dependecies, else delete dependencies.
            loadDefConfig: If loadDefConfig, add default config for ports as well.

        Returns:
            (deps, ret) (tuple)[list, bool]: dependecies and success/failure.
        '''
        MAX_WAIT = 60
        try:
            # delete Port and get the Config diff, deps and True/False
            delConfigToLoad, deps, ret = self._deletePorts(ports=delPorts, \
                force=force)
            # return dependencies if delete port fails
            if ret == False:
                return deps, ret

            # add Ports and get the config diff and True/False
            addConfigtoLoad, ret = self._addPorts(portJson=portJson, \
                loadDefConfig=loadDefConfig)
            # return if ret is False, Great thing, no change is done in Config
            if ret == False:
                return None, ret

            # Save Port OIDs Mapping Before Deleting Port
            dataBase = SonicV2Connector(host="127.0.0.1")
            if_name_map, if_oid_map = port_util.get_interface_oid_map(dataBase)
            self.sysLog(syslog.LOG_DEBUG, 'if_name_map {}'.format(if_name_map))

            # If we are here, then get ready to update the Config DB as below:
            # -- shutdown the ports,
            # -- Update deletion of ports in Config DB,
            # -- verify Asic DB for port deletion,
            # -- then update addition of ports in config DB.
            self._shutdownIntf(delPorts)
            self._verifyPortShutdown(dataBase, delPorts, MAX_WAIT)
            self.writeConfigDB(delConfigToLoad)
            # Verify in Asic DB,
            self._verifyAsicDB(db=dataBase, ports=delPorts, portMap=if_name_map, \
                timeout=MAX_WAIT)
            self.writeConfigDB(addConfigtoLoad)

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            return None, False

        return None, True

    def _deletePorts(self, ports=list(), force=False):
        '''
        Delete ports and dependecies from data tree, validate and return resultant
        config.

        Parameters:
            ports (list): list of ports
            force (bool): if false return dependecies, else delete dependencies.

        Returns:
            (configToLoad, deps, ret) (tuple)[dict, list, bool]: config, dependecies
            and success/fail.
        '''
        configToLoad = None; deps = None
        try:
            self.sysLog(msg="delPorts ports:{} force:{}".format(ports, force))

            self.sysLog(doPrint=True, msg='Start Port Deletion')
            deps = list()

            # Get all dependecies for ports
            for port in ports:
                xPathPort = self.sy.findXpathPortLeaf(port)
                self.sysLog(doPrint=True, msg='Find dependecies for port {}'.\
                    format(port))
                dep = self.sy.find_data_dependencies(str(xPathPort))
                if dep:
                    deps.extend(dep)

            # No further action with no force and deps exist
            if not force and deps:
                return configToLoad, deps, False

            # delets all deps, No topological sort is needed as of now, if deletion
            # of deps fails, return immediately
            elif deps:
                for dep in deps:
                    self.sysLog(msg='Deleting {}'.format(dep))
                    self.sy.deleteNode(str(dep))
            # mark deps as None now,
            deps = None

            # all deps are deleted now, delete all ports now
            for port in ports:
                xPathPort = self.sy.findXpathPort(port)
                self.sysLog(doPrint=True, msg="Deleting Port: " + port)
                self.sy.deleteNode(str(xPathPort))

            # Let`s Validate the tree now
            if not self.validateConfigData():
                return configToLoad, deps, False

            # All great if we are here, Lets get the diff
            self.configdbJsonOut = self.sy.getData()
            # Update configToLoad
            configToLoad = self._updateDiffConfigDB()

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="Port Deletion Failed")
            return configToLoad, deps, False

        return configToLoad, deps, True

    def _addPorts(self, portJson=dict(), loadDefConfig=True):
        '''
        Add ports and default confug in data tree, validate and return resultant
        config.

        Parameters:
            portJson (dict): Config DB json Part of all Ports, generated from
                platform.json.
            loadDefConfig: If loadDefConfig, add default config for ports as well.

        Returns:
            (configToLoad, ret) (tuple)[dict, bool]
        '''
        configToLoad = None
        ports = list(portJson['PORT'].keys())
        try:
            self.sysLog(doPrint=True, msg='Start Port Addition')
            self.sysLog(msg="addPorts Args portjson: {} loadDefConfig: {}".\
                format(portJson, loadDefConfig))

            if loadDefConfig:
                defConfig = self._getDefaultConfig(ports)
                self.sysLog(msg='Default Config: {}'.format(defConfig))

            # get the latest Data Tree, save this in input config, since this
            # is our starting point now
            self.configdbJsonIn = self.sy.getData()

            # Get the out dict as well, if not done already
            if self.configdbJsonOut is None:
                self.configdbJsonOut = self.sy.getData()

            # update portJson in configdbJsonOut PORT part
            self.configdbJsonOut['PORT'].update(portJson['PORT'])
            # merge new config with data tree, this is json level merge.
            # We do not allow new table merge while adding default config.
            if loadDefConfig:
                self.sysLog(doPrint=True, msg="Merge Default Config for {}".\
                    format(ports))
                self._mergeConfigs(self.configdbJsonOut, defConfig, True)

            # create a tree with merged config and validate, if validation is
            # sucessful, then configdbJsonOut contains final and valid config.
            self.sy.loadData(self.configdbJsonOut)
            if self.validateConfigData()==False:
                return configToLoad, False

            # All great if we are here, Let`s get the diff and update COnfig
            configToLoad = self._updateDiffConfigDB()

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="Port Addition Failed")
            return configToLoad, False

        return configToLoad, True

    def _shutdownIntf(self, ports):
        """
        Based on the list of Ports, create a dict to shutdown port, update Config DB.
        Shut down all the interfaces before deletion.

        Parameters:
            ports(list): list of ports, which are getting deleted due to DPB.

        Returns:
            void
        """
        configdb = ConfigDBConnector()
        configdb.connect(False)
        shutDownConf = dict(); shutDownConf["PORT"] = dict()
        for intf in ports:
            port_entry = configdb.get_entry('PORT', intf)
            port_status = port_entry.get("admin_status")
            if port_status == "up":
                shutDownConf["PORT"][intf] = {"admin_status": "down"}
        self.sysLog(msg='shutdown Interfaces: {}'.format(shutDownConf))

        if len(shutDownConf["PORT"]):
            self.writeConfigDB(shutDownConf)

        return

    def _mergeConfigs(self, D1, D2, uniqueKeys=True):
        '''
        Merge D2 dict in D1 dict, Note both first and second dict will change.
        First Dict will have merged part D1 + D2. Second dict will have D2 - D1
        i.e [unique keys in D2]. Unique keys in D2 will be merged in D1 only
        if uniqueKeys=True.
        Usage: This function can be used with 'config load' command to merge
        new config with old.

        Parameters:
            D1 (dict): Partial Config 1.
            D2 (dict): Partial Config 2.
            uniqueKeys (bool)

        Returns:
            bool
        '''
        try:
            def _mergeItems(it1, it2):
                if isinstance(it1, list) and isinstance(it2, list):
                    it1.extend(it2)
                elif isinstance(it1, dict) and isinstance(it2, dict):
                    self._mergeConfigs(it1, it2)
                elif isinstance(it1, list) or isinstance(it2, list):
                    raise Exception("Can not merge Configs, List problem")
                elif isinstance(it1, dict) or isinstance(it2, dict):
                    raise Exception("Can not merge Configs, Dict problem")
                else:
                    # First Dict takes priority
                    pass
                return

            for it in D1:
                # D2 has the key
                if D2.get(it):
                    _mergeItems(D1[it], D2[it])
                    del D2[it]

            # if uniqueKeys are needed, merge rest of the keys of D2 in D1
            if uniqueKeys:
                D1.update(D2)
        except Exce as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="Merge Config failed")
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise e

        return D1

    def _searchKeysInConfig(self, In, Out, skeys):
        '''
        Search Relevant Keys in Input Config using DFS, This function is mainly
        used to search ports related config in Default ConfigDbJson file.

        Parameters:
            In (dict): Input Config to be searched
            skeys (list): Keys to be searched in Input Config i.e. search Keys.
            Out (dict): Contains the search result, i.e. Output Config with skeys.

        Returns:
            found (bool): True if any of skeys is found else False.
        '''
        found = False
        if isinstance(In, dict):
            for key in In:
                for skey in skeys:
                    # pattern is very specific to current primary keys in
                    # config DB, may need to be updated later.
                    pattern = r'^{0}\||{0}$|^{0}$'.format(skey)
                    reg = re.compile(pattern)
                    if reg.search(key):
                        # In primary key, only 1 match can be found, so return
                        Out[key] = In[key]
                        found = True
                        break
                # Put the key in Out by default, if not added already.
                # Remove later, if subelements does not contain any port.
                if Out.get(key) is None:
                    Out[key] = type(In[key])()
                    if self._searchKeysInConfig(In[key], Out[key], skeys) == False:
                        del Out[key]
                    else:
                        found = True

        elif isinstance(In, list):
            for skey in skeys:
                if skey in In:
                    found = True
                    Out.append(skey)

        else:
            # nothing for other keys
            pass

        return found

    def configWithKeys(self, configIn=dict(), keys=list()):
        '''
        This function returns the config with relavant keys in Input Config.
        It calls _searchKeysInConfig.

        Parameters:
            configIn (dict): Input Config
            keys (list): Key list.

        Returns:
            configOut (dict): Output Config containing only key related config.
        '''
        configOut = dict()
        try:
            if len(configIn) and len(keys):
                self._searchKeysInConfig(configIn, configOut, skeys=keys)
        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="configWithKeys Failed, Error: {}".format(str(e)))
            raise e

        return configOut

    def _getDefaultConfig(self, ports=list()):
        '''
        Create a default Config for given Port list from Default Config File.
        It calls _searchKeysInConfig.

        Parameters:
            ports (list): list of ports, for which default config must be fetched.

        Returns:
            defConfigOut (dict): default Config for given Ports.
        '''
        # function code
        try:
            self.sysLog(doPrint=True, msg="Generating default config for {}".format(ports))
            defConfigIn = readJsonFile(DEFAULT_CONFIG_DB_JSON_FILE)
            defConfigOut = dict()
            self._searchKeysInConfig(defConfigIn, defConfigOut, skeys=ports)
        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="getDefaultConfig Failed, Error: {}".format(str(e)))
            raise e

        return defConfigOut

    def _updateDiffConfigDB(self):
        '''
        Return ConfigDb format Diff b/w self.configdbJsonIn, self.configdbJsonOut

        Parameters:
            void

        Returns:
            configToLoad (dict): ConfigDb format Diff
        '''
        try:
            # Get the Diff
            self.sysLog(msg='Generate Final Config to write in DB')
            configDBdiff = self._diffJson()
            # Process diff and create Config which can be updated in Config DB
            configToLoad = self._createConfigToLoad(configDBdiff, \
                self.configdbJsonIn, self.configdbJsonOut)

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="Config Diff Generation failed")
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise e

        return configToLoad

    def _createConfigToLoad(self, diff, inp, outp):
        '''
        Create the config to write in Config DB, i.e. compitible with mod_config()
        This functions has 3 inner functions:
        -- _deleteHandler: to handle delete in diff. See example below.
        -- _insertHandler: to handle insert in diff. See example below.
        -- _recurCreateConfig: recursively create this config.

        Parameters:
            diff: jsondiff b/w 2 configs.
            Example:
            {u'VLAN': {u'Vlan100': {'members': {delete: [(95, 'Ethernet1')]}},
             u'Vlan777': {u'members': {insert: [(92, 'Ethernet2')]}}},
            'PORT': {delete: {u'Ethernet1': {...}}}}

            inp: input config before delete/add ports, i.e. current config Db.
            outp: output config after delete/add ports. i.e. config DB once diff
                is applied.

        Returns:
            configToLoad (dict): config in a format compitible with mod_Config().
        '''

        ### Internal Functions ###
        def _deleteHandler(diff, inp, outp, config):
            '''
            Handle deletions in diff dict
            '''
            if isinstance(inp, dict):
                # Example Case: diff = PORT': {delete: {u'Ethernet1': {...}}}}
                self.sysLog(logLevel=syslog.LOG_DEBUG, \
                    msg="Delete Dict diff:{}".format(diff))
                for key in diff:
                    # make sure keys from diff are present in inp but not in outp
                    if key in inp and key not in outp:
                        if type(inp[key]) == list:
                            self.sysLog(logLevel=syslog.LOG_DEBUG, \
                                msg="Delete List key:{}".format(key))
                            # assign current lists as empty.
                            config[key] = []
                        else:
                            self.sysLog(logLevel=syslog.LOG_DEBUG, \
                                msg="Delete Dict key:{}".format(key))
                            # assign key to None(null), redis will delete entire key
                            config[key] = None
                    else:
                        # should not happen
                        raise Exception('Invalid deletion of {} in diff'.format(key))

            elif isinstance(inp, list):
                # Example case: diff: [(3, 'Ethernet10'), (2, 'Ethernet8')]
                # inp:['Ethernet0', 'Ethernet4', 'Ethernet8', 'Ethernet10']
                # outp:['Ethernet0', 'Ethernet4']
                self.sysLog(logLevel=syslog.LOG_DEBUG, \
                    msg="Delete List diff: {} inp:{} outp:{}".format(diff, inp, outp))
                config.extend(outp)
            return

        def _insertHandler(diff, inp, outp, config):
            '''
            Handle inserts in diff dict
            '''
            if isinstance(outp, dict):
                # Example Case: diff = PORT': {insert: {u'Ethernet1': {...}}}}
                self.sysLog(logLevel=syslog.LOG_DEBUG, \
                    msg="Insert Dict diff:{}".format(diff))
                for key in diff:
                    # make sure keys are only in outp
                    if key not in inp and key in outp:
                        self.sysLog(logLevel=syslog.LOG_DEBUG, \
                            msg="Insert Dict key:{}".format(key))
                        # assign key in config same as outp
                        config[key] = outp[key]
                    else:
                        # should not happen
                        raise Exception('Invalid insertion of {} in diff'.format(key))

            elif isinstance(outp, list):
                # Example diff:[(2, 'Ethernet8'), (3, 'Ethernet10')]
                # in:['Ethernet0', 'Ethernet4']
                # out:['Ethernet0', 'Ethernet4', 'Ethernet8', 'Ethernet10']
                self.sysLog(logLevel=syslog.LOG_DEBUG, \
                    msg="Insert list diff:{} inp:{} outp:{}".format(diff, inp, outp))
                config.extend(outp)
                # configDb stores []->[""], i.e. empty list as list of empty
                # string. While adding default config for newly created ports,
                # inp can be [""], in that case remove it from delta config.
                if inp == ['']:
                    config.remove('');
            return

        def _recurCreateConfig(diff, inp, outp, config):
            '''
            Recursively iterate diff to generate config to write in configDB
            '''
            changed = False
            # updates are represented by list in diff and as dict in outp\inp
            # we do not allow updates right now
            if isinstance(diff, list) and isinstance(outp, dict):
                return changed
            '''
            libYang converts ietf yang types to lower case internally, which
            creates false config diff for us while DPB.

            Example:
            For DEVICE_METADATA['localhost']['mac'] type is yang:mac-address.
            Libyang converts from 'XX:XX:XX:E4:B3:DD' -> 'xx:xx:xx:e4:b3:dd'
            so args for this functions will be:

            diff = DEVICE_METADATA['localhost']['mac']
            where DEVICE_METADATA': {'localhost': {'mac': ['XX:XX:XX:E4:B3:DD', 'xx:xx:xx:e4:b3:dd']}}}
            Note: above dict is representation of diff in config given by diffJson
            library.
            out = 'XX:XX:XX:e4:b3:dd'
            inp = 'xx:xx:xx:E4:B3:DD'

            With below check, we will avoid processing of such config diff for DPB.
            '''
            if isinstance(diff, list) and isinstance(outp, str) and \
              inp.lower() == outp.lower():
                return changed

            idx = -1
            for key in diff:
                idx = idx + 1
                if str(key) == '$delete':
                    _deleteHandler(diff[key], inp, outp, config)
                    changed = True
                elif str(key) == '$insert':
                    _insertHandler(diff[key], inp, outp, config)
                    changed = True
                else:
                    # insert in config by default, remove later if not needed
                    if isinstance(diff, dict):
                        # config should match type of outp
                        config[key] = type(outp[key])()
                        if _recurCreateConfig(diff[key], inp[key], outp[key], \
                            config[key]) == False:
                            del config[key]
                        else:
                            changed = True
                    elif isinstance(diff, list):
                        config.append(key)
                        if _recurCreateConfig(diff[idx], inp[idx], outp[idx], \
                            config[-1]) == False:
                            del config[-1]
                        else:
                            changed = True

            return changed

        ### Function Code ###
        try:
            configToLoad = dict()
            _recurCreateConfig(diff, inp, outp, configToLoad)

        except Exception as e:
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, \
                msg="Create Config to load in DB, Failed")
            self.sysLog(doPrint=True, logLevel=syslog.LOG_ERR, msg=str(e))
            raise e

        return configToLoad

    def _diffJson(self):
        '''
        Return json diff between self.configdbJsonIn, self.configdbJsonOut dicts.

        Parameters:
            void

        Returns:
            (dict): json diff between self.configdbJsonIn, self.configdbJsonOut
            dicts.
            Example:
            {u'VLAN': {u'Vlan100': {'members': {delete: [(95, 'Ethernet1')]}},
             u'Vlan777': {u'members': {insert: [(92, 'Ethernet2')]}}},
            'PORT': {delete: {u'Ethernet1': {...}}}}
        '''
        return diff(self.configdbJsonIn, self.configdbJsonOut, syntax='symmetric')

# end of class ConfigMgmtDPB

# Helper Functions
def readJsonFile(fileName):
    '''
    Read Json file.

    Parameters:
        fileName (str): file

    Returns:
        result (dict): json --> dict
    '''
    try:
        with open(fileName) as f:
            result = load(f)
    except Exception as e:
        raise Exception(e)

    return result
