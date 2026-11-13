"""IS-IS northbound contract, including gs1571 AF/MT/reset regression coverage."""
import copy
import os
from unittest import mock

import pytest
from click.testing import CliRunner
import config.main as config
import show.main as show
from utilities_common.db import Db
from sonic_isis import SNAPSHOT_TABLES, capture, commit

NET = '49.0001.0000.0000.0001.00'


@pytest.fixture
def isis_db(monkeypatch):
    db = Db()
    original = {table: copy.deepcopy(db.cfgdb.get_table(table)) for table in SNAPSHOT_TABLES}
    for table in SNAPSHOT_TABLES:
        for key in db.cfgdb.get_table(table):
            db.cfgdb.set_entry(table, key, None)
    db.cfgdb.set_entry('PORT', 'Ethernet0', {'alias': 'etp1'})
    db.cfgdb.set_entry('INTERFACE', 'Ethernet0', {'NULL': 'NULL'})
    db.cfgdb.set_entry('ISIS_INSTANCE', ('default', 'CORE'), {'enabled': 'false', 'net_titles': [NET]})
    # Standard sonic-utilities fixtures use mockredis, which does not implement
    # Lua. Local native-Redis mode executes the production capture/CAS scripts.
    if not os.environ.get('ISIS_TEST_REDIS'):
        def snapshot(connector):
            return {table: connector.get_table(table) for table in SNAPSHOT_TABLES}

        def fake_commit(connector, before, updates):
            if snapshot(connector) != before:
                raise ValueError('configuration changed; retry')
            for table, key, row in updates:
                connector.set_entry(table, key, row)
        monkeypatch.setattr('config.isis.capture', snapshot)
        monkeypatch.setattr('config.isis.commit', fake_commit)
    yield db
    for table in SNAPSHOT_TABLES:
        for key in db.cfgdb.get_table(table):
            db.cfgdb.set_entry(table, key, None)
        for key, row in original[table].items():
            db.cfgdb.set_entry(table, key, row)


def invoke(db, *args, interface=False):
    group = config.config.commands['interface'].commands['isis'] if interface else config.config.commands['isis']
    obj = {'config_db': db.cfgdb, 'namespace': ''} if interface else db
    return CliRunner().invoke(group, list(args), obj=obj)


def ok(db, *args, **kwargs):
    result = invoke(db, *args, **kwargs)
    assert result.exit_code == 0, result.output or str(result.exception)
    return result


def test_instance_lifecycle_and_reference_guard(isis_db):
    db = isis_db
    ok(db, 'instance', 'add', 'CORE')
    assert db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE'))['net_titles'] == [NET]
    ok(db, 'bind', 'Ethernet0', 'CORE', interface=True)
    ok(db, 'set', 'CORE', 'lsp-mtu', '1492')
    ok(db, 'instance', 'enable', 'CORE')
    ok(db, 'af', 'Ethernet0', 'ipv6', 'enable', interface=True)
    ok(db, 'enable', 'Ethernet0', interface=True)
    original = db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')
    ok(db, 'instance', 'disable', 'CORE')
    assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == original
    assert db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE'))['lsp_mtu'] == '1492'
    ok(db, 'disable', 'Ethernet0', interface=True)
    with mock.patch('config.isis.log.log_error') as log:
        rejected = invoke(db, 'instance', 'del', 'CORE')
        assert rejected.exit_code != 0
        log.assert_not_called()
    ok(db, 'level', 'set', 'Ethernet0', 'both', 'metric', '30', interface=True)
    ok(db, 'instance', 'enable', 'CORE')
    ok(db, 'enable', 'Ethernet0', interface=True)
    assert db.cfgdb.get_entry('ISIS_INTERFACE_LEVEL', ('Ethernet0', 'level-1'))['metric'] == '30'
    ok(db, 'unbind', 'Ethernet0', interface=True)
    assert not db.cfgdb.get_table('ISIS_INTERFACE_LEVEL')
    ok(db, 'instance', 'del', 'CORE')
    assert not db.cfgdb.get_table('ISIS_INSTANCE')


