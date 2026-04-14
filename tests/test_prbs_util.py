import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from utilities_common.prbs_util import (
    PRBS_MODES,
    PRBS_RX_STATUS,
    format_ber,
    format_ber_scientific,
    average_ber,
    get_lock_status_from_rx_status,
    format_elapsed_time,
    calculate_duration,
    validate_mode,
    get_lane_count_from_speed,
)


# ---------------------------------------------------------------------------
# Constants / data-structure tests
# ---------------------------------------------------------------------------
class TestPrbsConstants:

    def test_prbs_modes(self):
        assert set(PRBS_MODES) == {'both', 'rx', 'tx', 'disabled'}

    def test_prbs_rx_status_enum(self):
        assert PRBS_RX_STATUS[0] == 'OK'
        assert PRBS_RX_STATUS[1] == 'LOCK_WITH_ERRORS'
        assert PRBS_RX_STATUS[2] == 'NOT_LOCKED'
        assert PRBS_RX_STATUS[3] == 'LOST_LOCK'


# ---------------------------------------------------------------------------
# format_ber
# ---------------------------------------------------------------------------
class TestFormatBer:

    def test_none_mantissa(self):
        assert format_ber(None, 9) == "N/A"

    def test_none_exponent(self):
        assert format_ber(183, None) == "N/A"

    def test_both_none(self):
        assert format_ber(None, None) == "N/A"

    def test_zero_mantissa(self):
        assert format_ber(0, 9) == "0"

    def test_zero_mantissa_zero_exponent(self):
        assert format_ber(0, 0) == "0"

    def test_very_small_ber(self):
        result = format_ber(1, 12)
        assert result == "< 1.00 × 10⁻¹²"

    def test_very_small_ber_higher_exponent(self):
        result = format_ber(1, 15)
        assert result == "< 1.00 × 10⁻¹²"

    def test_scientific_notation_positive_exponent(self):
        result = format_ber(183, 9)
        assert "× 10" in result
        assert "1.83" in result

    def test_single_digit_mantissa(self):
        result = format_ber(5, 9)
        assert "× 10" in result
        assert "5.00" in result

    def test_large_mantissa_normalization(self):
        result = format_ber(50000, 9)
        assert "× 10" in result
        assert "5.00" in result

    def test_zero_exponent(self):
        result = format_ber(5, 0)
        assert "e" in result.lower()

    def test_superscript_in_output(self):
        result = format_ber(1, 9)
        assert "⁻" in result


# ---------------------------------------------------------------------------
# format_ber_scientific
# ---------------------------------------------------------------------------
class TestFormatBerScientific:

    def test_none_mantissa(self):
        assert format_ber_scientific(None, 9) is None

    def test_none_exponent(self):
        assert format_ber_scientific(183, None) is None

    def test_both_none(self):
        assert format_ber_scientific(None, None) is None

    def test_zero_mantissa(self):
        assert format_ber_scientific(0, 9) == "0"

    def test_very_small_ber(self):
        assert format_ber_scientific(1, 12) == "< 1.00e-12"

    def test_very_small_ber_higher_exponent(self):
        assert format_ber_scientific(1, 15) == "< 1.00e-12"

    def test_standard_value(self):
        result = format_ber_scientific(183, 9)
        assert "e-" in result
        val = float(result)
        assert abs(val - 1.83e-7) < 1e-9

    def test_single_digit_mantissa(self):
        result = format_ber_scientific(5, 9)
        val = float(result)
        assert abs(val - 5e-9) < 1e-11

    def test_zero_exponent(self):
        result = format_ber_scientific(5, 0)
        val = float(result)
        assert abs(val - 5.0) < 0.01


