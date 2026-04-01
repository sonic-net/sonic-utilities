from unittest.mock import MagicMock, patch

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
        result = SonicDB.get_namespace_db_connectors()
        assert result == []

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    def test_returns_empty_on_single_asic(self, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = False
        result = SonicDB.get_namespace_db_connectors()
        assert result == []

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_returns_connectors_on_multi_asic(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0', 'asic1']

        mock_conn = MagicMock()
        mock_swsscommon.ConfigDBConnector.return_value = mock_conn

        with patch('swsscommon.swsscommon.SonicDBConfig.initializeGlobalConfig'):
            result = SonicDB.get_namespace_db_connectors()

        assert len(result) == 2
        assert mock_swsscommon.ConfigDBConnector.call_count == 2
        assert mock_conn.connect.call_count == 2

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_partial_connection_failure(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0', 'asic1']

        good_conn = MagicMock()
        bad_conn = MagicMock()
        bad_conn.connect.side_effect = RuntimeError("connection failed")

        mock_swsscommon.ConfigDBConnector.side_effect = [good_conn, bad_conn]

        with patch('swsscommon.swsscommon.SonicDBConfig.initializeGlobalConfig'):
            result = SonicDB.get_namespace_db_connectors()

        assert len(result) == 1
        assert result[0] is good_conn

    @patch('sonic_package_manager.service_creator.sonic_db.in_chroot', return_value=False)
    @patch('sonic_package_manager.service_creator.sonic_db.device_info')
    @patch('sonic_package_manager.service_creator.sonic_db.swsscommon')
    def test_caching_behavior(self, mock_swsscommon, mock_device_info, mock_in_chroot):
        mock_device_info.is_multi_npu.return_value = True
        mock_device_info.get_namespaces.return_value = ['asic0']

        mock_conn = MagicMock()
        mock_swsscommon.ConfigDBConnector.return_value = mock_conn

        with patch('swsscommon.swsscommon.SonicDBConfig.initializeGlobalConfig'):
            result1 = SonicDB.get_namespace_db_connectors()
            result2 = SonicDB.get_namespace_db_connectors()

        assert result1 is result2
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
