#!/usr/bin/env python3
"""
Unit tests for sonic-dpu-flow-dump.py
"""

import os
import sys
import json
import gzip
import tempfile
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from io import BytesIO

# Add the scripts directory to the path
test_path = os.path.dirname(os.path.abspath(__file__))
scripts_path = os.path.join(os.path.dirname(test_path), 'scripts')
sys.path.insert(0, scripts_path)

# Dynamically load the module since it has hyphens in the filename
import importlib.util
script_path = os.path.join(scripts_path, 'sonic-dpu-flow-dump.py')
spec = importlib.util.spec_from_file_location("sonic_dpu_flow_dump", script_path)
flow_dump = importlib.util.module_from_spec(spec)
sys.modules["sonic_dpu_flow_dump"] = flow_dump
spec.loader.exec_module(flow_dump)


class TestGenerateSessionName:
    """Test session name generation."""

    def test_generate_session_name_format(self):
        """Test that session name has correct format."""
        name = flow_dump.generate_session_name()
        assert name.startswith("flow_dump_session_")
        assert len(name) == len("flow_dump_session_") + 8

    def test_generate_session_name_unique(self):
        """Test that generated names are unique."""
        names = {flow_dump.generate_session_name() for _ in range(100)}
        assert len(names) == 100


class TestCheckSwitchType:
    """Test switch type checking."""

    @patch.object(flow_dump.swsscommon, 'DBConnector')
    @patch.object(flow_dump.swsscommon, 'Table')
    def test_is_dpu_type_dpu(self, mock_table_class, mock_db_connector):
        """Test switch type check for DPU."""
        mock_table = Mock()
        mock_table.hget.return_value = (True, "DPU")
        mock_table_class.return_value = mock_table

        result = flow_dump.is_dpu_type()

        assert result is True
        mock_db_connector.assert_called_once_with("CONFIG_DB", 0, True)
        mock_table_class.assert_called_once_with(mock_db_connector.return_value, "DEVICE_METADATA")
        mock_table.hget.assert_called_once_with("localhost", "switch_type")

    @patch.object(flow_dump.swsscommon, 'DBConnector')
    @patch.object(flow_dump.swsscommon, 'Table')
    def test_is_dpu_type_dpu_lowercase(self, mock_table_class, mock_db_connector):
        """Test switch type check for DPU (lowercase)."""
        mock_table = Mock()
        mock_table.hget.return_value = (True, "dpu")
        mock_table_class.return_value = mock_table

        result = flow_dump.is_dpu_type()

        assert result is True

    @patch.object(flow_dump.swsscommon, 'DBConnector')
    @patch.object(flow_dump.swsscommon, 'Table')
    def test_is_dpu_type_not_dpu(self, mock_table_class, mock_db_connector):
        """Test switch type check for non-DPU switch."""
        mock_table = Mock()
        mock_table.hget.return_value = (True, "switch")
        mock_table_class.return_value = mock_table

        result = flow_dump.is_dpu_type()

        assert result is False

    @patch.object(flow_dump.swsscommon, 'DBConnector')
    @patch.object(flow_dump.swsscommon, 'Table')
    def test_is_dpu_type_not_found(self, mock_table_class, mock_db_connector):
        """Test switch type check when field not found."""
        mock_table = Mock()
        mock_table.hget.return_value = (False, None)
        mock_table_class.return_value = mock_table

        result = flow_dump.is_dpu_type()

        assert result is False

    @patch.object(flow_dump.swsscommon, 'DBConnector')
    def test_is_dpu_type_exception(self, mock_db_connector):
        """Test switch type check when exception occurs."""
        mock_db_connector.side_effect = Exception("DB connection failed")

        result = flow_dump.is_dpu_type()

        assert result is False


class TestEnsureConfigDirectory:
    """Test config directory creation."""

    @patch('os.makedirs')
    def test_create_directory_success(self, mock_makedirs):
        """Test successful directory creation."""
        result = flow_dump.ensure_config_directory("/tmp/test_ha")
        assert result is True
        mock_makedirs.assert_called_once_with("/tmp/test_ha", exist_ok=True)

    @patch('os.makedirs')
    def test_create_directory_failure(self, mock_makedirs):
        """Test directory creation failure."""
        mock_makedirs.side_effect = OSError("Permission denied")
        result = flow_dump.ensure_config_directory("/tmp/test_ha")
        assert result is False


