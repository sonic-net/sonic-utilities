import pytest
import importlib
from unittest import mock
from mock import patch
fast_reboot_filter_routes = importlib.import_module("scripts.fast-reboot-filter-routes")

class TestFastRebootFilterRoutes(object):
    def setup_method(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes(self, mock_run_command):
        mock_run_command.side_effect = [('{"1.1.0.0/16": {}}', 0), ('{"2001:db8:1::/64": {}}', 0)]
        output = fast_reboot_filter_routes.get_connected_routes()
        mock_run_command.assert_has_calls([
            mock.call(['sudo', 'vtysh', '-c', "show ip route connected json"], return_cmd=True),
            mock.call(['sudo', 'vtysh', '-c', "show ipv6 route connected json"], return_cmd=True)
        ])
        assert output == ['1.1.0.0/16', '2001:db8:1::/64']

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes_command_failed(self, mock_run_command):
        mock_run_command.return_value = ('{"1.1.0.0/16": {}}', 1)
        with pytest.raises(Exception):
            fast_reboot_filter_routes.get_connected_routes()
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', "show ip route connected json"], return_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes_ipv6_command_failed(self, mock_run_command):
        mock_run_command.side_effect = [('{"1.1.0.0/16": {}}', 0), ('', 1)]
        with pytest.raises(Exception):
            fast_reboot_filter_routes.get_connected_routes()
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', "show ipv6 route connected json"], return_cmd=True)

    def teardown_method(self):
        print("TEAR DOWN")
