#
# lib.py
#
# Helper code for CLI for interacting with switches via console device
#

import json
import os
import pwd
import pexpect
import re
import socket
import struct
import subprocess
import sys
import time


import click
from sonic_py_common import device_info
from sonic_py_common.general import getstatusoutput_noshell_pipe

ERR_DISABLE = 1
ERR_CMD = 2
ERR_DEV = 3
ERR_CFG = 4
ERR_BUSY = 5

CONSOLE_PORT_TABLE = "CONSOLE_PORT"
CONSOLE_SWITCH_TABLE = "CONSOLE_SWITCH"

LINE_KEY = "LINE"
CUR_STATE_KEY = "CUR_STATE"

# CONFIG_DB Keys
BAUD_KEY = "baud_rate"
DEVICE_KEY = "remote_device"
FLOW_KEY = "flow_control"
FEATURE_KEY = "console_mgmt"
FEATURE_ENABLED_KEY = "enabled"
DEFAULT_FEATURE_ESCAPE_KEY = "default_escape_char"
FEATURE_ESCAPE_KEY = "escape_char"

# STATE_DB Keys
STATE_KEY = "state"
PID_KEY = "pid"
START_TIME_KEY = "start_time"
OPER_STATE_KEY = "oper_state"
LAST_STATE_CHANGE_KEY = "last_state_change"

BUSY_FLAG = "busy"
IDLE_FLAG = "idle"

# picocom Constants
PICOCOM_READY = "Terminal ready"
PICOCOM_BUSY = "Resource temporarily unavailable"

# mirror Constants
MIRROR_RUNTIME_DIR = "/run/console-monitor/mirror"
MIRROR_CONTROL_MAX_MESSAGE = 1024 * 1024
MIRROR_ARCHIVE_RESPONSE_TIMEOUT_SEC = 600
MIRROR_DIRECTIONS = ("rx", "tx", "both")
MIRROR_DURATION_SUFFIXES = ("s", "m", "h", "d")

UDEV_PREFIX_CONF_FILENAME = "udevprefix.conf"

PTY_SYMLINK_SUFFIX = "-PTS"

TIMEOUT_SEC = 0.2

CONSOLE_SESSION_SCRIPT = r"""
set -u

LINE_NUM="${1:?missing line_num}"
ESCAPE_DISPLAY="${2:?missing escape_display}"
PICOCOM_CMD="${3:?missing picocom_cmd}"

SAVED_STTY=""
if [ -r /dev/tty ]; then
    SAVED_STTY=$(stty -g < /dev/tty 2>/dev/null || true)
fi

console_state_set() {
    local ln="$1" st="$2" pid="${3:-}" start="${4:-}"
    local key="CONSOLE_PORT|${ln}"
    sonic-db-cli STATE_DB hset "$key" state "$st" > /dev/null 2>&1 || true
    sonic-db-cli STATE_DB hset "$key" pid "$pid" > /dev/null 2>&1 || true
    sonic-db-cli STATE_DB hset "$key" start_time "$start" > /dev/null 2>&1 || true
}

restore_tty() {
    if [ -w /dev/tty ]; then
        if [ -n "$SAVED_STTY" ]; then
            stty "$SAVED_STTY" < /dev/tty 2>/dev/null || stty sane < /dev/tty 2>/dev/null || true
        else
            stty sane < /dev/tty 2>/dev/null || true
        fi
    fi
}

picocom_pid=""

forward_signal() {
    if [ -n "$picocom_pid" ]; then
        kill -TERM "$picocom_pid" > /dev/null 2>&1 || true
    fi
}

cleanup() {
    if [ -n "$picocom_pid" ]; then
        wait "$picocom_pid" 2>/dev/null || true
    fi
    console_state_set "$LINE_NUM" idle "" ""
    restore_tty
}

trap cleanup EXIT
trap forward_signal HUP INT TERM

printf 'Successful connection to line [%s]\nPress ^%s ^X to disconnect\n' "$LINE_NUM" "$ESCAPE_DISPLAY"
bash -c "$PICOCOM_CMD" < /dev/tty > /dev/tty 2>&1 &
picocom_pid=$!
console_state_set "$LINE_NUM" busy "$picocom_pid" "$(ps -p "$picocom_pid" -o lstart= | sed 's/^ *//')"
wait "$picocom_pid"
rc=$?
restore_tty
printf '\nTerminating...\nThanks for using picocom\n'
exit "$rc"
"""

