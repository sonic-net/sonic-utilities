"""Connection-local allowlist for the Redis read broker."""

import re


class PolicyDenied(Exception):
    """A complete, valid request is outside the broker policy."""

    def __init__(self, command="UNKNOWN"):
        super(PolicyDenied, self).__init__("request denied")
        self.command = command


class Decision(object):
    __slots__ = ("command", "selected_db", "close_after_reply")

    def __init__(self, command, selected_db=None, close_after_reply=False):
        self.command = command
        self.selected_db = selected_db
        self.close_after_reply = close_after_reply


_COMMAND_NAME = re.compile(br"[A-Za-z][A-Za-z0-9_-]*\Z")
_UNSIGNED = re.compile(br"(?:0|[1-9][0-9]*)\Z")


class ReadPolicy(object):
    """Allow setup plus commands that cannot change Redis state.

    Unknown commands are denied.  The explicit dangerous set makes the
    intended transaction, scripting, publication, and administration
    boundary visible during review; it does not replace the allowlist.
    """

    ALWAYS_DENIED = frozenset((
        "ACL", "AUTH", "BGREWRITEAOF", "BGSAVE", "CONFIG", "DEBUG",
        "DISCARD", "EVAL", "EVALSHA", "EVAL_RO", "EXEC", "FCALL",
        "FCALL_RO", "FLUSHALL", "FLUSHDB", "FUNCTION", "MEMORY",
        "MIGRATE", "MODULE", "MONITOR", "MULTI", "PUBLISH", "PUBSUB",
        "PSUBSCRIBE", "PUNSUBSCRIBE", "REPLICAOF", "RESTORE", "SAVE",
        "SCRIPT", "SHUTDOWN", "SLAVEOF", "SUBSCRIBE", "SUNSUBSCRIBE",
        "SYNC", "UNSUBSCRIBE", "WATCH",
    ))

    # command: (minimum argument count after command, maximum or None)
    READ_COMMANDS = {
        # The first clients use only these commands.  Additions require a
        # caller inventory and their own resource-bound review.
        "EXISTS": (1, 1),
        "HGETALL": (1, 1),
    }

    SCAN_COMMANDS = frozenset(("SCAN",))

    def __init__(self, allowed_db_ids, max_scan_count=10000):
        self.allowed_db_ids = frozenset(allowed_db_ids)
        self.max_scan_count = max_scan_count

    @staticmethod
    def command_name(arguments):
        raw = arguments[0]
        if len(raw) > 64 or not _COMMAND_NAME.match(raw):
            raise PolicyDenied()
        try:
            return raw.decode("ascii").upper()
        except UnicodeDecodeError:
            raise PolicyDenied()

    def authorize_batch(self, request_arguments, selected_db):
        decisions = []
        planned_db = selected_db
        for index, arguments in enumerate(request_arguments):
            decision = self.authorize(arguments, planned_db)
            if decision.selected_db is not None:
                planned_db = decision.selected_db
            if decision.close_after_reply and index != len(request_arguments) - 1:
                raise PolicyDenied(decision.command)
            decisions.append(decision)
        return decisions

    def authorize(self, arguments, selected_db):
        command = self.command_name(arguments)
        args = arguments[1:]

        if command in self.ALWAYS_DENIED:
            raise PolicyDenied(command)

        if command == "SELECT":
            if (len(args) != 1 or len(args[0]) > 10 or
                    not _UNSIGNED.match(args[0])):
                raise PolicyDenied(command)
            db_id = int(args[0])
            if db_id not in self.allowed_db_ids:
                raise PolicyDenied(command)
            return Decision(command, selected_db=db_id)

        if command == "PING":
            if len(args) > 1:
                raise PolicyDenied(command)
            return Decision(command)

        if command == "ECHO":
            if len(args) != 1:
                raise PolicyDenied(command)
            return Decision(command)

        if command == "QUIT":
            if args:
                raise PolicyDenied(command)
            return Decision(command, close_after_reply=True)

        if command == "HELLO":
            self._authorize_hello(args, command)
            return Decision(command)

        if command == "CLIENT":
            self._authorize_client(args, command)
            return Decision(command)

        if command == "COMMAND":
            self._authorize_command_introspection(args, command)
            return Decision(command)

        if selected_db is None:
            raise PolicyDenied(command)

        if command in self.SCAN_COMMANDS:
            self._authorize_scan(command, args)
            return Decision(command)

        limits = self.READ_COMMANDS.get(command)
        if limits is None:
            raise PolicyDenied(command)
        minimum, maximum = limits
        if len(args) < minimum or (maximum is not None and len(args) > maximum):
            raise PolicyDenied(command)
        return Decision(command)

    @staticmethod
    def _authorize_hello(args, command):
        if not args:
            return
        if args[0] not in (b"2", b"3"):
            raise PolicyDenied(command)
        cursor = 1
        while cursor < len(args):
            option = args[cursor].upper()
            if option != b"SETNAME" or cursor + 1 >= len(args):
                # AUTH is deliberately excluded even when a client combines
                # it with HELLO.
                raise PolicyDenied(command)
            if len(args[cursor + 1]) > 128:
                raise PolicyDenied(command)
            cursor += 2

    @staticmethod
    def _authorize_client(args, command):
        if not args:
            raise PolicyDenied(command)
        subcommand = args[0].upper()
        if subcommand in (b"GETNAME", b"ID", b"INFO") and len(args) == 1:
            return
        if subcommand == b"SETNAME" and len(args) == 2 and len(args[1]) <= 128:
            return
        if (subcommand == b"SETINFO" and len(args) == 3 and
                args[1].upper() in (b"LIB-NAME", b"LIB-VER") and
                len(args[2]) <= 128):
            return
        raise PolicyDenied(command)

    @staticmethod
    def _authorize_command_introspection(args, command):
        if not args:
            return
        subcommand = args[0].upper()
        if subcommand == b"COUNT" and len(args) == 1:
            return
        if subcommand in (b"INFO", b"DOCS") and 1 < len(args) <= 65:
            for name in args[1:]:
                if len(name) > 64 or not _COMMAND_NAME.match(name):
                    raise PolicyDenied(command)
            return
        raise PolicyDenied(command)

    def _authorize_scan(self, command, args):
        minimum = 1 if command == "SCAN" else 2
        if (len(args) < minimum or len(args[minimum - 1]) > 20 or
                not _UNSIGNED.match(args[minimum - 1])):
            raise PolicyDenied(command)
        cursor = minimum
        seen = set()
        while cursor < len(args):
            option = args[cursor].upper()
            if option in seen or cursor + 1 >= len(args):
                raise PolicyDenied(command)
            seen.add(option)
            value = args[cursor + 1]
            if option == b"COUNT":
                if len(value) > 10 or not _UNSIGNED.match(value):
                    raise PolicyDenied(command)
                count = int(value)
                if count < 1 or count > self.max_scan_count:
                    raise PolicyDenied(command)
            elif option == b"MATCH":
                pass
            elif option == b"TYPE" and command == "SCAN":
                pass
            else:
                raise PolicyDenied(command)
            cursor += 2
