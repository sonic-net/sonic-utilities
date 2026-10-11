"""Small positive allowlist for the Redis read broker."""

import re


class PolicyDenied(Exception):
    """A complete request is not one of the reviewed read commands."""

    def __init__(self, command="UNKNOWN"):
        super(PolicyDenied, self).__init__("request denied")
        self.command = command


_COMMAND_NAME = re.compile(br"[A-Za-z][A-Za-z0-9_-]*\Z")


class ReadPolicy(object):
    """Allow only commands required by the reviewed display-client inventory."""

    CONNECTION_COMMANDS = frozenset(("SELECT", "PING"))
    READ_COMMANDS = frozenset(("EXISTS", "GET", "HGET", "HGETALL", "KEYS"))

    @staticmethod
    def command_name(arguments):
        if not arguments:
            raise PolicyDenied()
        raw = arguments[0]
        if len(raw) > 64 or not _COMMAND_NAME.match(raw):
            raise PolicyDenied()
        try:
            return raw.decode("ascii").upper()
        except UnicodeDecodeError:
            raise PolicyDenied()

    def authorize(self, arguments):
        command = self.command_name(arguments)
        if command not in self.CONNECTION_COMMANDS and command not in self.READ_COMMANDS:
            raise PolicyDenied(command)
        return command
