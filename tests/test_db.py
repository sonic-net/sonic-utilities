"""Unit tests for utilities_common.db.Db class"""
from unittest import mock

from .mock_tables import dbconnector
from utilities_common.db import Db


class TestUtilitiesDb(object):

    @mock.patch('utilities_common.db.device_info')
    @mock.patch('utilities_common.db.multi_asic')
    @mock.patch('utilities_common.db.SonicV2Connector')
    @mock.patch('utilities_common.db.ConfigDBPipeConnector')
    @mock.patch('utilities_common.db.ConfigDBConnector')
    def test_default_transport_remains_tcp(self, mock_config_db, mock_config_db_pipe,
                                           mock_sonic_db, mock_multi_asic, mock_device_info):
        mock_multi_asic.is_multi_asic.return_value = False
        mock_device_info.is_supervisor.return_value = True
        mock_sonic_db.return_value.get_db_list.return_value = ['APPL_DB']

        Db()

        mock_config_db.assert_called_once_with(use_unix_socket_path=False)
        mock_config_db_pipe.assert_called_once_with(use_unix_socket_path=False)
        mock_sonic_db.assert_called_once_with(use_unix_socket_path=False)

    @mock.patch('utilities_common.db.device_info')
    @mock.patch('utilities_common.db.multi_asic')
    @mock.patch('utilities_common.db.SonicV2Connector')
    @mock.patch('utilities_common.db.ConfigDBPipeConnector')
    @mock.patch('utilities_common.db.ConfigDBConnector')
    def test_unix_transport_keeps_chassis_dbs_on_tcp(self, mock_config_db, mock_config_db_pipe,
                                                     mock_sonic_db, mock_multi_asic, mock_device_info):
        mock_multi_asic.is_multi_asic.return_value = False
        mock_device_info.is_supervisor.return_value = True

        local_db = mock.Mock()
        local_db.get_db_list.return_value = [
            'APPL_DB', 'STATE_DB', 'CHASSIS_APP_DB', 'CHASSIS_STATE_DB'
        ]
        chassis_db = mock.Mock()
        chassis_db.get_db_list.return_value = ['CHASSIS_APP_DB', 'CHASSIS_STATE_DB']
        mock_sonic_db.side_effect = [local_db, chassis_db]

        db = Db(use_unix_socket_path=True)

        mock_config_db.assert_called_once_with(use_unix_socket_path=True)
        mock_config_db_pipe.assert_called_once_with(use_unix_socket_path=True)
        assert mock_sonic_db.call_args_list == [
            mock.call(use_unix_socket_path=True),
            mock.call(use_unix_socket_path=False),
        ]
        assert local_db.connect.call_args_list == [
            mock.call('APPL_DB'),
            mock.call('STATE_DB'),
        ]
        assert chassis_db.connect.call_args_list == [
            mock.call('CHASSIS_APP_DB'),
            mock.call('CHASSIS_STATE_DB'),
        ]
        assert db.db is local_db
        assert db.chassis_db is chassis_db

    @mock.patch('utilities_common.db.multi_asic_ns_choices', return_value=['asic0'])
    @mock.patch('utilities_common.db.device_info')
    @mock.patch('utilities_common.db.SonicDBConfig')
    @mock.patch('utilities_common.db.multi_asic')
    @mock.patch('utilities_common.db.SonicV2Connector')
    @mock.patch('utilities_common.db.ConfigDBPipeConnector')
    @mock.patch('utilities_common.db.ConfigDBConnector')
    def test_unix_transport_uses_namespace_sockets(self, mock_config_db, mock_config_db_pipe,
                                                   mock_sonic_db, mock_multi_asic,
                                                   mock_sonic_db_config, mock_device_info,
                                                   mock_ns_choices):
        mock_multi_asic.is_multi_asic.return_value = True
        mock_sonic_db_config.isGlobalInit.return_value = True
        mock_device_info.is_supervisor.return_value = False

        default_config_db = mock.Mock()
        namespace_config_db = mock.Mock()
        mock_config_db.side_effect = [default_config_db, namespace_config_db]

        default_db = mock.Mock()
        default_db.get_db_list.return_value = [
            'APPL_DB', 'CHASSIS_APP_DB', 'CHASSIS_STATE_DB'
        ]
        namespace_db = mock.Mock()
        namespace_db.get_db_list.return_value = [
            'APPL_DB', 'CHASSIS_APP_DB', 'CHASSIS_STATE_DB'
        ]
        mock_sonic_db.side_effect = [default_db, namespace_db]

        db = Db(use_unix_socket_path=True)

        assert mock_config_db.call_args_list == [
            mock.call(use_unix_socket_path=True),
            mock.call(use_unix_socket_path=True, namespace='asic0'),
        ]
        assert mock_sonic_db.call_args_list == [
            mock.call(use_unix_socket_path=True),
            mock.call(use_unix_socket_path=True, namespace='asic0'),
        ]
        mock_config_db_pipe.assert_called_once_with(use_unix_socket_path=True)
        default_db.connect.assert_called_once_with('APPL_DB')
        namespace_db.connect.assert_called_once_with('APPL_DB')
        assert db.cfgdb_clients['asic0'] is namespace_config_db
        assert db.db_clients['asic0'] is namespace_db
        mock_ns_choices.assert_called_once_with()

    @mock.patch('utilities_common.db.multi_asic_ns_choices', return_value=[])
    @mock.patch('utilities_common.db.SonicDBConfig')
    @mock.patch('utilities_common.db.multi_asic')
    def test_utilities_db_init_multi_asic(self, mock_multi_asic, mock_sonic_db_config, mock_ns_choices):
        mock_multi_asic.is_multi_asic.return_value = True
        mock_sonic_db_config.isGlobalInit.return_value = False
        Db()
        mock_multi_asic.is_multi_asic.assert_called()
        mock_sonic_db_config.isGlobalInit.assert_called()
        mock_sonic_db_config.initializeGlobalConfig.assert_called_once()

    @mock.patch('utilities_common.db.SonicDBConfig')
    @mock.patch('utilities_common.db.multi_asic')
    def test_utilities_db_init_single_asic(self, mock_multi_asic, mock_sonic_db_config):
        mock_multi_asic.is_multi_asic.return_value = False
        Db()
        mock_multi_asic.is_multi_asic.assert_called()
        mock_sonic_db_config.isGlobalInit.assert_not_called()
        mock_sonic_db_config.initializeGlobalConfig.assert_not_called()
