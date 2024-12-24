# Standard library imports
import json
import os
import signal
import socket
import sys
import syslog
import time
from typing import Any, Dict, Union

# Third-party library imports
import click
from dataclasses import dataclass

# Local application/library imports
from swsscommon.swsscommon import ConfigDBConnector


@dataclass
class Config:
    SOCKET_PATH: str = '/var/run/dbus/memstats.socket'
    SOCKET_TIMEOUT: int = 30
    BUFFER_SIZE: int = 8192
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    DEFAULT_CONFIG = {
        "enabled": "false",
        "sampling_interval": "5",
        "retention_period": "15"
    }


class ConnectionError(Exception):
    """Custom exception for connection-related errors."""
    pass


class Dict2Obj:
    """Converts dictionaries or lists into objects with attribute-style access."""
    def __init__(self, d: Union[Dict[str, Any], list]) -> None:
        if not isinstance(d, (dict, list)):
            raise ValueError("Input should be a dictionary or a list")

        if isinstance(d, dict):
            for key, value in d.items():
                if isinstance(value, (list, tuple)):
                    setattr(
                        self,
                        key,
                        [Dict2Obj(x) if isinstance(x, dict) else x for x in value],
                    )
                else:
                    setattr(
                        self, key, Dict2Obj(value) if isinstance(value, dict) else value
                    )
        elif isinstance(d, list):
            self.items = [Dict2Obj(x) if isinstance(x, dict) else x for x in d]

    def to_dict(self) -> Dict[str, Any]:
        """Converts the object back to a dictionary format."""
        result = {}
        if hasattr(self, "items"):
            return [x.to_dict() if isinstance(x, Dict2Obj) else x for x in self.items]

        for key in self.__dict__:
            value = getattr(self, key)
            if isinstance(value, Dict2Obj):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [v.to_dict() if isinstance(v, Dict2Obj) else v for v in value]
            else:
                result[key] = value
        return result

    def __repr__(self) -> str:
        """Provides a string representation of the object for debugging."""
        return f"<{self.__class__.__name__} {self.to_dict()}>"