@pytest.mark.parametrize('family', ['ipv4', 'ipv6'])
def test_independent_af_controls_and_reset_while_disabled(isis_db, family):
    db = isis_db
    ok(db, 'bind', 'Ethernet0', 'CORE', interface=True)
    ok(db, 'set', 'Ethernet0', 'passive', 'true', interface=True)
    original = db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')
    for state, value in [('enable', 'true'), ('disable', 'false')]:
        ok(db, 'af', 'Ethernet0', family, state, interface=True)
        assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == dict(original, **{family + '_enabled': value})
    ok(db, 'af', 'Ethernet0', family, 'reset', interface=True)
    assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == original
    assert invoke(db, 'af', 'Ethernet0', family, 'invalid', interface=True).exit_code == 2


def test_mt_is_distinct_from_interface_af_and_reset_preserves_fields(isis_db):
    db = isis_db
    ok(db, 'bind', 'Ethernet0', 'CORE', interface=True)
    before = db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')
    ok(db, 'set', 'CORE', 'ipv6-multi-topology', 'true')
    ok(db, 'reset', 'CORE', 'ipv6-multi-topology')
    assert 'ipv6_multi_topology' not in db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE'))
    assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == before
    assert db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE'))['net_titles'] == [NET]


def test_explicit_binding_vrf_and_interface_validation(isis_db):
    db = isis_db
    assert invoke(db, 'enable', 'Ethernet0', interface=True).exit_code != 0
    assert invoke(db, 'bind', 'Ethernet0', 'MISSING', interface=True).exit_code != 0
    assert invoke(db, 'bind', 'Ethernet0', 'CORE', '--vrf', 'VrfA', interface=True).exit_code != 0
    for table in ('PORTCHANNEL_MEMBER', 'VLAN_MEMBER'):
        db.cfgdb.set_entry(table, ('group', 'Ethernet0'), {'NULL': 'NULL'})
        assert invoke(db, 'bind', 'Ethernet0', 'CORE', interface=True).exit_code != 0
        db.cfgdb.set_entry(table, ('group', 'Ethernet0'), None)
    with mock.patch('utilities_common.cli.get_interface_naming_mode', return_value='alias'):
        ok(db, 'bind', 'etp1', 'CORE', interface=True)
    db.cfgdb.set_entry('VRF', 'VrfA', {'NULL': 'NULL'})
    ok(db, 'instance', 'add', 'CORE', '--vrf', 'VrfA')
    db.cfgdb.set_entry('INTERFACE', 'Ethernet0', {'vrf_name': 'VrfA'})
    assert invoke(db, 'enable', 'Ethernet0', interface=True).exit_code != 0
    assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')['vrf'] == 'default'
    ok(db, 'bind', 'Ethernet0', 'CORE', interface=True)
    assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')['vrf'] == 'VrfA'
    # Removal remains possible after the routed interface disappears.
    db.cfgdb.set_entry('INTERFACE', 'Ethernet0', None)
    db.cfgdb.set_entry('PORT', 'Ethernet0', None)
    ok(db, 'unbind', 'Ethernet0', interface=True)


def test_net_and_instance_identity(isis_db):
    db = isis_db
    ok(db, 'instance', 'add', 'EDGE')
    assert invoke(db, 'instance', 'enable', 'EDGE').exit_code != 0
    assert invoke(db, 'net', 'add', 'EDGE', '49.0001.00').exit_code != 0
    ok(db, 'net', 'add', 'EDGE', NET)
    ok(db, 'instance', 'enable', 'EDGE')
    assert invoke(db, 'net', 'del', 'EDGE', NET).exit_code != 0
    assert invoke(db, 'net', 'add', 'EDGE', '49.0001.0000.0000.0002.00').exit_code != 0
    ok(db, 'net', 'add', 'EDGE', '49.0002.0000.0000.0001.00')
    ok(db, 'instance', 'disable', 'EDGE')
    ok(db, 'net', 'del', 'EDGE', NET)
    assert db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE'))['net_titles'] == [NET]


