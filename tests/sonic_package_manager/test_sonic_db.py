import pytest
from unittest.mock import MagicMock, call, patch

from sonic_package_manager.service_creator.sonic_db import SonicDB


class TestGetNamespaceDbConnectors:

    def setup_method(self):
        SonicDB._namespace_db_conns = None
        SonicDB._running_db_conn = None

    def teardown_method(self):
        SonicDB._namespace_db_conns = None
        SonicDB._running_db_conn = None

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=True)
    def test_returns_empty_in_chroot(self, mock_in_chroot):
        assert SonicDB.get_namespace_db_connectors() == []

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    def test_returns_empty_on_single_asic(self, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = False
        assert SonicDB.get_namespace_db_connectors() == []
        mock_device_info.get_namespaces.assert_not_called()

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    def test_single_asic_result_is_cached(self, mock_device_info, mock_in_chroot):
        # Single-ASIC result is cached: the platform check runs only once.
        mock_device_info.is_multi_npu.return_value = False

        assert SonicDB.get_namespace_db_connectors() == []
        assert SonicDB.get_namespace_db_connectors() == []

        assert mock_device_info.is_multi_npu.call_count == 1

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_returns_connectors_on_multi_asic(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0', 'asic1']
        mock_swsscommon.SonicDBConfig.isGlobalInit.return_value = False

        # Distinct connectors per namespace, so the test fails if both
        # namespaces collapse onto a single shared connector instance.
        conn0 = MagicMock()
        conn1 = MagicMock()
        mock_swsscommon.ConfigDBConnector.side_effect = [conn0, conn1]

        result = SonicDB.get_namespace_db_connectors()

        assert result == [conn0, conn1]
        assert mock_swsscommon.ConfigDBConnector.call_args_list == [
            call(namespace='asic0'),
            call(namespace='asic1'),
        ]
        conn0.connect.assert_called_once_with()
        conn1.connect.assert_called_once_with()
        mock_swsscommon.SonicDBConfig.initializeGlobalConfig.assert_called_once()

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_skips_global_init_when_already_initialized(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0']
        mock_swsscommon.SonicDBConfig.isGlobalInit.return_value = True

        SonicDB.get_namespace_db_connectors()

        mock_swsscommon.SonicDBConfig.initializeGlobalConfig.assert_not_called()

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_connection_failure_propagates(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        # A failed namespace connect must raise, not yield a partial set.
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0', 'asic1']
        mock_swsscommon.SonicDBConfig.isGlobalInit.return_value = False

        good_conn = MagicMock()
        bad_conn = MagicMock()
        bad_conn.connect.side_effect = RuntimeError("connection failed")
        mock_swsscommon.ConfigDBConnector.side_effect = [good_conn, bad_conn]

        with pytest.raises(RuntimeError, match="connection failed"):
            SonicDB.get_namespace_db_connectors()

        # Failed run is not cached, so the next call retries.
        assert SonicDB._namespace_db_conns is None

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_connected_namespaces_are_cached(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0']
        mock_swsscommon.SonicDBConfig.isGlobalInit.return_value = False

        mock_conn = MagicMock()
        mock_swsscommon.ConfigDBConnector.return_value = mock_conn

        result1 = SonicDB.get_namespace_db_connectors()
        result2 = SonicDB.get_namespace_db_connectors()

        assert result1 is result2
        assert result1 == [mock_conn]
        # Cached: not reconnected on later calls.
        assert mock_swsscommon.ConfigDBConnector.call_count == 1


class TestGetConnectorsWithNamespaces:

    def setup_method(self):
        SonicDB._namespace_db_conns = None
        SonicDB._running_db_conn = None

    def teardown_method(self):
        SonicDB._namespace_db_conns = None
        SonicDB._running_db_conn = None

    @patch.object(SonicDB, 'get_namespace_db_connectors')
    @patch.object(SonicDB, 'get_running_db_connector')
    @patch.object(SonicDB, 'get_initial_db_connector')
    def test_yields_namespace_connectors_when_running_db_exists(
            self, mock_initial, mock_running, mock_ns):
        mock_init_conn = MagicMock()
        mock_run_conn = MagicMock()
        mock_ns_conn = MagicMock()

        mock_initial.return_value = mock_init_conn
        mock_running.return_value = mock_run_conn
        mock_ns.return_value = [mock_ns_conn]

        connectors = list(SonicDB.get_connectors())
        assert connectors == [mock_init_conn, mock_run_conn, mock_ns_conn]

    @patch.object(SonicDB, 'get_namespace_db_connectors')
    @patch.object(SonicDB, 'get_running_db_connector')
    @patch.object(SonicDB, 'get_initial_db_connector')
    def test_no_namespace_connectors_when_no_running_db(
            self, mock_initial, mock_running, mock_ns):
        mock_init_conn = MagicMock()
        mock_initial.return_value = mock_init_conn
        mock_running.return_value = None

        connectors = list(SonicDB.get_connectors())
        assert connectors == [mock_init_conn]
        mock_ns.assert_not_called()
