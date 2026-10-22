"""
show alarms -- CLI for SONiC alarm display (Event & Alarm Framework).

Reads eventd's ALARM table from EVENT_DB (logical Redis DB 19) and presents the
active alarms in a formatted table.  eventd's Event Consumer (the eventdb
service) is the sole writer of the ALARM / ALARM_STATS tables; this command is
a read-only view (HLD 9.1).  No dependency on alarmd or any alarm library --
it reads Redis directly.

EVENT_DB (and the ALARM table) exist only when the image is built with
include_system_eventd == "y".  When EVENT_DB is absent, the command reports
that the Event & Alarm Framework is not enabled.

Usage examples:
    show alarms                          # all active alarms
    show alarms -s critical              # filter by severity
    show alarms -i PSU_MISSING           # filter by alarm id (type-id)
    show alarms -r "PSU 2"               # filter by resource (object)
    show alarms -a false                 # only unacknowledged alarms
    show alarms -g severity              # group by severity
    show alarms --json                   # JSON output
    show alarms --summary                # counts only
"""

import click
import json as json_module
from tabulate import tabulate

# eventd table names (in EVENT_DB).  Keys follow the SONiC "TABLE|key"
# convention, e.g. "ALARM|<sequence-id>".
ALARM_TABLE = 'ALARM'

# eventd stores severities in uppercase.
_SEV_ORDER = {'CRITICAL': 0, 'MAJOR': 1, 'MINOR': 2, 'WARNING': 3,
              'INFORMATIONAL': 4}

_FRAMEWORK_DISABLED_MSG = (
    "Event & Alarm Framework is not enabled on this image "
    "(EVENT_DB not present; built without include_system_eventd). "
    "No alarm data to display."
)


# ---------------------------------------------------------------------------
# EVENT_DB reader -- standalone, no imports from sonic_alarm
# ---------------------------------------------------------------------------
def _get_event_db():
    """Return a SonicV2Connector connected to EVENT_DB, or None when the
    Event & Alarm Framework (EVENT_DB / logical Redis DB 19) is not present."""
    try:
        from swsscommon.swsscommon import SonicV2Connector
        db = SonicV2Connector()
        if not hasattr(db, 'EVENT_DB'):
            return None
        db.connect(db.EVENT_DB)
        return db
    except Exception:
        return None


def _read_alarms():
    """Read all ALARM rows from eventd's ALARM table (EVENT_DB).

    Returns a list of alarm dicts, or None when the Event & Alarm Framework
    (EVENT_DB) is not present.  Each alarm is the raw eventd row, with the
    Redis sequence-id exposed as 'sequence-id' when not already a field.
    """
    db = _get_event_db()
    if db is None:
        return None
    try:
        keys = db.keys(db.EVENT_DB, '{}|*'.format(ALARM_TABLE)) or []
        alarms = []
        for key in sorted(keys):
            entry = db.get_all(db.EVENT_DB, key)
            if not entry:
                continue
            entry = dict(entry)
            # Redis key is "ALARM|<sequence-id>"; expose the seq id.
            seq = key.split('|', 1)[1] if '|' in key else key
            entry.setdefault('sequence-id', seq)
            alarms.append(entry)
        return alarms
    except Exception as exc:
        click.echo(f"Error reading alarms: {exc}", err=True)
        return []


# ---------------------------------------------------------------------------
# Field accessors (eventd ALARM schema)
# ---------------------------------------------------------------------------
def _alarm_id(a):
    # type-id is alarmd's alarm_id (eventd's alarm-type identity).
    return a.get('type-id') or a.get('type_id') or a.get('id', '')


def _sequence_id(a):
    return a.get('sequence-id') or a.get('sequence_id') or ''


def _severity(a):
    return (a.get('severity') or '').upper()


def _resource(a):
    return a.get('resource', '')


def _text(a):
    return a.get('text', '')


def _acknowledged(a):
    return str(a.get('acknowledged', 'false')).lower() in ('true', '1', 'yes')


def _severity_sort_key(a):
    return _SEV_ORDER.get(_severity(a), 99)


