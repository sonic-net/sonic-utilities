#!/usr/bin/env python

""" This module implements new feature registration/de-registration in SONiC system. """
import copy
from typing import Dict, Type

from sonic_package_manager.logger import log
from sonic_package_manager.manifest import Manifest
from sonic_package_manager.service_creator.sonic_db import SonicDB

FEATURE = 'FEATURE'
DEFAULT_FEATURE_CONFIG = {
    'state': 'disabled',
    'auto_restart': 'enabled',
    'high_mem_alert': 'disabled',
    'set_owner': 'local'
}

AUTO_TS_GLOBAL = "AUTO_TECHSUPPORT"
AUTO_TS_FEATURE = "AUTO_TECHSUPPORT_FEATURE"
CFG_STATE = "state"
DEFAULT_AUTO_TS_FEATURE_CONFIG = {
    'state': 'disabled',
    'rate_limit_interval': '600',
    'available_mem_threshold': '10.0'
}

SYSLOG_CONFIG = 'SYSLOG_CONFIG_FEATURE'
DEFAULT_SYSLOG_FEATURE_CONFIG = {
    'rate_limit_interval': '300',
    'rate_limit_burst': '20000'
}

def is_enabled(cfg):
    return cfg.get('state', 'disabled').lower() == 'enabled'


def is_multi_instance(cfg):
    return str(cfg.get('has_per_asic_scope', 'False')).lower() == 'true'


