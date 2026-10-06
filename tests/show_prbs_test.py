"""Tests for show/interfaces/prbs.py"""

import fnmatch
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from show.interfaces.prbs import (
    get_prbs_display_status,
    _compute_duration,
    _parse_aggregate_results,
    _get_average_ber_from_lanes,
    prbs_group,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockDB:
    """Combined STATE_DB + APPL_DB mock for show/interfaces/prbs tests."""

    STATE_DB = "STATE_DB"
    APPL_DB = "APPL_DB"

    def __init__(self):
        self._stores = {self.STATE_DB: {}, self.APPL_DB: {}}

    def connect(self, db):
        pass

    def keys(self, db, pattern):
        matched = [k for k in self._stores.get(db, {}) if fnmatch.fnmatch(k, pattern)]
        return matched if matched else None

    def get_all(self, db, key):
        return self._stores.get(db, {}).get(key)

    def get(self, db, key, field):
        return self._stores.get(db, {}).get(key, {}).get(field)

    def seed_state(self, entries):
        self._stores[self.STATE_DB].update(entries)

    def seed_appl(self, entries):
        self._stores[self.APPL_DB].update(entries)


def _invoke_status(db, args=None):
    """Invoke 'show interfaces prbs status' with a pre-built MockDB."""
    runner = CliRunner()
    with patch('show.interfaces.prbs.SonicV2Connector', return_value=db), \
         patch('utilities_common.cli.get_interface_naming_mode', return_value='default'):
        return runner.invoke(prbs_group.commands['status'], args or [])


# ---------------------------------------------------------------------------
# get_prbs_display_status
# ---------------------------------------------------------------------------

class TestGetPrbsDisplayStatus:

    def test_errored(self):
        assert get_prbs_display_status('errored', 'testing') == 'Errored'

    def test_failed(self):
        assert get_prbs_display_status('failed', '') == 'Failed'

    def test_running_with_testing_oper_status(self):
        assert get_prbs_display_status('running', 'testing') == 'Running'

    def test_running_with_testing_uppercase(self):
        assert get_prbs_display_status('running', 'TESTING') == 'Running'

    def test_running_without_testing_oper_status(self):
        assert get_prbs_display_status('running', 'up') == 'Interrupted'

    def test_running_empty_oper_status(self):
        assert get_prbs_display_status('running', '') == 'Interrupted'

    def test_stopped_returns_completed(self):
        assert get_prbs_display_status('stopped', '') == 'Completed'

    def test_unknown_returns_none(self):
        assert get_prbs_display_status('some_unknown', '') is None

    def test_empty_status_returns_none(self):
        assert get_prbs_display_status('', '') is None


# ---------------------------------------------------------------------------
# _compute_duration
# ---------------------------------------------------------------------------

class TestComputeDuration:

    def test_running_valid_start_time(self):
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:01:00'):
            result = _compute_duration('Running', '1000.0', 'N/A')
        assert result == '00:01:00'

    def test_running_invalid_start_time_returns_dash(self):
        result = _compute_duration('Running', 'not_a_float', 'N/A')
        assert result == '--'

    def test_completed_uses_calculate_duration(self):
        with patch('show.interfaces.prbs.calculate_duration', return_value='01:00:00'):
            result = _compute_duration('Completed', '1000.0', '4600.0')
        assert result == '01:00:00'

    def test_errored_returns_dash(self):
        assert _compute_duration('Errored', '1000.0', '4600.0') == '--'

    def test_interrupted_returns_dash(self):
        assert _compute_duration('Interrupted', '1000.0', '4600.0') == '--'


# ---------------------------------------------------------------------------
# _parse_aggregate_results
# ---------------------------------------------------------------------------

class TestParseAggregateResults:

    def test_none_data(self):
        assert _parse_aggregate_results(None) == (None, None)

    def test_empty_dict(self):
        rx, ec = _parse_aggregate_results({})
        assert rx is None
        assert ec is None

    def test_valid_integer_error_count(self):
        data = {'rx_status': 'OK', 'error_count': '42'}
        rx, ec = _parse_aggregate_results(data)
        assert rx == 'OK'
        assert ec == 42

    def test_invalid_error_count_kept_as_string(self):
        data = {'rx_status': 'OK', 'error_count': 'bad'}
        rx, ec = _parse_aggregate_results(data)
        assert rx == 'OK'
        assert ec == 'bad'

    def test_missing_error_count_is_none(self):
        data = {'rx_status': 'NOT_LOCKED'}
        rx, ec = _parse_aggregate_results(data)
        assert rx == 'NOT_LOCKED'
        assert ec is None


# ---------------------------------------------------------------------------
# _get_average_ber_from_lanes
# ---------------------------------------------------------------------------

class TestGetAverageBerFromLanes:

    def test_no_lane_keys_returns_none_none(self):
        db = MockDB()
        assert _get_average_ber_from_lanes(db, 'Ethernet0') == (None, None)

    def test_valid_ber_values_returns_average(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber_mantissa': '183', 'ber_exponent': '11'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|1': {'ber_mantissa': '200', 'ber_exponent': '11'},
        })
        mantissa, exponent = _get_average_ber_from_lanes(db, 'Ethernet0')
        assert mantissa is not None
        assert exponent is not None

    def test_invalid_ber_mantissa_becomes_none(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'ber_mantissa': 'bad', 'ber_exponent': 'also_bad'
            },
        })
        mantissa, exponent = _get_average_ber_from_lanes(db, 'Ethernet0')
        assert mantissa is None
        assert exponent is None

    def test_mixed_valid_and_invalid_lanes(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber_mantissa': '100', 'ber_exponent': '10'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|1': {'ber_mantissa': 'bad', 'ber_exponent': '10'},
        })
        mantissa, exponent = _get_average_ber_from_lanes(db, 'Ethernet0')
        assert mantissa is not None

    def test_invalid_exponent_becomes_none(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'ber_mantissa': '183', 'ber_exponent': 'bad'
            },
        })
        mantissa, exponent = _get_average_ber_from_lanes(db, 'Ethernet0')
        assert mantissa is None
        assert exponent is None


