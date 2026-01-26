"""
Unit tests for tempershow script
Tests the TemperShow class and its ability to display temperature information
from both thermal sensors and transceiver/SFP modules with TRANSCEIVER_DOM_TEMPERATURE fallback
"""
import os
import sys
from unittest import TestCase, mock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, os.path.join(modules_path, 'scripts'))

from tempershow import TemperShow, TEMPER_TABLE_NAME, TRANSCEIVER_DOM_TEMPERATURE_TABLE_NAME, \
    TRANSCEIVER_DOM_SENSOR_TABLE_NAME, TEMPER_FIELD_NAME, HIGH_THRESH_FIELD_NAME, \
    LOW_THRESH_FIELD_NAME, CRIT_HIGH_THRESH_FIELD_NAME, CRIT_LOW_THRESH_FIELD_NAME, \
    WARNING_STATUS_FIELD_NAME, TIMESTAMP_FIELD_NAME


class TestTemperShowClass(TestCase):
    """Test cases for TemperShow class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_show = None

    def tearDown(self):
        """Clean up after tests"""
        if self.temp_show:
            self.temp_show.db = None

    @mock.patch('tempershow.SonicV2Connector')
    def test_init(self, mock_connector):
        """Test TemperShow initialization"""
        temp_show = TemperShow()
        mock_connector.assert_called_once_with(host="127.0.0.1")
        assert temp_show.db is not None

    @mock.patch('tempershow.SonicV2Connector')
    def test_get_transceiver_temperature_data_from_new_table(self, mock_connector):
        """
        Test _get_transceiver_temperature_data with new TRANSCEIVER_DOM_TEMPERATURE table
        Given: TRANSCEIVER_DOM_TEMPERATURE table has temperature data
        When: _get_transceiver_temperature_data is called
        Then: Should return temperature from new table
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()
        temp_show.db = mock_db

        # Mock get_all to return data for TRANSCEIVER_DOM_TEMPERATURE
        mock_db.get_all.return_value = {
            TEMPER_FIELD_NAME: '35.5'
        }

        result = temp_show._get_transceiver_temperature_data('Ethernet0')

        assert result == '35.5'
        # Verify that get_all was called with TRANSCEIVER_DOM_TEMPERATURE table
        mock_db.get_all.assert_called_with(mock_db.STATE_DB, 'TRANSCEIVER_DOM_TEMPERATURE|Ethernet0')

    @mock.patch('tempershow.SonicV2Connector')
    def test_get_transceiver_temperature_data_fallback_to_legacy(self, mock_connector):
        """
        Test _get_transceiver_temperature_data fallback to TRANSCEIVER_DOM_SENSOR
        Given: TRANSCEIVER_DOM_TEMPERATURE table is empty but TRANSCEIVER_DOM_SENSOR has data
        When: _get_transceiver_temperature_data is called
        Then: Should fallback to TRANSCEIVER_DOM_SENSOR and return temperature
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()
        temp_show.db = mock_db

        # Mock get_all to return empty for first call, then data for second call
        mock_db.get_all.side_effect = [
            {},  # Empty response for TRANSCEIVER_DOM_TEMPERATURE
            {TEMPER_FIELD_NAME: '36.2'}  # Data for TRANSCEIVER_DOM_SENSOR
        ]

        result = temp_show._get_transceiver_temperature_data('Ethernet1')

        assert result == '36.2'
        # Verify that get_all was called twice
        assert mock_db.get_all.call_count == 2

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
        temp_show.db = mock_db

        # Mock get_all to return empty for both tables
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
        temp_show.db = mock_db

        # Mock get_all to return data without temperature field
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
        When: _add_sensor_to_output is called with thresholds
        Then: Should add sensor to both JSON and table output
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()
        temp_show.db = mock_db

        json_output = []
        table = []
        thresholds = {
            HIGH_THRESH_FIELD_NAME: '50.0',
            LOW_THRESH_FIELD_NAME: '10.0',
            CRIT_HIGH_THRESH_FIELD_NAME: '60.0',
            CRIT_LOW_THRESH_FIELD_NAME: '0.0',
            WARNING_STATUS_FIELD_NAME: 'False',
            TIMESTAMP_FIELD_NAME: '20240101 12:00:00'
        }

        temp_show._add_sensor_to_output('Sensor1', '35.0', thresholds, json_output, table)

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
        When: _add_sensor_to_output is called with thresholds=None
        Then: Should add sensor with N/A for threshold fields
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()
        temp_show.db = mock_db

        json_output = []
        table = []

        temp_show._add_sensor_to_output('Ethernet0', '36.5', None, json_output, table)

        assert len(json_output) == 1
        assert len(table) == 1
        assert json_output[0]['Sensor'] == 'Ethernet0'
        assert json_output[0]['Temperature'] == '36.5'
        assert json_output[0]['High_TH'] == 'N/A'
        assert json_output[0]['Low_TH'] == 'N/A'
        assert table[0][2] == 'N/A'  # High_TH position in table
        assert table[0][3] == 'N/A'  # Low_TH position in table

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
        temp_show.db = mock_db

        # Mock keys to return thermal sensor key only
        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],  # Thermal sensors
            []  # No transceiver data
        ]

        # Mock get_all for thermal sensor data
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

        with mock.patch('builtins.print') as mock_print:
            temp_show.show(output_json=False)
            # Verify that tabulate was called (table output)
            mock_tabulate.assert_called_once()

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
        temp_show.db = mock_db

        # Mock keys to return both thermal and transceiver keys
        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],  # Thermal sensors
            ['TRANSCEIVER_DOM_TEMPERATURE|Ethernet0']  # Transceiver with new table
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
            elif 'TRANSCEIVER_DOM_TEMPERATURE' in key:
                return {TEMPER_FIELD_NAME: '37.5'}
            return {}

        mock_db.get_all.side_effect = get_all_side_effect

        with mock.patch('builtins.print') as mock_print:
            temp_show.show(output_json=False)
            # Verify that tabulate was called
            mock_tabulate.assert_called_once()

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
        temp_show.db = mock_db

        # Mock keys to return data
        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],
            []
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

        with mock.patch('builtins.print') as mock_print:
            temp_show.show(output_json=True)
            # Verify that json.dumps was called
            mock_json_dumps.assert_called_once()

    @mock.patch('tempershow.SonicV2Connector')
    def test_show_no_temperature_data(self, mock_connector):
        """
        Test show() with no temperature data available
        Given: No TEMPERATURE_INFO or TRANSCEIVER_DOM_TEMPERATURE data
        When: show() is called
        Then: Should print 'No temperature data available'
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()
        temp_show.db = mock_db

        # Mock keys to return no data
        mock_db.keys.return_value = None

        with mock.patch('builtins.print') as mock_print:
            temp_show.show(output_json=False)
            # Check that print was called with no temperature data message
            calls = [call[0][0] for call in mock_print.call_args_list]
            assert any('No temperature data available' in str(call) for call in calls)

    @mock.patch('tempershow.SonicV2Connector')
    def test_show_with_transceiver_fallback_to_legacy(self, mock_connector):
        """
        Test show() when TRANSCEIVER_DOM_TEMPERATURE is not available, falls back to legacy table
        Given: TRANSCEIVER_DOM_TEMPERATURE returns empty, but TRANSCEIVER_DOM_SENSOR has data
        When: show() is called
        Then: Should use TRANSCEIVER_DOM_SENSOR data as fallback
        """
        mock_db = mock.MagicMock()
        mock_connector.return_value = mock_db

        temp_show = TemperShow()
        temp_show.db = mock_db

        # Mock keys to return TRANSCEIVER_DOM_SENSOR key when TRANSCEIVER_DOM_TEMPERATURE is empty
        mock_db.keys.side_effect = [
            ['TEMPERATURE_INFO|Sensor1'],  # Thermal sensors
            [],  # Empty TRANSCEIVER_DOM_TEMPERATURE
            ['TRANSCEIVER_DOM_SENSOR|Ethernet0']  # Fallback to TRANSCEIVER_DOM_SENSOR
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
            elif 'TRANSCEIVER_DOM_TEMPERATURE' in key:
                return {}  # Empty new table
            elif 'TRANSCEIVER_DOM_SENSOR' in key:
                return {TEMPER_FIELD_NAME: '38.0'}  # Legacy table data
            return {}

        mock_db.get_all.side_effect = get_all_side_effect

        with (mock.patch('builtins.print'),
              mock.patch('tempershow.tabulate')):
            temp_show.show(output_json=False)
            # Verify that keys was called with TRANSCEIVER_DOM_SENSOR pattern
            calls = [str(call) for call in mock_db.keys.call_args_list]
            assert any('TRANSCEIVER_DOM_SENSOR' in str(call) for call in calls)
