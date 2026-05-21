""" These tests check the memory_threshold_check_handler script monit description string handling while the rest of auto thechsupport is unit tested by coredump_gen_handler_test.py """

import sys
from unittest.mock import patch, ANY
from utilities_common.auto_techsupport_helper import EVENT_TYPE_MEMORY
from utilities_common.db import Db

sys.path.append("scripts")
import memory_threshold_check_handler


@patch("os.environ.get", lambda var: "status code 2 -- swss")
def test_memory_threshold_check_handler_host():
    with patch('memory_threshold_check_handler.invoke_ts_command_rate_limited') as invoke_ts:
        memory_threshold_check_handler.main()
        invoke_ts.assert_called_once_with(ANY, EVENT_TYPE_MEMORY, 'swss')

@patch("os.environ.get", lambda var: "status code 2 -- no output")
def test_memory_threshold_check_handler_host():
    with patch('memory_threshold_check_handler.invoke_ts_command_rate_limited') as invoke_ts:
        memory_threshold_check_handler.main()
        invoke_ts.assert_called_once_with(ANY, EVENT_TYPE_MEMORY, None)

@patch("os.environ.get", lambda var: "foo bar")
def test_memory_threshold_check_handler_host():
    with patch('memory_threshold_check_handler.invoke_ts_command_rate_limited') as invoke_ts:
        memory_threshold_check_handler.main()
        invoke_ts.assert_not_called()
