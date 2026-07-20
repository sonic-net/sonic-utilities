"""
Utility functions for PRBS (Pseudo-Random Bit Sequence) operations
"""

from datetime import datetime

# PRBS modes
PRBS_MODES = ['both', 'rx', 'tx', 'disabled']

# RX status enum values (from SAI)
PRBS_RX_STATUS = {
    0: 'OK',
    1: 'LOCK_WITH_ERRORS',
    2: 'NOT_LOCKED',
    3: 'LOST_LOCK'
}


def format_ber(mantissa, exponent):
    """
    Format BER (Bit Error Rate) from mantissa and exponent.

    BER = mantissa × 10^(-exponent)

    Args:
        mantissa: Significant digits of the BERs
        exponent: Negative exponent (BER = mantissa × 10^-exponent)

    Returns:
        Formatted BER string (e.g., "1.83 × 10⁻⁹")
    """
    if mantissa is None or exponent is None:
        return "N/A"

    if mantissa == 0:
        return "0"

    # For very small BER (exponent >= 12), show as "< 1.00 × 10⁻¹²"
    if exponent >= 12 and mantissa == 1:
        return "< 1.00 × 10⁻¹²"

    # Format with scientific notation
    if exponent > 0:
        superscript_map = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")

        # Normalize mantissa to be between 1 and 10
        normalized_mantissa = float(mantissa)
        normalized_exp = exponent

        while normalized_mantissa >= 10:
            normalized_mantissa /= 10
            normalized_exp -= 1

        while normalized_mantissa < 1 and normalized_mantissa > 0:
            normalized_mantissa *= 10
            normalized_exp += 1

        exp_str = str(-normalized_exp).translate(superscript_map)
        return f"{normalized_mantissa:.2f} × 10{exp_str}"
    else:
        ber_value = float(mantissa) * (10 ** (-exponent))
        return f"{ber_value:.2e}"


def format_ber_scientific(mantissa, exponent):
    """
    Format BER in standard scientific notation for JSON output.

    Args:
        mantissa: Significant digits of the BER
        exponent: Negative exponent

    Returns:
        Formatted BER string (e.g., "1.83e-09")
    """
    if mantissa is None or exponent is None:
        return None

    if mantissa == 0:
        return "0"

    if exponent >= 12 and mantissa == 1:
        return "< 1.00e-12"

    # Normalize mantissa to be between 1 and 10 (preserves BER value)
    normalized_mantissa = float(mantissa)
    normalized_exp = exponent

    while normalized_mantissa >= 10:
        normalized_mantissa /= 10
        normalized_exp -= 1

    while normalized_mantissa < 1 and normalized_mantissa > 0:
        normalized_mantissa *= 10
        normalized_exp += 1

    ber = normalized_mantissa * (10 ** (-normalized_exp))
    return f"{ber:.2e}"


def average_ber(ber_values):
    """Compute the arithmetic average of per-lane BER values.

    Args:
        ber_values: list of (mantissa, exponent) tuples where
                    BER = mantissa × 10^(-exponent).
                    Entries with None mantissa/exponent are skipped.

    Returns:
        (avg_mantissa, avg_exponent) tuple suitable for format_ber(),
        or (None, None) if no valid lanes.
    """
    float_bers = []
    for mantissa, exponent in ber_values:
        if mantissa is None or exponent is None:
            continue
        float_bers.append(float(mantissa) * (10 ** (-exponent)))

    if not float_bers:
        return None, None

    avg = sum(float_bers) / len(float_bers)
    if avg == 0:
        return 0, 0

    import math
    exp = -int(math.floor(math.log10(abs(avg))))
    mant = round(avg * (10 ** exp), 2)
    return mant, exp


def get_lock_status_from_rx_status(rx_status):
    """
    Derive lock status from RX status enum.

    Args:
        rx_status: RX status enum value or string

    Returns:
        "Locked" or "Not Locked"
    """
    if rx_status is None:
        return None
    if isinstance(rx_status, int):
        rx_status = PRBS_RX_STATUS.get(rx_status, 'UNKNOWN')

    if rx_status in ['OK', 'LOCK_WITH_ERRORS']:
        return "Locked"
    else:
        return "Not Locked"


def format_elapsed_time(start_time):
    """
    Calculate elapsed time from start time to now.

    Args:
        start_time: Start timestamp (unix or ISO format)

    Returns:
        Formatted elapsed time string (HH:MM:SS)
    """
    if isinstance(start_time, str):
        try:
            # Try parsing as unix timestamp
            start_dt = datetime.fromtimestamp(float(start_time))
        except ValueError:
            # Try parsing as ISO format
            start_dt = datetime.fromisoformat(start_time)
    else:
        start_dt = datetime.fromtimestamp(start_time)

    elapsed = datetime.now() - start_dt
    hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def calculate_duration(start_time, stop_time):
    """
    Calculate duration between start and stop time.

    Args:
        start_time: Start timestamp (unix or ISO format)
        stop_time: Stop timestamp (unix or ISO format)

    Returns:
        Formatted duration string (HH:MM:SS) or "N/A" if times are invalid
    """
    if not start_time or not stop_time:
        return "N/A"

    try:
        if isinstance(start_time, str):
            try:
                start_dt = datetime.fromtimestamp(float(start_time))
            except ValueError:
                start_dt = datetime.fromisoformat(start_time)
        else:
            start_dt = datetime.fromtimestamp(start_time)

        if isinstance(stop_time, str):
            try:
                stop_dt = datetime.fromtimestamp(float(stop_time))
            except ValueError:
                stop_dt = datetime.fromisoformat(stop_time)
        else:
            stop_dt = datetime.fromtimestamp(stop_time)

        duration = stop_dt - start_dt
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError, OSError, OverflowError):
        return "N/A"


def validate_mode(mode):
    """
    Validate PRBS mode.

    Args:
        mode: Mode string

    Returns:
        Boolean indicating validity
    """
    return mode.lower() in PRBS_MODES


def get_lane_count_from_speed(speed):
    """
    Estimate lane count based on port speed.

    Args:
        speed: Port speed in Mbps (e.g., 100000 for 100G)

    Returns:
        Estimated lane count
    """
    speed_to_lanes = {
        10000: 1,    # 10G
        25000: 1,    # 25G
        40000: 4,    # 40G
        50000: 2,    # 50G
        100000: 4,   # 100G
        200000: 4,   # 200G (PAM4)
        400000: 8,   # 400G
        800000: 8,   # 800G (PAM4)
    }

    return speed_to_lanes.get(speed, 1)