class TestCreateConfigFile:
    """Test config file creation."""

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_create_config_file_success(self, mock_json_dump, mock_file):
        """Test successful config file creation."""
        with patch.object(flow_dump.os, 'makedirs') as mock_makedirs:
            mock_makedirs.return_value = None

            session_name = flow_dump.create_config_file(
                "/tmp/test_flow_dump.json",
                session_name="test_session",
                max_flows=500,
                timeout=120,
                flow_state=True
            )

            assert session_name == "test_session"
            mock_makedirs.assert_called_once()
            mock_file.assert_called_once_with("/tmp/test_flow_dump.json", 'w')
            mock_json_dump.assert_called_once()

    def test_create_config_file_directory_failure(self):
        """Test config file creation when directory creation fails."""
        with patch.object(flow_dump.os, 'makedirs') as mock_makedirs:
            mock_makedirs.side_effect = OSError("Permission denied")

            session_name = flow_dump.create_config_file("/tmp/test_flow_dump.json")
            assert session_name is None

    @patch('builtins.open', new_callable=mock_open)
    def test_create_config_file_write_error(self, mock_file):
        """Test config file creation when write fails."""
        with patch.object(flow_dump.os, 'makedirs') as mock_makedirs:
            mock_makedirs.return_value = None
            mock_file.side_effect = IOError("Write failed")

            session_name = flow_dump.create_config_file("/tmp/test_flow_dump.json")
            assert session_name is None


