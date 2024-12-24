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

    def apply(self, config):
        return self.patch.apply(config)

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
            sy.loadData(config_db_as_json)

            sy.validate_data_tree()
            return True, None
        except sonic_yang.SonicYangException as ex:
            return False, ex

    def validate_config_db_config(self, config_db_as_json):
        sy = self.create_sonic_yang_with_loaded_models()

        # TODO: Move these validators to YANG models
        supplemental_yang_validators = [self.validate_bgp_peer_group,
                                        self.validate_lanes]

        try:
            tmp_config_db_as_json = copy.deepcopy(config_db_as_json)

            sy.loadData(tmp_config_db_as_json)

            sy.validate_data_tree()

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
            return method_to_call(jsonpatch_element)

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
            for ip in ip_range:
                if ip in visited:
                    return False, f"{ip} is duplicated in BGP_PEER_RANGE: {set([peer_group_name, visited[ip]])}"
                visited[ip] = peer_group_name

        return True, None

    def crop_tables_without_yang(self, config_db_as_json):
        sy = self.create_sonic_yang_with_loaded_models()

        sy.jIn = copy.deepcopy(config_db_as_json)

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

        return copy.copy(self.sonic_yang_with_loaded_models)

class DryRunConfigWrapper(ConfigWrapper):
    # This class will simulate all read/write operations to ConfigDB on a virtual storage unit.
    def __init__(self, initial_imitated_config_db=None, scope=multi_asic.DEFAULT_NAMESPACE):
        super().__init__(scope=scope)
        self.logger = genericUpdaterLogging.get_logger(title="** DryRun", print_all_to_console=True)
        self.imitated_config_db = copy.deepcopy(initial_imitated_config_db)

    def apply_change_to_config_db(self, change):
        self._init_imitated_config_db_if_none()
        self.logger.log_notice(f"Would apply {change}")
        self.imitated_config_db = change.apply(self.imitated_config_db)

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

    def get_path_tokens(self, path):
        return JsonPointer(path).parts

    def create_path(self, tokens):
        return JsonPointer.from_parts(tokens).path

    def has_path(self, doc, path):
        return self.get_from_path(doc, path) is not None

    def get_from_path(self, doc, path):
        return JsonPointer(path).get(doc, default=None)

    def is_config_different(self, path, current, target):
        return self.get_from_path(current, path) != self.get_from_path(target, path)

    def get_xpath_tokens(self, xpath):
        """
        Splits the given xpath into tokens by '/'.

        Example:
          xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode
          tokens: sonic-vlan:sonic-vlan, VLAN_MEMBER, VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8'], tagging_mode
        """
        if xpath == "":
            raise ValueError("xpath cannot be empty")

        if xpath == "/":
            return []

        idx = 0
        tokens = []
        while idx < len(xpath):
            end = self._get_xpath_token_end(idx+1, xpath)
            token = xpath[idx+1:end]
            tokens.append(token)
            idx = end

        return tokens

    def _get_xpath_token_end(self, start, xpath):
        idx = start
        while idx < len(xpath):
            if xpath[idx] == PathAddressing.XPATH_SEPARATOR:
                break
            elif xpath[idx] == "[":
                idx = self._get_xpath_predicate_end(idx, xpath)
            idx = idx+1

        return idx

    def _get_xpath_predicate_end(self, start, xpath):
        idx = start
        while idx < len(xpath):
            if xpath[idx] == "]":
                break
            elif xpath[idx] == "'":
                idx = self._get_xpath_single_quote_str_end(idx, xpath)
            elif xpath[idx] == '"':
                idx = self._get_xpath_double_quote_str_end(idx, xpath)

            idx = idx+1

        return idx

    def _get_xpath_single_quote_str_end(self, start, xpath):
        idx = start+1 # skip first single quote
        while idx < len(xpath):
            if xpath[idx] == "'":
                break
            # libyang implements XPATH 1.0 which does not escape single quotes
            # libyang src: https://netopeer.liberouter.org/doc/libyang/master/html/howtoxpath.html
            # XPATH 1.0 src: https://www.w3.org/TR/1999/REC-xpath-19991116/#NT-Literal
            idx = idx+1

        return idx

    def _get_xpath_double_quote_str_end(self, start, xpath):
        idx = start+1 # skip first single quote
        while idx < len(xpath):
            if xpath[idx] == '"':
                break
            # libyang implements XPATH 1.0 which does not escape double quotes
            # libyang src: https://netopeer.liberouter.org/doc/libyang/master/html/howtoxpath.html
            # XPATH 1.0 src: https://www.w3.org/TR/1999/REC-xpath-19991116/#NT-Literal
            idx = idx+1

        return idx

    def create_xpath(self, tokens):
        """
        Creates an xpath by combining the given tokens using '/'
        Example:
          tokens: module, container, list[key='value'], leaf
          xpath: /module/container/list[key='value']/leaf
        """
        if len(tokens) == 0:
            return "/"

        return f"{PathAddressing.XPATH_SEPARATOR}{PathAddressing.XPATH_SEPARATOR.join(str(t) for t in tokens)}"

    def _create_sonic_yang_with_loaded_models(self):
        return self.config_wrapper.create_sonic_yang_with_loaded_models()

    def find_ref_paths(self, path, config):
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
        return self._find_leafref_paths(path, config)

    def _find_leafref_paths(self, path, config):
        sy = self._create_sonic_yang_with_loaded_models()

        tmp_config = copy.deepcopy(config)

        sy.loadData(tmp_config)

        xpath = self.convert_path_to_xpath(path, config, sy)

        leaf_xpaths = self._get_inner_leaf_xpaths(xpath, sy)

        ref_xpaths = []
        for xpath in leaf_xpaths:
            ref_xpaths.extend(sy.find_data_dependencies(xpath))

        ref_paths = []
        ref_paths_set = set()
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

    def convert_path_to_xpath(self, path, config, sy):
        """
        Converts the given JsonPatch path (i.e. JsonPointer) to XPATH.
        Example:
          path: /VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode
          xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode
        """
        self.convert_xpath_to_path
        tokens = self.get_path_tokens(path)
        if len(tokens) == 0:
            return self.create_xpath(tokens)

        xpath_tokens = []
        table = tokens[0]

        cmap = sy.confDbYangMap[table]

        # getting the top level element <module>:<topLevelContainer>
        xpath_tokens.append(cmap['module']+":"+cmap['topLevelContainer'])

        xpath_tokens.extend(self._get_xpath_tokens_from_container(cmap['container'], 0, tokens, config))

        return self.create_xpath(xpath_tokens)

    def _get_xpath_tokens_from_container(self, model, token_index, path_tokens, config):
        token = path_tokens[token_index]
        xpath_tokens = [token]

        if len(path_tokens)-1 == token_index:
            return xpath_tokens

        # check if the configdb token is referring to a list
        list_model = self._get_list_model(model, token_index, path_tokens)
        if list_model:
            new_xpath_tokens = self._get_xpath_tokens_from_list(list_model, token_index+1, path_tokens, config[path_tokens[token_index]])
            xpath_tokens.extend(new_xpath_tokens)
            return xpath_tokens

        # check if it is targetting a child container
        child_container_model = self._get_model(model.get('container'), path_tokens[token_index+1])
        if child_container_model:
            new_xpath_tokens = self._get_xpath_tokens_from_container(child_container_model, token_index+1, path_tokens, config[path_tokens[token_index]])
            xpath_tokens.extend(new_xpath_tokens)
            return xpath_tokens

        new_xpath_tokens = self._get_xpath_tokens_from_leaf(model, token_index+1, path_tokens, config[path_tokens[token_index]])
        xpath_tokens.extend(new_xpath_tokens)

        return xpath_tokens

    def _get_xpath_tokens_from_list(self, model, token_index, path_tokens, config):
        list_name = model['@name']

        tableKey = path_tokens[token_index]
        listKeys = model['key']['@value']
        keyDict = self._extractKey(tableKey, listKeys)
        keyTokens = [f"[{key}='{keyDict[key]}']" for key in keyDict]
        item_token = f"{list_name}{''.join(keyTokens)}"

        xpath_tokens = [item_token]

        # if whole list-item is needed i.e. if in the path is not referencing child leaf items
        # Example:
        #   path: /VLAN/Vlan1000
        #   xpath: /sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']
        if len(path_tokens)-1 == token_index:
            return xpath_tokens

        type_1_list_model = self._get_type_1_list_model(model)
        if type_1_list_model:
            new_xpath_tokens = self._get_xpath_tokens_from_type_1_list(type_1_list_model, token_index+1, path_tokens, config[path_tokens[token_index]])
            xpath_tokens.extend(new_xpath_tokens)
            return xpath_tokens

        new_xpath_tokens = self._get_xpath_tokens_from_leaf(model, token_index+1, path_tokens,config[path_tokens[token_index]])
        xpath_tokens.extend(new_xpath_tokens)
        return xpath_tokens

    def _get_xpath_tokens_from_type_1_list(self, model, token_index, path_tokens, config):
        type_1_list_name = model['@name']
        keyName = model['key']['@value']
        value = path_tokens[token_index]
        keyToken = f"[{keyName}='{value}']"
        itemToken = f"{type_1_list_name}{keyToken}"

        return [itemToken]

    def _get_xpath_tokens_from_leaf(self, model, token_index, path_tokens, config):
        token = path_tokens[token_index]

        # checking all leaves
        leaf_model = self._get_model(model.get('leaf'), token)
        if leaf_model:
            return [token]

        # checking choice
        choices = model.get('choice')
        if choices:
            for choice in choices:
                cases = choice['case']
                for case in cases:
                    leaf_model = self._get_model(case.get('leaf'), token)
                    if leaf_model:
                        return [token]

        # checking leaf-list (i.e. arrays of string, number or bool)
        leaf_list_model = self._get_model(model.get('leaf-list'), token)
        if leaf_list_model:
            # if whole-list is to be returned, just return the token without checking the list items
            # Example:
            #   path: /VLAN/Vlan1000/dhcp_servers
            #   xpath: /sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']/dhcp_servers
            if len(path_tokens)-1 == token_index:
                return [token]
            list_config = config[token]
            value = list_config[int(path_tokens[token_index+1])]
            # To get a leaf-list instance with the value 'val'
            #   /module-name:container/leaf-list[.='val']
            # Source: Check examples in https://netopeer.liberouter.org/doc/libyang/master/html/howto_x_path.html
            return [f"{token}[.='{value}']"]

        # checking 'uses' statement
        if not isinstance(config[token], list): # leaf-list under uses is not supported yet in sonic_yang
            table = path_tokens[0]
            uses_leaf_model = self._get_uses_leaf_model(model, table, token)
            if uses_leaf_model:
                return [token]

        raise ValueError(f"Path token not found.\n  model: {model}\n  token_index: {token_index}\n  " + \
                         f"path_tokens: {path_tokens}\n  config: {config}")

    def _extractKey(self, tableKey, keys):
        keyList = keys.split()
        # get the value groups
        value = tableKey.split("|")
        # match lens
        if len(keyList) != len(value):
            raise ValueError("Value not found for {} in {}".format(keys, tableKey))
        # create the keyDict
        keyDict = dict()
        for i in range(len(keyList)):
            keyDict[keyList[i]] = value[i].strip()

        return keyDict

    def _get_list_model(self, model, token_index, path_tokens):
        parent_container_name = path_tokens[token_index]
        clist = model.get('list')
        # Container contains a single list, just return it
        # TODO: check if matching also by name is necessary
        if isinstance(clist, dict):
            return clist

        if isinstance(clist, list):
            configdb_values_str = path_tokens[token_index+1]
            # Format: "value1|value2|value|..."
            configdb_values = configdb_values_str.split("|")
            for list_model in clist:
                yang_keys_str = list_model['key']['@value']
                # Format: "key1 key2 key3 ..."
                yang_keys = yang_keys_str.split()
                # if same number of values and keys, this is the intended list-model
                # TODO: Match also on types and not only the length of the keys/values
                if len(yang_keys) == len(configdb_values):
                    return list_model
            raise GenericConfigUpdaterError(f"Container {parent_container_name} has multiple lists, "
                                            f"but none of them match the config_db value {configdb_values_str}")

        return None

    def _get_type_1_list_model(self, model):
        list_name = model['@name']
        if list_name not in sonic_yang_ext.Type_1_list_maps_model:
            return None

        # Type 1 list is expected to have a single inner list model.
        # No need to check if it is a dictionary of list models.
        return model.get('list')

    def convert_xpath_to_path(self, xpath, config, sy):
        """
        Converts the given XPATH to JsonPatch path (i.e. JsonPointer).
        Example:
          xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode
          path: /VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode
        """
        tokens = self.get_xpath_tokens(xpath)
        if len(tokens) == 0:
            return self.create_path([])

        if len(tokens) == 1:
            raise GenericConfigUpdaterError("xpath cannot be just the module-name, there is no mapping to path")

        table = tokens[1]
        cmap = sy.confDbYangMap[table]

        path_tokens = self._get_path_tokens_from_container(cmap['container'], 1, tokens, config)
        return self.create_path(path_tokens)

    def _get_path_tokens_from_container(self, model, token_index, xpath_tokens, config):
        token = xpath_tokens[token_index]
        path_tokens = [token]

        if len(xpath_tokens)-1 == token_index:
            return path_tokens

        # check child list
        list_name = xpath_tokens[token_index+1].split("[")[0]
        list_model = self._get_model(model.get('list'), list_name)
        if list_model:
            new_path_tokens = self._get_path_tokens_from_list(list_model, token_index+1, xpath_tokens, config[token])
            path_tokens.extend(new_path_tokens)
            return path_tokens

        container_name = xpath_tokens[token_index+1]
        container_model = self._get_model(model.get('container'), container_name)
        if container_model:
            new_path_tokens = self._get_path_tokens_from_container(container_model, token_index+1, xpath_tokens, config[token])
            path_tokens.extend(new_path_tokens)
            return path_tokens

        new_path_tokens = self._get_path_tokens_from_leaf(model, token_index+1, xpath_tokens, config[token])
        path_tokens.extend(new_path_tokens)

        return path_tokens

    def _get_path_tokens_from_list(self, model, token_index, xpath_tokens, config):
        token = xpath_tokens[token_index]
        key_dict = self._extract_key_dict(token)

        # If no keys specified return empty tokens, as we are already inside the correct table.
        # Also note that the list name in SonicYang has no correspondence in ConfigDb and is ignored.
        # Example where VLAN_MEMBER_LIST has no specific key/value:
        #   xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST
        #   path: /VLAN_MEMBER
        if not(key_dict):
            return []

        listKeys = model['key']['@value']
        key_list = listKeys.split()

        if len(key_list) != len(key_dict):
            raise GenericConfigUpdaterError(f"Keys in configDb not matching keys in SonicYang. ConfigDb keys: {key_dict.keys()}. SonicYang keys: {key_list}")

        values = [key_dict[k] for k in key_list]
        path_token = '|'.join(values)
        path_tokens = [path_token]

        if len(xpath_tokens)-1 == token_index:
            return path_tokens

        next_token = xpath_tokens[token_index+1]
        # if the target node is a key, then it does not have a correspondene to path.
        # Just return the current 'key1|key2|..' token as it already refers to the keys
        # Example where the target node is 'name' which is a key in VLAN_MEMBER_LIST:
        #   xpath: /sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/name
        #   path: /VLAN_MEMBER/Vlan1000|Ethernet8
        if next_token in key_dict:
            return path_tokens

        type_1_list_model = self._get_type_1_list_model(model)
        if type_1_list_model:
            new_path_tokens = self._get_path_tokens_from_type_1_list(type_1_list_model, token_index+1, xpath_tokens, config[path_token])
            path_tokens.extend(new_path_tokens)
            return path_tokens

        new_path_tokens = self._get_path_tokens_from_leaf(model, token_index+1, xpath_tokens, config[path_token])
        path_tokens.extend(new_path_tokens)
        return path_tokens

    def _get_path_tokens_from_type_1_list(self, model, token_index, xpath_tokens, config):
        type_1_inner_list_name = model['@name']

        token = xpath_tokens[token_index]
        list_tokens = token.split("[", 1) # split once on the first '[', first element will be the inner list name
        inner_list_name = list_tokens[0]

        if type_1_inner_list_name != inner_list_name:
            raise GenericConfigUpdaterError(f"Type 1 inner list name '{type_1_inner_list_name}' does match xpath inner list name '{inner_list_name}'.")

        key_dict = self._extract_key_dict(token)

        # If no keys specified return empty tokens, as we are already inside the correct table.
        # Also note that the type 1 inner list name in SonicYang has no correspondence in ConfigDb and is ignored.
        # Example where VLAN_MEMBER_LIST has no specific key/value:
        #   xpath: /sonic-dot1p-tc-map:sonic-dot1p-tc-map/DOT1P_TO_TC_MAP/DOT1P_TO_TC_MAP_LIST[name='Dot1p_to_tc_map1']/DOT1P_TO_TC_MAP
        #   path: /DOT1P_TO_TC_MAP/Dot1p_to_tc_map1
        if not(key_dict):
            return []

        if len(key_dict) > 1:
            raise GenericConfigUpdaterError(f"Type 1 inner list should have only 1 key in xpath, {len(key_dict)} specified. Key dictionary: {key_dict}")

        keyName = next(iter(key_dict.keys()))
        value = key_dict[keyName]

        path_tokens = [value]

        # If this is the last xpath token, return the path tokens we have built so far, no need for futher checks
        # Example:
        #   xpath: /sonic-dot1p-tc-map:sonic-dot1p-tc-map/DOT1P_TO_TC_MAP/DOT1P_TO_TC_MAP_LIST[name='Dot1p_to_tc_map1']/DOT1P_TO_TC_MAP[dot1p='2']
        #   path: /DOT1P_TO_TC_MAP/Dot1p_to_tc_map1/2
        if token_index+1 >= len(xpath_tokens):
            return path_tokens

        # Checking if the next_token is actually a child leaf of the inner type 1 list, for which case
        # just ignore the token, and return the already created ConfigDb path pointing to the whole object
        # Example where the leaf specified is the key:
        #   xpath: /sonic-dot1p-tc-map:sonic-dot1p-tc-map/DOT1P_TO_TC_MAP/DOT1P_TO_TC_MAP_LIST[name='Dot1p_to_tc_map1']/DOT1P_TO_TC_MAP[dot1p='2']/dot1p
        #   path: /DOT1P_TO_TC_MAP/Dot1p_to_tc_map1/2
        # Example where the leaf specified is not the key:
        #   xpath: /sonic-dot1p-tc-map:sonic-dot1p-tc-map/DOT1P_TO_TC_MAP/DOT1P_TO_TC_MAP_LIST[name='Dot1p_to_tc_map1']/DOT1P_TO_TC_MAP[dot1p='2']/tc
        #   path: /DOT1P_TO_TC_MAP/Dot1p_to_tc_map1/2
        next_token = xpath_tokens[token_index+1]
        leaf_model = self._get_model(model.get('leaf'), next_token)
        if leaf_model:
            return path_tokens

        raise GenericConfigUpdaterError(f"Type 1 inner list '{type_1_inner_list_name}' does not have a child leaf named '{next_token}'")

    def _get_path_tokens_from_leaf(self, model, token_index, xpath_tokens, config):
        token = xpath_tokens[token_index]

        # checking all leaves
        leaf_model = self._get_model(model.get('leaf'), token)
        if leaf_model:
            return [token]

        # checking choices
        choices = model.get('choice')
        if choices:
            for choice in choices:
                cases = choice['case']
                for case in cases:
                    leaf_model = self._get_model(case.get('leaf'), token)
                    if leaf_model:
                        return [token]

        # checking leaf-list
        leaf_list_tokens = token.split("[", 1) # split once on the first '[', a regex is used later to fetch keys/values
        leaf_list_name = leaf_list_tokens[0]
        leaf_list_model = self._get_model(model.get('leaf-list'), leaf_list_name)
        if leaf_list_model:
            # if whole-list is to be returned, just return the list-name without checking the list items
            # Example:
            #   xpath: /sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']/dhcp_servers
            #   path: /VLAN/Vlan1000/dhcp_servers
            if len(leaf_list_tokens) == 1:
                return [leaf_list_name]
            leaf_list_pattern = "^[^\[]+(?:\[\.='([^']*)'\])?$"
            leaf_list_regex = re.compile(leaf_list_pattern)
            match = leaf_list_regex.match(token)
            # leaf_list_name = match.group(1)
            leaf_list_value = match.group(1)
            list_config = config[leaf_list_name]
            # Workaround for those fields who is defined as leaf-list in YANG model but have string value in config DB
            # No need to lookup the item index in ConfigDb since the list is represented as a string, return path to string immediately
            # Example:
            #   xpath: /sonic-buffer-port-egress-profile-list:sonic-buffer-port-egress-profile-list/BUFFER_PORT_EGRESS_PROFILE_LIST/BUFFER_PORT_EGRESS_PROFILE_LIST_LIST[port='Ethernet9']/profile_list[.='egress_lossy_profile']
            #   path: /BUFFER_PORT_EGRESS_PROFILE_LIST/Ethernet9/profile_list
            if isinstance(list_config, str):
                return [leaf_list_name]

            if not isinstance(list_config, list):
                raise ValueError(f"list_config is expected to be of type list or string. Found {type(list_config)}.\n  " + \
                                 f"model: {model}\n  token_index: {token_index}\n  " + \
                                 f"xpath_tokens: {xpath_tokens}\n  config: {config}")

            list_idx = list_config.index(leaf_list_value)
            return [leaf_list_name, list_idx]

        # checking 'uses' statement
        if not isinstance(config[leaf_list_name], list):  # leaf-list under uses is not supported yet in sonic_yang
            table = xpath_tokens[1]
            uses_leaf_model = self._get_uses_leaf_model(model, table, token)
            if uses_leaf_model:
                return [token]

        raise ValueError(f"Xpath token not found.\n  model: {model}\n  token_index: {token_index}\n  " + \
                         f"xpath_tokens: {xpath_tokens}\n  config: {config}")

    def _extract_key_dict(self, list_token):
        # Example: VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']
        # the groups would be ('VLAN_MEMBER'), ("[name='Vlan1000'][port='Ethernet8']")
        table_keys_pattern = "^([^\[]+)(.*)$"
        text = list_token
        table_keys_regex = re.compile(table_keys_pattern)
        match = table_keys_regex.match(text)
        # list_name = match.group(1)
        all_key_value = match.group(2)

        # Example: [name='Vlan1000'][port='Ethernet8']
        # the findall groups would be ('name', 'Vlan1000'), ('port', 'Ethernet8')
        key_value_pattern = "\[([^=]+)='([^']*)'\]"
        matches = re.findall(key_value_pattern, all_key_value)
        key_dict = {}
        for item in matches:
            key = item[0]
            value = item[1]
            key_dict[key] = value

        return key_dict

    def _get_model(self, model, name):
        if isinstance(model, dict) and model['@name'] == name:
            return model
        if isinstance(model, list):
            for submodel in model:
                if submodel['@name'] == name:
                    return submodel

        return None

    def _get_uses_leaf_model(self, model, table, token):
        """
          Getting leaf model in uses model matching the given token.
        """
        uses_s = model.get('uses')
        if not uses_s:
            return None

        # a model can be a single dict or a list of dictionaries, unify to a list of dictionaries
        if not isinstance(uses_s, list):
            uses_s = [uses_s]

        sy = self._create_sonic_yang_with_loaded_models()
        # find yang module for current table
        table_module = sy.confDbYangMap[table]['yangModule']
        # uses Example: "@name": "bgpcmn:sonic-bgp-cmn"
        for uses in uses_s:
            if not isinstance(uses, dict):
                raise GenericConfigUpdaterError(f"'uses' is expected to be a dictionary found '{type(uses)}'.\n" \
                                                f"  uses: {uses}\n  model: {model}\n  table: {table}\n  token: {token}")

            # Assume ':'  means reference to another module
            if ':' in uses['@name']:
                name_parts = uses['@name'].split(':')
                prefix = name_parts[0].strip()
                uses_module_name = sy._findYangModuleFromPrefix(prefix, table_module)
                grouping = name_parts[-1].strip()
            else:
                uses_module_name = table_module['@name']
                grouping = uses['@name']

            leafs = sy.preProcessedYang['grouping'][uses_module_name][grouping]

            leaf_model = self._get_model(leafs, token)
            if leaf_model:
                return leaf_model

        return None

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
