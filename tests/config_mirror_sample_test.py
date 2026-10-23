"""Sampled binding CLI tests with isolated ConfigDB state."""
from copy import deepcopy
from unittest import mock

import pytest
from click.testing import CliRunner

import config.main as config
from config import mirror_sample
import show.main as show
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
    monkeypatch.setattr(mirror_sample.device_info, 'is_yang_config_validation_enabled', lambda db: False)
    monkeypatch.setattr(mirror_sample.clicommon, 'get_interface_naming_mode', lambda: 'default')
    state = mock.Mock()
    state.get.return_value = 'true'
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', lambda **kwargs: state)
    return db


def invoke(args):
    return CliRunner().invoke(config.config.commands['mirror_session'], args)


@pytest.mark.parametrize('direction,expected', [('rx', ['rx']), ('tx', ['tx']), ('both', ['rx', 'tx'])])
@pytest.mark.parametrize('disabled', [False, True])
def test_add_binding(database, direction, expected, disabled):
    exports = database.get_table('MIRROR_SESSION')
    args = ['sample', 'add', 'export1', 'Ethernet4', direction, '--sample-rate', '1000']
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
                     '--sample-rate', rate, '--truncate-size', truncate])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('PortChannel1', 'rx')]
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('PortChannel1', 'rx'))['truncate_size'] == truncate


@pytest.mark.parametrize('options', [[], ['--sample-rate', '0'], ['--sample-rate', '1'],
                                     ['--sample-rate', '4294967296'], ['--sample-rate', '-1'],
                                     ['--sample-rate', '2', '--truncate-size', '0'],
                                     ['--sample-rate', '2', '--truncate-size', '63'],
                                     ['--sample-rate', '2', '--truncate-size', '9217']])
def test_invalid_policy_never_writes(database, options):
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx'] + options)
    assert result.exit_code != 0
    assert database.writes == []


