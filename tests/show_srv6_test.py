from unittest.mock import patch, MagicMock
from click.testing import CliRunner

with patch("utilities_common.multi_asic.multi_asic_ns_choices", return_value=['asic0', 'asic1']):
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
- Multi-ASIC support: Tests namespace handling and multi-ASIC scenarios

To run these tests:
    cd /path/to/sonic-utilities
    python -m pytest tests/show_srv6_test.py -v

To run specific test class:
    python -m pytest tests/show_srv6_test.py::TestShowSRv6Locators -v
    python -m pytest tests/show_srv6_test.py::TestShowSRv6StaticSids -v
    python -m pytest tests/show_srv6_test.py::TestShowSRv6EdgeCases -v
    python -m pytest tests/show_srv6_test.py::TestShowSRv6MultiAsic -v

To run with more verbose output:
    python -m pytest tests/show_srv6_test.py -v -s
"""


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
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{'
            '"dest":"10.0.0.1/32","sid":"2001:db8:1::1",'
            '"locator_block_len":"32","locator_node_len":"16","function_len":"16"}'
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
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'], ['2001:db8:1::1/128'])

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
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{'
            '"dest":"10.0.0.1/32","sid":"2001:db8:1::1",'
            '"locator_block_len":"32","locator_node_len":"16","function_len":"16"}'
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
        assert "Warning: SID entry ('InvalidKey',) is malformed" in result.output
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
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:INVALID_JSON'  # This should be skipped due to JSON error
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


class TestShowSRv6MultiAsic(object):
    def setup_method(self):
        print('SETUP MULTI-ASIC')

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_multi_asic_all_namespaces(
        self, mock_config_db, mock_is_multi_asic, mock_get_namespaces
    ):
        # Setup multi-ASIC environment
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector for different namespaces
        mock_db_asic0 = MagicMock()
        mock_db_asic1 = MagicMock()

        def config_db_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_db_asic0
            elif namespace == 'asic1':
                return mock_db_asic1
            return mock_db_asic0  # default

        mock_config_db.side_effect = config_db_side_effect

        # Mock data for different ASICs
        mock_locators_data_asic0 = {
            'Locator1': {
                'prefix': '2001:db8:1::/48',
                'block_len': '32',
                'node_len': '16',
                'func_len': '16'
            }
        }
        mock_locators_data_asic1 = {
            'Locator2': {
                'prefix': '2001:db8:2::/48',
                'block_len': '40',
                'node_len': '8',
                'func_len': '16'
            }
        }
        mock_db_asic0.get_table.return_value = mock_locators_data_asic0
        mock_db_asic1.get_table.return_value = mock_locators_data_asic1

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert 'Locator2' in result.output
        assert '2001:db8:1::/48' in result.output
        assert '2001:db8:2::/48' in result.output
        mock_db_asic0.connect.assert_called_once()
        mock_db_asic1.connect.assert_called_once()

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_multi_asic_specific_namespace(
        self, mock_config_db, mock_is_multi_asic, mock_get_namespaces
    ):
        # Setup multi-ASIC environment
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data for specific namespace
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
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'], ['-n', 'asic0'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert '2001:db8:1::/48' in result.output
        mock_db.connect.assert_called_once()

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_multi_asic_all_namespaces(
        self, mock_config_db, mock_sonic_v2, mock_is_multi_asic, mock_get_namespaces
    ):
        # Setup multi-ASIC environment
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector for different namespaces
        mock_config_db_asic0 = MagicMock()
        mock_config_db_asic1 = MagicMock()

        def config_db_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_config_db_asic0
            elif namespace == 'asic1':
                return mock_config_db_asic1
            return mock_config_db_asic0  # default

        mock_config_db.side_effect = config_db_side_effect

        # Mock SonicV2Connector for different namespaces
        mock_asic_db_asic0 = MagicMock()
        mock_asic_db_asic1 = MagicMock()

        def sonic_v2_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_asic_db_asic0
            elif namespace == 'asic1':
                return mock_asic_db_asic1
            return mock_asic_db_asic0  # default

        mock_sonic_v2.side_effect = sonic_v2_side_effect

        # Mock data for different ASICs
        mock_sids_data_asic0 = {
            ('Locator1', '2001:db8:1::1/128'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            }
        }
        mock_sids_data_asic1 = {
            ('Locator2', '2001:db8:2::1/128'): {
                'action': 'end.dt4',
                'decap_dscp_mode': 'pipe',
                'decap_vrf': 'Vrf2'
            }
        }
        mock_config_db_asic0.get_table.return_value = mock_sids_data_asic0
        mock_config_db_asic1.get_table.return_value = mock_sids_data_asic1

        # Mock ASIC data
        mock_asic_db_asic0.keys.return_value = [
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{'
            '"dest":"10.0.0.1/32","sid":"2001:db8:1::1",'
            '"locator_block_len":"32","locator_node_len":"16","function_len":"80"}'
        ]
        mock_asic_db_asic1.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/128' in result.output
        assert '2001:db8:2::1/128' in result.output
        assert 'Locator1' in result.output
        assert 'Locator2' in result.output
        mock_config_db_asic0.connect.assert_called_once()
        mock_config_db_asic1.connect.assert_called_once()

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_multi_asic_specific_namespace(
        self, mock_config_db, mock_sonic_v2, mock_is_multi_asic, mock_get_namespaces
    ):
        # Setup multi-ASIC environment
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock SonicV2Connector
        mock_asic_db = MagicMock()
        mock_sonic_v2.return_value = mock_asic_db

        # Mock data for specific namespace
        mock_sids_data = {
            ('Locator1', '2001:db8:1::1/128'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            }
        }
        mock_db.get_table.return_value = mock_sids_data
        mock_asic_db.keys.return_value = []

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'], ['-n', 'asic0'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/128' in result.output
        assert 'Locator1' in result.output
        mock_db.connect.assert_called_once()

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_multi_asic_empty_namespaces(
        self, mock_config_db, mock_is_multi_asic, mock_get_namespaces
    ):
        # Setup multi-ASIC environment with empty data
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector for different namespaces
        mock_db_asic0 = MagicMock()
        mock_db_asic1 = MagicMock()

        def config_db_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_db_asic0
            elif namespace == 'asic1':
                return mock_db_asic1
            return mock_db_asic0  # default

        mock_config_db.side_effect = config_db_side_effect

        # Mock empty data for both ASICs
        mock_db_asic0.get_table.return_value = {}
        mock_db_asic1.get_table.return_value = {}

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        # Should show header but no data rows
        assert 'Locator' in result.output
        assert 'Prefix' in result.output
        mock_db_asic0.connect.assert_called_once()
        mock_db_asic1.connect.assert_called_once()

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_single_asic_fallback(self, mock_config_db, mock_is_multi_asic, mock_get_namespaces):
        # Test single ASIC fallback when multi-ASIC is available but namespace is specified
        mock_is_multi_asic.return_value = False  # Single ASIC mode

        # Mock ConfigDBConnector
        mock_db = MagicMock()
        mock_config_db.return_value = mock_db

        # Mock data
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
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert '2001:db8:1::/48' in result.output
        mock_db.connect.assert_called_once()

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.SonicV2Connector')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_static_sids_multi_asic_mixed_offload_status(
        self, mock_config_db, mock_sonic_v2, mock_is_multi_asic, mock_get_namespaces
    ):
        # Test scenario where SIDs from different ASICs have different offload status
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector for different namespaces
        mock_config_db_asic0 = MagicMock()
        mock_config_db_asic1 = MagicMock()

        def config_db_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_config_db_asic0
            elif namespace == 'asic1':
                return mock_config_db_asic1
            return mock_config_db_asic0

        mock_config_db.side_effect = config_db_side_effect

        # Mock SonicV2Connector for different namespaces
        mock_asic_db_asic0 = MagicMock()
        mock_asic_db_asic1 = MagicMock()

        def sonic_v2_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_asic_db_asic0
            elif namespace == 'asic1':
                return mock_asic_db_asic1
            return mock_asic_db_asic0

        mock_sonic_v2.side_effect = sonic_v2_side_effect

        # Mock data for different ASICs - same SID prefix, different offload status
        mock_sids_data_asic0 = {
            ('Locator1', '2001:db8:1::1/64'): {
                'action': 'end',
                'decap_dscp_mode': 'uniform',
                'decap_vrf': 'Vrf1'
            }
        }
        mock_sids_data_asic1 = {
            ('Locator2', '2001:db8:2::1/64'): {
                'action': 'end.dt6',
                'decap_dscp_mode': 'pipe',
                'decap_vrf': 'Vrf2'
            }
        }
        mock_config_db_asic0.get_table.return_value = mock_sids_data_asic0
        mock_config_db_asic1.get_table.return_value = mock_sids_data_asic1

        # Only SID from asic0 is offloaded
        mock_asic_db_asic0.keys.return_value = [
            'ASIC_STATE:SAI_OBJECT_TYPE_SRV6_SID:{'
            '"dest":"10.0.0.1/32","sid":"2001:db8:1::1",'
            '"locator_block_len":"32","locator_node_len":"16","function_len":"16"}'
        ]
        mock_asic_db_asic1.keys.return_value = []  # No offloaded SIDs in asic1

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['static-sids'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert '2001:db8:1::1/64' in result.output
        assert '2001:db8:2::1/64' in result.output
        # Check that one is offloaded and one is not
        lines = result.output.split('\n')
        sid1_line = [line for line in lines if '2001:db8:1::1/64' in line]
        sid2_line = [line for line in lines if '2001:db8:2::1/64' in line]
        assert len(sid1_line) == 1
        assert len(sid2_line) == 1
        assert 'True' in sid1_line[0]  # Should be offloaded
        assert 'False' in sid2_line[0]  # Should not be offloaded

    @patch('sonic_py_common.multi_asic.get_namespace_list')
    @patch('sonic_py_common.multi_asic.is_multi_asic')
    @patch('show.srv6.ConfigDBConnector')
    def test_show_srv6_locators_multi_asic_with_locator_filter(
        self, mock_config_db, mock_is_multi_asic, mock_get_namespaces
    ):
        # Test filtering by specific locator in multi-ASIC scenario
        mock_is_multi_asic.return_value = True
        mock_get_namespaces.return_value = ['asic0', 'asic1']

        # Mock ConfigDBConnector for different namespaces
        mock_db_asic0 = MagicMock()
        mock_db_asic1 = MagicMock()

        def config_db_side_effect(namespace=None):
            if namespace == 'asic0':
                return mock_db_asic0
            elif namespace == 'asic1':
                return mock_db_asic1
            return mock_db_asic0

        mock_config_db.side_effect = config_db_side_effect

        # Mock data - only asic0 has the requested locator
        mock_locators_data_asic0 = {
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
        mock_locators_data_asic1 = {
            'Locator3': {
                'prefix': '2001:db8:3::/48',
                'block_len': '32',
                'node_len': '16',
                'func_len': '16'
            }
        }
        mock_db_asic0.get_table.return_value = mock_locators_data_asic0
        mock_db_asic1.get_table.return_value = mock_locators_data_asic1

        runner = CliRunner()
        result = runner.invoke(show.cli.commands['srv6'].commands['locators'], ['Locator1'])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert 'Locator1' in result.output
        assert '2001:db8:1::/48' in result.output
        # Should not show other locators
        assert 'Locator2' not in result.output
        assert 'Locator3' not in result.output
        assert '2001:db8:2::/48' not in result.output
        assert '2001:db8:3::/48' not in result.output

    def teardown_method(self):
        print('TEAR DOWN MULTI-ASIC')
