"""Sampled binding CLI tests with isolated ConfigDB state."""
from copy import deepcopy
from unittest import mock

import pytest
from click.testing import CliRunner

import config.main as config
from utilities_common import port_mirror


class Database:
    def __init__(self):
        self.tables = {
            'PORT': {'Ethernet0': {'alias': 'Eth0'}, 'Ethernet4': {}},
            'PORTCHANNEL': {'PortChannel1': {}},
            'PORTCHANNEL_MEMBER': {('PortChannel1', 'Ethernet0'): {}},
            'MIRROR_SESSION': {'export1': {'type': 'ERSPAN'}, 'export2': {'type': 'ERSPAN'}},
        }
        self.writes = []

    def get_table(self, table):
        return deepcopy(self.tables.get(table, {}))

    def get_keys(self, table):
        return list(self.tables.get(table, {}))

    def get_entry(self, table, key):
        return deepcopy(self.tables.get(table, {}).get(key, {}))

    def set_entry(self, table, key, value):
        self.writes.append((table, key, deepcopy(value)))
        if value is None:
            self.tables.get(table, {}).pop(key, None)
        else:
            self.tables.setdefault(table, {})[key] = deepcopy(value)


@pytest.fixture
def database(monkeypatch):
    db = Database()
    monkeypatch.setattr(port_mirror, 'config_databases', lambda host_db=None, **kwargs: {'': db})
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: False)
    monkeypatch.setattr(config.clicommon, 'get_interface_naming_mode', lambda: 'default')
    state = mock.Mock()
    state.get.return_value = 'true'
    monkeypatch.setattr(config, 'SonicV2Connector', lambda **kwargs: state)
    return db


def invoke(args):
    return CliRunner().invoke(config.config.commands['mirror_session'], args)


@pytest.mark.parametrize('direction,expected', [('rx', ['rx']), ('tx', ['tx']), ('both', ['rx', 'tx'])])
@pytest.mark.parametrize('disabled', [False, True])
def test_add_binding(database, direction, expected, disabled):
    exports = database.get_table('MIRROR_SESSION')
    args = ['sample', 'add', 'export1', 'Ethernet4', direction, '--sample_rate', '1000']
    if disabled:
        args.append('--disabled')
    result = invoke(args)
    assert result.exit_code == 0, result.output
    assert database.get_table('PORT_MIRROR_SAMPLE') == {
        ('Ethernet4', d): {
            'mirror_session': 'export1', 'sample_rate': '1000',
            'admin_state': 'down' if disabled else 'up',
        } for d in expected
    }
    assert database.get_table('MIRROR_SESSION') == exports


@pytest.mark.parametrize('rate', ['2', '4294967295'])
@pytest.mark.parametrize('truncate', ['64', '9216'])
def test_policy_boundaries_and_logical_portchannel(database, rate, truncate):
    result = invoke(['sample', 'add', 'export1', 'PortChannel1', 'rx',
                     '--sample_rate', rate, '--truncate_size', truncate])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('PortChannel1', 'rx')]
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('PortChannel1', 'rx'))['truncate_size'] == truncate


@pytest.mark.parametrize('options', [[], ['--sample_rate', '0'], ['--sample_rate', '1'],
                                     ['--sample_rate', '4294967296'], ['--sample_rate', '-1'],
                                     ['--sample_rate', '2', '--truncate_size', '0'],
                                     ['--sample_rate', '2', '--truncate_size', '63'],
                                     ['--sample_rate', '2', '--truncate_size', '9217']])
def test_invalid_policy_never_writes(database, options):
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx'] + options)
    assert result.exit_code != 0
    assert database.writes == []


@pytest.mark.parametrize('global_entry', [{}, {'admin_state': 'down'}, {'admin_state': 'up'}])
def test_sflow_global_blocks_even_disabled_binding(database, global_entry):
    database.tables['SFLOW'] = {'global': global_entry}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2', '--disabled'])
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output
    assert database.writes == []