@pytest.mark.parametrize('global_entry', [{}, {'admin_state': 'down'}, {'admin_state': 'up'}])
def test_sflow_global_blocks_even_disabled_binding(database, global_entry):
    database.tables['SFLOW'] = {'global': global_entry}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2', '--disabled'])
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
    result = invoke(['sample', 'add', session, port, 'rx', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert expected in result.output
    assert not database.writes


def test_both_duplicate_prevents_partial_write(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'tx'): {'mirror_session': 'export2'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert not database.writes


@pytest.mark.parametrize('existing,new', [('PortChannel1', 'Ethernet0'), ('Ethernet0', 'PortChannel1')])
def test_portchannel_member_overlap(database, existing, new):
    database.tables['PORT_MIRROR_SAMPLE'] = {(existing, 'rx'): {'mirror_session': 'export2'}}
    result = invoke(['sample', 'add', 'export1', new, 'rx', '--sample-rate', '2'])
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
    monkeypatch.setattr(mirror_sample.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    monkeypatch.setattr(mirror_sample, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2'])
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


def test_show_sample_bindings(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {
        ('Ethernet4', 'rx'): {'mirror_session': 'export1', 'sample_rate': '1000'},
        ('Ethernet0', 'tx'): {
            'mirror_session': 'export2', 'sample_rate': '2',
            'truncate_size': '128', 'admin_state': 'up',
        },
    }
    result = CliRunner().invoke(show.cli.commands['mirror_session'], ['sample'])
    assert result.exit_code == 0, result.output
    assert 'Sampled ERSPAN Bindings' in result.output
    assert 'Disabled' in result.output
    assert 'down' in result.output
    assert result.output.index('Ethernet0') < result.output.index('Ethernet4')


def test_namespace_and_alias_resolution(database, monkeypatch):
    host = Database()
    host.tables['PORT'] = {}
    other = Database()
    other.tables['PORT'] = {}
    other.tables['PORTCHANNEL'] = {}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda host_db=None:
                        {'': host, 'asic0': other, 'asic1': database})
    monkeypatch.setattr(mirror_sample.clicommon, 'get_interface_naming_mode', lambda: 'alias')
    result = invoke(['sample', 'add', 'export1', 'Eth0', 'rx', '--sample-rate', '2'])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('Ethernet0', 'rx')]
    assert not host.writes and not other.writes
    other.tables['SFLOW'] = {'global': {'admin_state': 'down'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert 'cannot coexist' in result.output


def test_explicit_unsupported_capability_rejects_both(database, monkeypatch):
    state = mock.Mock()
    state.get.side_effect = lambda db, key, field: 'false' if 'EGRESS' in field else 'true'
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert 'not supported' in result.output
    assert not database.writes


@pytest.mark.parametrize('capability', [None, 'true', 'false'])
def test_truncation_capability(database, monkeypatch, capability):
    state = mock.Mock()
    state.get.side_effect = lambda db, key, field: capability if 'TRUNCATION' in field else 'true'
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx',
                     '--sample-rate', '2', '--truncate-size', '128'])
    assert (result.exit_code == 0) == (capability != 'false'), result.output
    if capability == 'false':
        assert not database.writes


def test_capability_service_failure_does_not_write(database, monkeypatch):
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', mock.Mock(side_effect=RuntimeError('unavailable')))
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert 'Unable to read sampled mirror capabilities' in result.output
    assert not database.writes


def test_missing_direction_capabilities_allow_configuration(database, monkeypatch):
    state = mock.Mock()
    state.get.return_value = None
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2'])
    assert result.exit_code == 0, result.output
    assert database.get_keys('PORT_MIRROR_SAMPLE') == [('Ethernet4', 'rx'), ('Ethernet4', 'tx')]


def test_partial_capability_read_failure_does_not_bypass_rejection(database, monkeypatch):
    state = mock.Mock()
    state.get.side_effect = ['false', RuntimeError('STATE_DB read failed')]
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', lambda **kwargs: state)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert not database.writes


def test_sflow_sessions_without_global_do_not_conflict(database):
    database.tables['SFLOW_SESSION'] = {'Ethernet4': {'admin_state': 'up'}}
    database.tables['SFLOW_COLLECTOR'] = {'collector': {'collector_ip': '10.0.0.1'}}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample-rate', '2'])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('keep_other', [False, True])
def test_yang_remove_avoids_empty_table(database, monkeypatch, keep_other):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'mirror_session': 'export1'}}
    if keep_other:
        database.tables['PORT_MIRROR_SAMPLE'][('Ethernet0', 'tx')] = {'mirror_session': 'export2'}
    monkeypatch.setattr(mirror_sample.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    monkeypatch.setattr(mirror_sample, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'rx'])
    assert result.exit_code == 0, result.output
    expected_path = '/PORT_MIRROR_SAMPLE/Ethernet4|rx' if keep_other else '/PORT_MIRROR_SAMPLE'
    assert updater.apply_patch.call_args.kwargs['patch'].patch == [{'op': 'remove', 'path': expected_path}]
    assert not database.writes


def test_yang_failure_reported_without_direct_writes(database, monkeypatch):
    monkeypatch.setattr(mirror_sample.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    updater.apply_patch.side_effect = ValueError('schema rejected candidate')
    monkeypatch.setattr(mirror_sample, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '2'])
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


def test_show_empty_and_multi_asic_bindings(database, monkeypatch):
    result = CliRunner().invoke(show.cli.commands['mirror_session'], ['sample'])
    assert result.exit_code == 0
    assert 'Source Port' in result.output
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'mirror_session': 'export1'}}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'': Database(), 'asic1': database})
    result = CliRunner().invoke(show.cli.commands['mirror_session'], ['sample'])
    assert result.exit_code == 0, result.output
    assert 'Namespace' in result.output and 'asic1' in result.output


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
    monkeypatch.setattr(mirror_sample, 'SonicV2Connector', mock.Mock(side_effect=RuntimeError))
    result = invoke(['sample', 'remove', 'export1', 'Ethernet4', 'rx'])
    assert result.exit_code == 0, result.output
    assert not database.get_keys('PORT_MIRROR_SAMPLE')


