import copy
import json
import jsondiff
import jsonpatch
import os
import unittest
from collections import defaultdict
from unittest.mock import patch, Mock, call

import generic_config_updater.change_applier
import generic_config_updater.generic_updater as gu
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

# Mimics os.system call for `sonic-cfggen -d --print-data` output
def subprocess_Popen_cfggen(cmd, *args, **kwargs):
    global running_config

    stdout = kwargs.get('stdout', None)

    if stdout is None:
        output = json.dumps(running_config, indent=4)
    elif isinstance(stdout, int) and stdout == -1:
        output = json.dumps(running_config, indent=4)
    else:
        raise ValueError("stdout must be set to subprocess.PIPE or omitted for capturing output")

    class MockPopen:
        def __init__(self):
            self.returncode = 0

        def communicate(self):
            return output.encode(), "".encode()

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
    def apply(self, config, in_place):
        config = copy.deepcopy(config)
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

    @patch("generic_config_updater.gu_common.subprocess.Popen")
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

        generic_config_updater.change_applier.ChangeApplier.updater_conf = None
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

            current_config = copy.deepcopy(start_running_config)
            current_config = applier.apply(current_config, mock_obj())

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
        current_config = copy.deepcopy(running_config)
        current_config = applier.apply(current_config, change)
        current_config = applier.remove_backend_tables_from_config(current_config)

        # Assert
        applier.config_wrapper.apply_change_to_config_db.assert_called()


class TestDryRunChangeApplierRestartServices(unittest.TestCase):
    @patch("generic_config_updater.services_validator._service_restart")
    def test_restart_services__restarts_nothing(self, mock_restart):
        applier = generic_config_updater.change_applier.DryRunChangeApplier(Mock())
        assert applier.restart_services()
        mock_restart.assert_not_called()


