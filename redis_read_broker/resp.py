"""Bounded RESP2 and RESP3 frame parsing.

The broker forwards the original bytes after parsing them.  Keeping framing
here, instead of asking Redis to classify a partly read request, prevents a
denied command from being hidden behind an allowed command in one pipeline.
"""

import re
import select
import socket
import time


class RESPError(Exception):
    """Base class for safe, caller-independent protocol errors."""


class IncompleteFrame(RESPError):
    """More bytes are required to complete a frame."""


class InvalidFrame(RESPError):
    """The bytes do not form a valid RESP frame."""


class FrameTooLarge(RESPError):
    """A configured frame or parser limit was exceeded."""


class ConnectionClosed(RESPError):
    """The peer closed the connection."""


class Frame(object):
    __slots__ = ("kind", "value", "children", "end")

    def __init__(self, kind, value=None, children=None, end=0):
        self.kind = kind
        self.value = value
        self.children = children
        self.end = end


class ParsedFrame(object):
    __slots__ = ("frame", "raw")

    def __init__(self, frame, raw):
        self.frame = frame
        self.raw = raw


_INTEGER = re.compile(br"-?(?:0|[1-9][0-9]*)\Z")


class RESPParser(object):
    """Parse one complete RESP frame from a byte buffer."""

    STRING_KINDS = frozenset((b"+", b"-", b"(", b","))
    BULK_KINDS = frozenset((b"$", b"!", b"="))
    AGGREGATE_KINDS = frozenset((b"*", b"%", b"~", b">", b"|"))

    def __init__(self, max_frame_bytes, max_depth=16,
                 max_elements=262144, max_line_bytes=65536):
        self.max_frame_bytes = max_frame_bytes
        self.max_depth = max_depth
        self.max_elements = max_elements
        self.max_line_bytes = max_line_bytes

    def parse(self, data, start=0):
        frame = self._parse_at(data, start, 0)
        if frame.end - start > self.max_frame_bytes:
            raise FrameTooLarge("frame exceeds byte limit")
        return frame

    def _line(self, data, start):
        end = data.find(b"\r\n", start)
        if end < 0:
            if len(data) - start > self.max_line_bytes:
                raise FrameTooLarge("RESP line exceeds byte limit")
            raise IncompleteFrame()
        if end - start > self.max_line_bytes:
            raise FrameTooLarge("RESP line exceeds byte limit")
        value = bytes(data[start:end])
        if b"\r" in value or b"\n" in value:
            raise InvalidFrame("RESP line contains a line break")
        return value, end + 2

    @staticmethod
    def _number(value, description):
        if len(value) > 20 or not _INTEGER.match(value):
            raise InvalidFrame("invalid {}".format(description))
        try:
            return int(value)
        except (ValueError, OverflowError):
            raise InvalidFrame("invalid {}".format(description))

    def _parse_at(self, data, start, depth):
        if depth > self.max_depth:
            raise FrameTooLarge("RESP nesting exceeds limit")
        if start >= len(data):
            raise IncompleteFrame()
        if len(data) - start > self.max_frame_bytes:
            # A complete frame may still end before the buffered pipeline, so
            # only reject after parsing.  The socket reader bounds the buffer.
            pass

        prefix = bytes(data[start:start + 1])
        cursor = start + 1

        if prefix in self.STRING_KINDS:
            value, cursor = self._line(data, cursor)
            return Frame(prefix, value=value, end=cursor)

        if prefix == b":":
            value, cursor = self._line(data, cursor)
            number = self._number(value, "integer")
            return Frame(prefix, value=number, end=cursor)

        if prefix == b"#":
            value, cursor = self._line(data, cursor)
            if value not in (b"t", b"f"):
                raise InvalidFrame("invalid boolean")
            return Frame(prefix, value=value == b"t", end=cursor)

        if prefix == b"_":
            value, cursor = self._line(data, cursor)
            if value:
                raise InvalidFrame("invalid null")
            return Frame(prefix, value=None, end=cursor)

        if prefix in self.BULK_KINDS:
            length_value, cursor = self._line(data, cursor)
            if length_value == b"?":
                if prefix != b"$":
                    raise InvalidFrame("only blob strings may be streamed")
                return self._streamed_blob(data, cursor, start)

            length = self._number(length_value, "blob length")
            if length == -1:
                if prefix != b"$":
                    raise InvalidFrame("invalid null blob")
                return Frame(prefix, value=None, end=cursor)
            if length < 0:
                raise InvalidFrame("invalid blob length")
            if length > self.max_frame_bytes:
                raise FrameTooLarge("blob exceeds byte limit")
            end = cursor + length
            if end + 2 > len(data):
                raise IncompleteFrame()
            if bytes(data[end:end + 2]) != b"\r\n":
                raise InvalidFrame("blob is missing terminator")
            value = bytes(data[cursor:end])
            if prefix == b"=" and (len(value) < 4 or value[3:4] != b":"):
                raise InvalidFrame("invalid verbatim string")
            return Frame(prefix, value=value, end=end + 2)

        if prefix in self.AGGREGATE_KINDS:
            count_value, cursor = self._line(data, cursor)
            if count_value == b"?":
                return self._streamed_aggregate(
                    data, cursor, start, depth, prefix)

            count = self._number(count_value, "aggregate length")
            if count == -1:
                return Frame(prefix, children=None, end=cursor)
            if count < 0:
                raise InvalidFrame("invalid aggregate length")
            item_count = count * 2 if prefix in (b"%", b"|") else count
            if item_count > self.max_elements:
                raise FrameTooLarge("aggregate exceeds element limit")
            children = []
            for _ in range(item_count):
                child = self._parse_at(data, cursor, depth + 1)
                children.append(child)
                cursor = child.end
                if cursor - start > self.max_frame_bytes:
                    raise FrameTooLarge("frame exceeds byte limit")
            return Frame(prefix, children=tuple(children), end=cursor)

        raise InvalidFrame("unsupported RESP type")

    def _streamed_blob(self, data, cursor, start):
        chunks = []
        total = 0
        while True:
            if cursor >= len(data):
                raise IncompleteFrame()
            if bytes(data[cursor:cursor + 1]) != b";":
                raise InvalidFrame("invalid streamed blob chunk")
            length_value, cursor = self._line(data, cursor + 1)
            length = self._number(length_value, "chunk length")
            if length < 0:
                raise InvalidFrame("invalid chunk length")
            if length == 0:
                return Frame(b"$", value=b"".join(chunks), end=cursor)
            total += length
            if total > self.max_frame_bytes:
                raise FrameTooLarge("streamed blob exceeds byte limit")
            end = cursor + length
            if end + 2 > len(data):
                raise IncompleteFrame()
            if bytes(data[end:end + 2]) != b"\r\n":
                raise InvalidFrame("chunk is missing terminator")
            chunks.append(bytes(data[cursor:end]))
            cursor = end + 2
            if cursor - start > self.max_frame_bytes:
                raise FrameTooLarge("frame exceeds byte limit")

    def _streamed_aggregate(self, data, cursor, start, depth, prefix):
        children = []
        while True:
            if cursor >= len(data):
                raise IncompleteFrame()
            if bytes(data[cursor:cursor + 1]) == b".":
                if cursor + 3 > len(data):
                    raise IncompleteFrame()
                if bytes(data[cursor:cursor + 3]) != b".\r\n":
                    raise InvalidFrame("invalid streamed aggregate terminator")
                cursor += 3
                if prefix in (b"%", b"|") and len(children) % 2:
                    raise InvalidFrame("map has an odd element count")
                return Frame(prefix, children=tuple(children), end=cursor)
            if len(children) >= self.max_elements:
                raise FrameTooLarge("aggregate exceeds element limit")
            child = self._parse_at(data, cursor, depth + 1)
            children.append(child)
            cursor = child.end
            if cursor - start > self.max_frame_bytes:
                raise FrameTooLarge("frame exceeds byte limit")


