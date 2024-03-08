import os
import sys
import pytest
import mock
import jsonpatch
from importlib import reload
from click.testing import CliRunner
from unittest import TestCase
from swsscommon.swsscommon import ConfigDBConnector
from mock import patch
from jsonpatch import JsonPatchConflict

from .mock_tables import dbconnector

import show.main as show
import config.main as config
from utilities_common.db import Db

from .buffer_input.buffer_test_vectors import *
from config.validated_config_db_connector import ValidatedConfigDBConnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

class TestBuffer(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_config_buffer_profile_headroom_yang(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_config_buffer_profile_headroom(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '18432', 'xoff': '32768', 'size': '18432'}

    def test_config_buffer_profile_dynamic_th(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--dynamic_th", "3"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'headroom_type': 'dynamic'}

    def test_config_buffer_profile_add_existing(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["headroom_profile", "--dynamic_th", "3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Profile headroom_profile already exist" in result.output

    def test_config_buffer_profile_set_non_existing(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["non_existing_profile", "--dynamic_th", "3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Profile non_existing_profile doesn't exist" in result.output

    def test_config_buffer_profile_add_headroom_to_dynamic_profile(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["alpha_profile", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Can't change profile alpha_profile from dynamically calculating headroom to non-dynamically one" in result.output

    def test_config_buffer_profile_add_no_xon(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test_profile_no_xon", "--xoff", "32768"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Xon is mandatory for non-dynamic profile" in result.output

    def test_config_buffer_profile_add_no_param(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"], ["no_parameter"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Either size information (xon, xoff, size) or dynamic_th needs to be provided" in result.output

    def test_config_buffer_profile_multiple_or_none_default_buffer_param_in_database(self):
        runner = CliRunner()
        db = Db()
        default_lossless_buffer_parameter = db.cfgdb.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE')

        # Remove all entries from DEFAULT_LOSSLESS_BUFFER_PARAMETER
        db.cfgdb.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', None)
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Dynamic buffer calculation is enabled while no entry found in DEFAULT_LOSSLESS_BUFFER_PARAMETER table" in result.output

        # Insert AZURE and another entry into DEFAULT_LOSSLESS_BUFFER_PARAMETER
        db.cfgdb.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', default_lossless_buffer_parameter)
        db.cfgdb.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'TEST', default_lossless_buffer_parameter)
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Multiple entries are found in DEFAULT_LOSSLESS_BUFFER_PARAMETER while no dynamic_th specified" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_config_shp_size_negative_yang(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["size"],
                               ["200000"])
        print(result.exit_code)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_config_shp_size_negative(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["size"],
                               ["20000000"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Shared headroom pool must be less than mmu size" in result.output

    def test_config_shp_ratio(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["over-subscribe-ratio"],
                               ["4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert db.cfgdb.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE') == {'default_dynamic_th': '0', 'over_subscribe_ratio': '4'}

    def test_config_shp_ratio_negative(self):
        runner = CliRunner()
        db = Db()
        port_number = len(db.cfgdb.get_table('PORT').keys())
        bad_oversubscribe_ratio = str(port_number + 1)
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["over-subscribe-ratio"],
                               [bad_oversubscribe_ratio], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid over-subscribe-ratio value {}. It should be in range [0, {}]".format(bad_oversubscribe_ratio, port_number) in result.output

    def test_config_buffer_profile_headroom_toggle_shp(self):
        runner = CliRunner()
        db = Db()

        # Disable SHP by setting over-subscribe-ratio to 0
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["over-subscribe-ratio"],
                               ["0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE') == {'default_dynamic_th': '0', 'over_subscribe_ratio': '0'}

        # Size should equal xon + xoff
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test1", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test1')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '18432', 'xoff': '32768', 'size': '51200'}

        # Xoff should equal size - xon
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test2", "--dynamic_th", "3", "--xon", "18432", "--size", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '18432', 'xoff': '14336', 'size': '32768'}

        # Neither xon nor size is provided
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test_profile_neither_xoff_nor_size", "--xon", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Neither xoff nor size is provided" in result.output

        # Negative xoff
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test_profile_negative_xoff", "--xon", "32768", "--size", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "The xoff must be greater than 0 while we got -14336 (calculated by: size 18432 - xon 32768)" in result.output

        # Set size
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["test2", "--dynamic_th", "3", "--size", "65536"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '18432', 'xoff': '14336', 'size': '65536'}

        # Set xon
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["test2", "--xon", "19456"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '19456', 'xoff': '14336', 'size': '65536'}

        # Set xoff
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["test2", "--xoff", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '19456', 'xoff': '18432', 'size': '65536'}

        # Enable SHP by setting size
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["size"],
                               ["200000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert db.cfgdb.get_entry('BUFFER_POOL', 'ingress_lossless_pool') == {'mode': 'dynamic', 'type': 'ingress', 'xoff': '200000'}

        # Size should equal xon
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile3", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile3')
        assert profile == {'dynamic_th': '3', 'pool': 'ingress_lossless_pool', 'xon': '18432', 'xoff': '32768', 'size': '18432'}

        # Negative test: xoff not provided
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile4", "--dynamic_th", "3", "--xon", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Shared headroom pool is enabled, xoff is mandatory for non-dynamic profile" in result.output

    def test_show_buffer_configuration(self):
        self.executor(testData['show_buffer_configuration'])

    def test_show_buffer_information(self):
        self.executor(testData['show_buffer_information'])

    def executor(self, testcase):
        runner = CliRunner()

        for input in testcase:
            exec_cmd = show.cli.commands[input['cmd'][0]].commands[input['cmd'][1]]

            result = runner.invoke(exec_cmd, [], catch_exceptions=True)

            print(result.exit_code)
            print(result.output)
            if result.exception:
                print(result.exception)

            assert result.exit_code == 0
            assert result.output == input['rc_output']

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")


class TestInterfaceBuffer(object):
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        import config.main as config
        reload(config)
        yield
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        from .mock_tables import dbconnector
        dbconnector.dedicated_dbs = {}
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_config_int_buffer_pg_lossless_add_yang(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "5"], obj=db)
        assert "Invalid ConfigDB. Error" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_config_int_buffer_pg_lossless_remove(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # Remove non-exist entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["remove"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert "Invalidi ConfigDB. Error" in result.output
    
    def test_config_int_buffer_pg_lossless_add(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert {'profile': 'NULL'} == db.cfgdb.get_entry('BUFFER_PG', 'Ethernet0|5')
            assert {'pfc_enable': '3,4,5', 'scheduler': 'port_scheduler'} == db.cfgdb.get_entry('PORT_QOS_MAP', 'Ethernet0')

        # Try to add an existing entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group 5 overlaps with existing priority group 5" in result.output

        # Try to add an overlap entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "2-3"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group 2-3 overlaps with existing priority group 3-4" in result.output

        # Try to add an overlap entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "4-5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group 4-5 overlaps with existing priority group 3-4" in result.output

        # Try to add a lossy profile
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "6", "ingress_lossy_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Profile ingress_lossy_profile doesn't exist or isn't a lossless profile" in result.output

        # Try to add a large pg
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "8", "ingress_lossy_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group 8 is not valid" in result.output

        # Try to use a pg map in wrong format
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "3-", "testprofile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group 3- is not valid" in result.output

        # Try to use a pg which is not a number
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "a"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group a is not valid" in result.output

        # Try to use a non-exist profile
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["add"],
                                   ["Ethernet0", "7", "testprofile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Profile testprofile doesn't exist" in result.output

        # Try to remove all lossless profiles
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            keys = db.cfgdb.get_keys('BUFFER_PG')
            assert set(keys) == {('Ethernet0', '0'), ('Ethernet0', '3-4'), ('Ethernet0', '5')}
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["remove"],
                                   ["Ethernet0"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            keys = db.cfgdb.get_keys('BUFFER_PG')
            assert keys == [('Ethernet0', '0')]
            assert {'pfc_enable': '', 'scheduler': 'port_scheduler'} == db.cfgdb.get_entry('PORT_QOS_MAP', 'Ethernet0')

    def test_config_int_buffer_pg_lossless_set(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # Set a non-exist entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["set"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer priority group 5 doesn't exist" in result.output

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["set"],
                                   ["Ethernet0", "3-4", "headroom_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert {'profile': 'headroom_profile'} == db.cfgdb.get_entry('BUFFER_PG', 'Ethernet0|3-4')
            assert {'pfc_enable': '3,4', 'scheduler': 'port_scheduler'} == db.cfgdb.get_entry('PORT_QOS_MAP', 'Ethernet0')

    def test_config_int_buffer_pg_lossless_remove(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # Remove non-exist entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["remove"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "No specified lossless priority group 5 found on port Ethernet0" in result.output

        # Remove lossy PG
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["remove"],
                                   ["Ethernet0", "0"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Lossy PG 0 can't be removed" in result.output

        # Remove existing lossless PG
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            # Remove one lossless PG
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["priority-group"].
                                   commands["lossless"].commands["remove"],
                                   ["Ethernet0", "3-4"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert [('Ethernet0', '0')] == db.cfgdb.get_keys('BUFFER_PG')
            assert {'pfc_enable': '', 'scheduler': 'port_scheduler'} == db.cfgdb.get_entry('PORT_QOS_MAP', 'Ethernet0')

        # Remove all lossless PGs is tested in the 'add' test case to avoid repeating adding PGs

    def test_config_int_buffer_queue_add(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # Not providing a profile
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["add"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Missing argument" in result.output

        # Add existing
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["add"],
                                   ["Ethernet0", "3-4", "egress_lossy_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer queue 3-4 overlaps with existing queue 3-4" in result.output

        # Normal add
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["add"],
                                   ["Ethernet0", "5", "egress_lossy_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            queue = db.cfgdb.get_entry('BUFFER_QUEUE', 'Ethernet0|5')
            assert queue == {'profile': 'egress_lossy_profile'}

        # Large queue ID
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["add"],
                                   ["Ethernet0", "20", "egress_lossy_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Buffer queue 20 is not valid" in result.output

        # Remove all
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            keys = db.cfgdb.get_keys('BUFFER_QUEUE')
            assert set(keys) == {('Ethernet0', '3-4'), ('Ethernet0', '5')}
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["remove"],
                                   ["Ethernet0"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert [] == db.cfgdb.get_keys('BUFFER_QUEUE')

    def test_config_int_buffer_queue_set(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # Remove non-exist entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["set"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Missing argument" in result.output

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["set"],
                                   ["Ethernet0", "3-4", "headroom_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "Type of pool ingress_lossless_pool referenced by profile headroom_profile is wrong" in result.output

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["set"],
                                   ["Ethernet0", "3-4", "egress_lossy_profile"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            queue = db.cfgdb.get_entry('BUFFER_QUEUE', 'Ethernet0|3-4')
            assert queue == {'profile': 'egress_lossy_profile'}

    def test_config_int_buffer_queue_remove(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # Remove non-exist entry
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["remove"],
                                   ["Ethernet0", "5"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code
            assert "No specified queue 5 found on port Ethernet0" in result.output

        # Remove existing queue
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["buffer"].commands["queue"].commands["remove"],
                                   ["Ethernet0", "3-4"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert [] == db.cfgdb.get_keys('BUFFER_QUEUE')

        # Removing all queues is tested in "add" test case to avoid repeating adding queues.
