import jsonpatch
import copy
from jsonpointer import JsonPointer

from sonic_py_common import device_info
from generic_config_updater.generic_updater import GenericUpdater, ConfigFormat
from generic_config_updater.gu_common import EmptyTableError, genericUpdaterLogging

class ValidatedConfigDBConnector(object):
    
    def __init__(self, config_db_connector):
        self.connector = config_db_connector
        self.yang_enabled = device_info.is_yang_config_validation_enabled(self.connector)

    def __getattr__(self, name):
        if self.yang_enabled:
            if name == "set_entry":
                return self.validated_set_entry
            if name == "delete_table":
                return self.validated_delete_table
            if name == "mod_entry":
                return self.validated_mod_entry
        return self.connector.__getattribute__(name)

    def stringify_value(self, value):
        if isinstance(value, dict):
            value = {str(k):str(v) for k, v in value.items()}
        else:
            value = str(value)
        return value

    def make_path_value_jsonpatch_compatible(self, table, key, value):
        if type(key) == tuple:
            path = JsonPointer.from_parts([table, '|'.join(key)]).path
        elif type(key) == list:
            path = JsonPointer.from_parts([table, *key]).path
        else:
            path = JsonPointer.from_parts([table, key]).path
        if value == {"NULL" : "NULL"}:
            value = {}
        else:
            value = self.stringify_value(value)
        return path, value

    def create_gcu_patch(self, op, table, key=None, value=None, mod_entry=False):
        gcu_json_input = []
        """Add patch element to create new table if necessary, as GCU is unable to add to nonexistent table"""
        if op == "add" and not self.get_table(table):
            gcu_json = {"op": "{}".format(op),
                        "path": "/{}".format(table),
                        "value": {}}
            gcu_json_input.append(gcu_json)

        """Add patch element to create ConfigDB path if necessary, as GCU is unable to add to a nonexistent path"""
        if op == "add" and not self.get_entry(table, key):
            if type(key) == tuple: 
                path = JsonPointer.from_parts([table, '|'.join(key)]).path
            else:
                path = JsonPointer.from_parts([table, key]).path 
            gcu_json = {"op": "{}".format(op),
                        "path": "{}".format(path),
                        "value": {}}
            gcu_json_input.append(gcu_json)
         
        def add_patch_entry():
            if key: 
                patch_path, patch_value = self.make_path_value_jsonpatch_compatible(table, key, value)
            else:  
                patch_path = "/{}".format(table)
      
            gcu_json = {"op": "{}".format(op),
                        "path": "{}".format(patch_path)}
            if op == "add":
                gcu_json["value"] = patch_value

            gcu_json_input.append(gcu_json)
        
        """mod_entry makes path more granular so that preexisting fields in db are not removed"""
        if mod_entry:
            key_start = key
            value_copy = copy.deepcopy(value)
            for key_end, cleaned_value in value_copy.items():
                key = [key_start, key_end]
                value = cleaned_value
                add_patch_entry()
        else:
            add_patch_entry()

        gcu_patch = jsonpatch.JsonPatch(gcu_json_input)
        return gcu_patch

    def apply_patch(self, gcu_patch, table):
        format = ConfigFormat.CONFIGDB.name
        config_format = ConfigFormat[format.upper()]

        try:
            # Because all writes to ConfigDB through ValidatedConfigDBConnector are simple and don't require sorting, we set sort=False to skip sorting and improve performance
            GenericUpdater().apply_patch(patch=gcu_patch, config_format=config_format, verbose=False, dry_run=False, ignore_non_yang_tables=False, ignore_paths=None, sort=False)
        except EmptyTableError:
            self.validated_delete_table(table)

    def validated_delete_table(self, table):
        gcu_patch = self.create_gcu_patch("remove", table)
        format = ConfigFormat.CONFIGDB.name
        config_format = ConfigFormat[format.upper()]
        try:
            GenericUpdater().apply_patch(patch=gcu_patch, config_format=config_format, verbose=False, dry_run=False, ignore_non_yang_tables=False, ignore_paths=None, sort=False)
        except ValueError as e:
            logger = genericUpdaterLogging.get_logger(title="Patch Applier", print_all_to_console=True)
            logger.log_notice("Unable to remove entry, as doing so will result in invalid config. Error: {}".format(e))

    def validated_mod_entry(self, table, key, value):
        if isinstance(value, dict) and len(value) == 1 and list(value.values())[0] == "":
            op = "remove"        
        elif value is not None:
            op = "add"
        else:
            op = "remove"

        gcu_patch = self.create_gcu_patch(op, table, key, value, mod_entry=True)
        self.apply_patch(gcu_patch, table)

    def validated_set_entry(self, table, key, value):
        if isinstance(value, dict) and len(value) == 1 and list(value.values())[0] == "":
            op = "remove"        
        elif value is not None:
            op = "add"
        else:
            op = "remove"

        gcu_patch = self.create_gcu_patch(op, table, key, value)
        self.apply_patch(gcu_patch, table)
