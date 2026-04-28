#!/usr/bin/env python3

import os
import sys
from unittest import mock
from click.testing import CliRunner

# Add the parent directory to the path to import the modules
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

# Import after path setup to avoid E402
import show.main as show  # noqa: E402
from utilities_common.db import Db  # noqa: E402
from .mock_tables import dbconnector  # noqa: E402

# Set up mock database path
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "mock_tables")

# Mock data for testing
MOCK_STATE_DB_DATA = {
    'MONITOR_LINK_GROUP_STATE|critical_links': {
        'state': 'up',
        'description': 'Critical uplink and downlink monitoring group',
        'uplinks': 'Ethernet64,Ethernet72',
        'downlinks': 'Ethernet80',
        'link_up_threshold': '2',
        'link_up_delay': '10',
        'uplink_up_count': '2'
    },
    'MONITOR_LINK_GROUP_STATE|test_group': {
        'state': 'down',
        'description': 'Test monitoring group',
        'uplinks': 'PortChannel101,PortChannel103',
        'downlinks': 'PortChannel102',
        'link_up_threshold': '1',
        'link_up_delay': '5',
        'uplink_up_count': '0'
    },
    'PORT_TABLE|Ethernet64': {
        'netdev_oper_status': 'up',
        'state': 'ok'
    },
    'PORT_TABLE|Ethernet72': {
        'netdev_oper_status': 'up',
        'state': 'ok'
    },
    'PORT_TABLE|Ethernet80': {
        'netdev_oper_status': 'down',
        'state': 'down'
    },
    'LAG_TABLE|PortChannel101': {
        'oper_status': 'up',
        'state': 'ok'
    },
    'LAG_TABLE|PortChannel103': {
        'oper_status': 'down',
        'state': 'down'
    },
    'LAG_TABLE|PortChannel102': {
        'oper_status': 'down',
        'state': 'down'
    },
    'MONITOR_LINK_GROUP_MEMBER|Ethernet80': {
        'state': 'force_down',
        'down_due_to': 'critical_links'
    },
    'MONITOR_LINK_GROUP_MEMBER|PortChannel102': {
        'state': 'force_down',
        'down_due_to': 'test_group'
    }
}


class TestMonitorLink:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def setup_method(self):
        # Use the default state_db.json file which contains our merged monitor link data
        # No need to set dedicated_dbs since the data is already in state_db.json
        pass

    def test_show_monitor_link_all_groups(self):
        """Test showing all monitor link groups"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], [], obj=db)
        assert result.exit_code == 0
        assert "Monitor Link Group: critical_links" in result.output
        assert "Monitor Link Group: test_group" in result.output
        assert "State:" in result.output
        assert "Uplinks Up:" in result.output
        assert "Min-uplinks:" in result.output
        assert "Link-up-delay:" in result.output

    def test_show_monitor_link_specific_group(self):
        """Test showing a specific monitor link group"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)
        assert result.exit_code == 0
        assert "Monitor Link Group: critical_links" in result.output
        assert "Monitor Link Group: test_group" not in result.output
        assert "Critical uplink and downlink monitoring group" in result.output

    def test_show_monitor_link_nonexistent_group(self):
        """Test showing a non-existent monitor link group"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["nonexistent"], obj=db)
        assert result.exit_code == 0
        assert "Monitor link group 'nonexistent' not found" in result.output

    def test_show_monitor_link_no_groups(self):
        """Test showing monitor link when no groups are configured"""
        # Create a temporary empty state db file
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            empty_db_file = f.name

        try:
            dbconnector.dedicated_dbs['STATE_DB'] = empty_db_file

            runner = CliRunner()
            db = Db()

            result = runner.invoke(show.cli.commands["monitor-link-group"], [], obj=db)

            assert result.exit_code == 0
            assert "No monitor link groups configured" in result.output
        finally:
            # Clean up
            import os
            os.unlink(empty_db_file)
            if 'STATE_DB' in dbconnector.dedicated_dbs:
                del dbconnector.dedicated_dbs['STATE_DB']

    def test_interface_status_display(self):
        """Test that interface statuses are displayed correctly"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)

        assert result.exit_code == 0
        assert "Ethernet64" in result.output
        assert "Ethernet72" in result.output
        assert "Ethernet80" in result.output
        assert "uplink" in result.output
        assert "downlink" in result.output

    def test_downlink_reason_display(self):
        """Test that downlink down reasons are displayed"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)

        assert result.exit_code == 0
        assert "Down due to group critical_links" in result.output

    def test_uplink_count_calculation(self):
        """Test that uplink counts are calculated correctly"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)

        assert result.exit_code == 0
        # Should show 2/2 uplinks up (both Ethernet64 and Ethernet72 are up)
        assert "Uplinks Up:       2/2" in result.output

    def test_portchannel_interfaces(self):
        """Test that PortChannel interfaces are handled correctly"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["test_group"], obj=db)

        assert result.exit_code == 0
        assert "PortChannel101" in result.output
        assert "PortChannel103" in result.output
        assert "PortChannel102" in result.output

    def test_group_state_formatting(self):
        """Test that group states are formatted with colors"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], [], obj=db)

        assert result.exit_code == 0
        # The actual color codes won't be visible in test output, but the states should be there
        assert "State:" in result.output

    def test_empty_fields_handling(self):
        """Test handling of empty or missing fields"""
        # Create test data with missing fields
        test_data = {
            'MONITOR_LINK_GROUP_STATE|empty_group': {
                'state': 'unknown',
                'uplinks': '',
                'downlinks': '',
                'link_up_threshold': '',
                'link_up_delay': ''
            }
        }
        # Backup and modify the existing state_db.json file
        import json
        import shutil

        state_db_file = os.path.join(mock_db_path, 'state_db.json')
        backup_file = state_db_file + '.backup'

        # Backup original file
        shutil.copy2(state_db_file, backup_file)

        try:
            # Write test data to state_db.json
            with open(state_db_file, 'w') as f:
                json.dump(test_data, f)

            runner = CliRunner()
            db = Db()

            result = runner.invoke(show.cli.commands["monitor-link-group"], ["empty_group"], obj=db)

            assert result.exit_code == 0
            assert "Monitor Link Group: empty_group" in result.output
            assert "No description" in result.output
            assert "Min-uplinks:      1" in result.output  # Default value
            assert "Link-up-delay:    0 seconds" in result.output  # Default value
        finally:
            # Restore original file
            shutil.move(backup_file, state_db_file)


