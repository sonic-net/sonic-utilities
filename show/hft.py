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
DEFAULT_CELL_PLACEHOLDER = '-'
TABLE_HEADER = [
    'Profile',
    'Stream State',
    'Poll Interval (usec)',
    'Group Type',
    'Object Names',
    'Object Counters'
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

    rows = _build_rows(profile_table, group_table)
    if not rows:
        click.echo("No high frequency telemetry configuration present.")
        return

    click.echo(tabulate(rows, TABLE_HEADER, tablefmt='grid'))


def _build_rows(profile_table, group_table):
    group_index = _index_groups(group_table)
    rows = []

    for profile_name in natsorted(profile_table.keys()):
        profile_entry = profile_table.get(profile_name, {}) or {}
        stream_state = profile_entry.get('stream_state', DEFAULT_CELL_PLACEHOLDER)
        poll_interval_raw = profile_entry.get('poll_interval', DEFAULT_CELL_PLACEHOLDER)
        poll_interval = _format_poll_interval(poll_interval_raw)
        groups = group_index.get(profile_name)

        if not groups:
            rows.append([
                profile_name,
                stream_state,
                poll_interval,
                DEFAULT_CELL_PLACEHOLDER,
                DEFAULT_CELL_PLACEHOLDER,
                DEFAULT_CELL_PLACEHOLDER
            ])
            continue

        for idx, group in enumerate(groups):
            rows.append([
                profile_name if idx == 0 else '',
                stream_state if idx == 0 else '',
                poll_interval if idx == 0 else '',
                group['type'],
                group['names'],
                group['counters']
            ])

    return rows


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
