"""
Unit tests for `show orchagent tasks`.

The CLI talks to orchagent over two APPL_DB notification channels. We
mock the swsscommon NotificationProducer / NotificationConsumer / Select
so the test is self-contained — no Redis required.
"""

from unittest import mock

import pytest
from click.testing import CliRunner

from show import orchagent as show_orchagent


SAMPLE_REPLY_FVS = [
    # 14 pipe-separated fields:
    #   count | total_run_ns
    #   | median_run_ns | q1_run_ns | q3_run_ns | max_run_ns
    #   | high_outliers | low_outliers
    #   | sched_count | total_sched_ns
    #   | median_sched_ns | q1_sched_ns | q3_sched_ns | max_sched_ns
    #
    # RouteOrch dominates total runtime -> sorts first.
    # Run-time: median 1.80, Q1 0.90, Q3 3.20, max 47.00 ms.
    # Sched-latency: median 5, Q1 2, Q3 12, max 200 ms; total 40.495 s.
    ("RouteOrch",  "8100|18630000000|1800000|900000|3200000|47000000|42|3|"
                   "8099|40495000000|5000000|2000000|12000000|200000000"),
    ("PortsOrch",  "12450|3859500000|310000|180000|520000|4100000|7|0|"
                   "12449|37347000000|3000000|1500000|6000000|80000000"),
    ("logRotate",  "3|19200000|6400000|5900000|7100000|21000000|0|0|"
                   "2|20000000|10000000|9000000|11000000|15000000"),
    ("flush",      "3200|288000000|90000|60000|150000|410000|11|0|"
                   "3199|6398000000|2000000|1000000|4000000|50000000"),
    # Empty slot: orchagent emits zeros, CLI prints "-".
    ("NeverRan",   "0|0|0|0|0|0|0|0|0|0|0|0|0|0"),
]


@pytest.fixture
def fake_swsscommon():
    """Patch swsscommon used by show.orchagent so the producer/consumer
    are mocks. Returns the producer mock so tests can inspect what was
    sent.
    """
    fake = mock.MagicMock()

    # Select.OBJECT / TIMEOUT constants the CLI compares against.
    fake.Select.OBJECT = 0
    fake.Select.TIMEOUT = 1
    fake.Select.return_value.select.return_value = (fake.Select.OBJECT, None)

    consumer = fake.NotificationConsumer.return_value
    consumer.pop.return_value = ("ok", "", SAMPLE_REPLY_FVS)

    producer = fake.NotificationProducer.return_value
    producer.send.return_value = None

    fake.FieldValuePairs.side_effect = lambda x: x
    fake.DBConnector.return_value = mock.MagicMock()

    # Default to single-ASIC: one default namespace, no ASIC column.
    with mock.patch.object(show_orchagent, "swsscommon", fake), \
         mock.patch.object(show_orchagent.multi_asic, "get_namespace_list",
                           return_value=['']), \
         mock.patch.object(show_orchagent.multi_asic, "is_multi_asic",
                           return_value=False):
        yield fake


