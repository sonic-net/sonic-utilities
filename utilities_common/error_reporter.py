"""
SONiC error report management library for crash-resilient JSON error reporting.
Provides structured error reporting for SONiC operations including reboots,
upgrades, and other system operations.
"""
import sys
import json
import os
import re
import uuid

# Try to import sonic_py_common logger, fall back to standard logging if not
# available
try:
    from sonic_py_common import logger
    SONIC_LOGGER_AVAILABLE = True
except ImportError:
    SONIC_LOGGER_AVAILABLE = False

# Always import logging for fallback functionality
import logging
if not SONIC_LOGGER_AVAILABLE:
    # Set up basic logging as fallback
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Global logger instance
sonic_logger = None


def get_logger():
    """Get or create the logger instance (SONiC or fallback)."""
    global sonic_logger
    if sonic_logger is None:
        if SONIC_LOGGER_AVAILABLE:
            sonic_logger = logger.Logger("sonic-error-report")
        else:
            # Create a wrapper for standard logging that mimics SONiC logger
            # interface
            class FallbackLogger:
                def __init__(self):
                    self.logger = logging.getLogger("sonic-error-report")

                def log_info(self, msg):
                    self.logger.info(msg)

                def log_warning(self, msg, also_print_to_console=False):
                    self.logger.warning(msg)
                    if also_print_to_console:
                        sys.stderr.write("WARNING: {}\n".format(msg))

                def log_error(self, msg, also_print_to_console=False):
                    self.logger.error(msg)
                    if also_print_to_console:
                        sys.stderr.write("ERROR: {}\n".format(msg))

            sonic_logger = FallbackLogger()
    return sonic_logger