# ---------------------------------------------------------------------------
# average_ber
# ---------------------------------------------------------------------------
class TestAverageBer:

    def test_empty_list(self):
        assert average_ber([]) == (None, None)

    def test_all_none_entries(self):
        assert average_ber([(None, 9), (183, None), (None, None)]) == (None, None)

    def test_single_lane(self):
        mant, exp = average_ber([(183, 9)])
        ber = mant * (10 ** (-exp))
        assert abs(ber - 183e-9) < 1e-12

    def test_uniform_lanes(self):
        mant, exp = average_ber([(5, 9), (5, 9), (5, 9), (5, 9)])
        ber = mant * (10 ** (-exp))
        assert abs(ber - 5e-9) < 1e-12

    def test_mixed_values(self):
        lanes = [(100, 9), (200, 9), (300, 9), (400, 9)]
        mant, exp = average_ber(lanes)
        expected_avg = (100e-9 + 200e-9 + 300e-9 + 400e-9) / 4
        ber = mant * (10 ** (-exp))
        assert abs(ber - expected_avg) / expected_avg < 0.01

    def test_different_exponents(self):
        lanes = [(1, 9), (1, 7)]
        mant, exp = average_ber(lanes)
        expected_avg = (1e-9 + 1e-7) / 2
        ber = mant * (10 ** (-exp))
        assert abs(ber - expected_avg) / expected_avg < 0.01

    def test_skips_none_entries(self):
        lanes = [(183, 9), (None, 9), (183, 9)]
        mant, exp = average_ber(lanes)
        ber = mant * (10 ** (-exp))
        assert abs(ber - 183e-9) < 1e-12

    def test_all_zero_mantissa(self):
        assert average_ber([(0, 9), (0, 9)]) == (0, 0)

    def test_eight_lanes(self):
        lanes = [(150, 9), (160, 9), (170, 9), (180, 9),
                 (190, 9), (200, 9), (210, 9), (220, 9)]
        mant, exp = average_ber(lanes)
        expected_avg = sum(v * 1e-9 for v, _ in lanes) / 8
        ber = mant * (10 ** (-exp))
        assert abs(ber - expected_avg) / expected_avg < 0.01

    def test_result_usable_by_format_ber(self):
        mant, exp = average_ber([(183, 9), (200, 9)])
        result = format_ber(mant, exp)
        assert "× 10" in result


# ---------------------------------------------------------------------------
# get_lock_status_from_rx_status
# ---------------------------------------------------------------------------
class TestGetLockStatusFromRxStatus:

    def test_none_returns_none(self):
        assert get_lock_status_from_rx_status(None) is None

    def test_ok_string(self):
        assert get_lock_status_from_rx_status('OK') == "Locked"

    def test_lock_with_errors_string(self):
        assert get_lock_status_from_rx_status('LOCK_WITH_ERRORS') == "Locked"

    def test_not_locked_string(self):
        assert get_lock_status_from_rx_status('NOT_LOCKED') == "Not Locked"

    def test_lost_lock_string(self):
        assert get_lock_status_from_rx_status('LOST_LOCK') == "Not Locked"

    def test_unknown_string(self):
        assert get_lock_status_from_rx_status('SOMETHING_ELSE') == "Not Locked"

    def test_int_0_ok(self):
        assert get_lock_status_from_rx_status(0) == "Locked"

    def test_int_1_lock_with_errors(self):
        assert get_lock_status_from_rx_status(1) == "Locked"

    def test_int_2_not_locked(self):
        assert get_lock_status_from_rx_status(2) == "Not Locked"

    def test_int_3_lost_lock(self):
        assert get_lock_status_from_rx_status(3) == "Not Locked"

    def test_int_unknown(self):
        assert get_lock_status_from_rx_status(99) == "Not Locked"


# ---------------------------------------------------------------------------
# format_elapsed_time
# ---------------------------------------------------------------------------
class TestFormatElapsedTime:

    @patch('utilities_common.prbs_util.datetime')
    def test_numeric_timestamp(self, mock_dt):
        mock_dt.fromtimestamp.return_value = datetime(2024, 3, 31, 10, 0, 0)
        mock_dt.now.return_value = datetime(2024, 3, 31, 11, 30, 45)
        result = format_elapsed_time(1711875600.0)
        assert result == '01:30:45'

    @patch('utilities_common.prbs_util.datetime')
    def test_string_unix_timestamp(self, mock_dt):
        mock_dt.fromtimestamp.return_value = datetime(2024, 3, 31, 10, 0, 0)
        mock_dt.now.return_value = datetime(2024, 3, 31, 10, 5, 30)
        result = format_elapsed_time('1711875600.0')
        assert result == '00:05:30'

    @patch('utilities_common.prbs_util.datetime')
    def test_string_iso_format(self, mock_dt):
        mock_dt.fromtimestamp.side_effect = ValueError("not a float")
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.now.return_value = datetime(2024, 3, 31, 12, 0, 0)

        def from_ts(val):
            raise ValueError
        mock_dt.fromtimestamp = from_ts
        result = format_elapsed_time('2024-03-31T10:00:00')
        assert result == '02:00:00'

    @patch('utilities_common.prbs_util.datetime')
    def test_zero_elapsed(self, mock_dt):
        now = datetime(2024, 3, 31, 10, 0, 0)
        mock_dt.fromtimestamp.return_value = now
        mock_dt.now.return_value = now
        result = format_elapsed_time(1711875600.0)
        assert result == '00:00:00'

    @patch('utilities_common.prbs_util.datetime')
    def test_large_elapsed(self, mock_dt):
        mock_dt.fromtimestamp.return_value = datetime(2024, 3, 30, 0, 0, 0)
        mock_dt.now.return_value = datetime(2024, 3, 31, 2, 3, 4)
        result = format_elapsed_time(1711756800.0)
        assert result == '26:03:04'


