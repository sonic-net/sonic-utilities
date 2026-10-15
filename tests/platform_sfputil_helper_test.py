"""Regression coverage for shared optical port helpers and formatting."""

from unittest import mock

import click
import pytest

from utilities_common import platform_sfputil_helper as helper
from utilities_common.sfp_helper import covert_application_advertisement_to_output_string


@pytest.fixture
def port_mapper(monkeypatch):
    mapper = mock.Mock()
    mapper.is_logical_port.side_effect = lambda name: name == "Ethernet0"
    mapper.get_logical_to_physical.return_value = [2, 2, 1]
    monkeypatch.setattr(helper, "platform_sfputil", mapper)
    return mapper


@pytest.mark.parametrize("validated, expected", [(False, [2, 2, 1]), (True, [2, 1])])
def test_logical_port_resolution(port_mapper, capsys, validated, expected):
    resolver = (helper.get_validated_physical_port_list if validated else
                helper.logical_port_name_to_physical_port_list)
    assert resolver("Ethernet0") == expected
    port_mapper.get_logical_to_physical.assert_called_once_with("Ethernet0")
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("port, validated", [("7", False), ("7", True), (7, True)])
def test_physical_port_resolution(port_mapper, port, validated):
    resolver = (helper.get_validated_physical_port_list if validated else
                helper.logical_port_name_to_physical_port_list)
    assert resolver(port) == [7]
    port_mapper.get_logical_to_physical.assert_not_called()


@pytest.mark.parametrize("port", ["Ethernet999", "not-a-port"])
@pytest.mark.parametrize("validated", [False, True])
def test_invalid_port_reporting(port_mapper, capsys, port, validated):
    if validated:
        with pytest.raises(click.ClickException, match="Invalid port '{}'".format(port)):
            helper.get_validated_physical_port_list(port)
        assert capsys.readouterr().out == ""
    else:
        assert helper.logical_port_name_to_physical_port_list(port) is None
        assert capsys.readouterr().out == "Invalid port '{}'\n".format(port)
    port_mapper.get_logical_to_physical.assert_not_called()


@pytest.mark.parametrize("physical_ports", [None, []])
def test_missing_mapping_preserves_legacy_and_rejects_validated(port_mapper, capsys, physical_ports):
    port_mapper.get_logical_to_physical.return_value = physical_ports
    assert helper.logical_port_name_to_physical_port_list("Ethernet0") == physical_ports
    with pytest.raises(click.ClickException, match="Invalid port 'Ethernet0'"):
        helper.get_validated_physical_port_list("Ethernet0")
    assert capsys.readouterr().out == ""


def test_physical_index_none_member_reports_error(port_mapper, capsys):
    port_mapper.get_logical_to_physical.return_value = [None]
    with pytest.raises(SystemExit) as error:
        helper.logical_port_to_physical_port_index("Ethernet0")
    assert error.value.code == helper.EXIT_FAIL
    assert capsys.readouterr().out == "Error: No physical port found for logical port 'Ethernet0'\n"


def test_physical_index_uses_first_member(port_mapper, capsys):
    assert helper.logical_port_to_physical_port_index("Ethernet0") == 2
    assert capsys.readouterr().out == ""


def test_physical_index_rejects_invalid_port(port_mapper, capsys):
    with pytest.raises(SystemExit) as error:
        helper.logical_port_to_physical_port_index("Ethernet999")
    assert error.value.code == helper.ERROR_INVALID_PORT
    assert "Error: invalid port Ethernet999" in capsys.readouterr().out
    port_mapper.get_logical_to_physical.assert_not_called()


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
    assert helper.hexdump(indent, data, 128, start_newline) == expected


@pytest.mark.parametrize("logical, physical, ganged, expected", [
    (0, 0, False, "0"),
    (0, 0, True, "0"),
    ("Ethernet0", 1, False, "Ethernet0"),
    ("Ethernet0", 2, True, "Ethernet0:2 (ganged)"),
])
def test_physical_port_labels(logical, physical, ganged, expected):
    assert helper.get_physical_port_name(logical, physical, ganged) == expected


def test_dom_units_missing_values_and_alignment():
    labels = {"temp": "Temperature", "rx": "Rx", "tx": "Tx", "bias": "Bias", "missing": "Missing"}
    units = {"temp": "C", "rx": "dBm", "tx": "dBm", "bias": "mA"}
    values = {"temp": 32.5, "rx": "-2.1dBm", "tx": "Unknown", "bias": "N/A"}
    assert helper.format_dict_value_to_string(labels, values, labels, units, 12) == (
        "                Temperature : 32.5C\n"
        "                Rx          : -2.1dBm\n"
        "                Tx          : Unknown\n"
    )
    assert helper.format_dict_value_to_string(labels, None, labels, units) == ""


@pytest.mark.parametrize("serialized", [False, True])
def test_application_advertisements_keep_natural_order_and_zero_assignments(serialized):
    advertisements = {
        10: {"host_electrical_interface_id": "400G", "module_media_interface_id": "FR4",
             "host_lane_assignment_options": 1, "media_lane_assignment_options": 2},
        2: {"host_electrical_interface_id": "100G", "module_media_interface_id": "DR",
            "host_lane_assignment_options": 0},
    }
    value = repr(advertisements) if serialized else advertisements
    assert helper.format_application_advertisement(value) == [
        "100G - Host Assign (0x00) - DR - Media Assign (N/A)",
        "400G - Host Assign (0x01) - FR4 - Media Assign (0x02)",
    ]


@pytest.mark.parametrize("value, expected", [
    ({}, ["N/A"]),
    ("not-a-dict", ["not-a-dict"]),
    ({1: "legacy"}, ["legacy"]),
])
def test_application_advertisement_fallbacks(value, expected):
    assert helper.format_application_advertisement(value) == expected


def test_legacy_application_format_retains_unknown_and_insertion_order():
    advertisements = {
        10: {"host_electrical_interface_id": "400G", "module_media_interface_id": "FR4",
             "host_lane_assignment_options": 1, "media_lane_assignment_options": 2},
        2: {"host_electrical_interface_id": "100G", "host_lane_assignment_options": 0},
        1: {},
    }
    assert covert_application_advertisement_to_output_string(
        "", {"application_advertisement": repr(advertisements)}) == (
            "Application Advertisement: 400G - Host Assign (0x1) - FR4 - Media Assign (0x2)\n"
            "                           100G - Host Assign (Unknown) - Unknown - Media Assign (Unknown)\n"
        )
