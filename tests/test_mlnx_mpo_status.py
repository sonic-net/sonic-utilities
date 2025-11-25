import types
import pytest
import click

# Import the plugin module
from show.plugins import mlnx as mlnx_mod


class MockCfgDB:
    def __init__(self, tbl):
        self._tbl = tbl
    def connect(self, *args, **kwargs):
        return
    def get_table(self, name):
        return self._tbl if name == 'PORT' else {}


class MockDb:
    def __init__(self, state=None, appl=None):
        self.STATE_DB = 6
        self.APPL_DB = 0
        self._state = state or {}
        self._appl = appl or {}
    def connect(self, *args, **kwargs):
        return
    def get(self, dbid, key, field):
        if dbid == self.STATE_DB:
            return self._state.get((key, field))
        if dbid == self.APPL_DB:
            return self._appl.get((key, field))
        return None


def test_single_asic_rows(monkeypatch):
    # CONFIG_DB PORT table
    port_tbl = {
        'Ethernet0': {'lanes': '0,1,2,3'},
        'Ethernet4': {'lanes': '4,5'},
        'Ethernet6': {'lanes': '6'},
        'Ethernet7': {'lanes': '7'},
    }
    # STATE_DB CPO type
    state_map = {
        ('TRANSCEIVER_INFO|Ethernet0', 'type'): 'CPO',
        ('TRANSCEIVER_INFO|Ethernet4', 'type'): 'CPO',
        ('TRANSCEIVER_INFO|Ethernet6', 'type'): 'CPO',
        ('TRANSCEIVER_INFO|Ethernet7', 'type'): 'CPO',
    }
    # APPL_DB oper status
    appl_map = {
        ('PORT_TABLE:Ethernet0', 'oper_status'): 'up',
        ('PORT_TABLE:Ethernet4', 'oper_status'): 'down',
        ('PORT_TABLE:Ethernet6', 'oper_status'): 'up',
        ('PORT_TABLE:Ethernet7', 'oper_status'): 'up',
    }

    monkeypatch.setattr(mlnx_mod, 'connect_cfgdb', lambda namespace=None: MockCfgDB(port_tbl))
    monkeypatch.setattr(mlnx_mod, 'connect_state_db', lambda ns=None: MockDb(state=state_map))
    monkeypatch.setattr(mlnx_mod, 'connect_appl_db', lambda ns=None: MockDb(appl=appl_map))

    rows = mlnx_mod.create_single_asic_mpo_rows()
    # Expect:
    # MPO 1 -> Ethernet0 in all lanes
    # MPO 2 -> Ethernet4, Ethernet4, Ethernet6, Ethernet7
    assert rows[0] == [1, 'Ethernet0(UP)', 'Ethernet0(UP)', 'Ethernet0(UP)', 'Ethernet0(UP)']
    assert rows[1] == [2, 'Ethernet4(DOWN)', 'Ethernet4(DOWN)', 'Ethernet6(UP)', 'Ethernet7(UP)']


def test_multi_asic_rows(monkeypatch):
    # Namespaces
    monkeypatch.setattr(mlnx_mod.multi_asic, 'get_namespace_list', lambda: ['asic0', 'asic1', 'asic2', 'asic3'])
    # Per namespace PORT tables
    cfg_by_ns = {
        'asic0': {'Ethernet0': {}, 'Ethernet1': {}},
        'asic1': {'Ethernet512': {}, 'Ethernet513': {}},
        'asic2': {'Ethernet1024': {}, 'Ethernet1025': {}},
        'asic3': {'Ethernet1536': {}, 'Ethernet1537': {}},
    }
    def cfg_factory(ns):
        return MockCfgDB(cfg_by_ns[ns])
    monkeypatch.setattr(mlnx_mod, 'connect_cfgdb', cfg_factory)
    # All CPO
    def state_factory(ns=None):
        state_map = {}
        for p in cfg_by_ns[ns]:
            state_map[(f'TRANSCEIVER_INFO|{p}', 'type')] = 'CPO'
        return MockDb(state=state_map)
    monkeypatch.setattr(mlnx_mod, 'connect_state_db', state_factory)
    # oper_status (mix)
    def appl_factory(ns=None):
        appl_map = {}
        for p in cfg_by_ns[ns]:
            appl_map[(f'PORT_TABLE:{p}', 'oper_status')] = 'up'
        return MockDb(appl=appl_map)
    monkeypatch.setattr(mlnx_mod, 'connect_appl_db', appl_factory)

    rows = mlnx_mod.create_multi_asic_mpo_rows()
    # Expect:
    # MPO 1: Ethernet0/asic0, Ethernet512/asic1, Ethernet1024/asic2, Ethernet1536/asic3
    # MPO 2: Ethernet1/asic0, Ethernet513/asic1, Ethernet1025/asic2, Ethernet1537/asic3
    assert rows[0] == [1, 'Ethernet0/asic0(UP)', 'Ethernet512/asic1(UP)', 'Ethernet1024/asic2(UP)', 'Ethernet1536/asic3(UP)']
    assert rows[1] == [2, 'Ethernet1/asic0(UP)', 'Ethernet513/asic1(UP)', 'Ethernet1025/asic2(UP)', 'Ethernet1537/asic3(UP)']


