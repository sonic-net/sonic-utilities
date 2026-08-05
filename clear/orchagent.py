import click
import sys

from swsscommon import swsscommon

from sonic_py_common import multi_asic
from utilities_common.multi_asic import multi_asic_click_option_namespace


TASK_STATS_QUERY_CHANNEL = "ORCH_TASK_STATS_QUERY"
TASK_STATS_REPLY_CHANNEL = "ORCH_TASK_STATS_REPLY"
REPLY_TIMEOUT_MS = 10000
# DBConnector connection timeout (0 = library default); the reply wait is
# governed separately by REPLY_TIMEOUT_MS on the Select below.
REDIS_TIMEOUT_MSECS = 0


def _send_clear(namespace):
    # orchagent runs per-ASIC on multi-ASIC platforms, so target the right
    # namespace's APPL_DB ('' for the default/single-ASIC DB).
    db = swsscommon.DBConnector("APPL_DB", REDIS_TIMEOUT_MSECS, True, namespace)
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
@multi_asic_click_option_namespace
def tasks(namespace):
    """Reset per-Executor execution timing counters in orchagent"""
    # Clear each ASIC's orchagent (or just the requested/default one). On a
    # single-ASIC box get_namespace_list('' / None) -> [''] and this is a
    # single clear; on a fabric-only supervisor the list is empty (no-op).
    namespaces = multi_asic.get_namespace_list(namespace)
    label = multi_asic.is_multi_asic()

    errors = []
    for ns in namespaces:
        try:
            _send_clear(ns)
        except RuntimeError as e:
            errors.append((ns, e))
            continue
        click.echo(f"OK ({ns})" if label else "OK")

    for ns, e in errors:
        click.echo(f"Error ({ns or 'default'}): {e}", err=True)
    if errors:
        sys.exit(1)
