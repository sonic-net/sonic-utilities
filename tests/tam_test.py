import os
import json
from unittest import mock

from click.testing import CliRunner
from utilities_common.db import Db

import show.main as show


class TestTamModSessions(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_tam_mod_sessions_text_output(self):
        """Test 'show tam mod sessions' with table output."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["tam"].commands["mod"].commands["sessions"], obj=db)

        print(f"Exit code: {result.exit_code}")
        print(f"Output: \n{result.output}")

        assert result.exit_code == 0
        # Verify table headers are present
        assert "Session" in result.output
        assert "Status" in result.output
        assert "Event Type" in result.output
        assert "Drop Stages" in result.output
        assert "Collectors" in result.output
        assert "Flow Group" in result.output
        assert "Report Type" in result.output
        # Verify session data is present
        assert "SESSION1" in result.output
        assert "SESSION2" in result.output
        assert "SESSION3" in result.output
        assert "Active" in result.output
        assert "Inactive (Collector not reachable)" in result.output
        assert "Inactive (Configuration error)" in result.output

    def test_tam_mod_sessions_json_output(self):
        """Test 'show tam mod sessions --json' with JSON output."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            show.cli.commands["tam"].commands["mod"].commands["sessions"],
            ["--json"],
            obj=db
        )

        print(f"Exit code: {result.exit_code}")
        print(f"Output: \n{result.output}")

        assert result.exit_code == 0

        # Parse JSON output
        output = json.loads(result.output)
        assert isinstance(output, list)
        assert len(output) == 3

        # Find each session and verify fields
        session_map = {s["session_name"]: s for s in output}

        # Verify SESSION1 (active, no flow group)
        session1 = session_map.get("SESSION1")
        assert session1 is not None
        assert session1["status"] == "active"
        assert session1["event_type"] == "packet-drop-stateless"
        assert session1["drop_stages"] == "ingress,egress,tm"
        assert session1["collectors"] == "COLLECTOR1,COLLECTOR2"
        assert session1["flow_group"] == ""
        assert session1["report_type"] == "ipfix"
        assert session1["status_detail"] == ""  # Always present in JSON, empty for active

        # Verify SESSION2 (inactive, with flow group, collector not reachable)
        session2 = session_map.get("SESSION2")
        assert session2 is not None
        assert session2["status"] == "inactive"
        assert session2["event_type"] == "packet-drop-stateful"
        assert session2["drop_stages"] == "ingress"
        assert session2["collectors"] == "COLLECTOR3"
        assert session2["flow_group"] == "FG1"
        assert session2["report_type"] == "ipfix"
        assert session2["status_detail"] == "Collector not reachable"

        # Verify SESSION3 (inactive, configuration error)
        session3 = session_map.get("SESSION3")
        assert session3 is not None
        assert session3["status"] == "inactive"
        assert session3["status_detail"] == "Configuration error"
        assert session3["flow_group"] == ""

    def test_tam_mod_sessions_active_session_fields(self):
        """Test that active session shows 'Active' status without parenthetical detail."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["tam"].commands["mod"].commands["sessions"], obj=db)

        assert result.exit_code == 0
        # Active session should show just "Active" without parenthetical detail
        # In table format, "Active" appears without any additional detail
        assert "Active" in result.output
        # Verify the inactive sessions have their status details
        assert "Inactive (Collector not reachable)" in result.output
        assert "Inactive (Configuration error)" in result.output

    def test_tam_mod_sessions_flow_group_display(self):
        """Test that Flow Group column is displayed with values when configured."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["tam"].commands["mod"].commands["sessions"], obj=db)

        assert result.exit_code == 0
        # Flow Group column header should be present (table format)
        assert "Flow Group" in result.output
        # SESSION2 has flow group "FG1", should be displayed
        assert "FG1" in result.output

    @mock.patch('show.tam.TamModShow.get_all_sessions', return_value=[])
    def test_tam_mod_sessions_empty_text_output(self, mock_get_sessions):
        """Test 'show tam mod sessions' with no sessions configured (text output)."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["tam"].commands["mod"].commands["sessions"], obj=db)

        print(f"Exit code: {result.exit_code}")
        print(f"Output: \n{result.output}")

        assert result.exit_code == 0
        # When no sessions, table displays headers only with no data rows
        assert "Session" in result.output
        assert "Status" in result.output
        assert "Event Type" in result.output
        assert "Drop Stages" in result.output
        assert "Collectors" in result.output
        assert "Flow Group" in result.output
        assert "Report Type" in result.output
        # Verify no session data is present
        assert "SESSION1" not in result.output
        assert "SESSION2" not in result.output
        assert "SESSION3" not in result.output

    @mock.patch('show.tam.TamModShow.get_all_sessions', return_value=[])
    def test_tam_mod_sessions_empty_json_output(self, mock_get_sessions):
        """Test 'show tam mod sessions --json' with no sessions configured (JSON output)."""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            show.cli.commands["tam"].commands["mod"].commands["sessions"],
            ["--json"],
            obj=db
        )

        print(f"Exit code: {result.exit_code}")
        print(f"Output: \n{result.output}")

        assert result.exit_code == 0

        # Parse JSON output - should be an empty list
        output = json.loads(result.output)
        assert isinstance(output, list)
        assert len(output) == 0

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