# ---------------------------------------------------------------------------
# show_all_prbs_status  (via status command, no -i)
# ---------------------------------------------------------------------------

class TestShowAllPrbsStatus:

    def test_no_tests_found_table(self):
        db = MockDB()
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert "No PRBS tests found" in result.output

    def test_no_tests_found_json(self):
        db = MockDB()
        result = _invoke_status(db, ['--json'])
        assert result.exit_code == 0
        assert json.loads(result.output) == {}

    def test_all_unknown_status_shows_no_active(self):
        """Keys exist but none have a recognisable display status."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'unknown_state'},
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert "No active PRBS tests" in result.output

    def test_running_test_appears_in_table(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:05:00'):
            result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'Ethernet0' in result.output
        assert 'Running' in result.output

    def test_completed_test_with_ok_rx_status(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_RESULTS|Ethernet0': {
                'rx_status': 'OK', 'error_count': '0',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber_mantissa': '183', 'ber_exponent': '11'},
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'Completed' in result.output
        assert 'Ethernet0' in result.output

    def test_completed_test_with_lock_with_errors(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_RESULTS|Ethernet0': {
                'rx_status': 'LOCK_WITH_ERRORS', 'error_count': '500',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber_mantissa': '100', 'ber_exponent': '9'},
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'Completed' in result.output
        assert 'LOCK_WITH_ERRORS' in result.output

    def test_completed_test_with_not_locked_rx_status(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_RESULTS|Ethernet0': {'rx_status': 'NOT_LOCKED'},
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'NOT_LOCKED' in result.output

    def test_completed_with_no_ber_lane_data(self):
        """Completed + OK rx_status but no lane keys → ber shows '--'."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_RESULTS|Ethernet0': {'rx_status': 'OK', 'error_count': '0'},
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'Ethernet0' in result.output

    def test_start_time_invalid_string_uses_raw(self):
        """If start_time can't be parsed as a float, the raw string is displayed."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': 'not-a-timestamp', 'stop_time': 'also-bad',
            },
            'PORT_PRBS_RESULTS|Ethernet0': {'rx_status': 'OK', 'error_count': '0'},
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'not-a-timestamp' in result.output

    def test_start_time_na_shows_dash(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'none',
                'start_time': 'N/A', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:00:00'):
            result = _invoke_status(db)
        assert result.exit_code == 0
        assert '--' in result.output

    def test_json_output_with_running_test(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:05:00'):
            result = _invoke_status(db, ['--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'Ethernet0' in data
        assert data['Ethernet0']['status'] == 'Running'

    def test_json_output_with_completed_test(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_RESULTS|Ethernet0': {'rx_status': 'OK', 'error_count': '5'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber_mantissa': '183', 'ber_exponent': '11'},
        })
        result = _invoke_status(db, ['--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['Ethernet0']['status'] == 'Completed'
        assert data['Ethernet0']['rx_status'] == 'OK'

    def test_no_port_data_in_appl_db(self):
        """oper_status defaults to '' when PORT_TABLE entry is absent."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:01:00'):
            result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'Interrupted' in result.output

    def test_completed_no_results_data(self):
        """Completed test with no PORT_PRBS_RESULTS entry — rx_status stays '--'."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
        })
        result = _invoke_status(db)
        assert result.exit_code == 0
        assert 'Completed' in result.output


# ---------------------------------------------------------------------------
# status command — per-interface (with -i)
# ---------------------------------------------------------------------------

class TestPrbsStatusPerInterface:

    def test_no_test_data_table(self):
        db = MockDB()
        result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert "No PRBS test data available for Ethernet0" in result.output

    def test_no_test_data_json(self):
        db = MockDB()
        result = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'error' in data

    def test_failed_status_table(self):
        db = MockDB()
        db.seed_state({'PORT_PRBS_TEST|Ethernet0': {'status': 'failed'}})
        result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'Failed to start prbs test on Ethernet0' in result.output

    def test_failed_status_json(self):
        db = MockDB()
        db.seed_state({'PORT_PRBS_TEST|Ethernet0': {'status': 'failed'}})
        result = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['status'] == 'Failed'

    def test_tx_mode_table(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'tx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:01:00'):
            result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'TX mode does not capture PRBS results' in result.output

    def test_tx_mode_json(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'tx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:01:00'):
            result = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'message' in data
        assert 'TX mode' in data['message']

    def test_no_lane_keys_table(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:02:00'):
            result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'No PRBS result data available' in result.output

    def test_no_lane_keys_json(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        db.seed_appl({'PORT_TABLE:Ethernet0': {'oper_status': 'testing'}})
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:02:00'):
            result = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'message' in data

    def test_lane_results_table(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'rx_status': 'OK', 'error_count': '0',
                'ber_mantissa': '183', 'ber_exponent': '11',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|1': {
                'rx_status': 'OK', 'error_count': '2',
                'ber_mantissa': '200', 'ber_exponent': '11',
            },
        })
        result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'Lane' in result.output
        assert 'BER' in result.output
        assert 'Locked' in result.output

    def test_lane_results_json(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'PRBS31',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'rx_status': 'OK', 'error_count': '0',
                'ber_mantissa': '183', 'ber_exponent': '11',
            },
        })
        result = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'lanes' in data
        assert len(data['lanes']) == 1
        assert data['lanes'][0]['lock_status'] == 'Locked'

    def test_lane_invalid_ber_shows_na(self):
        """Lane with unparseable BER strings → 'N/A' in table, None in JSON."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'rx_status': 'NOT_LOCKED', 'error_count': 'bad',
                'ber_mantissa': 'not_int', 'ber_exponent': 'not_int',
            },
        })
        result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'N/A' in result.output
        assert 'Not Locked' in result.output

    def test_lane_invalid_ber_json_is_none(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'rx_status': 'NOT_LOCKED', 'error_count': None,
                'ber_mantissa': 'bad', 'ber_exponent': 'bad',
            },
        })
        result = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['lanes'][0]['ber'] is None

    def test_lane_invalid_error_count_has_error_count_false(self):
        """Unparseable error_count → error_count=None in JSON, 'N/A' in table."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {
                'rx_status': 'OK', 'error_count': 'invalid',
                'ber_mantissa': '100', 'ber_exponent': '9',
            },
        })
        result_table = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result_table.exit_code == 0
        assert 'N/A' in result_table.output

        result_json = _invoke_status(db, ['-i', 'Ethernet0', '--json'])
        data = json.loads(result_json.output)
        assert data['lanes'][0]['error_count'] is None

    def test_unknown_prbs_status_shows_unknown(self):
        """get_prbs_display_status returns None → display as 'Unknown'."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': '', 'mode': 'rx', 'pattern': 'none',
                'start_time': 'N/A', 'stop_time': 'N/A',
            },
        })
        result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'Unknown' in result.output

    def test_no_appl_db_port_data(self):
        """Missing APPL_DB PORT_TABLE entry defaults oper_status to ''."""
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'running', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': 'N/A',
            },
        })
        with patch('show.interfaces.prbs.format_elapsed_time', return_value='00:00:30'):
            result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'Interrupted' in result.output

    def test_header_line_contains_interface_info(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'both', 'pattern': 'PRBS7',
                'start_time': '1000.0', 'stop_time': '4600.0',
            },
        })
        result = _invoke_status(db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert 'Interface: Ethernet0' in result.output
        assert 'Mode: both' in result.output
        assert 'Pattern: PRBS7' in result.output


# ---------------------------------------------------------------------------
# status command — alias mode
# ---------------------------------------------------------------------------

class TestPrbsStatusAlias:

    def _invoke_alias(self, db, args, alias_return):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = alias_return
        runner = CliRunner()
        with patch('show.interfaces.prbs.SonicV2Connector', return_value=db), \
             patch('utilities_common.cli.get_interface_naming_mode', return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter', mock_converter):
            return runner.invoke(prbs_group.commands['status'], args)

    def test_valid_alias_resolves_to_interface(self):
        db = MockDB()
        db.seed_state({
            'PORT_PRBS_TEST|Ethernet0': {
                'status': 'stopped', 'mode': 'rx', 'pattern': 'none',
                'start_time': '1000.0', 'stop_time': '4600.0',
            }
        })
        result = self._invoke_alias(db, ['-i', 'etp1'], 'Ethernet0')
        assert result.exit_code == 0
        assert 'Ethernet0' in result.output

    def test_invalid_alias_fails(self):
        db = MockDB()
        result = self._invoke_alias(db, ['-i', 'bad_alias'], None)
        assert result.exit_code != 0
        assert 'Invalid interface name' in result.output
