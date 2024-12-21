import click
import syslog
from swsscommon.swsscommon import ConfigDBConnector

MEMORY_STATISTICS_TABLE = "MEMORY_STATISTICS"
MEMORY_STATISTICS_KEY = "memory_statistics"
SAMPLING_INTERVAL_MIN = 3
SAMPLING_INTERVAL_MAX = 15
RETENTION_PERIOD_MIN = 1
RETENTION_PERIOD_MAX = 30
DEFAULT_SAMPLING_INTERVAL = 5  # minutes
DEFAULT_RETENTION_PERIOD = 15  # days


def log_to_syslog(message, level=syslog.LOG_INFO):
    """Log a message to syslog."""
    syslog.openlog("memory_statistics", syslog.LOG_PID | syslog.LOG_CONS, syslog.LOG_USER)
    syslog.syslog(level, message)


def get_db_connection():
    """Create and return a database connection."""
    db = ConfigDBConnector()
    db.connect()
    return db


def update_memory_statistics_status(status, db):
    """
    Updates the status of the memory statistics feature in the config DB.
    Returns a tuple of (success, error_message).
    """
    try:
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
    """Memory statistics configuration tool."""
    pass


@cli.group()
def config():
    """Configuration commands."""
    pass


@config.group(name='memory-stats')
def memory_stats():
    """Configure memory statistics."""
    pass


@memory_stats.command(name='enable')
def memory_stats_enable():
    """Enable memory statistics collection."""
    db = get_db_connection()
    success, error = update_memory_statistics_status("true", db)
    if success:
        click.echo("Reminder: Please run 'config save' to persist changes.")
        log_to_syslog("Memory statistics enabled. Reminder to run 'config save'")


@memory_stats.command(name='disable')
def memory_stats_disable():
    """Disable memory statistics collection."""
    db = get_db_connection()
    success, error = update_memory_statistics_status("false", db)
    if success:
        click.echo("Reminder: Please run 'config save' to persist changes.")
        log_to_syslog("Memory statistics disabled. Reminder to run 'config save'")


@memory_stats.command(name='sampling-interval')
@click.argument("interval", type=int)
def memory_stats_sampling_interval(interval):
    """
    Set sampling interval for memory statistics.

    The sampling interval must be between 3 and 15 minutes.
    This determines how frequently memory usage data is collected.
    """
    if not (SAMPLING_INTERVAL_MIN <= interval <= SAMPLING_INTERVAL_MAX):
        error_msg = (
            f"Error: Sampling interval must be between {SAMPLING_INTERVAL_MIN} "
            f"and {SAMPLING_INTERVAL_MAX} minutes."
        )
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return

    db = get_db_connection()
    try:
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
    """
    Set retention period for memory statistics.

    The retention period must be between 1 and 30 days.
    This determines how long memory usage data is stored before being purged.
    """
    if not (RETENTION_PERIOD_MIN <= period <= RETENTION_PERIOD_MAX):
        error_msg = f"Error: Retention period must be between {RETENTION_PERIOD_MIN} and {RETENTION_PERIOD_MAX} days."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return

    db = get_db_connection()
    try:
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
