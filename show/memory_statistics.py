import sys
import socket
import json
import click
import syslog
import time
import os
from typing import Dict, Any, Union
from dataclasses import dataclass


@dataclass
class Config:
    SOCKET_PATH: str = '/var/run/dbus/memstats.socket'
    SOCKET_TIMEOUT: int = 30
    BUFFER_SIZE: int = 8192
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0


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


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Main entry point for the SONiC Memory Statistics CLI."""
    ctx.ensure_object(dict)


@click.group()
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
@click.pass_context
def memory_stats(ctx: click.Context, from_time: str, to_time: str, select_metric: str) -> None:
    """Displays memory statistics."""
    try:
        display_statistics(ctx, from_time, to_time, select_metric)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


def display_statistics(ctx: click.Context, from_time: str, to_time: str, select_metric: str) -> None:
    """Retrieves and displays memory statistics."""
    request_data = {
        "type": "system",
        "metric_name": select_metric,
        "from": from_time,
        "to": to_time
    }

    try:
        response = send_data("memory_statistics_command_request_handler", request_data)
        if isinstance(response, Dict2Obj):
            clean_and_print(response.to_dict())
        else:
            error_msg = f"Unexpected response type: {type(response)}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise click.ClickException(error_msg)
    except Exception as e:
        error_msg = f"Failed to retrieve memory statistics: {str(e)}"
        syslog.syslog(syslog.LOG_ERR, error_msg)
        raise click.ClickException(error_msg)


def clean_and_print(data: Dict[str, Any]) -> None:
    """Formats and prints memory statistics."""
    if isinstance(data, dict):
        memory_stats = data.get("data", "")
        cleaned_output = memory_stats.replace("\n", "\n").strip()
        print(f"Memory Statistics:\n{cleaned_output}")
    else:
        error_msg = "Invalid data format received"
        syslog.syslog(syslog.LOG_ERR, error_msg)
        print(f"Error: {error_msg}")


def main():
    """Entry point for the CLI application."""
    cli.add_command(show)
    cli()


if __name__ == '__main__':
    valid_commands = ['show']
    user_input = sys.argv[1:]
    if user_input:
        command = user_input[0]
        if command not in valid_commands:
            error_msg = f"Error: Invalid command '{command}'."
            syslog.syslog(syslog.LOG_ERR, error_msg)
            raise click.UsageError(error_msg)
    main()
