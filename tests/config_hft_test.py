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
                ['add', 'profile', 'profileA', '--harmonizer', 'hm0']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE',
            'value': {
                'profileA': {
                    'stream_state': 'disabled',
                    'poll_interval': '10000',
                    'harmonizer': 'hm0'
                }
            }
        }]
        assert payload == expected_payload

    def test_add_harmonizer_splits_comma_separated_lists(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'harmonizer', 'hm0',
                    '--reporting_rate', '1000',
                    '--rollover_counters', 'PORT|IF_IN_UCAST_PKTS, QUEUE|DROPPED_PACKETS',
                    '--heatmap_counters', 'PORT|IF_OUT_ERRORS, QUEUE|WRED_ECN_MARKED_PACKETS'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_HARMONIZER',
            'value': {
                'hm0': {
                    'reporting_rate': '1000',
                    'rollover_counters': ['PORT|IF_IN_UCAST_PKTS', 'QUEUE|DROPPED_PACKETS'],
                    'heatmap_counters': ['PORT|IF_OUT_ERRORS', 'QUEUE|WRED_ECN_MARKED_PACKETS']
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

    def test_bind_harmonizer_sets_profile_harmonizer_patch(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['bind-harmonizer', 'profileA', 'hm0']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE/profileA/harmonizer',
            'value': 'hm0'
        }]
        assert payload == expected_payload

    def test_unbind_harmonizer_removes_profile_harmonizer_patch(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['unbind-harmonizer', 'profileA']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE/profileA/harmonizer'
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

    def test_delete_harmonizer_removes_entry(self):
        with patch('config.hft._is_last_entry', return_value=False), \
                patch('config.hft._get_harmonizer_users', return_value=[]), \
                patch('config.hft._has_table_entry', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'harmonizer', 'hm0']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_HARMONIZER/hm0'
        }]
        assert payload == expected_payload

    def test_delete_harmonizer_rejected_when_profile_still_references_it(self):
        with patch('config.hft._get_harmonizer_users', return_value=['profileA']), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'harmonizer', 'hm0']
            )

        assert result.exit_code == 1
        assert "Cannot delete harmonizer 'hm0'" in result.output
        assert 'profileA' in result.output
        mock_process.assert_not_called()

    def test_delete_harmonizer_rejected_when_harmonizer_does_not_exist(self):
        with patch('config.hft._get_harmonizer_users', return_value=[]), \
                patch('config.hft._has_table_entry', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'harmonizer', 'missing']
            )

        assert result.exit_code == 1
        assert "Harmonizer 'missing' does not exist." in result.output
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
