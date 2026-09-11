"""Unit tests for the ``tempershow`` script.

The port-name mapping tests focus on ``_build_port_index_map`` /
``_sfp_display_name``, which translate a logical port name (e.g.
``Ethernet0``) into the legacy ``xSFP module <N> Temp`` label. The mapping is
built directly from the port config via ``portconfig.get_port_config`` instead
of loading the heavy ``sonic_platform_base``/``sonic_xcvr`` stack, so these
tests pin both the correctness of the labels and the lightweight code path.

The remaining tests exercise ``__init__``'s DB-config selection, the STATE_DB
collection path (platform and SFP sensors), the multi-ASIC connection
fan-out, warning derivation, and the table/JSON rendering, all against an
in-memory ``SonicV2Connector`` stand-in.
"""
import builtins
import contextlib
import json
from unittest import mock

from .utils import load_source

tempershow = load_source('tempershow', 'scripts/tempershow', cache_module=True)


class _FakeDB:
    """Minimal ``SonicV2Connector`` stand-in backed by an in-memory dict.

    Keys are ``<TABLE>|<port>`` strings mapping to ``{field: value}`` dicts,
    matching how ``tempershow`` reads STATE_DB.
    """

    STATE_DB = 'STATE_DB'

    def __init__(self, data=None, keys_error=False, get_all_error=False):
        self._data = data or {}
        self._keys_error = keys_error
        self._get_all_error = get_all_error
        self.connected = []

    def connect(self, db_id):
        self.connected.append(db_id)

    def keys(self, db_id, pattern):
        if self._keys_error:
            raise RuntimeError('keys() failed')
        prefix = pattern[:-1]  # strip the trailing '*'
        return [key for key in self._data if key.startswith(prefix)]

    def get_all(self, db_id, key):
        if self._get_all_error:
            raise RuntimeError('get_all() failed')
        value = self._data.get(key)
        return dict(value) if value else {}


@contextlib.contextmanager
def _temper_show(state_data=None, port_index_map=None, is_multi_asic=False,
                 is_init=True, is_global_init=True):
    """Yield a ``TemperShow`` whose STATE_DB and platform deps are mocked.

    A single shared ``_FakeDB`` backs both the instance ``db`` and the
    connection returned by ``_get_sfp_db_connections`` on single-ASIC setups.
    Yields ``(instance, db, sonic_db_config_mock, multi_asic_mock)``.
    """
    db = _FakeDB(state_data or {})
    sonic_db_config = mock.Mock()
    sonic_db_config.isInit.return_value = is_init
    sonic_db_config.isGlobalInit.return_value = is_global_init
    multi_asic = mock.Mock()
    multi_asic.is_multi_asic.return_value = is_multi_asic
    with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
         mock.patch.object(tempershow, 'SonicDBConfig', sonic_db_config), \
         mock.patch.object(tempershow, 'multi_asic', multi_asic), \
         mock.patch.object(tempershow, 'get_port_config', None):
        inst = tempershow.TemperShow()
        if port_index_map is not None:
            inst._port_index_map = port_index_map
        yield inst, db, sonic_db_config, multi_asic