class SonicErrorReportManager:
    def __init__(self, report_dir="/host/sonic-upgrade-reports",
                 scenario=None):
        self.report_dir = report_dir
        self.scenario = scenario
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

    def get_report_path(self, guid):
        """Get path for report file using <scenario>.<eventGuid>.json."""
        # Sanitize guid to prevent directory traversal attacks
        # Only allow alphanumeric, dash, underscore, and dot
        safe_guid = re.sub(r'[^a-zA-Z0-9._-]', '_', guid)

        # Also remove any path separators that might have survived
        safe_guid = safe_guid.replace('/', '_').replace('\\', '_')

        # Ensure the guid doesn't start with dots (hidden files or .., .)
        while safe_guid.startswith('.'):
            safe_guid = safe_guid[1:]

        # If guid becomes empty after sanitization, use a default
        if not safe_guid:
            safe_guid = 'invalid_guid'

        # Sanitize scenario name
        safe_scenario = re.sub(r'[^a-zA-Z0-9._-]', '_', self.scenario)
        filename = "{}.{}.json".format(safe_scenario, safe_guid)

        return os.path.join(self.report_dir, filename)

    def _apply_kwargs_to_report(self, report, **kwargs):
        """Apply kwargs to customize report fields with defaults."""
        # sonic_upgrade_summary customization
        if 'package_version' in kwargs:
            report["sonic_upgrade_summary"][
                "sonic_upgrade_package_version"] = kwargs['package_version']

        # sonic_upgrade_actions customization
        actions = report["sonic_upgrade_actions"]
        if 'reputation_impact' in kwargs:
            actions["reputation_impact"] = kwargs['reputation_impact']
        if 'retriable' in kwargs:
            actions["retriable"] = kwargs['retriable']
        if 'isolate_on_failure' in kwargs:
            actions["isolate_on_failure"] = kwargs['isolate_on_failure']

        # auto_triage customization
        auto_triage = actions["auto_triage"]
        if 'triage_status' in kwargs:
            auto_triage["status"] = kwargs['triage_status']
        if 'triage_queue' in kwargs:
            auto_triage["triage_queue"] = kwargs['triage_queue']
        if 'triage_action' in kwargs:
            auto_triage["triage_action"] = kwargs['triage_action']

        # sonic_upgrade_report customization
        upgrade_report = report["sonic_upgrade_report"]
        if 'duration' in kwargs:
            upgrade_report["duration"] = str(kwargs['duration'])
        if 'stages' in kwargs:
            upgrade_report["stages"] = kwargs['stages']
        if 'health_checks' in kwargs:
            upgrade_report["health_checks"] = kwargs['health_checks']

    def init_report(self, operation_type, guid=None, **kwargs):
        """Initialize a staged report for crash resilience.

        Args:
            operation_type: Type of operation (e.g., fast-reboot, upgrade)
            guid: Optional GUID. If not provided, one will be auto-generated.
            **kwargs: Additional report customizations

        Returns:
            str: The GUID used for this report (provided or generated)
        """
        # Generate GUID if not provided, otherwise use the provided one
        if guid is None:
            guid = str(uuid.uuid4())
        else:
            guid = str(guid)  # Convert to string in case UUID object is passed
        report = {
            "sonic_upgrade_summary": {
                "script_name": "{}".format(operation_type),
                "sonic_upgrade_package_version": "1.0.0",  # TODO: Impl ver
                "fault_code": "124",
                "fault_reason": (
                    "Operation timeout - system became unresponsive"),
                "guid": guid
            },
            "sonic_upgrade_actions": {
                "reputation_impact": False,
                "retriable": True,
                "isolate_on_failure": False,
                "auto_triage": {
                    "status": False,
                    "triage_queue": "",
                    "triage_action": ""
                }
            },
            "sonic_upgrade_report": {
                "duration": "0",
                "stages": [],
                "health_checks": [],
                "errors": [{
                    "name": "TIMEOUT",
                    "message": "Operation timed out or system crashed"
                }]
            }
        }

        # Apply any customizations from kwargs
        self._apply_kwargs_to_report(report, **kwargs)

        report_path = self.get_report_path(guid)
        temp_path = report_path + '.tmp'

        # Write to temporary file first for atomicity
        with open(temp_path, 'w') as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename (on POSIX systems)
        os.rename(temp_path, report_path)

        get_logger().log_info(
            "Initialized staged report: {}".format(report_path))

        # Return the GUID for programmatic use
        return guid

    def mark_failure(self, guid, exit_code, fault_reason=None, **kwargs):
        """Mark report as failed with exit code and optional reason."""
        report_path = self.get_report_path(guid)

        if not os.path.exists(report_path):
            get_logger().log_error(
                "Report {} does not exist".format(report_path))
            sys.exit(1)

        # Load existing report
        with open(report_path, 'r') as f:
            report = json.load(f)

        # Update summary with failure details
        report["sonic_upgrade_summary"]["fault_code"] = str(exit_code)
        if fault_reason:
            report["sonic_upgrade_summary"]["fault_reason"] = fault_reason
        else:
            report["sonic_upgrade_summary"]["fault_reason"] = (
                "Operation failed with exit code {}".format(exit_code))

        # Clear timeout error and add actual error
        error_message = (fault_reason if fault_reason else
                         "Operation failed with exit code {}".format(
                             exit_code))
        report["sonic_upgrade_report"]["errors"] = [{
            "name": "EXIT_CODE_{}".format(exit_code),
            "message": error_message
        }]

        # Apply any customizations from kwargs
        self._apply_kwargs_to_report(report, **kwargs)

        # Write back atomically
        temp_path = report_path + '.tmp'

        with open(temp_path, 'w') as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename (on POSIX systems)
        os.rename(temp_path, report_path)

        get_logger().log_info(
            "Marked report as failed: {}".format(report_path))

    def mark_success(self, guid, **kwargs):
        """Mark report as successful with success details."""
        report_path = self.get_report_path(guid)

        if not os.path.exists(report_path):
            get_logger().log_warning("Report {} not found".format(report_path))
            return

        # Load existing report
        with open(report_path, 'r') as f:
            report = json.load(f)

        # Update summary with success details
        report["sonic_upgrade_summary"]["fault_code"] = "0"
        report["sonic_upgrade_summary"]["fault_reason"] = (
            "Operation completed successfully")

        # Update actions for successful operation
        report["sonic_upgrade_actions"]["reputation_impact"] = False
        report["sonic_upgrade_actions"]["retriable"] = False
        report["sonic_upgrade_actions"]["isolate_on_failure"] = False

        # Clear errors for successful operation
        report["sonic_upgrade_report"]["errors"] = []

        # Apply any customizations from kwargs
        self._apply_kwargs_to_report(report, **kwargs)

        # Write back atomically
        temp_path = report_path + '.tmp'

        with open(temp_path, 'w') as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename (on POSIX systems)
        os.rename(temp_path, report_path)

        get_logger().log_info(
            "Marked report as successful: {}".format(report_path))