class ConsolePortProvider(object):
    """
    The console ports' provider.
    The provider can let user to get console ports information.
    """

    def __init__(self, db, configured_only, refresh=False):
        self._db = db
        self._db_utils = DbUtils(db)
        self._configured_only = configured_only
        self._ports = []
        self._init_all(refresh)

    def get_all(self):
        """Gets all console ports information"""
        for port in self._ports:
            yield ConsolePortInfo(self._db_utils, port, self._default_escape_char)

    def get(self, target, use_device=False):
        """Gets information of a ports, the target is the line number by default"""
        # figure out the search key
        search_key = LINE_KEY
        if use_device:
            search_key = DEVICE_KEY

        # identify the line number by searching configuration
        for port in self._ports:
            if search_key in port and port[search_key] == target:
                return ConsolePortInfo(self._db_utils, port, self._default_escape_char)

        raise LineNotFoundError

    def _init_all(self, refresh):
        config_db = self._db.cfgdb
        state_db = self._db.db

        # Querying CONFIG_DB to get console management feature state
        feature_state = config_db.get_entry(CONSOLE_SWITCH_TABLE, FEATURE_KEY)
        # Default to no escape character when console management feature is disabled or missing.
        self._default_escape_char = None
        if feature_state and feature_state.get(FEATURE_ENABLED_KEY, "no") == "yes":
            self._default_escape_char = feature_state.get(
                DEFAULT_FEATURE_ESCAPE_KEY,
                feature_state.get(DEFAULT_FEATURE_ESCAPE_KEY, None),
            )
            if self._default_escape_char is not None and not self._default_escape_char.islower():
                raise InvalidConfigurationError(
                    DEFAULT_FEATURE_ESCAPE_KEY,
                    "default console escape character is not valid",
                )

        # Querying CONFIG_DB to get configured console ports
        keys = config_db.get_keys(CONSOLE_PORT_TABLE)
        ports = []
        if refresh:
            busy_lines = SysInfoProvider.list_active_console_processes()
        for k in keys:
            port = config_db.get_entry(CONSOLE_PORT_TABLE, k)
            port[LINE_KEY] = k
            if refresh:
                if k in busy_lines:
                    pid, date = busy_lines[k]
                    port[CUR_STATE_KEY] = self._db_utils.update_state(k, BUSY_FLAG, pid, date)
                else:
                    port[CUR_STATE_KEY] = self._db_utils.update_state(k, IDLE_FLAG)
            else:
                port[CUR_STATE_KEY] = state_db.get_all(state_db.STATE_DB, "{}|{}".format(CONSOLE_PORT_TABLE, k))
            ports.append(port)

        # Querying device directory to get all available console ports
        if not self._configured_only:
            available_ttys = SysInfoProvider.list_console_ttys()
            for tty in available_ttys:
                k = tty[len(SysInfoProvider.DEVICE_PREFIX):]
                if k not in keys:
                    port = { LINE_KEY: k }
                    ports.append(port)
        self._ports = ports

