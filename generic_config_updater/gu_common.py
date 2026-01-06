import json
import jsonpatch
import importlib
from jsonpointer import JsonPointer
import sonic_yang
import sonic_yang_ext
import subprocess
import yang as ly
import copy
import re
import os
from sonic_py_common import logger, multi_asic
from enum import Enum
from functools import cmp_to_key

YANG_DIR = "/usr/local/yang-models"
SYSLOG_IDENTIFIER = "GenericConfigUpdater"
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
GCU_FIELD_OP_CONF_FILE = f"{SCRIPT_DIR}/gcu_field_operation_validators.conf.json"
HOST_NAMESPACE = "localhost"


class GenericConfigUpdaterError(Exception):
    pass

class IllegalPatchOperationError(ValueError):
    pass

class EmptyTableError(ValueError):
    pass

class JsonChange:
    """
    A class that describes a partial change to a JSON object.
    It is is similar to JsonPatch, but the order of updating the configs is unknown.
    Only the final outcome of the update can be retrieved.
    It provides a single function to apply the change to a given JSON object.
   """
    def __init__(self, patch):
        self.patch = patch

    def apply(self, config, in_place: bool = False):
        return self.patch.apply(config, in_place)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'{self.patch}'

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, JsonChange):
            return self.patch == other.patch
        return False


def get_config_db_as_json(scope=None):
    text = get_config_db_as_text(scope=scope)
    config_db_json = json.loads(text)
    config_db_json.pop("bgpraw", None)
    return config_db_json