class SonicDBConnector:
    """Handles interactions with SONiC's configuration database with improved connection handling."""
    def __init__(self) -> None:
        """Initialize the database connector with retry mechanism."""
        self.config_db = ConfigDBConnector()
        self.connect_with_retry()

    def connect_with_retry(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """
        Attempts to connect to the database with a retry mechanism.
        """
        retries = 0
        last_error = None

        while retries < max_retries:
            try:
                self.config_db.connect()
                syslog.syslog(syslog.LOG_INFO, "Successfully connected to SONiC config database")
                return
            except Exception as e:
                last_error = e
                retries += 1
                if retries < max_retries:
                    syslog.syslog(syslog.LOG_WARNING,
                                f"Failed to connect to database (attempt {retries}/{max_retries}): {str(e)}")
                    time.sleep(retry_delay)

        error_msg = (
            f"Failed to connect to SONiC config database after {max_retries} attempts. "
            f"Last error: {str(last_error)}"
        )
        syslog.syslog(syslog.LOG_ERR, error_msg)
        raise ConnectionError(error_msg)

    def get_memory_statistics_config(self) -> Dict[str, str]:
        """
        Retrieves memory statistics configuration with error handling.
        """
        try:
            config = self.config_db.get_table('MEMORY_STATISTICS')
            if not isinstance(config, dict) or 'memory_statistics' not in config:
                return Config.DEFAULT_CONFIG.copy()
            
            # Handle invalid configurations by merging with defaults
            current_config = config.get('memory_statistics', {})
            if not isinstance(current_config, dict):
                return Config.DEFAULT_CONFIG.copy()

            result_config = Config.DEFAULT_CONFIG.copy()
            # Only update with valid values from current config
            for key, value in current_config.items():
                if value is not None and value != "":
                    result_config[key] = value

            return result_config

        except Exception as e:
            error_msg = f"Error retrieving memory statistics configuration: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise RuntimeError(error_msg)


class SocketManager:
    """Manages Unix domain socket connections with improved reliability."""
    def __init__(self, socket_path: str = Config.SOCKET_PATH):
        self.socket_path = socket_path
        self.sock = None
        self._validate_socket_path()

    def _validate_socket_path(self) -> None:
        """Validates the socket path exists or can be created."""
        socket_dir = os.path.dirname(self.socket_path)
        if not os.path.exists(socket_dir):
            error_msg = f"Socket directory {socket_dir} does not exist"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise ConnectionError(error_msg)

    def connect(self) -> None:
        """Establishes socket connection with improved error handling."""
        retries = 0
        last_error = None

        while retries < Config.MAX_RETRIES:
            try:
                if self.sock:
                    self.close()

                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(Config.SOCKET_TIMEOUT)
                self.sock.connect(self.socket_path)
                syslog.syslog(syslog.LOG_INFO, "Successfully connected to memory statistics service")
                return
            except socket.error as e:
                last_error = e
                retries += 1
                if retries < Config.MAX_RETRIES:
                    syslog.syslog(syslog.LOG_WARNING,
                                  f"Failed to connect to socket (attempt {retries}/{Config.MAX_RETRIES}): {str(e)}")
                    time.sleep(Config.RETRY_DELAY)
                self.close()

        error_msg = (
            f"Failed to connect to memory statistics service after {Config.MAX_RETRIES} "
            f"attempts. Last error: {str(last_error)}. "
            f"Please verify that the service is running and socket file exists at {self.socket_path}"
        )
        syslog.syslog(syslog.LOG_ERR, error_msg)
        raise ConnectionError(error_msg)

    def receive_all(self) -> str:
        """Receives all data with improved error handling."""
        if not self.sock:
            raise ConnectionError("No active socket connection")

        chunks = []
        while True:
            try:
                chunk = self.sock.recv(Config.BUFFER_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
            except socket.timeout:
                error_msg = f"Socket operation timed out after {Config.SOCKET_TIMEOUT} seconds"
                syslog.syslog(syslog.LOG_ERR, error_msg)
                raise ConnectionError(error_msg)
            except socket.error as e:
                error_msg = f"Socket error during receive: {str(e)}"
                syslog.syslog(syslog.LOG_ERR, error_msg)
                raise ConnectionError(error_msg)

        return b''.join(chunks).decode('utf-8')

    def send(self, data: str) -> None:
        """Sends data with improved error handling."""
        if not self.sock:
            raise ConnectionError("No active socket connection")

        try:
            self.sock.sendall(data.encode('utf-8'))
        except socket.error as e:
            error_msg = f"Failed to send data: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise ConnectionError(error_msg)

    def close(self) -> None:
        """Closes the socket connection safely."""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                syslog.syslog(syslog.LOG_WARNING, f"Error closing socket: {str(e)}")
            finally:
                self.sock = None


def send_data(command: str, data: Dict[str, Any], quiet: bool = False) -> Dict2Obj:
    """Sends a command and data to the memory statistics service."""
    socket_manager = SocketManager()

    try:
        socket_manager.connect()
        request = {"command": command, "data": data}
        socket_manager.sock.sendall(json.dumps(request).encode('utf-8'))

        response = socket_manager.receive_all()
        if not response:
            raise ConnectionError("No response received from memory statistics service")

        try:
            jdata = json.loads(response)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse server response: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise ValueError(error_msg)

        if not isinstance(jdata, dict):
            raise ValueError("Invalid response format from server")

        response_obj = Dict2Obj(jdata)
        if not getattr(response_obj, 'status', True):
            error_msg = getattr(response_obj, 'msg', 'Unknown error occurred')
            raise RuntimeError(error_msg)

        return response_obj

    except Exception as e:
        if not quiet:
            click.echo(f"Error: {str(e)}", err=True)
        raise
    finally:
        socket_manager.close()


def format_field_value(field_name: str, value: str) -> str:
    """Formats configuration field values for display."""
    if field_name == "enabled":
        return "True" if value.lower() == "true" else "False"
    return value if value != "Unknown" else "Not configured"


def display_config(db_connector: SonicDBConnector) -> None:
    """Displays memory statistics configuration."""
    try:
        config = db_connector.get_memory_statistics_config()
        enabled = format_field_value("enabled", config.get("enabled", "Unknown"))
        retention = format_field_value("retention_period", config.get("retention_period", "Unknown"))
        sampling = format_field_value("sampling_interval", config.get("sampling_interval", "Unknown"))

        click.echo(f"{'Configuration Field':<30}{'Value'}")
        click.echo("-" * 50)
        click.echo(f"{'Enabled':<30}{enabled}")
        click.echo(f"{'Retention Time (days)':<30}{retention}")
        click.echo(f"{'Sampling Interval (minutes)':<30}{sampling}")
    except Exception as e:
        error_msg = f"Failed to retrieve configuration: {str(e)}"
        syslog.syslog(syslog.LOG_ERR, error_msg)
        raise click.ClickException(error_msg)

@click.group()
def cli():
    """Main entry point for the SONiC Memory Statistics CLI."""
    pass


@cli.group()
def show():
    """Show commands for memory statistics."""
    pass

@show.command(name="memory-stats")
@click.option(
    '--from', 'from_time',
    help='Start time for memory statistics (e.g., "15 hours ago", "7 days ago", "ISO Format")'
)
@click.option(
    '--to', 'to_time',
    help='End time for memory statistics (e.g., "now", "ISO Format")'
)
@click.option(
    '--select', 'select_metric',
    help='Show statistics for specific metric (e.g., total_memory, used_memory)'
)
def show_statistics(from_time: str, to_time: str, select_metric: str):
    """Display memory statistics."""
    try:
        request_data = {
            "type": "system",
            "metric_name": select_metric,
            "from": from_time,
            "to": to_time
        }

        response = send_data("memory_statistics_command_request_handler", request_data)
        stats_data = response.to_dict()

        if isinstance(stats_data, dict):
            memory_stats = stats_data.get("data", "")
            if memory_stats:
                cleaned_output = memory_stats.replace("\n", "\n").strip()
                click.echo(f"Memory Statistics:\n{cleaned_output}")
            else:
                click.echo("No memory statistics data available.")
        else:
            click.echo("Error: Invalid data format received")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)

@show.command(name="memory-stats-config")
def show_configuration():
    """Display memory statistics configuration."""
    try:
        db_connector = SonicDBConnector()
        display_config(db_connector)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)

def cleanup_resources():
    """Performs cleanup of resources before shutdown."""
    try:
        if hasattr(cleanup_resources, 'db_connector'):
            del cleanup_resources.db_connector
        
        if hasattr(cleanup_resources, 'socket_manager'):
            cleanup_resources.socket_manager.close()
            
        syslog.syslog(syslog.LOG_INFO, "Successfully cleaned up resources during shutdown")
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error during cleanup: {str(e)}")

def shutdown_handler(signum: int, frame) -> None:
    """
    Signal handler for graceful shutdown.
    Handles SIGTERM signal with proper resource cleanup.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    try:
        syslog.syslog(syslog.LOG_INFO, "Received SIGTERM signal, initiating graceful shutdown...")
        cleanup_resources()
        click.echo("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error during shutdown: {str(e)}")
        sys.exit(1)

def main():
    """Main entry point with enhanced error handling and shutdown management."""
    try:
        # Register SIGTERM handler only
        signal.signal(signal.SIGTERM, shutdown_handler)
        
        # Store resources that need cleanup
        cleanup_resources.db_connector = None
        cleanup_resources.socket_manager = None
        
        cli()
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Fatal error in main: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)
        cleanup_resources()
        sys.exit(1)

if __name__ == '__main__':
    main()