def _format_time(a):
    """Format eventd's time-created (UTC nanoseconds) to a readable string."""
    raw = a.get('time-created') or a.get('time_created') or ''
    if not raw:
        return ''
    try:
        from datetime import datetime, timezone
        secs = int(raw) / 1e9
        return datetime.fromtimestamp(secs, tz=timezone.utc).strftime(
            '%Y-%m-%d %H:%M:%S.%f')[:-3]
    except (ValueError, TypeError, OSError):
        return str(raw)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_table(alarms):
    """Render alarms as a tabulate table, sorted by severity."""
    if not alarms:
        click.echo("No active alarms.")
        return

    headers = ['Seq', 'Severity', 'Alarm ID', 'Resource', 'Description',
               'Ack', 'Time']
    rows = []
    for a in sorted(alarms, key=_severity_sort_key):
        rows.append([
            _sequence_id(a),
            _severity(a),
            _alarm_id(a),
            _resource(a),
            _text(a),
            'true' if _acknowledged(a) else 'false',
            _format_time(a),
        ])
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
    click.echo(f"\nTotal: {len(alarms)} active alarm(s)")


def _format_json(alarms):
    """Render alarms as JSON (raw ALARM rows)."""
    click.echo(json_module.dumps(alarms, indent=2))


def _format_summary(alarms):
    """Render a severity-count summary.

    Counts are derived from the ALARM rows (equivalent to eventd's ALARM_STATS
    counters) so the summary honours any active filters.
    """
    counts = {}
    for a in alarms:
        sev = _severity(a) or 'UNKNOWN'
        counts[sev] = counts.get(sev, 0) + 1
    ack = sum(1 for a in alarms if _acknowledged(a))

    click.echo("Alarm Summary")
    click.echo("-" * 30)
    for sev in ['CRITICAL', 'MAJOR', 'MINOR', 'WARNING']:
        click.echo(f"  {sev.capitalize():14s}: {counts.get(sev, 0)}")
    click.echo(f"  {'Acknowledged':14s}: {ack}")
    click.echo(f"  {'Total':14s}: {len(alarms)}")


def _format_grouped(alarms, group_by):
    """Render alarms grouped by a field (severity / id / resource)."""
    accessor = {
        'severity': _severity,
        'id': _alarm_id,
        'resource': _resource,
    }[group_by]

    groups = {}
    for a in alarms:
        groups.setdefault(accessor(a) or 'Unknown', []).append(a)

    for group_name in sorted(groups.keys()):
        click.echo(f"\n=== {group_by}: {group_name} "
                   f"({len(groups[group_name])}) ===")
        _format_table(groups[group_name])


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------
@click.command('alarms')
@click.option('-s', '--severity', default=None,
              help='Filter by severity (Critical, Major, Minor, Warning)')
@click.option('-i', '--id', 'alarm_id', default=None,
              help='Filter by alarm id (type-id, e.g. PSU_MISSING)')
@click.option('-r', '--resource', default=None,
              help='Filter by resource / object (e.g. "PSU 2")')
@click.option('-a', '--acknowledged', default=None,
              type=click.Choice(['true', 'false'], case_sensitive=False),
              help='Show only acknowledged / unacknowledged alarms')
@click.option('-g', '--group-by', default=None,
              type=click.Choice(['severity', 'id', 'resource'],
                                case_sensitive=False),
              help='Group output by field')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.option('--summary', is_flag=True, help='Show counts only')
def alarms(severity, alarm_id, resource, acknowledged, group_by, as_json,
           summary):
    """Display active system alarms (from the Event & Alarm Framework)."""
    all_alarms = _read_alarms()
    if all_alarms is None:
        click.echo(_FRAMEWORK_DISABLED_MSG)
        return

    # Apply filters (AND together)
    filtered = all_alarms
    if severity:
        filtered = [a for a in filtered if _severity(a) == severity.upper()]
    if alarm_id:
        filtered = [a for a in filtered
                    if _alarm_id(a).lower() == alarm_id.lower()]
    if resource:
        filtered = [a for a in filtered
                    if _resource(a).lower() == resource.lower()]
    if acknowledged is not None:
        want = acknowledged.lower() == 'true'
        filtered = [a for a in filtered if _acknowledged(a) == want]

    # Render
    if summary:
        _format_summary(filtered)
    elif as_json:
        _format_json(filtered)
    elif group_by:
        _format_grouped(filtered, group_by.lower())
    else:
        _format_table(filtered)