@pytest.mark.parametrize('session,port,expected', [
    ('missing', 'Ethernet4', 'does not exist'),
    ('span', 'Ethernet4', 'ERSPAN'),
    ('source', 'Ethernet4', 'src_port'),
    ('export1', 'Vlan100', 'Source interface'),
])
def test_invalid_references(database, session, port, expected):
    database.tables['MIRROR_SESSION']['span'] = {'type': 'SPAN'}
    database.tables['MIRROR_SESSION']['source'] = {'type': 'ERSPAN', 'src_port': ''}
    result = invoke(['sample', 'add', session, port, 'rx', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert expected in result.output
    assert not database.writes


def test_both_duplicate_prevents_partial_write(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'tx'): {'mirror_session': 'export2'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert not database.writes


@pytest.mark.parametrize('existing,new', [('PortChannel1', 'Ethernet0'), ('Ethernet0', 'PortChannel1')])
def test_portchannel_member_overlap(database, existing, new):
    database.tables['PORT_MIRROR_SAMPLE'] = {(existing, 'rx'): {'mirror_session': 'export2'}}
    result = invoke(['sample', 'add', 'export1', new, 'rx', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert not database.writes


def test_remove_both_checks_all_references_first(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {
        ('Ethernet4', 'rx'): {'mirror_session': 'export1'},
        ('Ethernet4', 'tx'): {'mirror_session': 'export2'},
    }
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'both'])
    assert result.exit_code != 0
    assert 'different mirror session' in result.output
    assert not database.writes


@pytest.mark.parametrize('directions', [['rx'], ['tx'], ['rx', 'tx']])
def test_remove_both_allows_missing_direction_and_preserves_export(database, directions):
    exports = database.get_table('MIRROR_SESSION')
    database.tables['PORT_MIRROR_SAMPLE'] = {
        ('Ethernet4', d): {'mirror_session': 'export1'} for d in directions
    }
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'both'])
    assert result.exit_code == 0, result.output
    assert not database.get_keys('PORT_MIRROR_SAMPLE')
    assert database.get_table('MIRROR_SESSION') == exports


def test_remove_missing_binding(database):
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'rx'])
    assert result.exit_code != 0
    assert 'No matching' in result.output
    assert not database.writes


def test_yang_enabled_both_submitted_in_one_patch(database, monkeypatch):
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    monkeypatch.setattr(config, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output
    updater.apply_patch.assert_called_once()
    patch = updater.apply_patch.call_args.kwargs['patch'].patch
    assert [op['path'] for op in patch] == [
        '/PORT_MIRROR_SAMPLE', '/PORT_MIRROR_SAMPLE/Ethernet4|rx', '/PORT_MIRROR_SAMPLE/Ethernet4|tx']
    assert not database.writes


@pytest.mark.parametrize('command,args', [
    ('enable', []), ('disable', []), ('polling-interval', ['20']),
    ('sample-direction', ['rx']), ('drop-monitor-limit', ['0']),
])
def test_global_sflow_commands_reject_with_binding(database, command, args):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'admin_state': 'down'}}
    before = deepcopy(database.tables)
    result = CliRunner().invoke(config.config.commands['sflow'].commands[command], args, obj={'db': database})
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output
    assert database.tables == before


@pytest.mark.parametrize('command,args', [('add', ['Ethernet0']), ('del', [])])
def test_sflow_agent_commands_reject_with_binding(database, command, args):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'admin_state': 'down'}}
    database.tables['SFLOW'] = {'global': {'admin_state': 'down', 'agent_id': 'Ethernet0'}}
    result = CliRunner().invoke(config.config.commands['sflow'].commands['agent-id'].commands[command],
                                args, obj={'db': database})
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output
    assert not database.writes


def test_export_delete_rejects_referenced_session(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'mirror_session': 'export1'}}
    result = invoke(['remove', 'export1'])
    assert result.exit_code != 0
    assert 'referenced by a sampled binding' in result.output
    assert not database.writes


