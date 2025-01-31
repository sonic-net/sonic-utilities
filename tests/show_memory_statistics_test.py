import json
import os
import signal
import socket
import syslog
import unittest
from unittest.mock import MagicMock, Mock, patch

import click
from click.testing import CliRunner
import pytest

from show.memory_statistics import (
    Config,
    ConnectionError,
    Dict2Obj,
    SonicDBConnector,
    SocketManager,
    cleanup_resources,
    display_config,
    format_field_value,
    main,
    send_data,
    show_configuration,
    show_statistics,
    shutdown_handler,
)


class TestConfig(unittest.TestCase):
    """Tests for Config class"""

    def test_default_config_values(self):
        """Test that Config class has correct default values"""
        self.assertEqual(Config.SOCKET_PATH, '/var/run/dbus/memstats.socket')
        self.assertEqual(Config.SOCKET_TIMEOUT, 30)
        self.assertEqual(Config.BUFFER_SIZE, 8192)
        self.assertEqual(Config.MAX_RETRIES, 3)
        self.assertEqual(Config.RETRY_DELAY, 1.0)

    def test_default_config_dictionary(self):
        """Test the DEFAULT_CONFIG dictionary has correct values"""
        expected = {
            "enabled": "false",
            "sampling_interval": "5",
            "retention_period": "15"
        }
        self.assertEqual(Config.DEFAULT_CONFIG, expected)


class TestDict2Obj(unittest.TestCase):
    """Tests for Dict2Obj class"""

    def test_dict_conversion(self):
        """Test basic dictionary conversion"""
        test_dict = {"name": "test", "value": 123}
        obj = Dict2Obj(test_dict)
        self.assertEqual(obj.name, "test")
        self.assertEqual(obj.value, 123)

    def test_nested_dict_conversion(self):
        """Test nested dictionary conversion"""
        test_dict = {
            "outer": {
                "inner": "value",
                "number": 42
            }
        }
        obj = Dict2Obj(test_dict)
        self.assertEqual(obj.outer.inner, "value")
        self.assertEqual(obj.outer.number, 42)

    def test_list_conversion(self):
        """Test list conversion"""
        test_list = [{"name": "item1"}, {"name": "item2"}]
        obj = Dict2Obj(test_list)
        self.assertEqual(obj.items[0].name, "item1")
        self.assertEqual(obj.items[1].name, "item2")

    def test_invalid_input(self):
        """Test invalid input handling"""
        with self.assertRaises(ValueError):
            Dict2Obj("invalid")

    def test_to_dict_conversion(self):
        """Test conversion back to dictionary"""
        original = {"name": "test", "nested": {"value": 123}}
        obj = Dict2Obj(original)
        result = obj.to_dict()
        self.assertEqual(result, original)

    def test_nested_list_conversion(self):
        """Test conversion of nested lists with dictionaries"""
        test_dict = {
            "items": [
                {"id": 1, "subitems": [{"name": "sub1"}, {"name": "sub2"}]},
                {"id": 2, "subitems": [{"name": "sub3"}, {"name": "sub4"}]}
            ]
        }
        obj = Dict2Obj(test_dict)
        self.assertEqual(obj.items[0].subitems[0].name, "sub1")
        self.assertEqual(obj.items[1].subitems[1].name, "sub4")

    def test_empty_structures(self):
        """Test conversion of empty structures"""
        self.assertEqual(Dict2Obj({}).to_dict(), {})
        self.assertEqual(Dict2Obj([]).to_dict(), [])

    def test_complex_nested_structure(self):
        """Test conversion of complex nested structures"""
        test_dict = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": 42,
                        "list": [1, 2, {"nested": "value"}]
                    }
                }
            }
        }
        obj = Dict2Obj(test_dict)
        self.assertEqual(obj.level1.level2.level3.value, 42)
        self.assertEqual(obj.level1.level2.level3.list[2].nested, "value")


