import json
import time
from datetime import datetime, timezone

import click
from tabulate import tabulate

import utilities_common.multi_asic as multi_asic_util
from utilities_common.portstat import Portstat


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_byte_counters(stat):
    """Return RX/TX byte counters as floats from dict or object stats, else None."""
    if isinstance(stat, dict):
        return _safe_float(stat.get("rx_byt")), _safe_float(stat.get("tx_byt"))
    if hasattr(stat, "rx_byt") and hasattr(stat, "tx_byt"):
        return _safe_float(stat.rx_byt), _safe_float(stat.tx_byt)
    return None


def fetch_interface_rates(namespace, display_option, interval=1):
    try:
        portstat = Portstat(namespace, display_option)
        cnstat_dict_1, _ = portstat.get_cnstat_dict()
        if interval > 0:
            time.sleep(interval)
            cnstat_dict_2, _ = portstat.get_cnstat_dict()
        else:
            cnstat_dict_2 = cnstat_dict_1
    except Exception as e:
        raise click.ClickException(f"Error fetching interface rates: {e}") from e

    actual_interval = float(interval)
    if interval > 0:
        time_1 = cnstat_dict_1.get("time")
        time_2 = cnstat_dict_2.get("time")
        if isinstance(time_1, datetime) and isinstance(time_2, datetime):
            actual_interval = (time_2 - time_1).total_seconds()

    rates = {}
    for port_name in set(cnstat_dict_1.keys()) & set(cnstat_dict_2.keys()):
        if port_name == "time":
            continue
        stat_1 = cnstat_dict_1.get(port_name)
        stat_2 = cnstat_dict_2.get(port_name)
        counters_1 = _extract_byte_counters(stat_1)
        counters_2 = _extract_byte_counters(stat_2)
        if counters_1 is None or counters_2 is None:
            continue

        sample1_rx_byt, sample1_tx_byt = counters_1
        sample2_rx_byt, sample2_tx_byt = counters_2

        if actual_interval > 0:
            rx_mbps = max(0.0, sample2_rx_byt - sample1_rx_byt) * 8 / actual_interval / 1_000_000
            tx_mbps = max(0.0, sample2_tx_byt - sample1_tx_byt) * 8 / actual_interval / 1_000_000
        else:
            rx_mbps = 0.0
            tx_mbps = 0.0

        rates[port_name] = {"rx_mbps": rx_mbps, "tx_mbps": tx_mbps}
    return rates


def rank_interfaces_by_traffic(port_rates, count):
    ranked = []
    for interface, rates in port_rates.items():
        rx_mbps = _safe_float(rates.get("rx_mbps"))
        tx_mbps = _safe_float(rates.get("tx_mbps"))
        total_mbps = rx_mbps + tx_mbps
        ranked.append({
            "interface": interface,
            "rx_mbps": rx_mbps,
            "tx_mbps": tx_mbps,
            "total_mbps": total_mbps,
        })

    ranked.sort(key=lambda entry: (-entry["total_mbps"], entry["interface"]))
    top_n = ranked[:count]

    for index, row in enumerate(top_n, start=1):
        row["rank"] = index

    return top_n


@click.command(name="top")
@multi_asic_util.multi_asic_click_options
@click.option("--count", type=click.IntRange(min=1), default=5, show_default=True, help="Number of top interfaces")
@click.option(
    "--interval",
    type=click.IntRange(min=0),
    default=1,
    show_default=True,
    help="Sampling interval in seconds"
)
@click.option("-j", "--json", "json_fmt", is_flag=True, help="Print in JSON format")
def top(namespace, display, count, interval, json_fmt):
    """Show top N interfaces by traffic (RX + TX).

    The command reads interface rate counters for the selected namespace/display
    scope, ranks interfaces by total throughput, and prints table or JSON output.
    """

    rates = fetch_interface_rates(namespace, display, interval)

    top_interfaces = rank_interfaces_by_traffic(rates, count)

    if json_fmt:
        click.echo(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "interval_seconds": float(interval),
            "top_interfaces": top_interfaces
        }, indent=4))
        return

    headers = ["Rank", "Interface", "RX (Mbps)", "TX (Mbps)", "Total (Mbps)"]
    rows = []
    for row in top_interfaces:
        rows.append([
            row["rank"],
            row["interface"],
            f"{row['rx_mbps']:.2f}",
            f"{row['tx_mbps']:.2f}",
            f"{row['total_mbps']:.2f}",
        ])

    click.echo(tabulate(rows, headers=headers))