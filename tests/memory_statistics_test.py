import unittest
from unittest.mock import patch, MagicMock
import click
from click.testing import CliRunner
import json
import socket

# Import the functions to be tested
from show.memory_statistics import (
    send_data,
    display_statistics,
    clean_and_print,
    memory_stats,
    SocketManager,
    Dict2Obj,
    ConnectionError
)


class TestMemoryStatisticsCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch('show.memory_statistics.send_data')
    def test_display_statistics_successful(self, mock_send_data):
        """
        Test successful retrieval and display of memory statistics
        """
        # Create a mock response using Dict2Obj to match the expected structure
        mock_response_data = {
            'status': True,
            'data': "Memory Statistics:\nTotal Memory: 16GB\nUsed Memory: 8GB"
        }
        mock_response = Dict2Obj(mock_response_data)  # Use actual Dict2Obj

        # Configure the mock to return the Dict2Obj instance
        mock_send_data.return_value = mock_response

        # Capture stdout
        with patch('sys.stdout', new_callable=MagicMock) as mock_stdout:
            # Call the function with test parameters
            display_statistics(
                click.Context(click.Command('memory-stats')),
                from_time='1 hour ago',
                to_time='now',
                select_metric='total_memory'
            )

            # Verify output
            captured_output = ''.join(call[0][0] for call in mock_stdout.write.call_args_list)
            self.assertIn("Memory Statistics:\nTotal Memory: 16GB\nUsed Memory: 8GB", captured_output)

    def test_clean_and_print_valid_data(self):
        """
        Test clean_and_print function with valid data
        """
        with patch('sys.stdout', new_callable=MagicMock) as mock_stdout:
            clean_and_print({
                'data': "Memory Stats:\nTotal: 16GB\nUsed: 8GB"
            })
            output = ''.join(call[0][0] for call in mock_stdout.write.call_args_list)
            self.assertIn("Memory Stats:\nTotal: 16GB\nUsed: 8GB", output)

    def test_clean_and_print_invalid_data(self):
        """
        Test clean_and_print function with invalid data
        """
        with patch('sys.stdout', new_callable=MagicMock) as mock_stdout:
            clean_and_print([])  # Invalid data type
            output = ''.join(call[0][0] for call in mock_stdout.write.call_args_list)
            self.assertIn("Error: Invalid data format received", output)

    @patch('show.memory_statistics.send_data')  # Fixed patch path
    def test_display_statistics_error_handling(self, mock_send_data):
        """
        Test error handling in display_statistics
        """
        # Simulate exception
        mock_send_data.side_effect = Exception("Connection error")

        result = self.runner.invoke(memory_stats, [
            '--from', '1 hour ago',
            '--to', 'now',
            '--select', 'total_memory'
        ])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Error:", result.output)

    @patch('show.memory_statistics.SocketManager')  # Fixed patch path
    def test_send_data_successful(self, mock_socket_manager):
        """
        Test send_data function with successful socket communication
        """
        # Setup mock socket manager
        mock_socket_manager_instance = MagicMock()
        mock_socket_manager.return_value = mock_socket_manager_instance
        mock_socket_manager_instance.connect.return_value = None
        mock_socket_manager_instance.receive_all.return_value = json.dumps({
            'status': True,
            'data': 'Test response'
        })
        mock_socket_manager_instance.sock = MagicMock()  # Simulate sending

        # Call send_data
        result = send_data(
            'memory_statistics_command_request_handler',
            {'type': 'system', 'metric_name': 'total_memory'}
        )

        # Verify interactions
        mock_socket_manager_instance.connect.assert_called_once()
        mock_socket_manager_instance.receive_all.assert_called_once()
        self.assertTrue(result.status)

    def test_send_data_connection_error(self):
        """
        Test send_data function with connection errors
        """
        with self.assertRaises(Exception):
            send_data(
                'memory_statistics_command_request_handler',
                {'type': 'system', 'metric_name': 'total_memory'},
                quiet=True
            )