# ---------------------------------------------------------------------------
# calculate_duration
# ---------------------------------------------------------------------------
class TestCalculateDuration:

    def test_numeric_timestamps(self):
        result = calculate_duration(1000000, 1003661)
        assert result == '01:01:01'

    def test_string_unix_timestamps(self):
        result = calculate_duration('1000000', '1003600')
        assert result == '01:00:00'

    def test_iso_format_strings(self):
        result = calculate_duration('2024-03-31T10:00:00', '2024-03-31T12:30:45')
        assert result == '02:30:45'

    def test_none_start(self):
        assert calculate_duration(None, '1003600') == 'N/A'

    def test_none_stop(self):
        assert calculate_duration('1000000', None) == 'N/A'

    def test_both_none(self):
        assert calculate_duration(None, None) == 'N/A'

    def test_empty_start(self):
        assert calculate_duration('', '1003600') == 'N/A'

    def test_empty_stop(self):
        assert calculate_duration('1000000', '') == 'N/A'

    def test_invalid_start(self):
        assert calculate_duration('not_a_timestamp', '1003600') == 'N/A'

    def test_invalid_stop(self):
        assert calculate_duration('1000000', 'bad_value') == 'N/A'

    def test_zero_duration(self):
        result = calculate_duration(1000000, 1000000)
        assert result == '00:00:00'

    def test_large_duration(self):
        result = calculate_duration(1000000, 1100000)
        hours, remainder = divmod(100000, 3600)
        minutes, seconds = divmod(remainder, 60)
        expected = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        assert result == expected

    def test_mixed_string_and_numeric(self):
        result = calculate_duration('1000000', 1003600)
        assert result == '01:00:00'


# ---------------------------------------------------------------------------
# validate_mode
# ---------------------------------------------------------------------------
class TestValidateMode:

    @pytest.mark.parametrize("mode", ['both', 'rx', 'tx', 'disabled'])
    def test_valid_modes(self, mode):
        assert validate_mode(mode) is True

    @pytest.mark.parametrize("mode", ['BOTH', 'RX', 'TX', 'DISABLED', 'Both', 'Rx'])
    def test_case_insensitive(self, mode):
        assert validate_mode(mode) is True

    def test_invalid_mode(self):
        assert validate_mode('invalid') is False

    def test_empty_string(self):
        assert validate_mode('') is False

    def test_partial_match(self):
        assert validate_mode('bo') is False


# ---------------------------------------------------------------------------
# get_lane_count_from_speed
# ---------------------------------------------------------------------------
class TestGetLaneCountFromSpeed:

    @pytest.mark.parametrize("speed,expected_lanes", [
        (10000, 1),
        (25000, 1),
        (40000, 4),
        (50000, 2),
        (100000, 4),
        (200000, 4),
        (400000, 8),
        (800000, 8),
    ])
    def test_known_speeds(self, speed, expected_lanes):
        assert get_lane_count_from_speed(speed) == expected_lanes

    def test_unknown_speed_defaults_to_1(self):
        assert get_lane_count_from_speed(999999) == 1

    def test_zero_speed_defaults_to_1(self):
        assert get_lane_count_from_speed(0) == 1

    def test_negative_speed_defaults_to_1(self):
        assert get_lane_count_from_speed(-100000) == 1
