#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time

import sonic_py_common.logger
from swsscommon.swsscommon import ConfigDBConnector, SonicV2Connector
from utilities_common.auto_techsupport_helper import STATE_DB

# Exit codes (ordered by priority and severity)
EXIT_SUCCESS = 0  # Success
EXIT_FAILURE = 1  # General failure occurred, no techsupport is invoked
EXIT_THRESHOLD = 2  # Configurable threshold (available_mem_threshold) crossed - logs + techsupport
EXIT_THRESHOLD_60 = 3  # 60% memory usage threshold crossed (logs only; checker invokes handler)
EXIT_THRESHOLD_80 = 4  # 80% memory usage threshold crossed (logs only; checker invokes handler)
EXIT_THRESHOLD_90 = 5  # 90% memory usage threshold crossed (logs only)

# Installed path used by monit and by this checker for log-only 60%/80% handling
HANDLER_SCRIPT = "/usr/local/bin/memory_threshold_check_handler.py"

# Recreate monit: 30 times within 60 cycles, then repeat every 120/30 cycles
# (daemon 60s => 1 cycle = 1 minute). State is process-local across runs.
LOG_ONLY_STATE_FILE = "/var/run/memory_threshold_check.json"
LOG_ONLY_WINDOW_SECONDS = 60 * 60
LOG_ONLY_HITS_REQUIRED = 30
LOG_ONLY_COOLDOWN_SECONDS = {
    3: 120 * 60,  # EXIT_THRESHOLD_60, repeat every 120 cycles
    4: 30 * 60,   # EXIT_THRESHOLD_80, repeat every 30 cycles
}

SYSLOG_IDENTIFIER = "memory_threshold_check"

# Config DB tables
AUTO_TECHSUPPORT = "AUTO_TECHSUPPORT"
AUTO_TECHSUPPORT_FEATURE = "AUTO_TECHSUPPORT_FEATURE"

# State DB docker stats table
DOCKER_STATS = "DOCKER_STATS"

# (%) Default value for available memory left in the system
DEFAULT_MEMORY_AVAILABLE_THRESHOLD = 10
# (MB) Default value for minimum available memory in the system to run techsupport
DEFAULT_MEMORY_AVAILABLE_MIN_THRESHOLD = 200
# (%) Default value for available memory inside container
DEFAULT_MEMORY_AVAILABLE_FEATURE_THRESHOLD = 0

MB_TO_KB_MULTIPLIER = 1024

# Global logger instance
logger = sonic_py_common.logger.Logger(SYSLOG_IDENTIFIER)


class MemoryCheckerException(Exception):
    """General memory checker exception"""

    pass


class MemoryStats:
    """MemoryStats provides an interface to query memory statistics of the system and per feature."""

    def __init__(self, state_db):
        """Initialize MemoryStats

        Args:
            state_db (swsscommon.DBConnector): state DB connector instance
        """
        self.state_db = state_db

    def get_sys_memory_stats(self):
        """Returns system memory statistic dictionary, reflects the /proc/meminfo

        Returns:
            Dictionary of strings to integers where integer values
            represent memory amount in Kb, e.g:
            {
                "MemTotal": 8104856,
                "MemAvailable": 6035192,
                ...
            }
        """
        with open("/proc/meminfo") as fd:
            lines = fd.read().split("\n")
            rows = [line.split() for line in lines]

            # e.g row is ('MemTotal:', '8104860', 'kB')
            # key is the first element with removed remove last ':'.
            # value is the second element converted to int.
            def row_to_key(row):
                return row[0][:-1]

            def row_to_value(row):
                return int(row[1])

            return {row_to_key(row): row_to_value(row) for row in rows if len(row) >= 2}

    def get_containers_memory_usage(self):
        """Returns per container memory usage, reflects the DOCKER_STATS state DB table

        Returns:
            Dictionary of strings to floats where floating point values
            represent memory usage of the feature container which is carefully
            calculated for us by the dockerd and published by procdockerstatsd, e.g:

            {
                "swss": 1.5,
                "teamd": 10.92,
                ...
            }
        """
        result = {}
        dockers = self.state_db.keys(STATE_DB, DOCKER_STATS + "|*")
        stats = [
            stat for stat in [self.state_db.get_all(STATE_DB, key) for key in dockers] if stat is not None
        ]

        for stat in stats:
            try:
                name = stat["NAME"]
                mem_usage = float(stat["MEM%"])
            except KeyError:
                continue
            except ValueError as err:
                logger.log_error(f'Failed to parse memory usage for "{stat}": {err}')
                raise MemoryCheckerException(err)

            result[name] = mem_usage

        return result


