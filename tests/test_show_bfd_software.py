"""
Unit tests for 'show bfd' commands with software BFD support
"""
import json
import os
import pytest
from click.testing import CliRunner
from unittest import mock
from utilities_common.db import Db
from utilities_common import bfd_util
import show.main as show


class TestShowBfdSoftware:
    """Test class for show bfd commands with software BFD"""

    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @pytest.fixture
    def runner(self):
        """Click test runner"""
        return CliRunner()

    @pytest.fixture
    def db(self):
        """Database object"""
        return Db()

    def test_show_bfd_summary_software_bfd_enabled(self, runner, db):
        """Test show bfd summary with software BFD enabled"""
        # Mock FRR output
        frr_output = json.dumps([
            {
                "peer": "10.0.0.1",
                "interface": "Ethernet0",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1234567890
            }
        ])

        # Mock config DB
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"}},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        # Mock the functions
        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        # Restore
        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 1" in result.output
        assert "10.0.0.1" in result.output
        assert "Ethernet0" in result.output
        assert "up" in result.output

    def test_show_bfd_summary_software_bfd_filters_unconfigured(self, runner, db):
        """Test show bfd summary filters out unconfigured peers"""
        # Mock FRR output with two sessions (one not configured)
        frr_output = json.dumps([
            {
                "peer": "10.0.0.1",
                "interface": "Ethernet0",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1234567890
            },
            {
                "peer": "10.0.0.99",  # Not configured in CONFIG_DB
                "interface": "Ethernet4",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1234567891
            }
        ])

        # Mock config DB - only one BGP neighbor configured
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"}},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 1" in result.output
        assert "10.0.0.1" in result.output
        assert "10.0.0.99" not in result.output  # Should be filtered out

    def test_show_bfd_summary_software_bfd_static_routes(self, runner, db):
        """Test show bfd summary with static route BFD peers"""
        # Mock FRR output
        frr_output = json.dumps([
            {
                "peer": "10.1.0.1",
                "interface": "default",
                "vrf": "default",
                "status": "down",
                "type": "async_active",
                "local": "10.1.0.2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": True,
                "id": 9876543210
            }
        ])

        # Mock config DB - static route with BFD
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {("default", "192.168.0.0/24"): {"nexthop": "10.1.0.1", "bfd": "true"}}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 1" in result.output
        assert "10.1.0.1" in result.output

    def test_show_bfd_summary_hardware_bfd(self, runner, db):
        """Test show bfd summary with hardware BFD (backward compatibility)"""
        # Mock config DB - software BFD disabled
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "disabled"}

        # Set up STATE_DB with hardware BFD sessions
        dbconnector = db.db
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "state", "UP")
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "type", "async_active")
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "local_addr", "10.0.0.2")
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "tx_interval", "300")
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "rx_interval", "300")
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "multiplier", "3")
        dbconnector.set(dbconnector.STATE_DB,
                        "BFD_SESSION_TABLE|default|Ethernet0|10.0.0.1",
                        "multihop", "false")

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        assert result.exit_code == 0
        assert "10.0.0.1" in result.output
        assert "Ethernet0" in result.output

    def test_show_bfd_peer_software_bfd_found(self, runner, db):
        """Test show bfd peer with software BFD - peer found"""
        # Mock FRR output
        frr_output = json.dumps([
            {
                "peer": "10.0.0.1",
                "interface": "Ethernet0",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1234567890
            }
        ])

        # Mock config DB
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"}},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['peer'], ['10.0.0.1'], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions for peer IP 10.0.0.1: 1" in result.output
        assert "10.0.0.1" in result.output
        assert "Ethernet0" in result.output

    def test_show_bfd_peer_software_bfd_not_configured(self, runner, db):
        """Test show bfd peer with software BFD - peer not configured"""
        # Mock config DB - no BGP neighbors
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['peer'], ['10.0.0.99'], obj=db)

        assert result.exit_code == 0
        assert "No BFD sessions found for peer IP 10.0.0.99" in result.output

    def test_show_bfd_peer_software_bfd_configured_but_not_in_frr(self, runner, db):
        """Test show bfd peer - configured but session not up in FRR"""
        # Mock FRR output - empty (session not established yet)
        frr_output = json.dumps([])

        # Mock config DB - BGP neighbor configured
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"}},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['peer'], ['10.0.0.1'], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        # Should show no sessions because FRR doesn't have it yet
        assert "No BFD sessions found for peer IP 10.0.0.1" in result.output

    def test_show_bfd_summary_software_bfd_no_sessions(self, runner, db):
        """Test show bfd summary with software BFD but no sessions"""
        # Mock empty FRR output
        frr_output = json.dumps([])

        # Mock config DB - no configured peers
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {},
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 0" in result.output

    def test_show_bfd_summary_software_bfd_ipv6_and_multihop(self, runner, db):
        """Test show bfd summary with IPv6 peers and multihop sessions"""
        # Mock FRR output with IPv6 and multihop
        frr_output = json.dumps([
            {
                "peer": "fc00::1",
                "interface": "Ethernet0",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "fc00::2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1111111111
            },
            {
                "peer": "fc00::10",
                "interface": "default",
                "vrf": "default",
                "status": "down",
                "type": "async_active",
                "local": "fc00::2",
                "transmit-interval": 500,
                "receive-interval": 500,
                "detect-multiplier": 5,
                "multihop": True,
                "id": 2222222222
            }
        ])

        # Mock config DB - IPv6 BGP neighbor and static route
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {},
            # BGP_INTERNAL_NEIGHBOR
            {("default", "fc00::1"): {"bfd": "true", "asn": "65100"}},
            # STATIC_ROUTE
            {("default", "2001:db8::/32"): {"nexthop": "fc00::10", "bfd": "true"}}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 2" in result.output
        assert "fc00::1" in result.output
        assert "fc00::10" in result.output
        assert "yes" in result.output  # multihop = yes
        assert "no" in result.output   # multihop = no

    def test_show_bfd_summary_software_bfd_multiple_vrfs(self, runner, db):
        """Test show bfd summary with multiple VRFs"""
        # Mock FRR output with multiple VRFs
        frr_output = json.dumps([
            {
                "peer": "10.0.0.1",
                "interface": "Ethernet0",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.2",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 3333333333
            },
            {
                "peer": "10.1.0.1",
                "interface": "Ethernet4",
                "vrf": "VrfRed",
                "status": "up",
                "type": "async_active",
                "local": "10.1.0.2",
                "transmit-interval": 200,
                "receive-interval": 200,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 4444444444
            }
        ])

        # Mock config DB - BGP neighbors in different VRFs
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP
            {},
            # BGP_NEIGHBOR
            {
                ("default", "10.0.0.1"): {"bfd": "true", "asn": "65001"},
                ("VrfRed", "10.1.0.1"): {"bfd": "true", "asn": "65002"},
            },
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 2" in result.output
        assert "10.0.0.1" in result.output
        assert "10.1.0.1" in result.output
        assert "VrfRed" in result.output

    def test_show_bfd_summary_peer_group_inheritance(self, runner, db):
        """Test show bfd summary with BGP peer group BFD inheritance"""
        # Mock FRR output
        frr_output = json.dumps([
            {
                "peer": "10.0.0.1",
                "interface": "Ethernet0",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.10",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1234567890
            },
            {
                "peer": "10.0.0.3",
                "interface": "Ethernet2",
                "vrf": "default",
                "status": "up",
                "type": "async_active",
                "local": "10.0.0.11",
                "transmit-interval": 300,
                "receive-interval": 300,
                "detect-multiplier": 3,
                "multihop": False,
                "id": 1234567891
            }
        ])

        # Mock config DB - peer group with BFD and neighbors inheriting from it
        mock_config_db = mock.MagicMock()
        mock_config_db.get_entry.return_value = {"status": "enabled"}
        mock_config_db.get_table.side_effect = [
            # BGP_PEER_GROUP - PEER_V4 has BFD enabled
            {
                ("default", "PEER_V4"): {"bfd": "true", "asn": "65000"},
                ("default", "PEER_V6"): {"bfd": "false", "asn": "65000"},
            },
            # BGP_NEIGHBOR
            {
                ("default", "10.0.0.1"): {"peer_group": "PEER_V4", "asn": "65001"},  # Inherits BFD
                ("default", "10.0.0.2"): {"peer_group": "PEER_V6", "asn": "65002"},  # No BFD
                ("default", "10.0.0.3"): {"bfd": "true", "asn": "65003"},  # Direct BFD
            },
            # BGP_INTERNAL_NEIGHBOR
            {},
            # STATIC_ROUTE
            {}
        ]

        _old_run_bfd_command = bfd_util.run_bfd_command
        bfd_util.run_bfd_command = mock.MagicMock(return_value=frr_output)

        with mock.patch('sonic_py_common.multi_asic.connect_config_db_for_ns', return_value=mock_config_db):
            result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)

        bfd_util.run_bfd_command = _old_run_bfd_command

        assert result.exit_code == 0
        assert "Total number of BFD sessions: 2" in result.output
        # Should show 10.0.0.1 (inherited from PEER_V4) and 10.0.0.3 (direct BFD)
        assert "10.0.0.1" in result.output
        assert "10.0.0.3" in result.output
        # Should NOT show 10.0.0.2 (PEER_V6 has bfd=false)
        assert "10.0.0.2" not in result.output
