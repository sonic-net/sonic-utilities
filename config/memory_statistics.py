import syslog

import click
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


def log_to_syslog(message, level=syslog.LOG_INFO):
    """Log a message to syslog.

    This function logs the provided message to syslog at the specified level.
    It opens the syslog with the application name 'memory_statistics' and the
    appropriate log level, ensuring the connection is closed after logging.

    Args:
        message (str): The message to log.
        level (int): The syslog log level.
    """
    try:
        syslog.openlog("memory_statistics", syslog.LOG_PID | syslog.LOG_CONS, syslog.LOG_USER)
        syslog.syslog(level, message)
    finally:
        syslog.closelog()


class MemoryStatisticsDB:
    """Singleton class to handle memory statistics database connection.

    This class ensures only one instance of the database connection exists using
    the Singleton pattern. It provides access to the database connection and
    ensures that it is created only once during the application's lifetime.
    """
    _instance = None
    _db = None

    def __new__(cls):
        """Ensure only one instance of MemoryStatisticsDB is created.

        This method implements the Singleton pattern to guarantee that only one
        instance of the MemoryStatisticsDB class exists. If no instance exists,
        it creates one and connects to the database.

        Returns:
            MemoryStatisticsDB: The singleton instance of the class.
        """
        if cls._instance is None:
            cls._instance = super(MemoryStatisticsDB, cls).__new__(cls)
            cls._db = ConfigDBConnector()
            cls._db.connect()
        return cls._instance

    @classmethod
    def get_db(cls):
        """Get the singleton database connection instance.

        Returns the existing database connection instance. If it doesn't exist,
        a new instance is created by calling the __new__ method.

        Returns:
            ConfigDBConnector: The database connection instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._db


def update_memory_statistics_status(status):
    """
    Update the status of the memory statistics feature in the config DB.

    This function modifies the configuration database to enable or disable
    memory statistics collection based on the provided status. It also logs
    the action and returns a tuple indicating whether the operation was successful.

    Args:
        status (str): The status to set for memory statistics ("true" or "false").

    Returns:
        tuple: A tuple (success, error_message) where `success` is a boolean
               indicating whether the operation was successful, and
               `error_message` contains any error details if unsuccessful.
    """
    try:
        db = MemoryStatisticsDB.get_db()
        db.mod_entry(MEMORY_STATISTICS_TABLE, MEMORY_STATISTICS_KEY, {"enabled": status})
        msg = f"Memory statistics feature {'enabled' if status == 'true' else 'disabled'} successfully."
        click.echo(msg)
        log_to_syslog(msg)
        return True, None
    except Exception as e:
        error_msg = f"Error updating memory statistics status: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return False, error_msg


@click.group()
def cli():
    """Memory statistics configuration tool.

    This command-line interface (CLI) allows users to configure and manage
    memory statistics settings such as enabling/disabling the feature and
    modifying parameters like the sampling interval and retention period.
    """
    pass


@cli.group()
def config():
    """Configuration commands for managing memory statistics.

    Example:
        $ config memory-stats enable
        $ config memory-stats sampling-interval 5
    """
    pass


@config.group(name='memory-stats')
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
    success, error = update_memory_statistics_status("true")
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
    success, error = update_memory_statistics_status("false")
    if success:
        click.echo("Reminder: Please run 'config save' to persist changes.")
        log_to_syslog("Memory statistics disabled. Reminder to run 'config save'")


@memory_stats.command(name='sampling-interval')
@click.argument("interval", type=int)
def memory_stats_sampling_interval(interval):
    """Set the sampling interval for memory statistics.

    This command allows users to configure the frequency at which memory statistics
    are collected. The interval must be between 3 and 15 minutes.

    Args:
        interval (int): The sampling interval in minutes (must be between 3 and 15).

    Examples:
        Set sampling interval to 5 minutes:
        $ config memory-stats sampling-interval 5
        Sampling interval set to 5 minutes successfully.
        Reminder: Please run 'config save' to persist changes.

        Invalid interval example:
        $ config memory-stats sampling-interval 20
        Error: Sampling interval must be between 3 and 15 minutes.
    """
    if not (SAMPLING_INTERVAL_MIN <= interval <= SAMPLING_INTERVAL_MAX):
        error_msg = (
            f"Error: Sampling interval must be between {SAMPLING_INTERVAL_MIN} "
            f"and {SAMPLING_INTERVAL_MAX} minutes."
        )
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
    except Exception as e:
        error_msg = f"Error setting sampling interval: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)


@memory_stats.command(name='retention-period')
@click.argument("period", type=int)
def memory_stats_retention_period(period):
    """Set the retention period for memory statistics.

    This command allows users to configure how long memory statistics are retained
    before being purged. The retention period must be between 1 and 30 days.

    Args:
        period (int): The retention period in days (must be between 1 and 30).

    Examples:
        Set retention period to 7 days:
        $ config memory-stats retention-period 7
        Retention period set to 7 days successfully.
        Reminder: Please run 'config save' to persist changes.

        Invalid period example:
        $ config memory-stats retention-period 45
        Error: Retention period must be between 1 and 30 days.
    """
    if not (RETENTION_PERIOD_MIN <= period <= RETENTION_PERIOD_MAX):
        error_msg = f"Error: Retention period must be between {RETENTION_PERIOD_MIN} and {RETENTION_PERIOD_MAX} days."
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
    except Exception as e:
        error_msg = f"Error setting retention period: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)


if __name__ == "__main__":
    cli()