def get_config_db_as_text(scope=None):
    if scope is not None and scope != multi_asic.DEFAULT_NAMESPACE:
        cmd = ['sonic-cfggen', '-d', '--print-data', '-n', scope]
    else:
        cmd = ['sonic-cfggen', '-d', '--print-data']
    result = subprocess.Popen(cmd, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    text, err = result.communicate()
    return_code = result.returncode
    if return_code:
        raise GenericConfigUpdaterError(f"Failed to get running config for namespace: {scope},"
                                        f" Return code: {return_code}, Error: {err}")
    return text


class ConfigWrapper:
    def __init__(self, yang_dir=YANG_DIR, scope=multi_asic.DEFAULT_NAMESPACE):
        self.scope = scope
        self.yang_dir = YANG_DIR
        self.sonic_yang_with_loaded_models = None

    def get_config_db_as_json(self):
        return get_config_db_as_json(self.scope)

    def _get_config_db_as_text(self):
        return get_config_db_as_text(self.scope)

    def get_sonic_yang_as_json(self):
        config_db_json = self.get_config_db_as_json()
        return self.convert_config_db_to_sonic_yang(config_db_json)

    def convert_config_db_to_sonic_yang(self, config_db_as_json):
        sy = self.create_sonic_yang_with_loaded_models()

        # Crop config_db tables that do not have sonic yang models
        cropped_config_db_as_json = self.crop_tables_without_yang(config_db_as_json)

        sonic_yang_as_json = dict()

        sy._xlateConfigDBtoYang(cropped_config_db_as_json, sonic_yang_as_json)

        return sonic_yang_as_json

    def convert_sonic_yang_to_config_db(self, sonic_yang_as_json):
        sy = self.create_sonic_yang_with_loaded_models()

        # replace container of the format 'module:table' with just 'table'
        new_sonic_yang_json = {}
        for module_top in sonic_yang_as_json:
            new_sonic_yang_json[module_top] = {}
            for container in sonic_yang_as_json[module_top]:
                tokens = container.split(':')
                if len(tokens) > 2:
                    raise ValueError(f"Expecting '<module>:<table>' or '<table>', found {container}")
                table = container if len(tokens) == 1 else tokens[1]
                new_sonic_yang_json[module_top][table] = sonic_yang_as_json[module_top][container]

        config_db_as_json = dict()
        sy.xlateJson = new_sonic_yang_json
        sy.revXlateJson = config_db_as_json
        sy._revXlateYangtoConfigDB(new_sonic_yang_json, config_db_as_json)

        return config_db_as_json

    def validate_sonic_yang_config(self, sonic_yang_as_json):
        config_db_as_json = self.convert_sonic_yang_to_config_db(sonic_yang_as_json)

        sy = self.create_sonic_yang_with_loaded_models()

        try:
            # Loading data automatically does full validation
            sy.loadData(config_db_as_json)
            return True, None
        except sonic_yang.SonicYangException as ex:
            return False, ex

    def validate_config_db_config(self, config_db_as_json):
        sy = self.create_sonic_yang_with_loaded_models()

        # TODO: Move these validators to YANG models
        supplemental_yang_validators = [self.validate_bgp_peer_group,
                                        self.validate_lanes]

        try:
            # Loading data automatically does full validation
            sy.loadData(config_db_as_json)
            for supplemental_yang_validator in supplemental_yang_validators:
                success, error = supplemental_yang_validator(config_db_as_json)
                if not success:
                    return success, error
        except sonic_yang.SonicYangException as ex:
            return False, ex

        return True, None

    def validate_field_operation(self, old_config, target_config):
        """
        Some fields in ConfigDB are restricted and may not allow third-party addition, replacement, or removal.
        Because YANG only validates state and not transitions, this method helps to JsonPatch operations/transitions for the specified fields.
        """
        patch = jsonpatch.JsonPatch.from_diff(old_config, target_config)

        # illegal_operations_to_fields_map['remove'] yields a list of fields for which `remove` is an illegal operation
        illegal_operations_to_fields_map = {
            'add':[],
            'replace': [],
            'remove': [
                '/PFC_WD/GLOBAL/POLL_INTERVAL',
                '/PFC_WD/GLOBAL',
                '/LOOPBACK_INTERFACE/Loopback0']
        }
        for operation, field_list in illegal_operations_to_fields_map.items():
            for field in field_list:
                if any(op['op'] == operation and field == op['path'] for op in patch):
                    raise IllegalPatchOperationError("Given patch operation is invalid. Operation: {} is illegal on field: {}".format(operation, field))

        self.illegal_dataacl_check(old_config, target_config)

        def _invoke_validating_function(cmd, jsonpatch_element):
            # cmd is in the format as <package/module name>.<method name>
            method_name = cmd.split(".")[-1]
            module_name = ".".join(cmd.split(".")[0:-1])
            if module_name != "generic_config_updater.field_operation_validators" or "validator" not in method_name:
                raise GenericConfigUpdaterError("Attempting to call invalid method {} in module {}. Module must be generic_config_updater.field_operation_validators, and method must be a defined validator".format(method_name, module_name))
            module = importlib.import_module(module_name, package=None)
            method_to_call = getattr(module, method_name)
            return method_to_call(self.scope, jsonpatch_element)

        if os.path.exists(GCU_FIELD_OP_CONF_FILE):
            with open(GCU_FIELD_OP_CONF_FILE, "r") as s:
                gcu_field_operation_conf = json.load(s)
        else:
            raise GenericConfigUpdaterError("GCU field operation validators config file not found")

        for element in patch:
            path = element["path"]
            match = re.search(r'\/([^\/]+)(\/|$)', path) # This matches the table name in the path, eg if path if /PFC_WD/GLOBAL, the match would be PFC_WD
            if match is not None:
                table = match.group(1)
            else:
                raise GenericConfigUpdaterError("Invalid jsonpatch path: {}".format(path))
            validating_functions= set()
            tables = gcu_field_operation_conf["tables"]
            validating_functions.update(tables.get(table, {}).get("field_operation_validators", []))

            for function in validating_functions:
                if not _invoke_validating_function(function, element):
                    raise IllegalPatchOperationError("Modification of {} table is illegal- validating function {} returned False".format(table, function))

    def illegal_dataacl_check(self, old_config, upd_config):
        '''
        Block data ACL changes when patch includes:
        1. table "type" being replaced
        2. rule update on tables with table "type" replaced
        This will cause race condition when swss consume the change of
        acl table and acl rule and make the changed acl rule inactive
        '''
        old_acl_table = old_config.get("ACL_TABLE", {})
        upd_acl_table = upd_config.get("ACL_TABLE", {})

        # Pick data acl table with "type" field
        old_dacl_table = [table for table, fields in old_acl_table.items()
                          if fields.get("type") and fields["type"] != "CTRLPLANE"]
        upd_dacl_table = [table for table, fields in upd_acl_table.items()
                          if fields.get("type") and fields["type"] != "CTRLPLANE"]

        # Pick intersect common tables that "type" being replaced
        common_dacl_table = set(old_dacl_table).intersection(set(upd_dacl_table))
        # Identify tables from the intersection where the "type" field differs
        modified_common_dacl_table = [
            table for table in common_dacl_table
            if old_acl_table[table]["type"] != upd_acl_table[table]["type"]
        ]

        old_acl_rule = old_config.get("ACL_RULE", {})
        upd_acl_rule = upd_config.get("ACL_RULE", {})

        # Pick rules with its dependent table which has "type" replaced
        old_dacl_rule = [rule for rule in old_acl_rule
                         if rule.split("|")[0] in modified_common_dacl_table]
        upd_dacl_rule = [rule for rule in upd_acl_rule
                         if rule.split("|")[0] in modified_common_dacl_table]

        # Block changes if acl rule change on tables with "type" replaced
        for key in set(old_dacl_rule).union(set(upd_dacl_rule)):
            if (old_acl_rule.get(key, {}) != upd_acl_rule.get(key, {})):
                raise IllegalPatchOperationError(
                    "Modification of dataacl rule {} is illegal: \
                        acl table type changed in {}".format(
                            key, modified_common_dacl_table
                    ))

    def validate_lanes(self, config_db):
        if "PORT" not in config_db:
            return True, None

        ports = config_db["PORT"]

        # Validate each lane separately, make sure it is not empty, and is a number
        port_to_lanes_map = {}
        for port in ports:
            attrs = ports[port]
            if "lanes" in attrs:
                lanes_str = attrs["lanes"]
                lanes_with_whitespaces = lanes_str.split(",")
                lanes = [lane.strip() for lane in lanes_with_whitespaces]
                for lane in lanes:
                    if not lane:
                        return False, f"PORT '{port}' has an empty lane"
                    if not lane.isdigit():
                        return False, f"PORT '{port}' has an invalid lane '{lane}'"
                port_to_lanes_map[port] = lanes

        # Validate lanes are unique
        # TODO: Move this attribute (platform with duplicated lanes in ports) to YANG models
        dup_lanes_platforms = [
            'x86_64-arista_7050cx3_32c',
            'x86_64-arista_7050cx3_32s',
            'x86_64-dellemc_s5232f_c3538-r0',
        ]
        metadata = config_db.get("DEVICE_METADATA", {})
        platform = metadata.get("localhost", {}).get("platform", None)
        if platform not in dup_lanes_platforms:
            existing = {}
            for port in port_to_lanes_map:
                lanes = port_to_lanes_map[port]
                for lane in lanes:
                    if lane in existing:
                        return False, f"'{lane}' lane is used multiple times in PORT: {set([port, existing[lane]])}"
                    existing[lane] = port
        return True, None

    def validate_bgp_peer_group(self, config_db):
        if "BGP_PEER_RANGE" not in config_db:
            return True, None

        visited = {}
        table = config_db["BGP_PEER_RANGE"]
        for peer_group_name in table:
            peer_group = table[peer_group_name]
            if "ip_range" not in peer_group:
                continue

            # TODO: convert string to IpAddress object for better handling of IPs
            # TODO: validate range intersection
            ip_range = peer_group["ip_range"]

            # Use "default" if vrf_name is missing or empty
            if "vrf_name" not in peer_group:
                vrf_name = "default"
            else:
                vrf_name = peer_group["vrf_name"]

            for ip in ip_range:
                key = (ip, vrf_name)
                if key in visited:
                    return False, f"{ip} with vrf {vrf_name} is duplicated in BGP_PEER_RANGE: {set([peer_group_name, visited[key]])}"
                visited[key] = peer_group_name

        return True, None

    def crop_tables_without_yang(self, config_db_as_json):
        sy = self.create_sonic_yang_with_loaded_models()

        # Current sonic-yang-mgmt guarantees _cropConfigDB() will deep copy if
        # it needs to modify.
        sy.jIn = config_db_as_json
        sy.tablesWithOutYang = dict()
        sy._cropConfigDB()

        return sy.jIn

    def get_empty_tables(self, config):
        empty_tables = []
        for key in config.keys():
            if not(config[key]):
                empty_tables.append(key)
        return empty_tables

    def remove_empty_tables(self, config):
        config_with_non_empty_tables = {}
        for table in config:
            if config[table]:
                config_with_non_empty_tables[table] = copy.deepcopy(config[table])
        return config_with_non_empty_tables

    # TODO: move creating copies of sonic_yang with loaded models to sonic-yang-mgmt directly
    def create_sonic_yang_with_loaded_models(self):
        # sonic_yang_with_loaded_models will only be initialized once the first time this method is called
        if self.sonic_yang_with_loaded_models is None:
            sonic_yang_print_log_enabled = genericUpdaterLogging.get_verbose()
            loaded_models_sy = sonic_yang.SonicYang(self.yang_dir, print_log_enabled=sonic_yang_print_log_enabled)
            loaded_models_sy.loadYangModel() # This call takes a long time (100s of ms) because it reads files from disk
            self.sonic_yang_with_loaded_models = loaded_models_sy

        return self.sonic_yang_with_loaded_models

class DryRunConfigWrapper(ConfigWrapper):
    # This class will simulate all read/write operations to ConfigDB on a virtual storage unit.
    def __init__(self, initial_imitated_config_db=None, scope=multi_asic.DEFAULT_NAMESPACE):
        super().__init__(scope=scope)
        self.logger = genericUpdaterLogging.get_logger(title="** DryRun", print_all_to_console=True)
        self.imitated_config_db = copy.deepcopy(initial_imitated_config_db)

    def apply_change_to_config_db(self, current_config_db: dict, change):
        self._init_imitated_config_db_if_none()
        self.logger.log_notice(f"Would apply {change}")
        self.imitated_config_db = change.apply(current_config_db, in_place=True)
        return self.imitated_config_db

    def get_config_db_as_json(self):
        self._init_imitated_config_db_if_none()
        return self.imitated_config_db

    def _init_imitated_config_db_if_none(self):
        # if there is no initial imitated config_db and it is the first time calling this method
        if self.imitated_config_db is None:
            self.imitated_config_db = super().get_config_db_as_json()


class PatchWrapper:
    def __init__(self, config_wrapper=None, scope=multi_asic.DEFAULT_NAMESPACE):
        self.scope = scope
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper(self.scope)
        self.path_addressing = PathAddressing(self.config_wrapper)

    def validate_config_db_patch_has_yang_models(self, patch):
        config_db = {}
        for operation in patch:
            tokens = self.path_addressing.get_path_tokens(operation[OperationWrapper.PATH_KEYWORD])
            if len(tokens) == 0: # Modifying whole config_db
                tables_dict = {table_name: {} for table_name in operation['value']}
                config_db.update(tables_dict)
            elif not tokens[0]: # Not empty
                raise ValueError("Table name in patch cannot be empty")
            else:
                config_db[tokens[0]] = {}

        cropped_config_db = self.config_wrapper.crop_tables_without_yang(config_db)

        # valid if no tables dropped during cropping
        return len(cropped_config_db.keys()) == len(config_db.keys())

    def verify_same_json(self, expected, actual):
        # patch will be [] if no diff, [] evaluates to False
        return not jsonpatch.make_patch(expected, actual)

    def generate_patch(self, current, target):
        return jsonpatch.make_patch(current, target)

    def simulate_patch(self, patch, jsonconfig):
        return patch.apply(jsonconfig)

    def convert_config_db_patch_to_sonic_yang_patch(self, patch):
        if not(self.validate_config_db_patch_has_yang_models(patch)):
            raise ValueError(f"Given patch is not valid")

        current_config_db = self.config_wrapper.get_config_db_as_json()
        target_config_db = self.simulate_patch(patch, current_config_db)

        current_yang = self.config_wrapper.convert_config_db_to_sonic_yang(current_config_db)
        target_yang = self.config_wrapper.convert_config_db_to_sonic_yang(target_config_db)

        return self.generate_patch(current_yang, target_yang)

    def convert_sonic_yang_patch_to_config_db_patch(self, patch):
        current_yang = self.config_wrapper.get_sonic_yang_as_json()
        target_yang = self.simulate_patch(patch, current_yang)

        current_config_db = self.config_wrapper.convert_sonic_yang_to_config_db(current_yang)
        target_config_db = self.config_wrapper.convert_sonic_yang_to_config_db(target_yang)

        return self.generate_patch(current_config_db, target_config_db)

class OperationType(Enum):
    ADD = 1
    REMOVE = 2
    REPLACE = 3

class OperationWrapper:
    OP_KEYWORD = "op"
    PATH_KEYWORD = "path"
    VALUE_KEYWORD = "value"

    def create(self, operation_type, path, value=None):
        op_type = operation_type.name.lower()

        operation = {OperationWrapper.OP_KEYWORD: op_type, OperationWrapper.PATH_KEYWORD: path}

        if operation_type in [OperationType.ADD, OperationType.REPLACE]:
            operation[OperationWrapper.VALUE_KEYWORD] = value

        return operation

class PathAddressing:
    """
    Path refers to the 'path' in JsonPatch operations: https://tools.ietf.org/html/rfc6902
    The path corresponds to JsonPointer: https://tools.ietf.org/html/rfc6901

    All xpath operations in this class are only relevent to ConfigDb and the conversion to YANG xpath.
    It is not meant to support all the xpath functionalities, just the ones relevent to ConfigDb/YANG.
    """
    PATH_SEPARATOR = "/"
    XPATH_SEPARATOR = "/"

    def __init__(self, config_wrapper=None):
        self.config_wrapper = config_wrapper

    @staticmethod
    def get_path_tokens(path):
        return sonic_yang.SonicYang.configdb_path_split(path)

    @staticmethod
    def create_path(tokens):
        return sonic_yang.SonicYang.configdb_path_join(tokens)

    @staticmethod
    def get_xpath_tokens(xpath):
        return sonic_yang.SonicYang.xpath_split(xpath)

    def has_path(self, doc, path):
        return self.get_from_path(doc, path) is not None

    def get_from_path(self, doc, path):
        return JsonPointer(path).get(doc, default=None)

    def is_config_different(self, path, current, target):
        return self.get_from_path(current, path) != self.get_from_path(target, path)

    def _create_sonic_yang_with_loaded_models(self):
        return self.config_wrapper.create_sonic_yang_with_loaded_models()

    def find_ref_paths(self, paths, config, reload_config: bool = True):
        """
        Finds the paths referencing any line under the given 'path' within the given 'config'.
        Example:
          path: /PORT
          config:
            {
                "VLAN_MEMBER": {
                    "Vlan1000|Ethernet0": {},
                    "Vlan1000|Ethernet4": {}
                },
                "ACL_TABLE": {
                    "EVERFLOW": {
                        "ports": [
                            "Ethernet4"
                        ],
                    },
                    "EVERFLOWV6": {
                        "ports": [
                            "Ethernet4",
                            "Ethernet8"
                        ]
                    }
                },
                "PORT": {
                    "Ethernet0": {},
                    "Ethernet4": {},
                    "Ethernet8": {}
                }
            }
          return:
            /VLAN_MEMBER/Vlan1000|Ethernet0
            /VLAN_MEMBER/Vlan1000|Ethernet4
            /ACL_TABLE/EVERFLOW/ports/0
            /ACL_TABLE/EVERFLOW6/ports/0
            /ACL_TABLE/EVERFLOW6/ports/1
        """
        # TODO: Also fetch references by must statement (check similar statements)
        sy = self._create_sonic_yang_with_loaded_models()

        if reload_config:
            sy.loadData(config)

        # Force to be a list
        if not isinstance(paths, list):
            paths = [paths]

        ref_paths = []
        ref_paths_set = set()
        ref_xpaths = []

        # Iterate across all paths fetching references
        for path in paths:
            xpath = self.convert_path_to_xpath(path, config, sy)

            leaf_xpaths = self._get_inner_leaf_xpaths(xpath, sy)
            for xpath in leaf_xpaths:
                ref_xpaths.extend(sy.find_data_dependencies(xpath))

        # For each xpath, convert to configdb path
        for ref_xpath in ref_xpaths:
            ref_path = self.convert_xpath_to_path(ref_xpath, config, sy)
            if ref_path not in ref_paths_set:
                ref_paths.append(ref_path)
                ref_paths_set.add(ref_path)

        ref_paths.sort()
        return ref_paths

    def _get_inner_leaf_xpaths(self, xpath, sy):
        if xpath == "/": # Point to Root element which contains all xpaths
            nodes = sy.root.tree_for()
        else: # Otherwise get all nodes that match xpath
            nodes = sy.root.find_path(xpath).data()

        for node in nodes:
            for inner_node in node.tree_dfs():
                # TODO: leaflist also can be used as the 'path' argument in 'leafref' so add support to leaflist
                if self._is_leaf_node(inner_node):
                    yield inner_node.path()

    def _is_leaf_node(self, node):
        schema = node.schema()
        return ly.LYS_LEAF == schema.nodetype()

    def convert_path_to_xpath(self, path, config=None, sy=None):
        """
        Converts the given JsonPatch path (i.e. JsonPointer) to XPATH.
        Example:
          path: /VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode
          xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode
        """
        if sy is None:
            sy = self._create_sonic_yang_with_loaded_models()
        return sy.configdb_path_to_xpath(path, configdb=config)

    def convert_xpath_to_path(self, xpath, config=None, sy=None):
        """
        Converts the given XPATH to JsonPatch path (i.e. JsonPointer).
        Example:
          xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode
          path: /VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode
        """
        if sy is None:
            sy = self._create_sonic_yang_with_loaded_models()
        return sy.xpath_to_configdb_path(xpath, config)

    def configdb_sort_cmp(self, a, b):
        # Order first by number of backlinks
        cmp = a["backlinks"] - b["backlinks"]
        if cmp != 0:
            return cmp

        # Then order (in reverse!) by musts
        cmp = b["musts"] - a["musts"]
        if cmp != 0:
            return cmp

        # Finally, if we differ by number of separators, a lot of times the
        # one with fewer separators wins.  Hopefully the 'musts' will catch
        # this anyhow.
        cmp = a["nsep"] - b["nsep"]
        return cmp

    def configdb_sorted_keys_by_backlinks(self, configdb_path: str, configdb: dict, reverse: bool = False,
                                          configdb_relative: bool = False, sy=None):
        """
        Given a path and a config, iterates across all keys at the path location
        to look up the number of backlinks per key, then returns the keys sorted
        by backlinks in acending order by default (set reverse=True to use descending order)

        The configdb is only used to look up the keys at the given path, it is not
        loaded into the context.  The sort is not performed by actual references
        to the key in data, but rather the "potential" number of references based
        on the schema alone.

        If configdb_relative=True then we will use the provided configdb ptr
        directly instead of using the configdb_path parameter to find the proper
        position.
        """

        if sy is None and self.config_wrapper is not None:
            sy = self._create_sonic_yang_with_loaded_models()

        # Traverse configdb to find the right pointer
        ptr = configdb
        tokens = self.get_path_tokens(configdb_path)
        if not configdb_relative:
            for token in tokens:
                ptr = ptr[token]

        # Test cases expect non-sorted and config_wrapper isn't set.
        if self.config_wrapper is None:
            return [key for key in ptr]

        keys = []
        # Enumerate all keys and retrieve backlinks, store in a list of dictionaries for sorting
        for key in ptr:
            tokens.append(key)
            path = self.create_path(tokens)
            try:
                xpath = sy.configdb_path_to_xpath(path, schema_xpath=True)
            except KeyError:
                # Test cases use invalid tables, so we have to handle that even
                # though it shouldn't be possible in live code as tables without
                # yang are trimmed
                keys.append({
                            "key": key,
                            "backlinks": 0,
                            "musts": 0,
                            "nsep": 0
                            })
            else:
                keys.append({
                            "key": key,
                            "backlinks": len(sy.find_schema_dependencies(xpath, match_ancestors=True)),
                            "musts": sy.find_schema_must_count(xpath, match_ancestors=True),
                            "nsep": str(key).count("|")
                            })
            tokens.pop()

        # Sort list of keys by count
        keys = sorted(keys, key=cmp_to_key(self.configdb_sort_cmp), reverse=reverse)

        # Caller doesn't care about the count, just that the list of keys is ordered
        return [d['key'] for d in keys]

class TitledLogger(logger.Logger):
    def __init__(self, syslog_identifier, title, verbose, print_all_to_console):
        super().__init__(syslog_identifier)
        self._title = title
        if verbose:
            self.set_min_log_priority_debug()
        self.print_all_to_console = print_all_to_console

    def log(self, priority, msg, also_print_to_console=False):
        combined_msg = f"{self._title}: {msg}"
        super().log(priority, combined_msg, self.print_all_to_console or also_print_to_console)

class GenericUpdaterLogging:
    def __init__(self):
        self.set_verbose(False)

    def set_verbose(self, verbose):
        self._verbose = verbose

    def get_verbose(self):
        return self._verbose

    def get_logger(self, title, print_all_to_console=False):
        return TitledLogger(SYSLOG_IDENTIFIER, title, self._verbose, print_all_to_console)

genericUpdaterLogging = GenericUpdaterLogging()
