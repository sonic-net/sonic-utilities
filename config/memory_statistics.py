# Standard library imports
import syslog

# Third-party imports
import click

# Type hints
from typing import Tuple, Optional

# Local imports
from swsscommon.swsscommon import ConfigDBConnector

# Constants
MEMORY_STATISTICS_TABLE = "MEMORY_STATISTICS"
MEMORY_STATISTICS_KEY = "memory_statistics"

SAMPLING_INTERVAL_MIN = 3
SAMPLING_INTERVAL_MAX = 15
RETENTION_PERIOD_MIN = 1
RETENTION_PERIOD_MAX = 30

DEFAULT_SAMPLING_INTERVAL = 5  # minutes
DEFAULT_RETENTION_PERIOD = 15  # days

syslog.openlog("memory_statistics", syslog.LOG_PID | syslog.LOG_CONS, syslog.LOG_USER)


def log_to_syslog(message: str, level: int = syslog.LOG_INFO) -> None:
    """
    Logs a message to the system log (syslog).

    This function logs the provided message to syslog at the specified level.
    It opens the syslog with the application name 'memory_statistics' and the
    appropriate log level, ensuring the connection is closed after logging.

    Args:
        message (str): The message to log.
        level (int, optional): The log level (default is syslog.LOG_INFO).

    Raises:
        Exception: If syslog logging fails.
    """
    try:
        syslog.syslog(level, message)
    except Exception as e:
        click.echo(f"Failed to log to syslog: {e}", err=True)


def generate_error_message(error_type: str, error: Exception) -> str:
    """
    Generates a formatted error message for logging and user feedback.

    Args:
        error_type (str): A short description of the error type.
        error (Exception): The actual exception object.

    Returns:
        str: A formatted error message string.
    """
    return f"{error_type}: {error}"


def validate_range(value: int, min_val: int, max_val: int) -> bool:
    """
    Validates whether a given integer value falls within a specified range.

    Args:
        value (int): The value to validate.
        min_val (int): The minimum allowable value.
        max_val (int): The maximum allowable value.

    Returns:
        bool: True if the value is within range, False otherwise.
    """
    return min_val <= value <= max_val


class MemoryStatisticsDB:
    """
    Singleton class for managing the connection to the memory statistics configuration database.
    """
    _instance = None
    _db = None

    def __new__(cls):
        """
        Creates and returns a singleton instance of MemoryStatisticsDB.

        Returns:
            MemoryStatisticsDB: The singleton instance.
        """
        if cls._instance is None:
            cls._instance = super(MemoryStatisticsDB, cls).__new__(cls)
            cls._connect_db()
        return cls._instance

    @classmethod
    def _connect_db(cls):
        """
        Establishes a connection to the ConfigDB database.

        Logs an error if the connection fails.
        """
        try:
            cls._db = ConfigDBConnector()
            cls._db.connect()
        except RuntimeError as e:
            log_to_syslog(f"ConfigDB connection failed: {e}", syslog.LOG_ERR)
            cls._db = None

    @classmethod
    def get_db(cls):
        """
        Retrieves the database connection instance, reconnecting if necessary.

        Returns:
            ConfigDBConnector: The active database connection.

        Raises:
            RuntimeError: If the database connection is unavailable.
        """
        if cls._db is None:
            cls._connect_db()
        if cls._db is None:
            raise RuntimeError("Database connection unavailable")
        return cls._db


def update_memory_statistics_status(enabled: bool) -> Tuple[bool, Optional[str]]:
    """
    Updates the enable/disable status of memory statistics in the configuration database.

    This function modifies the configuration database to enable or disable
    memory statistics collection based on the provided status. It also logs
    the action and returns a tuple indicating whether the operation was successful.

    Args:
        enabled (bool): True to enable memory statistics, False to disable.

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing success status and an optional error message.
    """
    try:
        db = MemoryStatisticsDB.get_db()

        db.mod_entry(MEMORY_STATISTICS_TABLE, MEMORY_STATISTICS_KEY, {"enabled": str(enabled).lower()})
        msg = f"Memory statistics feature {'enabled' if enabled else 'disabled'} successfully."
        click.echo(msg)
        log_to_syslog(msg)
        return True, None
    except (KeyError, ConnectionError, RuntimeError) as e:
        error_msg = generate_error_message(f"Failed to {'enable' if enabled else 'disable'} memory statistics", e)

        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return False, error_msg
    except Exception as e:
        error_msg = generate_error_message("Unexpected error updating memory statistics status", e)

        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return False, error_msg


@click.group(help="Tool to manage memory statistics configuration.")
def cli():
    """
    Memory statistics configuration tool.

    This command-line interface (CLI) allows users to configure and manage
    memory statistics settings such as enabling/disabling the feature and
    modifying parameters like the sampling interval and retention period.
    """
    pass


@cli.group(help="Commands to configure system settings.")
def config():
    """
    Configuration commands for managing memory statistics.

    Example:
        $ config memory-stats enable
        $ config memory-stats sampling-interval 5
    """
    pass