def test_level_values_both_and_single_reset(isis_db):
    db = isis_db
    ok(db, 'level', 'set', 'CORE', 'both', 'lsp-maximum-lifetime', '1500')
    ok(db, 'level', 'set', 'CORE', 'both', 'lsp-refresh-interval', '1000')
    original = copy.deepcopy(db.cfgdb.get_table('ISIS_INSTANCE_LEVEL'))
    assert invoke(db, 'level', 'reset', 'CORE', 'both', 'lsp-maximum-lifetime').exit_code != 0
    assert db.cfgdb.get_table('ISIS_INSTANCE_LEVEL') == original
    ok(db, 'level', 'reset', 'CORE', 'level-1', 'lsp-refresh-interval')
    assert 'lsp_refresh_interval' not in db.cfgdb.get_entry('ISIS_INSTANCE_LEVEL', ('default', 'CORE', 'level-1'))
    assert db.cfgdb.get_entry('ISIS_INSTANCE_LEVEL', ('default', 'CORE', 'level-2'))['lsp_refresh_interval'] == '1000'
    ok(db, 'instance', 'del', 'CORE')
    assert not db.cfgdb.get_table('ISIS_INSTANCE_LEVEL')


def test_overload_spf_redistribution_and_reset(isis_db):
    db = isis_db
    ok(db, 'set', 'CORE', 'overload', 'true')
    ok(db, 'set', 'CORE', 'overload-on-startup', '30')
    assert invoke(db, 'set', 'CORE', 'overload-on-startup', '86401').exit_code != 0
    assert invoke(db, 'spf-backoff', 'set', 'CORE', '1', '10', '100', '100', '100').exit_code != 0
    ok(db, 'spf-backoff', 'set', 'CORE', '1', '10', '100', '1000', '500')
    ok(db, 'spf-backoff', 'reset', 'CORE')
    assert not any(field.startswith('spf_') for field in db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE')))
    assert invoke(db, 'redistribute', 'add', 'CORE', 'ipv6', 'ospf', 'level-1').exit_code != 0
    assert invoke(db, 'redistribute', 'add', 'CORE', 'ipv4', 'static', 'level-1',
                  '--route-map', 'MISSING').exit_code != 0
    db.cfgdb.set_entry('ROUTE_MAP_SET', 'EXPORT', {'NULL': 'NULL'})
    ok(db, 'redistribute', 'add', 'CORE', 'ipv4', 'static', 'level-1', '--route-map', 'EXPORT', '--metric', '20')
    assert invoke(db, 'set', 'CORE', 'level-type', 'level-2-only').exit_code != 0
    ok(db, 'redistribute', 'del', 'CORE', 'ipv4', 'static', 'level-1')
    ok(db, 'set', 'CORE', 'level-type', 'level-2-only')


def test_namespace_selects_connector(isis_db):
    group = config.config.commands['isis']
    option = next(p for p in group.params if p.name == 'namespace')
    with mock.patch.object(option.type, 'choices', ['asic0']), \
            mock.patch('config.isis.ConfigDBConnector', return_value=isis_db.cfgdb) as connector:
        ok(isis_db, '-n', 'asic0', 'set', 'CORE', 'overload', 'true')
        connector.assert_called_once_with(use_unix_socket_path=True, namespace='asic0')


def test_database_failure_does_not_report_success(isis_db):
    original = isis_db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE'))
    with mock.patch('config.isis.commit', side_effect=RuntimeError('write failed')):
        result = invoke(isis_db, 'set', 'CORE', 'overload', 'true')
    assert result.exit_code != 0 and 'write failed' in result.output
    assert isis_db.cfgdb.get_entry('ISIS_INSTANCE', ('default', 'CORE')) == original


@pytest.mark.skipif(not os.environ.get('ISIS_TEST_REDIS'), reason='requires native Redis Lua evaluation')
def test_native_redis_transaction_rejects_concurrent_insert(isis_db):
    db = isis_db.cfgdb
    before = capture(db)
    db.set_entry('ISIS_INTERFACE', 'Ethernet0', {'vrf': 'default', 'instance': 'CORE', 'enabled': 'false'})
    with pytest.raises(Exception, match='changed; retry'):
        commit(db, before, [('ISIS_INSTANCE', ('default', 'CORE'), None)])
    assert db.get_entry('ISIS_INSTANCE', ('default', 'CORE'))


@mock.patch('utilities_common.bgp_util.get_vtysh_shell_cmd', return_value='vtysh')
@mock.patch('utilities_common.cli.run_command')
def test_show_failure_is_not_empty_success(run, shell):
    run.return_value = ('', 1)
    result = CliRunner().invoke(show.cli.commands['isis'].commands['database'], [])
    assert result.exit_code == 1


@pytest.mark.parametrize('command', ['summary', 'neighbor', 'database', 'interface', 'route', 'topology', 'hostname'])
@mock.patch('utilities_common.bgp_util.get_vtysh_shell_cmd', return_value='rvtysh')
@mock.patch('utilities_common.bgp_util.run_bgp_command', return_value='native state\n')
def test_show_vrf_and_namespace(run, shell, command):
    result = CliRunner().invoke(show.cli.commands['isis'].commands[command], ['--vrf', 'VrfA'])
    assert result.exit_code == 0, result.output
    run.assert_called_once_with('show isis vrf VrfA ' + command, '', 'rvtysh')


@mock.patch('utilities_common.bgp_util.run_bgp_command')
def test_show_instance_filters_only_scoped_areas(run):
    run.return_value = '{"areas":[{"area":"CORE","circuits":[]},{"area":"EDGE","circuits":[]}]}'
    group = show.cli.commands['isis'].commands['interface']
    result = CliRunner().invoke(group, ['--json', '--instance', 'CORE'])
    assert result.exit_code == 0
    assert 'EDGE' not in result.output and 'CORE' in result.output
    assert CliRunner().invoke(group, ['--instance', 'CORE']).exit_code != 0
    assert CliRunner().invoke(group, ['--json', '--vrf', 'all']).exit_code != 0
    run.return_value = '{"unknown":[]}'
    assert CliRunner().invoke(group, ['--json', '--instance', 'CORE']).exit_code != 0


@mock.patch('utilities_common.bgp_util.run_bgp_command')
def test_show_route_rejects_lossy_native_json(run):
    run.return_value = '{"vrfs":[{"vrf":"default","areas":[{"area":"CORE"},{"area":"EDGE"}]}]}'
    result = CliRunner().invoke(show.cli.commands['isis'].commands['route'], ['--json'])
    assert result.exit_code != 0 and 'loses multiple areas' in result.output
    assert run.call_count == 1


def test_cleanup_is_idempotent_and_does_not_require_stale_parent(isis_db):
    db = isis_db
    ok(db, 'unbind', 'Ethernet0', interface=True)
    ok(db, 'instance', 'del', 'MISSING')
    db.cfgdb.set_entry('ISIS_INTERFACE', 'Ethernet0', {'vrf': 'default', 'instance': 'MISSING'})
    db.cfgdb.set_entry('ISIS_INTERFACE_LEVEL', ('Ethernet0', 'level-1'), {'metric': '20'})
    ok(db, 'unbind', 'Ethernet0', interface=True)
    assert not db.cfgdb.get_table('ISIS_INTERFACE_LEVEL')
    ok(db, 'unbind', 'Ethernet0', interface=True)


@mock.patch('utilities_common.bgp_util.run_bgp_command')
def test_show_rejects_invalid_json_and_missing_area_identity(run):
    group = show.cli.commands['isis'].commands['interface']
    for output in ('ISIS is not running', '{"areas":[{}]}'):
        run.return_value = output
        result = CliRunner().invoke(group, ['--json', '--instance', 'CORE'])
        assert result.exit_code != 0
    run.return_value = 'ISIS is not running'
    assert CliRunner().invoke(group, ['--json']).exit_code != 0


@pytest.mark.parametrize('action', ['disable', 'del'])
def test_multi_area_retirement_is_refused_without_configdb_change(isis_db, action):
    ok(isis_db, 'instance', 'enable', 'CORE')
    ok(isis_db, 'instance', 'add', 'EDGE')
    ok(isis_db, 'net', 'add', 'EDGE', '49.0002.0000.0000.0001.00')
    ok(isis_db, 'instance', 'enable', 'EDGE')
    before = copy.deepcopy(isis_db.cfgdb.get_table('ISIS_INSTANCE'))
    result = invoke(isis_db, 'instance', action, 'EDGE')
    assert result.exit_code != 0 and 'operation refused until FRR is fixed' in result.output
    assert isis_db.cfgdb.get_table('ISIS_INSTANCE') == before
