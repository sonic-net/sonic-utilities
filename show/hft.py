import json
import signal
import subprocess
import sys

import click
from natsort import natsorted
from tabulate import tabulate

import utilities_common.cli as clicommon

PROFILE_TABLE = 'HIGH_FREQUENCY_TELEMETRY_PROFILE'
GROUP_TABLE = 'HIGH_FREQUENCY_TELEMETRY_GROUP'
AGGREGATOR_TABLE = 'HIGH_FREQUENCY_TELEMETRY_AGGREGATOR'
AGGREGATOR_HISTOGRAM_TABLE = 'HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_HISTOGRAM'
AGGREGATOR_ROLLOVER_TABLE = 'HIGH_FREQUENCY_TELEMETRY_AGGREGATOR_ROLLOVER'
DEFAULT_ROLLOVER_BIT_WIDTH = 32
DEFAULT_CELL_PLACEHOLDER = '-'
TABLE_HEADER = [
    'Profile',
    'Stream State',
    'Poll Interval (usec)',
    'Aggregator',
    'Group Type',
    'Object Names',
    'Object Counters',
    'Reporting Rate (usec)',
    'Rollover Counters',
    'Rollover Bit Widths',
    'Heatmap Interval (usec)',
    'Heatmap Counters',
    'Per-counter Explicit Bounds'
]


@click.group(name='hft', cls=clicommon.AliasedGroup, invoke_without_command=True)
@clicommon.pass_db
@click.pass_context
def hft(ctx, db):
    """Show high frequency telemetry configuration."""
    if ctx.invoked_subcommand is None:
        _display_hft(db)


@hft.command('configuration', short_help="Show high frequency telemetry configuration")
@clicommon.pass_db
def hft_configuration(db):
    """Display all configured HFT profiles and groups."""
    _display_hft(db)


@hft.command('counters', short_help="Continuously monitor HFT counters (Ctrl+C to stop)")
@click.option('-i', '--stats-interval', default=10, show_default=True,
              type=click.IntRange(min=1), help='Stats reporting interval in seconds.')
@click.option('-m', '--max-stats-per-report', default=0, show_default=True,
              type=click.IntRange(min=0), help='Maximum counters per report (0 for unlimited).')
@click.option('-l', '--log-level', default='warn', show_default=True,
              type=click.Choice(['trace', 'debug', 'info', 'warn', 'error']),
              help='Logging level for countersyncd output (matches Rust log levels).')
@click.option('--log-format', default='simple', show_default=True,
              type=click.Choice(['simple', 'full']),
              help='Logging output format.')
def hft_counters(stats_interval, max_stats_per_report, log_level, log_format):
    """Tail countersyncd output for live HFT statistics until interrupted."""
    cmd = [
        'docker', 'exec', '-i', '-t', 'swss',
        'countersyncd',
        '--enable-stats',
        '--stats-interval', str(stats_interval),
        '--max-stats-per-report', str(max_stats_per_report),
        '--log-level', log_level,
        '--log-format', log_format,
    ]
    _execute_streaming_command(cmd)


def _display_hft(db):
    profile_table = db.cfgdb.get_table(PROFILE_TABLE) or {}
    group_table = db.cfgdb.get_table(GROUP_TABLE) or {}
    aggregator_table = db.cfgdb.get_table(AGGREGATOR_TABLE) or {}
    histogram_table = db.cfgdb.get_table(AGGREGATOR_HISTOGRAM_TABLE) or {}
    rollover_table = db.cfgdb.get_table(AGGREGATOR_ROLLOVER_TABLE) or {}

    rows = _build_rows(
        profile_table,
        group_table,
        aggregator_table,
        histogram_table,
        rollover_table
    )
    if not rows:
        click.echo("No high frequency telemetry configuration present.")
        return

    click.echo(tabulate(rows, TABLE_HEADER, tablefmt='grid'))


