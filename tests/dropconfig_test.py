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
    @patch('sys.argv', ['dropconfig', '-c', 'config_monitor', '-s', 'off'])
    def test_config_monitor_status_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to configure drop monitor: '
                                           'Invalid status: off, expected: enabled/disabled')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'config_monitor', '-w', '-1'])
    def test_config_monitor_window_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to configure drop monitor: '
                                           'Invalid window size. Window size should be positive, received: -1')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'config_monitor', '-dct', '-1'])
    def test_config_monitor_dct_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to configure drop monitor: '
                                           'Invalid drop count threshold. '
                                           'Drop count threshold should be positive, received: -1')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'config_monitor', '-ict', '-1'])
    def test_config_monitor_ict_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to configure drop monitor: '
                                           'Invalid incident count threshold. Incident count threshold '
                                           'should be positive, received: -1')
        assert e.value.code == 1

    def teardown(self):
        print('TEARDOWN')