class TestSonicDBConnector(unittest.TestCase):
    """Tests for SonicDBConnector class"""

    @patch('show.memory_statistics.ConfigDBConnector')
    def setUp(self, mock_config_db):
        self.mock_config_db = mock_config_db
        self.connector = SonicDBConnector()
        self.mock_config_db.reset_mock()

    def test_successful_connection(self):
        """Test successful database connection"""
        self.mock_config_db.return_value.connect.return_value = None
        self.connector.connect_with_retry()
        self.mock_config_db.return_value.connect.assert_called_once()

    @patch('time.sleep')
    def test_connection_retry(self, mock_sleep):
        """Test connection retry mechanism"""
        self.mock_config_db.return_value.connect.side_effect = [
            Exception("Connection failed"),
            None
        ]
        self.connector.connect_with_retry(max_retries=2, retry_delay=0.1)
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertEqual(self.mock_config_db.return_value.connect.call_count, 2)

    def test_connection_failure(self):
        """Test connection failure after max retries"""
        self.mock_config_db.return_value.connect.side_effect = Exception("Connection failed")
        with self.assertRaises(ConnectionError):
            self.connector.connect_with_retry(max_retries=1)

    def test_get_memory_statistics_config_success(self):
        """Test successful config retrieval"""
        expected_config = {
            "memory_statistics": {
                "enabled": "true",
                "sampling_interval": "10",
                "retention_period": "30"
            }
        }
        self.mock_config_db.return_value.get_table.return_value = expected_config
        result = self.connector.get_memory_statistics_config()
        self.assertEqual(result["enabled"], "true")
        self.assertEqual(result["sampling_interval"], "10")
        self.assertEqual(result["retention_period"], "30")

    def test_get_memory_statistics_config_default(self):
        """Test default config when table is empty"""
        self.mock_config_db.return_value.get_table.return_value = {}
        result = self.connector.get_memory_statistics_config()
        self.assertEqual(result, Config.DEFAULT_CONFIG)

    def test_invalid_config_format(self):
        """Test handling of invalid configuration format"""
        self.mock_config_db.return_value.get_table.return_value = {
            "memory_statistics": "invalid_string_instead_of_dict"
        }
        result = self.connector.get_memory_statistics_config()
        self.assertEqual(result, Config.DEFAULT_CONFIG)

    def test_partial_config(self):
        """Test handling of partial configuration"""
        self.mock_config_db.return_value.get_table.return_value = {
            "memory_statistics": {
                "enabled": "true"
                # missing other fields
            }
        }
        result = self.connector.get_memory_statistics_config()
        self.assertEqual(result["enabled"], "true")
        self.assertEqual(result["sampling_interval"], "5")  # default value
        self.assertEqual(result["retention_period"], "15")  # default value