class Config:
    def __init__(self, cfg_db):
        self.table = cfg_db.get_table(AUTO_TECHSUPPORT)
        self.feature_table = cfg_db.get_table(AUTO_TECHSUPPORT_FEATURE)

        config = self.table.get("GLOBAL")

        self.memory_available_threshold = self.parse_value_from_db(
            config,
            "available_mem_threshold",
            float,
            DEFAULT_MEMORY_AVAILABLE_THRESHOLD,
        )
        self.memory_available_min_threshold = self.parse_value_from_db(
            config,
            "min_available_mem",
            float,
            DEFAULT_MEMORY_AVAILABLE_MIN_THRESHOLD,
        ) * MB_TO_KB_MULTIPLIER

        keys = self.feature_table.keys()
        self.feature_config = {}
        for key in keys:
            config = self.feature_table.get(key)

            self.feature_config[key] = self.parse_value_from_db(
                config,
                "available_mem_threshold",
                float,
                DEFAULT_MEMORY_AVAILABLE_FEATURE_THRESHOLD,
            )

    @staticmethod
    def parse_value_from_db(config, key, converter, default):
        value = config.get(key)
        if not value:
            return default
        try:
            return converter(value)
        except ValueError as err:
            logger.log_error(f'Failed to parse {key} value "{value}": {err}')
            raise MemoryCheckerException(err)


def _empty_log_only_band():
    return {"hits": [], "last_fired": None}


def _coerce_log_only_band(raw):
    """Return a usable band; discard malformed hits / last_fired."""
    band = _empty_log_only_band()
    if not isinstance(raw, dict):
        return band
    raw_hits = raw.get("hits", [])
    if isinstance(raw_hits, list):
        hits = []
        for ts in raw_hits:
            try:
                hits.append(float(ts))
            except (TypeError, ValueError):
                continue
        band["hits"] = hits
    last_fired = raw.get("last_fired")
    if last_fired is not None:
        try:
            band["last_fired"] = float(last_fired)
        except (TypeError, ValueError):
            band["last_fired"] = None
    return band


def load_log_only_state():
    if not os.path.exists(LOG_ONLY_STATE_FILE):
        return {}
    try:
        with open(LOG_ONLY_STATE_FILE) as fd:
            data = json.load(fd)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as err:
        logger.log_error(f"Failed to load {LOG_ONLY_STATE_FILE}: {err}")
        return {}


def save_log_only_state(state):
    directory = os.path.dirname(LOG_ONLY_STATE_FILE)
    try:
        os.makedirs(directory, exist_ok=True)
        tmp_path = LOG_ONLY_STATE_FILE + ".tmp"
        with open(tmp_path, "w") as fd:
            json.dump(state, fd)
        os.replace(tmp_path, LOG_ONLY_STATE_FILE)
    except OSError as err:
        logger.log_error(f"Failed to save {LOG_ONLY_STATE_FILE}: {err}")


def reset_log_only_bands(codes=None):
    """Clear 60%/80% hysteresis (monit recovered / other status won)."""
    state = load_log_only_state()
    if codes is None:
        codes = (EXIT_THRESHOLD_60, EXIT_THRESHOLD_80)
    changed = False
    for code in codes:
        key = str(code)
        if state.get(key):
            state[key] = _empty_log_only_band()
            changed = True
    if changed:
        save_log_only_state(state)


def should_fire_log_only_handler(exit_code, now=None):
    """Return True when monit would have exec'd the handler for status 3 or 4.

    First fire: 30 samples in the last 60 minutes.
    After that, while still in this band: fire again after the cooldown
    (120 min at 60%, 30 min at 80%) without re-arming 30/60.
    Leaving the band clears state so the next incident must arm again.
    """
    if now is None:
        now = time.time()
    other = EXIT_THRESHOLD_80 if exit_code == EXIT_THRESHOLD_60 else EXIT_THRESHOLD_60
    state = load_log_only_state()
    state[str(other)] = _empty_log_only_band()
    band = _coerce_log_only_band(state.get(str(exit_code)))
    hits = list(band["hits"])
    hits.append(now)
    hits = [ts for ts in hits if ts >= now - LOG_ONLY_WINDOW_SECONDS]
    last_fired = band.get("last_fired")
    cooldown = LOG_ONLY_COOLDOWN_SECONDS[exit_code]
    if last_fired is None:
        fire = len(hits) >= LOG_ONLY_HITS_REQUIRED
    else:
        fire = (now - last_fired) >= cooldown
    # Persist hits only. last_fired is written after Popen succeeds so a
    # spawn failure can retry on the next cycle instead of waiting cooldown.
    state[str(exit_code)] = {"hits": hits, "last_fired": last_fired}
    save_log_only_state(state)
    return fire


def mark_log_only_handler_fired(exit_code, now=None):
    """Record a successful handler start so cooldown applies."""
    if now is None:
        now = time.time()
    state = load_log_only_state()
    band = _coerce_log_only_band(state.get(str(exit_code)))
    band["last_fired"] = now
    state[str(exit_code)] = band
    save_log_only_state(state)


