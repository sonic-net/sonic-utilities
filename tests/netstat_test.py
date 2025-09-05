from utilities_common.netstat import (
    format_brate,
    format_util,
    STATUS_NA,
)

 def test_format_brate_uses_1024_units():
    # > 10,000,000 bytes/s → MB path (now divides by 1024*1024)
    assert format_brate(11 * 1024 * 1024) == "11.00 MB/s"

    # > 10,000 bytes/s → KB path (now divides by 1024)
    assert format_brate(20 * 1024) == "20.00 KB/s"

    # <= 10,000 bytes/s → B path
    assert format_brate(9_999) == "9999.00 B/s"

 def test_format_util_uses_1024_conversion():
    """
    util = brate / (port_rate * 1024 * 1024 / 8) * 100
    Choose brate so utilization is exactly 50.00% at port_rate=1000 (Mb/s).
    """
    port_rate_mbps = 1000
    bytes_per_sec_at_line_rate = (port_rate_mbps * 1024 * 1024) / 8.0
    brate = 0.5 * bytes_per_sec_at_line_rate
    assert format_util(brate, port_rate_mbps) == "50.00%"

 def test_format_util_status_na_passthrough():
    assert format_util(STATUS_NA, 1000) == STATUS_NA
    assert format_util(12345, STATUS_NA) == STATUS_NA
