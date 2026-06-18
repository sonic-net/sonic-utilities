import click
import sys

from swsscommon import swsscommon
from tabulate import tabulate


TASK_STATS_QUERY_CHANNEL = "ORCH_TASK_STATS_QUERY"
TASK_STATS_REPLY_CHANNEL = "ORCH_TASK_STATS_REPLY"
REPLY_TIMEOUT_MS = 10000


def _ms(ns):
    """Convert ns -> ms as a float (no unit suffix)."""
    return ns / 1_000_000.0


def _fmt_quartet(median_ns, q1_ns, q3_ns, max_ns):
    """Render a 'median/q1/q3/max' quartet in ms, two decimals each."""
    return (f"{_ms(median_ns):.2f}/"
            f"{_ms(q1_ns):.2f}/"
            f"{_ms(q3_ns):.2f}/"
            f"{_ms(max_ns):.2f}")


def _query_orchagent(op):
    """Send a query to orchagent over APPL_DB notification channels and
    return (op_ret, data_ret, fvs) on success.

    Raises RuntimeError on timeout or transport error.
    """
    db = swsscommon.DBConnector("APPL_DB", 0)
    producer = swsscommon.NotificationProducer(db, TASK_STATS_QUERY_CHANNEL)
    consumer = swsscommon.NotificationConsumer(db, TASK_STATS_REPLY_CHANNEL)

    sel = swsscommon.Select()
    sel.addSelectable(consumer)

    producer.send(op, "", swsscommon.FieldValuePairs([]))

    state, _ = sel.select(REPLY_TIMEOUT_MS)
    if state == swsscommon.Select.TIMEOUT:
        raise RuntimeError(
            f"Timed out after {REPLY_TIMEOUT_MS} ms waiting for orchagent reply")
    if state != swsscommon.Select.OBJECT:
        raise RuntimeError(f"Select error waiting for orchagent reply: {state}")

    op_ret, data_ret, fvs = consumer.pop()
    if op_ret != "ok":
        raise RuntimeError(
            f"orchagent returned error: op={op_ret} data={data_ret}")
    return op_ret, data_ret, fvs


def _parse_stats(fvs):
    """Parse the FieldValueTuples returned by orchagent into a list of
    dicts. Each value is 14 pipe-separated fields:
      count | total_run_ns
      | median_run_ns | q1_run_ns | q3_run_ns | max_run_ns
      | high_outliers | low_outliers
      | sched_count | total_sched_ns
      | median_sched_ns | q1_sched_ns | q3_sched_ns | max_sched_ns
    """
    rows = []
    for name, blob in fvs:
        parts = blob.split("|")
        if len(parts) != 14:
            # Skip malformed rows rather than failing the whole table.
            continue
        try:
            count            = int(parts[0])
            total_ns         = int(parts[1])
            median_ns        = int(parts[2])
            q1_ns            = int(parts[3])
            q3_ns            = int(parts[4])
            max_ns           = int(parts[5])
            high_outliers    = int(parts[6])
            low_outliers     = int(parts[7])
            sched_count      = int(parts[8])
            total_sched_ns   = int(parts[9])
            sched_median_ns  = int(parts[10])
            sched_q1_ns      = int(parts[11])
            sched_q3_ns      = int(parts[12])
            sched_max_ns     = int(parts[13])
        except ValueError:
            continue
        rows.append({
            "name":            name,
            "count":           count,
            "total_ns":        total_ns,
            "median_ns":       median_ns,
            "q1_ns":           q1_ns,
            "q3_ns":           q3_ns,
            "max_ns":          max_ns,
            "high_outliers":   high_outliers,
            "low_outliers":    low_outliers,
            "sched_count":     sched_count,
            "total_sched_ns":  total_sched_ns,
            "sched_median_ns": sched_median_ns,
            "sched_q1_ns":     sched_q1_ns,
            "sched_q3_ns":     sched_q3_ns,
            "sched_max_ns":    sched_max_ns,
        })
    return rows


def _render_table(rows):
    # Sort: total_ns descending, ties broken by name ascending.
    rows = sorted(rows,
                  key=lambda r: (-r["total_ns"], r["name"]))

    table = []
    for r in rows:
        if r["count"] == 0:
            run_quartet  = "-"
            total_run    = "-"
        else:
            run_quartet  = _fmt_quartet(r["median_ns"],
                                        r["q1_ns"],
                                        r["q3_ns"],
                                        r["max_ns"])
            total_run    = f"{_ms(r['total_ns']):.2f}"

        if r["sched_count"] == 0:
            sched_quartet = "-"
            total_sched   = "-"
        else:
            sched_quartet = _fmt_quartet(r["sched_median_ns"],
                                         r["sched_q1_ns"],
                                         r["sched_q3_ns"],
                                         r["sched_max_ns"])
            total_sched   = f"{_ms(r['total_sched_ns']):.2f}"

        # TOTAL column shows "<run>/<sched>" so a viewer can see at a
        # glance how much wall-clock the loop spent inside the task vs
        # waiting before scheduling it.
        total_str = f"{total_run}/{total_sched}"

        outliers = r["high_outliers"] + r["low_outliers"]

        table.append([
            r["name"],
            run_quartet,
            r["count"],
            outliers,
            sched_quartet,
            total_str,
        ])

    headers = [
        "TASK",
        "RUN TIME\nmedian/q1/q3/max\n(in msec)",
        "RUNS",
        "OUTLIERS",
        "SCHED LATENCY\nmedian/q1/q3/max\n(in msec)",
        "TOTAL\nrun/sched\n(in msec)",
    ]
    return tabulate(table, headers=headers, tablefmt="plain")


@click.group()
def orchagent():
    """Show orchagent runtime information"""
    pass


@orchagent.command("tasks")
def tasks():
    """Show per-Executor execution timing in orchagent"""
    try:
        _, _, fvs = _query_orchagent("show")
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    rows = _parse_stats(fvs)
    click.echo(_render_table(rows))
