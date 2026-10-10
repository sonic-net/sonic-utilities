import socket

import pytest

from redis_read_broker.resp import (
    ConnectionClosed,
    Frame,
    FrameTooLarge,
    IncompleteFrame,
    InvalidFrame,
    RESPParser,
    SocketReader,
    request_arguments,
)


def test_parses_scalar_frames():
    parser = RESPParser(1024)

    assert parser.parse(b"+OK\r\n").value == b"OK"
    assert parser.parse(b"-ERR no\r\n").value == b"ERR no"
    assert parser.parse(b":-12\r\n").value == -12
    assert parser.parse(b"#t\r\n").value is True
    assert parser.parse(b"#f\r\n").value is False
    assert parser.parse(b"_\r\n").value is None
    assert parser.parse(b",1.25\r\n").value == b"1.25"
    assert parser.parse(b"(123456\r\n").value == b"123456"


def test_parses_blob_and_aggregate_frames():
    parser = RESPParser(1024)

    assert parser.parse(b"$3\r\nfoo\r\n").value == b"foo"
    assert parser.parse(b"$-1\r\n").value is None
    assert parser.parse(b"!3\r\nERR\r\n").value == b"ERR"
    assert parser.parse(b"=7\r\ntxt:abc\r\n").value == b"txt:abc"
    array = parser.parse(b"*2\r\n$3\r\nGET\r\n+key\r\n")
    assert [child.value for child in array.children] == [b"GET", b"key"]
    mapping = parser.parse(b"%1\r\n+a\r\n:1\r\n")
    assert [child.value for child in mapping.children] == [b"a", 1]
    assert parser.parse(b"*-1\r\n").children is None


def test_parses_streamed_frames():
    parser = RESPParser(1024)

    blob = parser.parse(b"$?\r\n;3\r\nfoo\r\n;2\r\nba\r\n;0\r\n")
    assert blob.value == b"fooba"
    array = parser.parse(b"*?\r\n+one\r\n:2\r\n.\r\n")
    assert [child.value for child in array.children] == [b"one", 2]
    mapping = parser.parse(b"%?\r\n+k\r\n+v\r\n.\r\n")
    assert [child.value for child in mapping.children] == [b"k", b"v"]


@pytest.mark.parametrize("raw", [
    b"?bad\r\n",
    b"#x\r\n",
    b"_x\r\n",
    b":01\r\n",
    b":123456789012345678901\r\n",
    b"$-2\r\n",
    b"! -1\r\n",
    b"=3\r\nabc\r\n",
    b"$3\r\nfooXX",
    b"%?\r\n+key\r\n.\r\n",
    b"*?\r\nx\r\n",
    b"*?\r\n..\r\n",
])
def test_rejects_invalid_frames(raw):
    with pytest.raises(InvalidFrame):
        RESPParser(1024).parse(raw)


@pytest.mark.parametrize("raw", [
    b"+partial",
    b"$3\r\nfo",
    b"$?\r\n;3\r\nfo",
    b"*2\r\n+one\r\n",
    b"*?\r\n+one\r\n",
    b"*?\r\n.",
])
def test_reports_incomplete_frames(raw):
    with pytest.raises(IncompleteFrame):
        RESPParser(1024).parse(raw)


def test_enforces_parser_limits():
    with pytest.raises(FrameTooLarge):
        RESPParser(4).parse(b"+hello\r\n")
    with pytest.raises(FrameTooLarge):
        RESPParser(1024, max_line_bytes=3).parse(b"+hello")
    with pytest.raises(FrameTooLarge):
        RESPParser(1024, max_elements=1).parse(b"*2\r\n+a\r\n+b\r\n")
    with pytest.raises(FrameTooLarge):
        RESPParser(1024, max_depth=0).parse(b"*1\r\n+x\r\n")
    with pytest.raises(FrameTooLarge):
        RESPParser(8).parse(b"$9\r\n123456789\r\n")
    with pytest.raises(FrameTooLarge):
        RESPParser(12).parse(b"$?\r\n;9\r\n123456789\r\n;0\r\n")
    with pytest.raises(FrameTooLarge):
        RESPParser(1024, max_elements=1).parse(b"*?\r\n+a\r\n+b\r\n.\r\n")


class FakeSocket(object):
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def recv(self, _size):
        return self.chunks.pop(0)


def test_socket_reader_handles_partial_and_pipelined_frames():
    reader = SocketReader(128)
    sock = FakeSocket([b"+O", b"K\r\n+NEXT\r\n"])

    first = reader.read_frame(sock, 1)
    second = reader.try_frame()

    assert first.raw == b"+OK\r\n"
    assert second.raw == b"+NEXT\r\n"
    assert reader.try_frame() is None


def test_socket_reader_rejects_closed_and_oversized_inputs():
    with pytest.raises(ConnectionClosed):
        SocketReader(16).read_frame(FakeSocket([b""]), 1)
    with pytest.raises(InvalidFrame):
        SocketReader(16).read_frame(FakeSocket([b"+partial", b""]), 1)
    with pytest.raises(FrameTooLarge):
        SocketReader(4).read_frame(FakeSocket([b"+hello"]), 1)


def test_socket_reader_timeout(monkeypatch):
    values = iter((10.0, 11.1))
    monkeypatch.setattr("redis_read_broker.resp.time.monotonic", lambda: next(values))

    with pytest.raises(socket.timeout):
        SocketReader(16).read_frame(FakeSocket([]), 1)


def test_request_arguments_accepts_strings_and_rejects_other_values():
    frame = RESPParser(1024).parse(b"*3\r\n$3\r\nGET\r\n+key\r\n=7\r\ntxt:arg\r\n")
    assert request_arguments(frame) == (b"GET", b"key", b"txt:arg")

    with pytest.raises(InvalidFrame):
        request_arguments(Frame(b"+", value=b"PING"))
    with pytest.raises(InvalidFrame):
        request_arguments(Frame(b"*", children=()))
    with pytest.raises(FrameTooLarge):
        request_arguments(frame, max_arguments=2)
    with pytest.raises(InvalidFrame):
        request_arguments(Frame(b"*", children=(Frame(b":", value=1),)))
    with pytest.raises(InvalidFrame):
        request_arguments(Frame(b"*", children=(Frame(b"$", value=None),)))
