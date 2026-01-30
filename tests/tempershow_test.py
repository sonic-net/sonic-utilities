"""
Unit tests for tempershow script

Tests the TemperShow class and its ability to display temperature information
from both thermal sensors and transceiver/SFP modules with TRANSCEIVER_DOM_TEMPERATURE fallback.
"""
import os
import sys
from unittest import TestCase, mock
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, 'scripts')
sys.path.insert(0, modules_path)

# Load the tempershow script as a module
tempershow_path = os.path.join(scripts_path, 'tempershow')
tempershow = load_module_from_source('tempershow', tempershow_path)

# Import the required classes and constants from the loaded module
TemperShow = tempershow.TemperShow
TEMPER_FIELD_NAME = tempershow.TEMPER_FIELD_NAME
HIGH_THRESH_FIELD_NAME = tempershow.HIGH_THRESH_FIELD_NAME
LOW_THRESH_FIELD_NAME = tempershow.LOW_THRESH_FIELD_NAME
CRIT_HIGH_THRESH_FIELD_NAME = tempershow.CRIT_HIGH_THRESH_FIELD_NAME
CRIT_LOW_THRESH_FIELD_NAME = tempershow.CRIT_LOW_THRESH_FIELD_NAME
WARNING_STATUS_FIELD_NAME = tempershow.WARNING_STATUS_FIELD_NAME
TIMESTAMP_FIELD_NAME = tempershow.TIMESTAMP_FIELD_NAME


