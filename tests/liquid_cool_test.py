import os
import sys

from click.testing import CliRunner
from unittest.mock import MagicMock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

from config.liquid_cool import liquid_cool  # noqa: E402


def _make_mock_db(cfgdb=None):
    """Return a MagicMock with spec=Db and a controlled cfgdb attribute."""
    from utilities_common.db import Db
    db = MagicMock(spec=Db)
    db.cfgdb = cfgdb if cfgdb is not None else MagicMock()
    return db


class TestLeakControl(object):
    """Tests for 'config liquid_cool leak-control' command"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def _invoke(self, args, cfgdb=None):
        runner = CliRunner()
        db = _make_mock_db(cfgdb)
        return runner.invoke(liquid_cool, args, obj=db)

    def test_leak_control_system_enabled(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-control', 'system', 'enabled'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        assert "system" in result.output
        assert "enabled" in result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'system_leak_policy': 'enabled'}
        )

    def test_leak_control_system_disabled(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-control', 'system', 'disabled'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        assert "disabled" in result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'system_leak_policy': 'disabled'}
        )

    def test_leak_control_rack_mgr_enabled(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-control', 'rack_mgr', 'enabled'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'rack_mgr_leak_policy': 'enabled'}
        )

    def test_leak_control_rack_mgr_disabled(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-control', 'rack_mgr', 'disabled'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'rack_mgr_leak_policy': 'disabled'}
        )

    def test_leak_control_invalid_policy_type(self):
        result = self._invoke(['leak-control', 'invalid_type', 'enabled'])
        assert result.exit_code != 0

    def test_leak_control_invalid_state(self):
        result = self._invoke(['leak-control', 'system', 'invalid_state'])
        assert result.exit_code != 0

    def test_leak_control_missing_args(self):
        result = self._invoke(['leak-control'])
        assert result.exit_code != 0


class TestLeakAction(object):
    """Tests for 'config liquid_cool leak-action' command"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def _invoke(self, args, cfgdb=None):
        runner = CliRunner()
        db = _make_mock_db(cfgdb)
        return runner.invoke(liquid_cool, args, obj=db)

    def test_leak_action_system_critical_power_off(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-action', 'system', 'critical', 'power_off'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'system_critical_leak_action': 'power_off'}
        )

    def test_leak_action_system_critical_graceful_shutdown(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-action', 'system', 'critical', 'graceful_shutdown'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'system_critical_leak_action': 'graceful_shutdown'}
        )

    def test_leak_action_system_critical_syslog_only(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-action', 'system', 'critical', 'syslog_only'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'system_critical_leak_action': 'syslog_only'}
        )

    def test_leak_action_system_minor_syslog_only(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-action', 'system', 'minor', 'syslog_only'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'system_minor_leak_action': 'syslog_only'}
        )

    def test_leak_action_rack_mgr_critical_syslog_only(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-action', 'rack_mgr', 'critical', 'syslog_only'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'rack_mgr_critical_alert_action': 'syslog_only'}
        )

    def test_leak_action_rack_mgr_minor_syslog_only(self):
        mock_cfgdb = MagicMock()
        result = self._invoke(['leak-action', 'rack_mgr', 'minor', 'syslog_only'], mock_cfgdb)
        assert result.exit_code == 0, result.output
        mock_cfgdb.mod_entry.assert_called_once_with(
            'LEAK_CONTROL_POLICY', 'policy', {'rack_mgr_minor_alert_action': 'syslog_only'}
        )

    def test_leak_action_invalid_action(self):
        result = self._invoke(['leak-action', 'system', 'critical', 'invalid'])
        assert result.exit_code != 0

    def test_leak_action_invalid_severity(self):
        result = self._invoke(['leak-action', 'system', 'invalid', 'power_off'])
        assert result.exit_code != 0

    def test_leak_action_missing_args(self):
        result = self._invoke(['leak-action', 'system', 'critical'])
        assert result.exit_code != 0
