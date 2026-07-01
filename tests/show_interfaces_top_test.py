import json
from datetime import datetime, timedelta
from unittest import mock

from click.testing import CliRunner

import show.main as show
from show.interfaces import top as top_module


def test_extract_byte_counters():
    class _NoByteCounters:
        rx_pps = 1

    assert top_module._extract_byte_counters({"rx_byt": "100", "tx_byt": "200"}) == (100.0, 200.0)
    assert top_module._extract_byte_counters(mock.Mock(rx_byt=300, tx_byt=400)) == (300.0, 400.0)
    assert top_module._extract_byte_counters({"rx_byt": "invalid", "tx_byt": None}) == (0.0, 0.0)
    assert top_module._extract_byte_counters(_NoByteCounters()) is None


def test_portstat_layer():
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    cnstat_dict_1 = {
        "time": base_time,
        "Ethernet0": {"rx_byt": 0, "tx_byt": 0},
        "Ethernet4": {"rx_byt": 0, "tx_byt": 0},
    }
    cnstat_dict_2 = {
        "time": base_time + timedelta(seconds=1),
        "Ethernet0": {"rx_byt": 62_500_000, "tx_byt": 0},
        "Ethernet4": {"rx_byt": 0, "tx_byt": 125_000_000},
    }

    with mock.patch("show.interfaces.top.Portstat") as mock_portstat_cls:
        mock_portstat = mock_portstat_cls.return_value
        mock_portstat.get_cnstat_dict.side_effect = [
            (cnstat_dict_1, {}),
            (cnstat_dict_2, {}),
        ]
        with mock.patch("show.interfaces.top.time.sleep", return_value=None):
            result = top_module.fetch_interface_rates(namespace=None, display_option="all", interval=1)

        assert result == {
            "Ethernet0": {"rx_mbps": 500.0, "tx_mbps": 0.0},
            "Ethernet4": {"rx_mbps": 0.0, "tx_mbps": 1000.0},
        }
        mock_portstat.get_cnstat_dict.assert_called()

    mock_portstat_cls.assert_called_once_with(None, "all")


def test_fetch_interval_zero():
    cnstat_dict = {
        "Ethernet0": {"rx_byt": 500, "tx_byt": 1000},
        "Ethernet4": {"rx_byt": 2000, "tx_byt": 3000},
    }

    with mock.patch("show.interfaces.top.Portstat") as mock_portstat_cls:
        mock_portstat = mock_portstat_cls.return_value
        mock_portstat.get_cnstat_dict.return_value = (cnstat_dict, {})
        with mock.patch("show.interfaces.top.time.sleep", return_value=None) as mock_sleep:
            result = top_module.fetch_interface_rates(namespace=None, display_option="all", interval=0)

    assert result == {
        "Ethernet0": {"rx_mbps": 0.0, "tx_mbps": 0.0},
        "Ethernet4": {"rx_mbps": 0.0, "tx_mbps": 0.0},
    }
    mock_sleep.assert_not_called()
    mock_portstat.get_cnstat_dict.assert_called_once()


def test_ranking_logic():
    port_rates = {
        "Ethernet0": {"rx_mbps": 3.0, "tx_mbps": 1.0},
        "Ethernet4": {"rx_mbps": 2.0, "tx_mbps": 6.0},
        "Ethernet8": {"rx_mbps": 2.5, "tx_mbps": 2.5},
    }

    ranked = top_module.rank_interfaces_by_traffic(port_rates, 2)

    assert ranked == [
        {
            "interface": "Ethernet4",
            "rx_mbps": 2.0,
            "tx_mbps": 6.0,
            "total_mbps": 8.0,
            "rank": 1,
        },
        {
            "interface": "Ethernet8",
            "rx_mbps": 2.5,
            "tx_mbps": 2.5,
            "total_mbps": 5.0,
            "rank": 2,
        },
    ]


def test_top_default():
    sample_rates = {
        "Ethernet0": {"rx_mbps": 10.0, "tx_mbps": 5.0},
        "Ethernet1": {"rx_mbps": 9.0, "tx_mbps": 5.0},
        "Ethernet2": {"rx_mbps": 8.0, "tx_mbps": 5.0},
        "Ethernet3": {"rx_mbps": 7.0, "tx_mbps": 5.0},
        "Ethernet4": {"rx_mbps": 6.0, "tx_mbps": 5.0},
        "Ethernet5": {"rx_mbps": 5.0, "tx_mbps": 5.0},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value=sample_rates):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], [])

    assert result.exit_code == 0
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 5


def test_top_count_3():
    sample_rates = {
        "Ethernet0": {"rx_mbps": 10.0, "tx_mbps": 5.0},
        "Ethernet1": {"rx_mbps": 9.0, "tx_mbps": 5.0},
        "Ethernet2": {"rx_mbps": 8.0, "tx_mbps": 5.0},
        "Ethernet3": {"rx_mbps": 7.0, "tx_mbps": 5.0},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value=sample_rates):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], ["--count", "3"])

    assert result.exit_code == 0
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 3


def test_top_json_output():
    sample_rates = {
        "Ethernet0": {"rx_mbps": 10.0, "tx_mbps": 5.0},
        "Ethernet1": {"rx_mbps": 9.0, "tx_mbps": 5.0},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value=sample_rates):
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["top"],
            ["-j", "--count", "2", "--interval", "2"]
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "timestamp" in payload
    assert "interval_seconds" in payload
    assert payload["interval_seconds"] == 2.0
    assert "top_interfaces" in payload
    assert len(payload["top_interfaces"]) == 2
    assert payload["top_interfaces"][0]["rank"] == 1


def test_top_empty_counters():
    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value={}):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], [])

    assert result.exit_code == 0
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 0


def test_top_portstat_error():
    runner = CliRunner(mix_stderr=True)
    with mock.patch("show.interfaces.top.Portstat", side_effect=Exception("DB connection failed")):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], [])

    assert result.exit_code == 1
    assert "Error: Error fetching interface rates: DB connection failed" in result.output


def test_two_sample_delta_computation():
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    cnstat_dict_1 = {
        "time": base_time,
        "Ethernet0": {"rx_byt": 100_000_000, "tx_byt": 50_000_000},
    }
    cnstat_dict_2 = {
        "time": base_time + timedelta(seconds=5),
        "Ethernet0": {"rx_byt": 350_000_000, "tx_byt": 150_000_000},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.Portstat") as mock_portstat_cls:
        mock_portstat = mock_portstat_cls.return_value
        mock_portstat.get_cnstat_dict.side_effect = [
            (cnstat_dict_1, {}),
            (cnstat_dict_2, {}),
        ]
        with mock.patch("show.interfaces.top.time.sleep", return_value=None):
            result = runner.invoke(
                show.cli.commands["interfaces"].commands["top"],
                ["--interval", "5", "--count", "1"]
            )

    assert result.exit_code == 0
    header_line = [line for line in result.output.splitlines() if "RX (Mbps)" in line and "TX (Mbps)" in line]
    assert len(header_line) == 1
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 1
    columns = data_lines[0].split()
    assert columns[1] == "Ethernet0"
    assert float(columns[2]) == 400.0
    assert float(columns[3]) == 160.0
    assert float(columns[4]) == 560.0