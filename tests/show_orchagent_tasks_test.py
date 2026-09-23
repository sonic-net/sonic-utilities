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
    # Header height is derived rather than hardcoded: the tallest header cell
    # decides how many rows tabulate emits, so it changes whenever a header
    # gains or loses a sub-line. Everything from the first recognised task
    # name onward is the body.
    task_names = ["RouteOrch", "PortsOrch", "flush", "logRotate", "NeverRan"]
    first_data = next(i for i, ln in enumerate(lines)
                      if ln.lstrip().split()[0] in task_names)
    header_block = "\n".join(lines[:first_data])
    body = lines[first_data:]

    assert len(body) == len(task_names)
    assert "TASK" in header_block
    assert "RUN TIME" in header_block
    assert "median/q1/q3/max" in header_block
    assert "RUNS" in header_block
    assert "OUTLIERS" in header_block
    assert "SCHED LATENCY" in header_block
    assert "TOTAL" in header_block

    # Rows are sorted by total_run_ns descending.
    order = []
    for name in task_names:
        for i, line in enumerate(body):
            if line.lstrip().split()[:1] == [name]:
                order.append((name, i))
                break
    assert len(order) == len(task_names)
    assert [n for n, _ in order] == task_names


def test_tasks_formats_quartet_autoscaled(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0

    # Each value carries its own unit, so a quartet spanning sub-millisecond
    # and tens-of-milliseconds stays legible. RouteOrch run time: median
    # 1.8 ms, q1 900 us, q3 3.2 ms, max 47 ms.
    assert "1.80ms/900us/3.20ms/47.0ms" in result.output

    # PortsOrch run time is entirely sub-millisecond -- under the old fixed-ms
    # format median/q1/q3 rendered as 0.00 and the column was unreadable.
    assert "310us/180us/520us/4.10ms" in result.output
    assert "0.00/0.00/0.00" not in result.output

    # PortsOrch sched latency: median 3 ms, q1 1.5 ms, q3 6 ms, max 80 ms.
    assert "3.00ms/1.50ms/6.00ms/80.0ms" in result.output


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

    # TOTAL column is "<total_run>/<total_sched>", each auto-scaled.
    # RouteOrch: total_run = 18.63 s, total_sched = 40.495 s.
    route_line = next(ln for ln in result.output.splitlines()
                      if ln.lstrip().split()[:1] == ["RouteOrch"])
    cols = route_line.split()
    assert cols[5] == "18.6s/40.5s", f"unexpected total in {cols}"

    # PortsOrch: total_run = 3.8595 s, total_sched = 37.347 s.
    ports_line = next(ln for ln in result.output.splitlines()
                      if ln.lstrip().split()[:1] == ["PortsOrch"])
    pcols = ports_line.split()
    assert pcols[5] == "3.86s/37.3s"


def test_tasks_empty_reply_prints_only_headers(fake_swsscommon):
    fake_swsscommon.NotificationConsumer.return_value.pop.return_value = (
        "ok", "", [])

    runner = CliRunner()
    result = runner.invoke(show_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0
    # Two header rows (the TASK row and the "median/q1/q3/max" sub-row) and no
    # data rows. There is no unit row: units travel with each value now, so
    # the header carries no "(in msec)" line.
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "TASK" in lines[0]
    assert "median/q1/q3/max" in lines[1]
    assert "(in msec)" not in result.output


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


# ---------------------------------------------------------------------------
# _fmt_duration: unit selection and 3-significant-figure rendering.
#
# Boundaries are pinned on both sides because the ladder is a tuple scan --
# a refactor to log10 would be liable to drift at exactly 1000 ns / 1 s.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ns,expected", [
    # Zero is distinct from "-", which callers use for "no samples yet".
    (0,                       "0ns"),
    # ns tier renders as an integer -- source resolution is already 1 ns.
    (1,                       "1ns"),
    (850,                     "850ns"),
    (999,                     "999ns"),
    # us tier
    (1_000,                   "1.00us"),
    (3_100,                   "3.10us"),
    (510_000,                 "510us"),
    # 3-sig-fig rounding at the top of a tier legitimately yields four
    # digits rather than rolling over to the next unit.
    (999_999,                 "1000us"),
    # ms tier
    (1_000_000,               "1.00ms"),
    (8_420_000,               "8.42ms"),
    (95_200_000,              "95.2ms"),
    # s tier
    (1_000_000_000,           "1.00s"),
    (45_200_000_000,          "45.2s"),
    # Rounding-before-rollover at the s->m boundary: 59.95s rounds to the
    # display value "60.0s" but stays in the s tier (below the 60 B ns
    # threshold) -- it does NOT become "1.00m".
    (59_950_000_000,          "60.0s"),
    # Same behavior one tier down (ms->s): 999.5ms renders "1000ms".
    (999_500_000,             "1000ms"),
    # m / h / d tiers exist so the TOTAL column stays readable: total_sched_ns
    # accumulates over daemon uptime.
    (60_000_000_000,          "1.00m"),
    (3_600_000_000_000,       "1.00h"),
    (86_400_000_000_000,      "1.00d"),
    (2_592_000_000_000_000,   "30.0d"),   # ~1 second/poll on a 30-day uptime
])
def test_fmt_duration_scales_and_labels(ns, expected):
    assert show_orchagent._fmt_duration(ns) == expected


def test_fmt_duration_negative_treated_as_zero():
    # The daemon sends unsigned counters, but a version/format mismatch
    # should not raise or emit a nonsense unit.
    assert show_orchagent._fmt_duration(-1) == "0ns"


def test_fmt_quartet_joins_four_autoscaled_values():
    assert show_orchagent._fmt_quartet(1_800_000, 900_000,
                                       3_200_000, 47_000_000) == \
        "1.80ms/900us/3.20ms/47.0ms"
