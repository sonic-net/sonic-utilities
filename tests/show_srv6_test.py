from unittest.mock import patch, MagicMock
from click.testing import CliRunner

import show.main as show

"""
Unit tests for SRv6 show commands (show srv6 locators and show srv6 static-sids)

These tests verify the functionality of the SRv6 show commands implemented in show/srv6.py.
The tests use mocking to simulate database responses and verify correct output formatting.

Test Coverage:
- show srv6 locators: All locators, specific locator, empty data, defaults, non-existent locator
- show srv6 static-sids: All SIDs, specific SID, empty data, defaults, invalid key format
- Offloading status: Tests ASIC_DB interaction and offload status determination
- Error handling: Database connection errors, malformed ASIC data
- Table formatting: Verifies headers and data formatting

To run these tests:
    cd /path/to/sonic-utilities
    python -m pytest tests/show_srv6_test.py -v

To run specific test class:
    python -m pytest tests/show_srv6_test.py::TestShowSRv6Locators -v
    python -m pytest tests/show_srv6_test.py::TestShowSRv6StaticSids -v
    python -m pytest tests/show_srv6_test.py::TestShowSRv6EdgeCases -v

To run with more verbose output:
    python -m pytest tests/show_srv6_test.py -v -s
"""

# NOTE: The current SRv6 implementation in show/srv6.py doesn't have proper error
# handling for ASIC_DB JSON parsing. These tests reveal areas where the implementation
# could be improved with try-catch blocks around:
# 1. entry.split(":", 2) operations
# 2. json.loads() calls
# 3. Field access like fields["sid"], fields["locator_block_len"], etc.
# The malformed data test cases below will currently cause the implementation to fail
# with exceptions, but ideally should be handled gracefully.


class TestShowSRv6Locators(object):
    def setup_method(self):
        print('SETUP')

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_all(self, mock_config_db):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_LOCATORS table
        mock_locators_data = {
            'Locator1': {
                'prefix': '2001:db8:1::/48',
                'block_len': '32',
                'node_len': '16',
                'func_len': '16'
            },
            'Locator2': {
                'prefix': '2001:db8:2::/48',
                'block_len': '40',
                'node_len': '8',
                'func_len': '16'
            }
        }
        mock_db.get_table.return_value = mock_locators_data

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert 'Locator2' in result.output
        assert '2001:db8:1::/48' in result.output
        assert '2001:db8:2::/48' in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_LOCATORS')

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_specific(self, mock_config_db):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_LOCATORS table
        mock_locators_data = {
            'Locator1': {
                'prefix': '2001:db8:1::/48',
                'block_len': '32',
                'node_len': '16',
                'func_len': '16'
            },
            'Locator2': {
                'prefix': '2001:db8:2::/48',
                'block_len': '40',
                'node_len': '8',
                'func_len': '16'
            }
        }
        mock_db.get_table.return_value = mock_locators_data

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'], ['Locator1'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert 'Locator2' not in result.output
        assert '2001:db8:1::/48' in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_LOCATORS')

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_empty(self, mock_config_db):
        # Mock ConfigDBConnector with empty data
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db
        mock_db.get_table.return_value = {}

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Should show header but no data rows
        assert 'Locator' in result.output
        assert 'Prefix' in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_LOCATORS')

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_with_defaults(self, mock_config_db):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data with missing optional fields (should use defaults)
        mock_locators_data = {
            'Locator1': {
                'prefix': '2001:db8:1::/48'
                # Missing block_len, node_len, func_len - should default to 32, 16, 16
            }
        }
        mock_db.get_table.return_value = mock_locators_data

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert '2001:db8:1::/48' in result.output
        # Check defaults are applied
        assert '32' in result.output  # default block_len
        assert '16' in result.output  # default node_len and func_len
        mock_db.connect.assert_called_once()

    def teardown_method(self):
        print('TEAR DOWN')


