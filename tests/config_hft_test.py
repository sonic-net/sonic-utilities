import json
import os

from click.testing import CliRunner
from unittest.mock import patch

import config.hft as config_hft


class TestConfigHftCli:
    def setup_method(self):
        self.runner = CliRunner()

    def test_add_profile_invokes_process_payload(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'profile', 'profileA']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE/profileA',
            'value': {
                'stream_state': 'disabled',
                'poll_interval': '10000'
            }
        }]
        assert payload == expected_payload

    def test_add_group_splits_comma_separated_lists(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'group', 'profileA',
                    '--group_type', 'PORT',
                    '--object_names', 'Ethernet0, Ethernet4',
                    '--object_counters', 'COUNTER_A, COUNTER_B'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_GROUP/profileA|PORT',
            'value': {
                'object_names': ['Ethernet0', 'Ethernet4'],
                'object_counters': ['COUNTER_A', 'COUNTER_B']
            }
        }]
        assert payload == expected_payload

    def test_enable_profile_sets_stream_state_patch(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['enable', 'profileZ']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE/profileZ/stream_state',
            'value': 'enabled'
        }]
        assert payload == expected_payload

    def test_add_profile_rejected_when_profile_already_exists(self):
        with patch('config.hft._has_existing_profile', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'profile', 'duplicate']
            )

        assert result.exit_code == 1
        assert 'A profile already exists' in result.output
        mock_process.assert_not_called()

    def test_delete_profile_removes_entire_table_when_last_entry(self):
        with patch('config.hft._is_last_entry', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'profile', 'profileFINAL']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE'
        }]
        assert payload == expected_payload

    def test_add_group_rejected_while_stream_active(self):
        with patch('config.hft._get_state_db', return_value=object()), \
                patch('config.hft._active_session_groups', return_value=['PORT']), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'group', 'profileA',
                    '--group_type', 'BUFFER_POOL',
                    '--object_names', 'egress_lossless_pool',
                    '--object_counters', 'COUNTER_A'
                ]
            )

        assert result.exit_code != 0
        assert 'active runtime streams' in result.output
        assert 'config hft disable profileA' in result.output
        mock_process.assert_not_called()

    def test_delete_group_rejected_while_stream_active(self):
        with patch('config.hft._get_state_db', return_value=object()), \
                patch('config.hft._active_session_groups', return_value=['PORT']), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'group', 'profileA', 'PORT']
            )

        assert result.exit_code != 0
        assert 'active runtime streams' in result.output
        mock_process.assert_not_called()

    def test_add_group_succeeds_when_stream_inactive(self):
        with patch('config.hft._get_state_db', return_value=object()), \
                patch('config.hft._active_session_groups', return_value=[]), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'group', 'profileA',
                    '--group_type', 'PORT',
                    '--object_names', 'Ethernet0',
                    '--object_counters', 'COUNTER_A'
                ]
            )

        assert result.exit_code == 0
        mock_process.assert_called_once()

    def test_add_group_rejected_when_sibling_group_active_in_mixed(self):
        """MIXED-mode scenario: adding BUFFER_POOL is rejected because a
        sibling group (PORT / QUEUE) is still streaming against the shared
        tel_type/report resources.
        """
        with patch('config.hft._get_state_db', return_value=object()), \
                patch('config.hft._active_session_groups',
                      return_value=['PORT', 'QUEUE']), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'group', 'profileA',
                    '--group_type', 'BUFFER_POOL',
                    '--object_names', 'egress_lossless_pool',
                    '--object_counters', 'COUNTER_A'
                ]
            )

        assert result.exit_code != 0
        assert 'PORT' in result.output
        assert 'QUEUE' in result.output
        mock_process.assert_not_called()


def test_is_last_entry_true_and_false():
    class MockCfgDb:
        def __init__(self, tables):
            self.tables = tables

        def get_table(self, name):
            return self.tables.get(name, {})

    class MockCtx:
        def __init__(self, tables):
            self.obj = type('Obj', (), {'cfgdb': MockCfgDb(tables)})

        def find_root(self):
            return self

    tables = {'HIGH_FREQUENCY_TELEMETRY_PROFILE': {'p1': {}}, 'OTHER': {}}
    assert config_hft._is_last_entry(MockCtx(tables), 'HIGH_FREQUENCY_TELEMETRY_PROFILE') is True

    tables = {'HIGH_FREQUENCY_TELEMETRY_PROFILE': {'p1': {}, 'p2': {}}}
    assert config_hft._is_last_entry(MockCtx(tables), 'HIGH_FREQUENCY_TELEMETRY_PROFILE') is False


def test_active_session_groups_filters_by_stream_status():
    """_active_session_groups must include only sessions whose
    stream_status field is exactly 'enabled', excluding disabled and
    missing values, and only under the requested profile.
    """
    entries = {
        'HIGH_FREQUENCY_TELEMETRY_SESSION_TABLE|profileA|PORT': {'stream_status': 'enabled'},
        'HIGH_FREQUENCY_TELEMETRY_SESSION_TABLE|profileA|QUEUE': {'stream_status': 'disabled'},
        'HIGH_FREQUENCY_TELEMETRY_SESSION_TABLE|profileA|IPG': {},  # no field
        'HIGH_FREQUENCY_TELEMETRY_SESSION_TABLE|profileB|PORT': {'stream_status': 'enabled'},
    }

    class MockStateDb:
        STATE_DB = 6

        def keys(self, db, pattern):
            # Interpret glob-style pattern with a single trailing '*'.
            assert pattern.endswith('*')
            prefix = pattern[:-1]
            return [k for k in entries.keys() if k.startswith(prefix)]

        def get_all(self, db, key):
            return entries.get(key)

    assert config_hft._active_session_groups(MockStateDb(), 'profileA') == ['PORT']
    assert config_hft._active_session_groups(MockStateDb(), 'profileB') == ['PORT']
    assert config_hft._active_session_groups(MockStateDb(), 'unknown') == []


def test_materialize_payload_creates_file():
    payload = [{'op': 'add', 'path': '/X', 'value': {'k': 'v'}}]
    path = config_hft._materialize_payload(payload)

    try:
        assert path
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data == payload
    finally:
        if path:
            os.remove(path)
