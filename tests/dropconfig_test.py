import os
import pytest
from unittest.mock import call, patch, MagicMock
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

dropconfig_path = os.path.join(scripts_path, 'dropconfig')
dropconfig = load_module_from_source('dropconfig', dropconfig_path)

class TestDropConfig(object):
    def setup(self):
        print('SETUP')

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'install'])
    def test_install_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to install counter: Counter name not provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'install',
                        '-n', 'DEBUG_2', '-t', 'PORT_INGRESS_DROPS',
                        '-r', '[EXCEEDS_L2_MTU]', '-w', '300'])
    def test_install_insufficient_arg_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        err_msg = ("Encountered error trying to install counter: "
                   "If a drop monitor is to be installed, "
                   "all three arguments (window, drop_count_threshold and "
                   "incident_count threshold) must be provided")
        mock_print.assert_called_once_with(err_msg)
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'install',
                        '-n', 'DEBUG_10', '-t', 'PORT_INGRESS_DROPS',
                        '-r', '[IP_HEADER_ERROR]', '-w', '300',
                        '-ict', '2', '-dct', '10'])
    def test_install_debug_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'uninstall'])
    def test_delete_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to uninstall counter: No counter name provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'add'])
    def test_add_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to add reasons: No counter name provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'remove'])
    def test_remove_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to remove reasons: No counter name provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor'])
    def test_enable_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'disable_drop_monitor'])
    def test_disable_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor'])
    def test_enable_global_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0
        mock_print.assert_called_once_with('Drop counter monitor is globally enabled.')

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor', '-n', 'DEBUG_0'])
    def test_enable_specific_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0
        mock_print.assert_called_once_with('Drop counter monitor is enabled for counter DEBUG_0')

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'disable_drop_monitor'])
    def test_disable_global_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0
        mock_print.assert_called_once_with('Drop counter monitor is globally disabled.')

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'disable_drop_monitor', '-n', 'DEBUG_0'])
    def test_disable_specific_monitor(self, mock_print):
        try:
            dropconfig.main()
        except SystemExit as e:
            assert e.code == 0
        mock_print.assert_called_once_with('Drop counter monitor is disabled for counter DEBUG_0')

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor', '-n', 'INVALID'])
    def test_invalid_counter_enable_monitor_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        error_message = ("Encountered error trying to enable drop monitor: "
                         "Counter 'INVALID' not found")
        mock_print.assert_called_once_with(error_message)
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'disable_drop_monitor', '-n', 'INVALID'])
    def test_invalid_counter_disable_monitor_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        error_message = ("Encountered error trying to disable drop monitor: "
                         "Counter 'INVALID' not found")
        mock_print.assert_called_once_with(error_message)
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor', '-n', 'DEBUG_0', '-w', '-1'])
    def test_invalid_window_enable_monitor_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        err_msg = ("Encountered error trying to enable drop monitor: Invalid window size. "
                   "Window size should be positive, received: -1")
        mock_print.assert_called_once_with(err_msg)
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor', '-n', 'DEBUG_0', '-ict', '-1'])
    def test_invalid_ict_enable_monitor_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        err_msg = ("Encountered error trying to enable drop monitor: Invalid incident count threshold. "
                   "Incident count threshold should be non-negative, received: -1")
        mock_print.assert_called_once_with(err_msg)
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'enable_drop_monitor', '-n', 'DEBUG_0', '-dct', '-1'])
    def test_invalid_dct_enable_monitor_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        err_msg = ("Encountered error trying to enable drop monitor: Invalid drop count threshold. "
                   "Drop count threshold should be non-negative, received: -1")
        mock_print.assert_called_once_with(err_msg)
        assert e.value.code == 1

    def teardown(self):
        print('TEARDOWN')

