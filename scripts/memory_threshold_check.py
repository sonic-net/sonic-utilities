#!/usr/bin/env python3

import sys

import sonic_py_common.logger
from swsscommon.swsscommon import ConfigDBConnector, SonicV2Connector
from utilities_common.auto_techsupport_helper import STATE_DB

# Exit codes
EXIT_SUCCESS = 0  # Success
EXIT_FAILURE = 1  # General failure occurred, no techsupport is invoked
EXIT_THRESHOLD_CROSSED = 2  # Memory threshold crossed, techsupport is invoked

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
            except KeyError as err:
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


class MemoryChecker:
    """Business logic of the memory checker"""

    def __init__(self, stats, config):
        """Initialize MemoryChecker"""
        self.stats = stats
        self.config = config

    def run_check(self):
        """Runs the checks and returns a tuple of check result boolean
        and a container name or empty string if the check failed for the host.

        Returns:
            (bool, str)
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

            # free memory amount is less then configured minimum required memory for
            # running "show techsupport"
            if memory_free <= memory_min_free_threshold:
                logger.log_error(
                    f"Free memory {memory_free} is less then "
                    f"min free memory threshold {memory_min_free_threshold}"
                )
                return (False, "")

            # free memory amount is less then configured threshold
            if memory_free <= memory_free_threshold:
                logger.log_error(
                    f"Free memory {memory_free} is less then "
                    f"free memory threshold {memory_free_threshold}"
                )
                return (False, "")

        container_memory_usage = self.stats.get_containers_memory_usage()
        for feature, memory_available_threshold in self.config.feature_config.items():
            for container, memory_usage in container_memory_usage.items():
                # startswith to handle multi asic instances
                if not container.startswith(feature):
                    continue

                # free memory amount is less then configured threshold
                if (100 - memory_usage) <= memory_available_threshold:
                    logger.log_error(
                        f"Available {100 - memory_usage} for {feature} is less "
                        f"then free memory threshold {memory_available_threshold}"
                    )
                    return (False, feature)

        return (True, "")


def main():
    cfg_db = ConfigDBConnector(use_unix_socket_path=True)
    cfg_db.connect()
    state_db = SonicV2Connector(use_unix_socket_path=True)
    state_db.connect(STATE_DB)

    config = Config(cfg_db)
    mem_stats = MemoryStats(state_db)
    mem_checker = MemoryChecker(mem_stats, config)

    try:
        passed, name = mem_checker.run_check()
        if not passed:
            return EXIT_THRESHOLD_CROSSED, name
    except MemoryCheckerException as err:
        logger.log_error(f"Failure occurred {err}")
        return EXIT_FAILURE, ""

    return EXIT_SUCCESS, ""


if __name__ == "__main__":
    rc, component = main()
    print(component)
    sys.exit(rc)