class TestAdditionalMemoryStatisticsCLI(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    # ---- Tests for Dict2Obj Class ---- #

    def test_dict2obj_with_empty_dict(self):
        """Test Dict2Obj with an empty dictionary"""
        obj = Dict2Obj({})
        self.assertEqual(obj.to_dict(), {})

    def test_dict2obj_with_nested_data(self):
        """Test Dict2Obj with deeply nested dictionaries"""
        data = {'a': {'b': {'c': 1}}, 'list': [1, {'d': 2}]}
        obj = Dict2Obj(data)
        self.assertEqual(obj.a.b.c, 1)
        self.assertEqual(obj.list[1].d, 2)
        self.assertEqual(obj.to_dict(), data)

    def test_dict2obj_invalid_input(self):
        """Test Dict2Obj with invalid input (non-dict, non-list)"""
        with self.assertRaises(ValueError):
            Dict2Obj("invalid_input")

    # ---- Tests for SocketManager ---- #

    @patch('socket.socket')
    def test_socket_manager_connect_success(self, mock_socket):
        """Test SocketManager connects successfully"""
        mock_socket_instance = mock_socket.return_value
        manager = SocketManager(socket_path='/tmp/test.socket')

        manager.connect()
        mock_socket_instance.connect.assert_called_once()

    @patch('socket.socket')
    def test_socket_manager_connection_retries(self, mock_socket):
        """Test SocketManager retries connection on failure"""
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.connect.side_effect = socket.error("Connection failed")

        manager = SocketManager(socket_path='/tmp/test.socket')
        with self.assertRaises(ConnectionError):
            manager.connect()

        self.assertEqual(mock_socket_instance.connect.call_count, 3)  # Retries 3 times

    @patch('socket.socket')
    def test_socket_manager_receive_all_timeout(self, mock_socket):
        """Test SocketManager receive_all handles timeout"""
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.recv.side_effect = socket.timeout

        manager = SocketManager()
        manager.sock = mock_socket_instance

        with self.assertRaises(ConnectionError):
            manager.receive_all()

    @patch('socket.socket')
    def test_socket_manager_send_error(self, mock_socket):
        """Test SocketManager send method handles errors"""
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.sendall.side_effect = socket.error("Send error")

        manager = SocketManager()
        manager.sock = mock_socket_instance

        with self.assertRaises(ConnectionError):
            manager.send("test data")

    # ---- Tests for send_data Function---- #

    @patch('show.memory_statistics.SocketManager')
    def test_send_data_invalid_response_format(self, mock_socket_manager):
        """Test send_data when the response format is invalid"""
        mock_socket_instance = mock_socket_manager.return_value
        mock_socket_instance.receive_all.return_value = "INVALID_JSON"

        with self.assertRaises(ValueError):
            send_data("test_command", {"data": "test"})

    @patch('show.memory_statistics.SocketManager')
    def test_send_data_failed_status(self, mock_socket_manager):
        """Test send_data with a response indicating failure"""
        mock_socket_instance = mock_socket_manager.return_value
        mock_socket_instance.receive_all.return_value = json.dumps({
            'status': False,
            'msg': 'Test failure'
        })

        with self.assertRaises(RuntimeError):
            send_data("test_command", {"data": "test"})

    # ---- CLI Command Tests ---- #

    @patch('show.memory_statistics.send_data')
    def test_memory_stats_missing_options(self, mock_send_data):
        """Test memory_stats CLI command with missing options"""
        result = self.runner.invoke(memory_stats, [])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Error:", result.output)

    @patch('show.memory_statistics.send_data')
    def test_memory_stats_invalid_server_response(self, mock_send_data):
        """Test memory_stats with invalid server response"""
        mock_send_data.return_value = "INVALID_RESPONSE"

        result = self.runner.invoke(memory_stats, [
            '--from', '1 hour ago',
            '--to', 'now',
            '--select', 'used_memory'
        ])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unexpected response type", result.output)

    @patch('show.memory_statistics.send_data')
    def test_memory_stats_with_valid_output(self, mock_send_data):
        """Test memory_stats with valid input and output"""
        mock_send_data.return_value = Dict2Obj({
            'status': True,
            'data': "Memory Stats:\nTotal: 16GB\nUsed: 12GB"
        })

        result = self.runner.invoke(memory_stats, [
            '--from', '1 day ago',
            '--to', 'now',
            '--select', 'used_memory'
        ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Memory Stats:\nTotal: 16GB\nUsed: 12GB", result.output)

    # ---- Additional Edge Cases ---- #

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

    def test_clean_and_print_empty_data(self):
        """Test clean_and_print with empty data"""
        with patch('sys.stdout', new_callable=MagicMock) as mock_stdout:
            clean_and_print({'data': ""})
            output = ''.join(call[0][0] for call in mock_stdout.write.call_args_list)
            self.assertIn("Memory Statistics:\n", output)

    @patch('show.memory_statistics.send_data')
    def test_memory_stats_quiet_mode(self, mock_send_data):
        """Test CLI error output in quiet mode"""
        mock_send_data.side_effect = Exception("Connection error")

        result = self.runner.invoke(memory_stats, [
            '--from', '1 hour ago',
            '--to', 'now',
            '--select', 'total_memory'
        ], catch_exceptions=True)

        self.assertIn("Connection error", result.output)

    def test_dict2obj_with_list_of_dicts(self):
        """Test Dict2Obj with a list of dictionaries"""
        data = [{'a': 1}, {'b': 2}]
        obj = Dict2Obj(data)
        self.assertEqual(len(obj.items), 2)
        self.assertEqual(obj.items[0].a, 1)
        self.assertEqual(obj.items[1].b, 2)

    def test_dict2obj_repr(self):
        """Test the __repr__ method of Dict2Obj"""
        data = {'a': 1, 'b': {'c': 2}}
        obj = Dict2Obj(data)
        repr_str = repr(obj)
        self.assertTrue(repr_str.startswith('<Dict2Obj '))
        self.assertIn("'a': 1", repr_str)
        self.assertIn("'b': {'c': 2}", repr_str)

    def test_socket_manager_validate_socket_path_error(self):
        """Test SocketManager validation with non-existent directory"""
        with patch('os.path.exists', return_value=False):
            with patch('os.path.dirname', return_value='/nonexistent/path'):
                with patch('syslog.syslog') as mock_syslog:
                    with self.assertRaises(ConnectionError):
                        SocketManager('/var/run/test.socket')
                    # Verify syslog was called with the error message
                    mock_syslog.assert_called_with(3, "Socket directory /nonexistent/path does not exist")

    def test_send_data_json_decode_error(self):
        """Test send_data handling of JSON decoding errors"""
        with patch('show.memory_statistics.SocketManager') as mock_socket_manager:
            mock_socket_instance = mock_socket_manager.return_value
            mock_socket_instance.connect.return_value = None
            mock_socket_instance.receive_all.return_value = "Invalid JSON"
            mock_socket_instance.sock = MagicMock()

            with self.assertRaises(ValueError) as context:
                send_data(
                    'memory_statistics_command_request_handler', 
                    {'type': 'system', 'metric_name': 'total_memory'},
                    quiet=False
                )
            # Verify the error message
            self.assertIn("Failed to parse server response", str(context.exception))

    def test_send_data_runtime_error(self):
        """Test send_data handling of server-side errors"""
        with patch('show.memory_statistics.SocketManager') as mock_socket_manager:
            mock_socket_instance = mock_socket_manager.return_value
            mock_socket_instance.connect.return_value = None
            mock_socket_instance.receive_all.return_value = json.dumps({
                'status': False,
                'msg': 'Server-side error'
            })
            mock_socket_instance.sock = MagicMock()

            with self.assertRaises(RuntimeError) as context:
                send_data(
                    'memory_statistics_command_request_handler', 
                    {'type': 'system', 'metric_name': 'total_memory'},
                    quiet=False
                )
            self.assertIn('Server-side error', str(context.exception))

def main():
    """Run the tests"""
    unittest.main()


if __name__ == '__main__':
    main()
