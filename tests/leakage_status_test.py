import sys
import os
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
import show.platform as platform_show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)


def _make_state_db(table_data):
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


class TestLeakStatus(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_platform_leak_status(self):
        runner = CliRunner()
        table_data = {
            'LIQUID_COOLING_INFO|leakage_sensors1': {
                'name': 'leakage1', 'leaking': 'No',
                'leak_sensor_status': 'OK', 'type': 'rope', 'leak_severity': 'N/A',
            },
            'LIQUID_COOLING_INFO|leakage_sensors2': {
                'name': 'leakage2', 'leaking': 'No',
                'leak_sensor_status': 'OK', 'type': 'spot', 'leak_severity': 'N/A',
            },
            'LIQUID_COOLING_INFO|leakage_sensors3': {
                'name': 'leakage3', 'leaking': 'Yes',
                'leak_sensor_status': 'OK', 'type': 'rope', 'leak_severity': 'MINOR',
            },
        }
        mock_state_db = _make_state_db(table_data)

        with patch('show.platform._get_state_db', return_value=mock_state_db):
            result = runner.invoke(
                platform_show.platform.commands["leak"].commands["status"]
            )
        assert result.exit_code == 0
        assert 'leakage1' in result.output
        assert 'leakage2' in result.output
        assert 'leakage3' in result.output
        assert 'Yes' in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