class TestChangeApplierRestartServices(unittest.TestCase):
    CONF = {
        "tables": {
            "SNMP": {"restart_on_change": [{"units": ["snmp"], "host_only": True}]},
            "SNMP_COMMUNITY": {"restart_on_change": [{"units": ["snmp"], "host_only": True}]},
            "PORT": {"restart_on_change": [{"fields": ["speed"], "modified_only": True, "units": ["telemetry"]}]},
            "SYSLOG_SERVER": {"restart_on_change": [{"units": ["rsyslog-config"], "reset_failed": ["rsyslog"]}]},
            "DEVICE_METADATA": {
                "restart_on_change": [
                    {"fields": ["docker_routing_config_mode"], "units": ["bgp"]},
                    {"fields": ["synchronous_mode"], "defaults": {"synchronous_mode": "enable"},
                     "units": ["swss"], "reset_failed": ["syncd"], "per_asic": True},
                ],
            },
            "VLAN": {"services_to_validate": ["vlan-service"]},
        }
    }
    OLD = {
        "SNMP": {"LOCATION": {"Location": "lab"}},
        "SNMP_COMMUNITY": {"public": {"TYPE": "RO"}},
        "DEVICE_METADATA": {"localhost": {"hostname": "sw1"}},
        "VLAN": {"Vlan100": {"vlanid": "100"}},
    }

    def setUp(self):
        mod = "generic_config_updater."
        for target, attr, kwargs in [
            (mod + "change_applier.get_config_db", "get_db", {}),
            (mod + "services_validator._service_restart", "restart", {"return_value": True}),
            (mod + "services_validator.command_wrapper", "command", {"return_value": 0}),
        ]:
            p = patch(target, **kwargs)
            setattr(self, attr, p.start())
            self.addCleanup(p.stop)
        p = patch.object(generic_config_updater.change_applier.ChangeApplier, "updater_conf", self.CONF)
        p.start()
        self.addCleanup(p.stop)
        self.applier = generic_config_updater.change_applier.ChangeApplier()

    def updated(self, **tables):
        upd = copy.deepcopy(self.OLD)
        for tbl, data in tables.items():
            if data is None:
                upd.pop(tbl, None)
            else:
                upd[tbl] = data
        return upd

    def restart_after(self, *changes, applier=None):
        applier = applier or self.applier
        for old, upd in changes:
            applier._collect_restarts(old, upd)
        return applier.restart_services()

    def test_unchanged__no_restart(self):
        assert self.restart_after((self.OLD, copy.deepcopy(self.OLD)))
        self.restart.assert_not_called()
        self.command.assert_not_called()

    def test_unrelated_table__no_restart(self):
        assert self.restart_after((self.OLD, self.updated(VLAN={})))
        self.restart.assert_not_called()

    def test_tables_sharing_a_unit__one_restart(self):
        upd = self.updated(SNMP={"LOCATION": {"Location": "dc"}}, SNMP_COMMUNITY={"private": {"TYPE": "RW"}})
        assert self.restart_after((self.OLD, upd))
        self.restart.assert_called_once_with("snmp")
        self.command.assert_called_once_with(["systemctl", "reset-failed", "snmp"])

    def test_table_added_or_removed__restart(self):
        added = self.updated(SNMP={"LOCATION": {"Location": "lab"}, "CONTACT": {"Contact": "noc"}})
        for upd in (self.updated(SNMP=None), added):
            self.restart.reset_mock()
            assert self.restart_after((self.OLD, upd))
            self.restart.assert_called_once_with("snmp")
        self.restart.reset_mock()
        old = self.updated(SNMP_COMMUNITY=None)
        assert self.restart_after((old, self.OLD))
        self.restart.assert_called_once_with("snmp")

    def test_field_rule__other_field__no_restart(self):
        upd = self.updated(DEVICE_METADATA={"localhost": {"hostname": "sw2"}})
        assert self.restart_after((self.OLD, upd))
        self.restart.assert_not_called()

    def test_field_rule__listed_field__restart(self):
        for meta in ({"hostname": "sw1", "docker_routing_config_mode": "split"},
                     {"hostname": "sw1"},
                     {}):
            old = self.updated(DEVICE_METADATA={"localhost": {"hostname": "sw1",
                                                              "docker_routing_config_mode": "unified"}})
            upd = self.updated(DEVICE_METADATA={"localhost": meta} if meta else None)
            self.restart.reset_mock()
            assert self.restart_after((old, upd))
            self.restart.assert_called_once_with("bgp")

    def test_each_unit_restarted_once_in_order(self):
        upd = self.updated(SNMP={}, DEVICE_METADATA={"localhost": {"docker_routing_config_mode": "split"}})
        assert self.restart_after((self.OLD, upd))
        assert self.restart.call_args_list == [call("bgp"), call("snmp")]

    def test_disabled_feature__no_restart(self):
        for state in ("disabled", "always_disabled"):
            upd = self.updated(SNMP={}, FEATURE={"snmp": {"state": state}})
            assert self.restart_after((self.OLD, upd))
        self.restart.assert_not_called()
        self.command.assert_not_called()
        upd = self.updated(SNMP={}, FEATURE={"snmp": {"state": "enabled"}})
        assert self.restart_after((self.OLD, upd))
        self.restart.assert_called_once_with("snmp")

    def test_restart_failure__returns_false_and_restarts_the_rest(self):
        self.restart.side_effect = lambda unit: unit != "bgp"
        upd = self.updated(SNMP={}, DEVICE_METADATA={"localhost": {"docker_routing_config_mode": "split"}})
        assert not self.restart_after((self.OLD, upd))
        assert self.restart.call_args_list == [call("bgp"), call("snmp")]

    def test_namespace_scope__skips_host_only_rules(self):
        applier = generic_config_updater.change_applier.ChangeApplier(scope="asic0")
        assert self.restart_after((self.OLD, self.updated(SNMP={})), applier=applier)
        self.restart.assert_not_called()
        upd = self.updated(SNMP={}, DEVICE_METADATA={"localhost": {"docker_routing_config_mode": "split"}})
        assert self.restart_after((self.OLD, upd), applier=applier)
        self.restart.assert_called_once_with("bgp")

    def test_key_deleted_and_readded__restart(self):
        removed = self.updated(SNMP_COMMUNITY=None)
        assert self.restart_after((self.OLD, removed), (removed, copy.deepcopy(self.OLD)))
        self.restart.assert_called_once_with("snmp")

    def test_pending_restarts_cleared__not_repeated(self):
        assert self.restart_after((self.OLD, self.updated(SNMP={})))
        assert self.restart_after()
        self.restart.assert_called_once_with("snmp")

    def test_empty_field_value__counts_as_unset(self):
        for value in ("", []):
            upd = self.updated(DEVICE_METADATA={"localhost": {"hostname": "sw1",
                                                              "docker_routing_config_mode": value}})
            assert self.restart_after((self.OLD, upd))
        self.restart.assert_not_called()

    def test_modified_only__ignores_field_set_or_cleared(self):
        old = self.updated(PORT={"Ethernet0": {"speed": "100000"}, "Ethernet4": {"mtu": "9100"}})
        for port in ({"Ethernet0": {"speed": "100000"}, "Ethernet4": {"mtu": "9100", "speed": "100000"}},
                     {"Ethernet0": {}, "Ethernet4": {"mtu": "9100"}},
                     {"Ethernet4": {"mtu": "9100"}}):
            assert self.restart_after((old, self.updated(PORT=port)))
        self.restart.assert_not_called()
        upd = self.updated(PORT={"Ethernet0": {"speed": "400000"}, "Ethernet4": {"mtu": "9100"}})
        assert self.restart_after((old, upd))
        self.restart.assert_called_once_with("telemetry")

    def test_defaults__unset_field_takes_default(self):
        for old_meta, upd_meta in (({}, {"synchronous_mode": "enable"}),
                                   ({"synchronous_mode": "enable"}, {}),
                                   ({"synchronous_mode": ""}, {"synchronous_mode": "enable"})):
            old = self.updated(DEVICE_METADATA={"localhost": old_meta})
            assert self.restart_after((old, self.updated(DEVICE_METADATA={"localhost": upd_meta})))
        assert self.restart_after((self.OLD, self.updated(DEVICE_METADATA=None)))
        self.restart.assert_not_called()
        for old_meta, upd_meta in (({}, {"synchronous_mode": "disable"}),
                                   ({"synchronous_mode": "disable"}, {})):
            self.restart.reset_mock()
            old = self.updated(DEVICE_METADATA={"localhost": old_meta})
            assert self.restart_after((old, self.updated(DEVICE_METADATA={"localhost": upd_meta})))
            self.restart.assert_called_once_with("swss")

    def test_per_asic__asic_scope_restarts_the_asic_instance(self):
        applier = generic_config_updater.change_applier.ChangeApplier(scope="asic1")
        upd = self.updated(DEVICE_METADATA={"localhost": {"hostname": "sw1", "synchronous_mode": "disable"}})
        assert self.restart_after((self.OLD, upd), applier=applier)
        self.command.assert_called_once_with(["systemctl", "reset-failed", "swss@1", "syncd@1"])
        self.restart.assert_called_once_with("swss@1")

    def test_swss_restarts_first(self):
        upd = self.updated(SNMP={}, DEVICE_METADATA={"localhost": {"docker_routing_config_mode": "split",
                                                                   "synchronous_mode": "disable"}})
        with patch("generic_config_updater.change_applier.multi_asic.is_multi_asic", return_value=False):
            assert self.restart_after((self.OLD, upd))
        assert self.restart.call_args_list == [call("swss"), call("bgp"), call("snmp")]

    def test_per_asic__disabled_feature__no_restart(self):
        applier = generic_config_updater.change_applier.ChangeApplier(scope="asic1")
        upd = self.updated(DEVICE_METADATA={"localhost": {"synchronous_mode": "disable"}},
                           FEATURE={"swss": {"state": "disabled"}})
        assert self.restart_after((self.OLD, upd), applier=applier)
        self.restart.assert_not_called()

    def test_per_asic__host_scope(self):
        upd = self.updated(DEVICE_METADATA={"localhost": {"hostname": "sw1", "synchronous_mode": "disable"}})
        with patch("generic_config_updater.change_applier.multi_asic.is_multi_asic", return_value=True):
            assert self.restart_after((self.OLD, upd))
        self.restart.assert_not_called()
        with patch("generic_config_updater.change_applier.multi_asic.is_multi_asic", return_value=False):
            assert self.restart_after((self.OLD, upd))
        self.command.assert_called_once_with(["systemctl", "reset-failed", "swss", "syncd"])
        self.restart.assert_called_once_with("swss")

    def test_reset_failed__clears_extra_units_first(self):
        upd = self.updated(SYSLOG_SERVER={"10.0.0.1": {}})
        assert self.restart_after((self.OLD, upd))
        self.command.assert_called_once_with(["systemctl", "reset-failed", "rsyslog-config", "rsyslog"])
        self.restart.assert_called_once_with("rsyslog-config")

    def test_patch_with_several_snmp_changes__one_restart(self):
        target = self.updated(SNMP={"LOCATION": {"Location": "dc"}, "CONTACT": {"Contact": "noc"}},
                              SNMP_COMMUNITY={"private": {"TYPE": "RW"}})
        patch_ops = jsonpatch.JsonPatch([
            {"op": "replace", "path": "/SNMP/LOCATION/Location", "value": "dc"},
            {"op": "add", "path": "/SNMP/CONTACT", "value": {"Contact": "noc"}},
            {"op": "add", "path": "/SNMP_COMMUNITY/private", "value": {"TYPE": "RW"}},
            {"op": "remove", "path": "/SNMP_COMMUNITY/public"},
        ])
        config_wrapper = Mock()
        config_wrapper.get_config_db_as_json.side_effect = [copy.deepcopy(self.OLD), target]
        config_wrapper.get_empty_tables.return_value = []
        patch_wrapper = Mock()
        patch_wrapper.simulate_config_db_patch.return_value = target
        patch_wrapper.verify_same_json.return_value = True
        patchsorter = Mock()
        patchsorter.sort.return_value = [generic_config_updater.gu_common.JsonChange(jsonpatch.JsonPatch([op]))
                                         for op in patch_ops]
        with patch("generic_config_updater.change_applier.set_config"), \
                patch("generic_config_updater.change_applier.time.sleep"), \
                patch.object(self.applier, "_services_validate", return_value=0):
            gu.PatchApplier(patchsorter, self.applier, config_wrapper, patch_wrapper).apply(patch_ops)
        self.restart.assert_called_once_with("snmp")

    def apply_then_fail(self, applied_ops):
        target = self.updated(SNMP={"LOCATION": {"Location": "dc"}}, VLAN={"Vlan100": {"vlanid": "100", "mtu": "9100"}})
        config_wrapper = Mock()
        config_wrapper.get_config_db_as_json.return_value = copy.deepcopy(self.OLD)
        config_wrapper.get_empty_tables.return_value = []
        patch_wrapper = Mock()
        patch_wrapper.simulate_config_db_patch.return_value = target
        applied_change = generic_config_updater.gu_common.JsonChange(jsonpatch.JsonPatch(applied_ops))
        failing_change = Mock()
        failing_change.apply.side_effect = generic_config_updater.gu_common.GenericConfigUpdaterError("boom")
        patchsorter = Mock()
        patchsorter.sort.return_value = [applied_change, failing_change]
        with patch("generic_config_updater.change_applier.set_config"), \
                patch("generic_config_updater.change_applier.time.sleep"), \
                patch.object(self.applier, "_services_validate", return_value=0):
            with self.assertRaisesRegex(generic_config_updater.gu_common.GenericConfigUpdaterError, "boom"):
                gu.PatchApplier(patchsorter, self.applier, config_wrapper, patch_wrapper).apply(Mock())

    def test_failed_change__restarts_for_changes_already_applied(self):
        self.apply_then_fail([{"op": "replace", "path": "/SNMP/LOCATION/Location", "value": "dc"}])
        self.restart.assert_called_once_with("snmp")

    def test_failed_change__no_restart_for_changes_not_applied(self):
        self.apply_then_fail([{"op": "add", "path": "/VLAN/Vlan100/mtu", "value": "9100"}])
        self.restart.assert_not_called()


