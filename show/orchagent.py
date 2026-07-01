import click
import utilities_common.cli as clicommon
from tabulate import tabulate


ORCHAGENT_QUEUE_TABLE = "ORCHAGENT_QUEUE"


@click.group(cls=clicommon.AliasedGroup)
def orchagent():
    """Show orchagent state."""
    pass


@orchagent.command()
@click.option('--all', 'show_all', is_flag=True, default=False,
              help='Show all consumers including those with zero pending tasks.')
@clicommon.pass_db
def queue(db, show_all):
    """Show per-consumer pending task counts in orchagent's m_toSync queues.

    Each row is one Redis-table consumer registered with an orchagent Orch.
    A non-zero pending_count indicates either dependency-driven retries
    (e.g., RIF not ready yet) or SAI-level retries (sync mode).

    By default, consumers with zero pending tasks are hidden. Use --all to
    show every consumer."""
    state_db = db.db
    keys = state_db.keys(state_db.STATE_DB, f"{ORCHAGENT_QUEUE_TABLE}|*") or []

    rows = []
    for key in keys:
        entry = state_db.get_all(state_db.STATE_DB, key) or {}

        # Prefer the orch/consumer fields written by orchagent. Fall back to
        # parsing the key as ORCHAGENT_QUEUE|<Orch>|<consumer> if the row was
        # written by a build that did not include those fields.
        orch_name = entry.get("orch")
        consumer_name = entry.get("consumer")
        if not orch_name or not consumer_name:
            parts = key.split("|", 2)
            if len(parts) == 3:
                _, orch_name, consumer_name = parts
            elif len(parts) == 2:
                # Legacy single-segment key written by older orchagent.
                _, consumer_name = parts
                orch_name = "-"
            else:
                continue

        try:
            pending = int(entry.get("pending_count", "0"))
        except (TypeError, ValueError):
            pending = 0

        if pending == 0 and not show_all:
            continue

        rows.append([orch_name, consumer_name, pending])

    if not rows:
        if show_all:
            click.echo("No orchagent queue entries found in STATE_DB. "
                       "Is orchagent running and does this build include the "
                       "queue-depth telemetry change?")
        else:
            click.echo("No consumers with pending tasks. "
                       "Use --all to see all consumers.")
        return

    # Sort by pending_count descending so the most-loaded consumers are at the
    # top, then by (orch, consumer) ascending for a deterministic tiebreak.
    rows.sort(key=lambda r: (-r[2], r[0], r[1]))

    header = ["Orch", "Consumer", "Pending Count"]
    click.echo(tabulate(rows, header, tablefmt="simple"))