class ConsolePortInfo(object):
    def __init__(self, db_utils, info, default_escape_char=None):
        self._db_utils = db_utils
        self._info = info
        self._session = None
        self._default_escape_char = default_escape_char

    def __str__(self):
        return "({}, {}, {})".format(self.line_num, self.baud, self.remote_device)

    @property
    def line_num(self):
        return self._info[LINE_KEY]

    @property
    def baud(self):
        return self._info[BAUD_KEY] if BAUD_KEY in self._info else None

    @property
    def flow_control(self):
        return FLOW_KEY in self._info and self._info[FLOW_KEY] == "1"

    @property
    def remote_device(self):
        return self._info[DEVICE_KEY] if DEVICE_KEY in self._info else None

    @property
    def default_escape_char(self):
        return self._default_escape_char

    @property
    def line_escape_char(self):
        return self._info.get(FEATURE_ESCAPE_KEY, None)

    @property
    def escape_char(self):
        return self._info.get(FEATURE_ESCAPE_KEY, self._default_escape_char)

    @property
    def busy(self):
        return STATE_KEY in self.cur_state and self.cur_state[STATE_KEY] == BUSY_FLAG

    @property
    def session_pid(self):
        return self.cur_state[PID_KEY] if PID_KEY in self.cur_state else None

    @property
    def oper_state(self):
        return self.cur_state[OPER_STATE_KEY] if OPER_STATE_KEY in self.cur_state else None

    @property
    def last_state_change(self):
        return self.cur_state[LAST_STATE_CHANGE_KEY] if LAST_STATE_CHANGE_KEY in self.cur_state else None

    @property
    def state_duration(self):
        """Calculate and format the duration since last state change.
        Format: XdXhXmXs (only shows non-zero parts)
        """
        if not self.last_state_change:
            return None
        try:
            ts = int(self.last_state_change)
            now = int(time.time())
            diff = now - ts
            if diff < 0:
                return None

            # Calculate time components
            days, remainder = divmod(diff, 24 * 3600)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Build formatted string, only include non-zero parts for d/h/m, always show seconds
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0 or days > 0:
                parts.append(f"{hours}h")
            if minutes > 0 or hours > 0 or days > 0:
                parts.append(f"{minutes}m")

            parts.append(f"{seconds}s")  # Always show seconds

            return "".join(parts)
        except (ValueError, OSError):
            return None

    @property
    def session_start_date(self):
        return self.cur_state[START_TIME_KEY] if START_TIME_KEY in self.cur_state else None

    @property
    def cur_state(self):
        if CUR_STATE_KEY not in self._info or self._info[CUR_STATE_KEY] is None:
            self._info[CUR_STATE_KEY] = {}
        return self._info[CUR_STATE_KEY]

    def connect(self):
        """Connect to current line"""
        self.refresh()

        # check if line is busy
        if self.busy:
            raise LineBusyError

        # check required configuration
        if self.baud is None:
            raise InvalidConfigurationError("baud", "line [{}] has no baud rate".format(self.line_num))

        # build and start picocom command
        flow_cmd = "h" if self.flow_control else "n"
        escape_cmd = "-e {}".format(self.escape_char) if self.escape_char else ""
        cmd = "picocom {} -b {} -f {} {}{}{}".format(
            escape_cmd, self.baud, flow_cmd,
            SysInfoProvider.DEVICE_PREFIX, self.line_num, PTY_SYMLINK_SUFFIX)

        # Hand off the entire interactive session to an inline bash script.
        # os.execvp replaces this Python process image with bash, so on
        # success control never returns. If execvp itself fails (e.g.
        # /bin/bash missing) the OSError propagates to the caller.
        escape_display = self.escape_char.upper() if self.escape_char else "A"
        quiet_cmd = cmd.replace("picocom ", "picocom --quiet ", 1)
        os.execvp("/bin/bash", [
            "/bin/bash", "-c", CONSOLE_SESSION_SCRIPT,
            "console_connect", self.line_num, escape_display, quiet_cmd,
        ])

    def clear_session(self):
        """Clear existing session on current line, returns True if the line has been clear"""
        self.refresh()
        if not self.busy:
            return False

        try:
            if not self._session:
                pid = self.session_pid
                cmd = ['sudo', 'kill', '-SIGTERM', str(pid)]
                SysInfoProvider.run_command(cmd)
            else:
                self._session.close()
        finally:
            self.refresh()
            self._session = None

        return True

    def refresh(self):
        """Refresh state for current console port"""
        if self._session is not None:
            proc_info = SysInfoProvider.get_active_console_process_info(self._session.proc.pid)
            if proc_info is not None:
                line_num, pid, date = proc_info
                if line_num != self.line_num:
                    # line mismatch which means the session is stale and shouldn't be use anymore
                    self._update_state(BUSY_FLAG, pid, date, line_num)
                    self._update_state(IDLE_FLAG, "", "")
                    raise ConnectionFailedError
                else:
                    self._update_state(BUSY_FLAG, pid, date)
            else:
                self._update_state(IDLE_FLAG, "", "")
        else:
            # refresh all active ports' state because we already got newest state for all ports
            busy_lines = SysInfoProvider.list_active_console_processes()
            for line_num, proc_info in busy_lines.items():
                pid, date = proc_info
                self._update_state(BUSY_FLAG, pid, date, line_num)
            if self.line_num not in busy_lines:
                self._update_state(IDLE_FLAG, "", "")

    def _update_state(self, state, pid, date, line_num=None):
        self._info[CUR_STATE_KEY] = self._db_utils.update_state(
            self.line_num if line_num is None else line_num, state, pid, date)

class ConsoleSession(object):
    """
    The Console connection session.
    """

    def __init__(self, port, proc):
        self.port = port
        self.proc = proc

    def interact(self):
        """Interact with picocom"""
        try:
            self.proc.interact()
        finally:
            self.port.refresh()

    def close(self):
        """Close picocom session"""
        self.proc.close(force=True)

