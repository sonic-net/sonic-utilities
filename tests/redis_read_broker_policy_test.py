import pytest

from redis_read_broker.policy import PolicyDenied, ReadPolicy


@pytest.fixture
def policy():
    return ReadPolicy((0, 4), max_scan_count=100)


@pytest.mark.parametrize(("arguments", "selected_db", "expected_db", "close"), [
    ((b"SELECT", b"4"), None, 4, False),
    ((b"PING",), None, None, False),
    ((b"PING", b"hello"), None, None, False),
    ((b"ECHO", b"hello"), None, None, False),
    ((b"QUIT",), None, None, True),
    ((b"HELLO",), None, None, False),
    ((b"HELLO", b"3", b"SETNAME", b"cli"), None, None, False),
    ((b"CLIENT", b"GETNAME"), None, None, False),
    ((b"CLIENT", b"SETNAME", b"cli"), None, None, False),
    ((b"CLIENT", b"SETINFO", b"LIB-NAME", b"swsscommon"), None, None, False),
    ((b"COMMAND",), None, None, False),
    ((b"COMMAND", b"COUNT"), None, None, False),
    ((b"COMMAND", b"INFO", b"HGETALL"), None, None, False),
    ((b"EXISTS", b"key"), 4, None, False),
    ((b"HGETALL", b"key"), 4, None, False),
    ((b"SCAN", b"0"), 4, None, False),
    ((b"SCAN", b"0", b"MATCH", b"FEATURE|*", b"COUNT", b"100"), 4, None, False),
    ((b"SCAN", b"0", b"TYPE", b"hash"), 4, None, False),
])
def test_allows_only_reviewed_commands(policy, arguments, selected_db,
                                       expected_db, close):
    decision = policy.authorize(arguments, selected_db)

    assert decision.command == arguments[0].decode().upper()
    assert decision.selected_db == expected_db
    assert decision.close_after_reply is close


@pytest.mark.parametrize("arguments", [
    (b"GET", b"key"),
    (b"SET", b"key", b"value"),
    (b"AUTH", b"secret"),
    (b"EVAL_RO", b"return 1", b"0"),
    (b"SELECT", b"3"),
    (b"SELECT", b"-1"),
    (b"SELECT", b"0004"),
    (b"SELECT",),
    (b"PING", b"one", b"two"),
    (b"ECHO",),
    (b"QUIT", b"now"),
    (b"HELLO", b"1"),
    (b"HELLO", b"3", b"AUTH", b"user", b"secret"),
    (b"HELLO", b"3", b"SETNAME"),
    (b"CLIENT",),
    (b"CLIENT", b"LIST"),
    (b"CLIENT", b"GETNAME", b"extra"),
    (b"CLIENT", b"SETINFO", b"bad", b"value"),
    (b"COMMAND", b"GETKEYS"),
    (b"COMMAND", b"INFO", b"bad name"),
    (b"EXISTS",),
    (b"EXISTS", b"one", b"two"),
    (b"SCAN", b"bad"),
    (b"SCAN", b"0", b"COUNT", b"0"),
    (b"SCAN", b"0", b"COUNT", b"101"),
    (b"SCAN", b"0", b"MATCH"),
    (b"SCAN", b"0", b"MATCH", b"*", b"MATCH", b"x"),
    (b"SCAN", b"0", b"UNKNOWN", b"x"),
])
def test_denies_writes_unknown_commands_and_invalid_arguments(policy, arguments):
    with pytest.raises(PolicyDenied) as error:
        policy.authorize(arguments, 4)

    assert error.value.command in (arguments[0].decode().upper(), "UNKNOWN")


@pytest.mark.parametrize("command", [
    b"",
    b"1PING",
    b"bad name",
    b"x" * 65,
    b"\xff",
])
def test_denies_invalid_command_names(policy, command):
    with pytest.raises(PolicyDenied):
        policy.authorize((command,), 4)


def test_requires_database_selection_for_data_reads(policy):
    with pytest.raises(PolicyDenied) as error:
        policy.authorize((b"HGETALL", b"key"), None)

    assert error.value.command == "HGETALL"


def test_batch_applies_select_before_read(policy):
    decisions = policy.authorize_batch([
        (b"SELECT", b"4"),
        (b"HGETALL", b"FEATURE|bgp"),
        (b"QUIT",),
    ], None)

    assert [decision.command for decision in decisions] == [
        "SELECT", "HGETALL", "QUIT"]


def test_batch_rejects_commands_after_quit(policy):
    with pytest.raises(PolicyDenied) as error:
        policy.authorize_batch([(b"QUIT",), (b"PING",)], None)

    assert error.value.command == "QUIT"