def test_namespace_and_alias_resolution(database, monkeypatch):
    host = Database()
    host.tables['PORT'] = {}
    other = Database()
    other.tables['PORT'] = {}
    other.tables['PORTCHANNEL'] = {}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda host_db=None:
                        {'': host, 'asic0': other, 'asic1': database})
    monkeypatch.setattr(config.clicommon, 'get_interface_naming_mode', lambda: 'alias')
    result = invoke(['sample', 'add', 'export1', 'Eth0', 'rx', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('Ethernet0', 'rx')]
    assert not host.writes and not other.writes
    other.tables['SFLOW'] = {'global': {'admin_state': 'down'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output


def test_explicit_unsupported_capability_rejects_both(database, monkeypatch):
    state = mock.Mock()
    state.get.side_effect = lambda db, key, field: 'false' if 'EGRESS' in field else 'true'
    monkeypatch.setattr(config, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert 'not supported' in result.output
    assert not database.writes


@pytest.mark.parametrize('capability', [None, 'true', 'false'])
def test_truncation_capability(database, monkeypatch, capability):
    state = mock.Mock()
    state.get.side_effect = lambda db, key, field: capability if 'TRUNCATION' in field else 'true'
    monkeypatch.setattr(config, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx',
                     '--sample_rate', '2', '--truncate_size', '128'])
    assert (result.exit_code == 0) == (capability != 'false'), result.output
    if capability == 'false':
        assert not database.writes


def test_capability_service_failure_does_not_write(database, monkeypatch):
    monkeypatch.setattr(config, 'SonicV2Connector', mock.Mock(side_effect=RuntimeError('unavailable')))
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert 'Unable to read sampled mirror capabilities' in result.output
    assert not database.writes


def test_missing_direction_capabilities_allow_configuration(database, monkeypatch):
    state = mock.Mock()
    state.get.return_value = None
    monkeypatch.setattr(config, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('Ethernet4', 'rx'), ('Ethernet4', 'tx')]


def test_partial_capability_read_failure_does_not_bypass_rejection(database, monkeypatch):
    state = mock.Mock()
    state.get.side_effect = ['false', RuntimeError('STATE_DB read failed')]
    monkeypatch.setattr(config, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert not database.writes


def test_sflow_sessions_without_global_do_not_conflict(database):
    database.tables['SFLOW_SESSION'] = {'Ethernet4': {'admin_state': 'up'}}
    database.tables['SFLOW_COLLECTOR'] = {'collector': {'collector_ip': '10.0.0.1'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('keep_other', [False, True])
def test_yang_remove_avoids_empty_table(database, monkeypatch, keep_other):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'mirror_session': 'export1'}}
    if keep_other:
        database.tables['PORT_MIRROR_SAMPLE'][('Ethernet0', 'tx')] = {'mirror_session': 'export2'}
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    monkeypatch.setattr(config, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'rx'])
    assert result.exit_code == 0, result.output
    expected_path = '/PORT_MIRROR_SAMPLE/Ethernet4|rx' if keep_other else '/PORT_MIRROR_SAMPLE'
    assert updater.apply_patch.call_args.kwargs['patch'].patch == [{'op': 'remove', 'path': expected_path}]
    assert not database.writes


def test_yang_failure_reported_without_direct_writes(database, monkeypatch):
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    updater.apply_patch.side_effect = ValueError('schema rejected candidate')
    monkeypatch.setattr(config, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert 'schema rejected candidate' in result.output
    assert not database.writes


def test_global_sflow_conflict_detected_on_another_asic(database, monkeypatch):
    other = Database()
    other.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'tx'): {'admin_state': 'down'}}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda host_db=None: {'': database, 'asic0': other})
    result = CliRunner().invoke(config.config.commands['sflow'].commands['disable'], [], obj={'db': database})
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output
    assert not database.writes and not other.writes


@pytest.mark.parametrize('field', ['MIRROR_ACTION', 'MIRROR_INGRESS_ACTION', 'MIRROR_EGRESS_ACTION'])
def test_export_delete_rejects_acl_references(database, field):
    database.tables['ACL_RULE'] = {('ACL1', 'RULE1'): {field: 'export1'}}
    result = invoke(['remove', 'export1'])
    assert result.exit_code != 0
    assert 'referenced by an ACL' in result.output
    assert not database.writes


def test_database_discovery_includes_host_and_front_asics(monkeypatch):
    monkeypatch.setattr(port_mirror.multi_asic, 'get_all_namespaces', lambda: {'front_ns': ['asic0', 'asic1']})
    factory = mock.Mock(side_effect=[mock.Mock(), mock.Mock(), mock.Mock()])
    databases = port_mirror.config_databases(connector_factory=factory)
    assert list(databases) == ['', 'asic0', 'asic1']
    for db in databases.values():
        db.connect.assert_called_once()
    assert factory.call_args_list == [mock.call(),
                                      mock.call(use_unix_socket_path=True, namespace='asic0'),
                                      mock.call(use_unix_socket_path=True, namespace='asic1')]


@pytest.mark.parametrize('source,table', [('Ethernet4', 'PORT'), ('PortChannel1', 'PORTCHANNEL')])
def test_remove_binding_after_source_deleted(database, source, table):
    del database.tables[table][source]
    database.tables['PORT_MIRROR_SAMPLE'] = {(source, 'rx'): {'mirror_session': 'export1'}}
    result = invoke(['sample', 'remove', 'export1', source, 'rx'])
    assert result.exit_code == 0, result.output
    assert not database.get_keys('PORT_MIRROR_SAMPLE')


def test_remove_does_not_require_export_or_capabilities(database, monkeypatch):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'mirror_session': 'export1'}}
    del database.tables['MIRROR_SESSION']['export1']
    monkeypatch.setattr(config, 'SonicV2Connector', mock.Mock(side_effect=RuntimeError))
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'rx'])
    assert result.exit_code == 0, result.output
    assert not database.get_keys('PORT_MIRROR_SAMPLE')


