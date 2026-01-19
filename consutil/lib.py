#
# lib.py
#
# Helper code for CLI for interacting with switches via console device
#

import os
import pexpect
import re
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

UDEV_PREFIX_CONF_FILENAME = "udevprefix.conf"

PTY_SYMLINK_SUFFIX = "-PTS"

TIMEOUT_SEC = 0.2

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
            yield ConsolePortInfo(self._db_utils, port)

    def get(self, target, use_device=False):
        """Gets information of a ports, the target is the line number by default"""
        # figure out the search key
        search_key = LINE_KEY
        if use_device:
            search_key = DEVICE_KEY

        # identify the line number by searching configuration
        for port in self._ports:
            if search_key in port and port[search_key] == target:
                return ConsolePortInfo(self._db_utils, port)

        raise LineNotFoundError

    def _init_all(self, refresh):
        config_db = self._db.cfgdb
        state_db = self._db.db

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
    def __init__(self, db_utils, info):
        self._db_utils = db_utils
        self._info = info
        self._session = None
    
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
        cmd = "picocom -b {} -f {} {}{}{}".format(
            self.baud, flow_cmd, SysInfoProvider.DEVICE_PREFIX,
            self.line_num, PTY_SYMLINK_SUFFIX)

        # start connection
        try:
            proc = pexpect.spawn(cmd)
            proc.send("\n")
            self._session = ConsoleSession(self, proc)
        finally:
            self.refresh()

        # check if connection succeed
        index = proc.expect([PICOCOM_READY, PICOCOM_BUSY, pexpect.EOF, pexpect.TIMEOUT], timeout=TIMEOUT_SEC)
        if index == 0:
            return self._session
        elif index == 1:
            self._session = None
            raise LineBusyError
        else:
            self._session = None
            raise ConnectionFailedError

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
        ttys = list([dev for dev in ttys if re.match(SysInfoProvider.DEVICE_PREFIX + r"\d+", dev) != None])
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
