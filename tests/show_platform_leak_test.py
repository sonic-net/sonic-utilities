import os
import sys

from click.testing import CliRunner
from unittest.mock import MagicMock, patch

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

import show.platform as show_platform  # noqa: E402


def _make_state_db(table_data):
    """Build a mock SonicV2Connector with STATE_DB data keyed by full Redis keys."""
    state_db = MagicMock()
    state_db.STATE_DB = 'STATE_DB'

    def _keys(db_id, pattern):
        prefix = pattern.rstrip('*')
        return [k for k in table_data if k.startswith(prefix)]

    def _get_all(db_id, key):
        return table_data.get(key)

    state_db.keys.side_effect = _keys
    state_db.get_all.side_effect = _get_all
    return state_db


class TestShowPlatformLeakControlPolicy(object):
    """Tests for 'show platform leak control-policy'"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_leak_control_policy_with_data(self):
        runner = CliRunner()
        mock_cfgdb = MagicMock()
        mock_cfgdb.get_entry.return_value = {
            'system_leak_policy': 'enabled',
            'system_critical_leak_action': 'power_off',
            'system_minor_leak_action': 'syslog_only',
            'rack_mgr_leak_policy': 'disabled',
            'rack_mgr_critical_alert_action': 'syslog_only',
            'rack_mgr_minor_alert_action': 'syslog_only',
        }
        mock_db = MagicMock()
        mock_db.cfgdb = mock_cfgdb

        with patch('utilities_common.db.Db', return_value=mock_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['control-policy']
            )
        assert result.exit_code == 0
        assert 'system_leak_policy' in result.output
        assert 'enabled' in result.output
        assert 'rack_mgr_leak_policy' in result.output
        assert 'disabled' in result.output
        assert 'power_off' in result.output

    def test_leak_control_policy_empty_db(self):
        runner = CliRunner()
        mock_cfgdb = MagicMock()
        mock_cfgdb.get_entry.return_value = {}
        mock_db = MagicMock()
        mock_db.cfgdb = mock_cfgdb

        with patch('utilities_common.db.Db', return_value=mock_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['control-policy']
            )
        assert result.exit_code == 0
        # Defaults should be shown
        assert 'enabled' in result.output
        assert 'power_off' in result.output
        assert 'syslog_only' in result.output


class TestShowPlatformLeakRackManagerAlerts(object):
    """Tests for 'show platform leak rack-manager alerts'"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_rack_manager_alerts_with_data(self):
        runner = CliRunner()
        table_data = {
            'RACK_MANAGER_ALERT|Inlet_liquid_temperature': {
                'severity': 'NORMAL',
                'timestamp': '2026-03-25 22:10:00',
            },
            'RACK_MANAGER_ALERT|Rack_level_leak': {
                'severity': 'CRITICAL',
                'timestamp': '2026-03-25 22:11:00',
            },
        }
        mock_state_db = _make_state_db(table_data)

        with patch('show.platform._get_state_db', return_value=mock_state_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['rack-manager'].commands['alerts']
            )
        assert result.exit_code == 0
        assert 'Inlet_liquid_temperature' in result.output
        assert 'NORMAL' in result.output
        assert 'Rack_level_leak' in result.output
        assert 'CRITICAL' in result.output

    def test_rack_manager_alerts_empty(self):
        runner = CliRunner()
        mock_state_db = _make_state_db({})

        with patch('show.platform._get_state_db', return_value=mock_state_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['rack-manager'].commands['alerts']
            )
        assert result.exit_code == 0
        assert 'No rack-manager alerts found' in result.output


class TestShowPlatformLeakProfiles(object):
    """Tests for 'show platform leak profiles'"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_leak_profiles_with_data(self):
        runner = CliRunner()
        mock_cfgdb = MagicMock()
        mock_cfgdb.get_keys.return_value = ['rope', 'spot', 'flex_pcb']
        mock_cfgdb.get_entry.side_effect = lambda t, k: {
            'rope':     {'max_minor_duration_sec': '300'},
            'spot':     {'max_minor_duration_sec': '600'},
            'flex_pcb': {'max_minor_duration_sec': '180'},
        }[k]
        mock_db = MagicMock()
        mock_db.cfgdb = mock_cfgdb

        with patch('utilities_common.db.Db', return_value=mock_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['profiles']
            )
        assert result.exit_code == 0
        assert 'rope' in result.output
        assert '300' in result.output
        assert 'spot' in result.output
        assert 'flex_pcb' in result.output
        assert '180' in result.output

    def test_leak_profiles_empty(self):
        runner = CliRunner()
        mock_cfgdb = MagicMock()
        mock_cfgdb.get_keys.return_value = []
        mock_db = MagicMock()
        mock_db.cfgdb = mock_cfgdb

        with patch('utilities_common.db.Db', return_value=mock_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['profiles']
            )
        assert result.exit_code == 0
        assert 'No leak profiles found' in result.output


class TestShowPlatformLeakStatus(object):
    """Tests for 'show platform leak status'"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_leak_status_with_data(self):
        runner = CliRunner()
        table_data = {
            'LIQUID_COOLING_INFO|leakage_sensors1': {
                'name': 'leak_sensors1',
                'leaking': 'YES',
                'leak_sensor_status': 'OK',
                'type': 'rope',
                'leak_severity': 'MINOR',
            },
            'LIQUID_COOLING_INFO|leakage_sensors2': {
                'name': 'leak_sensors2',
                'leaking': 'NO',
                'leak_sensor_status': 'FAULTY',
                'type': 'spot',
                'leak_severity': 'N/A',
            },
        }
        mock_state_db = _make_state_db(table_data)

        with patch('show.platform._get_state_db', return_value=mock_state_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['status']
            )
        assert result.exit_code == 0
        assert 'leak_sensors1' in result.output
        assert 'YES' in result.output
        assert 'MINOR' in result.output
        assert 'leak_sensors2' in result.output
        # leaking=NO → severity shown as NA
        assert 'NA' in result.output

    def test_leak_status_critical_sensor(self):
        runner = CliRunner()
        table_data = {
            'LIQUID_COOLING_INFO|leakage_sensorsX': {
                'name': 'leak_sensorsX',
                'leaking': 'Yes',
                'leak_sensor_status': 'OK',
                'type': 'flex_pcb',
                'leak_severity': 'CRITICAL',
            },
        }
        mock_state_db = _make_state_db(table_data)

        with patch('show.platform._get_state_db', return_value=mock_state_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['status']
            )
        assert result.exit_code == 0
        assert 'CRITICAL' in result.output
        assert 'flex_pcb' in result.output

    def test_leak_status_empty(self):
        runner = CliRunner()
        mock_state_db = _make_state_db({})

        with patch('show.platform._get_state_db', return_value=mock_state_db):
            result = runner.invoke(
                show_platform.platform.commands['leak'].commands['status']
            )
        assert result.exit_code == 0
        assert 'No leak sensor data found' in result.output