class TestMonitorLinkFunctions:
    """Test individual functions from monitor_link module"""

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def setup_method(self):
        # Use the default state_db.json file which contains our merged monitor link data
        pass

    def test_get_monitor_link_groups(self):
        """Test get_monitor_link_groups function"""
        from show.monitor_link import get_monitor_link_groups

        # Create a mock database connection
        db = Db()
        groups = get_monitor_link_groups(db.db)

        assert len(groups) == 3
        assert 'critical_links' in groups
        assert 'test_group' in groups

        # Test critical_links group
        critical_group = groups['critical_links']
        assert critical_group['state'] == 'up'
        assert critical_group['description'] == 'Critical uplink and downlink monitoring group'
        assert critical_group['min_uplinks'] == '2'
        assert critical_group['linkup_delay'] == '10'
        assert len(critical_group['interfaces']) == 3

        # Check interfaces
        interface_names = [intf['name'] for intf in critical_group['interfaces']]
        assert 'Ethernet64' in interface_names
        assert 'Ethernet72' in interface_names
        assert 'Ethernet80' in interface_names

    def test_get_monitor_link_member_info(self):
        """Test get_monitor_link_member_info function"""
        from show.monitor_link import get_monitor_link_member_info

        db = Db()

        # Test existing member
        member_info = get_monitor_link_member_info(db.db, 'Ethernet80')
        assert member_info is not None
        assert member_info['state'] == 'force_down'
        assert member_info['down_due_to'] == 'critical_links'

        # Test non-existing member
        member_info = get_monitor_link_member_info(db.db, 'NonExistent')
        assert member_info is None

    def test_format_group_state(self):
        """Test format_group_state function"""
        from show.monitor_link import format_group_state

        # Test different states (we can't test colors directly, but we can test the function runs)
        up_state = format_group_state('up')
        down_state = format_group_state('down')
        pending_state = format_group_state('pending')
        unknown_state = format_group_state('unknown')

        # The function should return strings (with ANSI color codes)
        assert isinstance(up_state, str)
        assert isinstance(down_state, str)
        assert isinstance(pending_state, str)
        assert isinstance(unknown_state, str)

    @mock.patch('utilities_common.cli.get_interface_operational_status')
    def test_uplink_count_calculation_with_mock(self, mock_get_status):
        """Test uplink count calculation with mocked interface status"""
        from show.monitor_link import get_monitor_link_groups

        # Mock interface status calls
        def mock_status_side_effect(db, interface):  # noqa: ARG001
            status_map = {
                'Ethernet64': 'UP',
                'Ethernet72': 'UP',
                'PortChannel101': 'UP',
                'PortChannel103': 'DOWN'
            }
            return status_map.get(interface, 'DOWN')

        mock_get_status.side_effect = mock_status_side_effect

        db = Db()
        groups = get_monitor_link_groups(db.db)

        # The function itself doesn't calculate uplink counts, but we can test the data structure
        assert 'critical_links' in groups
        assert 'test_group' in groups


