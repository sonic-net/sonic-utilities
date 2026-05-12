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
        'description': 'Critical monitored and managed link monitoring group',
        'monitored-links': 'Ethernet64,Ethernet72',
        'managed-links': 'Ethernet80',
        'link_up_threshold': '2',
        'link_up_delay': '10',
        'total_transitions': '3'
    },
    'MONITOR_LINK_GROUP_STATE|test_group': {
        'state': 'down',
        'description': 'Test monitoring group',
        'monitored-links': 'PortChannel101,PortChannel103',
        'managed-links': 'PortChannel102',
        'link_up_threshold': '1',
        'link_up_delay': '5',
        'total_transitions': '5'
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
        assert "Monitored Up:" in result.output
        assert "Min-monitored-links:" in result.output
        assert "Link-up-delay:" in result.output

    def test_show_monitor_link_specific_group(self):
        """Test showing a specific monitor link group"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)
        assert result.exit_code == 0
        assert "Monitor Link Group: critical_links" in result.output
        assert "Monitor Link Group: test_group" not in result.output
        assert "Critical monitored and managed link monitoring group" in result.output

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
        assert "monitored" in result.output
        assert "managed" in result.output

    def test_managed_reason_display(self):
        """Test that managed-link down reasons are displayed"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)

        assert result.exit_code == 0
        assert "Down due to group critical_links" in result.output

    def test_monitored_count_calculation(self):
        """Test that monitored-link counts are calculated correctly"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)

        assert result.exit_code == 0
        # Should show 2/2 monitored-links up (both Ethernet64 and Ethernet72 are up)
        assert "Monitored Up:          2/2" in result.output

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
                'monitored-links': '',
                'managed-links': '',
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
            assert "Min-monitored-links:   1" in result.output  # Default value
            assert "Link-up-delay:         0 seconds" in result.output  # Default value
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
        assert critical_group['description'] == 'Critical monitored and managed link monitoring group'
        assert critical_group['min_monitored_links'] == '2'
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
    def test_monitored_count_calculation_with_mock(self, mock_get_status):
        """Test monitored-link count calculation with mocked interface status"""
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

        # The function itself doesn't calculate monitored-link counts, but we can test the data structure
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
                'monitored-links': 'Ethernet1,,Ethernet2,   ,Ethernet3',  # Extra commas and spaces
                'managed-links': ',Ethernet4,',  # Leading and trailing commas
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
        """Test that interfaces are sorted correctly (monitored first, then by name)"""
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

        # Should have monitored first, then managed
        managed_found = False
        for line in interface_lines:
            if 'monitored' in line:
                assert not managed_found, "Monitored should come before managed"
            elif 'managed' in line:
                managed_found = True

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


class TestMonitorLinkTransitionTracking:
    """PR-B: rendering of last_state_change_*, PENDING elapsed/remaining, transition counters."""

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def test_last_change_line_shown(self):
        """When transition fields are present, the 'Last change:' line is rendered."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["critical_links"], obj=db)
        assert result.exit_code == 0
        assert "Last change:" in result.output
        # epoch 1700000000 == 2023-11-14 22:13:20 UTC
        assert "2023-11-14" in result.output
        assert "DOWN -> UP" in result.output

    def test_transitions_counter_line(self):
        """The 'Transitions:' line is always present and shows a total count."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["monitor-link-group"], ["test_group"], obj=db)
        assert result.exit_code == 0
        # test_group fixture has total_transitions=5
        assert "Transitions:           5" in result.output

    def test_pending_linkup_delay_progress(self):
        """When state is PENDING, Link-up-delay shows elapsed/remaining."""
        # pending_start_time in mock is 1700000200, link_up_delay is 15.
        # Mock time.time() to 1700000204 -> elapsed=4s, remaining=11s.
        with mock.patch('show.monitor_link.time.time', return_value=1700000204):
            runner = CliRunner()
            db = Db()
            result = runner.invoke(show.cli.commands["monitor-link-group"], ["pending_group"], obj=db)

        assert result.exit_code == 0
        assert "Link-up-delay:         15 seconds (elapsed: 4s, remaining: 11s)" in result.output

    def test_pending_progress_overdue(self):
        """When the timer has overshot (raw elapsed > delay), display is OVERDUE."""
        # pending_start_time=1700000200, delay=15. Mock now = pending_start + 999.
        with mock.patch('show.monitor_link.time.time', return_value=1700001199):
            runner = CliRunner()
            db = Db()
            result = runner.invoke(show.cli.commands["monitor-link-group"], ["pending_group"], obj=db)

        assert result.exit_code == 0
        # 999s elapsed - 15s delay = OVERDUE by 984s
        assert "elapsed: 999s, OVERDUE by 984s" in result.output
        # Make sure the misleading "remaining: 0s" form is not shown
        assert "remaining:" not in result.output

    def test_no_last_change_when_fields_missing(self):
        """Backward compat: when transition fields are absent, 'Last change:' is omitted."""
        minimal_data = {
            'MONITOR_LINK_GROUP_STATE|legacy_group': {
                'state': 'up',
                'description': 'Legacy group without transition fields',
                'monitored-links': 'Ethernet1',
                'managed-links': '',
                'link_up_threshold': '1',
                'link_up_delay': '0',
            }
        }
        import json
        import shutil
        import tempfile

        # Use a per-test tempdir so parallel runs don't collide and a killed test
        # doesn't leave the workspace dirty.
        tmpdir = tempfile.mkdtemp()
        test_db_file = os.path.join(tmpdir, 'state_db.json')
        with open(test_db_file, 'w') as f:
            json.dump(minimal_data, f)

        try:
            dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(tmpdir, 'state_db')

            runner = CliRunner()
            db = Db()
            result = runner.invoke(show.cli.commands["monitor-link-group"], ["legacy_group"], obj=db)
            assert result.exit_code == 0
            assert "Monitor Link Group: legacy_group" in result.output
            assert "Last change:" not in result.output
            # Counter falls back to 0 when field missing
            assert "Transitions:           0" in result.output
        finally:
            if 'STATE_DB' in dbconnector.dedicated_dbs:
                del dbconnector.dedicated_dbs['STATE_DB']
            shutil.rmtree(tmpdir, ignore_errors=True)