def test_tasks_renders_table_sorted_by_total(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0, result.output

    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    # Multi-line headers (3 rows) + 5 data rows.
    assert len(lines) >= 8
    # The combined header text appears across the first few lines.
    header_block = "\n".join(lines[:3])
    assert "TASK" in header_block
    assert "RUN TIME" in header_block
    assert "median/q1/q3/max" in header_block
    assert "RUNS" in header_block
    assert "OUTLIERS" in header_block
    assert "SCHED LATENCY" in header_block
    assert "TOTAL" in header_block

    # Rows are sorted by total_run_ns descending.
    body = lines[3:]
    order = []
    for name in ["RouteOrch", "PortsOrch", "flush", "logRotate", "NeverRan"]:
        for i, line in enumerate(body):
            if line.lstrip().split()[:1] == [name]:
                order.append((name, i))
                break
    assert len(order) == 5
    assert [n for n, _ in order] == [
        "RouteOrch", "PortsOrch", "flush", "logRotate", "NeverRan"
    ]


def test_tasks_formats_quartet_in_ms(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0

    # The new RUN TIME quartet replaces individual median/max/min columns.
    # RouteOrch: median 1.80, q1 0.90, q3 3.20, max 47.00 (all ms).
    assert "1.80/0.90/3.20/47000.00" not in result.output  # not millions
    assert "1.80/0.90/3.20/47.00" in result.output

    # PortsOrch sched: median 3.00, q1 1.50, q3 6.00, max 80.00 ms.
    assert "3.00/1.50/6.00/80.00" in result.output

    # The new format drops the per-cell "ms" suffix (the unit appears
    # only in the header sub-line "(in msec)").
    body_lines = [ln for ln in result.output.splitlines()
                  if ln and not ln.lstrip().startswith(("TASK", "median", "(in"))]
    for ln in body_lines:
        assert " ms" not in ln, f"unexpected 'ms' suffix in body row: {ln!r}"


def test_tasks_handles_zero_count_slot(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0

    # The empty NeverRan row should print "-" for the run quartet, the
    # sched quartet, and the total — but RUNS=0 and OUTLIERS=0 are real
    # integers, not dashes.
    never_lines = [ln for ln in result.output.splitlines()
                   if ln.lstrip().split()[:1] == ["NeverRan"]]
    assert len(never_lines) == 1
    cols = never_lines[0].split()
    # Expected: ['NeverRan', '-', '0', '0', '-', '-/-']
    assert cols[0] == "NeverRan"
    assert cols[1] == "-"           # run quartet
    assert cols[2] == "0"           # runs
    assert cols[3] == "0"           # outliers
    assert cols[4] == "-"           # sched quartet
    assert cols[5] == "-/-"         # total run/sched


def test_tasks_shows_outlier_counts(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0

    # RouteOrch had high=42, low=3 -> sum 45 in the new combined column.
    route_line = next(ln for ln in result.output.splitlines()
                      if ln.lstrip().split()[:1] == ["RouteOrch"])
    cols = route_line.split()
    # cols = [name, run_quartet, runs, outliers, sched_quartet, total]
    assert cols[2] == "8100", f"expected runs=8100 in {cols}"
    assert cols[3] == "45",   f"expected outliers=42+3=45 in {cols}"

    # PortsOrch: high=7 + low=0 = 7.
    ports_line = next(ln for ln in result.output.splitlines()
                      if ln.lstrip().split()[:1] == ["PortsOrch"])
    pcols = ports_line.split()
    assert pcols[2] == "12450"
    assert pcols[3] == "7"


def test_tasks_total_column_is_run_over_sched(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0

    # TOTAL column is "<total_run>/<total_sched>" in ms, two decimals.
    # RouteOrch: total_run = 18630 ms, total_sched = 40495 ms.
    route_line = next(ln for ln in result.output.splitlines()
                      if ln.lstrip().split()[:1] == ["RouteOrch"])
    cols = route_line.split()
    assert cols[5] == "18630.00/40495.00", f"unexpected total in {cols}"

    # PortsOrch: total_run = 3859.50, total_sched = 37347.00 ms.
    ports_line = next(ln for ln in result.output.splitlines()
                      if ln.lstrip().split()[:1] == ["PortsOrch"])
    pcols = ports_line.split()
    assert pcols[5] == "3859.50/37347.00"


def test_tasks_empty_reply_prints_only_headers(fake_swsscommon):
    fake_swsscommon.NotificationConsumer.return_value.pop.return_value = (
        "ok", "", [])

    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0
    # New format has a 3-line header (TASK row, sub-row "median/q1/q3/max",
    # unit row "(in msec)") and no data rows.
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert "TASK" in lines[0]
    assert "median/q1/q3/max" in lines[1]
    assert "(in msec)" in lines[2]


def test_tasks_timeout_reports_error(fake_swsscommon):
    fake_swsscommon.Select.return_value.select.return_value = (
        fake_swsscommon.Select.TIMEOUT, None)

    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code != 0
    assert "Timed out" in result.output or "Timed out" in (result.stderr or "")


def test_tasks_orchagent_error_reply_reports_error(fake_swsscommon):
    fake_swsscommon.NotificationConsumer.return_value.pop.return_value = (
        "error", "unknown op", [])

    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code != 0


def test_tasks_sends_show_op(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0

    producer = fake_swsscommon.NotificationProducer.return_value
    assert producer.send.call_count == 1
    op_arg = producer.send.call_args[0][0]
    assert op_arg == "show"


def test_tasks_multi_asic_iterates_namespaces(fake_swsscommon):
    """On multi-ASIC, query each asicN namespace's APPL_DB and render an
    aggregated table with an ASIC column."""
    with mock.patch.object(show_orchagent.multi_asic, "get_namespace_list",
                           return_value=["asic0", "asic1"]), \
         mock.patch.object(show_orchagent.multi_asic, "is_multi_asic",
                           return_value=True):
        runner = CliRunner()
        result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0, result.output

    # One query per namespace.
    producer = fake_swsscommon.NotificationProducer.return_value
    assert producer.send.call_count == 2

    # DBConnector opened per-namespace (4-arg form: name, timeout, wait, ns).
    ns_args = [c.args[3] for c in fake_swsscommon.DBConnector.call_args_list
               if len(c.args) >= 4]
    assert "asic0" in ns_args and "asic1" in ns_args

    # Aggregated table has an ASIC column populated for both namespaces.
    assert "ASIC" in result.output
    assert "asic0" in result.output
    assert "asic1" in result.output


def test_tasks_single_asic_has_no_asic_column(fake_swsscommon):
    """Single-ASIC output is unchanged (no ASIC column)."""
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0
    assert "ASIC" not in result.output


def test_tasks_multi_asic_single_namespace_keeps_asic_column(fake_swsscommon):
    """On a multi-ASIC platform, selecting one namespace with -n still shows
    the ASIC column so the owning ASIC stays explicit."""
    with mock.patch.object(show_orchagent.multi_asic, "get_namespace_list",
                           return_value=["asic0"]), \
         mock.patch.object(show_orchagent.multi_asic, "is_multi_asic",
                           return_value=True):
        runner = CliRunner()
        result = runner.invoke(show_orchagent.orchagent, ["tasks", "-n", "asic0"])
    assert result.exit_code == 0, result.output

    # Only the selected namespace is queried.
    producer = fake_swsscommon.NotificationProducer.return_value
    assert producer.send.call_count == 1

    # ASIC column is present and populated for the single namespace.
    assert "ASIC" in result.output
    assert "asic0" in result.output


def test_tasks_malformed_row_warns_and_skips(fake_swsscommon):
    """A row with the wrong field count is skipped with a stderr warning
    rather than silently dropped."""
    fake_swsscommon.NotificationConsumer.return_value.pop.return_value = (
        "ok", "", [("RouteOrch", "1|2|3")])  # only 3 fields

    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0
    assert "Warning" in result.output and "malformed" in result.output
    # RouteOrch skipped -> not a data row.
    assert not any(ln.lstrip().split()[:1] == ["RouteOrch"]
                   for ln in result.output.splitlines())