def _handler_env():
    """Environment for a checker-spawned handler (not a monit exec)."""
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("MONIT_"):
            env.pop(key, None)
    return env


def invoke_log_only_handler(exit_code):
    """Start the handler without blocking monit's program timeout.

    Strip MONIT_* so inherited monit env cannot make the handler treat this
    as a failed exec (MONIT_DESCRIPTION without '--'). Detach the session so
    a later monit kill of the checker does not take the handler with it.
    """
    try:
        subprocess.Popen(
            [HANDLER_SCRIPT, str(exit_code)],
            env=_handler_env(),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.SubprocessError) as err:
        logger.log_error(
            f"Failed to start handler for threshold code {exit_code}: {err}; "
            f"monit check still OK"
        )
        return False


def handle_log_only_threshold(exit_code):
    """Maybe run the handler, matching old monit 30-in-60 plus repeat cooldown."""
    if should_fire_log_only_handler(exit_code) and invoke_log_only_handler(exit_code):
        mark_log_only_handler_fired(exit_code)


class MemoryChecker:
    """Business logic of the memory checker"""

    def __init__(self, stats, config):
        """Initialize MemoryChecker"""
        self.stats = stats
        self.config = config

    def run_check(self):
        """Runs the checks and returns a tuple of exit code and container name.
        Checks multiple thresholds: 60%, 80%, 90% and CONFIG_DB configured threshold.
        Returns highest severity threshold crossed.

        Returns:
            (int, str): exit code and container name (empty string for host)
        """
        # don't bother getting stats if available memory threshold is set to 0
        if self.config.memory_available_threshold:
            memory_stats = self.stats.get_sys_memory_stats()
            memory_free = memory_stats["MemAvailable"]
            memory_total = memory_stats["MemTotal"]
            memory_free_threshold = (
                memory_total * self.config.memory_available_threshold / 100
            )
            memory_min_free_threshold = self.config.memory_available_min_threshold
            memory_used_percent = ((memory_total - memory_free) / memory_total) * 100

            # free memory amount is less than configured minimum required memory for
            # running "show techsupport"
            if memory_free <= memory_min_free_threshold:
                logger.log_error(
                    f"Free memory {memory_free} is less than "
                    f"min free memory threshold {memory_min_free_threshold}"
                )
                reset_log_only_bands()
                return (EXIT_FAILURE, "")

            # Check configurable threshold FIRST (prioritized - triggers logs + techsupport)
            if memory_free <= memory_free_threshold:
                logger.log_error(
                    f"Free memory {memory_free} is less than "
                    f"free memory threshold {memory_free_threshold}"
                )
                reset_log_only_bands()
                return (EXIT_THRESHOLD, "")

        # Check container memory usage with configured thresholds (if any)
        container_memory_usage = self.stats.get_containers_memory_usage()
        for feature, memory_available_threshold in self.config.feature_config.items():
            for container, memory_usage in container_memory_usage.items():
                # startswith to handle multi asic instances
                if not container.startswith(feature):
                    continue

                # Check if available memory is below configured threshold
                # memory_available_threshold is % of available memory that should remain
                # memory_usage is % of memory being used
                if (100 - memory_usage) <= memory_available_threshold:
                    logger.log_error(
                        f"Available {100 - memory_usage:.2f}% for {feature} is less "
                        f"than free memory threshold {memory_available_threshold}%"
                    )
                    reset_log_only_bands()
                    return (EXIT_THRESHOLD, feature)

        # Check fixed thresholds (logs only, no techsupport).
        # 90% still fails monit (system-health). 80% and 60% invoke the handler
        # in-process and return success so memory_check stays Status ok.
        if self.config.memory_available_threshold:
            if memory_used_percent >= 90:
                reset_log_only_bands()
                return (EXIT_THRESHOLD_90, "")
            elif memory_used_percent >= 80:
                handle_log_only_threshold(EXIT_THRESHOLD_80)
                return (EXIT_SUCCESS, "")
            elif memory_used_percent >= 60:
                handle_log_only_threshold(EXIT_THRESHOLD_60)
                return (EXIT_SUCCESS, "")

        reset_log_only_bands()
        return (EXIT_SUCCESS, "")


def main():
    cfg_db = ConfigDBConnector(use_unix_socket_path=True)
    cfg_db.connect()
    state_db = SonicV2Connector(use_unix_socket_path=True)
    state_db.connect(STATE_DB)

    config = Config(cfg_db)
    mem_stats = MemoryStats(state_db)
    mem_checker = MemoryChecker(mem_stats, config)

    try:
        exit_code, name = mem_checker.run_check()
        return exit_code, name
    except MemoryCheckerException as err:
        logger.log_error(f"Failure occurred: {err}")
        return EXIT_FAILURE, ""
    except Exception as err:
        logger.log_error(f"{err}")
        return EXIT_FAILURE, ""


if __name__ == "__main__":
    rc, component = main()
    print(component)
    sys.exit(rc)