def test_yang_operational_failure_is_reported(database, monkeypatch):
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    updater.apply_patch.side_effect = config.GenericConfigUpdaterError('configuration lock failed')
    monkeypatch.setattr(config, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert 'configuration lock failed' in result.output
    assert not database.writes


def test_sflow_agent_remove_without_agent_is_noop(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'admin_state': 'down'}}
    result = CliRunner().invoke(config.config.commands['sflow'].commands['agent-id'].commands['del'],
                                [], obj={'db': database})
    assert result.exit_code == 0, result.output
    assert 'not configured' in result.output
    assert not database.writes


def test_both_add_uses_same_policy_and_preserves_existing_bindings(database):
    exports = database.get_table('MIRROR_SESSION')
    existing = {'mirror_session': 'export2', 'sample_rate': '1000', 'admin_state': 'down'}
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'rx'): dict(existing)}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both',
                     '--sample_rate', '5000', '--truncate_size', '128'])
    assert result.exit_code == 0, result.output
    expected = {'mirror_session': 'export1', 'sample_rate': '5000',
                'truncate_size': '128', 'admin_state': 'up'}
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('Ethernet4', 'rx')) == expected
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('Ethernet4', 'tx')) == expected
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('Ethernet0', 'rx')) == existing
    assert database.get_table('MIRROR_SESSION') == exports
    assert all(table == 'PORT_MIRROR_SAMPLE' for table, _, _ in database.writes)


def test_yang_patch_targets_source_namespace(database, monkeypatch):
    host = Database()
    host.tables['PORT'] = {}
    host.tables['PORTCHANNEL'] = {}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'': host, 'asic1': database})
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    factory = mock.Mock()
    monkeypatch.setattr(config, 'GenericUpdater', factory)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample_rate', '5000'])
    assert result.exit_code == 0, result.output
    factory.assert_called_once_with(scope='asic1')
    kwargs = factory.return_value.apply_patch.call_args.kwargs
    assert kwargs['sort'] is True
    assert kwargs['config_format'] == config.ConfigFormat.CONFIGDB
    candidate = kwargs['patch'].apply({})
    assert set(candidate['PORT_MIRROR_SAMPLE']) == {'Ethernet4|rx', 'Ethernet4|tx'}
    assert not host.writes and not database.writes


def test_ambiguous_source_namespace_is_rejected(database, monkeypatch):
    other = Database()
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'asic0': database, 'asic1': other})
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample_rate', '5000'])
    assert result.exit_code != 0
    assert 'must identify one' in result.output
    assert not database.writes and not other.writes


def test_export_removal_checks_all_namespaces_before_writes(database, monkeypatch):
    other = Database()
    other.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'rx'): {'mirror_session': 'export1'}}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda **kwargs: {'': database, 'asic1': other})
    result = invoke(['remove', 'export1'])
    assert result.exit_code != 0
    assert 'referenced by a sampled binding' in result.output
    assert not database.writes and not other.writes


@pytest.mark.parametrize('direction,expected', [('rx', ['rx']), ('tx', ['tx']), ('both', ['rx', 'tx'])])
def test_source_list_add_and_remove(database, direction, expected):
    exports = database.get_table('MIRROR_SESSION')
    result = invoke(['sample', 'add', 'export1', 'Ethernet0,Ethernet4', direction,
                     '--sample_rate', '5000', '--truncate_size', '128', '--disabled'])
    assert result.exit_code == 0, result.output
    policy = {'mirror_session': 'export1', 'sample_rate': '5000',
              'truncate_size': '128', 'admin_state': 'down'}
    assert database.get_table('PORT_MIRROR_SAMPLE') == {
        (port, d): policy for port in ['Ethernet0', 'Ethernet4'] for d in expected
    }
    result = invoke(['sample', 'remove', 'export1', 'Ethernet0,Ethernet4', direction])
    assert result.exit_code == 0, result.output
    assert not database.get_keys('PORT_MIRROR_SAMPLE')
    assert database.get_table('MIRROR_SESSION') == exports


