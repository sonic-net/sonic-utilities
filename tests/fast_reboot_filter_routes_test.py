import pytest
import importlib
from unittest import mock
from mock import patch
fast_reboot_filter_routes = importlib.import_module("scripts.fast-reboot-filter-routes")

class TestFastRebootFilterRoutes(object):
    def setup(self):
        print("SETUP")

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes(self, mock_run_command):
        mock_run_command.return_value = ('{"1.1.0.0/16": {}}', 0)
        output = fast_reboot_filter_routes.get_connected_routes()
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', "show ip route connected json"], return_cmd=True)
        assert output == ['1.1.0.0/16']

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes_command_failed(self, mock_run_command):
        mock_run_command.return_value = ('{"1.1.0.0/16": {}}', 1)
        with pytest.raises(Exception):
            fast_reboot_filter_routes.get_connected_routes()
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', "show ip route connected json"], return_cmd=True)

    def teardown(self):
        print("TEAR DOWN")