def test_import_fallbacks_when_optional_deps_missing():
    """Missing ``sonic_py_common``/``portconfig`` degrade to ``None`` names
    rather than raising at import time."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ('sonic_py_common', 'portconfig'):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    with mock.patch.object(builtins, '__import__', side_effect=fake_import):
        mod = load_source('tempershow_no_optional_deps', 'scripts/tempershow')
    assert mod.multi_asic is None
    assert mod.device_info is None
    assert mod.get_port_config is None


def _patch_env(get_port_config, is_multi_asic=False, num_asics=1):
    """Context managers to drive _build_port_index_map deterministically."""
    return (
        mock.patch.object(tempershow, 'get_port_config', get_port_config),
        mock.patch.object(tempershow.multi_asic, 'is_multi_asic',
                          return_value=is_multi_asic),
        mock.patch.object(tempershow.multi_asic, 'get_num_asics',
                          return_value=num_asics),
        mock.patch.object(tempershow.device_info, 'get_platform_and_hwsku',
                          return_value=('x86_64-mlnx_msn2700-r0', 'ACS-MSN2700')),
    )


class TestBuildPortIndexMap:
    def test_single_asic_uses_index_column(self):
        ports = {
            'Ethernet0': {'lanes': '0,1,2,3', 'alias': 'etp1', 'index': '1'},
            'Ethernet4': {'lanes': '4,5,6,7', 'alias': 'etp2', 'index': '2'},
            # No 'index' -> skipped (e.g. internal/backplane port).
            'Ethernet-BP0': {'lanes': '9', 'role': 'Int'},
        }
        get_port_config = mock.Mock(return_value=(ports, {}, {}))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            result = tempershow.TemperShow._build_port_index_map()
        assert result == {'Ethernet0': 1, 'Ethernet4': 2}

    def test_multi_asic_merges_all_namespaces(self):
        cfgs = {
            'asic0': {'Ethernet0': {'index': '1'}, 'Ethernet4': {'index': '2'}},
            'asic1': {'Ethernet8': {'index': '1'}, 'Ethernet12': {'index': '2'}},
        }

        def fake_get_port_config(hwsku, platform, asic_name=None):
            return (cfgs.get(asic_name, {}), {}, {})

        p1, p2, p3, p4 = _patch_env(fake_get_port_config, is_multi_asic=True,
                                    num_asics=2)
        with p1, p2, p3, p4:
            result = tempershow.TemperShow._build_port_index_map()
        assert result == {
            'Ethernet0': 1, 'Ethernet4': 2, 'Ethernet8': 1, 'Ethernet12': 2,
        }

    def test_returns_empty_when_portconfig_unavailable(self):
        with mock.patch.object(tempershow, 'get_port_config', None):
            assert tempershow.TemperShow._build_port_index_map() == {}

    def test_get_port_config_failure_is_swallowed(self):
        get_port_config = mock.Mock(side_effect=RuntimeError('no db'))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            assert tempershow.TemperShow._build_port_index_map() == {}

    def test_invalid_index_value_is_skipped(self):
        ports = {'Ethernet0': {'index': '1'}, 'EthernetX': {'index': 'NaN'}}
        get_port_config = mock.Mock(return_value=(ports, {}, {}))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            assert tempershow.TemperShow._build_port_index_map() == {'Ethernet0': 1}

    def test_platform_lookup_failure_returns_empty(self):
        # device_info.get_platform_and_hwsku raising must short-circuit before
        # get_port_config is ever consulted.
        get_port_config = mock.Mock(
            return_value=({'Ethernet0': {'index': '1'}}, {}, {}))
        with mock.patch.object(tempershow, 'get_port_config', get_port_config), \
             mock.patch.object(tempershow.device_info, 'get_platform_and_hwsku',
                               side_effect=RuntimeError('no platform')):
            assert tempershow.TemperShow._build_port_index_map() == {}
        get_port_config.assert_not_called()

    def test_num_asics_failure_falls_back_to_single_namespace(self):
        captured = []

        def fake_get_port_config(hwsku, platform, asic_name=None):
            captured.append(asic_name)
            return ({'Ethernet0': {'index': '1'}}, {}, {})

        with mock.patch.object(tempershow, 'get_port_config',
                               fake_get_port_config), \
             mock.patch.object(tempershow.multi_asic, 'is_multi_asic',
                               return_value=True), \
             mock.patch.object(tempershow.multi_asic, 'get_num_asics',
                               side_effect=RuntimeError('cannot count asics')), \
             mock.patch.object(
                 tempershow.device_info, 'get_platform_and_hwsku',
                 return_value=('x86_64-mlnx_msn2700-r0', 'ACS-MSN2700')):
            result = tempershow.TemperShow._build_port_index_map()
        assert result == {'Ethernet0': 1}
        assert captured == [None]  # fell back to a single None namespace

    def test_empty_port_config_is_skipped(self):
        get_port_config = mock.Mock(return_value=({}, {}, {}))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            assert tempershow.TemperShow._build_port_index_map() == {}


class TestSfpDisplayName:
    @staticmethod
    def _instance(port_index_map):
        # Bypass __init__ so no STATE_DB connection is needed.
        inst = tempershow.TemperShow.__new__(tempershow.TemperShow)
        inst._port_index_map = port_index_map
        return inst

    def test_maps_logical_name_to_legacy_label(self):
        inst = self._instance({'Ethernet0': 1, 'Ethernet8': 3})
        assert inst._sfp_display_name('Ethernet0') == 'xSFP module 1 Temp'
        assert inst._sfp_display_name('Ethernet8') == 'xSFP module 3 Temp'

    def test_unknown_port_falls_back_to_logical_name(self):
        inst = self._instance({'Ethernet0': 1})
        assert inst._sfp_display_name('Ethernet999') == 'Ethernet999'

    def test_empty_map_falls_back_to_logical_name(self):
        inst = self._instance({})
        assert inst._sfp_display_name('Ethernet0') == 'Ethernet0'


class TestInit:
    """Cover ``TemperShow.__init__`` DB-config selection and index-map build."""

    def test_single_asic_loads_db_config_when_needed(self):
        with _temper_show(is_init=False) as (inst, db, sonic_db_config, _):
            sonic_db_config.load_sonic_db_config.assert_called_once_with()
            sonic_db_config.load_sonic_global_db_config.assert_not_called()
            assert db.connected == [db.STATE_DB]
            assert inst._port_index_map == {}

    def test_single_asic_skips_db_config_when_initialized(self):
        with _temper_show(is_init=True) as (_inst, _db, sonic_db_config, _ma):
            sonic_db_config.load_sonic_db_config.assert_not_called()

    def test_multi_asic_loads_global_db_config_when_needed(self):
        with _temper_show(is_multi_asic=True, is_global_init=False) as (
                _inst, _db, sonic_db_config, _ma):
            sonic_db_config.load_sonic_global_db_config.assert_called_once_with()
            sonic_db_config.load_sonic_db_config.assert_not_called()

    def test_multi_asic_skips_global_db_config_when_initialized(self):
        with _temper_show(is_multi_asic=True, is_global_init=True) as (
                _inst, _db, sonic_db_config, _ma):
            sonic_db_config.load_sonic_global_db_config.assert_not_called()


class TestGetSfpDbConnections:
    """Cover ``_get_sfp_db_connections`` single- and multi-ASIC fan-out."""

    def test_single_asic_returns_one_host_connection(self):
        db = _FakeDB()
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = False
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            conns = tempershow.TemperShow._get_sfp_db_connections()
        assert conns == [db]
        assert db.connected == [db.STATE_DB]

    def test_multi_asic_returns_a_connection_per_namespace(self):
        ns_conn = {'asic0': mock.Mock(name='asic0-db'),
                   'asic1': mock.Mock(name='asic1-db')}
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = True
        multi_asic.get_front_end_namespaces.return_value = ['asic0', 'asic1']
        multi_asic.connect_to_all_dbs_for_ns.side_effect = lambda ns: ns_conn[ns]
        with mock.patch.object(tempershow, 'multi_asic', multi_asic):
            conns = tempershow.TemperShow._get_sfp_db_connections()
        assert conns == [ns_conn['asic0'], ns_conn['asic1']]

    def test_multi_asic_namespace_lookup_failure_falls_back_to_host(self):
        db = _FakeDB()
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = True
        multi_asic.get_front_end_namespaces.side_effect = RuntimeError('boom')
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            conns = tempershow.TemperShow._get_sfp_db_connections()
        assert conns == [db]

    def test_multi_asic_per_namespace_connect_failure_is_skipped(self):
        good = mock.Mock(name='asic1-db')
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = True
        multi_asic.get_front_end_namespaces.return_value = ['asic0', 'asic1']

        def connect(ns):
            if ns == 'asic0':
                raise RuntimeError('cannot connect')
            return good

        multi_asic.connect_to_all_dbs_for_ns.side_effect = connect
        with mock.patch.object(tempershow, 'multi_asic', multi_asic):
            conns = tempershow.TemperShow._get_sfp_db_connections()
        assert conns == [good]


class TestCollectPlatformSensors:
    """Cover ``_collect_platform_sensors`` against TEMPERATURE_INFO."""

    @staticmethod
    def _instance(data):
        inst = tempershow.TemperShow.__new__(tempershow.TemperShow)
        inst.db = _FakeDB(data)
        inst._port_index_map = {}
        return inst

    def test_returns_a_row_per_sensor(self):
        data = {
            'TEMPERATURE_INFO|CPU': {
                'temperature': '40', 'high_threshold': '90',
                'low_threshold': '0', 'critical_high_threshold': '100',
                'critical_low_threshold': '-10', 'warning_status': 'False',
                'timestamp': '20240101 00:00:00',
            },
        }
        rows = self._instance(data)._collect_platform_sensors()
        assert rows == [{
            'name': 'CPU', 'temperature': '40', 'high_th': '90',
            'low_th': '0', 'crit_high_th': '100', 'crit_low_th': '-10',
            'warning': 'False', 'timestamp': '20240101 00:00:00',
        }]

    def test_missing_fields_default_to_na(self):
        rows = self._instance(
            {'TEMPERATURE_INFO|PSU1': {}})._collect_platform_sensors()
        assert rows[0]['name'] == 'PSU1'
        assert rows[0]['temperature'] == tempershow.NA
        assert rows[0]['warning'] == tempershow.NA

    def test_invalid_key_is_skipped(self, capsys):
        rows = self._instance(
            {'TEMPERATURE_INFO|a|b': {'temperature': '1'}}
        )._collect_platform_sensors()
        assert rows == []
        assert 'Invalid key' in capsys.readouterr().out

    def test_empty_table_returns_no_rows(self):
        assert self._instance({})._collect_platform_sensors() == []


class TestCollectSfpSensors:
    """Cover ``_collect_sfp_sensors`` across the transceiver tables."""

    @staticmethod
    def _instance(port_index_map=None):
        inst = tempershow.TemperShow.__new__(tempershow.TemperShow)
        inst._port_index_map = port_index_map or {}
        return inst

    def test_returns_labelled_rows_with_mapped_thresholds(self):
        data = {
            'TRANSCEIVER_DOM_TEMPERATURE|Ethernet0': {'temperature': '45'},
            'TRANSCEIVER_DOM_THRESHOLD|Ethernet0': {
                'temphighwarning': '70', 'templowwarning': '0',
                'temphighalarm': '80', 'templowalarm': '-5',
            },
            'TRANSCEIVER_DOM_FLAG|Ethernet0': {
                'tempHWarn': 'False', 'tempLWarn': 'False',
                'tempHAlarm': 'False', 'tempLAlarm': 'False',
            },
        }
        db = _FakeDB(data)
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = False
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            rows = self._instance({'Ethernet0': 1})._collect_sfp_sensors()
        assert len(rows) == 1
        row = rows[0]
        assert row['name'] == 'xSFP module 1 Temp'
        assert row['temperature'] == '45'
        assert row['high_th'] == '70'
        assert row['low_th'] == '0'
        assert row['crit_high_th'] == '80'
        assert row['crit_low_th'] == '-5'
        assert row['warning'] == 'False'

    def test_duplicate_ports_across_namespaces_are_deduped(self):
        data = {'TRANSCEIVER_DOM_TEMPERATURE|Ethernet0': {'temperature': '45'}}
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = True
        multi_asic.get_front_end_namespaces.return_value = ['asic0', 'asic1']
        multi_asic.connect_to_all_dbs_for_ns.side_effect = [
            _FakeDB(data), _FakeDB(data)]
        with mock.patch.object(tempershow, 'multi_asic', multi_asic):
            rows = self._instance({'Ethernet0': 1})._collect_sfp_sensors()
        assert len(rows) == 1
        assert rows[0]['name'] == 'xSFP module 1 Temp'

    def test_unmapped_port_falls_back_to_logical_name(self):
        data = {'TRANSCEIVER_DOM_TEMPERATURE|Ethernet8': {'temperature': '50'}}
        db = _FakeDB(data)
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = False
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            rows = self._instance({})._collect_sfp_sensors()
        assert rows[0]['name'] == 'Ethernet8'

    def test_invalid_key_is_skipped(self, capsys):
        data = {'TRANSCEIVER_DOM_TEMPERATURE|a|b': {'temperature': '1'}}
        db = _FakeDB(data)
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = False
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            rows = self._instance()._collect_sfp_sensors()
        assert rows == []
        assert 'Invalid key' in capsys.readouterr().out

    def test_keys_error_on_connection_is_skipped(self):
        db = _FakeDB({}, keys_error=True)
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = False
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            assert self._instance()._collect_sfp_sensors() == []

    def test_empty_temperature_table_returns_no_rows(self):
        db = _FakeDB({})
        multi_asic = mock.Mock()
        multi_asic.is_multi_asic.return_value = False
        with mock.patch.object(tempershow, 'SonicV2Connector', return_value=db), \
             mock.patch.object(tempershow, 'multi_asic', multi_asic):
            assert self._instance()._collect_sfp_sensors() == []


class TestPrefetchTable:
    """Cover ``_prefetch_table`` table materialization and error handling."""

    def test_builds_port_to_fields_map(self):
        data = {
            'TRANSCEIVER_DOM_THRESHOLD|Ethernet0': {'temphighwarning': '70'},
            'TRANSCEIVER_DOM_THRESHOLD|Ethernet4': {'temphighwarning': '71'},
        }
        result = tempershow.TemperShow._prefetch_table(
            _FakeDB(data), 'TRANSCEIVER_DOM_THRESHOLD')
        assert result == {
            'Ethernet0': {'temphighwarning': '70'},
            'Ethernet4': {'temphighwarning': '71'},
        }

    def test_keys_error_returns_empty(self):
        db = _FakeDB({}, keys_error=True)
        assert tempershow.TemperShow._prefetch_table(db, 'ANY') == {}

    def test_empty_table_returns_empty(self):
        assert tempershow.TemperShow._prefetch_table(_FakeDB({}), 'ANY') == {}

    def test_invalid_key_is_skipped(self):
        data = {'T|a|b': {'f': '1'}, 'T|Ethernet0': {'f': '2'}}
        result = tempershow.TemperShow._prefetch_table(_FakeDB(data), 'T')
        assert result == {'Ethernet0': {'f': '2'}}

    def test_get_all_error_is_skipped(self):
        db = _FakeDB({'T|Ethernet0': {'f': '1'}}, get_all_error=True)
        assert tempershow.TemperShow._prefetch_table(db, 'T') == {}


class TestDeriveSfpWarning:
    """Cover ``_derive_sfp_warning`` truth table."""

    def test_empty_flags_returns_na(self):
        assert tempershow.TemperShow._derive_sfp_warning({}) == tempershow.NA

    def test_asserted_flag_returns_true(self):
        assert tempershow.TemperShow._derive_sfp_warning(
            {'tempHAlarm': 'true'}) == 'True'

    def test_all_flags_present_and_deasserted_returns_false(self):
        flags = {'tempHWarn': 'False', 'tempLWarn': 'False',
                 'tempHAlarm': 'False', 'tempLAlarm': 'False'}
        assert tempershow.TemperShow._derive_sfp_warning(flags) == 'False'

    def test_only_unrelated_flags_present_returns_na(self):
        assert tempershow.TemperShow._derive_sfp_warning(
            {'unrelated': 'True'}) == tempershow.NA


class TestShow:
    """Cover ``show`` table, JSON, and empty rendering paths."""

    def test_table_output_lists_sensor(self, capsys):
        data = {'TEMPERATURE_INFO|CPU': {'temperature': '40',
                                         'warning_status': 'False'}}
        with _temper_show(state_data=data) as (inst, *_):
            inst.show(output_json=False)
        out = capsys.readouterr().out
        assert 'CPU' in out
        assert '40' in out

    def test_json_output_is_valid(self, capsys):
        data = {'TEMPERATURE_INFO|CPU': {'temperature': '40'}}
        with _temper_show(state_data=data) as (inst, *_):
            inst.show(output_json=True)
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]['Sensor'] == 'CPU'
        assert payload[0]['Temperature'] == '40'

    def test_no_sensors_reports_not_detected(self, capsys):
        with _temper_show(state_data={}) as (inst, *_):
            inst.show(output_json=False)
        assert 'Thermal Not detected' in capsys.readouterr().out
