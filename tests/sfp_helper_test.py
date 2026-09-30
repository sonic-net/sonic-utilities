"""Regression coverage for formatting and port lookup shared by SFP and CPO."""

from unittest import mock

import pytest

from utilities_common import platform_sfputil_helper, sfp_helper


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
    assert sfp_helper.hexdump(indent, data, 128, start_newline) == expected


@pytest.mark.parametrize("logical, physical, ganged, expected", [
    (0, 0, False, "0"),
    (0, 0, True, "0"),
    ("Ethernet0", 1, False, "Ethernet0"),
    ("Ethernet0", 2, True, "Ethernet0:2 (ganged)"),
])
def test_physical_port_labels(logical, physical, ganged, expected):
    assert sfp_helper.get_physical_port_name(logical, physical, ganged) == expected


def test_dom_units_missing_values_and_alignment():
    labels = {"temp": "Temperature", "rx": "Rx", "tx": "Tx", "bias": "Bias", "missing": "Missing"}
    units = {"temp": "C", "rx": "dBm", "tx": "dBm", "bias": "mA"}
    values = {"temp": 32.5, "rx": "-2.1dBm", "tx": "Unknown", "bias": "N/A"}
    assert sfp_helper.format_dict_value_to_string(labels, values, labels, units, 12) == (
        "                Temperature : 32.5C\n"
        "                Rx          : -2.1dBm\n"
        "                Tx          : Unknown\n"
    )
    assert sfp_helper.format_dict_value_to_string(labels, None, labels, units) == ""


@pytest.mark.parametrize("explicit_mapping", [False, True])
def test_logical_and_numeric_ports(monkeypatch, capsys, explicit_mapping):
    mapping = mock.Mock()
    mapping.is_logical_port.side_effect = lambda port: port in ("Ethernet0", "Ethernet2")
    mapping.get_logical_to_physical.side_effect = lambda port: {"Ethernet0": [1, 2], "Ethernet2": [1]}[port]
    other_mapping = mock.Mock(side_effect=AssertionError("wrong port mapping"))
    monkeypatch.setattr(platform_sfputil_helper, "platform_sfputil", other_mapping if explicit_mapping else mapping)
    kwargs = {"sfputil": mapping} if explicit_mapping else {}
    resolve = platform_sfputil_helper.logical_port_name_to_physical_port_list
    assert resolve("Ethernet0", **kwargs) == [1, 2]
    assert resolve("Ethernet2", **kwargs) == [1]
    assert resolve("7", **kwargs) == [7]
    assert capsys.readouterr().out == ""
    for port in ("Ethernet999", "not-a-port", ""):
        assert resolve(port, **kwargs) is None
        assert capsys.readouterr().out == "Invalid port '{}'\n".format(port)
    other_mapping.is_logical_port.assert_not_called()
    other_mapping.get_logical_to_physical.assert_not_called()