def test_single_asic_excludes_non_cpo(monkeypatch):
    # CONFIG_DB: include one CPO and one non-CPO "service" (simulated by type != CPO)
    port_tbl = {
        'Ethernet0': {'lanes': '0,1,2,3'},
        'Ethernet100': {'lanes': '100,101,102,103'},  # not CPO
    }
    state_map = {
        ('TRANSCEIVER_INFO|Ethernet0', 'type'): 'CPO',
        ('TRANSCEIVER_INFO|Ethernet100', 'type'): 'QSFP',  # non-CPO
    }
    appl_map = {
        ('PORT_TABLE:Ethernet0', 'oper_status'): 'up',
        ('PORT_TABLE:Ethernet100', 'oper_status'): 'up',
    }
    monkeypatch.setattr(mlnx_mod, 'connect_cfgdb', lambda namespace=None: MockCfgDB(port_tbl))
    monkeypatch.setattr(mlnx_mod, 'connect_state_db', lambda ns=None: MockDb(state=state_map))
    monkeypatch.setattr(mlnx_mod, 'connect_appl_db', lambda ns=None: MockDb(appl=appl_map))
    rows = mlnx_mod.create_single_asic_mpo_rows()
    # Only Ethernet0 should appear; Ethernet100 (non-CPO) must be excluded
    assert rows == [[1, 'Ethernet0(UP)', 'Ethernet0(UP)', 'Ethernet0(UP)', 'Ethernet0(UP)']]


def test_single_asic_no_cpo_raises(monkeypatch):
    # CONFIG_DB ports but none are CPO
    port_tbl = {
        'Ethernet0': {'lanes': '0,1,2,3'},
        'Ethernet4': {'lanes': '4,5,6,7'},
    }
    state_map = {
        ('TRANSCEIVER_INFO|Ethernet0', 'type'): 'QSFP',
        ('TRANSCEIVER_INFO|Ethernet4', 'type'): 'QSFP',
    }
    appl_map = {}
    monkeypatch.setattr(mlnx_mod, 'connect_cfgdb', lambda namespace=None: MockCfgDB(port_tbl))
    monkeypatch.setattr(mlnx_mod, 'connect_state_db', lambda ns=None: MockDb(state=state_map))
    monkeypatch.setattr(mlnx_mod, 'connect_appl_db', lambda ns=None: MockDb(appl=appl_map))
    with pytest.raises(click.ClickException):
        _ = mlnx_mod.create_single_asic_mpo_rows()


def test_multi_asic_no_cpo_raises(monkeypatch):
    # No CPO in any namespace
    monkeypatch.setattr(mlnx_mod.multi_asic, 'get_namespace_list', lambda: ['asic0', 'asic1'])
    cfg_by_ns = {
        'asic0': {'Ethernet0': {}},
        'asic1': {'Ethernet512': {}},
    }
    def cfg_factory(ns):
        return MockCfgDB(cfg_by_ns[ns])
    monkeypatch.setattr(mlnx_mod, 'connect_cfgdb', cfg_factory)
    def state_factory(ns=None):
        state_map = {}
        for p in cfg_by_ns[ns]:
            state_map[(f'TRANSCEIVER_INFO|{p}', 'type')] = 'QSFP'  # non-CPO
        return MockDb(state=state_map)
    monkeypatch.setattr(mlnx_mod, 'connect_state_db', state_factory)
    monkeypatch.setattr(mlnx_mod, 'connect_appl_db', lambda ns=None: MockDb(appl={}))
    with pytest.raises(click.ClickException):
        _ = mlnx_mod.create_multi_asic_mpo_rows()


