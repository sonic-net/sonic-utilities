"""Parse only the Redis request form needed to block write commands.

Redis command requests are flat arrays of strings. The broker parses those
arrays before forwarding them, but it never parses or buffers Redis replies.
"""

import re


class RESPError(Exception):
    """Base class for request protocol errors."""


class IncompleteFrame(RESPError):
    """More bytes are required to complete a request."""


class InvalidFrame(RESPError):
    """The bytes do not form a flat Redis command request."""


class FrameTooLarge(RESPError):
    """One request exceeds the parser memory bound."""


class ParsedRequest(object):
    __slots__ = ("arguments", "raw")

    def __init__(self, arguments, raw):
        self.arguments = arguments
        self.raw = raw


_UNSIGNED = re.compile(br"(?:0|[1-9][0-9]*)\Z")


class RequestParser(object):
    """Parse one flat RESP command array without parsing Redis responses."""

    def __init__(self, max_request_bytes, max_line_bytes=65536):
        self.max_request_bytes = max_request_bytes
        self.max_line_bytes = max_line_bytes

    def _line(self, data, start, request_start):
        end = data.find(b"\r\n", start)
        if end < 0:
            if len(data) - request_start > self.max_request_bytes:
                raise FrameTooLarge("request exceeds byte limit")
            if len(data) - start > self.max_line_bytes:
                raise FrameTooLarge("request line exceeds byte limit")
            raise IncompleteFrame()
        if end - start > self.max_line_bytes:
            raise FrameTooLarge("request line exceeds byte limit")
        value = bytes(data[start:end])
        if b"\r" in value or b"\n" in value:
            raise InvalidFrame("request line contains a line break")
        return value, end + 2

    @staticmethod
    def _unsigned(value, description):
        if len(value) > 20 or not _UNSIGNED.match(value):
            raise InvalidFrame("invalid {}".format(description))
        try:
            return int(value)
        except (ValueError, OverflowError):
            raise InvalidFrame("invalid {}".format(description))

    def parse(self, data, start=0):
        if start >= len(data):
            raise IncompleteFrame()
        if bytes(data[start:start + 1]) != b"*":
            raise InvalidFrame("request must be a Redis command array")

        count_value, cursor = self._line(data, start + 1, start)
        count = self._unsigned(count_value, "argument count")
        if count < 1:
            raise InvalidFrame("request array is empty")

        if count > self.max_request_bytes // 4:
            raise FrameTooLarge("request has too many arguments")

        arguments = []
        for _ in range(count):
            if cursor >= len(data):
                raise IncompleteFrame()
            prefix = bytes(data[cursor:cursor + 1])
            cursor += 1

            if prefix == b"+":
                value, cursor = self._line(data, cursor, start)
            elif prefix == b"$":
                length_value, cursor = self._line(data, cursor, start)
                length = self._unsigned(length_value, "argument length")
                if length > self.max_request_bytes:
                    raise FrameTooLarge("request argument exceeds byte limit")
                end = cursor + length
                if end + 2 > len(data):
                    if len(data) - start > self.max_request_bytes:
                        raise FrameTooLarge("request exceeds byte limit")
                    raise IncompleteFrame()
                if bytes(data[end:end + 2]) != b"\r\n":
                    raise InvalidFrame("request argument is missing terminator")
                value = bytes(data[cursor:end])
                cursor = end + 2
            else:
                raise InvalidFrame("request arguments must be strings")

            if cursor - start > self.max_request_bytes:
                raise FrameTooLarge("request exceeds byte limit")
            arguments.append(value)

        return tuple(arguments), cursor


class RequestBuffer(object):
    """Collect fragmented requests and return every complete command."""

    def __init__(self, max_request_bytes):
        self.max_request_bytes = max_request_bytes
        self.parser = RequestParser(max_request_bytes)
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)

    def pop_requests(self):
        requests = []
        cursor = 0
        while cursor < len(self.buffer):
            try:
                arguments, end = self.parser.parse(self.buffer, cursor)
            except IncompleteFrame:
                break
            requests.append(ParsedRequest(
                arguments, bytes(self.buffer[cursor:end])))
            cursor = end

        if cursor:
            del self.buffer[:cursor]
        if len(self.buffer) > self.max_request_bytes:
            raise FrameTooLarge("request exceeds byte limit")
        return requests

    def closed(self):
        if self.buffer:
            raise InvalidFrame("connection ended inside a request")
