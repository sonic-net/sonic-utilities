import os
import sys
from unittest import mock

import pytest

from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

hw_defaults = load_module_from_source(
    'pfcwd_hw_defaults', os.path.join(modules_path, 'scripts', 'pfcwd_hw_defaults'))

PORTS = ['Ethernet0', 'Ethernet4']
SW_DEFAULTS = {**{p: {'action': 'drop', 'detection_time': '200', 'restoration_time': '200',
                      'pfc_stat_history': 'disable'} for p in PORTS},
               'GLOBAL': {'POLL_INTERVAL': '200'}}
HW = {'RECOVERY_MECHANISM': 'HARDWARE', 'DETECTION_TIME_MIN': '1', 'DETECTION_TIME_MAX': '1500',
      'RESTORATION_TIME_MIN': '100', 'RESTORATION_TIME_MAX': '1000'}


class FakeConfigDb:
    def __init__(self, pfcwd, default_status='enable'):
        self.t = {
            'DEVICE_METADATA': {'localhost': {'default_pfcwd_status': default_status}},
            'DEVICE_NEIGHBOR': {p: {'name': 'n' + p} for p in PORTS},
            'PORT_QOS_MAP': {p: {'pfc_enable': '3,4'} for p in PORTS},
            'PORT': {p: {} for p in PORTS},
            'PFC_WD': {k: dict(v) for k, v in pfcwd.items()},
        }

    def get_table(self, name):
        return {k: dict(v) for k, v in self.t.get(name, {}).items()}

    def get_entry(self, table, key):
        return dict(self.t.get(table, {}).get(key, {}))

    def mod_entry(self, table, key, fields):
        if fields is None:
            self.t.get(table, {}).pop(key, None)
            return
        self.t.setdefault(table, {}).setdefault(key, {}).update({k: str(v) for k, v in fields.items()})

    def set_entry(self, table, key, fields):
        if not fields:
            self.t.get(table, {}).pop(key, None)
        else:
            self.t.setdefault(table, {})[key] = {k: str(v) for k, v in fields.items()}


class FakeStateDb:
    STATE_DB = 'STATE_DB'

    def __init__(self, entry, dldr_capable=None):
        self.entry = entry
        self.capability = {} if dldr_capable is None else {'PFC_DLDR_CAPABLE': dldr_capable}
        self.calls = 0  # reads of the watchdog's entry

    def get_all(self, db, key):
        if key == 'SWITCH_CAPABILITY|switch':
            return dict(self.capability)
        self.calls += 1
        return dict(self.entry) if self.entry is not None else None


class Box:
    """The DBs of each namespace, with the script's syslog and 'pfcwd start_default' captured."""

    def __init__(self, cfg, state):
        self.cfg, self.state, self.logs = cfg, state, []

    def run(self, start_default_rc=0, mode_wait=None):
        log = mock.Mock()
        for name in ('log_info', 'log_notice', 'log_warning', 'log_error'):
            getattr(log, name).side_effect = (lambda n: lambda msg: self.logs.append((n, msg)))(name)
        self.calls = []

        def record(name, result):
            def call(*args):
                self.calls.append(name)
                return result(*args)
            return call
        patches = [
            mock.patch.object(hw_defaults, 'load_db_config', side_effect=record('load_db_config', lambda: None)),
            mock.patch.object(hw_defaults.multi_asic, 'get_namespace_list', return_value=list(self.cfg)),
            mock.patch.object(hw_defaults.multi_asic, 'connect_config_db_for_ns',
                              side_effect=record('connect', self.cfg.__getitem__)),
            mock.patch.object(hw_defaults.multi_asic, 'connect_to_all_dbs_for_ns',
                              side_effect=record('connect', self.state.__getitem__)),
            mock.patch.object(hw_defaults, 'log', log),
            mock.patch.object(hw_defaults, 'POLL_SECONDS', 0.05),
            mock.patch.object(hw_defaults, 'RANGE_WAIT_SECONDS', 0.2),
            mock.patch.object(hw_defaults.subprocess, 'run',
                              return_value=mock.Mock(returncode=start_default_rc, stderr='boom')),
        ]
        if mode_wait is not None:
            patches.append(mock.patch.object(hw_defaults, 'MODE_WAIT_SECONDS', mode_wait))
        for p in patches:
            p.start()
        try:
            self.rc = hw_defaults.main()
            self.start_default_runs = hw_defaults.subprocess.run.call_count
        finally:
            for p in reversed(patches):
                p.stop()
        return self

    def logged(self, text):
        return any(text in msg for _, msg in self.logs)