class TestShowSRv6StaticSids(object):
    def setup_method(self):
        print('SETUP')

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_all(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/128'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            },
            ('Locator2', '2001:db8:2::1/128'): {
                'action': 'end.dt4',
                'decap_dscp_mode': 'pipe',
                'decap_vrf': 'Vrf2'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = [
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{"dest":"10.0.0.1/32",\
            "sid":"2001:db8:1::1","locator_block_len":"32","locator_node_len":"16",\
            "function_len":"16"}'
        ]

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/128' in result.output
        assert '2001:db8:2::1/128' in result.output
        assert 'Locator1' in result.output
        assert 'Locator2' in result.output
        assert 'end' in result.output
        assert 'end.dt4' in result.output
        assert 'uniform' in result.output
        assert 'pipe' in result.output
        assert 'Vrf1' in result.output
        assert 'Vrf2' in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_SIDS')
        mock_asic_db.connect.assert_called_once_with(mock_asic_db.ASIC_DB)

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_specific(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/128'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            },
            ('Locator2', '2001:db8:2::1/128'): {
                'action': 'end.dt4',
                'decap_dscp_mode': 'pipe',
                'decap_vrf': 'Vrf2'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'], ['2001:db8:1::1'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/128' in result.output
        assert '2001:db8:2::1/128' not in result.output
        assert 'Locator1' in result.output
        assert 'Locator2' not in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_SIDS')

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_offloaded(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/64'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB with matching SID
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = [
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{"dest":"10.0.0.1/32",\
            "sid":"2001:db8:1::1","locator_block_len":"32","locator_node_len":"16",\
            "function_len":"16"}'
        ]

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/64' in result.output
        assert 'True' in result.output  # Should be offloaded
        mock_db.connect.assert_called_once()

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_not_offloaded(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/64'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB with no matching SID
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = []  # No offloaded SIDs

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/64' in result.output
        assert 'False' in result.output  # Should not be offloaded
        mock_db.connect.assert_called_once()

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_empty(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector with empty data
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db
        mock_db.get_table.return_value = {}

        # Mock SonicV2Connector for ASIC_DB
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Should show header but no data rows
        assert 'SID' in result.output
        assert 'Locator' in result.output
        assert 'Action' in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_SIDS')

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_with_defaults(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data with missing optional fields (should use defaults)
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/128'): {
                # Missing action, decap_dscp_mode, decap_vrf - should default to N/A
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/128' in result.output
        assert 'Locator1' in result.output
        # Check defaults are applied
        assert 'N/A' in result.output  # default for missing fields
        mock_db.connect.assert_called_once()

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_invalid_key_format(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data with invalid key format (should be skipped)
        mock_sids_data = {
            ('InvalidKey',): {  # Only one element, should be skipped
                'action': 'end'
            },
            ('Locator1', '2001:db8:1::1/128'): {  # Valid key
                'action': 'end'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Should only show the valid entry
        assert '2001:db8:1::1/128' in result.output
        assert 'Locator1' in result.output
        # Invalid key should not appear
        assert 'InvalidKey' not in result.output
        mock_db.connect.assert_called_once()

    def teardown_method(self):
        print('TEAR DOWN')


class TestShowSRv6EdgeCases(object):
    def setup_method(self):
        print('SETUP')

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_nonexistent_locator(self, mock_config_db):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_LOCATORS table
        mock_locators_data = {
            'Locator1': {
                'prefix': '2001:db8:1::/48',
                'block_len': '32',
                'node_len': '16',
                'func_len': '16'
            }
        }
        mock_db.get_table.return_value = mock_locators_data

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'], ['NonExistentLocator'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Should show header but no data rows since locator doesn't exist
        assert 'Locator' in result.output
        assert 'NonExistentLocator' not in result.output
        assert 'Locator1' not in result.output
        mock_db.connect.assert_called_once()
        mock_db.get_table.assert_called_once_with('SRV6_MY_LOCATORS')

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_asic_db_connection_error(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/128'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector to raise exception on keys() call
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.side_effect = Exception("Connection failed")

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 1
        mock_db.connect.assert_called_once()

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_malformed_asic_data(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/128'): {
                'action': 'end'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB with malformed data
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = [
            'MALFORMED_ENTRY',  # This should be skipped due to split error
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:INVALID_JSON',  # This should be skipped due to JSON error
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{"incomplete":"data"}'  # This should be skipped due to missing fields
        ]

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        # Test should complete successfully despite malformed ASIC data
        assert result.exit_code == 0
        assert '2001:db8:1::1/128' in result.output
        assert 'False' in result.output  # Should not be offloaded due to malformed data
        mock_db.connect.assert_called_once()

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_connection_error(self, mock_config_db):
        # Mock ConfigDBConnector to raise exception on connect
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db
        mock_db.connect.side_effect = Exception("Database connection failed")

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        # Should raise exception and exit with non-zero code
        assert result.exit_code != 0

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_config_db_connection_error(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector to raise exception on connect
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db
        mock_db.connect.side_effect = Exception("Database connection failed")

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        # Should raise exception and exit with non-zero code
        assert result.exit_code != 0

    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_table_format(self, mock_config_db):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_LOCATORS table
        mock_locators_data = {
            'TestLocator': {
                'prefix': '2001:db8:100::/48',
                'block_len': '40',
                'node_len': '8',
                'func_len': '16'
            }
        }
        mock_db.get_table.return_value = mock_locators_data

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Verify all expected headers are present
        headers = ['Locator', 'Prefix', 'Block Len', 'Node Len', 'Func Len']
        for header in headers:
            assert header in result.output

        # Verify data is formatted correctly in the output
        assert 'TestLocator' in result.output
        assert '2001:db8:100::/48' in result.output
        assert '40' in result.output
        assert '8' in result.output
        assert '16' in result.output

    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_table_format(self, mock_config_db, mock_sonic_v2):
        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for SRV6_MY_SIDS table
        mock_sids_data = {
            ('TestLocator', '2001:db8:100::100/128'): {
                'action': 'end.dt6',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'TestVrf'
            }
        }
        mock_db.get_table.return_value = mock_sids_data

        # Mock SonicV2Connector for ASIC_DB
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db
        mock_asic_db.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Verify all expected headers are present
        headers = ['SID', 'Locator', 'Action', 'Decap DSCP Mode', 'Decap VRF', 'Offloaded']
        for header in headers:
            assert header in result.output

        # Verify data is formatted correctly in the output
        assert '2001:db8:100::100/128' in result.output
        assert 'TestLocator' in result.output
        assert 'end.dt6' in result.output
        assert 'uniform' in result.output
        assert 'TestVrf' in result.output
        assert 'False' in result.output  # Not offloaded

    def teardown_method(self):
        print('TEAR DOWN')
