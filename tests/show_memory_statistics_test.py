import json
import os
import socket
import signal
import syslog
import unittest
from unittest.mock import MagicMock, Mock, patch

import click
from click.testing import CliRunner
import pytest

from show.memory_statistics import (
    Config,
    ConnectionError,
    DatabaseError,
    Dict2Obj,
    SonicDBConnector,
    SocketManager,
    ResourceManager,
    send_data,
    format_field_value,
    display_config,
    show_statistics,
    show_configuration,
    shutdown_handler,
    main,
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
    
    def test_dict2obj_invalid_input(self):
        with pytest.raises(ValueError):
            Dict2Obj("invalid_input")

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


class TestHelperFunctions(unittest.TestCase):
    """Tests for helper functions"""

    def test_format_field_value(self):
        """Test field value formatting"""
        self.assertEqual(format_field_value("enabled", "true"), "True")
        self.assertEqual(format_field_value("enabled", "false"), "False")
        self.assertEqual(format_field_value("retention_period", "15"), "15")
        self.assertEqual(format_field_value("sampling_interval", "Unknown"), "Not configured")

    # New test case for ResourceManager
    def test_resource_manager_cleanup_no_resources(self):
        """Test ResourceManager cleanup when no resources exist"""
        resource_manager = ResourceManager()
        resource_manager.cleanup()  # Should not raise any errors

    # New test case for shutdown_handler
    def test_shutdown_handler_cleanup(self):
        """Test shutdown_handler performs cleanup"""
        resource_manager = ResourceManager()
        resource_manager.db_connector = MagicMock()
        resource_manager.socket_manager = MagicMock()
        
        # Use pytest.raises to catch the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            shutdown_handler(signal.SIGTERM, None, resource_manager)
        
        # Verify cleanup was called
        resource_manager.socket_manager.close.assert_called_once()
        # Verify exit code is 0
        assert exc_info.value.code == 0

class TestSendData(unittest.TestCase):
    """Tests for send_data function"""

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


    @patch('show.memory_statistics.SocketManager')
    def test_send_data_json_decode_error(self, mock_socket_manager):
        """Test send_data handles JSON decode errors"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        mock_instance.receive_all.return_value = "invalid json"

        with self.assertRaises(ValueError):
            send_data("test_command", {})

    @patch('show.memory_statistics.SocketManager')
    def test_send_data_invalid_response_format(self, mock_socket_manager):
        """Test send_data handles invalid response format"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        mock_instance.receive_all.return_value = json.dumps(["not a dict"])

        with self.assertRaises(ValueError):
            send_data("test_command", {})

    @patch("show.memory_statistics.SocketManager")
    def test_send_data_invalid_response(self, mock_socket_manager):
        """Test send_data with invalid JSON response"""
        mock_instance = Mock()
        mock_socket_manager.return_value = mock_instance
        mock_instance.receive_all.return_value = "invalid_json"

        with self.assertRaises(ValueError):
            send_data("test_command", {})



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

    @patch('show.memory_statistics.ConfigDBConnector')
    def test_get_memory_statistics_config_invalid_data(self, mock_connector):
        """Test get_memory_statistics_config with invalid data"""
        mock_instance = mock_connector.return_value
        mock_instance.connect = MagicMock()
        mock_instance.get_table = MagicMock(return_value={"invalid_key": "invalid_value"})

        db_connector = SonicDBConnector()
        config = db_connector.get_memory_statistics_config()
        assert config == Config.DEFAULT_CONFIG

    @patch('show.memory_statistics.click.echo')
    @patch('show.memory_statistics.SonicDBConnector')
    def test_show_configuration_database_error(self, mock_sonic_db, mock_echo):
        """Test show_configuration handles database errors"""
        mock_instance = mock_sonic_db.return_value
        mock_instance.get_memory_statistics_config.side_effect = Exception("DB error")

        runner = CliRunner()
        with patch('show.memory_statistics.sys.exit') as mock_exit:
            runner.invoke(show_configuration, catch_exceptions=False)

            mock_echo.assert_any_call("Error: Failed to retrieve configuration: DB error", err=True)

            assert mock_exit.call_count >= 1
            mock_exit.assert_any_call(1)

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
    def test_socket_send_error(self, mock_socket):
        """Test socket send error (line 166)"""
        manager = SocketManager()
        mock_socket.return_value.sendall.side_effect = socket.error("Send failed")
        manager.sock = mock_socket.return_value

        with self.assertRaises(ConnectionError):
            manager.send("test data")

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
            mock_socket_instance.receive_all.return_value = None  # Simulate no response
            mock_socket_instance.sock = MagicMock()

            with self.assertRaises(ConnectionError) as context:
                send_data(
                    'memory_statistics_command_request_handler',
                    {'type': 'system', 'metric_name': 'total_memory'},
                    quiet=False
                )
            self.assertIn("No response received", str(context.exception))


class TestSonicDBConnector(unittest.TestCase):
    """Tests for SonicDBConnector class"""

    @patch('show.memory_statistics.ConfigDBConnector')
    def setUp(self, mock_config_db):
        self.mock_config_db = mock_config_db
        self.connector = SonicDBConnector()
        self.mock_config_db.reset_mock()

    def test_connect_with_retry_success_after_retries(self):
        """Test _connect_with_retry succeeds after retries"""
        mock_instance = self.mock_config_db.return_value
        mock_instance.connect.side_effect = [
            socket.error("Failed"),
            socket.error("Failed"),
            None
        ]
        
        self.connector._connect_with_retry(max_retries=3, retry_delay=0.1)
        assert mock_instance.connect.call_count == 3

    def test_connect_with_retry_failure(self):
        """Test _connect_with_retry raises ConnectionError after max retries"""
        mock_instance = self.mock_config_db.return_value
        mock_instance.connect.side_effect = socket.error("Failed")
        
        with pytest.raises(ConnectionError) as exc_info:
            self.connector._connect_with_retry(max_retries=2, retry_delay=0.1)
        
        assert "Failed to connect to SONiC config database after 2 attempts" in str(exc_info.value)
        assert mock_instance.connect.call_count == 2

    def test_get_memory_statistics_config_missing_table(self):
        """Test get_memory_statistics_config with missing table"""
        mock_instance = self.mock_config_db.return_value
        mock_instance.get_table.return_value = {}
        
        config = self.connector.get_memory_statistics_config()
        assert config == Config.DEFAULT_CONFIG

    def test_get_memory_statistics_config_invalid_table(self):
        """Test get_memory_statistics_config with invalid table data"""
        mock_instance = self.mock_config_db.return_value
        mock_instance.get_table.return_value = {"memory_statistics": "invalid"}
        
        config = self.connector.get_memory_statistics_config()
        assert config == Config.DEFAULT_CONFIG

    def test_send_data_database_error(self):
        """Test send_data with database error response"""
        error_response = {"status": False, "msg": "Database error"}
        
        with patch('show.memory_statistics.SocketManager') as mock_socket:
            instance = mock_socket.return_value
            instance.receive_all.return_value = json.dumps(error_response)
            
            with pytest.raises(DatabaseError):
                send_data("test_command", {}, quiet=True)


class TestSocketValidation:

    def test_validate_socket_path_missing_directory(self):
        with pytest.raises(ConnectionError):
            SocketManager("/nonexistent/path/socket")

    def test_validate_socket_path_create_if_missing(self, tmpdir):
        socket_path = tmpdir.join("test.socket")
        manager = SocketManager(str(socket_path))
        assert os.path.exists(str(socket_path))
        assert oct(os.stat(str(socket_path)).st_mode & 0o777) == '0o600'

    def test_validate_socket_path_invalid_permissions(self, tmpdir):
        socket_path = tmpdir.join("test.socket")
        socket_path.write("")
        os.chmod(str(socket_path), 0o777)
        
        with pytest.raises(PermissionError):
            SocketManager(str(socket_path))


class TestSocketManager:
    def test_socket_connect_failure(self):
        socket_manager = SocketManager()
        socket_manager.sock = MagicMock()
        socket_manager.sock.connect.side_effect = socket.error("Connection failed")

        with pytest.raises(ConnectionError):
            socket_manager.connect()

    def test_socket_receive_all_timeout(self):
        socket_manager = SocketManager()
        socket_manager.sock = MagicMock()
        socket_manager.sock.recv.side_effect = socket.timeout("Timeout")

        with pytest.raises(ConnectionError):
            socket_manager.receive_all(expected_size=1024)

    def test_socket_send_error(self):
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.sendall.side_effect = socket.error("Send failed")
            manager = SocketManager()
            manager.sock = mock_socket.return_value
            with pytest.raises(ConnectionError):
                manager.send("test data")

    def test_socket_connect_retry_success(self):
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = [socket.error("Failed"), socket.error("Failed"), None]
            manager = SocketManager()
            manager.connect()
            assert mock_socket.return_value.connect.call_count == 3

    def test_socket_connect_retry_failure(self):
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = socket.error("Failed")
            manager = SocketManager()
            with pytest.raises(ConnectionError):
                manager.connect()

    def test_receive_all_incomplete_data(self):
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.recv.return_value = b"partial"
            manager = SocketManager()
            manager.sock = mock_socket.return_value
            result = manager.receive_all(expected_size=10, max_attempts=1)
            assert result == "partial"

    def test_socket_close_error(self):
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.close.side_effect = Exception("Close error")
            manager = SocketManager()
            manager.sock = mock_socket.return_value
            with patch('syslog.syslog') as mock_syslog:
                manager.close()
                mock_syslog.assert_called_with(syslog.LOG_WARNING, "Error closing socket: Close error")


class TestMainFunction(unittest.TestCase):
    """Tests for the main function"""

    @patch("show.memory_statistics.cli")
    def test_main_cli_failure(self, mock_cli):
        """Test main handles CLI failure"""
        mock_cli.side_effect = Exception("CLI failed")
        with self.assertRaises(SystemExit):  # Expect SystemExit instead of Exception
            main()

    @patch('sys.exit')
    @patch('click.echo')
    @patch('show.memory_statistics.cli')
    def test_main_cli_failure_with_handling(self, mock_cli, mock_echo, mock_exit):
        """Test main function handles CLI failure gracefully"""
        mock_cli.side_effect = Exception("CLI failed")
        main()
        mock_echo.assert_called_with("Error: CLI failed", err=True)
        mock_exit.assert_called_with(1)

    @patch('signal.signal')
    def test_main_signal_registration_error(self, mock_signal):
        """Test main handles signal registration errors"""
        mock_signal.side_effect = Exception("Signal error")
        with self.assertRaises(SystemExit):
            main()


if __name__ == '__main__':
    unittest.main()