def test_yang_operational_failure_is_reported(database, monkeypatch):
    monkeypatch.setattr(mirror_sample.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    updater = mock.Mock()
    updater.apply_patch.side_effect = mirror_sample.GenericConfigUpdaterError('configuration lock failed')
    monkeypatch.setattr(mirror_sample, 'GenericUpdater', lambda **kwargs: updater)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample-rate', '2'])
    assert result.exit_code != 0
    assert 'configuration lock failed' in result.output
    assert not database.writes


def test_show_explicit_session_named_sample(database, monkeypatch):
    command = mock.Mock()
    monkeypatch.setattr(show, 'run_command', command)
    result = CliRunner().invoke(show.cli.commands['mirror_session'], ['--session-name', 'sample'])
    assert result.exit_code == 0, result.output
    command.assert_called_once_with(['acl-loader', 'show', 'session', 'sample'], display_cmd=False)


@pytest.mark.parametrize('args,command', [
    ([], ['acl-loader', 'show', 'session']),
    (['export1'], ['acl-loader', 'show', 'session', 'export1']),
])
def test_existing_show_commands_unchanged(database, monkeypatch, args, command):
    run = mock.Mock()
    monkeypatch.setattr(show, 'run_command', run)
    result = CliRunner().invoke(show.cli.commands['mirror_session'], args)
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(command, display_cmd=False)


def test_show_rejects_two_session_selectors(database):
    result = CliRunner().invoke(show.cli.commands['mirror_session'], ['export1', '--session-name', 'export2'])
    assert result.exit_code != 0
    assert 'not both' in result.output


def test_sflow_agent_remove_without_agent_is_noop(database):
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet4', 'rx'): {'admin_state': 'down'}}
    result = CliRunner().invoke(config.config.commands['sflow'].commands['agent-id'].commands['del'],
                                [], obj={'db': database})
    assert result.exit_code == 0, result.output
    assert 'not configured' in result.output
    assert not database.writes


def test_both_add_uses_same_policy_and_preserves_existing_bindings(database):
    existing = {'mirror_session': 'export2', 'sample_rate': '1000', 'admin_state': 'down'}
    database.tables['PORT_MIRROR_SAMPLE'] = {('Ethernet0', 'rx'): dict(existing)}
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both',
                     '--sample-rate', '5000', '--truncate-size', '128'])
    assert result.exit_code == 0, result.output
    expected = {'mirror_session': 'export1', 'sample_rate': '5000',
                'truncate_size': '128', 'admin_state': 'up'}
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('Ethernet4', 'rx')) == expected
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('Ethernet4', 'tx')) == expected
    assert database.get_entry('PORT_MIRROR_SAMPLE', ('Ethernet0', 'rx')) == existing


def test_yang_patch_targets_source_namespace(database, monkeypatch):
    host = Database()
    host.tables['PORT'] = {}
    host.tables['PORTCHANNEL'] = {}
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'': host, 'asic1': database})
    monkeypatch.setattr(mirror_sample.device_info, 'is_yang_config_validation_enabled', lambda db: True)
    factory = mock.Mock()
    monkeypatch.setattr(mirror_sample, 'GenericUpdater', factory)
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'both', '--sample-rate', '5000'])
    assert result.exit_code == 0, result.output
    factory.assert_called_once_with(scope='asic1')
    kwargs = factory.return_value.apply_patch.call_args.kwargs
    assert kwargs['sort'] is True
    assert kwargs['config_format'] == mirror_sample.ConfigFormat.CONFIGDB
    candidate = kwargs['patch'].apply({})
    assert set(candidate['PORT_MIRROR_SAMPLE']) == {'Ethernet4|rx', 'Ethernet4|tx'}
    assert not host.writes and not database.writes


def test_ambiguous_source_namespace_is_rejected(database, monkeypatch):
    other = Database()
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'asic0': database, 'asic1': other})
    result = invoke(['sample', 'add', 'export1', 'Ethernet4', 'rx', '--sample-rate', '5000'])
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
