"""Regression coverage for CPO output formatting."""

import pytest

from utilities_common import cpo_helper


@pytest.mark.parametrize("data, expected", [
    (b"", ""),
    (b"A", "00000080 41                                               |A|"),
    (b"ABCDEFGH", "00000080 41 42 43 44 45 46 47 48                          |ABCDEFGH|"),
    (b"ABCDEFGHI", "00000080 41 42 43 44 45 46 47 48  49                      |ABCDEFGHI|"),
    (b"ABCDEFGHIJKLMNOP", "00000080 41 42 43 44 45 46 47 48  49 4a 4b 4c 4d 4e 4f 50 |ABCDEFGHIJKLMNOP|"),
    (b"ABCDEFGHIJKLMNOPQ", "00000080 41 42 43 44 45 46 47 48  49 4a 4b 4c 4d 4e 4f 50 |ABCDEFGHIJKLMNOP|\n"
     "00000090 51                                               |Q|"),
    (b"\x00\x1f ~\x7f\xff", "00000080 00 1f 20 7e 7f ff                                |.. ~..|"),
])
@pytest.mark.parametrize("start_newline", [False, True])
def test_eeprom_hexdump_layout(data, expected, start_newline):
    indent = " " * 8
    expected = "\n".join(indent + line for line in expected.splitlines())
    if start_newline and data:
        expected = "\n" + expected
    assert cpo_helper.hexdump(indent, data, 128, start_newline) == expected


@pytest.mark.parametrize("logical, physical, ganged, expected", [
    (0, 0, False, "0"),
    (0, 0, True, "0"),
    ("Ethernet0", 1, False, "Ethernet0"),
    ("Ethernet0", 2, True, "Ethernet0:2 (ganged)"),
])
def test_physical_port_labels(logical, physical, ganged, expected):
    assert cpo_helper.get_physical_port_name(logical, physical, ganged) == expected


def test_dom_units_missing_values_and_alignment():
    labels = {"temp": "Temperature", "rx": "Rx", "tx": "Tx", "bias": "Bias", "missing": "Missing"}
    units = {"temp": "C", "rx": "dBm", "tx": "dBm", "bias": "mA"}
    values = {"temp": 32.5, "rx": "-2.1dBm", "tx": "Unknown", "bias": "N/A"}
    assert cpo_helper.format_dict_value_to_string(labels, values, labels, units, 12) == (
        "                Temperature : 32.5C\n"
        "                Rx          : -2.1dBm\n"
        "                Tx          : Unknown\n"
    )
    assert cpo_helper.format_dict_value_to_string(labels, None, labels, units) == ""