class TestShippedRestartConf(unittest.TestCase):
    def load_conf(self):
        conf_file = os.path.join(os.path.dirname(generic_config_updater.change_applier.__file__),
                                 "gcu_services_validator.conf.json")
        with open(conf_file) as f:
            return json.load(f)

    def test_restart_rules_are_well_formed(self):
        # Other tools read these rules, so keep them to the documented shape.
        for tbl, tbl_conf in self.load_conf()["tables"].items():
            rules = tbl_conf.get("restart_on_change", [])
            assert isinstance(rules, list), tbl
            for rule in rules:
                assert isinstance(rule, dict) and "units" in rule, tbl
                assert set(rule) <= {"units", "fields", "reset_failed", "modified_only", "host_only",
                                     "per_asic", "defaults"}, tbl
                for key in ("units", "fields", "reset_failed"):
                    values = rule.get(key, ["x"])
                    assert isinstance(values, list) and values, tbl
                    assert all(isinstance(v, str) and v for v in values), tbl
                for key in ("modified_only", "host_only", "per_asic"):
                    assert rule.get(key, True) is True, tbl
                assert not (rule.get("host_only") and rule.get("per_asic")), tbl
                defaults = rule.get("defaults", {"x": "x"})
                assert isinstance(defaults, dict) and defaults, tbl
                assert all(isinstance(v, str) and v for v in defaults.values()), tbl
                if "defaults" in rule:
                    assert set(defaults) <= set(rule.get("fields", [])), tbl

    # snmpd.conf is rendered from these tables only when the snmp container starts.
    SNMP_TABLES = ["SNMP", "SNMP_COMMUNITY", "SNMP_USER", "SNMP_AGENT_ADDRESS_CONFIG", "SNMP_TRAP_CONFIG"]

    @patch("generic_config_updater.services_validator.command_wrapper", return_value=0)
    @patch("generic_config_updater.services_validator._service_restart", return_value=True)
    @patch("generic_config_updater.change_applier.get_config_db")
    def test_each_snmp_table_restarts_snmp(self, mock_db, mock_restart, mock_command):
        conf = self.load_conf()
        with patch.object(generic_config_updater.change_applier.ChangeApplier, "updater_conf", conf):
            applier = generic_config_updater.change_applier.ChangeApplier()
            for tbl in self.SNMP_TABLES:
                mock_restart.reset_mock()
                applier._collect_restarts({}, {tbl: {"key": {"field": "value"}}})
                assert applier.restart_services()
                mock_restart.assert_called_once_with("snmp")
