import os
import re
import glob
import time
import subprocess
import shutil
import math
import syslog
from os.path import basename, splitext

__all__ = [  # Constants
            "CORE_DUMP_DIR", "CORE_DUMP_PTRN", "TS_DIR", "TS_PTRN",
            "CFG_DB", "AUTO_TS", "CFG_STATE", "CFG_MAX_TS", "COOLOFF",
            "CFG_CORE_USAGE", "CFG_SINCE", "FEATURE", "STATE_DB",
            "TS_MAP", "CORE_DUMP", "TIMESTAMP", "CONTAINER", "TIME_BUF",
            "SINCE_DEFAULT", "TS_PTRN_GLOB", "EXT_LOCKFAIL", "EXT_RETRY",
            "EXT_SUCCESS", "MAX_RETRY_LIMIT", "EVENT_TYPE", "EVENT_TYPE_CORE",
            "EVENT_TYPE_MEMORY"
        ] + [  # Methods
            "verify_recent_file_creation",
            "get_ts_dumps",
            "strip_ts_ext",
            "get_stats",
            "pretty_size",
            "cleanup_process",
            "subprocess_exec",
            "trim_masic_suffix",
            "invoke_ts_command_rate_limited",
        ]


# MISC
CORE_DUMP_DIR = "/var/core"
CORE_DUMP_PTRN = "*.core.gz"

TS_DIR = "/var/dump"
TS_ROOT = "sonic_dump_*"
TS_PTRN = "sonic_dump_.*tar.*" # Regex Exp
TS_PTRN_GLOB = "sonic_dump_*tar*" # Glob Exp

# DBs identifiers
CFG_DB = "CONFIG_DB"
STATE_DB = "STATE_DB"

# AUTO_TECHSUPPORT|GLOBAL table attributes
AUTO_TS = "AUTO_TECHSUPPORT|GLOBAL"
CFG_STATE = "state"
CFG_MAX_TS = "max_techsupport_limit"
COOLOFF = "rate_limit_interval"
CFG_CORE_USAGE = "max_core_limit"
CFG_SINCE = "since"

# AUTO_TECHSUPPORT_FEATURE Table
FEATURE = "AUTO_TECHSUPPORT_FEATURE|{}"

# State DB Attributes
STATE_DB = "STATE_DB"

# AUTO_TECHSUPPORT_DUMP_INFO table info
TS_MAP = "AUTO_TECHSUPPORT_DUMP_INFO"
CORE_DUMP = "core_dump"
TIMESTAMP = "timestamp"
CONTAINER = "container_name"
EVENT_TYPE = "event_type"

EVENT_TYPE_CORE = "core"
EVENT_TYPE_MEMORY = "memory"

TIME_BUF = 20
SINCE_DEFAULT = "2 days ago"
TS_GLOBAL_TIMEOUT = "60"

# Explicitly Pass this to the subprocess invoking techsupport
ENV_VAR = os.environ
if ('CROSS_BUILD_ENVIRON' not in ENV_VAR) or (ENV_VAR['CROSS_BUILD_ENVIRON'] != 'y'):
	# Add native system directories to PATH variable only if it is not cross-compilation build 
	PATH_PREV = ENV_VAR["PATH"] if "PATH" in ENV_VAR else ""
	ENV_VAR["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + PATH_PREV

# Techsupport Exit Codes
EXT_LOCKFAIL = 2
EXT_RETRY = 4
EXT_SUCCESS = 0
MAX_RETRY_LIMIT = 2

# Helper methods
def subprocess_exec(cmd, env=None):
    output = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env
    )
    return output.returncode, output.stdout, output.stderr


def strip_ts_ext(ts_path):
    """ Return the basename and strip the techsupport dump of any extensions """
    base_name = basename(ts_path)
    name, _ = splitext(splitext(base_name)[0])  # *.tar.gz
    return name


def get_ts_dumps(full_path=False):
    """
    Get the list of TS dumps in the TS_DIR, sorted by the creation time
    """
    curr_list = glob.glob(os.path.join(TS_DIR, TS_ROOT))
    curr_list.sort(key=os.path.getmtime)
    if full_path:
        return curr_list
    return [os.path.basename(name) for name in curr_list]