class TestExtractFlowsFromFile:
    """Test flow extraction from gzipped JSONL file."""

    def test_extract_flows_empty_file(self):
        """Test extraction from empty file."""
        with tempfile.NamedTemporaryFile(suffix='.jsonl.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with gzip.open(tmp_path, 'wt') as f:
                f.write("")

        try:
            flows = flow_dump.extract_flows_from_file(tmp_path)
            assert flows == []
        finally:
            os.unlink(tmp_path)

    def test_extract_flows_single_flow(self):
        """Test extraction of single flow."""
        flow_data = {"flow_id": "1", "eni": "eni1", "action": "forward"}

        with tempfile.NamedTemporaryFile(suffix='.jsonl.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with gzip.open(tmp_path, 'wt') as f:
                f.write(json.dumps(flow_data) + "\n")

        try:
            flows = flow_dump.extract_flows_from_file(tmp_path)
            assert len(flows) == 1
            assert flows[0] == flow_data
        finally:
            os.unlink(tmp_path)

    def test_extract_flows_multiple_flows(self):
        """Test extraction of multiple flows."""
        flow1 = {"flow_id": "1", "eni": "eni1"}
        flow2 = {"flow_id": "2", "eni": "eni2"}
        flow3 = {"flow_id": "3", "eni": "eni3"}

        with tempfile.NamedTemporaryFile(suffix='.jsonl.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with gzip.open(tmp_path, 'wt') as f:
                f.write(json.dumps(flow1) + "\n")
                f.write(json.dumps(flow2) + "\n")
                f.write(json.dumps(flow3) + "\n")

        try:
            flows = flow_dump.extract_flows_from_file(tmp_path)
            assert len(flows) == 3
            assert flows[0] == flow1
            assert flows[1] == flow2
            assert flows[2] == flow3
        finally:
            os.unlink(tmp_path)

    def test_extract_flows_invalid_json_skipped(self):
        """Test that invalid JSON lines are skipped."""
        flow1 = {"flow_id": "1", "eni": "eni1"}
        invalid_line = "not a json object"
        flow2 = {"flow_id": "2", "eni": "eni2"}

        with tempfile.NamedTemporaryFile(suffix='.jsonl.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with gzip.open(tmp_path, 'wt') as f:
                f.write(json.dumps(flow1) + "\n")
                f.write(invalid_line + "\n")
                f.write(json.dumps(flow2) + "\n")

        try:
            flows = flow_dump.extract_flows_from_file(tmp_path)
            assert len(flows) == 2
            assert flows[0] == flow1
            assert flows[1] == flow2
        finally:
            os.unlink(tmp_path)

    def test_extract_flows_nonexistent_file(self):
        """Test extraction from nonexistent file."""
        flows = flow_dump.extract_flows_from_file("/nonexistent/file.jsonl.gz")
        assert flows == []

    def test_extract_flows_empty_path(self):
        """Test extraction with empty path."""
        flows = flow_dump.extract_flows_from_file("")
        assert flows == []


class TestCheckSessionState:
    """Test session state checking."""

    def test_check_session_state_exists(self):
        """Test checking state when session exists."""
        mock_table = Mock()
        mock_table.get.return_value = (True, [
            ("state", "completed"),
            ("output_file", "/var/dump/flows/flow_dump_0x001800800000002a.jsonl.gz"),
            ("creation_time_in_ms", "0")
        ])

        state, output_file = flow_dump.check_session_state(mock_table, "test_session")

        assert state == "completed"
        assert output_file == "/var/dump/flows/flow_dump_0x001800800000002a.jsonl.gz"

    def test_check_session_state_not_exists(self):
        """Test checking state when session doesn't exist."""
        mock_table = Mock()
        mock_table.get.return_value = (False, [])

        state, output_file = flow_dump.check_session_state(mock_table, "test_session")

        assert state is None
        assert output_file is None

    def test_check_session_state_failed(self):
        """Test checking state for failed session."""
        mock_table = Mock()
        mock_table.get.return_value = (True, [
            ("state", "failed"),
            ("creation_time_in_ms", "0")
        ])

        state, output_file = flow_dump.check_session_state(mock_table, "test_session")

        assert state == "failed"
        assert output_file is None


class TestProcessNotification:
    """Test notification processing."""

    def test_process_notification_matching_session(self):
        """Test processing notification for matching session."""
        mock_table = Mock()
        mock_table.get.return_value = (True, [
            ("state", "completed"),
            ("output_file", "/var/dump/flows/flow_dump.jsonl.gz")
        ])

        fvs = [("state", "in_progress"), ("type", "flow_dump")]
        state, output_file = flow_dump.process_notification(
            "test_session", "SET", fvs, "test_session", mock_table
        )

        assert state == "completed"
        assert output_file == "/var/dump/flows/flow_dump.jsonl.gz"

    def test_process_notification_non_matching_session(self):
        """Test processing notification for different session."""
        mock_table = Mock()

        fvs = [("state", "completed")]
        state, output_file = flow_dump.process_notification(
            "other_session", "SET", fvs, "test_session", mock_table
        )

        assert state is None
        assert output_file is None


class TestTriggerFlowDump:
    """Test flow dump triggering."""

    @patch('subprocess.run')
    def test_trigger_flow_dump_success(self, mock_run):
        """Test successful flow dump trigger."""
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")

        result = flow_dump.trigger_flow_dump("/tmp/test.json")

        assert result is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_trigger_flow_dump_failure(self, mock_run):
        """Test flow dump trigger failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker")

        result = flow_dump.trigger_flow_dump("/tmp/test.json")

        assert result is False


class TestPrintFlows:
    """Test flow printing."""

    @patch('builtins.print')
    @patch('os.path.exists')
    def test_print_flows_file_exists(self, mock_exists, mock_print):
        """Test printing flows when file exists."""
        mock_exists.return_value = True

        flow1 = {"flow_id": "1", "eni": "eni1"}
        flow2 = {"flow_id": "2", "eni": "eni2"}

        with tempfile.NamedTemporaryFile(suffix='.jsonl.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with gzip.open(tmp_path, 'wt') as f:
                f.write(json.dumps(flow1) + "\n")
                f.write(json.dumps(flow2) + "\n")

        try:
            flow_dump.print_flows(tmp_path, file_only=False)

            # Check that file path was printed
            assert mock_print.call_count >= 1
            # Check that flows were printed
            printed_calls = [str(call) for call in mock_print.call_args_list]
            assert any("flow_id" in str(call) for call in mock_print.call_args_list)
        finally:
            os.unlink(tmp_path)

    @patch('builtins.print')
    @patch('os.path.exists')
    def test_print_flows_file_not_exists(self, mock_exists, mock_print):
        """Test printing flows when file doesn't exist."""
        mock_exists.return_value = False

        flow_dump.print_flows("/nonexistent/file.jsonl.gz", file_only=False)

        # When file doesn't exist and file_only=False, nothing is printed
        # (only verbose messages which require verbose=True)
        mock_print.assert_not_called()

    @patch('builtins.print')
    def test_print_flows_empty_path(self, mock_print):
        """Test printing flows with empty path."""
        flow_dump.print_flows("", file_only=False)

        # Should not print anything
        mock_print.assert_not_called()


class TestIntegration:
    """Integration tests with sample file."""

    def test_extract_flows_from_sample_file(self):
        """Test extraction from a sample flow dump file."""
        # Create sample flow dump data similar to real file
        sample_flows = [
            {
                "sai_flow_entry": {
                    "eni_id": "eni-001",
                    "vni": 100,
                    "src_ip": "10.1.0.10",
                    "dst_ip": "10.1.0.20"
                },
                "action": "forward",
                "priority": 100
            },
            {
                "sai_flow_entry": {
                    "eni_id": "eni-002",
                    "vni": 200,
                    "src_ip": "10.2.0.10",
                    "dst_ip": "10.2.0.20"
                },
                "action": "drop",
                "priority": 200
            }
        ]

        with tempfile.NamedTemporaryFile(suffix='.jsonl.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with gzip.open(tmp_path, 'wt') as f:
                for flow in sample_flows:
                    f.write(json.dumps(flow) + "\n")

        try:
            flows = flow_dump.extract_flows_from_file(tmp_path)

            assert len(flows) == 2
            assert flows[0] == sample_flows[0]
            assert flows[1] == sample_flows[1]

            # Verify structure
            assert "sai_flow_entry" in flows[0]
            assert flows[0]["sai_flow_entry"]["eni_id"] == "eni-001"
            assert flows[1]["sai_flow_entry"]["eni_id"] == "eni-002"
        finally:
            os.unlink(tmp_path)
