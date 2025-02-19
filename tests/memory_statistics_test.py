import unittest
from unittest.mock import patch, MagicMock
import socket
import os
import click
from click.testing import CliRunner
import syslog
import pytest
import json
from unittest.mock import Mock

from show.memory_statistics import (
    Config,
    Dict2Obj,
    SonicDBConnector,
    SocketManager,
    send_data,
    display_config,
    display_statistics,
    main,
    show,
    format_field_value,
    clean_and_print,
    validate_command,
)


class TestDict2Obj(unittest.TestCase):
    """Test cases for Dict2Obj class"""
    def test_dict_conversion(self):
        """Test dictionary to object conversion"""
        test_dict = {
            "name": "test",
            "values": [1, 2, 3],
            "nested": {"key": "value"}
        }
        obj = Dict2Obj(test_dict)
        self.assertEqual(obj.name, "test")
        self.assertEqual(obj.values, [1, 2, 3])
        self.assertEqual(obj.nested.key, "value")

    def test_list_conversion(self):
        """Test list conversion"""
        test_list = [{"a": 1}, {"b": 2}]
        obj = Dict2Obj(test_list)
        self.assertEqual(obj.items[0].a, 1)
        self.assertEqual(obj.items[1].b, 2)

    def test_invalid_input(self):
        """Test invalid input handling"""
        with self.assertRaises(ValueError):
            Dict2Obj("invalid")

    def test_to_dict_conversion(self):
        """Test converting object back to dictionary"""
        test_dict = {
            "name": "test",
            "nested": {"key": "value"},
            "list": [{"item": 1}, {"item": 2}]
        }
        obj = Dict2Obj(test_dict)
        result = obj.to_dict()
        self.assertEqual(result, test_dict)

    def test_repr_method(self):
        """Test string representation of Dict2Obj"""
        test_dict = {"name": "test"}
        obj = Dict2Obj(test_dict)
        expected_repr = "<Dict2Obj {'name': 'test'}>"
        self.assertEqual(repr(obj), expected_repr)


class TestSonicDBConnector(unittest.TestCase):
    def setUp(self):
        self.mock_config_db = MagicMock()
        self.patcher = patch('show.memory_statistics.ConfigDBConnector',
                             return_value=self.mock_config_db)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('show.memory_statistics.ConfigDBConnector')  # Fixed import path
    def test_get_memory_statistics_config(self, mock_config_db):
        """Test retrieving memory statistics configuration"""
        test_config = {
            'memory_statistics': {
                'enabled': 'true',
                'retention_period': '7',
                'sampling_interval': '1'
            }
        }
        mock_config_db.return_value.get_table.return_value = test_config
        connector = SonicDBConnector()
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, test_config['memory_statistics'])

    @patch('show.memory_statistics.ConfigDBConnector')  # Fixed import path
    def test_get_default_config(self, mock_config_db):
        """Test retrieving default configuration when none exists"""
        mock_config_db.return_value.get_table.return_value = {}
        connector = SonicDBConnector()
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, Config.DEFAULT_CONFIG)

    def test_successful_connection(self):
        """Test successful database connection on first attempt"""
        SonicDBConnector()
        self.mock_config_db.connect.assert_called_once()

    def test_connection_retry_success(self):
        """Test successful connection after initial failures"""
        self.mock_config_db.connect.side_effect = [Exception("First try"), Exception("Second try"), None]
        SonicDBConnector()
        self.assertEqual(self.mock_config_db.connect.call_count, 3)

    def test_get_memory_statistics_config_success(self):
        """Test successful retrieval of memory statistics configuration"""
        test_config = {
            'memory_statistics': {
                'enabled': 'true',
                'retention_period': '7',
                'sampling_interval': '1'
            }
        }
        connector = SonicDBConnector()
        self.mock_config_db.get_table.return_value = test_config
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, test_config['memory_statistics'])

    def test_get_memory_statistics_config_empty(self):
        """Test handling of empty configuration"""
        connector = SonicDBConnector()
        self.mock_config_db.get_table.return_value = {}
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, Config.DEFAULT_CONFIG)

    def test_get_memory_statistics_config_error(self):
        """Test error handling in configuration retrieval"""
        connector = SonicDBConnector()
        self.mock_config_db.get_table.side_effect = Exception("Database error")
        with self.assertRaises(RuntimeError) as context:
            connector.get_memory_statistics_config()
        self.assertIn("Error retrieving memory statistics configuration", str(context.exception))


