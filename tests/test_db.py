"""Unit tests for utilities_common.db.Db class"""
from unittest import mock

from .mock_tables import dbconnector
from utilities_common.db import Db


class TestUtilitiesDb(object):
    @classmethod
    def setup_class(cls):
        dbconnector.load_database_config()

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
