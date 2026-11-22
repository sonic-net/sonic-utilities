"""Gearbox display baselines, including namespace-specific clear integration."""

import importlib.machinery
import importlib.util
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from utilities_common import gearbox_stats as stats
from utilities_common.cli import UserCache


GB = stats.GB_COUNTERS_DB
SYMBOL = 'SAI_PORT_STAT_IF_IN_FEC_SYMBOL_ERRORS'
BIN0 = stats.FEC_HISTOGRAM_BINS[0]


def load_script(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / name
    loader = importlib.machinery.SourceFileLoader('gearbox_clear_' + name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def clear_env(tmp_path, monkeypatch):
    monkeypatch.setenv('SONIC_CLI_CACHE_DIR', str(tmp_path))
    portstat = load_script('portstat')
    gearbox = load_script('gearboxutil')
    data, databases, deleted = {}, {}, []
    for ns, count in (('asic0', 100), ('asic1', 300)):
        # Deliberately reuse OIDs and port names across namespaces.
        data[ns] = {
            ('COUNTERS_DB', 'COUNTERS_PORT_NAME_MAP'): {'Ethernet64': 'asic'},
            (GB, 'COUNTERS_PORT_NAME_MAP'): {
                'Ethernet64_line': 'line', 'Ethernet64_system': 'system'},
        }
        for oid, value in (('line', count), ('system', count + 100)):
            data[ns][GB, 'COUNTERS:' + oid] = {
                **{name: str(value) for name in stats.FEC_COUNTERS},
                'NON_FEC_COUNTER': '71',
            }
            data[ns][GB, 'RATES:' + oid] = {
                'FEC_PRE_BER': '1e-8', 'FEC_POST_BER': '0',
                'FEC_PRE_BER_MAX': '2e-8', 'FEC_MAX_T': '15',
            }
        db = mock.MagicMock()
        db.COUNTERS_DB = 'COUNTERS_DB'
        db.get_db_list.return_value = ['COUNTERS_DB', GB]
        db.get_all.side_effect = lambda name, key, ns=ns: dict(data[ns].get((name, key), {}))
        db.get.return_value = 'up'

        def redis_client(name, ns=ns):
            client = mock.Mock()

            def hdel(key, fields):
                deleted.append((ns, name, key, fields))
                for field in fields:
                    data[ns].get((name, key), {}).pop(field, None)

            client.hdel.side_effect = hdel
            return client

        db.get_redis_client.side_effect = redis_client
        databases[ns] = db

    instances = []

    def portstat_factory(namespace, display):
        instance = mock.MagicMock()
        selected = [namespace] if namespace is not None else list(databases)
        instance.multi_asic.get_ns_list_based_on_options.return_value = selected
        instance.get_db_client.side_effect = databases.__getitem__
        instance.get_cnstat_dict.return_value = ({
            'time': 'new clear',
            **{ns + '_interface': {'rx_ok': '123'} for ns in selected},
        }, {})
        instances.append(instance)
        return instance

    monkeypatch.setattr(portstat, 'Portstat', portstat_factory)
    monkeypatch.setattr(gearbox, 'SonicV2Connector',
                        lambda namespace='', **kwargs: databases[namespace or 'asic0'])

    def clear(namespace=None, tag=None):
        argv = ['portstat', '-c']
        if namespace is not None:
            argv += ['-n', namespace]
        if tag is not None:
            argv += ['-t', tag]
        with mock.patch.object(sys, 'argv', argv), pytest.raises(SystemExit) as result:
            portstat.main()
        assert result.value.code == 0

    def display(namespace='asic0', display_type='stats'):
        return gearbox.InterfaceFecStats('Ethernet64', display_type, namespace)

    return mock.Mock(data=data, databases=databases, deleted=deleted, clear=clear,
                     display=display, instances=instances, portstat=portstat)


def cache_file(tag=None):
    return Path(UserCache(app_name='portstat', tag=tag).get_directory()) / 'portstat'


def test_snapshot_keeps_both_sides_and_only_fec_fields(clear_env):
    before = deepcopy(clear_env.data)
    saved = stats.snapshot_gearbox_counters(clear_env.databases['asic0'])
    assert set(saved) == {'line', 'system'}
    assert set(saved['line']) == set(stats.FEC_COUNTERS)
    assert saved['line'][SYMBOL] == '100'
    assert saved['system'][SYMBOL] == '200'
    assert clear_env.data == before
    assert not clear_env.deleted


def test_clear_and_show_all_asics_both_sides(clear_env, capsys):
    before = deepcopy(clear_env.data)
    clear_env.clear()
    saved = json.loads(cache_file().read_text())
    assert set(saved[stats.GEARBOX_CACHE_KEY]) == {'asic0', 'asic1'}
    assert saved['asic0_interface'] == {'rx_ok': '123'}
    for ns in ('asic0', 'asic1'):
        for display_type in ('stats', 'histogram'):
            view = clear_env.display(ns, display_type)
            for oid in ('line', 'system'):
                counters = view.get_counters_for_oid(oid)
                assert all(counters[name] == '0' for name in stats.FEC_COUNTERS)
                assert counters['NON_FEC_COUNTER'] == '71'
                assert clear_env.data[ns][GB, 'COUNTERS:' + oid] == before[ns][GB, 'COUNTERS:' + oid]
                rates = view.get_rates_for_oid(oid)
                assert rates['FEC_PRE_BER'] == '1e-8'
                assert rates['FEC_POST_BER'] == '0'
                assert 'FEC_PRE_BER_MAX' not in rates
    # The valid histogram header contains "Symbol Errors Per Codeword".
    assert not any(line.lstrip().startswith('Error')
                   for line in capsys.readouterr().out.splitlines())
    assert {row[0] for row in clear_env.deleted} == {'asic0', 'asic1'}
    assert all(row[3] == ('FEC_PRE_BER_MAX',) for row in clear_env.deleted)


def test_namespace_clear_preserves_other_asic(clear_env):
    clear_env.clear()
    original = json.loads(cache_file().read_text())
    clear_env.data['asic0'][GB, 'COUNTERS:line'][SYMBOL] = '105'
    clear_env.data['asic1'][GB, 'COUNTERS:line'][SYMBOL] = '311'
    clear_env.data['asic1'][GB, 'RATES:line']['FEC_PRE_BER_MAX'] = '3e-8'
    clear_env.deleted.clear()
    clear_env.clear('asic0')
    saved = json.loads(cache_file().read_text())
    assert saved[stats.GEARBOX_CACHE_KEY]['asic1'] == original[stats.GEARBOX_CACHE_KEY]['asic1']
    assert saved['asic1_interface'] == original['asic1_interface']
    assert clear_env.display('asic0').get_counters_for_oid('line')[SYMBOL] == '0'
    assert clear_env.display('asic1').get_counters_for_oid('line')[SYMBOL] == '11'
    assert clear_env.data['asic1'][GB, 'RATES:line']['FEC_PRE_BER_MAX'] == '3e-8'
    assert {row[0] for row in clear_env.deleted} == {'asic0'}


def test_namespace_clear_without_previous_cache(clear_env):
    clear_env.clear('asic1')
    assert stats.load_gearbox_baseline('asic0') == {}
    assert clear_env.display('asic0').get_counters_for_oid('line')[SYMBOL] == '100'
    assert clear_env.display('asic1').get_counters_for_oid('line')[SYMBOL] == '0'


def test_new_errors_and_histogram_maximum_after_clear(clear_env, capsys):
    clear_env.clear()
    raw = clear_env.data['asic0'][GB, 'COUNTERS:line']
    raw[SYMBOL] = '103'
    raw[stats.FEC_HISTOGRAM_BINS[7]] = '104'
    view = clear_env.display()
    counts = view.get_counters_for_oid('line')
    assert counts[SYMBOL] == '3'
    assert counts[stats.FEC_HISTOGRAM_BINS[7]] == '4'
    assert stats.get_gearbox_fec_max_t(counts, '15') == '7'
    assert stats.get_gearbox_fec_max_t(view.get_counters_for_oid('system'), '15') == '-1'
    # Also verify that the displayed row uses the baseline-derived maximum.
    rows = [line.split() for line in capsys.readouterr().out.splitlines()
            if 'Ethernet64 Line' in line]
    assert rows[-1][-1] == '7'


def test_repeated_clear_uses_raw_counts(clear_env):
    clear_env.clear()
    clear_env.data['asic0'][GB, 'COUNTERS:line'][SYMBOL] = '109'
    clear_env.clear('asic0')
    assert stats.load_gearbox_baseline('asic0')['line'][SYMBOL] == '109'
    assert clear_env.display().get_counters_for_oid('line')[SYMBOL] == '0'


def test_line_only_polling_keeps_missing_system_counters_empty(clear_env):
    del clear_env.data['asic0'][GB, 'COUNTERS:system']
    clear_env.clear('asic0')
    view = clear_env.display()
    assert view.get_counters_for_oid('line')[SYMBOL] == '0'
    assert view.get_counters_for_oid('system') == {}


def test_recreated_port_ignores_old_oid(clear_env):
    clear_env.clear('asic0')
    data = clear_env.data['asic0']
    data[GB, 'COUNTERS_PORT_NAME_MAP']['Ethernet64_line'] = 'new_line'
    data[GB, 'COUNTERS:new_line'] = {SYMBOL: '7'}
    assert clear_env.display().get_counters_for_oid('new_line')[SYMBOL] == '7'


def test_platform_without_gearbox_database(clear_env):
    for db in clear_env.databases.values():
        db.get_db_list.return_value = ['COUNTERS_DB']
    clear_env.clear()
    assert stats.GEARBOX_CACHE_KEY not in json.loads(cache_file().read_text())
    for db in clear_env.databases.values():
        assert all(call.args[0] == 'COUNTERS_DB' for call in db.get_all.call_args_list)


def test_tagged_clear_preserves_default_baseline_and_rates(clear_env):
    clear_env.clear()
    default = cache_file().read_text()
    raw = clear_env.data['asic0']
    raw[GB, 'COUNTERS:line'][SYMBOL] = '109'
    raw[GB, 'RATES:line']['FEC_PRE_BER_MAX'] = '3e-8'
    clear_env.deleted.clear()
    clear_env.clear('asic0', tag='test')
    assert json.loads(cache_file('test').read_text())[stats.GEARBOX_CACHE_KEY]['asic0']['line'][SYMBOL] == '109'
    assert cache_file().read_text() == default
    assert clear_env.display().get_counters_for_oid('line')[SYMBOL] == '9'
    assert raw[GB, 'RATES:line']['FEC_PRE_BER_MAX'] == '3e-8'
    assert not clear_env.deleted


@pytest.mark.parametrize('error', [RuntimeError('gearbox unavailable'), OSError('read failure')])
def test_failed_gearbox_snapshot_preserves_cache_and_rates(clear_env, monkeypatch, error):
    clear_env.clear()
    original = cache_file().read_text()
    clear_env.deleted.clear()
    monkeypatch.setattr(clear_env.portstat, 'snapshot_gearbox_counters',
                        mock.Mock(side_effect=error))
    with mock.patch.object(sys, 'argv', ['portstat', '-c', '-n', 'asic0']), \
            pytest.raises(SystemExit, match='Failed to read gearbox counters'):
        clear_env.portstat.main()
    assert cache_file().read_text() == original
    assert not clear_env.deleted


@pytest.mark.parametrize('current,baseline,expected', [
    (100, 100, '0'), (109, 100, '9'), (2, 100, '2'),
    (2**63 + 6, 2**63 + 5, '1'),
])
def test_subtract_preserves_integer_precision_and_handles_reset(current, baseline, expected):
    counters = {SYMBOL: str(current), 'OTHER': '70'}
    result = stats.subtract_gearbox_baseline(counters, {SYMBOL: str(baseline), BIN0: '1'})
    assert result == {SYMBOL: expected, 'OTHER': '70'}
    assert counters[SYMBOL] == str(current)


def test_maximum_without_histogram_keeps_rate_value():
    assert stats.get_gearbox_fec_max_t({SYMBOL: '1'}, '9') == '9'


@pytest.mark.parametrize('contents', [None, '{"time": "legacy clear"}',
                                      '{invalid', '[]', '{"_gearbox": []}'])
def test_missing_legacy_and_invalid_cache_use_raw_counts(clear_env, contents):
    if contents is not None:
        cache_file().write_text(contents)
    assert stats.load_gearbox_baseline('asic0') == {}
    assert clear_env.display().get_counters_for_oid('line')[SYMBOL] == '100'


def test_default_namespace_and_user_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv('SONIC_CLI_CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(os, 'getuid', lambda: 1000)
    cache_file().write_text(json.dumps({stats.GEARBOX_CACHE_KEY: {'': {'line': {SYMBOL: '7'}}}}))
    assert stats.load_gearbox_baseline(None) == stats.load_gearbox_baseline('') == {'line': {SYMBOL: '7'}}
    monkeypatch.setattr(os, 'getuid', lambda: 2000)
    assert stats.load_gearbox_baseline('') == {}