class TestSocketManager1(unittest.TestCase):
    """Test cases for SocketManager class"""
    def setUp(self):
        self.socket_path = '/tmp/test_socket'
        self.socket_manager = SocketManager(self.socket_path)

    @patch('socket.socket')
    def test_successful_connection(self, mock_socket):
        """Test successful socket connection"""
        mock_socket.return_value.connect.return_value = None
        self.socket_manager.connect()
        mock_socket.assert_called_with(socket.AF_UNIX, socket.SOCK_STREAM)

    @patch('socket.socket')
    def test_connection_retry(self, mock_socket):
        """Test connection retry mechanism"""
        mock_socket.return_value.connect.side_effect = [
            socket.error("Connection failed"),
            None
        ]
        self.socket_manager.connect()
        self.assertEqual(mock_socket.return_value.connect.call_count, 2)

    @patch('os.path.exists')
    def test_validate_socket_path_success(self, mock_exists):
        """Test successful socket path validation"""
        mock_exists.return_value = True
        self.socket_manager._validate_socket_path()
        mock_exists.assert_called_once_with(os.path.dirname(self.socket_path))

    @patch('socket.socket')
    def test_connect_success(self, mock_socket):
        """Test successful socket connection"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        self.socket_manager.connect()
        mock_sock.settimeout.assert_called_with(Config.SOCKET_TIMEOUT)
        mock_sock.connect.assert_called_with(self.socket_path)

    @patch('socket.socket')
    def test_connect_retry_success(self, mock_socket):
        """Test successful connection after retries"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.side_effect = [socket.error(), socket.error(), None]
        self.socket_manager.connect()
        self.assertEqual(mock_sock.connect.call_count, 3)

    @patch('socket.socket')
    def test_receive_all_success(self, mock_socket):
        """Test successful data reception"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recv.side_effect = [b'test', b'data', b'']
        self.socket_manager.sock = mock_sock
        result = self.socket_manager.receive_all()
        self.assertEqual(result, 'testdata')

    def test_close_success(self):
        """Test successful socket closure"""
        mock_sock = MagicMock()
        self.socket_manager.sock = mock_sock
        self.socket_manager.close()
        mock_sock.close.assert_called_once()
        self.assertIsNone(self.socket_manager.sock)

    def test_close_with_error(self):
        """Test socket closure with error"""
        mock_sock = MagicMock()
        mock_sock.close.side_effect = Exception("Close error")
        self.socket_manager.sock = mock_sock
        self.socket_manager.close()
        self.assertIsNone(self.socket_manager.sock)

    @patch('socket.socket')
    def test_send_data_success(self, mock_socket):
        """Test successful data sending"""
        mock_sock = MagicMock()
        self.socket_manager.sock = mock_sock
        test_data = "test message"
        self.socket_manager.send(test_data)
        mock_sock.sendall.assert_called_with(test_data.encode('utf-8'))


class TestCLICommands(unittest.TestCase):
    """Test cases for CLI commands"""
    def setUp(self):
        self.runner = CliRunner()
        self.ctx = click.Context(click.Command('test'))

    def test_validate_command_invalid_with_suggestion(self):
        """Test command validation with invalid command but close match"""
        valid_commands = ['show', 'config']
        with self.assertRaises(click.UsageError) as context:
            validate_command('shw', valid_commands)
        self.assertIn("Did you mean 'show'", str(context.exception))

    def test_validate_command_invalid_no_suggestion(self):
        """Test command validation with invalid command and no close match"""
        valid_commands = ['show', 'config']
        with self.assertRaises(click.UsageError) as context:
            validate_command('xyz', valid_commands)
        self.assertIn("Invalid command 'xyz'", str(context.exception))

    def test_format_field_value(self):
        """Test field value formatting"""
        self.assertEqual(format_field_value("enabled", "true"), "True")
        self.assertEqual(format_field_value("enabled", "false"), "False")
        self.assertEqual(format_field_value("retention_period", "Unknown"), "Not configured")
        self.assertEqual(format_field_value("sampling_interval", "5"), "5")

    def test_clean_and_print(self):
        """Test data cleaning and printing"""
        test_data = {
            "data": "Memory Usage: 50%\nSwap Usage: 10%"
        }
        with patch('builtins.print') as mock_print:
            clean_and_print(test_data)
            mock_print.assert_called_with("Memory Statistics:\nMemory Usage: 50%\nSwap Usage: 10%")

    def test_clean_and_print_invalid_data(self):
        """Test clean_and_print with invalid data"""
        with patch('builtins.print') as mock_print:
            clean_and_print("invalid data")
            mock_print.assert_called_with("Error: Invalid data format received")


class TestCLIEntryPoint(unittest.TestCase):

    @patch('sys.argv', ['memory_statistics.py', 'show'])
    @patch('show.memory_statistics.cli')
    def test_main_valid_command(self, mock_cli):
        """Test main() with a valid 'show' command."""
        mock_cli.add_command = MagicMock()
        mock_cli.return_value = None

        try:
            main()
        except SystemExit:
            pass  # CLI might call sys.exit()

        mock_cli.add_command.assert_called_once_with(show)
        mock_cli.assert_called_once()  # Ensure cli() is invoked

    # @patch('sys.argv', ['memory_statistics.py', 'invalid_command'])
    # @patch('syslog.syslog')
    # def test_main_invalid_command(self, mock_syslog):
    #     """Test main() with an invalid command."""
    #     with self.assertRaises(click.UsageError) as context:
    #         main()

    #     self.assertIn("Error: Invalid command", str(context.exception))
    #     mock_syslog.assert_called_once_with(
    #         syslog.LOG_ERR, "Error: Invalid command 'invalid_command'."
    #     )

    @patch('sys.argv', ['memory_statistics.py'])
    @patch('show.memory_statistics.cli')
    def test_main_no_command(self, mock_cli):
        """Test main() with no command-line arguments."""
        try:
            main()
        except SystemExit:
            pass  # CLI might call sys.exit()

        mock_cli.add_command.assert_called_once_with(show)
        mock_cli.assert_called_once()  # Ensure cli() is invoked


# class TestMemoryStatisticsCLI(unittest.TestCase):

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats'])
#     def test_show_memory_stats_valid(self, mock_stdout):
#         """Test the valid 'show memory-stats' command."""
#         with patch('show.memory_statistics.SocketManager.get_memory_stats',
#                    return_value={'total_memory': 4096, 'used_memory': 2048}), \
#              patch('show.memory_statistics.SonicDBConnector.fetch_config',
#                    return_value={'enabled': 'true', 'sampling_interval': 5, 'retention_period': 15}):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("total_memory", output)
#         self.assertIn("used_memory", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats', '--from', '10 minutes ago', '--to', 'now'])
#     def test_show_memory_stats_with_time_range(self, mock_stdout):
#         """Test the 'show memory-stats' command with --from and --to options."""
#         with patch('show.memory_statistics.SocketManager.get_memory_stats',
#                    return_value={'total_memory': 4096, 'used_memory': 2048}):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("total_memory", output)
#         self.assertIn("used_memory", output)
#         self.assertIn("10 minutes ago", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats', '--select', 'total_memory'])
#     def test_show_memory_stats_with_select_option(self, mock_stdout):
#         """Test the 'show memory-stats' command with --select option."""
#         with patch('show.memory_statistics.SocketManager.get_memory_stats', return_value={'total_memory': 4096}):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("total_memory", output)
#         self.assertNotIn("used_memory", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats', 'config'])
#     def test_show_memory_stats_config(self, mock_stdout):
#         """Test the 'show memory-stats config' command."""
#         with patch('show.memory_statistics.SonicDBConnector.fetch_config',
#                    return_value={'enabled': 'true', 'sampling_interval': 5, 'retention_period': 15}):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("enabled", output)
#         self.assertIn("sampling_interval", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'invalid_command'])
#     def test_invalid_command(self, mock_stdout):
#         """Test an invalid command."""
#         with self.assertRaises(SystemExit):
#             main()
#         output = mock_stdout.getvalue()
#         self.assertIn("Error: Invalid command", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show'])
#     def test_missing_required_argument(self, mock_stdout):
#         """Test a missing required argument."""
#         with self.assertRaises(SystemExit):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("Error", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats', '--from', 'invalid_time'])
#     def test_invalid_time_range(self, mock_stdout):
#         """Test invalid time range input."""
#         with self.assertRaises(SystemExit):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("Invalid value for", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats', '--select', 'invalid_metric'])
#     def test_invalid_select_option(self, mock_stdout):
#         """Test invalid --select option."""
#         with self.assertRaises(SystemExit):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("Invalid value for", output)

#     @patch('sys.stdout', new_callable=StringIO)
#     @patch('sys.argv', new=['main.py', 'show', 'memory-stats'])
#     def test_show_memory_stats_no_args(self, mock_stdout):
#         """Test the 'show memory-stats' command with no options."""
#         with patch('show.memory_statistics.SocketManager.get_memory_stats',
#                    return_value={'total_memory': 4096, 'used_memory': 2048}):
#             main()

#         output = mock_stdout.getvalue()
#         self.assertIn("total_memory", output)
#         self.assertIn("used_memory", output)


class TestMemoryStatisticsCLI2(unittest.TestCase):

    # @patch('show.memory_statistics.SocketManager.connect')
    # @patch('show.memory_statistics.SocketManager.receive_all')
    # def test_send_data_success(self, mock_receive_all, mock_connect):
    #     """Test successful data sending and response handling."""
    #     mock_receive_all.return_value = json.dumps({"status": True, "data": "OK"})

    #     response = send_data("test_command", {"param": "value"})
    #     self.assertEqual(response.data, "OK")
    #     mock_connect.assert_called_once()

    # @patch('show.memory_statistics.SocketManager.connect')
    # def test_send_data_connection_failure(self, mock_connect):
    #     """Test socket connection failure scenario."""
    #     mock_connect.side_effect = ConnectionError("Connection failed")

    #     with self.assertRaises(ConnectionError):
    #         send_data("test_command", {"param": "value"})

    # @patch('show.memory_statistics.SonicDBConnector.get_memory_statistics_config')
    # @patch('click.echo')
    # def test_display_config_success(self, mock_echo, mock_get_config):
    #     """Test display_config with successful data retrieval."""
    #     mock_get_config.return_value = {
    #         "enabled": "true",
    #         "sampling_interval": "5",
    #         "retention_period": "15"
    #     }

    #     db_connector = Mock()
    #     display_config(db_connector)
    #     mock_echo.assert_any_call("Enabled                         true")

    # def test_format_field_value(self):
    #     """Test formatting field values."""
    #     result = format_field_value("enabled", "true")
    #     self.assertEqual(result, "true")

    # @patch('show.memory_statistics.send_data')
    # @patch('click.echo')
    # def test_display_statistics_success(self, mock_echo, mock_send_data):
    #     """Test display_statistics with valid data."""
    #     mock_send_data.return_value = Dict2Obj({"items": [{"metric": "usage", "value": 50}]})

    #     ctx = MagicMock()
    #     display_statistics(ctx, "2024-01-01", "2024-01-02", "usage")
    #     mock_echo.assert_called()

    @patch('show.memory_statistics.send_data')
    def test_display_statistics_no_response(self, mock_send_data):
        """Test display_statistics with no response."""
        mock_send_data.side_effect = click.ClickException("No data")

        ctx = MagicMock()
        with self.assertRaises(click.ClickException):
            display_statistics(ctx, "2024-01-01", "2024-01-02", "usage")


# class TestSocketManager:
#     def test_to_dict_method_with_list_of_dict2obj(self):
#         """Test to_dict method with a list of Dict2Obj instances."""
#         class TestDict2Obj(Dict2Obj):
#             def to_dict(self):
#                 return {"test_key": "test_value"}

#         test_obj = Dict2Obj({"items": [TestDict2Obj({"key": "value"}), "plain_value"]})
#         result = test_obj.to_dict()
#         assert result == [{"test_key": "test_value"}, "plain_value"]

#     @patch('syslog.syslog')
#     def test_validate_socket_path_non_existent_directory(self, mock_syslog):
#         """Test _validate_socket_path when socket directory does not exist."""
#         with patch('os.path.exists', return_value=False):
#             with pytest.raises(ConnectionError) as excinfo:
#                 socket_manager = SocketManager()
#                 socket_manager.socket_path = '/non/existent/path/socket'
#                 socket_manager._validate_socket_path()

#         assert "Socket directory /non/existent/path does not exist" in str(excinfo.value)
#         mock_syslog.assert_called_once_with(syslog.LOG_ERR,
#                                             "Socket directory /non/existent/path does not exist")

#     @patch('socket.socket')
#     @patch('time.sleep')
#     @patch('syslog.syslog')
#     def test_connect_max_retries_exceeded(self, mock_syslog, mock_sleep, mock_socket):
#         """Test connect method when max retries are exceeded."""
#         Mock()
#         mock_socket.side_effect = socket.error("Connection failed")

#         with patch.object(Config, 'MAX_RETRIES', 3), \
#              patch.object(Config, 'RETRY_DELAY', 0.1), \
#              pytest.raises(ConnectionError) as excinfo:
#             socket_manager = SocketManager()
#             socket_manager.connect()

#         assert f"Failed to connect to memory statistics service after 3 attempts" in str(excinfo.value)
#         assert mock_socket.call_count == 3
#         assert mock_sleep.call_count == 3
#         mock_syslog.assert_called()

#     def test_receive_all_no_active_socket(self):
#         """Test receive_all method when no active socket connection exists."""
#         socket_manager = SocketManager()
#         socket_manager.sock = None

#         with pytest.raises(ConnectionError) as excinfo:
#             socket_manager.receive_all()

#         assert "No active socket connection" in str(excinfo.value)

#     @patch('socket.socket')
#     def test_receive_all_socket_timeout(self, mock_socket):
#         """Test receive_all method with socket timeout."""
#         mock_socket_instance = Mock()
#         mock_socket_instance.recv.side_effect = socket.timeout()

#         with patch.object(Config, 'SOCKET_TIMEOUT', 5), \
#              patch.object(Config, 'BUFFER_SIZE', 1024), \
#              pytest.raises(ConnectionError) as excinfo:
#             socket_manager = SocketManager()
#             socket_manager.sock = mock_socket_instance
#             socket_manager.receive_all()

#         assert f"Socket operation timed out after 5 seconds" in str(excinfo.value)

#     def test_send_no_active_socket(self):
#         """Test send method when no active socket connection exists."""
#         socket_manager = SocketManager()
#         socket_manager.sock = None

#         with pytest.raises(ConnectionError) as excinfo:
#             socket_manager.send("test data")

#         assert "No active socket connection" in str(excinfo.value)

#     @patch('socket.socket')
#     def test_send_socket_error(self, mock_socket):
#         """Test send method with socket send error."""
#         mock_socket_instance = Mock()
#         mock_socket_instance.sendall.side_effect = socket.error("Send failed")

#         with pytest.raises(ConnectionError) as excinfo:
#             socket_manager = SocketManager()
#             socket_manager.sock = mock_socket_instance
#             socket_manager.send("test data")

#         assert "Failed to send data: Send failed" in str(excinfo.value)

# def test_send_data_no_response():
#     """Test send_data function when no response is received."""
#     with patch('socket.socket') as mock_socket, \
#          patch.object(SocketManager, 'receive_all', return_value='') as mock_receive:
#         with pytest.raises(ConnectionError) as excinfo:
#             send_data("test_command", {"key": "value"})

#         assert "No response received from memory statistics service" in str(excinfo.value)

# def test_send_data_json_decode_error():
#     """Test send_data function with invalid JSON response."""
#     with patch('socket.socket'), \
#          patch.object(SocketManager, 'receive_all', return_value='invalid json'):
#         with pytest.raises(ValueError) as excinfo:
#             send_data("test_command", {"key": "value"})

#         assert "Failed to parse server response" in str(excinfo.value)

# def test_send_data_invalid_response_format():
#     """Test send_data function with invalid response format."""
#     with patch('socket.socket'), \
#          patch.object(SocketManager, 'receive_all', return_value='[1, 2, 3]'):
#         with pytest.raises(ValueError) as excinfo:
#             send_data("test_command", {"key": "value"})

#         assert "Invalid response format from server" in str(excinfo.value)

# def test_send_data_server_error_response():
#     """Test send_data function with server error response."""
#     error_response = json.dumps({"status": False, "msg": "Server error"})
#     with patch('socket.socket'), \
#          patch.object(SocketManager, 'receive_all', return_value=error_response):
#         with pytest.raises(RuntimeError) as excinfo:
#             send_data("test_command", {"key": "value"})

#         assert "Server error" in str(excinfo.value)

# @patch('click.echo')
# def test_display_config_exception(mock_echo):
#     """Test display_config function with database connection error."""
#     mock_db_connector = Mock()
#     mock_db_connector.get_memory_statistics_config.side_effect = Exception("DB Error")

#     with patch('syslog.syslog') as mock_syslog, \
#          pytest.raises(click.ClickException) as excinfo:
#         display_config(mock_db_connector)

#     assert "Failed to retrieve configuration: DB Error" in str(excinfo.value)
#     mock_syslog.assert_called_once_with(syslog.LOG_ERR,
#                                          "Failed to retrieve configuration: DB Error")

# def test_main_invalid_command():
#     """Test main function with an invalid command."""
#     with patch('sys.argv', ['script.py', 'invalid_command']), \
#          patch('syslog.syslog') as mock_syslog, \
#          pytest.raises(click.UsageError) as excinfo:
#         main()

#     assert "Error: Invalid command 'invalid_command'" in str(excinfo.value)
#     mock_syslog.assert_called_once_with(syslog.LOG_ERR,
#                                          "Error: Invalid command 'invalid_command'.")


class TestSocketManager:
    def test_to_dict_method_with_list_of_dict2obj(self):
        """Test to_dict method with a list of Dict2Obj instances."""
        class TestDict2Obj(Dict2Obj):
            def to_dict(self):
                return {"test_key": "test_value"}

        test_obj = Dict2Obj({"items": [TestDict2Obj({"key": "value"}), "plain_value"]})
        result = test_obj.to_dict()
        assert result == [{"test_key": "test_value"}, "plain_value"]

    @patch('syslog.syslog')
    def test_validate_socket_path_non_existent_directory(self, mock_syslog):
        """Test _validate_socket_path when socket directory does not exist."""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(ConnectionError) as excinfo:
                socket_manager = SocketManager()
                socket_manager.socket_path = '/non/existent/path/socket'
                socket_manager._validate_socket_path()

        assert "Socket directory /non/existent/path does not exist" in str(excinfo.value)
        mock_syslog.assert_called_once_with(syslog.LOG_ERR,
                                            "Socket directory /non/existent/path does not exist")

    @patch('socket.socket')
    @patch('time.sleep')
    @patch('syslog.syslog')
    def test_connect_max_retries_exceeded(self, mock_syslog, mock_sleep, mock_socket):
        """Test connect method when max retries are exceeded."""
        mock_socket.side_effect = socket.error("Connection failed")

        with patch.object(Config, 'MAX_RETRIES', 3), \
             patch.object(Config, 'RETRY_DELAY', 0.1):
            with pytest.raises(ConnectionError) as excinfo:
                socket_manager = SocketManager()
                socket_manager.connect()

        assert "Failed to connect to memory statistics service after 3 attempts" in str(excinfo.value)
        assert mock_socket.call_count == 3
        assert mock_sleep.call_count == 3
        mock_syslog.assert_called()

    def test_receive_all_no_active_socket(self):
        """Test receive_all method when no active socket connection exists."""
        socket_manager = SocketManager()
        socket_manager.sock = None

        with pytest.raises(ConnectionError) as excinfo:
            socket_manager.receive_all()

        assert "No active socket connection" in str(excinfo.value)

    @patch('socket.socket')
    def test_receive_all_socket_timeout(self, mock_socket):
        """Test receive_all method with socket timeout."""
        mock_socket_instance = Mock()
        mock_socket_instance.recv.side_effect = socket.timeout()

        with patch.object(Config, 'SOCKET_TIMEOUT', 5), \
             patch.object(Config, 'BUFFER_SIZE', 1024):
            with pytest.raises(ConnectionError) as excinfo:
                socket_manager = SocketManager()
                socket_manager.sock = mock_socket_instance
                socket_manager.receive_all()

        assert "Socket operation timed out after 5 seconds" in str(excinfo.value)

    def test_send_no_active_socket(self):
        """Test send method when no active socket connection exists."""
        socket_manager = SocketManager()
        socket_manager.sock = None

        with pytest.raises(ConnectionError) as excinfo:
            socket_manager.send("test data")

        assert "No active socket connection" in str(excinfo.value)

    @patch('socket.socket')
    def test_send_socket_error(self, mock_socket):
        """Test send method with socket send error."""
        mock_socket_instance = Mock()
        mock_socket_instance.sendall.side_effect = socket.error("Send failed")

        with pytest.raises(ConnectionError) as excinfo:
            socket_manager = SocketManager()
            socket_manager.sock = mock_socket_instance
            socket_manager.send("test data")

        assert "Failed to send data: Send failed" in str(excinfo.value)


def test_send_data_no_response():
    """Test send_data function when no response is received."""
    with patch('socket.socket'), \
         patch.object(SocketManager, 'receive_all', return_value=''):
        with pytest.raises(ConnectionError) as excinfo:
            send_data("test_command", {"key": "value"})

        assert "No response received from memory statistics service" in str(excinfo.value)


def test_send_data_json_decode_error():
    """Test send_data function with invalid JSON response."""
    with patch('socket.socket'), \
         patch.object(SocketManager, 'receive_all', return_value='invalid json'):
        with pytest.raises(ValueError) as excinfo:
            send_data("test_command", {"key": "value"})

        assert "Failed to parse server response" in str(excinfo.value)


def test_send_data_invalid_response_format():
    """Test send_data function with invalid response format."""
    with patch('socket.socket'), \
         patch.object(SocketManager, 'receive_all', return_value='[1, 2, 3]'):
        with pytest.raises(ValueError) as excinfo:
            send_data("test_command", {"key": "value"})

        assert "Invalid response format from server" in str(excinfo.value)


def test_send_data_server_error_response():
    """Test send_data function with server error response."""
    error_response = json.dumps({"status": False, "msg": "Server error"})
    with patch('socket.socket'), \
         patch.object(SocketManager, 'receive_all', return_value=error_response):
        with pytest.raises(RuntimeError) as excinfo:
            send_data("test_command", {"key": "value"})

        assert "Server error" in str(excinfo.value)


@patch('click.echo')
def test_display_config_exception(mock_echo):
    """Test display_config function with database connection error."""
    mock_db_connector = Mock()
    mock_db_connector.get_memory_statistics_config.side_effect = Exception("DB Error")

    with patch('syslog.syslog') as mock_syslog:
        with pytest.raises(click.ClickException) as excinfo:
            display_config(mock_db_connector)

        assert "Failed to retrieve configuration: DB Error" in str(excinfo.value)
        mock_syslog.assert_called_once_with(syslog.LOG_ERR,
                                            "Failed to retrieve configuration: DB Error")


def test_main_invalid_command():
    """Test main function with an invalid command."""
    with patch('sys.argv', ['script.py', 'invalid_command']), \
         patch('syslog.syslog') as mock_syslog:
        with pytest.raises(click.UsageError) as excinfo:
            main()

        assert "Error: Invalid command 'invalid_command'" in str(excinfo.value)
        mock_syslog.assert_called_once_with(syslog.LOG_ERR,
                                            "Error: Invalid command 'invalid_command'.")


if __name__ == '__main__':
    unittest.main()
