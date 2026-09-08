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
        mock_run_command.return_value = ('{"1.1.0.0/16": {}}', 0)
        output = fast_reboot_filter_routes.get_connected_routes(namespace="")
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', "show ip route connected json"], return_cmd=True)
        assert output == ['1.1.0.0/16']

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes_command_failed(self, mock_run_command):
        mock_run_command.return_value = ('{"1.1.0.0/16": {}}', 1)
        with pytest.raises(Exception):
            fast_reboot_filter_routes.get_connected_routes(namespace="")
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', "show ip route connected json"], return_cmd=True)

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes_for_namespace(self, mock_run_command):
        mock_run_command.return_value = ('{"2.2.0.0/16": {}}', 0)
        with mock.patch.object(fast_reboot_filter_routes.multi_asic,
                               'get_asic_id_from_name',
                               return_value='0') as mock_get_asic_id:
            output = fast_reboot_filter_routes.get_connected_routes(namespace="asic0")

        mock_get_asic_id.assert_called_once_with("asic0")
        mock_run_command.assert_called_with(
            ['sudo', 'vtysh', '-n', '0', '-c', "show ip route connected json"],
            return_cmd=True
        )
        assert output == ['2.2.0.0/16']

    @patch('utilities_common.cli.run_command')
    def test_get_connected_routes_with_empty_output(self, mock_run_command):
        mock_run_command.return_value = (None, 0)
        output = fast_reboot_filter_routes.get_connected_routes(namespace="")
        assert output == []

    def test_get_route(self):
        db = mock.Mock()
        db.APPL_DB = "APPL_DB"
        db.keys.return_value = ["ROUTE_TABLE:0.0.0.0/0"]

        output = fast_reboot_filter_routes.get_route(db, "0.0.0.0/0")

        db.keys.assert_called_once_with("APPL_DB", "ROUTE_TABLE:0.0.0.0/0")
        assert output == "0.0.0.0/0"

    def test_get_route_not_found(self):
        db = mock.Mock()
        db.APPL_DB = "APPL_DB"
        db.keys.return_value = []

        output = fast_reboot_filter_routes.get_route(db, "0.0.0.0/0")

        assert output is None

    def test_generate_default_route_entries(self):
        db = mock.Mock()
        db.APPL_DB = "APPL_DB"
        db.keys.side_effect = [
            ["ROUTE_TABLE:0.0.0.0/0"],
            ["ROUTE_TABLE:::/0"],
        ]

        with mock.patch.object(fast_reboot_filter_routes,
                               'ConfigDBConnector',
                               return_value=db) as mock_config_db:
            output = fast_reboot_filter_routes.generate_default_route_entries("asic0")

        mock_config_db.assert_called_once_with(namespace="asic0")
        db.db_connect.assert_called_once_with("APPL_DB")
        assert output == ["0.0.0.0/0", "::/0"]

    def test_filter_routes(self):
        db = mock.Mock()
        db.APPL_DB = "APPL_DB"
        db.keys.return_value = [
            "ROUTE_TABLE:0.0.0.0/0",
            "ROUTE_TABLE:10.0.0.0/24",
            "ROUTE_TABLE:192.0.2.0/24",
        ]

        with mock.patch.object(fast_reboot_filter_routes,
                               'ConfigDBConnector',
                               return_value=db) as mock_config_db:
            fast_reboot_filter_routes.filter_routes("asic0", {"0.0.0.0/0", "10.0.0.0/24"})

        mock_config_db.assert_called_once_with(namespace="asic0")
        db.db_connect.assert_called_once_with("APPL_DB")
        db.delete.assert_called_once_with("APPL_DB", "ROUTE_TABLE:192.0.2.0/24")

    def test_main_multi_asic(self):
        with mock.patch("sys.argv", ["fast-reboot-filter-routes.py", "-n", "asic0"]), \
             mock.patch.object(fast_reboot_filter_routes.multi_asic,
                               'is_multi_asic',
                               return_value=True), \
             mock.patch.object(fast_reboot_filter_routes.SonicDBConfig,
                               'initializeGlobalConfig') as mock_init_config, \
             mock.patch.object(fast_reboot_filter_routes,
                               'generate_default_route_entries',
                               return_value=["0.0.0.0/0"]) as mock_generate_defaults, \
             mock.patch.object(fast_reboot_filter_routes,
                               'get_connected_routes',
                               return_value=["10.0.0.0/24"]) as mock_get_connected, \
             mock.patch.object(fast_reboot_filter_routes,
                               'filter_routes') as mock_filter_routes:
            output = fast_reboot_filter_routes.main()

        assert output == 0
        mock_init_config.assert_called_once_with()
        mock_generate_defaults.assert_called_once_with("asic0")
        mock_get_connected.assert_called_once_with("asic0")
        mock_filter_routes.assert_called_once_with("asic0", {"0.0.0.0/0", "10.0.0.0/24"})

    def teardown_method(self):
        print("TEAR DOWN")