def _build_rows(profile_table, group_table, aggregator_table=None, histogram_table=None,
                rollover_table=None):
    group_index = _index_groups(group_table)
    aggregator_table = aggregator_table or {}
    histogram_index = _index_histograms(histogram_table or {})
    rollover_index = _index_rollovers(rollover_table or {})
    used_aggregators = set()
    rows = []

    for profile_name in natsorted(profile_table.keys()):
        profile_entry = profile_table.get(profile_name, {}) or {}
        stream_state = profile_entry.get('stream_state', DEFAULT_CELL_PLACEHOLDER)
        poll_interval_raw = profile_entry.get('poll_interval', DEFAULT_CELL_PLACEHOLDER)
        poll_interval = _format_poll_interval(poll_interval_raw)
        aggregator_name = profile_entry.get('aggregator')
        aggregator_display = aggregator_name or DEFAULT_CELL_PLACEHOLDER
        if aggregator_name is not None:
            used_aggregators.add(aggregator_name)
        aggregator = aggregator_table.get(aggregator_name, {}) if aggregator_name is not None else {}
        aggregator_fields = _format_aggregator(
            aggregator,
            histogram_index.get(aggregator_name, []),
            rollover_index.get(aggregator_name, {})
        )
        reporting_rate, rollover_counters, rollover_bit_widths, heatmap_interval, \
            heatmap_counters, explicit_bounds = aggregator_fields
        groups = group_index.get(profile_name)

        if not groups:
            rows.append([
                profile_name,
                stream_state,
                poll_interval,
                aggregator_display,
                DEFAULT_CELL_PLACEHOLDER,
                DEFAULT_CELL_PLACEHOLDER,
                DEFAULT_CELL_PLACEHOLDER,
                reporting_rate,
                rollover_counters,
                rollover_bit_widths,
                heatmap_interval,
                heatmap_counters,
                explicit_bounds
            ])
            continue

        for idx, group in enumerate(groups):
            rows.append([
                profile_name if idx == 0 else '',
                stream_state if idx == 0 else '',
                poll_interval if idx == 0 else '',
                aggregator_display if idx == 0 else '',
                group['type'],
                group['names'],
                group['counters'],
                reporting_rate if idx == 0 else '',
                rollover_counters if idx == 0 else '',
                rollover_bit_widths if idx == 0 else '',
                heatmap_interval if idx == 0 else '',
                heatmap_counters if idx == 0 else '',
                explicit_bounds if idx == 0 else ''
            ])

    for aggregator_name in natsorted(set(aggregator_table.keys()) - used_aggregators):
        aggregator_fields = _format_aggregator(
            aggregator_table.get(aggregator_name, {}),
            histogram_index.get(aggregator_name, []),
            rollover_index.get(aggregator_name, {})
        )
        reporting_rate, rollover_counters, rollover_bit_widths, heatmap_interval, \
            heatmap_counters, explicit_bounds = aggregator_fields
        rows.append([
            DEFAULT_CELL_PLACEHOLDER,
            DEFAULT_CELL_PLACEHOLDER,
            DEFAULT_CELL_PLACEHOLDER,
            aggregator_name,
            DEFAULT_CELL_PLACEHOLDER,
            DEFAULT_CELL_PLACEHOLDER,
            DEFAULT_CELL_PLACEHOLDER,
            reporting_rate,
            rollover_counters,
            rollover_bit_widths,
            heatmap_interval,
            heatmap_counters,
            explicit_bounds
        ])

    return rows