def verify_recent_file_creation(file_path, in_last_sec=TIME_BUF):
    """ Verify if the file exists and is created within the last TIME_BUF sec """
    curr = time.time()
    try:
        was_created_on = os.path.getmtime(file_path)
    except Exception:
        return False
    if curr - was_created_on < in_last_sec:
        return True
    else:
        return False


def get_stats(ptrn, collect_stats=True):
    """
    Returns the size of the files (matched by the ptrn) occupied.
    Also returns the list of files Sorted by the Descending order of creation time & size
    """
    files = glob.glob(ptrn)
    file_stats = []
    total_size = 0
    for file in files:
        file_size = os.path.getsize(file)
        if collect_stats:
            file_stats.append((os.path.getmtime(file), file_size, file))
        total_size += file_size
    if collect_stats:
        # Sort by the Descending order of file_creation_time, size_of_file
        file_stats = sorted(file_stats, key=lambda sub: (-sub[0], sub[1], sub[2]))
    return (file_stats, total_size)


def pretty_size(bytes):
    """Get human-readable file sizes"""
    UNITS_MAPPING = [
        (1 << 50, ' PB'),
        (1 << 40, ' TB'),
        (1 << 30, ' GB'),
        (1 << 20, ' MB'),
        (1 << 10, ' KB'),
        (1, (' byte', ' bytes')),
    ]
    for factor, suffix in UNITS_MAPPING:
        if bytes >= factor:
            break
    amount = int(bytes / factor)

    if isinstance(suffix, tuple):
        singular, multiple = suffix
        if amount == 1:
            suffix = singular
        else:
            suffix = multiple
    return str(amount) + suffix


def cleanup_process(limit, file_ptrn, dir):
    """Deletes the oldest files incrementally until the size is under limit"""
    if not(0 < limit and limit < 100):
        syslog.syslog(syslog.LOG_ERR, "core_usage_limit can only be between 1 and 100, whereas the configured value is: {}".format(limit))
        return

    fs_stats, curr_size = get_stats(os.path.join(dir, file_ptrn))
    disk_stats = shutil.disk_usage(dir)
    max_limit_bytes = math.floor((limit * disk_stats.total / 100))

    if curr_size <= max_limit_bytes:
        return

    num_bytes_to_del = curr_size - max_limit_bytes
    num_deleted = 0
    removed_files = []
    # Preserve the latest file created
    while num_deleted < num_bytes_to_del and len(fs_stats) > 1:
        stat = fs_stats.pop()
        try:
            os.remove(stat[2])
            removed_files.append(stat[2])
        except OSError as error:
            continue
        num_deleted += stat[1]
    syslog.syslog(syslog.LOG_INFO, "{} deleted from {}".format(pretty_size(num_deleted), dir))
    return removed_files


def trim_masic_suffix(container_name):
    """ Trim any masic suffix i.e swss0 -> swss """
    arr = list(container_name)
    index = len(arr) - 1
    while index >= 0:
        if arr[-1].isdigit():
            arr.pop()
        else:
            break
        index = index - 1
    return "".join(arr)

def get_since_arg(db):
    """Get since configuration from AUTO_TECHSUPPORT table or default value"""
    since_cfg = db.get(CFG_DB, AUTO_TS, CFG_SINCE)
    if not since_cfg:
        return SINCE_DEFAULT
    rc, _, stderr = subprocess_exec(["date", "--date={}".format(since_cfg)], env=ENV_VAR)
    if rc == 0:
        return since_cfg
    return SINCE_DEFAULT


def parse_ts_dump_name(ts_stdout):
    """ Figure out the ts_dump name from the techsupport stdout """
    matches = re.findall(TS_PTRN, ts_stdout)
    if matches:
        return matches[-1]
    syslog.syslog(syslog.LOG_ERR, "stdout of the 'show techsupport' cmd doesn't have the dump name")
    return ""