class SocketReader(object):
    """Read complete frames while preserving unread pipeline bytes."""

    def __init__(self, max_buffer_bytes, max_frame_bytes=None):
        self.max_buffer_bytes = max_buffer_bytes
        self.parser = RESPParser(max_frame_bytes or max_buffer_bytes)
        self.buffer = bytearray()

    def try_frame(self):
        if not self.buffer:
            return None
        try:
            frame = self.parser.parse(self.buffer)
        except IncompleteFrame:
            return None
        raw = bytes(self.buffer[:frame.end])
        del self.buffer[:frame.end]
        return ParsedFrame(frame, raw)

    def read_frame(self, sock, timeout):
        deadline = time.monotonic() + timeout
        while True:
            parsed = self.try_frame()
            if parsed is not None:
                return parsed
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout()
            sock.settimeout(remaining)
            chunk = sock.recv(65536)
            if not chunk:
                if self.buffer:
                    raise InvalidFrame("connection ended inside a frame")
                raise ConnectionClosed()
            self.buffer.extend(chunk)
            if len(self.buffer) > self.max_buffer_bytes:
                raise FrameTooLarge("buffer exceeds byte limit")

    @staticmethod
    def is_readable(sock):
        readable, _, _ = select.select([sock], [], [], 0)
        return bool(readable)


def request_arguments(frame, max_arguments=1024):
    """Return byte arguments from a valid command request array."""

    if frame.kind != b"*" or frame.children is None:
        raise InvalidFrame("request must be a non-null array")
    if not frame.children:
        raise InvalidFrame("request array is empty")
    if len(frame.children) > max_arguments:
        raise FrameTooLarge("request has too many arguments")

    arguments = []
    for child in frame.children:
        if child.kind not in (b"$", b"+", b"=") or child.value is None:
            raise InvalidFrame("request arguments must be strings")
        arguments.append(child.value)
    return tuple(arguments)
