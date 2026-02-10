import os
import sys
import subprocess
import jsonpatch
import pexpect
from unittest import mock
from mock import patch

import pytest

import config.main as config
import consutil.main as consutil
import tests.mock_tables.dbconnector

from click.testing import CliRunner
from utilities_common.db import Db
from consutil.lib import ConsolePortProvider, ConsolePortInfo, ConsoleSession, SysInfoProvider, DbUtils, \
    InvalidConfigurationError, LineBusyError, LineNotFoundError, ConnectionFailedError
from sonic_py_common import device_info
from jsonpatch import JsonPatchConflict

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONSOLE_MOCK_DIR = SCRIPT_DIR + "/console_mock"


class TestConfigConsoleCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
    
    def test_enable_console_switch(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["console"].commands["enable"])
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_enable_console_switch_yang_validation(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["console"].commands["enable"])
        print(result.exit_code)
        assert "Invalid ConfigDB. Error" in result.output

    def test_disable_console_switch(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["console"].commands["disable"])
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_disable_console_switch_yang_validation(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["console"].commands["disable"])
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_console_add_exists(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"baud_rate": "9600"})

        # add a console setting which the port exists
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1", '--baud', "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to add console port setting, which is already exists." in result.output
    
    def test_console_add_no_baud(self):
        runner = CliRunner()
        db = Db()

        # add a console setting without baud
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Missing option '--baud'" in result.output

    def test_console_add_name_conflict(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch1"})

        # add a console setting which the device name has been used by other port
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1", '--baud', "9600", "--devicename", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Please enter a valid device name or remove the existing one" in result.output

    def test_console_add_success(self):
        runner = CliRunner()
        db = Db()

        # add a console setting without flow control option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["0", '--baud', "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # add a console setting with flow control option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1", '--baud', "9600", "--flowcontrol"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # add a console setting with device name option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["2", '--baud', "9600", "--devicename", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_console_add_yang_validation(self):
        runner = CliRunner()
        db = Db()

        # add a console setting without flow control option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["0", '--baud', "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_console_del_non_exists(self):
        runner = CliRunner()
        db = Db()

        # remote a console port setting which is not exists
        result = runner.invoke(config.config.commands["console"].commands["del"], ["0"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to delete console port setting, which is not present." in result.output

    def test_console_del_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # add a console setting which the port exists
        result = runner.invoke(config.config.commands["console"].commands["del"], ["1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_console_del_yang_validation(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # add a console setting which the port exists
        result = runner.invoke(config.config.commands["console"].commands["del"], ["1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_update_console_remote_device_name_non_exists(self):
        runner = CliRunner()
        db = Db()

        # trying to update a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to update console port setting, which is not present." in result.output

    def test_update_console_remote_device_name_conflict(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"baud": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"baud": "9600", "remote_device": "switch1"})

        # trying to update a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Please enter a valid device name or remove the existing one" in result.output
    
    def test_update_console_remote_device_name_existing_and_same(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch1"})

        # trying to update a console line remote device configuration which is existing and same with user provided value
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["2", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_remote_device_name_reset(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch1"})

        # trying to reset a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["2"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_update_console_remote_device_name_reset_yang_validation(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch1"})

        # trying to reset a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["2"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_update_console_remote_device_name_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # trying to set a console line remote device configuration
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_update_console_remote_device_name_yang_validation(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # trying to set a console line remote device configuration
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_console_escape_set_lowercase(self):
        runner = CliRunner()
        db = Db()

        # set console escape character to 'd'
        result = runner.invoke(config.config.commands["console"].commands["escape"], ["d"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # verify the escape_char is stored in the config
        console_mgmt = db.cfgdb.get_entry("CONSOLE_SWITCH", "console_mgmt")
        assert console_mgmt.get("escape_char") == "d"

    def test_console_escape_set_uppercase(self):
        runner = CliRunner()
        db = Db()

        # set console escape character to 'D' (uppercase) - should be converted to lowercase
        result = runner.invoke(config.config.commands["console"].commands["escape"], ["D"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # verify the escape_char is stored as lowercase in the config
        console_mgmt = db.cfgdb.get_entry("CONSOLE_SWITCH", "console_mgmt")
        assert console_mgmt.get("escape_char") == "d"

    def test_console_escape_clear(self):
        runner = CliRunner()
        db = Db()

        # first set an escape character
        db.cfgdb.set_entry("CONSOLE_SWITCH", "console_mgmt", {"enabled": "yes", "escape_char": "d"})

        # clear the escape character
        result = runner.invoke(config.config.commands["console"].commands["escape"], ["clear"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # verify the escape_char is removed but enabled is preserved
        console_mgmt = db.cfgdb.get_entry("CONSOLE_SWITCH", "console_mgmt")
        assert "escape_char" not in console_mgmt
        assert console_mgmt.get("enabled") == "yes"

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry",
           mock.Mock(side_effect=ValueError))
    def test_console_escape_set_yang_validation(self):
        runner = CliRunner()
        db = Db()

        # set console escape character with yang validation error
        result = runner.invoke(config.config.commands["console"].commands["escape"], ["d"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_update_console_baud_no_change(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # trying to set a console line baud which is same with existing one
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
    
    def test_update_console_baud_non_exists(self):
        runner = CliRunner()
        db = Db()

        # trying to set a console line baud which is not exists
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to update console port setting, which is not present." in result.output
    
    def test_update_console_baud_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # trying to set a console line baud
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "115200"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_update_console_baud_yang_validation(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        # trying to set a console line baud
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "115200"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_update_console_flow_control_no_change(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600", "flow_control": "0"})

        # trying to set a console line flow control option which is same with existing one
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["disable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_flow_control_non_exists(self):
        runner = CliRunner()
        db = Db()

        # trying to set a console line flow control option which is not exists
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["enable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to update console port setting, which is not present." in result.output

    def test_update_console_flow_control_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600", "flow_control": "0"})

        # trying to set a console line flow control option
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["enable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_update_console_flow_control_yang_validation(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600", "flow_control": "0"})

        # trying to set a console line flow control option
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["enable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert "Invalid ConfigDB. Error" in result.output

class TestConsutilLib(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_console_port_provider_get_all_configured_only_empty(self):
        db = Db()
        provider = ConsolePortProvider(db, configured_only=True)
        assert len(list(provider.get_all())) == 0

    def test_console_port_provider_get_all_configured_only_nonempty(self):
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        provider = ConsolePortProvider(db, configured_only=True)
        assert len(list(provider.get_all())) == 1

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB0", "/dev/ttyUSB1"]))
    def test_console_port_provider_get_all_with_ttys(self):
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        provider = ConsolePortProvider(db, configured_only=False)
        ports = list(provider.get_all())
        print('[{}]'.format(', '.join(map(str, ports))))
        assert len(ports) == 2

    def test_console_port_provider_get_line_success(self):
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", {"baud_rate": "9600"})

        provider = ConsolePortProvider(db, configured_only=True)
        port = provider.get("1")
        assert port is not None
        assert port.line_num == "1"

    def test_console_port_provider_get_line_not_found(self):
        with pytest.raises(LineNotFoundError):
            db = Db()
            provider = ConsolePortProvider(db, configured_only=True)
            provider.get("1")

    def test_console_port_provider_get_line_by_device_success(self):
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch2"})

        provider = ConsolePortProvider(db, configured_only=True)
        port = provider.get("switch2", use_device=True)
        assert port is not None
        assert port.line_num == "2"

    def test_console_port_provider_get_line_by_device_not_found(self):
        with pytest.raises(LineNotFoundError):
            db = Db()
            db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch2"})

            provider = ConsolePortProvider(db, configured_only=True)
            provider.get("switch1")

    @mock.patch('consutil.lib.SysInfoProvider.list_active_console_processes',
                mock.MagicMock(return_value={"1": ("223", "2020/11/2")}))
    def test_console_port_info_refresh_without_session(self):
        db = Db()

        port = ConsolePortInfo(DbUtils(db), {"LINE": "1"})
        port.refresh()
        assert port.busy
        assert port.session_pid == "223"
        assert port.session_start_date == "2020/11/2"

    @mock.patch('consutil.lib.SysInfoProvider.list_active_console_processes',
                mock.MagicMock(return_value={"2": ("223", "2020/11/2")}))
    def test_console_port_info_refresh_without_session_idle(self):
        db = Db()

        port = ConsolePortInfo(DbUtils(db), {"LINE": "1"})
        port.refresh()
        assert port.busy == False

    @mock.patch('consutil.lib.SysInfoProvider.get_active_console_process_info', mock.MagicMock(return_value=("1", "223", "2020/11/2")))
    def test_console_port_info_refresh_with_session(self):
        db = Db()

        port = ConsolePortInfo(DbUtils(db), {"LINE": "1"})
        port._session = ConsoleSession(port, mock.MagicMock(pid="223"))
        print(port)

        port.refresh()
        assert port.busy == True
        assert port.session_pid == "223"
        assert port.session_start_date == "2020/11/2"

    @mock.patch('consutil.lib.SysInfoProvider.get_active_console_process_info', mock.MagicMock(return_value=("2", "223", "2020/11/2")))
    def test_console_port_info_refresh_with_session_line_mismatch(self):
        db = Db()

        port = ConsolePortInfo(DbUtils(db), {"LINE": "1"})
        port._session = ConsoleSession(port, mock.MagicMock(pid="223"))
        print(port)

        with pytest.raises(ConnectionFailedError):
            port.refresh()

        assert port.busy == False

    @mock.patch('consutil.lib.SysInfoProvider.get_active_console_process_info', mock.MagicMock(return_value=None))
    def test_console_port_info_refresh_with_session_process_ended(self):
        db = Db()

        port = ConsolePortInfo(DbUtils(db), {"LINE": "1"})
        port._session = ConsoleSession(port, mock.MagicMock(pid="223"))
        print(port)

        port.refresh()
        assert port.busy == False

    def test_console_port_info_connect_state_busy(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "CUR_STATE": {"state": "busy"}})

        port.refresh = mock.MagicMock(return_value=None)
        with pytest.raises(LineBusyError):
            port.connect()

    def test_console_port_info_connect_invalid_config(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "CUR_STATE": {"state": "idle"}})

        port.refresh = mock.MagicMock(return_value=None)
        with pytest.raises(InvalidConfigurationError):
            port.connect()

    def test_console_port_info_connect_device_busy(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "baud_rate": "9600", "CUR_STATE": {"state": "idle"}})

        port.refresh = mock.MagicMock(return_value=None)
        mock_proc = mock.MagicMock(spec=subprocess.Popen)
        mock_proc.send = mock.MagicMock(return_value=None)
        mock_proc.expect = mock.MagicMock(return_value=1)
        with mock.patch('pexpect.spawn', mock.MagicMock(return_value=mock_proc)):
            with pytest.raises(LineBusyError):
                port.connect()

    def test_console_port_info_connect_connection_fail(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "baud_rate": "9600", "CUR_STATE": {"state": "idle"}})

        port.refresh = mock.MagicMock(return_value=None)
        mock_proc = mock.MagicMock(spec=subprocess.Popen)
        mock_proc.send = mock.MagicMock(return_value=None)
        mock_proc.expect = mock.MagicMock(return_value=2)
        with mock.patch('pexpect.spawn', mock.MagicMock(return_value=mock_proc)):
            with pytest.raises(ConnectionFailedError):
                port.connect()

    def test_console_port_info_connect_success(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "baud_rate": "9600", "CUR_STATE": {"state": "idle"}})

        port.refresh = mock.MagicMock(return_value=None)
        mock_proc = mock.MagicMock(spec=subprocess.Popen, pid="223")
        mock_proc.send = mock.MagicMock(return_value=None)
        mock_proc.expect = mock.MagicMock(return_value=0)
        with mock.patch('pexpect.spawn', mock.MagicMock(return_value=mock_proc)):
            session = port.connect()
            assert session.proc.pid == "223"
            assert session.port.line_num == "1"

    def test_console_port_info_clear_session_line_not_busy(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "baud_rate": "9600", "CUR_STATE": {"state": "idle"}})

        port.refresh = mock.MagicMock(return_value=None)
        assert not port.clear_session()

    @mock.patch('consutil.lib.SysInfoProvider.run_command', mock.MagicMock(return_value=None))
    def test_console_port_info_clear_session_with_state_db(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "baud_rate": "9600",
                                             "CUR_STATE": {"state": "busy", "pid": "223"}})

        port.refresh = mock.MagicMock(return_value=None)
        assert port.clear_session()

    def test_console_port_info_clear_session_with_existing_session(self):
        db = Db()
        port = ConsolePortInfo(DbUtils(db), {"LINE": "1", "baud_rate": "9600", "CUR_STATE": {"state": "busy"}})
        port._session = ConsoleSession(port, None)
        port._session.close = mock.MagicMock(return_value=None)
        port.refresh = mock.MagicMock(return_value=None)
        assert port.clear_session()

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    @mock.patch('os.path.exists', mock.MagicMock(return_value=False))
    def test_sys_info_provider_init_device_prefix_plugin_nonexists(self):
        SysInfoProvider.init_device_prefix()
        assert SysInfoProvider.DEVICE_PREFIX == "/dev/ttyUSB"

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    @mock.patch('os.path.exists', mock.MagicMock(return_value=True))
    def test_sys_info_provider_init_device_prefix_plugin(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="C0-")):
            SysInfoProvider.init_device_prefix()
            assert SysInfoProvider.DEVICE_PREFIX == "/dev/C0-"

    def test_sys_info_provider_list_console_ttys(self):
        SysInfoProvider.DEVICE_PREFIX = CONSOLE_MOCK_DIR + "/dev/ttyUSB"
        ttys = SysInfoProvider.list_console_ttys()
        print(SysInfoProvider.DEVICE_PREFIX)
        assert len(ttys) == 1

    def test_sys_info_provider_list_console_ttys_device_not_exists(self):
        SysInfoProvider.DEVICE_PREFIX = CONSOLE_MOCK_DIR + "/dev_not_exist/ttyUSB"
        ttys = SysInfoProvider.list_console_ttys()
        assert len(ttys) == 0

    all_active_processes_output = ''+ \
        """    PID                  STARTED CMD
      8 Mon Nov  2 04:29:41 2020 picocom /dev/ttyUSB0 
        """
    @mock.patch('consutil.lib.SysInfoProvider.run_command', mock.MagicMock(return_value=all_active_processes_output))
    def test_sys_info_provider_list_active_console_processes(self):
        SysInfoProvider.DEVICE_PREFIX = "/dev/ttyUSB"
        procs = SysInfoProvider.list_active_console_processes()
        assert len(procs) == 1
        assert "0" in procs
        assert procs["0"] == ("8", "Mon Nov  2 04:29:41 2020")

    active_process_output = "13751 Wed Mar  6 08:31:35 2019 /usr/bin/sudo picocom -b 9600 -f n /dev/ttyUSB1"
    @mock.patch('consutil.lib.SysInfoProvider.run_command', mock.MagicMock(return_value=active_process_output))
    def test_sys_info_provider_get_active_console_process_info_exists(self):
        SysInfoProvider.DEVICE_PREFIX = "/dev/ttyUSB"
        proc = SysInfoProvider.get_active_console_process_info("13751")
        assert proc is not None
        assert proc == ("1", "13751",  "Wed Mar  6 08:31:35 2019")

    active_process_empty_output = ""
    @mock.patch('consutil.lib.SysInfoProvider.run_command', mock.MagicMock(return_value=active_process_empty_output))
    def test_sys_info_provider_get_active_console_process_info_nonexists(self):
        SysInfoProvider.DEVICE_PREFIX = "/dev/ttyUSB"
        proc = SysInfoProvider.get_active_console_process_info("2")
        assert proc is None

class TestConsutil(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.main.show', mock.MagicMock(return_value=None))
    def test_consutil_feature_disabled_null_config(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(consutil.consutil, ['show'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 1
        assert result.output == "Console switch feature is disabled\n"

    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.main.show', mock.MagicMock(return_value=None))
    def test_consutil_feature_disabled_config(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_SWITCH", "console_mgmt", {"enabled": "no"})

        result = runner.invoke(consutil.consutil, ['show'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 1
        assert result.output == "Console switch feature is disabled\n"

    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.main.show', mock.MagicMock(return_value=None))
    def test_consutil_feature_enabled(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_SWITCH", "console_mgmt", {"enabled": "yes"})

        result = runner.invoke(consutil.consutil, ['show'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

class TestConsutilShow(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    expect_show_output = ''+ \
        """  Line    Baud    Flow Control    PID                Start Time    Device
------  ------  --------------  -----  ------------------------  --------
     1    9600        Disabled      -                         -   switch1
    *2    9600        Disabled    223  Wed Mar  6 08:31:35 2019   switch2
     3    9600         Enabled      -                         -
"""
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.SysInfoProvider.list_active_console_processes',
                mock.MagicMock(return_value={"2": ("223", "Wed Mar  6 08:31:35 2019")}))
    def test_show(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch2", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 3, {"baud_rate": "9600", "flow_control": "1"})

        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|2", "state", "busy")
        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|2", "pid", "223")
        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|2", "start_time", "Wed Mar  6 08:31:35 2019")

        # use '--brief' option to avoid access system
        result = runner.invoke(consutil.consutil.commands["show"], ['--brief'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == TestConsutilShow.expect_show_output

    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.SysInfoProvider.list_active_console_processes',
                mock.MagicMock(return_value={"2": ("223", "Wed Mar  6 08:31:35 2019")}))
    def test_show_stale_idle_to_busy(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch2", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 3, {"baud_rate": "9600", "flow_control": "1"})

        # use '--brief' option to avoid access system
        result = runner.invoke(consutil.consutil.commands["show"], ['--brief'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == TestConsutilShow.expect_show_output

    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.SysInfoProvider.list_active_console_processes',
                mock.MagicMock(return_value={"2": ("223", "Wed Mar  6 08:31:35 2019")}))
    def test_show_stale_busy_to_idle(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 2, {"remote_device": "switch2", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_PORT", 3, {"baud_rate": "9600", "flow_control": "1"})

        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|1", "state", "busy")
        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|1", "pid", "222")
        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|1", "start_time", "Wed Mar  6 08:31:35 2019")

        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|2", "state", "busy")
        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|2", "pid", "223")
        db.db.set(db.db.STATE_DB, "CONSOLE_PORT|2", "start_time", "Wed Mar  6 08:31:35 2019")

        # use '--brief' option to avoid access system
        result = runner.invoke(consutil.consutil.commands["show"], ['--brief'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == TestConsutilShow.expect_show_output

class TestConsutilConnect(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    def test_connect_target_nonexists(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})

        result = runner.invoke(consutil.consutil.commands["connect"], ['2'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 3
        assert result.output == "Cannot connect: target [2] does not exist\n"

        result = runner.invoke(consutil.consutil.commands["connect"], ['--devicename', 'switch2'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 3
        assert result.output == "Cannot connect: target [switch2] does not exist\n"

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.ConsolePortInfo.connect', mock.MagicMock(side_effect=LineBusyError()))
    def test_connect_line_busy(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})

        result = runner.invoke(consutil.consutil.commands["connect"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 5
        assert result.output == "Cannot connect: line [1] is busy\n"

        result = runner.invoke(consutil.consutil.commands["connect"], ['--devicename', 'switch1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 5
        assert result.output == "Cannot connect: line [1] is busy\n"

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    def test_connect_no_baud(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(consutil.consutil.commands["connect"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 4
        assert result.output == "Cannot connect: line [1] has no baud rate\n"

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.ConsolePortInfo.connect', mock.MagicMock(side_effect=ConnectionFailedError()))
    def test_connect_picocom_err(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(consutil.consutil.commands["connect"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 3
        assert result.output == "Cannot connect: unable to open picocom process\n"

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.ConsolePortInfo.connect', mock.MagicMock(return_value=mock.MagicMock(interact=mock.MagicMock(return_value=None))))
    def test_connect_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})

        result = runner.invoke(consutil.consutil.commands["connect"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == "Successful connection to line [1]\nPress ^A ^X to disconnect\n"

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.ConsolePortInfo.connect',
                mock.MagicMock(return_value=mock.MagicMock(interact=mock.MagicMock(return_value=None))))
    def test_connect_with_custom_escape_char(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})
        db.cfgdb.set_entry("CONSOLE_SWITCH", "console_mgmt", {"enabled": "yes", "escape_char": "d"})

        result = runner.invoke(consutil.consutil.commands["connect"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == "Successful connection to line [1]\nPress ^D ^X to disconnect\n"

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('consutil.lib.ConsolePortInfo.connect',
                mock.MagicMock(return_value=mock.MagicMock(interact=mock.MagicMock(return_value=None))))
    def test_connect_default_escape_after_clear(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})
        # Set CONSOLE_SWITCH with escape_char, and clear it later
        db.cfgdb.set_entry("CONSOLE_SWITCH", "console_mgmt", {"enabled": "yes", "escape_char": "d"})

        runner.invoke(config.config.commands["console"].commands["escape"], ["clear"], obj=db)

        result = runner.invoke(consutil.consutil.commands["connect"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == "Successful connection to line [1]\nPress ^A ^X to disconnect\n"

class TestConsutilClear(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('os.geteuid', mock.MagicMock(return_value=1))
    def test_clear_without_root(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(consutil.consutil.commands["clear"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 2
        assert "Root privileges are required for this operation" in result.output

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    def test_clear_line_not_found(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(consutil.consutil.commands["clear"], ['2'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 3
        assert "Target [2] does not exist" in result.output

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('consutil.lib.ConsolePortInfo.clear_session', mock.MagicMock(return_value=False))
    def test_clear_idle(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})

        result = runner.invoke(consutil.consutil.commands["clear"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert "No process is connected to line 1" in result.output

    @mock.patch('consutil.lib.SysInfoProvider.list_console_ttys', mock.MagicMock(return_value=["/dev/ttyUSB1"]))
    @mock.patch('consutil.lib.SysInfoProvider.init_device_prefix', mock.MagicMock(return_value=None))
    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('consutil.lib.ConsolePortInfo.clear_session', mock.MagicMock(return_value=True))
    def test_clear_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, {"remote_device": "switch1", "baud_rate": "9600"})

        result = runner.invoke(consutil.consutil.commands["clear"], ['1'], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert "Cleared line" in result.output
