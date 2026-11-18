"""
These tests check the memory_threshold_check_handler script monit description
string handling while the rest of auto techsupport is unit tested by
coredump_gen_handler_test.py
"""

import sys
from unittest.mock import patch, MagicMock
from utilities_common.auto_techsupport_helper import EVENT_TYPE_MEMORY

sys.path.append("scripts")
import memory_threshold_check_handler


@patch("memory_threshold_check_handler.log_top_processes_and_containers")
@patch("memory_threshold_check_handler.SonicV2Connector")
@patch("memory_threshold_check_handler.syslog")
@patch("os.environ.get", lambda var: "status code 2 -- swss")
@patch("sys.argv", ["memory_threshold_check_handler.py", "2"])
def test_memory_threshold_check_handler_container(mock_syslog, mock_db_cls, mock_log_top):
    mock_db = MagicMock()
    mock_db.get.return_value = "10.0"
    mock_db_cls.return_value = mock_db
    with patch('memory_threshold_check_handler.invoke_ts_command_rate_limited') as invoke_ts:
        memory_threshold_check_handler.main()
        invoke_ts.assert_called_once_with(mock_db, EVENT_TYPE_MEMORY, 'swss')


@patch("memory_threshold_check_handler.log_top_processes_and_containers")
@patch("memory_threshold_check_handler.SonicV2Connector")
@patch("memory_threshold_check_handler.syslog")
@patch("os.environ.get", lambda var: "status code 2 -- no output")
@patch("sys.argv", ["memory_threshold_check_handler.py", "2"])
def test_memory_threshold_check_handler_host(mock_syslog, mock_db_cls, mock_log_top):
    mock_db = MagicMock()
    mock_db.get.return_value = "10.0"
    mock_db_cls.return_value = mock_db
    with patch('memory_threshold_check_handler.invoke_ts_command_rate_limited') as invoke_ts:
        memory_threshold_check_handler.main()
        invoke_ts.assert_called_once_with(mock_db, EVENT_TYPE_MEMORY, None)


@patch("memory_threshold_check_handler.log_top_processes_and_containers")
@patch("memory_threshold_check_handler.SonicV2Connector")
@patch("memory_threshold_check_handler.syslog")
@patch("os.environ.get", lambda var: "foo bar")
@patch("sys.argv", ["memory_threshold_check_handler.py", "2"])
def test_memory_threshold_check_handler_bad_output(mock_syslog, mock_db_cls, mock_log_top):
    mock_db = MagicMock()
    mock_db.get.return_value = "10.0"
    mock_db_cls.return_value = mock_db
    with patch('memory_threshold_check_handler.invoke_ts_command_rate_limited') as invoke_ts:
        memory_threshold_check_handler.main()
        invoke_ts.assert_not_called()
