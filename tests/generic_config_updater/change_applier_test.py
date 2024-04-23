import copy
import json
import jsondiff
import os
import unittest
from collections import defaultdict
from unittest.mock import patch, Mock, call

import generic_config_updater.change_applier
import generic_config_updater.services_validator
import generic_config_updater.gu_common

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_FILE =  os.path.join(SCRIPT_DIR, "files", "change_applier_test.data.json")
CONF_FILE =  os.path.join(SCRIPT_DIR, "files", "change_applier_test.conf.json")
#
# Datafile is structured as 
# "running_config": {....}
# "json_changes": [ 
#        {
#         "notes": <short note on this change for dev>,
#         "update": { <tbl>: {<key>: {<new data>}, ...}...},
#         "remove": { <tbl>: { <key>: {}, ..}, ...},
#         "services_to_validate": [ <service name>, ...]
#        },
#        ...
#   ]
#
# The json_changes is read into global json_changes
# The ChangeApplier.apply is called with each change
# The mocked JsonChange.apply applies this diff on given config
# The ChangeApplier.apply calls set_entry to update redis
# But we mock set_entry, and that instead:
#       remove the corresponding changes from json_changes.
#       Updates the global running_config
# 
# At the end of application of all changes, expect global json-changes to
# be empty, which assures that set_entry is called for all expected keys.
# The global running config would reflect the final config
#
# The changes are written in such a way, upon the last change, the config
# will be same as the original config that we started with or as read from
# data file. 
#
# So compare global running_config with read_data for running config
# from the file.
# This compares the integrity of final o/p

# Data read from file
read_data = {}

# Keep a copy of running_config before calling apply
# This is used by service_validate call to verify the args
# Args from change applier: (<config before change>  <config after change>
#                               <affected keys>
start_running_config = {}

# The mock_set_entry (otherwise redis update) reflects the final config
# service_validate calls will verify <config after change > against this
#
running_config = {}

# Copy of changes read. Used by mock JsonChange.apply
# Cleared by mocked set_entry
json_changes = {}

# The index into list of i/p json changes for mock code to use
json_change_index = 0

DB_HANDLE = "config_db"

def debug_print(msg):
    print(msg)


# Mimics os.system call for sonic-cfggen -d --print-data > filename
def subprocess_Popen_cfggen(cmd, *args, **kwargs):
    global running_config

    # Extract file name from kwargs if 'stdout' is a file object
    stdout = kwargs.get('stdout')
    if hasattr(stdout, 'name'):
        fname = stdout.name
    else:
        raise ValueError("stdout is not a file")

    # Write the running configuration to the file specified in stdout
    with open(fname, "w") as s:
        json.dump(running_config, s, indent=4)
    
    class MockPopen:
        def __init__(self):
            self.returncode = 0  # Simulate successful command execution

        def communicate(self):
            return "", ""  # Simulate empty stdout and stderr

    return MockPopen()


# mimics config_db.set_entry
#
def set_entry(config_db, tbl, key, data):
    global running_config, json_changes, json_change_index

    assert config_db == DB_HANDLE
    debug_print("set_entry: {} {} {}".format(tbl, key, str(data)))

    json_change = json_changes[json_change_index]
    change_data = json_change["update"] if data != None else json_change["remove"]

    assert tbl in change_data
    assert key in change_data[tbl]

    if data != None:
        if tbl not in running_config:
            running_config[tbl] = {}
        running_config[tbl][key] = data
    else:
        assert tbl in running_config
        assert key in running_config[tbl]
        running_config[tbl].pop(key)
        if not running_config[tbl]:
            running_config.pop(tbl)

    change_data[tbl].pop(key)
    if not change_data[tbl]:
        change_data.pop(tbl)


# mimics JsonChange.apply
#
class mock_obj:
    def apply(self, config):
        json_change = json_changes[json_change_index]

        update = copy.deepcopy(json_change["update"])
        for tbl in update:
            if tbl not in config:
                config[tbl] = {}
            for key in update[tbl]:
                debug_print("apply: tbl={} key={} ".format(tbl, key))
                if key in config[tbl]:
                    config[tbl][key].update(update[tbl][key])
                else:
                    config[tbl][key] = update[tbl][key]

        remove = json_change["remove"]
        for tbl in remove:
            if tbl in config:
                for key in remove[tbl]:
                    config[tbl].pop(key, None)
                    debug_print("apply: popped tbl={} key={}".format(tbl, key))
                if not config[tbl]:
                    config.pop(tbl, None)
                    debug_print("apply: popped EMPTY tbl={}".format(tbl))
        return config


