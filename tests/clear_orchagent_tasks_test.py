"""
Unit tests for `sonic-clear orchagent tasks`.

Mocks the swsscommon NotificationProducer / NotificationConsumer / Select
to round-trip the request without needing Redis.
"""

from unittest import mock

import pytest
from click.testing import CliRunner

from clear import orchagent as clear_orchagent


@pytest.fixture
def fake_swsscommon():
    fake = mock.MagicMock()
    fake.Select.OBJECT = 0
    fake.Select.TIMEOUT = 1
    fake.Select.return_value.select.return_value = (fake.Select.OBJECT, None)

    fake.NotificationConsumer.return_value.pop.return_value = ("ok", "", [])
    fake.NotificationProducer.return_value.send.return_value = None
    fake.FieldValuePairs.side_effect = lambda x: x
    fake.DBConnector.return_value = mock.MagicMock()

    # Default to single-ASIC: one default namespace.
    with mock.patch.object(clear_orchagent, "swsscommon", fake), \
         mock.patch.object(clear_orchagent.multi_asic, "get_namespace_list",
                           return_value=['']), \
         mock.patch.object(clear_orchagent.multi_asic, "is_multi_asic",
                           return_value=False):
        yield fake


def test_clear_sends_clear_op_and_prints_ok(fake_swsscommon):
    runner = CliRunner()
    result = runner.invoke(clear_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output

    producer = fake_swsscommon.NotificationProducer.return_value
    assert producer.send.call_count == 1
    op_arg = producer.send.call_args[0][0]
    assert op_arg == "clear"


def test_clear_timeout_reports_error(fake_swsscommon):
    fake_swsscommon.Select.return_value.select.return_value = (
        fake_swsscommon.Select.TIMEOUT, None)

    runner = CliRunner()
    result = runner.invoke(clear_orchagent.orchagent, ["tasks"])
    assert result.exit_code != 0


def test_clear_orchagent_error_reply_reports_error(fake_swsscommon):
    fake_swsscommon.NotificationConsumer.return_value.pop.return_value = (
        "error", "unknown op", [])

    runner = CliRunner()
    result = runner.invoke(clear_orchagent.orchagent, ["tasks"])
    assert result.exit_code != 0


def test_clear_multi_asic_clears_each_namespace(fake_swsscommon):
    """On multi-ASIC, send a clear to each asicN namespace's orchagent."""
    with mock.patch.object(clear_orchagent.multi_asic, "get_namespace_list",
                           return_value=["asic0", "asic1"]), \
         mock.patch.object(clear_orchagent.multi_asic, "is_multi_asic",
                           return_value=True):
        runner = CliRunner()
        result = runner.invoke(clear_orchagent.orchagent, ["tasks"])
    assert result.exit_code == 0, result.output

    # One clear per namespace.
    producer = fake_swsscommon.NotificationProducer.return_value
    assert producer.send.call_count == 2
    assert all(c.args[0] == "clear" for c in producer.send.call_args_list)

    # DBConnector opened per-namespace.
    ns_args = [c.args[3] for c in fake_swsscommon.DBConnector.call_args_list
               if len(c.args) >= 4]
    assert "asic0" in ns_args and "asic1" in ns_args
    assert "asic0" in result.output and "asic1" in result.output
