from unittest import mock

import os
import sys
import dbus

from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, 'scripts')
sys.path.insert(0, modules_path)

# Load the file under test
scripts_path = os.path.join(scripts_path, 'gpins_techsupport')
techsupport = load_module_from_source('gpins_techsupport', scripts_path)


class TestGpinsTechSupport(object):
    @mock.patch.object(dbus, 'SystemBus', autospec=True)
    @mock.patch('builtins.print', autospec=True)
    def test_host_service_success(self, mock_print, mock_system_bus):
        mock_object = mock.Mock()
        mock_object.collect.return_value = (0, '/var/dump/foo')
        mock_dbus = mock.Mock()
        mock_dbus.get_object.return_value = mock_object
        mock_system_bus.return_value = mock_dbus
        assert techsupport.main() == 0
        mock_system_bus.assert_called_once_with()
        mock_dbus.get_object.assert_called_once_with(
            "org.SONiC.HostService.debug_info", "/org/SONiC/HostService/debug_info")
        mock_object.collect.assert_called_once_with(
            ['{"component": "all", "level": "all"}'])
        mock_print.assert_called_once_with(
            'Debug artifact saved in /tmp/dump/foo')

    @mock.patch.object(dbus, 'SystemBus', autospec=True)
    @mock.patch('builtins.print', autospec=True)
    def test_host_service_fail(self, mock_print, mock_system_bus):
        mock_object = mock.Mock()
        mock_object.collect.return_value = (1, 'fail reason')
        mock_dbus = mock.Mock()
        mock_dbus.get_object.return_value = mock_object
        mock_system_bus.return_value = mock_dbus
        assert techsupport.main() == 1
        mock_system_bus.assert_called_once_with()
        mock_dbus.get_object.assert_called_once_with(
            "org.SONiC.HostService.debug_info", "/org/SONiC/HostService/debug_info")
        mock_object.collect.assert_called_once_with(
            ['{"component": "all", "level": "all"}'])
        mock_print.assert_called_once_with(
            'Failed to collect debug artifact: fail reason')
