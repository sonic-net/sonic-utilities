import json
import os

import pytest
from click.testing import CliRunner
from unittest.mock import patch

import config.hft as config_hft


def _make_cli_obj(tables):
    class MockCfgDb:
        def get_table(self, name):
            return tables.get(name, {})

    return type('Obj', (), {'cfgdb': MockCfgDb()})


class TestConfigHftCli:
    def setup_method(self):
        self.runner = CliRunner()

    def test_add_profile_invokes_process_payload(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'profile', 'profileA', '--aggregator', 'ag0']
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
                    'aggregator': 'ag0'
                }
            }
        }]
        assert payload == expected_payload

    def test_add_aggregator_splits_comma_separated_lists(self):
        with patch('config.hft._has_table', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'aggregator', 'ag0',
                    '--reporting_rate', '1000',
                    '--rollover_counters', 'PORT|IF_IN_UCAST_PKTS, QUEUE|DROPPED_PACKETS',
                    '--heatmap_interval', '1000000',
                    '--heatmap_counters', 'PORT|IF_OUT_ERRORS, QUEUE|WRED_ECN_MARKED_PACKETS',
                    '--heatmap_default_bucket_count', '64'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR',
            'value': {
                'ag0': {
                    'reporting_rate': '1000',
                    'rollover_counters': ['PORT|IF_IN_UCAST_PKTS', 'QUEUE|DROPPED_PACKETS'],
                    'heatmap_interval': '1000000',
                    'heatmap_counters': ['PORT|IF_OUT_ERRORS', 'QUEUE|WRED_ECN_MARKED_PACKETS'],
                    'heatmap_default_bucket_count': '64'
                }
            }
        }]
        assert payload == expected_payload

    def test_aggregator_entry_paths_reject_name_with_separator(self):
        commands = (
            ['add', 'aggregator', 'ag|0'],
            ['add', 'profile', 'profileA', '--aggregator', 'ag|0'],
            ['bind-aggregator', 'profileA', 'ag|0'],
            ['del', 'aggregator', 'ag|0'],
            ['del', 'histogram', 'ag|0', 'PORT|IF_OUT_OCTETS'],
            [
                'add', 'rollover', 'ag|0',
                '--counter', 'PORT|IF_OUT_OCTETS',
                '--bit_width', '32'
            ],
            ['del', 'rollover', 'ag|0', 'PORT|IF_OUT_OCTETS'],
        )
        for command in commands:
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(config_hft.hft, command)

            assert result.exit_code == 2
            assert "must not contain '|'" in result.output
            mock_process.assert_not_called()

    def test_aggregator_entry_paths_reject_surrounding_whitespace(self):
        for aggregator_name in (' ag0', 'ag0 '):
            commands = (
                ['add', 'aggregator', aggregator_name],
                ['add', 'profile', 'profileA', '--aggregator', aggregator_name],
                ['bind-aggregator', 'profileA', aggregator_name],
                ['del', 'aggregator', aggregator_name],
                [
                    'add', 'histogram', aggregator_name,
                    '--counter', 'PORT|IF_OUT_OCTETS',
                    '--explicit_bounds', '0,1'
                ],
                ['del', 'histogram', aggregator_name, 'PORT|IF_OUT_OCTETS'],
                [
                    'add', 'rollover', aggregator_name,
                    '--counter', 'PORT|IF_OUT_OCTETS',
                    '--bit_width', '32'
                ],
                ['del', 'rollover', aggregator_name, 'PORT|IF_OUT_OCTETS'],
            )
            for command in commands:
                with patch('config.hft._process_payload') as mock_process:
                    result = self.runner.invoke(config_hft.hft, command)

                assert result.exit_code == 2
                assert 'must not have leading or trailing whitespace' in result.output
                mock_process.assert_not_called()

    def test_add_aggregator_accepts_each_optional_method_independently(self):
        commands = [
            ['add', 'aggregator', 'reporting', '--reporting_rate', '1000'],
            [
                'add', 'aggregator', 'rollover',
                '--rollover_counters', 'PORT|IF_IN_UCAST_PKTS'
            ],
            [
                'add', 'aggregator', 'heatmap',
                '--heatmap_interval', '1000000',
                '--heatmap_counters', 'PORT|IF_OUT_ERRORS'
            ]
        ]

        for command in commands:
            with patch('config.hft._has_table', return_value=False), \
                    patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(config_hft.hft, command)
            assert result.exit_code == 0
            mock_process.assert_called_once()

    def test_add_aggregator_defaults_heatmap_bucket_count(self):
        with patch('config.hft._has_table', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'aggregator', 'ag0',
                    '--heatmap_interval', '1000000',
                    '--heatmap_counters', 'PORT|IF_OUT_ERRORS'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR',
            'value': {
                'ag0': {
                    'heatmap_interval': '1000000',
                    'heatmap_counters': ['PORT|IF_OUT_ERRORS'],
                    'heatmap_default_bucket_count': '256'
                }
            }
        }]

    def test_add_aggregator_rejects_heatmap_without_interval(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'aggregator', 'ag0',
                    '--heatmap_counters', 'PORT|IF_OUT_ERRORS'
                ]
            )

        assert result.exit_code == 2
        assert 'must be configured together' in result.output
        mock_process.assert_not_called()

    def test_add_aggregator_rejects_heatmap_without_counters(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'aggregator', 'ag0', '--heatmap_interval', '1000000']
            )

        assert result.exit_code == 2
        assert 'must be configured together' in result.output
        mock_process.assert_not_called()

    def test_add_aggregator_rejects_empty_heatmap_counters(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'aggregator', 'ag0',
                    '--heatmap_interval', '1000000',
                    '--heatmap_counters', ' , '
                ]
            )

        assert result.exit_code == 2
        assert 'at least one' in result.output
        mock_process.assert_not_called()

    def test_add_aggregator_rejects_bucket_count_without_heatmap(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'aggregator', 'ag0', '--heatmap_default_bucket_count', '32']
            )

        assert result.exit_code == 2
        assert 'requires --heatmap_interval' in result.output
        mock_process.assert_not_called()

    def test_add_aggregator_rejects_bucket_count_outside_range(self):
        for value in ('3', '513'):
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'aggregator', 'ag0',
                        '--heatmap_interval', '1000000',
                        '--heatmap_counters', 'PORT|IF_OUT_ERRORS',
                        '--heatmap_default_bucket_count', value
                    ]
                )

            assert result.exit_code == 2
            mock_process.assert_not_called()

    def test_add_aggregator_accepts_bucket_count_range_limits(self):
        for value in ('4', '512'):
            with patch('config.hft._has_table', return_value=False), \
                    patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'aggregator', 'ag0',
                        '--heatmap_interval', '1000000',
                        '--heatmap_counters', 'PORT|IF_OUT_ERRORS',
                        '--heatmap_default_bucket_count', value
                    ]
                )

            assert result.exit_code == 0
            _, payload = mock_process.call_args[0]
            assert payload[0]['value']['ag0']['heatmap_default_bucket_count'] == value

    def test_add_aggregator_rejects_intervals_above_uint32(self):
        for option in ('--reporting_rate', '--heatmap_interval'):
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    ['add', 'aggregator', 'ag0', option, str(2**32)]
                )

            assert result.exit_code == 2
            mock_process.assert_not_called()

    def test_add_histogram_creates_table_with_composite_key(self):
        with patch('config.hft._has_table', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'histogram', 'ag0',
                    '--counter', 'PORT|IF_OUT_OCTETS',
                    '--explicit_bounds', '0, 1250000, 2500000'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM',
            'value': {
                'ag0|PORT|IF_OUT_OCTETS': {
                    'explicit_bounds': ['0', '1250000', '2500000']
                }
            }
        }]

    def test_add_histogram_preserves_existing_table_entries(self):
        with patch('config.hft._has_table', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'histogram', 'ag1',
                    '--counter', 'QUEUE|BYTES',
                    '--explicit_bounds', '1'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': (
                '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                'ag1|QUEUE|BYTES'
            ),
            'value': {'explicit_bounds': ['1']}
        }]

    def test_add_histogram_rejects_malformed_selector(self):
        selectors = (
            'PORT',
            'PORT|',
            '|IF_OUT_OCTETS',
            'NOT_A_GROUP|IF_OUT_OCTETS',
            'PORT|IF_OUT_OCTETS|EXTRA',
        )
        for selector in selectors:
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'histogram', 'ag0',
                        '--counter', selector,
                        '--explicit_bounds', '0,1'
                    ]
                )

            assert result.exit_code == 2
            mock_process.assert_not_called()

    def test_add_histogram_rejects_aggregator_name_with_separator(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'histogram', 'ag|0',
                    '--counter', 'PORT|IF_OUT_OCTETS',
                    '--explicit_bounds', '0,1'
                ]
            )

        assert result.exit_code == 2
        assert "must not contain '|'" in result.output
        mock_process.assert_not_called()

    def test_add_histogram_rejects_invalid_explicit_bounds(self):
        invalid_bounds = (
            '',
            '0,,1',
            '-1,1',
            '+1,2',
            '1.0,2',
            '0,2,2',
            '0,2,1',
            str(2**53 + 1),
            ','.join(str(value) for value in range(512)),
        )
        for bounds in invalid_bounds:
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'histogram', 'ag0',
                        '--counter', 'PORT|IF_OUT_OCTETS',
                        '--explicit_bounds', bounds
                    ]
                )

            assert result.exit_code == 2
            mock_process.assert_not_called()

    def test_add_histogram_accepts_bounds_limits(self):
        bounds = ','.join([*(str(value) for value in range(510)), str(2**53)])
        with patch('config.hft._has_table', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'histogram', 'ag0',
                    '--counter', 'PORT|UNKNOWN_COUNTER_FOR_YANG',
                    '--explicit_bounds', bounds
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload[0]['value']['ag0|PORT|UNKNOWN_COUNTER_FOR_YANG'][
            'explicit_bounds'
        ][-1] == str(2**53)

    def test_add_rollover_creates_table_with_composite_key(self):
        with patch('config.hft._has_table', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'rollover', 'ag0',
                    '--counter', 'PORT|IF_OUT_OCTETS',
                    '--bit_width', '32'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER',
            'value': {
                'ag0|PORT|IF_OUT_OCTETS': {'bit_width': '32'}
            }
        }]

    def test_add_rollover_preserves_existing_table_entries(self):
        with patch('config.hft._has_table', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'rollover', 'ag1',
                    '--counter', 'QUEUE|BYTES',
                    '--bit_width', '63'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': (
                '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER/'
                'ag1|QUEUE|BYTES'
            ),
            'value': {'bit_width': '63'}
        }]

    def test_add_rollover_accepts_bit_width_range_limits(self):
        for bit_width in ('1', '63'):
            with patch('config.hft._has_table', return_value=False), \
                    patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'rollover', 'ag0',
                        '--counter', 'PORT|UNKNOWN_COUNTER_FOR_YANG',
                        '--bit_width', bit_width
                    ]
                )

            assert result.exit_code == 0
            _, payload = mock_process.call_args[0]
            assert payload[0]['value']['ag0|PORT|UNKNOWN_COUNTER_FOR_YANG'] == {
                'bit_width': bit_width
            }

    def test_add_rollover_rejects_bit_width_outside_range(self):
        for bit_width in ('0', '64'):
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'rollover', 'ag0',
                        '--counter', 'PORT|IF_OUT_OCTETS',
                        '--bit_width', bit_width
                    ]
                )

            assert result.exit_code == 2
            mock_process.assert_not_called()

    def test_add_rollover_rejects_malformed_selector(self):
        selectors = (
            'PORT',
            'PORT|',
            '|IF_OUT_OCTETS',
            'NOT_A_GROUP|IF_OUT_OCTETS',
            'PORT|IF_OUT_OCTETS|EXTRA',
        )
        for selector in selectors:
            with patch('config.hft._process_payload') as mock_process:
                result = self.runner.invoke(
                    config_hft.hft,
                    [
                        'add', 'rollover', 'ag0',
                        '--counter', selector,
                        '--bit_width', '32'
                    ]
                )

            assert result.exit_code == 2
            mock_process.assert_not_called()

    def test_add_rollover_rejects_empty_aggregator_name(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'rollover', '',
                    '--counter', 'PORT|IF_OUT_OCTETS',
                    '--bit_width', '32'
                ]
            )

        assert result.exit_code == 2
        assert 'must be nonempty' in result.output
        mock_process.assert_not_called()

    def test_add_group_splits_comma_separated_lists(self):
        with patch('config.hft._has_table', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
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

    def test_add_group_preserves_existing_table_entries(self):
        with patch('config.hft._has_table', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'group', 'profileA',
                    '--group_type', 'QUEUE',
                    '--object_names', 'Ethernet0|0',
                    '--object_counters', 'PACKETS'
                ]
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_GROUP/profileA|QUEUE',
            'value': {
                'object_names': ['Ethernet0|0'],
                'object_counters': ['PACKETS']
            }
        }]

    def test_add_aggregator_preserves_existing_table_entries(self):
        with patch('config.hft._get_table_or_fail', return_value={'ag0': {}}), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'aggregator', 'ag1', '--reporting_rate', '1000']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR/ag1',
            'value': {'reporting_rate': '1000'}
        }]

    def test_add_aggregator_rejects_existing_entry_before_patch(self):
        class MockCfgDb:
            def get_table(self, name):
                return {
                    config_hft.AGGREGATOR_TABLE_NAME: {
                        'ag0': {
                            'heatmap_interval': '1000000',
                            'heatmap_counters': ['PORT|IF_OUT_OCTETS']
                        }
                    },
                    config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: {
                        'ag0|PORT|IF_OUT_OCTETS': {'explicit_bounds': ['0', '1024']}
                    },
                    config_hft.AGGREGATOR_ROLLOVER_TABLE_NAME: {
                        'ag0|PORT|IF_IN_OCTETS': {'bit_width': '48'}
                    }
                }.get(name, {})

        obj = type('Obj', (), {'cfgdb': MockCfgDb()})
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                [
                    'add', 'aggregator', 'ag0',
                    '--heatmap_interval', '1000000',
                    '--heatmap_counters', 'PORT|IF_OUT_ERRORS'
                ],
                obj=obj
            )

        assert result.exit_code == 1
        assert "Aggregator 'ag0' already exists." in result.output
        mock_process.assert_not_called()

    def test_add_aggregator_fails_closed_when_table_read_fails(self):
        class MockCfgDb:
            def get_table(self, _name):
                raise RuntimeError('database unavailable')

        obj = type('Obj', (), {'cfgdb': MockCfgDb()})
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['add', 'aggregator', 'ag0', '--reporting_rate', '1000'],
                obj=obj
            )

        assert result.exit_code == 1
        assert "Failed to read Config DB table" in result.output
        assert 'database unavailable' in result.output
        mock_process.assert_not_called()

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

    def test_bind_aggregator_sets_profile_aggregator_patch(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['bind-aggregator', 'profileA', 'ag0']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'add',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE/profileA/aggregator',
            'value': 'ag0'
        }]
        assert payload == expected_payload

    def test_unbind_aggregator_removes_profile_aggregator_patch(self):
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['unbind-aggregator', 'profileA']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_PROFILE/profileA/aggregator'
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

    def test_delete_aggregator_removes_entry(self):
        with patch('config.hft._is_last_entry', return_value=False), \
                patch('config.hft._get_aggregator_users', return_value=[]), \
                patch('config.hft._has_table_entry', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'ag0']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR/ag0'
        }]
        assert payload == expected_payload

    def test_delete_aggregator_removes_entire_table_when_last_entry(self):
        with patch('config.hft._is_last_entry', return_value=True), \
                patch('config.hft._get_aggregator_users', return_value=[]), \
                patch('config.hft._has_table_entry', return_value=True), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'ag0']
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        expected_payload = [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR'
        }]
        assert payload == expected_payload

    def test_delete_histogram_rejects_missing_entry_in_empty_table(self):
        obj = _make_cli_obj({})
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'histogram', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 1
        assert "Histogram 'ag0|PORT|IF_OUT_OCTETS' does not exist." in result.output
        mock_process.assert_not_called()

    def test_delete_histogram_rejects_missing_entry_with_one_unrelated_row(self):
        obj = _make_cli_obj({
            config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: {
                'ag1|PORT|IF_IN_OCTETS': {}
            }
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'histogram', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 1
        assert "Histogram 'ag0|PORT|IF_OUT_OCTETS' does not exist." in result.output
        mock_process.assert_not_called()

    def test_delete_histogram_removes_exact_tuple_key(self):
        obj = _make_cli_obj({
            config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: {
                ('ag0', 'PORT', 'IF_OUT_OCTETS'): {},
                'ag1|QUEUE|BYTES': {}
            }
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'histogram', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'remove',
            'path': (
                '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                'ag0|PORT|IF_OUT_OCTETS'
            )
        }]

    def test_delete_histogram_removes_exact_list_key(self):
        class ListKeyTable:
            def __iter__(self):
                return iter([
                    ['ag0', 'PORT', 'IF_OUT_OCTETS'],
                    'ag1|QUEUE|BYTES'
                ])

        obj = _make_cli_obj({
            config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: ListKeyTable()
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'histogram', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'remove',
            'path': (
                '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                'ag0|PORT|IF_OUT_OCTETS'
            )
        }]

    def test_delete_histogram_removes_table_for_exact_sole_string_key(self):
        obj = _make_cli_obj({
            config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: {
                'ag0|PORT|IF_OUT_OCTETS': {}
            }
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'histogram', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM'
        }]

    def test_delete_rollover_rejects_missing_entry_in_empty_table(self):
        obj = _make_cli_obj({})
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'rollover', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 1
        assert "Rollover 'ag0|PORT|IF_OUT_OCTETS' does not exist." in result.output
        mock_process.assert_not_called()

    def test_delete_rollover_does_not_remove_unrelated_sole_row(self):
        obj = _make_cli_obj({
            config_hft.AGGREGATOR_ROLLOVER_TABLE_NAME: {
                'ag1|PORT|IF_IN_OCTETS': {'bit_width': '32'}
            }
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'rollover', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 1
        assert "Rollover 'ag0|PORT|IF_OUT_OCTETS' does not exist." in result.output
        mock_process.assert_not_called()

    def test_delete_rollover_removes_exact_tuple_key(self):
        obj = _make_cli_obj({
            config_hft.AGGREGATOR_ROLLOVER_TABLE_NAME: {
                ('ag0', 'PORT', 'IF_OUT_OCTETS'): {'bit_width': '32'},
                'ag1|QUEUE|BYTES': {'bit_width': '16'}
            }
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'rollover', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'remove',
            'path': (
                '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER/'
                'ag0|PORT|IF_OUT_OCTETS'
            )
        }]

    def test_delete_rollover_removes_exact_list_key(self):
        class ListKeyTable:
            def __iter__(self):
                return iter([
                    ['ag0', 'PORT', 'IF_OUT_OCTETS'],
                    'ag1|QUEUE|BYTES'
                ])

        obj = _make_cli_obj({
            config_hft.AGGREGATOR_ROLLOVER_TABLE_NAME: ListKeyTable()
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'rollover', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'remove',
            'path': (
                '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER/'
                'ag0|PORT|IF_OUT_OCTETS'
            )
        }]

    def test_delete_rollover_removes_table_for_exact_sole_string_key(self):
        obj = _make_cli_obj({
            config_hft.AGGREGATOR_ROLLOVER_TABLE_NAME: {
                'ag0|PORT|IF_OUT_OCTETS': {'bit_width': '32'}
            }
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'rollover', 'ag0', 'PORT|IF_OUT_OCTETS'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [{
            'op': 'remove',
            'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER'
        }]

    def test_delete_aggregator_cascades_histograms_before_parent(self):
        class MockCfgDb:
            def get_table(self, name):
                return {
                    config_hft.PROFILE_TABLE_NAME: {},
                    config_hft.AGGREGATOR_TABLE_NAME: {
                        'ag0': {},
                        'ag1': {}
                    },
                    config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: {
                        'ag0|QUEUE|BYTES': {},
                        ('ag0', 'PORT', 'IF_OUT_OCTETS'): {},
                        'ag1|PORT|IF_IN_OCTETS': {}
                    }
                }.get(name, {})

        obj = type('Obj', (), {'cfgdb': MockCfgDb()})
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'ag0'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [
            {
                'op': 'remove',
                'path': (
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                    'ag0|PORT|IF_OUT_OCTETS'
                )
            },
            {
                'op': 'remove',
                'path': (
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                    'ag0|QUEUE|BYTES'
                )
            },
            {
                'op': 'remove',
                'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR/ag0'
            }
        ]

    def test_delete_last_aggregator_cascades_entire_histogram_table(self):
        class MockCfgDb:
            def get_table(self, name):
                return {
                    config_hft.PROFILE_TABLE_NAME: {},
                    config_hft.AGGREGATOR_TABLE_NAME: {'ag0': {}},
                    config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: {
                        'ag0|PORT|IF_OUT_OCTETS': {},
                        'ag0|QUEUE|BYTES': {}
                    }
                }.get(name, {})

        obj = type('Obj', (), {'cfgdb': MockCfgDb()})
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'ag0'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert payload == [
            {
                'op': 'remove',
                'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM'
            },
            {
                'op': 'remove',
                'path': '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR'
            }
        ]

    @pytest.mark.parametrize(
        'histograms,rollovers,expected_children',
        [
            (
                {},
                {'ag0|PORT|IF_OUT_OCTETS': {}},
                ['/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER']
            ),
            (
                {},
                {
                    ('ag0', 'PORT', 'IF_OUT_OCTETS'): {},
                    'ag1|QUEUE|BYTES': {}
                },
                [
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER/'
                    'ag0|PORT|IF_OUT_OCTETS'
                ]
            ),
            (
                {'ag0|QUEUE|BYTES': {}},
                {'ag0|PORT|IF_OUT_OCTETS': {}},
                [
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM',
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER'
                ]
            ),
            (
                {'ag0|QUEUE|BYTES': {}},
                {
                    'ag0|PORT|IF_OUT_OCTETS': {},
                    'ag1|QUEUE|BYTES': {}
                },
                [
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM',
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER/'
                    'ag0|PORT|IF_OUT_OCTETS'
                ]
            ),
            (
                {
                    'ag0|QUEUE|BYTES': {},
                    'ag1|PORT|IF_IN_OCTETS': {}
                },
                {'ag0|PORT|IF_OUT_OCTETS': {}},
                [
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                    'ag0|QUEUE|BYTES',
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER'
                ]
            ),
            (
                {
                    'ag0|QUEUE|BYTES': {},
                    'ag1|PORT|IF_IN_OCTETS': {}
                },
                {
                    'ag0|PORT|IF_OUT_OCTETS': {},
                    'ag1|QUEUE|BYTES': {}
                },
                [
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM/'
                    'ag0|QUEUE|BYTES',
                    '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER/'
                    'ag0|PORT|IF_OUT_OCTETS'
                ]
            ),
        ]
    )
    def test_delete_aggregator_cascades_each_child_table_independently(
            self, histograms, rollovers, expected_children):
        obj = _make_cli_obj({
            config_hft.PROFILE_TABLE_NAME: {},
            config_hft.AGGREGATOR_TABLE_NAME: {'ag0': {}, 'ag1': {}},
            config_hft.AGGREGATOR_HISTOGRAM_TABLE_NAME: histograms,
            config_hft.AGGREGATOR_ROLLOVER_TABLE_NAME: rollovers
        })
        with patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'ag0'],
                obj=obj
            )

        assert result.exit_code == 0
        _, payload = mock_process.call_args[0]
        assert [entry['path'] for entry in payload] == [
            *expected_children,
            '/HIGH_FREQUENCY_TELEMETRY_AGGREGATOR/ag0'
        ]

    def test_delete_aggregator_rejected_when_profile_still_references_it(self):
        with patch('config.hft._get_aggregator_users', return_value=['profileA']), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'ag0']
            )

        assert result.exit_code == 1
        assert "Cannot delete aggregator 'ag0'" in result.output
        assert 'profileA' in result.output
        mock_process.assert_not_called()

    def test_delete_aggregator_rejected_when_aggregator_does_not_exist(self):
        with patch('config.hft._get_aggregator_users', return_value=[]), \
                patch('config.hft._has_table_entry', return_value=False), \
                patch('config.hft._process_payload') as mock_process:
            result = self.runner.invoke(
                config_hft.hft,
                ['del', 'aggregator', 'missing']
            )

        assert result.exit_code == 1
        assert "Aggregator 'missing' does not exist." in result.output
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


def test_aggregator_table_helpers():
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

    tables = {
        'HIGH_FREQUENCY_TELEMETRY_AGGREGATOR': {
            'ag0': {},
            'ag1': {}
        },
        'HIGH_FREQUENCY_TELEMETRY_PROFILE': {
            'profileB': {'aggregator': 'ag0'},
            'profileA': {'aggregator': 'ag0'},
            'profileC': {'aggregator': 'ag1'},
            'profileD': {}
        }
    }
    ctx = MockCtx(tables)

    assert config_hft._has_table_entry(ctx, 'HIGH_FREQUENCY_TELEMETRY_AGGREGATOR', 'ag0') is True
    assert config_hft._has_table_entry(ctx, 'HIGH_FREQUENCY_TELEMETRY_AGGREGATOR', 'missing') is False
    assert config_hft._get_aggregator_users(ctx, 'ag0') == ['profileA', 'profileB']
    assert config_hft._get_aggregator_users(ctx, 'missing') == []


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