@pytest.mark.parametrize('sources', ['', ',Ethernet4', 'Ethernet4,', 'Ethernet0,,Ethernet4',
                                     'Ethernet4,Ethernet4', 'Eth0,Ethernet0'])
@pytest.mark.parametrize('action', ['add', 'remove'])
def test_invalid_source_lists_do_not_write(database, monkeypatch, sources, action):
    monkeypatch.setattr(config.clicommon, 'get_interface_naming_mode', lambda: 'alias')
    args = ['sample', action, 'export1', sources, 'rx']
    if action == 'add':
        args += ['--sample_rate', '2']
    result = invoke(args)
    assert result.exit_code != 0
    assert 'empty entries' in result.output or 'more than once' in result.output
    assert not database.writes


@pytest.mark.parametrize('sources', ['PortChannel1,Ethernet0', 'Ethernet0,PortChannel1'])
def test_source_list_internal_lag_overlap_rejected(database, sources):
    result = invoke(['sample', 'add', 'export1', sources, 'both', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert 'already owns' in result.output
    assert not database.writes


def test_source_list_allows_nonoverlapping_portchannel_and_alias(database, monkeypatch):
    database.tables['PORT']['Ethernet4']['alias'] = 'Eth4'
    monkeypatch.setattr(config.clicommon, 'get_interface_naming_mode', lambda: 'alias')
    result = invoke(['sample', 'add', 'export1', 'PortChannel1, Eth4', 'both', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output
    assert set(database.get_keys('PORT_MIRROR_SAMPLE')) == {
        ('PortChannel1', 'rx'), ('PortChannel1', 'tx'), ('Ethernet4', 'rx'), ('Ethernet4', 'tx')}


def test_source_list_late_duplicate_prevents_all_writes(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'tx'): {'mirror_session': 'export2'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet0,Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert not database.writes


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_source_list_invalid_later_interface_prevents_all_writes(database, action):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'rx'): {'mirror_session': 'export1'}}
    args = ['sample', action, 'export1', 'Ethernet0,Ethernet999', 'rx']
    if action == 'add':
        args += ['--sample_rate', '2']
    result = invoke(args)
    assert result.exit_code != 0
    assert 'Source interface' in result.output
    assert not database.writes


@pytest.mark.parametrize('other', [None, {'mirror_session': 'export2'}])
def test_source_list_remove_validates_every_source(database, other):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'rx'): {'mirror_session': 'export1'}}
    if other is not None:
        database.tables['PORT_MIRROR_SAMPLE'][('Ethernet4', 'tx')] = other
    before = database.get_table('PORT_MIRROR_SAMPLE')
    result = invoke(['sample', 'remove', 'export1', 'Ethernet0,Ethernet4', 'both'])
    assert result.exit_code != 0
    assert not database.writes
    assert database.get_table('PORT_MIRROR_SAMPLE') == before


def test_source_list_remove_both_allows_missing_direction_per_source(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {
        ('Ethernet0', 'rx'): {'mirror_session': 'export1'},
        ('Ethernet4', 'tx'): {'mirror_session': 'export1'},
        ('PortChannel1', 'tx'): {'mirror_session': 'export2'},
    }
    result = invoke(['sample', 'remove', 'export1', 'Ethernet0,Ethernet4', 'both'])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('PortChannel1', 'tx')]


def test_source_list_yang_one_patch_per_namespace(database, monkeypatch):
    monkeypatch.setattr(config.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    factory = mock.Mock()
    monkeypatch.setattr(config, 'GenericUpdater', factory)
    result = invoke(['sample', 'add', 'export1', 'Ethernet0,Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output
    factory.assert_called_once_with(scope='')
    updater = factory.return_value
    updater.apply_patch.assert_called_once()
    target = updater.apply_patch.call_args.kwargs['patch'].apply({})
    assert set(target['PORT_MIRROR_SAMPLE']) == {'Ethernet0|rx', 'Ethernet0|tx', 'Ethernet4|rx', 'Ethernet4|tx'}
    database.tables['PORT_MIRROR_SAMPLE'] = {
        tuple(k.split('|')): v for k, v in target['PORT_MIRROR_SAMPLE'].items()}
    updater.reset_mock()
    result = invoke(['sample', 'remove', 'export1', 'Ethernet0,Ethernet4', 'both'])
    assert result.exit_code == 0, result.output
    updater.apply_patch.assert_called_once()
    assert updater.apply_patch.call_args.kwargs['patch'].apply(target) == {}
    assert not database.writes


@pytest.mark.parametrize('problem', [None, 'missing_export', 'unsupported', 'mismatch'])
def test_source_list_cross_namespace_prevalidation(database, monkeypatch, problem):
    other = Database()
    database.tables['PORT'] = {'Ethernet0': {}}
    database.tables['PORTCHANNEL'] = {}
    other.tables['PORT'] = {'Ethernet4': {}}
    other.tables['PORTCHANNEL'] = {}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'asic0': database, 'asic1': other})
    if problem == 'missing_export':
        other.tables['MIRROR_SESSION'] = {}
    if problem == 'unsupported':
        def capability(ctx, namespace, directions, truncate):
            if namespace == 'asic1':
                ctx.fail('unsupported')
        monkeypatch.setattr(config, 'validate_mirror_sample_capabilities', capability)
    if problem == 'mismatch':
        database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'rx'): {'mirror_session': 'export1'}}
        other.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'mirror_session': 'export2'}}
        args = ['sample', 'remove', 'export1', 'Ethernet0,Ethernet4', 'rx']
    else:
        args = ['sample', 'add', 'export1', 'Ethernet0,Ethernet4', 'rx', '--sample_rate', '2']
    result = invoke(args)
    assert (result.exit_code == 0) == (problem is None), result.output
    if problem is None:
        assert database.get_keys('PORT_MIRROR_SAMPLE') == [('Ethernet0', 'rx')]
        assert other.get_keys('PORT_MIRROR_SAMPLE') == [('Ethernet4', 'rx')]
    else:
        assert not database.writes and not other.writes


