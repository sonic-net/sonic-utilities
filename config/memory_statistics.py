import click
import syslog
from swsscommon.swsscommon import ConfigDBConnector

# Default values
DEFAULT_SAMPLING_INTERVAL = 5
DEFAULT_RETENTION_PERIOD = 15


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
        log_to_syslog(msg)  # Log to syslog
        return True, None  # Success: return True and no error
    except Exception as e:
        error_msg = f"Error updating memory statistics status: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)  # Log error to syslog
        return False, error_msg  # Failure: return False and the error message


@click.command()
def memory_statistics_enable():
    """Enable memory statistics."""
    db = ConfigDBConnector()
    db.connect()
    success, error = update_memory_statistics_status("true", db)
    if not success:
        click.echo(error, err=True)  # Handle error if unsuccessful
    else:
        success_msg = "Memory statistics enabled successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)  # Log to syslog
        reminder_msg = "Reminder: Please run 'config save' to persist changes."
        click.echo(reminder_msg)
        log_to_syslog(reminder_msg)  # Log to syslog


@click.command()
def memory_statistics_disable():
    """Disable memory statistics."""
    db = ConfigDBConnector()
    db.connect()
    success, error = update_memory_statistics_status("false", db)
    if not success:
        click.echo(error, err=True)  # Handle error if unsuccessful
    else:
        success_msg = "Memory statistics disabled successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)  # Log to syslog
        reminder_msg = "Reminder: Please run 'config save' to persist changes."
        click.echo(reminder_msg)
        log_to_syslog(reminder_msg)  # Log to syslog


@click.command()
@click.argument("retention_period", type=int, required=False, default=DEFAULT_RETENTION_PERIOD)
def memory_statistics_retention_period(retention_period):
    """Set retention period for memory statistics."""
    if not (1 <= retention_period <= 30):
        error_msg = "Error: Retention period must be between 1 and 30."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)  # Log error to syslog
        return

    db = ConfigDBConnector()
    db.connect()
    try:
        db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {"retention_period": retention_period})
        success_msg = f"Retention period set to {retention_period} successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)  # Log to syslog
    except Exception as e:
        error_msg = f"Error setting retention period: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)  # Log error to syslog


@click.command()
@click.argument("sampling_interval", type=int, required=False, default=DEFAULT_SAMPLING_INTERVAL)
def memory_statistics_sampling_interval(sampling_interval):
    """Set sampling interval for memory statistics."""
    if not (3 <= sampling_interval <= 15):
        error_msg = "Error: Sampling interval must be between 3 and 15."
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)  # Log error to syslog
        return

    db = ConfigDBConnector()
    db.connect()
    try:
        db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {"sampling_interval": sampling_interval})
        success_msg = f"Sampling interval set to {sampling_interval} successfully."
        click.echo(success_msg)
        log_to_syslog(success_msg)  # Log to syslog
    except Exception as e:
        error_msg = f"Error setting sampling interval: {e}"
        click.echo(error_msg, err=True)
        log_to_syslog(error_msg, syslog.LOG_ERR)  # Log error to syslog


def get_memory_statistics_table(db):
    """Retrieve MEMORY_STATISTICS table from config DB."""
    return db.get_table("MEMORY_STATISTICS")


def check_memory_statistics_table_existence(table):
    """Check if MEMORY_STATISTICS table exists in the given table."""
    return "memory_statistics" in table