class TestSocketManager(unittest.TestCase):
    """Tests for SocketManager class"""

    def setUp(self):
        self.test_socket_path = "/tmp/test_socket"
        os.makedirs(os.path.dirname(self.test_socket_path), exist_ok=True)
        self.socket_manager = SocketManager(self.test_socket_path)

    @patch('socket.socket')
    def test_successful_connection(self, mock_socket):
        """Test successful socket connection"""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        self.socket_manager.connect()
        mock_sock.connect.assert_called_once_with(self.test_socket_path)

    @patch('socket.socket')
    @patch('time.sleep')
    def test_connection_retry(self, mock_sleep, mock_socket):
        """Test socket connection retry mechanism"""
        mock_sock = Mock()
        mock_sock.connect.side_effect = [socket.error, None]
        mock_socket.return_value = mock_sock
        self.socket_manager.connect()
        self.assertEqual(mock_sock.connect.call_count, 2)

    @patch('socket.socket')
    def test_receive_all(self, mock_socket):
        """Test receiving data from socket"""
        mock_sock = Mock()
        mock_sock.recv.side_effect = [b'test', b'']
        mock_socket.return_value = mock_sock
        self.socket_manager.sock = mock_sock
        result = self.socket_manager.receive_all()
        self.assertEqual(result, 'test')

    @patch('socket.socket')
    def test_send_data(self, mock_socket):
        """Test sending data through socket"""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        self.socket_manager.sock = mock_sock
        self.socket_manager.send("test_data")
        mock_sock.sendall.assert_called_once_with(b'test_data')

    def test_close_connection(self):
        """Test closing socket connection"""
        mock_sock = Mock()
        self.socket_manager.sock = mock_sock
        self.socket_manager.close()
        mock_sock.close.assert_called_once()
        self.assertIsNone(self.socket_manager.sock)

    def test_invalid_socket_path(self):
        """Test socket creation with invalid path"""
        with self.assertRaises(ConnectionError):
            SocketManager("/nonexistent/path/socket")

    @patch('socket.socket')
    def test_connection_max_retries_exceeded(self, mock_socket):
        """Test connection failure after max retries"""
        mock_sock = Mock()
        mock_sock.connect.side_effect = socket.error("Connection failed")
        mock_socket.return_value = mock_sock

        with self.assertRaises(ConnectionError) as ctx:
            self.socket_manager.connect()
        self.assertIn("Failed to connect to memory statistics service", str(ctx.exception))

    @patch('socket.socket')
    def test_receive_timeout(self, mock_socket):
        """Test socket timeout during receive"""
        mock_sock = Mock()
        mock_sock.recv.side_effect = socket.timeout
        self.socket_manager.sock = mock_sock

        with self.assertRaises(ConnectionError) as context:
            self.socket_manager.receive_all()
        self.assertIn("timed out", str(context.exception))

    @patch('socket.socket')
    def test_receive_with_socket_error(self, mock_socket):
        """Test receive with socket error"""
        mock_sock = Mock()
        mock_sock.recv.side_effect = socket.error("Receive error")
        self.socket_manager.sock = mock_sock

        with self.assertRaises(ConnectionError) as ctx:
            self.socket_manager.receive_all()
        self.assertIn("Socket error during receive", str(ctx.exception))

    @patch('socket.socket')
    def test_send_without_connection(self, mock_socket):
        """Test sending data without an active connection"""
        self.socket_manager.sock = None
        with self.assertRaises(ConnectionError) as context:
            self.socket_manager.send("test")
        self.assertIn("No active socket connection", str(context.exception))

    @patch('socket.socket')
    def test_multiple_chunk_receive(self, mock_socket):
        """Test receiving multiple chunks of data"""
        mock_sock = Mock()
        mock_sock.recv.side_effect = [b'chunk1', b'chunk2', b'chunk3', b'']
        self.socket_manager.sock = mock_sock
        result = self.socket_manager.receive_all()
        self.assertEqual(result, 'chunk1chunk2chunk3')