def _format_aggregator(aggregator, histograms=None, rollover_overrides=None):
    reporting_rate = _format_poll_interval(aggregator.get('reporting_rate', DEFAULT_CELL_PLACEHOLDER))
    rollover_selectors = _ensure_list(aggregator.get('rollover_counters'))
    rollover_counters = '\n'.join(rollover_selectors) or DEFAULT_CELL_PLACEHOLDER
    rollover_overrides = rollover_overrides or {}
    rollover_bit_widths = '\n'.join(
        '{}: {}'.format(
            selector,
            rollover_overrides.get(selector, '{} (default)'.format(DEFAULT_ROLLOVER_BIT_WIDTH))
        )
        for selector in rollover_selectors
    ) or DEFAULT_CELL_PLACEHOLDER
    heatmap_interval = _format_poll_interval(
        aggregator.get('heatmap_interval', DEFAULT_CELL_PLACEHOLDER)
    )
    heatmap_counters = _format_list(aggregator.get('heatmap_counters')) or DEFAULT_CELL_PLACEHOLDER
    explicit_bounds = '\n'.join(histograms or []) or DEFAULT_CELL_PLACEHOLDER
    return (
        reporting_rate,
        rollover_counters,
        rollover_bit_widths,
        heatmap_interval,
        heatmap_counters,
        explicit_bounds
    )


def _index_histograms(histogram_table):
    index = {}
    for composite_key, attributes in histogram_table.items():
        aggregator_name, group_type, counter_name = _split_histogram_key(composite_key)
        if not aggregator_name or not group_type or not counter_name:
            continue

        bounds = ','.join(_ensure_list((attributes or {}).get('explicit_bounds')))
        if not bounds:
            continue
        index.setdefault(aggregator_name, []).append(
            '{}|{}: {}'.format(group_type, counter_name, bounds)
        )

    for histograms in index.values():
        histograms.sort()
    return index


def _index_rollovers(rollover_table):
    index = {}
    for composite_key, attributes in rollover_table.items():
        aggregator_name, group_type, counter_name = _split_counter_child_key(composite_key)
        if not aggregator_name or not group_type or not counter_name:
            continue
        if not isinstance(attributes, dict) or attributes.get('bit_width') is None:
            continue

        selector = '{}|{}'.format(group_type, counter_name)
        index.setdefault(aggregator_name, {})[selector] = str(attributes['bit_width'])
    return index


def _index_groups(group_table):
    index = {}
    for composite_key, attributes in group_table.items():
        profile_name, group_type = _split_group_key(composite_key)
        if not profile_name or not group_type:
            continue

        names = _format_list(attributes.get('object_names'))
        counters = _format_list(attributes.get('object_counters'))
        entry = {
            'type': group_type,
            'names': names or DEFAULT_CELL_PLACEHOLDER,
            'counters': counters or DEFAULT_CELL_PLACEHOLDER
        }
        index.setdefault(profile_name, []).append(entry)

    for groups in index.values():
        groups.sort(key=lambda item: item['type'])
    return index


def _split_group_key(key):
    if not key:
        return None, None

    if isinstance(key, (tuple, list)) and len(key) == 2:
        return key[0], key[1]

    if isinstance(key, str):
        parts = key.split('|', 1)
        if len(parts) == 2:
            return parts[0], parts[1]

    return None, None


def _split_histogram_key(key):
    return _split_counter_child_key(key)


def _split_counter_child_key(key):
    if not key:
        return None, None, None

    if isinstance(key, (tuple, list)) and len(key) == 3:
        return key[0], key[1], key[2]

    if isinstance(key, str):
        parts = key.split('|')
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]

    return None, None, None


def _format_list(value):
    items = _ensure_list(value)
    if not items:
        return ''
    return '\n'.join(items)


def _format_poll_interval(value):
    if value is None or value == DEFAULT_CELL_PLACEHOLDER:
        return DEFAULT_CELL_PLACEHOLDER

    try:
        integer_value = int(str(value), 10)
        return f"{integer_value:,}"
    except (ValueError, TypeError):
        return str(value)


def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith('['):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if str(item).strip()]
            except (ValueError, TypeError):
                pass
        return [item for item in [segment.strip() for segment in value.split(',')] if item]
    return [str(value)]


def _execute_streaming_command(cmd):
    proc = subprocess.Popen(cmd, stdout=None, stderr=None)
    try:
        returncode = proc.wait()
    except KeyboardInterrupt:
        try:
            proc.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass
        returncode = proc.wait()

    if returncode in (0, 130, -signal.SIGINT):
        click.echo()
        return

    sys.exit(returncode)