# Test validators
#
def system_health(old_cfg, new_cfg, keys):
    debug_print("system_health called")
    svc_name = "system_health"
    if old_cfg != new_cfg:
        debug_print("system_health: diff={}".format(str(
            jsondiff.diff(old_cfg, new_cfg))))
        assert False, "No change expected"
    svcs = json_changes[json_change_index].get("services_validated", None)
    if svcs != None:
        assert svc_name in svcs
        svcs.remove(svc_name)
    return True


def _validate_keys(keys):
    # validate keys against original change as read from data file
    #
    change = read_data["json_changes"][json_change_index]
    change_data = copy.deepcopy(change["update"])
    change_data.update(change["remove"])

    for tbl in set(change_data.keys()).union(set(keys.keys())):
        assert tbl in change_data
        assert tbl in keys
        chg_tbl = change_data[tbl]
        keys_tbl = keys[tbl]
        for key in set(chg_tbl.keys()).union(set(keys_tbl.keys())):
            assert key in chg_tbl
            assert key in keys_tbl

        
def _validate_svc(svc_name, old_cfg, new_cfg, keys):
    if old_cfg != start_running_config:
        debug_print("validate svc {}: old diff={}".format(svc_name, str(
            jsondiff.diff(old_cfg, start_running_config))))
        assert False, "_validate_svc: old config mismatch"

    if new_cfg != running_config:
        debug_print("validate svc {}: new diff={}".format(svc_name, str(
            jsondiff.diff(new_cfg, running_config))))
        assert False, "_validate_svc: running config mismatch"

    _validate_keys(keys)

    # None provides a chance for test data to skip services_validated
    # verification
    svcs = json_changes[json_change_index].get("services_validated", None)
    if svcs != None:
        assert svc_name in svcs
        svcs.remove(svc_name)


def acl_validate(old_cfg, new_cfg, keys):
    debug_print("acl_validate called")
    _validate_svc("acl_validate", old_cfg, new_cfg, keys)
    return True


def vlan_validate(old_cfg, new_cfg, keys):
    debug_print("vlan_validate called")
    _validate_svc("vlan_validate", old_cfg, new_cfg, keys)
    return True


class TestChangeApplier(unittest.TestCase):

    @patch("generic_config_updater.change_applier.subprocess.Popen")
    @patch("generic_config_updater.change_applier.get_config_db")
    @patch("generic_config_updater.change_applier.set_config")
    def test_change_apply(self, mock_set, mock_db, mock_subprocess_Popen):
        global read_data, running_config, json_changes, json_change_index
        global start_running_config

        mock_subprocess_Popen.side_effect = subprocess_Popen_cfggen
        mock_db.return_value = DB_HANDLE
        mock_set.side_effect = set_entry

        with open(DATA_FILE, "r") as s:
            read_data = json.load(s)

        running_config = copy.deepcopy(read_data["running_data"])
        json_changes = copy.deepcopy(read_data["json_changes"])

        generic_config_updater.change_applier.UPDATER_CONF_FILE = CONF_FILE
        generic_config_updater.change_applier.set_verbose(True)
        generic_config_updater.services_validator.set_verbose(True)
        
        applier = generic_config_updater.change_applier.ChangeApplier()
        debug_print("invoked applier")

        for i in range(len(json_changes)):
            json_change_index = i

            # Take copy for comparison
            start_running_config = copy.deepcopy(running_config)
            
            debug_print("main: json_change_index={}".format(json_change_index))

            applier.apply(mock_obj())

            debug_print(f"Testing json_change {json_change_index}")

            debug_print("Checking: index={} update:{} remove:{} svcs:{}".format(i,
                json.dumps(json_changes[i]["update"])[0:20],
                json.dumps(json_changes[i]["remove"])[0:20],
                json.dumps(json_changes[i].get("services_validated", []))[0:20]))
            assert not json_changes[i]["update"]
            assert not json_changes[i]["remove"]
            assert not json_changes[i].get("services_validated", [])
            debug_print(f"----------------------------- DONE {i} ---------------------------------")

        debug_print("All changes applied & tested")

        # Test data is set up in such a way the multiple changes
        # finally brings it back to original config.
        #
        if read_data["running_data"] != running_config:
            debug_print("final config mismatch: {}".format(str(
                jsondiff.diff(read_data["running_data"], running_config))))

        assert read_data["running_data"] == running_config

        debug_print("all good for applier")


class TestDryRunChangeApplier(unittest.TestCase):
    def test_apply__calls_apply_change_to_config_db(self):
        # Arrange
        change = Mock()
        config_wrapper = Mock()
        applier = generic_config_updater.change_applier.DryRunChangeApplier(config_wrapper)

        # Act
        applier.apply(change)
        applier.remove_backend_tables_from_config(change)

        # Assert
        applier.config_wrapper.apply_change_to_config_db.assert_has_calls([call(change)])

