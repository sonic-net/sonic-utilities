import click
import sys

from swsscommon import swsscommon
from tabulate import tabulate

from sonic_py_common import multi_asic
from utilities_common.multi_asic import multi_asic_click_option_namespace


TASK_STATS_QUERY_CHANNEL = "ORCH_TASK_STATS_QUERY"
TASK_STATS_REPLY_CHANNEL = "ORCH_TASK_STATS_REPLY"
REPLY_TIMEOUT_MS = 10000
# DBConnector connection timeout (0 = library default); the reply wait is
# governed separately by REPLY_TIMEOUT_MS on the Select below.
REDIS_TIMEOUT_MSECS = 0


def _ms(ns):
    """Convert ns -> ms as a float (no unit suffix)."""
    return ns / 1_000_000.0


def _fmt_quartet(median_ns, q1_ns, q3_ns, max_ns):
    """Render a 'median/q1/q3/max' quartet in ms, two decimals each."""
    return (f"{_ms(median_ns):.2f}/"
            f"{_ms(q1_ns):.2f}/"
            f"{_ms(q3_ns):.2f}/"
            f"{_ms(max_ns):.2f}")


def _query_orchagent(op, namespace):
    """Send a query to orchagent over APPL_DB notification channels and
    return (op_ret, data_ret, fvs) on success.

    On a multi-ASIC platform orchagent runs per-ASIC inside each asicN
    namespace with its own APPL_DB, so the query must target the right
    namespace's DB. `namespace` is '' for the default/single-ASIC DB.

    Raises RuntimeError on timeout or transport error.
    """
    db = swsscommon.DBConnector("APPL_DB", REDIS_TIMEOUT_MSECS, True, namespace)
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
        # Tolerate a trailing delimiter (e.g. "a|b|...|n|") from the daemon.
        parts = blob.rstrip("|").split("|")
        if len(parts) != 14:
            # Skip malformed rows rather than failing the whole table, but
            # surface it so a daemon/CLI version-format mismatch is visible
            # instead of producing a silently incomplete table.
            click.echo(f"Warning: skipping malformed stats for '{name}' "
                       f"({len(parts)} fields, expected 14)", err=True)
            continue
        try:
            count = int(parts[0])
            total_ns = int(parts[1])
            median_ns = int(parts[2])
            q1_ns = int(parts[3])
            q3_ns = int(parts[4])
            max_ns = int(parts[5])
            high_outliers = int(parts[6])
            low_outliers = int(parts[7])
            sched_count = int(parts[8])
            total_sched_ns = int(parts[9])
            sched_median_ns = int(parts[10])
            sched_q1_ns = int(parts[11])
            sched_q3_ns = int(parts[12])
            sched_max_ns = int(parts[13])
        except ValueError:
            click.echo(f"Warning: skipping stats with non-integer field "
                       f"for '{name}'", err=True)
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


def _render_table(rows, multi_asic_mode=False):
    # Sort: total_ns descending, ties broken by name ascending.
    rows = sorted(rows,
                  key=lambda r: (-r["total_ns"], r["name"]))

    table = []
    for r in rows:
        if r["count"] == 0:
            run_quartet = "-"
            total_run = "-"
        else:
            run_quartet = _fmt_quartet(r["median_ns"],
                                       r["q1_ns"],
                                       r["q3_ns"],
                                       r["max_ns"])
            total_run = f"{_ms(r['total_ns']):.2f}"

        if r["sched_count"] == 0:
            sched_quartet = "-"
            total_sched = "-"
        else:
            sched_quartet = _fmt_quartet(r["sched_median_ns"],
                                         r["sched_q1_ns"],
                                         r["sched_q3_ns"],
                                         r["sched_max_ns"])
            total_sched = f"{_ms(r['total_sched_ns']):.2f}"

        # TOTAL column shows "<run>/<sched>" so a viewer can see at a
        # glance how much wall-clock the loop spent inside the task vs
        # waiting before scheduling it.
        total_str = f"{total_run}/{total_sched}"

        outliers = r["high_outliers"] + r["low_outliers"]

        row = [
            r["name"],
            run_quartet,
            r["count"],
            outliers,
            sched_quartet,
            total_str,
        ]
        # On multi-ASIC, prepend the owning namespace so rows from different
        # ASICs are distinguishable in the aggregated table.
        if multi_asic_mode:
            row.insert(0, r.get("asic", ""))
        table.append(row)

    headers = [
        "TASK",
        "RUN TIME\nmedian/q1/q3/max\n(in msec)",
        "RUNS",
        "OUTLIERS",
        "SCHED LATENCY\nmedian/q1/q3/max\n(in msec)",
        "TOTAL\nrun/sched\n(in msec)",
    ]
    if multi_asic_mode:
        headers.insert(0, "ASIC")
    return tabulate(table, headers=headers, tablefmt="plain")


@click.group()
def orchagent():
    """Show orchagent runtime information"""
    pass


@orchagent.command("tasks")
@multi_asic_click_option_namespace
def tasks(namespace):
    """Show per-Executor execution timing in orchagent"""
    # get_namespace_list('' / None) -> [''] on single-ASIC, the per-ASIC
    # namespaces on multi-ASIC, and only the requested one when -n is given.
    # On a supervisor (fabric-only) it is empty, so this becomes a graceful
    # no-op instead of a blind timeout.
    namespaces = multi_asic.get_namespace_list(namespace)
    # Show the ASIC column on any multi-ASIC platform (including when a single
    # namespace is selected with -n) so the row's owning ASIC stays explicit;
    # single-ASIC boxes keep the original column set.
    multi_asic_mode = multi_asic.is_multi_asic()

    rows = []
    errors = []
    for ns in namespaces:
        try:
            _, _, fvs = _query_orchagent("show", ns)
        except RuntimeError as e:
            errors.append((ns, e))
            continue
        ns_rows = _parse_stats(fvs)
        for r in ns_rows:
            r["asic"] = ns
        rows.extend(ns_rows)

    # Print the table when we have data, or when there were no errors at all
    # (e.g. an empty reply or a no-op sup) so headers still render.
    if rows or not errors:
        click.echo(_render_table(rows, multi_asic_mode=multi_asic_mode))

    for ns, e in errors:
        click.echo(f"Error ({ns or 'default'}): {e}", err=True)
    if errors:
        sys.exit(1)
