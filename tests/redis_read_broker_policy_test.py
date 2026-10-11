import pytest

from redis_read_broker.policy import PolicyDenied, ReadPolicy


@pytest.fixture
def policy():
    return ReadPolicy()


def test_allowlist_contains_only_the_pilot_commands():
    assert ReadPolicy.CONNECTION_COMMANDS == frozenset(("SELECT", "PING"))
    assert ReadPolicy.READ_COMMANDS == frozenset((
        "EXISTS", "HGETALL", "KEYS"))


@pytest.mark.parametrize(("arguments", "expected"), [
    ((b"SELECT", b"4"), "SELECT"),
    ((b"ping",), "PING"),
    ((b"ExIsTs", b"FEATURE|bgp"), "EXISTS"),
    ((b"hgetall", b"FEATURE|bgp"), "HGETALL"),
    ((b"KeYs", b"FEATURE|*"), "KEYS"),
])
def test_allows_only_reviewed_command_names(policy, arguments, expected):
    assert policy.authorize(arguments) == expected


@pytest.mark.parametrize("arguments", [
    (b"SET", b"key", b"value"),
    (b"HSET", b"key", b"field", b"value"),
    (b"DEL", b"key"),
    (b"EVAL", b"return 1", b"0"),
    (b"EVAL_RO", b"return 1", b"0"),
    (b"AUTH", b"secret"),
    (b"CONFIG", b"GET", b"*"),
    (b"SCAN", b"0"),
    (b"GET", b"key"),
    (b"CLIENT", b"LIST"),
    (b"COMMAND",),
    (b"UNKNOWN",),
])
def test_denies_writes_and_every_other_command(policy, arguments):
    with pytest.raises(PolicyDenied) as error:
        policy.authorize(arguments)

    assert error.value.command == arguments[0].decode("ascii").upper()


@pytest.mark.parametrize("command", [
    b"",
    b"1PING",
    b"bad name",
    b"PING!",
    b"x" * 65,
    b"\xff",
])
def test_denies_malformed_command_names(policy, command):
    with pytest.raises(PolicyDenied) as error:
        policy.authorize((command,))

    assert error.value.command == "UNKNOWN"


def test_denies_missing_command_name(policy):
    with pytest.raises(PolicyDenied) as error:
        policy.authorize(())

    assert error.value.command == "UNKNOWN"


def test_leaves_argument_validation_to_redis(policy):
    assert policy.authorize((b"PING", b"one", b"two")) == "PING"
    assert policy.authorize((b"SELECT", b"not-a-number")) == "SELECT"