def invoke_ts_cmd(db, num_retry=0):
    """Invoke techsupport generation command"""
    since_cfg = get_since_arg(db)
    cmd_opts = ["show", "techsupport", "--silent", "--global-timeout", TS_GLOBAL_TIMEOUT, "--since", since_cfg]
    cmd  = " ".join(cmd_opts)
    rc, stdout, stderr = subprocess_exec(cmd_opts, env=ENV_VAR)
    new_dump = ""
    if rc == EXT_LOCKFAIL:
        syslog.syslog(syslog.LOG_NOTICE, "Another instance of techsupport running, aborting this. stderr: {}".format(stderr))
    elif rc == EXT_RETRY:
        if num_retry <= MAX_RETRY_LIMIT:
            return invoke_ts_cmd(db, num_retry+1)
        else:
            syslog.syslog(syslog.LOG_ERR, "MAX_RETRY_LIMIT for show techsupport invocation exceeded, stderr: {}".format(stderr))
    elif rc != EXT_SUCCESS:
        syslog.syslog(syslog.LOG_ERR, "show techsupport failed with exit code {}, stderr: {}".format(rc, stderr))
    else: # EXT_SUCCESS
        new_dump = parse_ts_dump_name(stdout) # Parse the dump name
        if not new_dump:
            syslog.syslog(syslog.LOG_ERR, "{} was run, but no techsupport dump is found".format(cmd))
        else:
            syslog.syslog(syslog.LOG_INFO, "{} is successful, {} is created".format(cmd, new_dump))
    return new_dump


def get_ts_map(db):
    """Create ts_dump & creation_time map"""
    ts_map = {}
    ts_keys = db.keys(STATE_DB, TS_MAP+"*")
    if not ts_keys:
        return ts_map
    for ts_key in ts_keys:
        data = db.get_all(STATE_DB, ts_key)
        if not data:
            continue
        container_name = data.get(CONTAINER, "")
        creation_time = data.get(TIMESTAMP, "")
        try:
            creation_time = int(creation_time)
        except Exception:
            continue  # if the creation time is invalid, skip the entry
        ts_dump = ts_key.split("|")[-1]
        if container_name not in ts_map:
            ts_map[container_name] = []
        ts_map[container_name].append((int(creation_time), ts_dump))
    for container_name in ts_map:
        ts_map[container_name].sort()
    return ts_map


def verify_rate_limit_intervals(db, global_cooloff, container_cooloff, container):
    """Verify both the global and per-proc rate_limit_intervals have passed"""
    curr_ts_list = get_ts_dumps(True)
    if global_cooloff and curr_ts_list:
        last_ts_dump_creation = os.path.getmtime(curr_ts_list[-1])
        if time.time() - last_ts_dump_creation < global_cooloff:
            msg = "Global rate_limit_interval period has not passed. Techsupport Invocation is skipped"
            syslog.syslog(msg)
            return False

    ts_map = get_ts_map(db)
    if container_cooloff and container in ts_map:
        last_creation_time = ts_map[container][0][0]
        if time.time() - last_creation_time < container_cooloff:
            msg = "Per Container rate_limit_interval for {} has not passed. Techsupport Invocation is skipped"
            syslog.syslog(msg.format(container))
            return False
    return True


def write_to_state_db(db, timestamp, ts_dump, event_type, event_data, container=None):
    name = strip_ts_ext(ts_dump)
    key = TS_MAP + "|" + name
    db.set(STATE_DB, key, TIMESTAMP, str(timestamp))
    db.set(STATE_DB, key, EVENT_TYPE, event_type)
    for event_data_key, event_data_value in event_data.items():
        db.set(STATE_DB, key, event_data_key, event_data_value)
    if container:
        db.set(STATE_DB, key, CONTAINER, container)


def invoke_ts_command_rate_limited(db, event_type, event_data, container=None):
    """Invoke techsupport generation command accounting the rate limit"""
    global_cooloff = db.get(CFG_DB, AUTO_TS, COOLOFF)
    if container:
        container_cooloff = db.get(
            CFG_DB, FEATURE.format(container), COOLOFF
        )
    else:
        container_cooloff = 0.0

    try:
        global_cooloff = float(global_cooloff)
    except ValueError:
        global_cooloff = 0.0

    try:
        container_cooloff = float(container_cooloff)
    except ValueError:
        container_cooloff = 0.0

    cooloff_passed = verify_rate_limit_intervals(db, global_cooloff, container_cooloff, container)
    if cooloff_passed:
        new_file = invoke_ts_cmd(db)
        if new_file:
            write_to_state_db(db, int(time.time()), new_file, event_type, event_data, container)