def _run_sampling_lock_command(command, args, database, results, ready=None, release=None, pause_table=None):
    """Run the actual decorated CLI callback in a separate process."""
    if ready is not None:
        get_keys = database.get_keys

        def paused_get_keys(table):
            keys = get_keys(table)
            if table == pause_table:
                ready.set()
                if not release.wait(10):
                    raise RuntimeError('Timed out waiting for competing CLI')
            return keys

        database.get_keys = paused_get_keys
    result = CliRunner().invoke(command, args, obj={'db': database})
    results.put((result.exit_code, result.output, database.writes))


@pytest.mark.parametrize('holder', ['sample', 'sflow'])
def test_sampling_lock_serializes_independent_cli_processes(database, monkeypatch, holder):
    import multiprocessing

    # Both child processes inherit the same isolated lock path and initial DB.
    # Pause the first command between its conflict read and its configuration write.
    monkeypatch.setattr(config, 'ValidatedConfigDBConnector', lambda db: db)
    database.mod_entry = database.set_entry
    sample = (config.config.commands['mirror_session'].commands['sample'].commands['add'],
              ['export1', 'Ethernet4', 'rx', '--sample_rate', '5000'])
    sflow = (config.config.commands['sflow'].commands['disable'], [])
    first, second = (sample, sflow) if holder == 'sample' else (sflow, sample)
    pause_table = 'SFLOW' if holder == 'sample' else 'PORT_MIRROR_SAMPLE'
    mp = multiprocessing.get_context('fork')
    ready, release = mp.Event(), mp.Event()
    first_results, second_results = mp.Queue(), mp.Queue()
    first_process = mp.Process(target=_run_sampling_lock_command,
                               args=(*first, database, first_results, ready, release, pause_table))
    second_process = mp.Process(target=_run_sampling_lock_command,
                                args=(*second, database, second_results))
    try:
        first_process.start()
        assert ready.wait(10), 'First CLI did not reach its protected conflict read'
        second_process.start()
        code, output, writes = second_results.get(timeout=10)
        second_process.join(10)
        assert second_process.exitcode == 0
        assert code != 0
        assert 'Failed to acquire lock' in output
        assert writes == []
        release.set()
        code, output, writes = first_results.get(timeout=10)
        first_process.join(10)
        assert first_process.exitcode == 0
        assert code == 0, output
        assert writes
        assert {table for table, _, _ in writes} == {
            'PORT_MIRROR_SAMPLE' if holder == 'sample' else 'SFLOW'}
    finally:
        release.set()
        for process in (first_process, second_process):
            if process.pid is not None:
                process.join(2)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
        first_results.close()
        second_results.close()


