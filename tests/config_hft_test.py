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
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE',
            'value': {
                'profileA': {
                    'stream_state': 'disabled',
                    'poll_interval': '10000'
                }
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
            'path': '/HIGH_FREQUENCY_TELEMETRY_GROUP',
            'value': {
                'profileA|PORT': {
                    'object_names': ['Ethernet0', 'Ethernet4'],
                    'object_counters': ['COUNTER_A', 'COUNTER_B']
                }
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
