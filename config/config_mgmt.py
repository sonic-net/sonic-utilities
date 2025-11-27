"""
config_mgmt.py provides classes for configuration validation and for Dynamic
Port Breakout.
"""

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


# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not
# have .py extension.
sonic_cfggen = load_module_from_source(
    "sonic_cfggen", "/usr/local/bin/sonic-cfggen"
)

# Globals
YANG_DIR = "/usr/local/yang-models"
CONFIG_DB_JSON_FILE = "/etc/sonic/confib_db.json"
# TODO: Find a place for it on sonic switch.
DEFAULT_CONFIG_DB_JSON_FILE = "/etc/sonic/port_breakout_config_db.json"


class ConfigMgmt:
    """
    Class to handle config managment for SONIC, this class will use sonic_yang
    to verify config for the commands which are capable of change in config DB.
    """

    def __init__(
        self,
        source="configDB",
        debug=False,
        allow_tables_without_yang=True,
        sonic_yang_options=0,
        configdb=None,
    ):
        """
        Initialise the class, --read the config, --load in data tree.

        Parameters:
            source (str): source for input config, default configDb
                else file.
            debug (bool): verbose mode.
            allow_tables_without_yang (bool): allow tables without yang
                model in config or not.
            configdb: configdb to work on.

        Returns:
            void
        """
        try:
            self.configdb_json_in = None
            self.configdb_json_out = None
            self.source = source
            self.allow_tables_without_yang = allow_tables_without_yang
            self.sonic_yang_options = sonic_yang_options
            self.configdb = configdb

            # logging vars
            self.SYSLOG_IDENTIFIER = "ConfigMgmt"
            self.DEBUG = debug

            self.__init_sonic_yang()

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise Exception("ConfigMgmt Class creation failed")

        return

    def __init_sonic_yang(self):
        self.sy = sonic_yang.SonicYang(
            YANG_DIR,
            debug=self.DEBUG,
            sonic_yang_options=self.sonic_yang_options,
        )
        # load yang models
        self.sy.loadYangModel()
        # load jIn from config DB or from config DB json file.
        if self.source.lower() == "configdb":
            self.read_config_db()
        # treat any other source as file input
        else:
            self.read_config_db_json(self.source)
        # this will crop config, xlate and load.
        self.sy.loadData(self.configdb_json_in)

        # Raise if tables without YANG models are not allowed but exist.
        if not self.allow_tables_without_yang and len(
            self.sy.tablesWithOutYang
        ):
            raise Exception("Config has tables without YANG models")

    def __del__(self):
        pass

    def tables_without_yang(self):
        """
        Return tables loaded in config for which YANG model does not exist.

        Parameters:
            void

        Returns:
            tables_without_yang (list): list of tables.
        """
        return self.sy.tablesWithOutYang

    def load_data(self, configdb_json):
        """
        Explicit function to load config data in Yang Data Tree.

        Parameters:
            configdb_json (dict): dict similar to configDb.

        Returns:
            void
        """
        self.sy.loadData(configdb_json)
        # Raise if tables without YANG models are not allowed but exist.
        if not self.allow_tables_without_yang and len(
            self.sy.tablesWithOutYang
        ):
            raise Exception("Config has tables without YANG models")

        return

    def validate_config_data(self):
        """
        Validate current config data Tree.

        Parameters:
            void

        Returns:
            bool
        """
        try:
            self.sy.validate_data_tree()
        except Exception:
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="Data Validation Failed",
            )
            return False

        self.sys_log(msg="Data Validation successful", do_print=True)
        return True

    def sys_log(self, log_level=syslog.LOG_INFO, msg=None, do_print=False):
        """
        Log the msg in syslog file.

        Parameters:
            debug : syslog level
            msg (str): msg to be logged.

        Returns:
            void
        """
        # log debug only if enabled
        if not self.DEBUG and log_level == syslog.LOG_DEBUG:
            return
        # always print < Info level msg with do_print flag
        if do_print and (
            log_level < syslog.LOG_INFO or flags.interactive != 0
        ):
            print("{}".format(msg))
        syslog.openlog(self.SYSLOG_IDENTIFIER)
        syslog.syslog(log_level, msg)
        syslog.closelog()

        return

    def read_config_db_json(self, source=CONFIG_DB_JSON_FILE):
        """
        Read the config from a Config File.

        Parameters:
            source(str): config file name.

        Returns:
            (void)
        """
        self.sys_log(msg="Reading data from {}".format(source))
        self.configdb_json_in = read_json_file(source)
        # self.sys_log(msg=type(self.configdb_json_in))
        if not self.configdb_json_in:
            raise Exception("Can not load config from config DB json file")
        self.sys_log(msg="Reading Input {}".format(self.configdb_json_in))

        return

    """
        Get config from redis config DB
    """

    def read_config_db(self):
        """
        Read the config in Config DB. Assign it in self.configdb_json_in.

        Parameters:
            (void)

        Returns:
            (void)
        """
        self.sys_log(do_print=True, msg="Reading data from Redis configDb")
        # Read from config DB on sonic switch
        data = dict()
        if self.configdb is None:
            configdb = ConfigDBConnector()
            configdb.connect()
        else:
            configdb = self.configdb
        sonic_cfggen.deep_update(
            data,
            sonic_cfggen.FormatConverter.db_to_output(configdb.get_config()),
        )
        self.configdb_json_in = sonic_cfggen.FormatConverter.to_serialized(
            data
        )
        self.sys_log(
            syslog.LOG_DEBUG,
            "Reading Input from ConfigDB {}".format(self.configdb_json_in),
        )

        return

    def write_config_db(self, j_diff):
        """
        Write the diff in Config DB.

        Parameters:
            j_diff (dict): config to push in config DB.

        Returns:
            void
        """
        self.sys_log(do_print=True, msg="Writing in Config DB")
        data = dict()
        if self.configdb is None:
            configdb = ConfigDBConnector()
            configdb.connect(False)
        else:
            configdb = self.configdb
        sonic_cfggen.deep_update(
            data, sonic_cfggen.FormatConverter.to_deserialized(j_diff)
        )
        self.sys_log(msg="Write in DB: {}".format(data))
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
        module_path = os.path.join(YANG_DIR, "{}.yang".format(module_name))
        if os.path.exists(module_path):
            raise Exception("{} already exists".format(module_name))
        with open(module_path, "w") as module_file:
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

        module_path = os.path.join(YANG_DIR, "{}.yang".format(module_name))
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

        # Instantiate new context since parse_module_mem() loads the
        # module into context.
        sy = sonic_yang.SonicYang(YANG_DIR)
        module = sy.ctx.parse_module_mem(yang_module_str, ly.LYS_IN_YANG)
        return module.name()