@pytest.mark.parametrize('path,args', [
    (['mirror_session', 'sample', 'add'], ['export1', 'Ethernet4', 'rx', '--sample_rate', '2']),
    (['mirror_session', 'sample', 'remove'], ['export1', 'Ethernet4', 'rx']),
    (['sflow', 'enable'], []),
    (['sflow', 'disable'], []),
    (['sflow', 'polling-interval'], ['20']),
    (['sflow', 'sample-direction'], ['rx']),
    (['sflow', 'drop-monitor-limit'], ['0']),
    (['sflow', 'agent-id', 'add'], ['Ethernet0']),
    (['sflow', 'agent-id', 'del'], []),
])
def test_sampling_commands_share_lock_before_any_db_access(database, path, args):
    from utilities_common.flock import acquire_flock, release_flock

    command = config.config
    for part in path:
        command = command.commands[part]
    with open(config.SAMPLING_CONFIG_LOCK, 'a+') as lock:
        assert acquire_flock(lock.fileno(), 0)
        try:
            with mock.patch.object(database, 'get_keys', side_effect=AssertionError('Unexpected DB read')):
                result = CliRunner().invoke(command, args, obj={'db': database})
            assert result.exit_code != 0
            assert 'Failed to acquire lock' in result.output
            assert not database.writes
        finally:
            release_flock(lock.fileno())


@pytest.mark.parametrize('failure', ['conflict', 'write_error'])
def test_sample_command_failure_releases_lock(database, monkeypatch, failure):
    from utilities_common.flock import acquire_flock, release_flock

    if failure == 'conflict':
        database.tables['SFLOW'] = {'global': {'admin_state': 'down'}}
    else:
        monkeypatch.setattr(database, 'set_entry', mock.Mock(side_effect=RuntimeError('DB write failed')))
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample_rate', '2'])
    assert result.exit_code != 0
    assert not database.writes
    if failure == 'conflict':
        assert 'cannot coexist' in result.output
    else:
        assert isinstance(result.exception, RuntimeError)
    with open(config.SAMPLING_CONFIG_LOCK, 'a+') as lock:
        assert acquire_flock(lock.fileno(), 0)
        release_flock(lock.fileno())


def test_sflow_conflict_failure_releases_lock(database):
    from utilities_common.flock import acquire_flock, release_flock

    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'admin_state': 'down'}}
    result = CliRunner().invoke(config.config.commands['sflow'].commands['disable'], [], obj={'db': database})
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output
    assert not database.writes
    with open(config.SAMPLING_CONFIG_LOCK, 'a+') as lock:
        assert acquire_flock(lock.fileno(), 0)
        release_flock(lock.fileno())


def test_sampling_lock_held_for_every_namespace_write(database, monkeypatch):
    from utilities_common.flock import acquire_flock, release_flock

    other = Database()
    database.tables['PORT'] = {'Ethernet0': {}}
    other.tables['PORT'] = {'Ethernet4': {}}
    database.tables['PORTCHANNEL'] = {}
    other.tables['PORTCHANNEL'] = {}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'asic0': database, 'asic1': other})
    checked = []

    def guarded_writer(db, namespace):
        write = db.set_entry

        def write_under_lock(table, key, value):
            with open(config.SAMPLING_CONFIG_LOCK, 'a+') as lock:
                acquired = acquire_flock(lock.fileno(), 0)
                if acquired:
                    release_flock(lock.fileno())
                assert not acquired, 'Sampling lock released before namespace write'
            checked.append(namespace)
            write(table, key, value)

        return write_under_lock

    monkeypatch.setattr(database, 'set_entry', guarded_writer(database, 'asic0'))
    monkeypatch.setattr(other, 'set_entry', guarded_writer(other, 'asic1'))
    result = invoke(['sample', 'add', 'export1', 'Ethernet0,Ethernet4', 'both', '--sample_rate', '2'])
    assert result.exit_code == 0, result.output
    assert checked == ['asic0', 'asic0', 'asic1', 'asic1']
    checked.clear()
    result = invoke(['sample', 'remove', 'export1', 'Ethernet0,Ethernet4', 'both'])
    assert result.exit_code == 0, result.output
    assert checked == ['asic0', 'asic0', 'asic1', 'asic1']