@config.group(name='memory-stats', help="Manage memory statistics collection settings.")
def memory_stats():
    """Configure memory statistics collection and settings.

    This group contains commands to enable/disable memory statistics collection
    and configure related parameters.

    Examples:
        Enable memory statistics:
        $ config memory-stats enable

        Set sampling interval to 5 minutes:
        $ config memory-stats sampling-interval 5

        Set retention period to 7 days:
        $ config memory-stats retention-period 7

        Disable memory statistics:
        $ config memory-stats disable
    """
    pass


@memory_stats.command(name='enable')
def memory_stats_enable():
    """Enable memory statistics collection.

    This command enables the collection of memory statistics on the device.
    It updates the configuration and reminds the user to run 'config save'
    to persist changes.

    Example:
        $ config memory-stats enable
        Memory statistics feature enabled successfully.
        Reminder: Please run 'config save' to persist changes.
    """
    success, error = update_memory_statistics_status(True)
    if success:
        click.echo("Reminder: Please run 'config save' to persist changes.")
        log_to_syslog("Memory statistics enabled. Reminder to run 'config save'")


@memory_stats.command(name='disable')
def memory_stats_disable():
    """Disable memory statistics collection.

    This command disables the collection of memory statistics on the device.
    It updates the configuration and reminds the user to run 'config save'
    to persist changes.

    Example:
        $ config memory-stats disable
        Memory statistics feature disabled successfully.
        Reminder: Please run 'config save' to persist changes.
    """
    success, error = update_memory_statistics_status(False)
    if success:
        click.echo("Reminder: Please run 'config save' to persist changes.")
        log_to_syslog("Memory statistics disabled. Reminder to run 'config save'")


@memory_stats.command(name='sampling-interval')
@click.argument("interval", type=int)
def memory_stats_sampling_interval(interval: int):
    """
    Configure the sampling interval for memory statistics collection.

    This command updates the interval at which memory statistics are collected.
    The interval must be between 3 and 15 minutes.

    Args:
        interval (int): The desired sampling interval in minutes.

    Examples:
        Set sampling interval to 5 minutes:
        $ config memory-stats sampling-interval 5
        Sampling interval set to 5 minutes successfully.
        Reminder: Please run 'config save' to persist changes.

        Invalid interval example:
        $ config memory-stats sampling-interval 20
        Error: Sampling interval must be between 3 and 15 minutes.
    """
    if not validate_range(interval, SAMPLING_INTERVAL_MIN, SAMPLING_INTERVAL_MAX):
        error_msg = f"Error: Sampling interval must be between {SAMPLING_INTERVAL_MIN} and {SAMPLING_INTERVAL_MAX}."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return

    try:
        db = MemoryStatisticsDB.get_db()
        db.mod_entry(MEMORY_STATISTICS_TABLE, MEMORY_STATISTICS_KEY, {"sampling_interval": str(interval)})
        success_msg = f"Sampling interval set to {interval} minutes successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)
        click.echo("Reminder: Please run 'config save' to persist changes.")
    except (KeyError, ConnectionError, ValueError, RuntimeError) as e:
        error_msg = generate_error_message(f"{type(e).__name__} setting sampling interval", e)
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return
    except Exception as e:
        error_msg = generate_error_message("Unexpected error setting sampling interval", e)
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return


@memory_stats.command(name='retention-period')
@click.argument("period", type=int)
def memory_stats_retention_period(period: int):
    """
    Configure the retention period for memory statistics storage.

    This command sets the number of days memory statistics should be retained.
    The retention period must be between 1 and 30 days.

    Args:
        period (int): The desired retention period in days.

    Examples:
        Set retention period to 7 days:
        $ config memory-stats retention-period 7
        Retention period set to 7 days successfully.
        Reminder: Please run 'config save' to persist changes.

        Invalid period example:
        $ config memory-stats retention-period 45
        Error: Retention period must be between 1 and 30 days.
    """
    if not validate_range(period, RETENTION_PERIOD_MIN, RETENTION_PERIOD_MAX):
        error_msg = f"Error: Retention period must be between {RETENTION_PERIOD_MIN} and {RETENTION_PERIOD_MAX}."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return

    try:
        db = MemoryStatisticsDB.get_db()
        db.mod_entry(MEMORY_STATISTICS_TABLE, MEMORY_STATISTICS_KEY, {"retention_period": str(period)})
        success_msg = f"Retention period set to {period} days successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)
        click.echo("Reminder: Please run 'config save' to persist changes.")
    except (KeyError, ConnectionError, ValueError, RuntimeError) as e:
        error_msg = generate_error_message(f"{type(e).__name__} setting retention period", e)
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return
    except Exception as e:
        error_msg = generate_error_message("Unexpected error setting retention period", e)
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return


if __name__ == "__main__":
    try:
        cli()
    finally:
        syslog.closelog()