def single(pfcwd, state, **kw):
    return Box({'': FakeConfigDb(pfcwd, **kw)}, {'': FakeStateDb(state)})


class TestPfcwdHwDefaults(object):

    def test_db_config_loaded_before_any_namespace_connect(self):
        """A multi-ASIC switch cannot connect to a namespace's DBs before the global DB config
        is loaded."""
        nss = ['asic0', 'asic1']
        box = Box({ns: FakeConfigDb(SW_DEFAULTS) for ns in nss},
                  {ns: FakeStateDb({'RECOVERY_MECHANISM': 'SOFTWARE'}) for ns in nss}).run()
        assert box.calls[0] == 'load_db_config' and 'connect' in box.calls

    def test_software_mode_changes_nothing(self):
        box = single(SW_DEFAULTS, {'RECOVERY_MECHANISM': 'SOFTWARE'}).run()
        assert box.state[''].calls == 1  # no wait
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg[''].get_table('PFC_WD') == SW_DEFAULTS
        assert box.logged('runs software')

    def test_no_mode_reported_waits_once_for_all_namespaces(self):
        nss = ['asic0', 'asic1', 'asic2']
        box = Box({ns: FakeConfigDb(SW_DEFAULTS) for ns in nss}, {ns: FakeStateDb({}) for ns in nss})
        box.run(mode_wait=0.5)
        # the first namespace uses up the shared wait; the others are read once
        assert box.state['asic0'].calls > 1
        assert box.state['asic1'].calls == 1 and box.state['asic2'].calls == 1
        assert box.rc == 0 and box.start_default_runs == 0
        assert sum('no mode reported' in msg for _, msg in box.logs) == 3
        assert all(box.cfg[ns].get_table('PFC_WD') == SW_DEFAULTS for ns in nss)

    def test_no_dldr_capability_exits_without_waiting(self):
        """A switch whose SAI lacks the capability cannot run the hardware watchdog: no wait,
        though this watchdog reports no mode."""
        box = Box({'': FakeConfigDb(SW_DEFAULTS)}, {'': FakeStateDb({}, dldr_capable='false')})
        box.run(mode_wait=30)
        assert box.state[''].calls == 1
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg[''].get_table('PFC_WD') == SW_DEFAULTS
        assert box.logged('without the PFC deadlock recovery capability')

    def test_dldr_capable_without_mode_still_waits(self):
        box = Box({'': FakeConfigDb(SW_DEFAULTS)}, {'': FakeStateDb({}, dldr_capable='true')})
        box.run(mode_wait=0.3)
        assert box.state[''].calls > 1
        assert box.start_default_runs == 0 and box.logged('no mode reported')

    def test_reported_mode_wins_over_capability(self):
        box = Box({'': FakeConfigDb(SW_DEFAULTS)}, {'': FakeStateDb(HW, dldr_capable='false')}).run()
        assert box.start_default_runs == 1

    def test_software_defaults_rerun_start_default(self):
        box = single(SW_DEFAULTS, HW).run()
        assert box.rc == 0 and box.start_default_runs == 1
        # start_default is mocked here, so the POLL_INTERVAL removal is step 2's
        assert 'GLOBAL' not in box.cfg[''].get_table('PFC_WD')

    def test_changed_table_only_brought_into_range(self):
        table = {'Ethernet0': {'action': 'drop', 'detection_time': '1600', 'restoration_time': '1600'},
                 'Ethernet4': {'action': 'drop', 'detection_time': '400', 'restoration_time': '50'},
                 'GLOBAL': {'POLL_INTERVAL': '1000', 'BIG_RED_SWITCH': 'enable'}}
        box = single(table, HW).run()
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg[''].get_entry('PFC_WD', 'Ethernet0') == {
            'action': 'drop', 'detection_time': '1500', 'restoration_time': '1000'}
        assert box.cfg[''].get_entry('PFC_WD', 'Ethernet4')['restoration_time'] == '100'
        assert box.cfg[''].get_entry('PFC_WD', 'GLOBAL') == {'BIG_RED_SWITCH': 'enable'}
        assert box.logged('BIG_RED_SWITCH') and box.logged('not applied by the hardware')

    def test_no_common_detection_value_skips_start_default(self):
        """A hardware detection maximum below sonic-pfcwd.yang's minimum: start_default would
        write a value YANG rejects, so it is not run, and detection times are left alone."""
        box = single(SW_DEFAULTS, dict(HW, DETECTION_TIME_MAX='50')).run()
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg[''].get_entry('PFC_WD', 'Ethernet0')['detection_time'] == '200'
        assert box.logged('No detection_time is in both') and box.logged('left as configured')
        assert 'GLOBAL' not in box.cfg[''].get_table('PFC_WD')

    def test_no_range_reported_still_removes_poll_interval(self):
        table = {'Ethernet0': {'action': 'drop', 'detection_time': '1600', 'restoration_time': '1600'},
                 'GLOBAL': {'POLL_INTERVAL': '1000'}}
        box = single(table, {'RECOVERY_MECHANISM': 'HARDWARE'}).run()
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg[''].get_entry('PFC_WD', 'Ethernet0')['detection_time'] == '1600'
        assert 'GLOBAL' not in box.cfg[''].get_table('PFC_WD')
        assert box.logged('No PFC watchdog hardware timer range reported')

    def test_default_disabled_still_brought_into_range(self):
        table = {'Ethernet0': {'action': 'drop', 'detection_time': '1600', 'restoration_time': '1600'}}
        box = single(table, HW, default_status='disable').run()
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg[''].get_entry('PFC_WD', 'Ethernet0')['detection_time'] == '1500'
        assert box.logged('Default PFC watchdog not enabled')

    def test_namespace_with_default_disabled_does_not_block_start_default(self):
        cfg = {'asic0': FakeConfigDb(SW_DEFAULTS), 'asic1': FakeConfigDb({}, default_status='disable')}
        box = Box(cfg, {'asic0': FakeStateDb(HW), 'asic1': FakeStateDb(HW)}).run()
        assert box.rc == 0 and box.start_default_runs == 1

    def test_enabled_namespace_not_in_hardware_blocks_start_default(self):
        cfg = {'asic0': FakeConfigDb(SW_DEFAULTS), 'asic1': FakeConfigDb(SW_DEFAULTS)}
        box = Box(cfg, {'asic0': FakeStateDb(HW), 'asic1': FakeStateDb({'RECOVERY_MECHANISM': 'SOFTWARE'})}).run()
        assert box.rc == 0 and box.start_default_runs == 0
        assert box.cfg['asic1'].get_table('PFC_WD') == SW_DEFAULTS

    def test_stopped_port_blocks_start_default(self):
        """A port whose row 'pfcwd stop' deleted stays stopped."""
        table = {k: v for k, v in SW_DEFAULTS.items() if k != 'Ethernet4'}
        box = single(table, HW).run()
        assert box.start_default_runs == 0
        assert 'Ethernet4' not in box.cfg[''].get_table('PFC_WD')

    def test_start_default_failure_still_brings_into_range(self):
        box = single(SW_DEFAULTS, HW).run(start_default_rc=2)
        assert box.rc == 1
        assert 'GLOBAL' not in box.cfg[''].get_table('PFC_WD')
        assert box.logged("'pfcwd start_default' failed (2): boom")

    @pytest.mark.parametrize('entry', [None, {}])
    def test_no_state_entry(self, entry):
        box = single(SW_DEFAULTS, entry).run(mode_wait=0.2)
        assert box.rc == 0 and box.start_default_runs == 0