class TestTemperShowClass(TestCase):
    """Test cases for TemperShow class"""

    def setUp(self):
        self.temp_show = None

    def tearDown(self):
        if self.temp_show:
            self.temp_show.db = None

    @mock.patch('tempershow.SonicV2Connector')
    def test_init(self, mock_connector):
        """Test TemperShow initialization"""
        temp_show = TemperShow()

        mock_connector.assert_called_once_with(host="127.0.0.1")
        # Ensure connect() is called to STATE_DB
        mock_connector.return_value.connect.assert_called_once_with(
            mock_connector.return_value.STATE_DB
        )
        # Ensure db is the connector instance
        assert temp_show.db is mock_connector.return_value

    @mock.patch('tempershow.SonicV2Connector')
    def test_get_transceiver_temperature_data_from_new_table(self, mock_connector):
        """
        Test _get_transceiver_temperature_data with new TRANSCEIVER_DOM_TEMPERATURE table
        Given: TRANSCEIVER_DOM_TEMPERATURE table has temperature data
        When: _get_transceiver_temperature_data is called
        Then: Should return full data dict from new table
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        # Mock get_all to return data for TRANSCEIVER_DOM_TEMPERATURE
        expected_data = {
            TEMPER_FIELD_NAME: '35.5',
            HIGH_THRESH_FIELD_NAME: '70.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '80.0'
        }
        mock_db.get_all.return_value = expected_data

        result = temp_show._get_transceiver_temperature_data('Ethernet0')

        assert result == expected_data
        mock_db.get_all.assert_called_with(
            temp_show.db.STATE_DB,
            'TRANSCEIVER_DOM_TEMPERATURE|Ethernet0'
        )

    @mock.patch('tempershow.SonicV2Connector')
    def test_get_transceiver_temperature_data_fallback_to_legacy(self, mock_connector):
        """
        Test _get_transceiver_temperature_data fallback to TRANSCEIVER_DOM_SENSOR
        Given: TRANSCEIVER_DOM_TEMPERATURE table is empty but TRANSCEIVER_DOM_SENSOR has data
        When: _get_transceiver_temperature_data is called
        Then: Should fallback to TRANSCEIVER_DOM_SENSOR and return full data dict
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        expected_data = {TEMPER_FIELD_NAME: '36.2'}
        mock_db.get_all.side_effect = [
            {},  # Empty response for TRANSCEIVER_DOM_TEMPERATURE
            expected_data  # Data for TRANSCEIVER_DOM_SENSOR
        ]

        result = temp_show._get_transceiver_temperature_data('Ethernet1')

        assert result == expected_data
        assert mock_db.get_all.call_count == 2

        # Verify legacy key was attempted
        calls = [c.args for c in mock_db.get_all.call_args_list]
        assert any('TRANSCEIVER_DOM_SENSOR|Ethernet1' in str(args) for args in calls)

    @mock.patch('tempershow.SonicV2Connector')
    def test_get_transceiver_temperature_data_no_data(self, mock_connector):
        """
        Test _get_transceiver_temperature_data when both tables are empty
        Given: Neither TRANSCEIVER_DOM_TEMPERATURE nor TRANSCEIVER_DOM_SENSOR tables have data
        When: _get_transceiver_temperature_data is called
        Then: Should return None
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        # Both calls return empty
        mock_db.get_all.return_value = {}

        result = temp_show._get_transceiver_temperature_data('Ethernet2')

        assert result is None

    @mock.patch('tempershow.SonicV2Connector')
    def test_get_transceiver_temperature_data_no_temperature_field(self, mock_connector):
        """
        Test _get_transceiver_temperature_data when table exists but has no temperature field
        Given: Tables exist but do not contain temperature field
        When: _get_transceiver_temperature_data is called
        Then: Should return None
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        mock_db.get_all.side_effect = [
            {'other_field': 'value'},  # No temperature in TRANSCEIVER_DOM_TEMPERATURE
            {}  # Empty TRANSCEIVER_DOM_SENSOR
        ]

        result = temp_show._get_transceiver_temperature_data('Ethernet3')

        assert result is None

    @mock.patch('tempershow.SonicV2Connector')
    def test_add_sensor_to_output_with_thresholds(self, mock_connector):
        """
        Test _add_sensor_to_output for thermal sensor with thresholds
        Given: A thermal sensor with temperature and threshold data
        When: _add_sensor_to_output is called with data_dict containing thresholds
        Then: Should add sensor to both JSON and table output
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        json_output = []
        table = []
        data_dict = {
            TEMPER_FIELD_NAME: '35.0',
            HIGH_THRESH_FIELD_NAME: '50.0',
            LOW_THRESH_FIELD_NAME: '10.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '60.0',
            CRIT_LOW_THRESH_FIELD_NAME: '0.0',
            WARNING_STATUS_FIELD_NAME: 'False',
            TIMESTAMP_FIELD_NAME: '20240101 12:00:00'
        }

        temp_show._add_sensor_to_output('Sensor1', data_dict, json_output, table)

        assert len(json_output) == 1
        assert len(table) == 1
        assert json_output[0]['Sensor'] == 'Sensor1'
        assert json_output[0]['Temperature'] == '35.0'
        assert json_output[0]['High_TH'] == '50.0'
        assert table[0][0] == 'Sensor1'
        assert table[0][1] == '35.0'

    @mock.patch('tempershow.SonicV2Connector')
    def test_add_sensor_to_output_without_thresholds(self, mock_connector):
        """
        Test _add_sensor_to_output for transceiver sensor without thresholds
        Given: A transceiver sensor with temperature but no thresholds
        When: _add_sensor_to_output is called with data_dict containing only temperature
        Then: Should add sensor with N/A for threshold fields
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        json_output = []
        table = []
        data_dict = {TEMPER_FIELD_NAME: '36.5'}

        temp_show._add_sensor_to_output('Ethernet0', data_dict, json_output, table)

        assert len(json_output) == 1
        assert len(table) == 1
        assert json_output[0]['Sensor'] == 'Ethernet0'
        assert json_output[0]['Temperature'] == '36.5'
        assert json_output[0]['High_TH'] == 'N/A'
        assert json_output[0]['Low_TH'] == 'N/A'
        assert table[0][2] == 'N/A'  # High_TH
        assert table[0][3] == 'N/A'  # Low_TH

    @mock.patch('tempershow.tabulate')
    @mock.patch('tempershow.SonicV2Connector')
    def test_show_thermal_sensors_only(self, mock_connector, mock_tabulate):
        """
        Test show() with only thermal sensor data
        Given: Only TEMPERATURE_INFO table has data, no transceiver data
        When: show() is called
        Then: Should display only thermal sensors
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        # show() calls keys() for:
        # 1) TEMPERATURE_INFO*
        # 2) TRANSCEIVER_DOM_TEMPERATURE*
        # 3) (if #2 empty) TRANSCEIVER_DOM_SENSOR*
        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],  # Thermal sensors
            [],                            # No TRANSCEIVER_DOM_TEMPERATURE
            []                             # No TRANSCEIVER_DOM_SENSOR
        ]

        thermal_data = {
            TEMPER_FIELD_NAME: '35.0',
            HIGH_THRESH_FIELD_NAME: '50.0',
            LOW_THRESH_FIELD_NAME: '10.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '60.0',
            CRIT_LOW_THRESH_FIELD_NAME: '0.0',
            WARNING_STATUS_FIELD_NAME: 'False',
            TIMESTAMP_FIELD_NAME: '20240101 12:00:00'
        }
        mock_db.get_all.return_value = thermal_data

        with mock.patch('builtins.print'):
            temp_show.show(output_json=False)
            mock_tabulate.assert_called_once()

            args, _kwargs = mock_tabulate.call_args
            table_passed = args[0]
            assert ('Sensor1', '35.0', '50.0', '10.0', '60.0', '0.0', 'False', '20240101 12:00:00') in table_passed

    @mock.patch('tempershow.tabulate')
    @mock.patch('tempershow.SonicV2Connector')
    def test_show_with_transceiver_temperature(self, mock_connector, mock_tabulate):
        """
        Test show() with both thermal and transceiver temperature data
        Given: Both TEMPERATURE_INFO and TRANSCEIVER_DOM_TEMPERATURE have data
        When: show() is called
        Then: Should display both thermal and transceiver sensors
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        # Thermal keys + transceiver keys from new table
        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],
            ['TRANSCEIVER_DOM_TEMPERATURE|Ethernet0']
        ]

        thermal_data = {
            TEMPER_FIELD_NAME: '35.0',
            HIGH_THRESH_FIELD_NAME: '50.0',
            LOW_THRESH_FIELD_NAME: '10.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '60.0',
            CRIT_LOW_THRESH_FIELD_NAME: '0.0',
            WARNING_STATUS_FIELD_NAME: 'False',
            TIMESTAMP_FIELD_NAME: '20240101 12:00:00'
        }

        def get_all_side_effect(db, key):
            if 'TEMPERATURE_INFO' in key:
                return thermal_data
            if 'TRANSCEIVER_DOM_TEMPERATURE' in key:
                return {TEMPER_FIELD_NAME: '37.5'}
            return {}

        mock_db.get_all.side_effect = get_all_side_effect

        with mock.patch('builtins.print'):
            temp_show.show(output_json=False)
            mock_tabulate.assert_called_once()

            args, _kwargs = mock_tabulate.call_args
            table_passed = args[0]
            assert ('Sensor1', '35.0', '50.0', '10.0', '60.0', '0.0', 'False', '20240101 12:00:00') in table_passed
            assert ('Ethernet0', '37.5', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A') in table_passed

    @mock.patch('tempershow.json.dumps')
    @mock.patch('tempershow.SonicV2Connector')
    def test_show_json_output(self, mock_connector, mock_json_dumps):
        """
        Test show() with JSON output format
        Given: Temperature data available
        When: show() is called with output_json=True
        Then: Should output JSON format
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],  # thermal
            [],                            # transceiver new
            []                             # transceiver legacy
        ]

        thermal_data = {
            TEMPER_FIELD_NAME: '35.0',
            HIGH_THRESH_FIELD_NAME: '50.0',
            LOW_THRESH_FIELD_NAME: '10.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '60.0',
            CRIT_LOW_THRESH_FIELD_NAME: '0.0',
            WARNING_STATUS_FIELD_NAME: 'False',
            TIMESTAMP_FIELD_NAME: '20240101 12:00:00'
        }
        mock_db.get_all.return_value = thermal_data
        mock_json_dumps.return_value = '[]'

        with mock.patch('builtins.print'):
            temp_show.show(output_json=True)
            # Note: show() uses json.dumps from stdlib json, not tempershow.json.dumps,
            # but we patched tempershow.json.dumps so this verifies that code path.
            mock_json_dumps.assert_called_once()

    @mock.patch('tempershow.SonicV2Connector')
    def test_show_no_temperature_data(self, mock_connector):
        """
        Test show() with no temperature data available
        Given: No TEMPERATURE_INFO or TRANSCEIVER tables have data
        When: show() is called
        Then: Should print 'No temperature data available'
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        # Return None for keys() to simulate no data
        mock_db.keys.return_value = None

        with mock.patch('builtins.print') as mock_print:
            temp_show.show(output_json=False)
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any('No temperature data available' in str(call) for call in calls)

    @mock.patch('tempershow.SonicV2Connector')
    def test_show_with_transceiver_fallback_to_legacy(self, mock_connector):
        """
        Test show() when TRANSCEIVER_DOM_TEMPERATURE is not available, falls back to legacy table
        Given: TRANSCEIVER_DOM_TEMPERATURE returns empty, but TRANSCEIVER_DOM_SENSOR has keys/data
        When: show() is called
        Then: Should use TRANSCEIVER_DOM_SENSOR data as fallback
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()

        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],         # Thermal sensors
            [],                                   # Empty TRANSCEIVER_DOM_TEMPERATURE*
            ['TRANSCEIVER_DOM_SENSOR|Ethernet0']  # Fallback keys from legacy
        ]

        thermal_data = {
            TEMPER_FIELD_NAME: '35.0',
            HIGH_THRESH_FIELD_NAME: '50.0',
            LOW_THRESH_FIELD_NAME: '10.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '60.0',
            CRIT_LOW_THRESH_FIELD_NAME: '0.0',
            WARNING_STATUS_FIELD_NAME: 'False',
            TIMESTAMP_FIELD_NAME: '20240101 12:00:00'
        }

        def get_all_side_effect(db, key):
            if 'TEMPERATURE_INFO' in key:
                return thermal_data
            if 'TRANSCEIVER_DOM_TEMPERATURE' in key:
                return {}  # empty new table
            if 'TRANSCEIVER_DOM_SENSOR' in key:
                return {TEMPER_FIELD_NAME: '38.0'}  # legacy data
            return {}

        mock_db.get_all.side_effect = get_all_side_effect

        with mock.patch('builtins.print'), mock.patch('tempershow.tabulate') as mock_tabulate:
            temp_show.show(output_json=False)

            # Verify fallback keys() call for legacy table happened
            calls = [str(c) for c in mock_db.keys.call_args_list]
            assert any('TRANSCEIVER_DOM_SENSOR' in c for c in calls)

            # Also verify Ethernet0 row made it to output table
            args, _kwargs = mock_tabulate.call_args
            table_passed = args[0]
            assert ('Ethernet0', '38.0', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A') in table_passed