# End of Class ConfigMgmt


class ConfigMgmtDPB(ConfigMgmt):
    """
    Config MGMT class for Dynamic Port Breakout(DPB). This is derived
    from ConfigMgmt.
    """

    def __init__(
        self,
        source="configDB",
        debug=False,
        allow_tables_without_yang=True,
    ):
        """
        Initialise the class

        Parameters:
            source (str): source for input config, default configDb
                else file.
            debug (bool): verbose mode.
            allow_tables_without_yang (bool): allow tables without yang
                model in config or not.

        Returns:
            void
        """
        try:
            ConfigMgmt.__init__(
                self,
                source=source,
                debug=debug,
                allow_tables_without_yang=allow_tables_without_yang,
            )
            self.oid_key = "ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x"

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise Exception("ConfigMgmtDPB Class creation failed")

        return

    def __del__(self):
        pass

    def _check_key_in_asic_db(self, key, db):
        """
        Check if a key exists in ASIC DB or not.

        Parameters:
            db (SonicV2Connector): database.
            key (str): key in ASIC DB, with table Seperator if applicable.

        Returns:
            (bool): True, if given key is present.
        """
        self.sys_log(msg="Check Key in Asic DB: {}".format(key))
        try:
            # chk key in ASIC DB
            if db.exists("ASIC_DB", key):
                return True
        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise (e)

        return False

    def _check_no_ports_in_asic_db(self, db, ports, port_map):
        """
        Check ASIC DB for PORTs in port List

        Parameters:
            db (SonicV2Connector): database.
            ports (list): List of ports
            port_map (dict): port to OID map.

        Returns:
            (bool): True, if all ports are not present.
        """
        try:
            # connect to ASIC DB,
            db.connect(db.ASIC_DB)
            for port in ports:
                key = self.oid_key + port_map[port]
                if self._check_key_in_asic_db(key, db):
                    return False

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            return False

        return True

    def _verify_asic_db(self, db, ports, port_map, timeout):
        """
        Verify in the Asic DB that port are deleted, Keep on trying till
        timeout period.

        Parameters:
            db (SonicV2Connector): database.
            ports (list): port list to check in ASIC DB.
            port_map (dict): oid<->port map.
            timeout (int): timeout period

        Returns:
            (bool)
        """
        self.sys_log(
            do_print=True, msg="Verify Port Deletion from Asic DB, Wait..."
        )
        try:
            for wait_time in range(timeout):
                self.sys_log(
                    log_level=syslog.LOG_DEBUG,
                    msg="Check Asic DB: {} try".format(wait_time + 1),
                )
                # _check_no_ports_in_asic_db will return True if all
                # ports are not present in ASIC DB
                if self._check_no_ports_in_asic_db(db, ports, port_map):
                    break
                tsleep(1)

            # raise if timer expired
            if wait_time + 1 == timeout:
                self.sys_log(
                    syslog.LOG_CRIT,
                    (
                        "!!!  Critical Failure, Ports are not Deleted "
                        "from ASIC DB, Bail Out  !!!"
                    ),
                    do_print=True,
                )
                raise Exception(
                    "Ports are present in ASIC DB after {} secs".format(
                        timeout
                    )
                )

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise e

        return True

    def break_out_port(
        self,
        del_ports=list(),
        port_json=dict(),
        force=False,
        load_def_config=True,
    ):
        """
        This is the main function for port breakout. Exposed to caller.

        Parameters:
            del_ports (list): ports to be deleted.
            port_json (dict): Config DB json Part of all Ports, generated
                from platform.json.
            force (bool): if false return dependecies, else delete
                dependencies.
            load_def_config: If load_def_config, add default config for
                ports as well.

        Returns:
            (deps, ret) (tuple)[list, bool]: dependecies and success/failure.
        """
        MAX_WAIT = 60
        try:
            # delete Port and get the Config diff, deps and True/False
            del_config_to_load, deps, ret = self._delete_ports(
                ports=del_ports, force=force
            )
            # return dependencies if delete port fails
            if not ret:
                return deps, ret

            # add Ports and get the config diff and True/False
            add_config_to_load, ret = self._add_ports(
                port_json=port_json, load_def_config=load_def_config
            )
            # return if ret is False, Great thing, no change is done in Config
            if not ret:
                return None, ret

            # Save Port OIDs Mapping Before Deleting Port
            data_base = SonicV2Connector(host="127.0.0.1")
            if_name_map, if_oid_map = port_util.get_interface_oid_map(
                data_base
            )
            self.sys_log(
                syslog.LOG_DEBUG, "if_name_map {}".format(if_name_map)
            )

            # If we are here, then get ready to update the Config DB as below:
            # -- shutdown the ports,
            # -- Update deletion of ports in Config DB,
            # -- verify Asic DB for port deletion,
            # -- then update addition of ports in config DB.
            self._shutdown_intf(del_ports)
            self.write_config_db(del_config_to_load)
            # Verify in Asic DB,
            self._verify_asic_db(
                db=data_base,
                ports=del_ports,
                port_map=if_name_map,
                timeout=MAX_WAIT,
            )
            self.write_config_db(add_config_to_load)

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            return None, False

        return None, True

    def _delete_ports(self, ports=list(), force=False):
        """
        Delete ports and dependecies from data tree, validate and return
        resultant config.

        Parameters:
            ports (list): list of ports
            force (bool): if false return dependecies, else delete
                dependencies.

        Returns:
            (config_to_load, deps, ret) (tuple)[dict, list, bool]:
                config, dependecies and success/fail.
        """
        config_to_load = None
        deps = None
        try:
            self.sys_log(msg="delPorts ports:{} force:{}".format(ports, force))

            self.sys_log(do_print=True, msg="Start Port Deletion")
            deps = list()

            # Get all dependecies for ports
            for port in ports:
                xPathPort = self.sy.findXpathPortLeaf(port)
                self.sys_log(
                    do_print=True,
                    msg="Find dependecies for port {}".format(port),
                )
                dep = self.sy.find_data_dependencies(str(xPathPort))
                if dep:
                    deps.extend(dep)

            # No further action with no force and deps exist
            if not force and deps:
                return config_to_load, deps, False

            # delets all deps, No topological sort is needed as of now,
            # if deletion of deps fails, return immediately
            elif deps:
                for dep in deps:
                    self.sys_log(msg="Deleting {}".format(dep))
                    self.sy.deleteNode(str(dep))
            # mark deps as None now,
            deps = None

            # all deps are deleted now, delete all ports now
            for port in ports:
                xPathPort = self.sy.findXpathPort(port)
                self.sys_log(do_print=True, msg="Deleting Port: " + port)
                self.sy.deleteNode(str(xPathPort))

            # Let`s Validate the tree now
            if not self.validate_config_data():
                return config_to_load, deps, False

            # All great if we are here, Lets get the diff
            self.configdb_json_out = self.sy.getData()
            # Update config_to_load
            config_to_load = self._update_diff_config_db()

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="Port Deletion Failed",
            )
            return config_to_load, deps, False

        return config_to_load, deps, True

    def _add_ports(self, port_json=dict(), load_def_config=True):
        """
        Add ports and default confug in data tree, validate and return
        resultant config.

        Parameters:
            port_json (dict): Config DB json Part of all Ports, generated
                from platform.json.
            load_def_config: If load_def_config, add default config for
                ports as well.

        Returns:
            (config_to_load, ret) (tuple)[dict, bool]
        """
        config_to_load = None
        ports = list(port_json["PORT"].keys())
        try:
            self.sys_log(do_print=True, msg="Start Port Addition")
            self.sys_log(
                msg="addPorts Args portjson: {} load_def_config: {}".format(
                    port_json, load_def_config
                )
            )

            if load_def_config:
                def_config = self._get_default_config(ports)
                self.sys_log(msg="Default Config: {}".format(def_config))

            # get the latest Data Tree, save this in input config, since this
            # is our starting point now
            self.configdb_json_in = self.sy.getData()

            # Get the out dict as well, if not done already
            if self.configdb_json_out is None:
                self.configdb_json_out = self.sy.getData()

            # update port_json in configdb_json_out PORT part
            self.configdb_json_out["PORT"].update(port_json["PORT"])
            # merge new config with data tree, this is json level merge.
            # We do not allow new table merge while adding default
            # config.
            if load_def_config:
                self.sys_log(
                    do_print=True,
                    msg="Merge Default Config for {}".format(ports),
                )
                self._merge_configs(self.configdb_json_out, def_config, True)

            # create a tree with merged config and validate, if validation
            # is sucessful, then configdb_json_out contains final and valid
            # config.
            self.sy.loadData(self.configdb_json_out)
            if not self.validate_config_data():
                return config_to_load, False

            # All great if we are here, Let`s get the diff and update COnfig
            config_to_load = self._update_diff_config_db()

        except Exception as e:
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="Port Addition Failed",
            )
            return config_to_load, False

        return config_to_load, True

    def _shutdown_intf(self, ports):
        """
        Based on the list of Ports, create a dict to shutdown port, update
        Config DB. Shut down all the interfaces before deletion.

        Parameters:
            ports(list): list of ports, which are getting deleted due to DPB.

        Returns:
            void
        """
        shut_down_conf = dict()
        shut_down_conf["PORT"] = dict()
        for intf in ports:
            shut_down_conf["PORT"][intf] = {"admin_status": "down"}
        self.sys_log(msg="shutdown Interfaces: {}".format(shut_down_conf))

        if len(shut_down_conf["PORT"]):
            self.write_config_db(shut_down_conf)

        return

    def _merge_configs(self, d1, d2, unique_keys=True):
        """
        Merge d2 dict in d1 dict, Note both first and second dict will change.
        First Dict will have merged part d1 + d2. Second dict will have d2 - d1
        i.e [unique keys in d2]. Unique keys in d2 will be merged in d1 only
        if unique_keys=True.
        Usage: This function can be used with 'config load' command to merge
        new config with old.

        Parameters:
            d1 (dict): Partial Config 1.
            d2 (dict): Partial Config 2.
            unique_keys (bool)

        Returns:
            bool
        """
        try:

            def _merge_items(it1, it2):
                if isinstance(it1, list) and isinstance(it2, list):
                    it1.extend(it2)
                elif isinstance(it1, dict) and isinstance(it2, dict):
                    self._merge_configs(it1, it2)
                elif isinstance(it1, list) or isinstance(it2, list):
                    raise Exception("Can not merge Configs, List problem")
                elif isinstance(it1, dict) or isinstance(it2, dict):
                    raise Exception("Can not merge Configs, Dict problem")
                else:
                    # First Dict takes priority
                    pass
                return

            for it in d1:
                # d2 has the key
                if d2.get(it):
                    _merge_items(d1[it], d2[it])
                    del d2[it]

            # if unique_keys are needed, merge rest of the keys of d2 in d1
            if unique_keys:
                d1.update(d2)
        except Exception as e:
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="Merge Config failed",
            )
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise e

        return d1

    def _search_keys_in_config(self, config_in, config_out, skeys):
        """
        Search Relevant Keys in Input Config using DFS, This function is mainly
        used to search ports related config in Default ConfigDbJson file.

        Parameters:
            config_in (dict): Input Config to be searched
            skeys (list): Keys to be searched in Input Config i.e. search Keys.
            config_out (dict): Contains the search result, i.e. Output
                Config with skeys.

        Returns:
            found (bool): True if any of skeys is found else False.
        """
        found = False
        if isinstance(config_in, dict):
            for key in config_in:
                for skey in skeys:
                    # pattern is very specific to current primary keys in
                    # config DB, may need to be updated later.
                    pattern = r"^{0}\||{0}$|^{0}$".format(skey)
                    reg = re.compile(pattern)
                    if reg.search(key):
                        # In primary key, only 1 match can be found, so return
                        config_out[key] = config_in[key]
                        found = True
                        break
                # Put the key in config_out by default, if not added already.
                # Remove later, if subelements does not contain any port.
                if config_out.get(key) is None:
                    config_out[key] = type(config_in[key])()
                    if not self._search_keys_in_config(
                        config_in[key], config_out[key], skeys
                    ):
                        del config_out[key]
                    else:
                        found = True

        elif isinstance(config_in, list):
            for skey in skeys:
                if skey in config_in:
                    found = True
                    config_out.append(skey)

        else:
            # nothing for other keys
            pass

        return found

    def config_with_keys(self, config_in=dict(), keys=list()):
        """
        This function returns the config with relavant keys in Input Config.
        It calls _search_keys_in_config.

        Parameters:
            config_in (dict): Input Config
            keys (list): Key list.

        Returns:
            config_out (dict): Output Config containing only key related
                config.
        """
        config_out = dict()
        try:
            if len(config_in) and len(keys):
                self._search_keys_in_config(config_in, config_out, skeys=keys)
        except Exception as e:
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="config_with_keys Failed, Error: {}".format(str(e)),
            )
            raise e

        return config_out

    def _get_default_config(self, ports=list()):
        """
        Create a default Config for given Port list from Default Config
        File. It calls _search_keys_in_config.

        Parameters:
            ports (list): list of ports, for which default config must
                be fetched.

        Returns:
            def_config_out (dict): default Config for given Ports.
        """
        # function code
        try:
            self.sys_log(
                do_print=True,
                msg="Generating default config for {}".format(ports),
            )
            def_config_in = read_json_file(DEFAULT_CONFIG_DB_JSON_FILE)
            def_config_out = dict()
            self._search_keys_in_config(
                def_config_in, def_config_out, skeys=ports
            )
        except Exception as e:
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="get_default_config Failed, Error: {}".format(str(e)),
            )
            raise e

        return def_config_out

    def _update_diff_config_db(self):
        """
        Return ConfigDb format Diff b/w self.configdb_json_in,
        self.configdb_json_out

        Parameters:
            void

        Returns:
            config_to_load (dict): ConfigDb format Diff
        """
        try:
            # Get the Diff
            self.sys_log(msg="Generate Final Config to write in DB")
            config_db_diff = self._diff_json()
            # Process diff and create Config which can be updated in
            # Config DB
            config_to_load = self._create_config_to_load(
                config_db_diff, self.configdb_json_in, self.configdb_json_out
            )

        except Exception as e:
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="Config Diff Generation failed",
            )
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise e

        return config_to_load

    def _create_config_to_load(self, diff, inp, outp):
        """
        Create the config to write in Config DB, i.e. compitible with
        mod_config(). This functions has 3 inner functions:
        -- _delete_handler: to handle delete in diff. See example below.
        -- _insert_handler: to handle insert in diff. See example below.
        -- _recur_create_config: recursively create this config.

        Parameters:
            diff: jsondiff b/w 2 configs.
            Example:
            {u'VLAN': {u'Vlan100': {'members': {delete: [(95,
                'Ethernet1')]}},
             u'Vlan777': {u'members': {insert: [(92, 'Ethernet2')]}}},
            'PORT': {delete: {u'Ethernet1': {...}}}}

            inp: input config before delete/add ports, i.e. current
                config Db.
            outp: output config after delete/add ports. i.e. config DB
                once diff is applied.

        Returns:
            config_to_load (dict): config in a format compitible with
                mod_Config().
        """

        # Internal Functions #
        def _delete_handler(diff, inp, outp, config):
            """
            Handle deletions in diff dict
            """
            if isinstance(inp, dict):
                # Example Case: diff = PORT': {delete: {u'Ethernet1':
                # {...}}}}
                self.sys_log(
                    log_level=syslog.LOG_DEBUG,
                    msg="Delete Dict diff:{}".format(diff),
                )
                for key in diff:
                    # make sure keys from diff are present in inp
                    # but not in outp
                    if key in inp and key not in outp:
                        if isinstance(inp[key], list):
                            self.sys_log(
                                log_level=syslog.LOG_DEBUG,
                                msg="Delete List key:{}".format(key),
                            )
                            # assign current lists as empty.
                            config[key] = []
                        else:
                            self.sys_log(
                                log_level=syslog.LOG_DEBUG,
                                msg="Delete Dict key:{}".format(key),
                            )
                            # assign key to None(null),
                            # redis will delete entire key
                            config[key] = None
                    else:
                        # should not happen
                        raise Exception(
                            "Invalid deletion of {} in diff".format(key)
                        )

            elif isinstance(inp, list):
                # Example case: diff: [(3, 'Ethernet10'), (2, 'Ethernet8')]
                # inp:['Ethernet0', 'Ethernet4', 'Ethernet8',
                # 'Ethernet10']
                # outp:['Ethernet0', 'Ethernet4']
                self.sys_log(
                    log_level=syslog.LOG_DEBUG,
                    msg="Delete List diff: {} inp:{} outp:{}".format(
                        diff, inp, outp
                    ),
                )
                config.extend(outp)
            return

        def _insert_handler(diff, inp, outp, config):
            """
            Handle inserts in diff dict
            """
            if isinstance(outp, dict):
                # Example Case: diff = PORT': {insert: {u'Ethernet1':
                # {...}}}}
                self.sys_log(
                    log_level=syslog.LOG_DEBUG,
                    msg="Insert Dict diff:{}".format(diff),
                )
                for key in diff:
                    # make sure keys are only in outp
                    if key not in inp and key in outp:
                        self.sys_log(
                            log_level=syslog.LOG_DEBUG,
                            msg="Insert Dict key:{}".format(key),
                        )
                        # assign key in config same as outp
                        config[key] = outp[key]
                    else:
                        # should not happen
                        raise Exception(
                            "Invalid insertion of {} in diff".format(key)
                        )

            elif isinstance(outp, list):
                # Example diff:[(2, 'Ethernet8'), (3, 'Ethernet10')]
                # in:['Ethernet0', 'Ethernet4']
                # out:['Ethernet0', 'Ethernet4', 'Ethernet8', 'Ethernet10']
                self.sys_log(
                    log_level=syslog.LOG_DEBUG,
                    msg="Insert list diff:{} inp:{} outp:{}".format(
                        diff, inp, outp
                    ),
                )
                config.extend(outp)
                # configDb stores []->[""], i.e. empty list as list of empty
                # string. While adding default config for newly created ports,
                # inp can be [""], in that case remove it from delta config.
                if inp == [""]:
                    config.remove("")
            return

        def _recur_create_config(diff, inp, outp, config):
            """
            Recursively iterate diff to generate config to write in configDB
            """
            changed = False
            # updates are represented by list in diff and as dict in outp\inp
            # we do not allow updates right now
            if isinstance(diff, list) and isinstance(outp, dict):
                return changed
            """
            libYang converts ietf yang types to lower case internally, which
            creates false config diff for us while DPB.

            Example:
            For DEVICE_METADATA['localhost']['mac'] type is yang:mac-address.
            Libyang converts from 'XX:XX:XX:E4:B3:DD' -> 'xx:xx:xx:e4:b3:dd'
            so args for this functions will be:

            diff = DEVICE_METADATA['localhost']['mac']
            where DEVICE_METADATA':
                {
                    'localhost':
                        {
                            'mac': ['XX:XX:XX:E4:B3:DD', 'xx:xx:xx:e4:b3:dd']
                        }
                    }
                }
            Note: above dict is representation of diff in config given by
            diffJson library.
            out = 'XX:XX:XX:e4:b3:dd'
            inp = 'xx:xx:xx:E4:B3:DD'

            With below check, we will avoid processing of such config diff
            for DPB.
            """
            if (
                isinstance(diff, list)
                and isinstance(outp, str)
                and inp.lower() == outp.lower()
            ):
                return changed

            idx = -1
            for key in diff:
                idx = idx + 1
                if str(key) == "$delete":
                    _delete_handler(diff[key], inp, outp, config)
                    changed = True
                elif str(key) == "$insert":
                    _insert_handler(diff[key], inp, outp, config)
                    changed = True
                else:
                    # insert in config by default, remove later if not needed
                    if isinstance(diff, dict):
                        # config should match type of outp
                        config[key] = type(outp[key])()
                        if not _recur_create_config(
                            diff[key], inp[key], outp[key], config[key]
                        ):
                            del config[key]
                        else:
                            changed = True
                    elif isinstance(diff, list):
                        config.append(key)
                        if not _recur_create_config(
                            diff[idx], inp[idx], outp[idx], config[-1]
                        ):
                            del config[-1]
                        else:
                            changed = True

            return changed

        # Function Code #
        try:
            config_to_load = dict()
            _recur_create_config(diff, inp, outp, config_to_load)

        except Exception as e:
            self.sys_log(
                do_print=True,
                log_level=syslog.LOG_ERR,
                msg="Create Config to load in DB, Failed",
            )
            self.sys_log(do_print=True, log_level=syslog.LOG_ERR, msg=str(e))
            raise e

        return config_to_load

    def _diff_json(self):
        """
        Return json diff between self.configdb_json_in,
        self.configdb_json_out dicts.

        Parameters:
            void

        Returns:
            (dict): json diff between self.configdb_json_in,
                self.configdb_json_out dicts.
            Example:
            {u'VLAN': {u'Vlan100': {'members': {delete: [(95, 'Ethernet1')]}},
             u'Vlan777': {u'members': {insert: [(92, 'Ethernet2')]}}},
            'PORT': {delete: {u'Ethernet1': {...}}}}
        """
        return diff(
            self.configdb_json_in,
            self.configdb_json_out,
            syntax="symmetric",
        )


# end of class ConfigMgmtDPB


# Helper Functions
def read_json_file(file_name):
    """
    Read Json file.

    Parameters:
        file_name (str): file

    Returns:
        result (dict): json --> dict
    """
    try:
        with open(file_name) as f:
            result = load(f)
    except Exception as e:
        raise Exception(e)

    return result
