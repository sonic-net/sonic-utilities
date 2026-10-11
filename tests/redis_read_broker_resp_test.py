import pytest

from redis_read_broker.resp import (
    FrameTooLarge,
    IncompleteFrame,
    InvalidFrame,
    RequestBuffer,
    RequestParser,
)


def command(*arguments):
    parts = [b"*%d\r\n" % len(arguments)]
    for argument in arguments:
        parts.extend((b"$%d\r\n" % len(argument), argument, b"\r\n"))
    return b"".join(parts)


def test_parses_one_flat_command_array():
    raw = b"*3\r\n$6\r\nSELECT\r\n+4\r\n$3\r\nkey\r\n"

    arguments, end = RequestParser(1024).parse(raw)

    assert arguments == (b"SELECT", b"4", b"key")
    assert end == len(raw)


def test_preserves_mixed_case_and_exact_raw_bytes():
    raw = command(b"hGeTaLl", b"FEATURE|bgp")
    buffer = RequestBuffer(1024)
    buffer.feed(raw)

    requests = buffer.pop_requests()

    assert len(requests) == 1
    assert requests[0].arguments == (b"hGeTaLl", b"FEATURE|bgp")
    assert requests[0].raw == raw


def test_handles_every_fragment_boundary():
    raw = command(b"HGETALL", b"FEATURE|bgp")

    for split in range(1, len(raw)):
        buffer = RequestBuffer(1024)
        buffer.feed(raw[:split])
        assert buffer.pop_requests() == []

        buffer.feed(raw[split:])
        requests = buffer.pop_requests()
        assert [request.arguments for request in requests] == [
            (b"HGETALL", b"FEATURE|bgp")]
        assert requests[0].raw == raw


def test_handles_one_byte_fragments():
    raw = command(b"EXISTS", b"FEATURE|bgp")
    buffer = RequestBuffer(1024)

    completed = []
    for byte in raw:
        buffer.feed(bytes((byte,)))
        completed.extend(buffer.pop_requests())

    assert [request.arguments for request in completed] == [
        (b"EXISTS", b"FEATURE|bgp")]
    assert completed[0].raw == raw


def test_returns_coalesced_commands_and_keeps_trailing_fragment():
    first = command(b"SELECT", b"4")
    second = command(b"KEYS", b"FEATURE|*")
    third = command(b"HGETALL", b"FEATURE|bgp")
    buffer = RequestBuffer(4096)
    buffer.feed(first + second + third[:-2])

    requests = buffer.pop_requests()

    assert [request.arguments for request in requests] == [
        (b"SELECT", b"4"),
        (b"KEYS", b"FEATURE|*"),
    ]
    assert [request.raw for request in requests] == [first, second]

    buffer.feed(third[-2:])
    requests = buffer.pop_requests()
    assert [request.arguments for request in requests] == [
        (b"HGETALL", b"FEATURE|bgp")]
    assert requests[0].raw == third


def test_does_not_parse_command_like_bytes_inside_a_bulk_argument():
    payload = b"prefix\r\n*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\nsuffix"
    raw = command(b"HGETALL", payload)
    buffer = RequestBuffer(4096)
    buffer.feed(raw)

    requests = buffer.pop_requests()

    assert len(requests) == 1
    assert requests[0].arguments == (b"HGETALL", payload)
    assert requests[0].raw == raw


@pytest.mark.parametrize("raw", [
    b"PING\r\n",
    b"+PING\r\n",
    b"*0\r\n",
    b"*-1\r\n",
    b"*1\r\n$-1\r\n",
    b"*1\r\n*1\r\n$4\r\nPING\r\n",
    b"*1\r\n:1\r\n",
    b"*1\r\n_\r\n",
    b"*1\r\n$4\r\nPINGxx",
])
def test_rejects_non_command_or_malformed_requests(raw):
    with pytest.raises(InvalidFrame):
        RequestParser(1024).parse(raw)


@pytest.mark.parametrize("raw", [
    b"",
    b"*",
    b"*1",
    b"*1\r\n",
    b"*1\r\n$4",
    b"*1\r\n$4\r\nPIN",
    b"*2\r\n$4\r\nPING\r\n",
])
def test_reports_incomplete_requests(raw):
    with pytest.raises(IncompleteFrame):
        RequestParser(1024).parse(raw)


def test_uses_one_generous_incomplete_request_size_bound():
    one_mib = 1024 * 1024
    payload = b"x" * (one_mib // 2)
    raw = command(b"HGETALL", payload)
    arguments, end = RequestParser(one_mib).parse(raw)

    assert arguments == (b"HGETALL", payload)
    assert end == len(raw)

    oversized_header = b"*1\r\n$%d\r\n" % (one_mib + 1)
    with pytest.raises(FrameTooLarge):
        RequestParser(one_mib).parse(oversized_header)


def test_request_buffer_rejects_an_oversized_incomplete_request():
    buffer = RequestBuffer(1024)
    buffer.feed(b"*2\r\n$4\r\nPING\r\n$999999\r\n" + b"x" * 1025)

    with pytest.raises(FrameTooLarge):
        buffer.pop_requests()


def test_closed_accepts_empty_buffer_and_rejects_partial_request():
    RequestBuffer(1024).closed()

    buffer = RequestBuffer(1024)
    buffer.feed(b"*1\r\n$4\r\nPIN")
    with pytest.raises(InvalidFrame):
        buffer.closed()
