import click
import sys

from swsscommon import swsscommon


TASK_STATS_QUERY_CHANNEL = "ORCH_TASK_STATS_QUERY"
TASK_STATS_REPLY_CHANNEL = "ORCH_TASK_STATS_REPLY"
REPLY_TIMEOUT_MS = 10000


def _send_clear():
    db = swsscommon.DBConnector("APPL_DB", 0)
    producer = swsscommon.NotificationProducer(db, TASK_STATS_QUERY_CHANNEL)
    consumer = swsscommon.NotificationConsumer(db, TASK_STATS_REPLY_CHANNEL)

    sel = swsscommon.Select()
    sel.addSelectable(consumer)

    producer.send("clear", "", swsscommon.FieldValuePairs([]))

    state, _ = sel.select(REPLY_TIMEOUT_MS)
    if state == swsscommon.Select.TIMEOUT:
        raise RuntimeError(
            f"Timed out after {REPLY_TIMEOUT_MS} ms waiting for orchagent reply")
    if state != swsscommon.Select.OBJECT:
        raise RuntimeError(f"Select error waiting for orchagent reply: {state}")

    op_ret, data_ret, _ = consumer.pop()
    if op_ret != "ok":
        raise RuntimeError(
            f"orchagent returned error: op={op_ret} data={data_ret}")


@click.group()
def orchagent():
    """Clear orchagent runtime stats"""
    pass


@orchagent.command("tasks")
def tasks():
    """Reset per-Executor execution timing counters in orchagent"""
    try:
        _send_clear()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo("OK")
