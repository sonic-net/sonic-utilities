"""
Unit tests for utilities_common/bfd_util.py
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from utilities_common import bfd_util


class TestBfdUtil:
    """Test class for BFD utility functions"""

    @pytest.fixture
    def mock_config_db(self):
        """Mock ConfigDBConnector"""
        mock_db = MagicMock()
        return mock_db

    def test_is_software_bfd_enabled_true(self, mock_config_db):
        """Test is_software_bfd_enabled returns True when enabled"""
        mock_config_db.get_entry.return_value = {"status": "enabled"}

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.is_software_bfd_enabled()

        assert result is True
        mock_config_db.get_entry.assert_called_once_with("SYSTEM_DEFAULTS", "software_bfd")

    def test_is_software_bfd_enabled_false(self, mock_config_db):
        """Test is_software_bfd_enabled returns False when disabled"""
        mock_config_db.get_entry.return_value = {"status": "disabled"}

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.is_software_bfd_enabled()

        assert result is False

    def test_is_software_bfd_enabled_not_configured(self, mock_config_db):
        """Test is_software_bfd_enabled returns False when not configured"""
        mock_config_db.get_entry.return_value = {}

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.is_software_bfd_enabled()

        assert result is False

    def test_get_bfd_peers_from_config_bgp_neighbors(self, mock_config_db):
        """Test get_bfd_peers_from_config extracts BGP neighbors with BFD enabled"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table
            {},
            # BGP_NEIGHBOR table
            {
                ("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"},
                ("default", "10.0.0.2"): {"bfd": "false", "asn": "65002"},
                ("default", "10.0.0.3"): {"asn": "65003"},  # No BFD field
            },
            # BGP_INTERNAL_NEIGHBOR table
            {
                "fc00::1": {"bfd": "true", "asn": "65100"},
            },
            # STATIC_ROUTE table
            {}
        ]

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        assert result == {"10.0.0.1", "fc00::1"}

    def test_get_bfd_peers_from_config_static_routes(self, mock_config_db):
        """Test get_bfd_peers_from_config extracts static route nexthops with BFD enabled"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table
            {},
            # BGP_NEIGHBOR table
            {},
            # BGP_INTERNAL_NEIGHBOR table
            {},
            # STATIC_ROUTE table
            {
                ("default", "192.168.0.0/24"): {"nexthop": "10.1.0.1,10.1.0.2", "bfd": "true"},
                ("default", "192.168.1.0/24"): {"nexthop": "10.2.0.1", "bfd": "false"},
                ("default", "192.168.2.0/24"): {"nexthop": "10.3.0.1"},  # No BFD field
            }
        ]

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        assert result == {"10.1.0.1", "10.1.0.2"}

    def test_get_bfd_peers_from_config_combined(self, mock_config_db):
        """Test get_bfd_peers_from_config with both BGP and static routes"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table
            {},
            # BGP_NEIGHBOR table
            {
                ("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"},
            },
            # BGP_INTERNAL_NEIGHBOR table
            {},
            # STATIC_ROUTE table
            {
                ("default", "192.168.0.0/24"): {"nexthop": "10.1.0.1", "bfd": "true"},
            }
        ]

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        assert result == {"10.0.0.1", "10.1.0.1"}

    def test_get_bfd_peers_from_config_peer_group(self, mock_config_db):
        """Test get_bfd_peers_from_config with BGP peer group BFD inheritance"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table
            {
                ("default", "PEER_V4"): {"bfd": "true", "asn": "65000"},
                ("default", "PEER_V6"): {"bfd": "false", "asn": "65000"},
            },
            # BGP_NEIGHBOR table
            {
                ("default", "10.0.0.1"): {"peer_group": "PEER_V4", "asn": "65001"},
                ("default", "10.0.0.2"): {"peer_group": "PEER_V6", "asn": "65002"},
                ("default", "10.0.0.3"): {"bfd": "true", "asn": "65003"},  # Direct BFD
            },
            # BGP_INTERNAL_NEIGHBOR table
            {},
            # STATIC_ROUTE table
            {}
        ]

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        # Should include: 10.0.0.1 (from PEER_V4 group), 10.0.0.3 (direct BFD)
        # Should NOT include: 10.0.0.2 (PEER_V6 has bfd=false)
        assert result == {"10.0.0.1", "10.0.0.3"}

    @patch('utilities_common.cli.run_command')
    def test_run_bfd_command_success(self, mock_run_command):
        """Test run_bfd_command executes vtysh successfully"""
        mock_run_command.return_value = ('{"peers": []}', 0)

        result = bfd_util.run_bfd_command("show bfd peers json")

        assert result == '{"peers": []}'
        mock_run_command.assert_called_once()

    @patch('utilities_common.cli.run_command')
    def test_run_bfd_command_failure(self, mock_run_command):
        """Test run_bfd_command handles vtysh failure"""
        mock_run_command.return_value = ('Error: command failed', 1)

        result = bfd_util.run_bfd_command("show bfd peers json")

        assert result is None

    @patch('utilities_common.bfd_util.run_bfd_command')
    def test_get_bfd_sessions_from_frr_success(self, mock_run_bfd_command):
        """Test get_bfd_sessions_from_frr parses FRR output correctly"""
        frr_output = json.dumps([
            {"peer": "10.0.0.1", "status": "up", "interface": "Ethernet0"},
            {"peer": "10.0.0.2", "status": "down", "interface": "Ethernet4"},
        ])
        mock_run_bfd_command.return_value = frr_output

        result = bfd_util.get_bfd_sessions_from_frr()

        assert len(result) == 2
        assert "10.0.0.1" in result
        assert "10.0.0.2" in result
        assert result["10.0.0.1"]["status"] == "up"

    @patch('utilities_common.bfd_util.run_bfd_command')
    def test_get_bfd_sessions_from_frr_empty(self, mock_run_bfd_command):
        """Test get_bfd_sessions_from_frr handles empty output"""
        mock_run_bfd_command.return_value = ''

        result = bfd_util.get_bfd_sessions_from_frr()

        assert result == {}

    @patch('utilities_common.bfd_util.run_bfd_command')
    def test_get_bfd_sessions_from_frr_invalid_json(self, mock_run_bfd_command):
        """Test get_bfd_sessions_from_frr handles invalid JSON"""
        mock_run_bfd_command.return_value = 'invalid json'

        result = bfd_util.get_bfd_sessions_from_frr()

        assert result == {}

    def test_filter_bfd_sessions_by_config(self):
        """Test filter_bfd_sessions_by_config filters sessions correctly"""
        frr_sessions = {
            "10.0.0.1": {"peer": "10.0.0.1", "status": "up"},
            "10.0.0.2": {"peer": "10.0.0.2", "status": "down"},
            "10.0.0.3": {"peer": "10.0.0.3", "status": "up"},
        }
        configured_peers = {"10.0.0.1", "10.0.0.3"}

        result = bfd_util.filter_bfd_sessions_by_config(frr_sessions, configured_peers)

        assert len(result) == 2
        assert any(s["peer"] == "10.0.0.1" for s in result)
        assert any(s["peer"] == "10.0.0.3" for s in result)
        assert not any(s["peer"] == "10.0.0.2" for s in result)

    def test_filter_bfd_sessions_by_config_empty_configured(self):
        """Test filter_bfd_sessions_by_config with no configured peers"""
        frr_sessions = {
            "10.0.0.1": {"peer": "10.0.0.1", "status": "up"},
        }
        configured_peers = set()

        result = bfd_util.filter_bfd_sessions_by_config(frr_sessions, configured_peers)

        assert len(result) == 0

    def test_filter_bfd_sessions_by_config_empty_frr(self):
        """Test filter_bfd_sessions_by_config with no FRR sessions"""
        frr_sessions = {}
        configured_peers = {"10.0.0.1"}

        result = bfd_util.filter_bfd_sessions_by_config(frr_sessions, configured_peers)

        assert len(result) == 0

    def test_get_bfd_peers_from_config_empty_tables(self, mock_config_db):
        """Test get_bfd_peers_from_config when all tables are empty"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table - empty
            {},
            # BGP_NEIGHBOR table - empty
            {},
            # BGP_INTERNAL_NEIGHBOR table - empty
            {},
            # STATIC_ROUTE table - empty
            {}
        ]

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        assert result == set()

    def test_get_bfd_peers_from_config_nonexistent_tables(self, mock_config_db):
        """Test get_bfd_peers_from_config when tables don't exist (get_table returns {})"""
        # When a table doesn't exist, ConfigDBConnector.get_table() returns {}
        mock_config_db.get_table.return_value = {}

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        # Should not raise AttributeError when calling .items() on empty dict
        assert result == set()

    @patch('utilities_common.cli.run_command')
    def test_run_bfd_command_returns_none_on_error(self, mock_run_command):
        """Test run_bfd_command returns None when command fails"""
        mock_run_command.return_value = ('Error: FRR not running', 127)

        result = bfd_util.run_bfd_command("show bfd peers json")

        assert result is None

    @patch('utilities_common.bfd_util.run_bfd_command')
    def test_get_bfd_sessions_from_frr_handles_none(self, mock_run_bfd_command):
        """Test get_bfd_sessions_from_frr handles None return from run_bfd_command"""
        mock_run_bfd_command.return_value = None

        result = bfd_util.get_bfd_sessions_from_frr()

        assert result == {}

    def test_get_bfd_peers_legacy_key_format(self, mock_config_db):
        """Test get_bfd_peers_from_config handles legacy key format (non-tuple)"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table
            {},
            # BGP_NEIGHBOR table - legacy format with string keys
            {
                "10.0.0.1": {"bfd": "true", "asn": "65001"},
                "10.0.0.2": {"asn": "65002"},
            },
            # BGP_INTERNAL_NEIGHBOR table
            {},
            # STATIC_ROUTE table
            {}
        ]

        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = bfd_util.get_bfd_peers_from_config()

        assert result == {"10.0.0.1"}

    def test_is_software_bfd_enabled_with_config_db_handle(self, mock_config_db):
        """Test is_software_bfd_enabled with pre-existing config_db handle"""
        mock_config_db.get_entry.return_value = {"status": "enabled"}

        # Pass config_db directly, should not call connect_config_db_for_ns
        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns') as mock_connect:
            result = bfd_util.is_software_bfd_enabled(config_db=mock_config_db)

        assert result is True
        # Should NOT have called connect_config_db_for_ns since we passed config_db
        mock_connect.assert_not_called()
        mock_config_db.get_entry.assert_called_once_with("SYSTEM_DEFAULTS", "software_bfd")

    def test_get_bfd_peers_from_config_with_config_db_handle(self, mock_config_db):
        """Test get_bfd_peers_from_config with pre-existing config_db handle"""
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP table
            {},
            # BGP_NEIGHBOR table
            {
                ("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"},
            },
            # BGP_INTERNAL_NEIGHBOR table
            {},
            # STATIC_ROUTE table
            {}
        ]

        # Pass config_db directly, should not call connect_config_db_for_ns
        with patch('sonic_py_common.multi_asic.connect_config_db_for_ns') as mock_connect:
            result = bfd_util.get_bfd_peers_from_config(config_db=mock_config_db)

        assert result == {"10.0.0.1"}
        # Should NOT have called connect_config_db_for_ns since we passed config_db
        mock_connect.assert_not_called()
