import copy
import json
import subprocess
import jsondiff
import importlib
import os
import tempfile
from collections import defaultdict
from swsscommon.swsscommon import ConfigDBConnector
from sonic_py_common import multi_asic
from .gu_common import GenericConfigUpdaterError, genericUpdaterLogging

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
UPDATER_CONF_FILE = f"{SCRIPT_DIR}/gcu_services_validator.conf.json"
logger = genericUpdaterLogging.get_logger(title="Change Applier")

print_to_console = False


def set_verbose(verbose=False):
    global print_to_console, logger

    print_to_console = verbose
    if verbose:
        logger.set_min_log_priority_debug()
    else:
        logger.set_min_log_priority_notice()


def log_debug(m):
    logger.log(logger.LOG_PRIORITY_DEBUG, m, print_to_console)


def log_error(m):
    logger.log(logger.LOG_PRIORITY_ERROR, m, print_to_console)


def get_config_db(scope=multi_asic.DEFAULT_NAMESPACE):
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=scope)
    config_db.connect()
    return config_db


def set_config(config_db, tbl, key, data):
    config_db.set_entry(tbl, key, data)


def prune_empty_table(data):
    # For JSON Patch empty entries are valid
    # With redis, when last key is removed, the table gets removed too.
    #
    # Hence where required, prune tables with no keys.
    #
    tables = list(data.keys())
    for tbl in tables:
        if not data[tbl]:
            data.pop(tbl)
    return data


class DryRunChangeApplier:

    def __init__(self, config_wrapper):
        self.config_wrapper = config_wrapper

    def apply(self, change):
        self.config_wrapper.apply_change_to_config_db(change)

    def remove_backend_tables_from_config(self, data):
        return data


class ChangeApplier:

    updater_conf = None

    def __init__(self, scope=multi_asic.DEFAULT_NAMESPACE):
        self.scope = scope
        self.config_db = get_config_db(self.scope)
        self.backend_tables = [
            "BUFFER_PG",
            "BUFFER_PROFILE",
            "FLEX_COUNTER_TABLE"
        ]
        if (not ChangeApplier.updater_conf) and os.path.exists(UPDATER_CONF_FILE):
            with open(UPDATER_CONF_FILE, "r") as s:
                ChangeApplier.updater_conf = json.load(s)

    def _invoke_cmd(self, cmd, old_cfg, upd_cfg, keys):
        # cmd is in the format as <package/module name>.<method name>
        #
        method_name = cmd.split(".")[-1]
        module_name = ".".join(cmd.split(".")[0:-1])

        module = importlib.import_module(module_name, package=None)
        method_to_call = getattr(module, method_name)

        return method_to_call(old_cfg, upd_cfg, keys)

    def _services_validate(self, old_cfg, upd_cfg, keys):
        lst_svcs = set()
        lst_cmds = set()
        if not keys:
            # calling apply with no config would invoke
            # default validation, if any
            #
            keys[""] = {}

        tables = ChangeApplier.updater_conf["tables"]
        for tbl in keys:
            lst_svcs.update(tables.get(tbl, {}).get("services_to_validate", []))

        services = ChangeApplier.updater_conf["services"]
        for svc in lst_svcs:
            lst_cmds.update(services.get(svc, {}).get("validate_commands", []))

        for cmd in lst_cmds:
            ret = self._invoke_cmd(cmd, old_cfg, upd_cfg, keys)
            if not ret:
                log_error("service invoked: {} failed with ret={}".format(cmd, ret))
                return ret
            log_debug("service invoked: {}".format(cmd))
        return 0

    def _upd_data(self, tbl, run_tbl, upd_tbl, upd_keys):
        for key in set(run_tbl.keys()).union(set(upd_tbl.keys())):
            run_data = run_tbl.get(key, None)
            upd_data = upd_tbl.get(key, None)

            if run_data != upd_data:
                set_config(self.config_db, tbl, key, upd_data)
                upd_keys[tbl][key] = {}
                log_debug("Patch affected tbl={} key={}".format(tbl, key))

    def _report_mismatch(self, run_data, upd_data):
        log_error("run_data vs expected_data: {}".format(
            str(jsondiff.diff(run_data, upd_data))[0:40]))

    def apply(self, change):
        run_data = self._get_running_config()
        upd_data = prune_empty_table(change.apply(copy.deepcopy(run_data)))
        upd_keys = defaultdict(dict)

        for tbl in sorted(set(run_data.keys()).union(set(upd_data.keys()))):
            self._upd_data(tbl, run_data.get(tbl, {}), upd_data.get(tbl, {}), upd_keys)

        ret = self._services_validate(run_data, upd_data, upd_keys)
        if not ret:
            run_data = self._get_running_config()
            self.remove_backend_tables_from_config(upd_data)
            self.remove_backend_tables_from_config(run_data)
            if upd_data != run_data:
                self._report_mismatch(run_data, upd_data)
                ret = -1
        if ret:
            log_error("Failed to apply Json change")
        return ret

    def remove_backend_tables_from_config(self, data):
        for key in self.backend_tables:
            data.pop(key, None)

    def _get_running_config(self):
        _, fname = tempfile.mkstemp(suffix="_changeApplier")

        if self.scope:
            cmd = ['sonic-cfggen', '-d', '--print-data', '-n', self.scope]
        else:
            cmd = ['sonic-cfggen', '-d', '--print-data']

        with open(fname, "w") as file:
            result = subprocess.Popen(cmd, stdout=file, stderr=subprocess.PIPE, text=True)
            _, err = result.communicate()

        return_code = result.returncode
        if return_code:
            os.remove(fname)
            raise GenericConfigUpdaterError(
                f"Failed to get running config for scope: {self.scope}," +
                f"Return code: {return_code}, Error: {err}")

        run_data = {}
        try:
            with open(fname, "r") as file:
                run_data = json.load(file)
        finally:
            if os.path.isfile(fname):
                os.remove(fname)
        return run_data