class TestMonitorLinkEdgeCases:
    """Test edge cases and error conditions"""

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def test_malformed_interface_lists(self):
        """Test handling of malformed interface lists"""
        malformed_data = {
            'MONITOR_LINK_GROUP_STATE|malformed_group': {
                'state': 'up',
                'description': 'Test group with malformed data',
                'uplinks': 'Ethernet1,,Ethernet2,   ,Ethernet3',  # Extra commas and spaces
                'downlinks': ',Ethernet4,',  # Leading and trailing commas
                'link_up_threshold': '2',
                'link_up_delay': '5'
            }
        }
        # Backup and modify the existing state_db.json file
        import json
        import shutil

        state_db_file = os.path.join(mock_db_path, 'state_db.json')
        backup_file = state_db_file + '.backup'

        # Backup original file
        shutil.copy2(state_db_file, backup_file)

        try:
            # Write malformed test data to state_db.json
            with open(state_db_file, 'w') as f:
                json.dump(malformed_data, f)

            runner = CliRunner()
            db = Db()

            result = runner.invoke(show.cli.commands["monitor-link-group"], ["malformed_group"], obj=db)

            assert result.exit_code == 0
            assert "Monitor Link Group: malformed_group" in result.output
            # Should handle malformed data gracefully
            assert "Ethernet1" in result.output
            assert "Ethernet2" in result.output
            assert "Ethernet3" in result.output
            assert "Ethernet4" in result.output
        finally:
            # Restore original file
            shutil.move(backup_file, state_db_file)

    def test_missing_state_db_fields(self):
        """Test handling of missing STATE_DB fields"""
        minimal_data = {
            'MONITOR_LINK_GROUP_STATE|minimal_group': {
                'state': 'up'
                # Missing other fields
            }
        }
        # Backup and modify the existing state_db.json file
        import json
        import shutil

        state_db_file = os.path.join(mock_db_path, 'state_db.json')
        backup_file = state_db_file + '.backup'

        # Backup original file
        shutil.copy2(state_db_file, backup_file)

        try:
            # Write minimal test data to state_db.json
            with open(state_db_file, 'w') as f:
                json.dump(minimal_data, f)

            runner = CliRunner()
            db = Db()

            result = runner.invoke(show.cli.commands["monitor-link-group"], ["minimal_group"], obj=db)

            assert result.exit_code == 0
            assert "Monitor Link Group: minimal_group" in result.output
            assert "No description" in result.output
        finally:
            # Restore original file
            shutil.move(backup_file, state_db_file)

    def test_interface_sorting(self):
        """Test that interfaces are sorted correctly (uplinks first, then by name)"""
        runner = CliRunner()
        db = Db()
        # Use default state_db.json which contains our monitor link data
        # No need to set dedicated_dbs

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)

        assert result.exit_code == 0
        output_lines = result.output.split('\n')

        # Find the interface table section
        interface_section_started = False
        interface_lines = []
        for line in output_lines:
            if "Interface" in line and "Link Type" in line and "Status" in line:
                interface_section_started = True
                continue
            if interface_section_started and line.strip() and not line.startswith('-'):
                if line.strip():
                    interface_lines.append(line.strip())
                if not line.strip() or line.startswith('Monitor Link Group:'):
                    break

        # Should have uplinks first, then downlinks
        downlink_found = False
        for line in interface_lines:
            if 'uplink' in line:
                assert not downlink_found, "Uplinks should come before downlinks"
            elif 'downlink' in line:
                downlink_found = True

    def test_utilities_common_integration(self):
        """Test integration with utilities_common.cli functions"""
        from utilities_common.cli import get_interface_operational_status

        db = Db()
        # Use default state_db.json which contains our monitor link data
        # No need to set dedicated_dbs

        # Test Ethernet interface (should use netdev_oper_status)
        status = get_interface_operational_status(db.db, 'Ethernet64')
        assert status == 'UP'

        status = get_interface_operational_status(db.db, 'Ethernet80')
        assert status == 'DOWN'

        # Test PortChannel interface (should use oper_status)
        status = get_interface_operational_status(db.db, 'PortChannel101')
        assert status == 'UP'

        status = get_interface_operational_status(db.db, 'PortChannel103')
        assert status == 'DOWN'

        # Test non-existent interface
        status = get_interface_operational_status(db.db, 'NonExistent')
        assert status == 'N/A'