class SysInfoProvider(object):
    """
    The system level information provider.
    """
    DEVICE_PREFIX = "/dev/ttyUSB"

    @staticmethod
    def init_device_prefix():
        platform_path, _ = device_info.get_paths_to_platform_and_hwsku_dirs()
        UDEV_PREFIX_CONF_FILE_PATH = os.path.join(platform_path, UDEV_PREFIX_CONF_FILENAME)

        if os.path.exists(UDEV_PREFIX_CONF_FILE_PATH):
            fp = open(UDEV_PREFIX_CONF_FILE_PATH, 'r')
            lines = fp.readlines()
            SysInfoProvider.DEVICE_PREFIX = "/dev/" + lines[0].rstrip()

    @staticmethod
    def list_console_ttys():
        """Lists all console tty devices"""
        cmd = ["bash", "-c", "ls " + SysInfoProvider.DEVICE_PREFIX + "*"]
        output, _ = SysInfoProvider.run_command(cmd, abort=False)
        ttys = output.split('\n')
        ttys = list([dev for dev in ttys if re.match(SysInfoProvider.DEVICE_PREFIX + r"\d+$", dev)])
        return ttys

    @staticmethod
    def list_active_console_processes():
        """Lists all active console session processes"""
        cmd0 = ['ps', '-eo', 'pid,lstart,cmd']
        cmd1 = ['grep', '-E', "(mini|pico)com"]
        output = SysInfoProvider.run_command(cmd0, cmd1)
        return SysInfoProvider._parse_processes_info(output)

    @staticmethod
    def get_active_console_process_info(pid):
        """Gets active console process information by PID"""
        cmd0 = ['ps', '-p', str(pid), '-o', 'pid,lstart,cmd']
        cmd1 = ['grep', '-E', "(mini|pico)com"]
        output = SysInfoProvider.run_command(cmd0, cmd1)
        processes = SysInfoProvider._parse_processes_info(output)
        if len(list(processes.keys())) == 1:
            return (list(processes.keys())[0],) + list(processes.values())[0]
        else:
            return None

    @staticmethod
    def _parse_processes_info(output):
        processes = output.split('\n')

        # matches any number of spaces then any number of digits
        regex_pid = r" *(\d+)"
        # matches anything of form: Xxx Xxx ( 0)or(00) 00:00:00 0000
        regex_date = r"([A-Z][a-z]{2} [A-Z][a-z]{2} [\d ]\d \d{2}:\d{2}:\d{2} \d{4})"
        # matches any characters ending in minicom or picocom,
        # then a space and any chars followed by /dev/ttyUSB<any digits>,
        # then any chars
        regex_cmd = r".*(?:(?:mini)|(?:pico))com .*" + SysInfoProvider.DEVICE_PREFIX + r"(\d+).*"
        regex_process = re.compile(r"^" + regex_pid + r" " + regex_date + r" " + regex_cmd + r"$")

        console_processes = {}
        for process in processes:
            match = regex_process.match(process)
            if match != None:
                pid = match.group(1)
                date = match.group(2)
                line_num = match.group(3)
                console_processes[line_num] = (pid, date)
        return console_processes

    @staticmethod
    def run_command(*args, abort=True):
        exitcodes, output = getstatusoutput_noshell_pipe(*args)
        if abort and any(exitcodes) and output != '':
            click.echo("Command resulted in error: {}".format(output))
            sys.exit(ERR_CMD)
        return output if abort else (output, output)

class DbUtils(object):
    def __init__(self, db):
        self._db = db
        self._config_db = db.cfgdb
        self._state_db = db.db

    def update_state(self, line_num, state, pid="", date=""):
        key = "{}|{}".format(CONSOLE_PORT_TABLE, line_num)
        self._state_db.set(self._state_db.STATE_DB, key, STATE_KEY, state)
        self._state_db.set(self._state_db.STATE_DB, key, PID_KEY, pid)
        self._state_db.set(self._state_db.STATE_DB, key, START_TIME_KEY, date)

        # Read existing oper_state and last_state_change from STATE_DB
        existing_data = self._state_db.get_all(self._state_db.STATE_DB, key)
        oper_state = existing_data.get(OPER_STATE_KEY, "") if existing_data else ""
        last_state_change = existing_data.get(LAST_STATE_CHANGE_KEY, "") if existing_data else ""

        return {
            STATE_KEY: state,
            PID_KEY: pid,
            START_TIME_KEY: date,
            OPER_STATE_KEY: oper_state,
            LAST_STATE_CHANGE_KEY: last_state_change
        }