class FeatureRegistry:
    """ 1) FeatureRegistry class provides an interface to
    register/de-register new feature tables persistently.
        2) Writes persistent configuration to FEATURE &
    AUTO_TECHSUPPORT_FEATURE tables
    """

    def __init__(self, sonic_db: Type[SonicDB]):
        self._sonic_db = sonic_db

    def register(self,
                 manifest: Manifest,
                 state: str = 'disabled',
                 owner: str = 'local'):
        """ Register feature in CONFIG DBs.

        Args:
            manifest: Feature's manifest.
            state: Desired feature admin state.
            owner: Owner of this feature (kube/local).
        Returns:
            None.
        """

        name = manifest['service']['name']
        db_connectors = self._sonic_db.get_connectors()
        cfg_entries = self.get_default_feature_entries(state, owner)
        non_cfg_entries = self.get_non_configurable_feature_entries(manifest)

        for conn in db_connectors:
            current_cfg = conn.get_entry(FEATURE, name)

            new_cfg = cfg_entries.copy()
            # Override configurable entries with CONFIG DB data.
            new_cfg = {**new_cfg, **current_cfg}
            # Override CONFIG DB data with non configurable entries.
            new_cfg = {**new_cfg, **non_cfg_entries}

            conn.set_entry(FEATURE, name, new_cfg)

        if self.register_auto_ts(name):
            log.info(f'{name} entry is added to {AUTO_TS_FEATURE} table')

        if 'syslog' in manifest['service'] and 'support-rate-limit' in manifest['service']['syslog'] and manifest['service']['syslog']['support-rate-limit']:
            self.register_syslog_config(name)
            log.info(f'{name} entry is added to {SYSLOG_CONFIG} table')

    def deregister(self, name: str):
        """ Deregister feature by name.

        Args:
            name: Name of the feature in CONFIG DB.
        Returns:
            None
        """

        db_connetors = self._sonic_db.get_connectors()
        for conn in db_connetors:
            conn.set_entry(FEATURE, name, None)
            conn.set_entry(AUTO_TS_FEATURE, name, None)
            conn.set_entry(SYSLOG_CONFIG, name, None)

    def update(self,
               old_manifest: Manifest,
               new_manifest: Manifest):
        """ Migrate feature configuration. It can be that non-configurable
        feature entries have to be updated. e.g: name of the service has
        changed, but user configurable entries are not changed).

        Args:
            old_manifest: Old feature manifest.
            new_manifest: New feature manifest.
        Returns:
            None
        """

        old_name = old_manifest['service']['name']
        new_name = new_manifest['service']['name']
        db_connectors = self._sonic_db.get_connectors()
        non_cfg_entries = self.get_non_configurable_feature_entries(new_manifest)

        for conn in db_connectors:
            current_cfg = conn.get_entry(FEATURE, old_name)
            conn.set_entry(FEATURE, old_name, None)

            new_cfg = current_cfg.copy()
            # Override CONFIG DB data with non configurable entries.
            new_cfg = {**new_cfg, **non_cfg_entries}

            conn.set_entry(FEATURE, new_name, new_cfg)

        if self.register_auto_ts(new_name, old_name):
            log.info(f'{new_name} entry is added to {AUTO_TS_FEATURE} table')

        if 'syslog' in new_manifest['service'] and 'support-rate-limit' in new_manifest['service']['syslog'] and new_manifest['service']['syslog']['support-rate-limit']:
            self.register_syslog_config(new_name, old_name)
            log.info(f'{new_name} entry is added to {SYSLOG_CONFIG} table')

    def is_feature_enabled(self, name: str) -> bool:
        """ Returns whether the feature is current enabled
        or not. Accesses running CONFIG DB. If no running CONFIG_DB
        table is found in tables returns False. """

        conn = self._sonic_db.get_running_db_connector()
        if conn is None:
            return False

        cfg = conn.get_entry(FEATURE, name)
        return is_enabled(cfg)

    def get_multi_instance_features(self):
        """ Returns a list of features which run in asic namespace. """

        conn = self._sonic_db.get_initial_db_connector()
        features = conn.get_table(FEATURE)
        return [feature for feature, cfg in features.items() if is_multi_instance(cfg)]

    def infer_auto_ts_capability(self, init_cfg_conn):
        """ Determine whether to enable/disable the state for new feature
        AUTO_TS provides a compile-time knob to enable/disable this feature
        Default State for the new feature follows the decision made at compile time.

        Args:
            init_cfg_conn: PersistentConfigDbConnector for init_cfg.json
        Returns:
            Capability: Tuple: (bool, ["enabled", "disabled"])
        """
        cfg = init_cfg_conn.get_entry(AUTO_TS_GLOBAL, "GLOBAL")
        default_state = cfg.get(CFG_STATE, "")
        if not default_state:
            return (False, "disabled")
        else:
            return (True, default_state)

    def register_auto_ts(self, new_name, old_name=None):
        """ Registers auto_ts feature
        """
        # Infer and update default config
        init_cfg_conn = self._sonic_db.get_initial_db_connector()
        def_cfg = DEFAULT_AUTO_TS_FEATURE_CONFIG.copy()
        (auto_ts_add_cfg, auto_ts_state) = self.infer_auto_ts_capability(init_cfg_conn)
        def_cfg['state'] = auto_ts_state

        if not auto_ts_add_cfg:
            log.debug("Skip adding AUTO_TECHSUPPORT_FEATURE table because no AUTO_TECHSUPPORT|GLOBAL entry is found")
            return False

        for conn in self._sonic_db.get_connectors():
            new_cfg = copy.deepcopy(def_cfg)
            if old_name:
                current_cfg = conn.get_entry(AUTO_TS_FEATURE, old_name)
                conn.set_entry(AUTO_TS_FEATURE, old_name, None)
                new_cfg.update(current_cfg)

            conn.set_entry(AUTO_TS_FEATURE, new_name, new_cfg)
        return True

    def register_syslog_config(self, new_name, old_name=None):
        """ Registers syslog configuration

        Args:
            new_name (str): new table name
            old_name (str, optional): old table name. Defaults to None.
        """
        for conn in self._sonic_db.get_connectors():
            new_cfg = copy.deepcopy(DEFAULT_SYSLOG_FEATURE_CONFIG)
            if old_name:
                current_cfg = conn.get_entry(SYSLOG_CONFIG, old_name)
                conn.set_entry(SYSLOG_CONFIG, old_name, None)
                new_cfg.update(current_cfg)

            conn.set_entry(SYSLOG_CONFIG, new_name, new_cfg)

    @staticmethod
    def get_default_feature_entries(state=None, owner=None) -> Dict[str, str]:
        """ Get configurable feature table entries:
        e.g. 'state', 'auto_restart', etc. """

        cfg = DEFAULT_FEATURE_CONFIG.copy()
        if state:
            cfg['state'] = state
        if owner:
            cfg['set_owner'] = owner
        return cfg

    @staticmethod
    def get_non_configurable_feature_entries(manifest) -> Dict[str, str]:
        """ Get non-configurable feature table entries: e.g. 'delayed' """

        return {
            'has_per_asic_scope': str(manifest['service']['asic-service']),
            'has_global_scope': str(manifest['service']['host-service']),
            'delayed': str(manifest['service']['delayed']),
            'check_up_status': str(manifest['service']['check_up_status']),
            'support_syslog_rate_limit': str(manifest['service']['syslog']['support-rate-limit']),
        }
