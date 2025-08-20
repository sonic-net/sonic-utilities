import json
import os
import sys
import tempfile
import unittest
import uuid
from io import StringIO
from unittest.mock import patch, MagicMock, mock_open, call

import pytest

# Import the module under test
from utilities_common.error_reporter import SonicErrorReportManager


class TestSonicErrorReportManager:
    """Test cases for SonicErrorReportManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_scenario = "test_scenario"
        self.test_guid = "test-guid-123"
        
    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_init_creates_directory_if_not_exists(self):
        """Test that __init__ creates report directory if it doesn't exist."""
        new_dir = os.path.join(self.test_dir, 'new_reports')
        assert not os.path.exists(new_dir)
        
        manager = SonicErrorReportManager(new_dir, self.test_scenario)
        
        assert os.path.exists(new_dir)
        assert manager.report_dir == new_dir
        assert manager.scenario == self.test_scenario
    
    def test_init_skips_directory_creation_if_exists(self):
        """Test that __init__ works with existing directory."""
        assert os.path.exists(self.test_dir)
        
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        assert os.path.exists(self.test_dir)
        assert manager.report_dir == self.test_dir
        assert manager.scenario == self.test_scenario
    
    def test_get_report_path_normal_guid(self):
        """Test get_report_path with normal GUID."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        path = manager.get_report_path(self.test_guid)
        expected = os.path.join(self.test_dir, f"{self.test_scenario}.{self.test_guid}.json")
        
        assert path == expected
    
    def test_get_report_path_sanitizes_malicious_guid(self):
        """Test that get_report_path sanitizes malicious GUID input."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        # Test directory traversal attempts
        malicious_guid = "../../../etc/passwd"
        path = manager.get_report_path(malicious_guid)
        
        # Should not contain path separators or escape the test directory
        assert self.test_dir in path
        assert "/etc/passwd" not in path
        assert path.endswith(".json")
    
    def test_get_report_path_sanitizes_special_characters(self):
        """Test GUID sanitization handles special characters."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        special_guid = "test<script>alert('xss')</script>guid"
        path = manager.get_report_path(special_guid)
        
        # Should replace special characters with underscores
        assert "<script>" not in path
        assert "test_script_alert__xss____script_guid" in path
    
    def test_get_report_path_handles_empty_guid(self):
        """Test handling of empty GUID after sanitization."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        empty_guid = "../../../"
        path = manager.get_report_path(empty_guid)
        
        # Should use 'invalid_guid' default
        assert "invalid_guid" in path
    
    def test_init_report_creates_staged_report(self):
        """Test init_report creates a staged report with defaults."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        result_guid = manager.init_report("test-operation", self.test_guid)
        
        # Check report file exists
        report_path = manager.get_report_path(self.test_guid)
        assert os.path.exists(report_path)
        
        # Verify report contents
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["sonic_upgrade_summary"]["script_name"] == "test-operation"
        assert report["sonic_upgrade_summary"]["fault_code"] == "124"
        assert report["sonic_upgrade_summary"]["fault_reason"] == "Operation timeout - system became unresponsive"
        assert report["sonic_upgrade_summary"]["guid"] == self.test_guid
        assert report["sonic_upgrade_actions"]["reputation_impact"] is True
        assert report["sonic_upgrade_report"]["errors"][0]["name"] == "TIMEOUT"
        assert result_guid == self.test_guid
    
    def test_init_report_auto_generates_guid(self):
        """Test init_report auto-generates GUID when not provided."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        result_guid = manager.init_report("test-operation")
        
        # GUID should be a valid UUID
        assert result_guid is not None
        # Validate it's a UUID format
        uuid.UUID(result_guid)
        
        # Report should exist with the auto-generated GUID
        report_path = manager.get_report_path(result_guid)
        assert os.path.exists(report_path)
    
    def test_init_report_with_custom_kwargs(self):
        """Test init_report accepts custom kwargs."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        manager.init_report(
            "test-operation",
            self.test_guid,
            package_version="2.0.5",
            reputation_impact=False,
            retriable=False,
            isolate_on_failure=False,
            triage_status=True,
            triage_queue="high-priority",
            triage_action="auto-retry",
            duration="300"
        )
        
        report_path = manager.get_report_path(self.test_guid)
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["sonic_upgrade_summary"]["sonic_upgrade_package_version"] == "2.0.5"
        assert report["sonic_upgrade_actions"]["reputation_impact"] is False
        assert report["sonic_upgrade_actions"]["retriable"] is False
        assert report["sonic_upgrade_actions"]["isolate_on_failure"] is False
        assert report["sonic_upgrade_actions"]["auto_triage"]["status"] is True
        assert report["sonic_upgrade_actions"]["auto_triage"]["triage_queue"] == "high-priority"
        assert report["sonic_upgrade_actions"]["auto_triage"]["triage_action"] == "auto-retry"
        assert report["sonic_upgrade_report"]["duration"] == "300"
    
    def test_mark_failure_updates_existing_report(self):
        """Test mark_failure updates an existing report with failure details."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        # Create initial report
        manager.init_report("test-operation", self.test_guid)
        
        # Mark as failure
        manager.mark_failure(self.test_guid, 42, "Custom failure reason")
        
        # Verify updated report
        report_path = manager.get_report_path(self.test_guid)
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["sonic_upgrade_summary"]["fault_code"] == "42"
        assert report["sonic_upgrade_summary"]["fault_reason"] == "Custom failure reason"
        assert report["sonic_upgrade_report"]["errors"][0]["name"] == "EXIT_CODE_42"
        assert report["sonic_upgrade_report"]["errors"][0]["message"] == "Custom failure reason"
    
    def test_mark_failure_with_default_reason(self):
        """Test mark_failure generates default reason when not provided."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        manager.init_report("test-operation", self.test_guid)
        manager.mark_failure(self.test_guid, 99)
        
        report_path = manager.get_report_path(self.test_guid)
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["sonic_upgrade_summary"]["fault_code"] == "99"
        assert report["sonic_upgrade_summary"]["fault_reason"] == "Operation failed with exit code 99"
        assert report["sonic_upgrade_report"]["errors"][0]["message"] == "Operation failed with exit code 99"
    
    @patch('sys.stderr', new_callable=StringIO)
    @patch('sys.exit')
    def test_mark_failure_missing_report(self, mock_exit, mock_stderr):
        """Test mark_failure exits when report doesn't exist."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        manager.mark_failure("nonexistent-guid", 1)
        
        mock_exit.assert_called_once_with(1)
        assert "Error: Report" in mock_stderr.getvalue()
        assert "does not exist" in mock_stderr.getvalue()
    
    def test_mark_success_updates_existing_report(self):
        """Test mark_success updates an existing report with success details."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        # Create initial report (starts with timeout defaults)
        manager.init_report("test-operation", self.test_guid)
        
        # Mark as success
        manager.mark_success(self.test_guid, duration="120")
        
        # Verify updated report
        report_path = manager.get_report_path(self.test_guid)
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["sonic_upgrade_summary"]["fault_code"] == "0"
        assert report["sonic_upgrade_summary"]["fault_reason"] == "Operation completed successfully"
        assert report["sonic_upgrade_actions"]["reputation_impact"] is False
        assert report["sonic_upgrade_actions"]["retriable"] is False
        assert report["sonic_upgrade_actions"]["isolate_on_failure"] is False
        assert report["sonic_upgrade_report"]["errors"] == []
        assert report["sonic_upgrade_report"]["duration"] == "120"
    
    @patch('sys.stderr', new_callable=StringIO)
    def test_mark_success_missing_report(self, mock_stderr):
        """Test mark_success warns but doesn't fail when report doesn't exist."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        # Should not throw exception
        manager.mark_success("nonexistent-guid")
        
        assert "Warning: Report" in mock_stderr.getvalue()
        assert "not found" in mock_stderr.getvalue()
    
    def test_atomic_write_operations(self):
        """Test that write operations are atomic (use temp file + rename)."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        with patch('os.rename') as mock_rename:
            manager.init_report("test-operation", self.test_guid)
            
            # Check that rename was called for atomic write
            expected_path = manager.get_report_path(self.test_guid)
            expected_temp = expected_path + '.tmp'
            mock_rename.assert_called_once_with(expected_temp, expected_path)
    
    def test_apply_kwargs_to_report(self):
        """Test _apply_kwargs_to_report method correctly applies customizations."""
        manager = SonicErrorReportManager(self.test_dir, self.test_scenario)
        
        report = {
            "sonic_upgrade_summary": {"sonic_upgrade_package_version": "1.0.0"},
            "sonic_upgrade_actions": {
                "reputation_impact": True,
                "retriable": True,
                "isolate_on_failure": True,
                "auto_triage": {
                    "status": False,
                    "triage_queue": "",
                    "triage_action": ""
                }
            },
            "sonic_upgrade_report": {
                "duration": "0",
                "stages": [],
                "health_checks": []
            }
        }
        
        manager._apply_kwargs_to_report(
            report,
            package_version="3.0.0",
            reputation_impact=False,
            retriable=False,
            isolate_on_failure=False,
            triage_status=True,
            triage_queue="test-queue",
            triage_action="test-action",
            duration="500",
            stages=["stage1", "stage2"],
            health_checks=["check1", "check2"]
        )
        
        assert report["sonic_upgrade_summary"]["sonic_upgrade_package_version"] == "3.0.0"
        assert report["sonic_upgrade_actions"]["reputation_impact"] is False
        assert report["sonic_upgrade_actions"]["retriable"] is False
        assert report["sonic_upgrade_actions"]["isolate_on_failure"] is False
        assert report["sonic_upgrade_actions"]["auto_triage"]["status"] is True
        assert report["sonic_upgrade_actions"]["auto_triage"]["triage_queue"] == "test-queue"
        assert report["sonic_upgrade_actions"]["auto_triage"]["triage_action"] == "test-action"
        assert report["sonic_upgrade_report"]["duration"] == "500"
        assert report["sonic_upgrade_report"]["stages"] == ["stage1", "stage2"]
        assert report["sonic_upgrade_report"]["health_checks"] == ["check1", "check2"]
    
    def test_scenario_sanitization(self):
        """Test that scenario names are also sanitized for security."""
        malicious_scenario = "../../../etc/malicious"
        manager = SonicErrorReportManager(self.test_dir, malicious_scenario)
        
        path = manager.get_report_path(self.test_guid)
        
        # Should not contain path separators
        assert "/etc/" not in path
        assert ".." not in path
        # Should contain sanitized version
        assert "___etc_malicious" in path