def initialize_console_runtime(db):
    """Validate console feature state and initialize device prefix."""
    config_db = db.cfgdb
    data = config_db.get_entry(CONSOLE_SWITCH_TABLE, FEATURE_KEY)
    if FEATURE_ENABLED_KEY not in data or data[FEATURE_ENABLED_KEY] == "no":
        click.echo("Console switch feature is disabled")
        sys.exit(ERR_DISABLE)

    SysInfoProvider.init_device_prefix()


def console_connect(target, use_device=False, db=None):
    """Connect to a console port. Can be called directly without Click context."""
    if db is None:
        from utilities_common.db import Db
        db = Db()
        initialize_console_runtime(db)

    port_provider = ConsolePortProvider(db, configured_only=False)
    try:
        target_port = port_provider.get(target, use_device=use_device)
    except LineNotFoundError:
        click.echo("Cannot connect: target [{}] does not exist".format(target))
        sys.exit(ERR_DEV)

    line_num = target_port.line_num

    try:
        session = target_port.connect()
    except LineBusyError:
        click.echo("Cannot connect: line [{}] is busy".format(line_num))
        sys.exit(ERR_BUSY)
    except InvalidConfigurationError as cfg_err:
        click.echo("Cannot connect: {}".format(cfg_err.message))
        sys.exit(ERR_CFG)
    except ConnectionFailedError:
        click.echo("Cannot connect: unable to open picocom process")
        sys.exit(ERR_DEV)

    click.echo("Successful connection to line [{}]\nPress ^{} ^X to disconnect"
               .format(line_num, target_port.escape_char.upper() if target_port.escape_char is not None else "A"))
    session.interact()


def get_target_line(db, target, use_device=False):
    port_provider = ConsolePortProvider(db, configured_only=True)
    try:
        return port_provider.get(target, use_device=use_device).line_num
    except LineNotFoundError:
        click.echo("Target [{}] does not exist".format(target))
        sys.exit(ERR_DEV)


def require_root():
    """Check if the current user is root, exit with error if not."""
    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERR_CMD)


def validate_mirror_timeout_duration(ctx, param, value):
    if value is None:
        return None
    if len(value) < 2 or value[-1] not in MIRROR_DURATION_SUFFIXES or not value[:-1].isdigit() or int(value[:-1]) <= 0:
        raise click.BadParameter(
            "must be a positive duration ending in s, m, h, or d")
    return value


def _mirror_error_message(response):
    return response.get("message") or response.get("error") or "mirror request failed"


def _recv_mirror_message(sock, timeout=None):
    def _recv_all(sock, size):
        data = b""
        while len(data) < size:
            try:
                chunk = sock.recv(size - len(data))
            except socket.timeout:
                raise RuntimeError("timed out waiting for mirror response")
            if not chunk:
                raise RuntimeError("unexpected EOF")
            data += chunk
        return data
    sock.settimeout(timeout)
    header = _recv_all(sock, 4)
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > MIRROR_CONTROL_MAX_MESSAGE:
        raise RuntimeError("invalid response size")
    try:
        response = json.loads(_recv_all(sock, size).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise RuntimeError("invalid response payload")
    if not isinstance(response, dict):
        raise RuntimeError("invalid response payload")
    return response


def send_mirror_message(line, message, wait_for_final=False, quiet=False, on_first_reply=None):
    path = os.path.join(MIRROR_RUNTIME_DIR, "line{}.sock".format(line))
    payload = json.dumps(message, separators=(",", ":"),
                         sort_keys=True).encode("utf-8")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(path)
            sock.sendall(struct.pack("!I", len(payload)) + payload)
            first = _recv_mirror_message(sock)
            if wait_for_final:
                if first.get("status") != "packaging":
                    raise RuntimeError(_mirror_error_message(first))
                if on_first_reply is not None:
                    on_first_reply(first)  # callback for first reply
                final = _recv_mirror_message(
                    sock, timeout=MIRROR_ARCHIVE_RESPONSE_TIMEOUT_SEC)
                if final.get("status") != "ok":
                    raise RuntimeError(_mirror_error_message(final))
                return first, final
            if first.get("status") != "ok":
                raise RuntimeError(_mirror_error_message(first))
            return first
    except (OSError, RuntimeError) as e:
        if quiet:
            raise
        click.echo("Mirror request failed on line [{}]: {}".format(line, e))
        sys.exit(ERR_CMD)


class InvalidConfigurationError(Exception):
    def __init__(self, config_key, message):
        self.config_key = config_key
        self.message = message

class LineBusyError(Exception):
    pass

class LineNotFoundError(Exception):
    pass

class ConnectionFailedError(Exception):
    pass
