import click
import syslog
from swsscommon.swsscommon import ConfigDBConnector

# Default values
DEFAULT_SAMPLING_INTERVAL = 5  # Default sampling interval in minutes
DEFAULT_RETENTION_PERIOD = 15  # Default retention period in days


def log_to_syslog(message, level=syslog.LOG_INFO):
    """Log a message to syslog."""
    syslog.openlog("memory_statistics", syslog.LOG_PID | syslog.LOG_CONS, syslog.LOG_USER)
    syslog.syslog(level, message)


def update_memory_statistics_status(status, db):
    """Updates the status of the memory statistics feature in the config DB."""
    try:
        db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {"enabled": status})
        msg = f"Memory statistics feature {'enabled' if status == 'true' else 'disabled'} successfully."
        click.echo(msg)
        log_to_syslog(msg)
        return True, None  # Success
    except Exception as e:
        error_msg = f"Error updating memory statistics status: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return False, error_msg


@click.group()
def config():
    """Top-level 'config' command."""
    pass


@config.group(name='memory-stats')
def memory_stats():
    """Configure memory statistics."""
    pass


@memory_stats.command(name='enable')
def memory_stats_enable():
    """Enable memory statistics."""
    db = ConfigDBConnector()
    db.connect()
    success, error = update_memory_statistics_status("true", db)
    if not success:
        click.echo(error, err=True)
    else:
        reminder_msg = "Reminder: Please run 'config save' to persist changes."
        click.echo(reminder_msg)
        log_to_syslog(reminder_msg)


@memory_stats.command(name='disable')
def memory_stats_disable():
    """Disable memory statistics."""
    db = ConfigDBConnector()
    db.connect()
    success, error = update_memory_statistics_status("false", db)
    if not success:
        click.echo(error, err=True)
    else:
        reminder_msg = "Reminder: Please run 'config save' to persist changes."
        click.echo(reminder_msg)
        log_to_syslog(reminder_msg)


@memory_stats.command(name='sampling-interval')
@click.argument("interval", type=int)
def memory_stats_sampling_interval(interval):
    """Set sampling interval for memory statistics."""
    if not (3 <= interval <= 15):
        error_msg = "Error: Sampling interval must be between 3 and 15 minutes."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return

    db = ConfigDBConnector()
    db.connect()
    try:
        db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {"sampling_interval": interval})
        success_msg = f"Sampling interval set to {interval} minutes successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)
    except Exception as e:
        error_msg = f"Error setting sampling interval: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)


@memory_stats.command(name='retention-period')
@click.argument("period", type=int)
def memory_stats_retention_period(period):
    """Set retention period for memory statistics."""
    if not (1 <= period <= 30):
        error_msg = "Error: Retention period must be between 1 and 30 days."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)
        return

    db = ConfigDBConnector()
    db.connect()
    try:
        db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {"retention_period": period})
        success_msg = f"Retention period set to {period} days successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)
    except Exception as e:
        error_msg = f"Error setting retention period: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)


if __name__ == "__main__":
    config()