class TestCLICommands(unittest.TestCase):
    """Tests for CLI commands"""

    def setUp(self):
        self.runner = CliRunner()

    @patch('show.memory_statistics.send_data')
    def test_show_statistics(self, mock_send_data):
        """Test show statistics command"""
        mock_response = Dict2Obj({
            "status": True,
            "data": "Memory Statistics Data"
        })
        mock_send_data.return_value = mock_response

        result = self.runner.invoke(show_statistics, ['--from', '1h', '--to', 'now'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Memory Statistics", result.output)

    @patch('show.memory_statistics.send_data')
    def test_show_statistics_with_metric(self, mock_send_data):
        """Test show statistics with specific metric"""
        mock_response = Dict2Obj({
            "status": True,
            "data": "Memory Usage: 75%"
        })
        mock_send_data.return_value = mock_response

        result = self.runner.invoke(show_statistics,
                                    ['--select', 'used_memory'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Memory Usage", result.output)

    @patch('show.memory_statistics.send_data')
    def test_show_statistics_error_handling(self, mock_send_data):
        """Test error handling in show statistics"""
        mock_send_data.side_effect = ConnectionError("Failed to connect")

        result = self.runner.invoke(show_statistics)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error", result.output)

    @patch('show.memory_statistics.send_data')
    def test_show_statistics_empty_data(self, mock_send):
        """Test show_statistics with empty data"""
        mock_send.return_value = Dict2Obj({"data": ""})
        result = self.runner.invoke(show_statistics)
        self.assertIn("No memory statistics data available", result.output)


class TestShowConfiguration(unittest.TestCase):
    """Tests for show_configuration command"""

    def setUp(self):
        self.runner = CliRunner()

    @patch('show.memory_statistics.SonicDBConnector')
    def test_show_config_error(self, mock_db):
        """Test show_configuration error handling"""
        mock_db.side_effect = Exception("DB Connection Error")
        result = self.runner.invoke(show_configuration)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error", result.output)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling"""

    def test_cleanup_resources(self):
        """Test resource cleanup"""
        mock_db = Mock()
        mock_socket = Mock()
        cleanup_resources.db_connector = mock_db
        cleanup_resources.socket_manager = mock_socket
        cleanup_resources()
        self.assertFalse(hasattr(cleanup_resources, 'db_connector'))
        mock_socket.close.assert_called_once()

    @patch('sys.exit')
    def test_shutdown_handler(self, mock_exit):
        """Test shutdown handler"""
        shutdown_handler(None, None)
        mock_exit.assert_called_once_with(0)

    @patch('syslog.syslog')
    def test_cleanup_with_exceptions(self, mock_syslog):
        """Test cleanup with exceptions"""
        mock_socket = Mock()
        mock_socket.close.side_effect = Exception("Cleanup failed")
        cleanup_resources.socket_manager = mock_socket

        cleanup_resources()
        mock_syslog.assert_any_call(syslog.LOG_ERR, "Error during cleanup: Cleanup failed")

    @patch('syslog.syslog')
    def test_cleanup_with_missing_attributes(self, mock_syslog):
        """Test cleanup when attributes don't exist"""
        # Ensure attributes don't exist
        if hasattr(cleanup_resources, 'db_connector'):
            delattr(cleanup_resources, 'db_connector')
        if hasattr(cleanup_resources, 'socket_manager'):
            delattr(cleanup_resources, 'socket_manager')

        cleanup_resources()
        mock_syslog.assert_any_call(syslog.LOG_INFO, "Successfully cleaned up resources during shutdown")

    @patch('sys.exit')
    @patch('syslog.syslog')
    def test_shutdown_handler_cleanup_error(self, mock_syslog, mock_exit):
        """Test shutdown handler with cleanup error"""
        @patch('show.memory_statistics.cleanup_resources', side_effect=Exception("Cleanup Error"))
        def test(mock_cleanup):
            shutdown_handler(signal.SIGTERM, None)
            mock_syslog.assert_any_call(syslog.LOG_ERR, "Error during shutdown: Cleanup Error")
            mock_exit.assert_called_once_with(1)
        test()


class TestHelperFunctions(unittest.TestCase):
    """Tests for helper functions"""

    def test_format_field_value(self):
        """Test field value formatting"""
        self.assertEqual(format_field_value("enabled", "true"), "True")
        self.assertEqual(format_field_value("enabled", "false"), "False")
        self.assertEqual(format_field_value("retention_period", "15"), "15")
        self.assertEqual(format_field_value("sampling_interval", "Unknown"), "Not configured")


class TestSendData(unittest.TestCase):
    """Tests for send_data function"""

    @patch('show.memory_statistics.SocketManager')
    def test_send_data_invalid_response(self, mock_socket_manager):
        """Test send_data with invalid JSON response"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        mock_instance.receive_all.return_value = "invalid json"

        with self.assertRaises(ValueError):
            send_data("test_command", {})

    @patch('show.memory_statistics.SocketManager')
    def test_send_data_non_dict_response(self, mock_socket_manager):
        """Test send_data with non-dict response"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        mock_instance.receive_all.return_value = json.dumps(["not a dict"])

        with self.assertRaises(ValueError):
            send_data("test_command", {})

    @patch('show.memory_statistics.SocketManager')
    def test_successful_response_with_status(self, mock_socket_manager):
        """Test successful response with status field"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        response_data = {
            "status": True,
            "data": "test data"
        }
        mock_instance.receive_all.return_value = json.dumps(response_data)

        result = send_data("test_command", {})
        self.assertTrue(result.status)
        self.assertEqual(result.data, "test data")

    @patch('show.memory_statistics.SocketManager')
    def test_response_without_status_field(self, mock_socket_manager):
        """Test response without status field (should default to True)"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        response_data = {
            "data": "test data"
        }
        mock_instance.receive_all.return_value = json.dumps(response_data)

        result = send_data("test_command", {})
        self.assertTrue(getattr(result, 'status', True))
        self.assertEqual(result.data, "test data")

    @patch('show.memory_statistics.SocketManager')
    def test_failed_response_with_error_message(self, mock_socket_manager):
        """Test response with status False and error message"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        response_data = {
            "status": False,
            "msg": "Operation failed"
        }
        mock_instance.receive_all.return_value = json.dumps(response_data)

        with self.assertRaises(RuntimeError) as context:
            send_data("test_command", {})
        self.assertEqual(str(context.exception), "Operation failed")

    @patch('show.memory_statistics.SocketManager')
    def test_failed_response_without_message(self, mock_socket_manager):
        """Test response with status False but no error message"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        response_data = {
            "status": False
        }
        mock_instance.receive_all.return_value = json.dumps(response_data)

        with self.assertRaises(RuntimeError) as context:
            send_data("test_command", {})
        self.assertEqual(str(context.exception), "Unknown error occurred")

    @patch('show.memory_statistics.SocketManager')
    def test_complex_response_object_conversion(self, mock_socket_manager):
        """Test conversion of complex response object"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        response_data = {
            "status": True,
            "data": {
                "metrics": [
                    {"name": "memory", "value": 100},
                    {"name": "cpu", "value": 50}
                ],
                "timestamp": "2024-01-01"
            }
        }
        mock_instance.receive_all.return_value = json.dumps(response_data)

        result = send_data("test_command", {})
        self.assertTrue(result.status)
        self.assertEqual(result.data.metrics[0].name, "memory")
        self.assertEqual(result.data.metrics[1].value, 50)
        self.assertEqual(result.data.timestamp, "2024-01-01")


class TestDisplayConfig(unittest.TestCase):
    """Tests for display_config function"""

    def test_display_config_success(self):
        """Test successful config display"""
        mock_connector = MagicMock()
        mock_connector.get_memory_statistics_config.return_value = {
            "enabled": "true",
            "retention_period": "15",
            "sampling_interval": "5"
        }

        runner = CliRunner()
        with runner.isolation():
            display_config(mock_connector)

    def test_display_config_error(self):
        """Test error handling in display config"""
        mock_connector = MagicMock()
        mock_connector.get_memory_statistics_config.side_effect = RuntimeError("Config error")

        with pytest.raises(click.ClickException):
            display_config(mock_connector)


class TestMainFunction(unittest.TestCase):
    """Tests for main function"""

    @patch('signal.signal')
    @patch('show.memory_statistics.cli')
    def test_successful_execution(self, mock_cli, mock_signal):
        """Test successful execution of main function"""
        main()
        mock_signal.assert_called_once_with(signal.SIGTERM, shutdown_handler)
        mock_cli.assert_called_once()

    @patch('signal.signal')
    @patch('show.memory_statistics.cli')
    @patch('show.memory_statistics.cleanup_resources')
    def test_main_with_exception(self, mock_cleanup, mock_cli, mock_signal):
        """Test main function with exception"""
        mock_cli.side_effect = Exception("CLI error")

        with self.assertRaises(SystemExit):
            main()
        mock_cleanup.assert_called_once()


class TestFormatFieldValue:
    """Tests for format_field_value function using pytest"""

    @pytest.mark.parametrize("field_name,value,expected", [
        ("enabled", "true", "True"),
        ("enabled", "false", "False"),
        ("enabled", "TRUE", "True"),
        ("enabled", "FALSE", "False"),
        ("retention_period", "15", "15"),
        ("sampling_interval", "5", "5"),
        ("any_field", "Unknown", "Not configured"),
    ])
    def test_format_field_value(self, field_name, value, expected):
        assert format_field_value(field_name, value) == expected


class TestMemoryStatistics(unittest.TestCase):
    def setUp(self):
        self.cli_runner = CliRunner()

    def test_dict2obj_invalid_input(self):
        """Test Dict2Obj with invalid input (line 71)"""
        with self.assertRaises(ValueError):
            Dict2Obj("invalid input")

    def test_dict2obj_empty_list(self):
        """Test Dict2Obj with empty list (line 78)"""
        obj = Dict2Obj([])
        self.assertEqual(obj.to_dict(), [])

    @patch('socket.socket')
    def test_socket_receive_timeout(self, mock_socket):
        """Test socket timeout during receive (lines 137-140)"""
        manager = SocketManager()
        mock_socket.return_value.recv.side_effect = socket.timeout
        manager.sock = mock_socket.return_value

        with self.assertRaises(ConnectionError):
            manager.receive_all()

    @patch('socket.socket')
    def test_socket_send_error(self, mock_socket):
        """Test socket send error (line 166)"""
        manager = SocketManager()
        mock_socket.return_value.sendall.side_effect = socket.error("Send failed")
        manager.sock = mock_socket.return_value

        with self.assertRaises(ConnectionError):
            manager.send("test data")

    @patch('syslog.syslog')
    def test_cleanup_resources_error(self, mock_syslog):
        """Test cleanup resources error handling (lines 220-223)"""
        cleanup_resources.socket_manager = MagicMock()
        cleanup_resources.socket_manager.close.side_effect = Exception("Cleanup failed")

        cleanup_resources()
        mock_syslog.assert_called_with(syslog.LOG_ERR, "Error during cleanup: Cleanup failed")

    @patch('show.memory_statistics.send_data')
    def test_show_statistics_invalid_data(self, mock_send):
        """Test show statistics with invalid data format (line 247)"""
        mock_send.return_value = Dict2Obj(["invalid"])
        result = self.cli_runner.invoke(show_statistics, [])
        self.assertIn("Error: Invalid data format received", result.output)

    @patch('show.memory_statistics.SonicDBConnector')
    def test_show_configuration_error(self, mock_db):
        """Test show configuration error (line 302)"""
        mock_db.side_effect = Exception("DB connection failed")
        result = self.cli_runner.invoke(show_configuration)
        self.assertIn("Error: DB connection failed", result.output)

    @patch('show.memory_statistics.signal.signal')
    def test_main_error(self, mock_signal):
        """Test main function error handling (lines 344, 355)"""
        mock_signal.side_effect = Exception("Signal registration failed")

        with self.assertRaises(SystemExit):
            main()

    def test_socket_manager_validation(self):
        """Test socket path validation (line 409)"""
        with self.assertRaises(ConnectionError):
            SocketManager("/nonexistent/path/socket")


class TestAdditionalMemoryStatisticsCLI(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_dict2obj_with_nested_data(self):
        """Test Dict2Obj with deeply nested dictionaries"""
        data = {'a': {'b': {'c': 1}}, 'list': [1, {'d': 2}]}
        obj = Dict2Obj(data)
        self.assertEqual(obj.a.b.c, 1)
        self.assertEqual(obj.list[1].d, 2)
        self.assertEqual(obj.to_dict(), data)

    @patch('show.memory_statistics.SocketManager')
    def test_socket_manager_close_exception(self, mock_socket_manager):
        """Test SocketManager close handles exceptions gracefully"""
        mock_socket_instance = mock_socket_manager.return_value
        mock_socket_instance.close.side_effect = Exception("Close error")

        manager = SocketManager()
        manager.sock = mock_socket_instance

        with patch('syslog.syslog') as mock_syslog:
            manager.close()
            mock_syslog.assert_any_call(4, "Error closing socket: Close error")

    def test_dict2obj_repr(self):
        """Test the __repr__ method of Dict2Obj"""
        data = {'a': 1, 'b': {'c': 2}}
        obj = Dict2Obj(data)
        repr_str = repr(obj)
        self.assertTrue(repr_str.startswith('<Dict2Obj '))
        self.assertIn("'a': 1", repr_str)
        self.assertIn("'b': {'c': 2}", repr_str)

    def test_send_data_no_response(self):
        """Test send_data handling of empty response"""
        with patch('show.memory_statistics.SocketManager') as mock_socket_manager:
            mock_socket_instance = mock_socket_manager.return_value
            mock_socket_instance.connect.return_value = None
            mock_socket_instance.receive_all.return_value = None
            mock_socket_instance.sock = MagicMock()

            with self.assertRaises(ConnectionError) as context:
                send_data(
                    'memory_statistics_command_request_handler',
                    {'type': 'system', 'metric_name': 'total_memory'},
                    quiet=False
                )
            self.assertIn("No response received", str(context.exception))


if __name__ == '__main__':
    unittest.main()
