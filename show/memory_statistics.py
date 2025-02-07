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

# Local imports
from swsscommon.swsscommon import ConfigDBConnector


@dataclass
class Config:
    """
    Configuration class to manage the settings for memory statistics service and socket.

    Attributes:
        SOCKET_PATH (str): The path to the Unix domain socket for communication.
        SOCKET_TIMEOUT (int): The timeout value in seconds for socket operations.
        BUFFER_SIZE (int): The buffer size for socket communication.
        MAX_RETRIES (int): Maximum number of retry attempts for socket connection.
        RETRY_DELAY (float): Delay in seconds between retry attempts.
        DEFAULT_CONFIG (dict): Default configuration for memory statistics, including enabled status,
                               sampling interval, and retention period.
    """

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
    """
    Custom exception raised for connection-related errors in the system.

    This exception is used to signal issues with network connections or socket communications.
    """
    pass


class DatabaseError(Exception):
    """
    Custom exception raised for errors related to database interactions.

    This exception is used to signal issues with retrieving or updating data in the SONiC configuration database.
    """
    pass


class Dict2Obj:
    """
    A utility class that converts dictionaries or lists into objects, providing attribute-style access.

    This class is helpful when you need to convert JSON-like data (dictionaries or lists) into Python objects
    with attributes that can be accessed using dot notation, and vice versa.

    Methods:
        __init__(d): Initializes the object either from a dictionary or list.
        _init_from_dict(d): Initializes the object from a dictionary.
        _init_from_list(d): Initializes the object from a list.
        to_dict(): Converts the object back to a dictionary format.
        __repr__(): Returns a string representation of the object for debugging purposes.
    """

    def __init__(self, d: Union[Dict[str, Any], list]) -> None:
        if isinstance(d, dict):
            self._init_from_dict(d)
        elif isinstance(d, list):
            self._init_from_list(d)
        else:
            raise ValueError("Input should be a dictionary or a list")

    def _init_from_dict(self, d: Dict[str, Any]) -> None:
        for key, value in d.items():
            if isinstance(value, (list, tuple)):
                setattr(self, key, [Dict2Obj(x) if isinstance(x, dict) else x for x in value])
            else:
                setattr(self, key, Dict2Obj(value) if isinstance(value, dict) else value)

    def _init_from_list(self, d: list) -> None:
        self.items = [Dict2Obj(x) if isinstance(x, dict) else x for x in d]

    def to_dict(self) -> Dict[str, Any]:
        """Converts the object back to a dictionary format."""
        if hasattr(self, "items"):
            return [x.to_dict() if isinstance(x, Dict2Obj) else x for x in self.items]

        result = {}
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
    """
    A class that handles interactions with the SONiC configuration database, including connection retries and error handling.

    This class ensures robust connection management by retrying failed attempts to connect to the database
    and provides methods for fetching memory statistics configuration.

    Methods:
        __init__(): Initializes the connector and attempts to connect to the database.
        _connect_with_retry(): Attempts to connect to the database with a retry mechanism.
        get_memory_statistics_config(): Retrieves the memory statistics configuration from the database.
    """

    def __init__(self) -> None:
        self.config_db = ConfigDBConnector()
        self._connect_with_retry()

    def _connect_with_retry(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """
        Attempts to connect to the SONiC configuration database with a retry mechanism.

        This function will attempt to connect to the database up to `max_retries` times, with a delay of `retry_delay` seconds
        between each attempt. If the connection fails after all retries, a `ConnectionError` is raised.

        Args:
            max_retries (int): Maximum number of retries before raising a `ConnectionError` (default is 3).
            retry_delay (float): Delay in seconds between retries (default is 1.0).

        Raises:
            ConnectionError: If the connection to the database fails after all retries.
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                self.config_db.connect()
                syslog.syslog(syslog.LOG_INFO, "Successfully connected to SONiC config database")
                return
            except (socket.error, IOError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    syslog.syslog(
                        syslog.LOG_WARNING,
                        f"Failed to connect to database (attempt {attempt + 1}/{max_retries}): {str(e)}"
                    )
                    time.sleep(retry_delay)
                else:
                    raise ConnectionError(
                        f"Failed to connect to SONiC config database after {max_retries} attempts: {str(e)}"
                    ) from e

    def get_memory_statistics_config(self) -> Dict[str, str]:
        """
        Retrieves the memory statistics configuration from the SONiC configuration database.

        This function fetches the memory statistics configuration from the database, providing default values if not found or if 
        there are any errors. It handles potential errors and logs them.

        Returns:
            Dict[str, str]: The memory statistics configuration as a dictionary.

        Raises:
            DatabaseError: If there is an error while retrieving the configuration from the database.
        """
        try:
            config = self.config_db.get_table('MEMORY_STATISTICS')
            if not isinstance(config, dict) or 'memory_statistics' not in config:
                return Config.DEFAULT_CONFIG.copy()

            current_config = config.get('memory_statistics', {})
            if not isinstance(current_config, dict):
                return Config.DEFAULT_CONFIG.copy()

            result_config = Config.DEFAULT_CONFIG.copy()
            for key, value in current_config.items():
                if value is not None and value != "":
                    result_config[key] = value

            return result_config

        except (KeyError, ValueError) as e:
            error_msg = f"Error retrieving memory statistics configuration: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise DatabaseError(error_msg) from e


class SocketManager:
    """
    A class that manages Unix domain socket connections for communication with the memory statistics service.

    This class ensures proper socket validation, connection retries, and error handling, while maintaining secure
    socket file permissions and ownership.

    Methods:
        __init__(socket_path): Initializes the socket manager and validates the socket file.
        _validate_socket_path(create_if_missing): Validates the socket file path, checking permissions and ownership.
        connect(): Establishes a connection to the memory statistics service via Unix domain socket.
        receive_all(expected_size, max_attempts): Receives all data from the socket with error handling.
        send(data): Sends data to the socket.
        close(): Closes the socket connection safely.
    """

    def __init__(self, socket_path: str = Config.SOCKET_PATH):
        self.socket_path = socket_path
        self.sock = None
        self._validate_socket_path(create_if_missing=True)

    def _validate_socket_path(self, create_if_missing: bool = False) -> None:
        """
        Validates the socket file path and checks for the necessary permissions and ownership.

        This function checks if the socket file exists and has the correct permissions (0o600), and that it is owned by root.
        If the file does not exist and `create_if_missing` is `True`, the socket file is created. If the file exists with
        incorrect permissions, a `PermissionError` is raised.

        Args:
            create_if_missing (bool): Whether to create the socket file if it does not exist (default is False).

        Raises:
            ConnectionError: If the socket directory or file is missing or not accessible.
            PermissionError: If the socket file has incorrect permissions or ownership.
        """
        socket_dir = os.path.dirname(self.socket_path)
        if not os.path.exists(socket_dir):
            raise ConnectionError(f"Socket directory {socket_dir} does not exist")

        if not os.path.exists(self.socket_path):
            if create_if_missing:
                syslog.syslog(syslog.LOG_INFO, f"Socket file {self.socket_path} does not exist, creating it.")
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.bind(self.socket_path)
                os.chmod(self.socket_path, 0o600)
                return
            else:
                raise ConnectionError(f"Socket file {self.socket_path} not found")

        try:
            socket_stat = os.stat(self.socket_path)
            permissions = oct(socket_stat.st_mode & 0o777)
            syslog.syslog(syslog.LOG_INFO, f"Socket permissions: {permissions}")

            if socket_stat.st_mode & 0o777 != 0o600:
                raise PermissionError(f"Insecure socket file permissions: {permissions}")

            if socket_stat.st_uid != 0:
                raise PermissionError(f"Socket not owned by root: {self.socket_path}")

        except FileNotFoundError:
            raise ConnectionError(f"Socket file {self.socket_path} not found")

    def connect(self) -> None:
        """
        Establishes a Unix domain socket connection with improved error handling.

        This function attempts to establish a connection to the memory statistics service via a Unix domain socket. It will retry 
        the connection up to `Config.MAX_RETRIES` times with a delay of `Config.RETRY_DELAY` seconds between attempts.

        Raises:
            ConnectionError: If the connection fails after the maximum number of retries.
        """
        retries = 0
        last_error = None

        syslog.syslog(syslog.LOG_INFO, f"Attempting socket connection from PID {os.getpid()}")

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
                    syslog.syslog(
                        syslog.LOG_WARNING,
                        f"Socket connection attempt {retries} failed: {str(e)}"
                    )
                    time.sleep(Config.RETRY_DELAY)
                else:
                    raise ConnectionError(
                        f"Failed to connect to memory statistics service after {Config.MAX_RETRIES} attempts: {str(e)}"
                    ) from e

    def receive_all(self, expected_size: int, max_attempts: int = 100) -> str:
        """
        Receives all data from the socket until the expected size is reached.

        This function ensures that the complete data is received from the socket. If the expected size is not reached within
        the specified number of attempts, it raises an exception. It also handles timeout and socket errors.

        Args:
            expected_size (int): The expected size of the data to receive.
            max_attempts (int): Maximum number of attempts to receive the data (default is 100).

        Returns:
            str: The received data as a string.

        Raises:
            ConnectionError: If the socket operation times out or encounters an error.
        """
        if not self.sock:
            raise ConnectionError("No active socket connection")

        data = b""
        attempts = 0

        while len(data) < expected_size and attempts < max_attempts:
            try:
                chunk = self.sock.recv(expected_size - len(data))
                if not chunk:
                    break
                data += chunk
            except socket.timeout as e:
                error_msg = f"Socket operation timed out after {Config.SOCKET_TIMEOUT} seconds"
                syslog.syslog(syslog.LOG_ERR, error_msg)
                raise ConnectionError(error_msg) from e
            except socket.error as e:
                error_msg = f"Socket error during receive: {str(e)}"
                syslog.syslog(syslog.LOG_ERR, error_msg)
                raise ConnectionError(error_msg) from e
            
            attempts += 1

        if len(data) < expected_size:
            syslog.syslog(syslog.LOG_WARNING, "Received incomplete data, possible socket issue.")

        try:
            return data.decode('utf-8')
        except UnicodeDecodeError as e:
            error_msg = f"Failed to decode received data: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise ConnectionError(error_msg) from e

    def send(self, data: str) -> None:
        """
        Sends data over the socket with improved error handling.

        This function sends data through the socket. It raises a `ConnectionError` if the data cannot be sent due to socket issues.

        Args:
            data (str): The data to send.

        Raises:
            ConnectionError: If there is an error while sending the data.
        """
        if not self.sock:
            raise ConnectionError("No active socket connection")

        try:
            self.sock.sendall(data.encode('utf-8'))
        except socket.error as e:
            error_msg = f"Failed to send data: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise ConnectionError(error_msg) from e

    def close(self) -> None:
        """
        Closes the socket connection safely.

        This function safely closes the socket connection and ensures that the socket is properly cleaned up.

        Raises:
            Exception: If there is an error closing the socket.
        """
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                syslog.syslog(syslog.LOG_WARNING, f"Error closing socket: {str(e)}")
            finally:
                self.sock = None


class ResourceManager:
    """
    A class that manages the cleanup of resources during shutdown.

    This class ensures that the necessary resources, including database connectors and socket connections, are
    properly cleaned up to avoid resource leaks and maintain system integrity.

    Methods:
        __init__(): Initializes the resource manager.
        cleanup(): Performs cleanup of resources, including database connectors and socket managers.
    """

    def __init__(self):
        self.db_connector = None
        self.socket_manager = None

    def cleanup(self):
        """
        Performs cleanup of resources during shutdown.

        This function cleans up all resources, including database connectors and socket connections, ensuring proper shutdown.

        Raises:
            None
        """
        if self.db_connector:
            del self.db_connector
        if self.socket_manager:
            self.socket_manager.close()
        syslog.syslog(syslog.LOG_INFO, "Successfully cleaned up resources during shutdown")


def send_data(command: str, data: Dict[str, Any], quiet: bool = False) -> Dict2Obj:
    """Sends a command and data to the memory statistics service.

        Time format for statistics retrieval are given below.
            - Relative time formats:
            - 'X days ago', 'X hours ago', 'X minutes ago'
            - 'yesterday', 'today'
            - Specific times and dates:
            - 'now'
            - 'July 23', 'July 23, 2024', '2 November 2024'
            - '7/24', '1/2'
            - Time expressions:
            - '2 am', '3:15 pm'
            - 'Aug 01 06:43:40', 'July 1 3:00:00'
            - Named months:
            - 'jan', 'feb', 'march', 'september', etc.
            - Full month names: 'January', 'February', 'March', etc.
            - ISO 8601 format (e.g., '2024-07-01T15:00:00')

    Args:
        command (str): The command to send to the service.
        data (Dict[str, Any]): The data payload to send with the command.
        quiet (bool): If True, suppresses error messages. Defaults to False.

    Returns:
        Dict2Obj: The response from the service as an object.

    Raises:
        ConnectionError: If there is an issue with the socket connection.
        ValueError: If the response cannot be parsed or is invalid.
        DatabaseError: If the service returns an error status.
    """
    socket_manager = SocketManager()

    try:
        socket_manager.connect()
        request = {"command": command, "data": data}
        socket_manager.send(json.dumps(request))

        response = socket_manager.receive_all(expected_size=Config.BUFFER_SIZE)
        if not response:
            raise ConnectionError("No response received from memory statistics service")

        try:
            jdata = json.loads(response)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse server response: {str(e)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise ValueError(error_msg) from e

        if not isinstance(jdata, dict):
            raise ValueError("Invalid response format from server")

        response_obj = Dict2Obj(jdata)
        if not getattr(response_obj, 'status', True):
            error_msg = getattr(response_obj, 'msg', 'Unknown error occurred')
            raise DatabaseError(error_msg) from None

        return response_obj

    except Exception as e:
        if not quiet:
            click.echo(f"Error: {str(e)}", err=True)
        raise
    finally:
        socket_manager.close()


def format_field_value(field_name: str, value: str) -> str:
    """Formats configuration field values for display.

    Args:
        field_name (str): The name of the configuration field.
        value (str): The value of the configuration field.

    Returns:
        str: The formatted value for display.
    """
    if field_name == "enabled":
        return "True" if value.lower() == "true" else "False"
    return value if value != "Unknown" else "Not configured"


def display_config(db_connector: SonicDBConnector) -> None:
    """Displays memory statistics configuration.

    Args:
        db_connector (SonicDBConnector): The database connector to retrieve configuration.

    Raises:
        click.ClickException: If there is an error retrieving the configuration.
    """
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
    """Display memory statistics.

    Args:
        from_time (str): Start time for memory statistics (e.g., "15 hours ago", "7 days ago", "ISO Format").
        to_time (str): End time for memory statistics (e.g., "now", "ISO Format").
        select_metric (str): Specific metric to show statistics for (e.g., total_memory, used_memory).

    Raises:
        Exception: If there is an error retrieving or displaying the statistics.
    """
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
    """Display memory statistics configuration.

    Raises:
        Exception: If there is an error retrieving or displaying the configuration.
    """
    try:
        db_connector = SonicDBConnector()
        display_config(db_connector)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


def shutdown_handler(signum: int, frame, resource_manager: ResourceManager) -> None:
    """Signal handler for graceful shutdown.

    Args:
        signum (int): Signal number.
        frame: Current stack frame.
        resource_manager (ResourceManager): ResourceManager instance for cleanup.

    Raises:
        Exception: If there is an error during shutdown.
    """
    try:
        syslog.syslog(syslog.LOG_INFO, "Received SIGTERM signal, initiating graceful shutdown...")
        resource_manager.cleanup()
        click.echo("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error during shutdown: {str(e)}")
        sys.exit(1)


def main():
    """Main entry point with enhanced error handling and shutdown management.

    Raises:
        Exception: If there is a fatal error during execution.
    """
    resource_manager = ResourceManager()

    try:
        signal.signal(signal.SIGTERM, lambda signum, frame: shutdown_handler(signum, frame, resource_manager))
        cli()
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Fatal error in main: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)
        resource_manager.cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()
