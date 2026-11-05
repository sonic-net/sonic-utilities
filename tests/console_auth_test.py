"""Console display and session privilege tests without serial hardware."""

import importlib.util
from pathlib import Path
import signal
import sys
import types
from unittest.mock import MagicMock, call

import click
import pytest


@pytest.fixture
def lib(monkeypatch):
    common = types.ModuleType('sonic_py_common')
    common.device_info = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, 'sonic_py_common', common)
    monkeypatch.setitem(sys.modules, 'sonic_py_common.general', types.SimpleNamespace(
        getstatusoutput_noshell_pipe=MagicMock()))
    path = Path(__file__).parents[1] / 'consutil/lib.py'
    spec = importlib.util.spec_from_file_location('console_auth_lib', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('uid', [0, 1000, 65534])
def test_refresh_keeps_display_values_without_ordinary_writes(lib, monkeypatch, uid):
    monkeypatch.setattr(lib.os, 'geteuid', lambda: uid)
    db = MagicMock()
    db.db.STATE_DB = 'STATE_DB'
    db.db.get_all.return_value = {'oper_state': 'Connected', 'last_state_change': '123'}
    result = lib.DbUtils(db).update_state('1', 'busy', '1234', 'test-date')
    assert result == {'state': 'busy', 'pid': '1234', 'start_time': 'test-date',
                      'oper_state': 'Connected', 'last_state_change': '123'}
    if uid == 0:
        assert db.db.set.call_args_list == [call('STATE_DB', 'CONSOLE_PORT|1', field, value)
            for field, value in [('state', 'busy'), ('pid', '1234'), ('start_time', 'test-date')]]
    else:
        db.db.set.assert_not_called()


@pytest.mark.parametrize('active', [False, True])
def test_root_operation_derives_only_known_line_state(lib, monkeypatch, active):
    monkeypatch.setattr(lib.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(lib.SysInfoProvider, 'list_active_console_processes',
                        lambda: {'1': ('1234', 'test-date')} if active else {})
    db = MagicMock()
    db.cfgdb.get_keys.return_value = ['1', '2']
    db.db.STATE_DB = 'STATE_DB'
    result = lib.refresh_console_state(db, '1')
    assert result['state'] == ('busy' if active else 'idle')
    assert result['pid'] == ('1234' if active else '')
    assert {args.args[1] for args in db.db.set.call_args_list} == {'CONSOLE_PORT|1'}


@pytest.mark.parametrize('line', ['2', '', '-1', '1 extra', '1\n', 'Ethernet0', '../1'])
def test_unknown_or_non_numeric_line_never_writes(lib, monkeypatch, line):
    monkeypatch.setattr(lib.os, 'geteuid', lambda: 0)
    db = MagicMock()
    db.cfgdb.get_keys.return_value = ['1']
    with pytest.raises(click.BadParameter):
        lib.refresh_console_state(db, line)
    db.db.set.assert_not_called()


def test_root_operation_rejects_direct_ordinary_caller(lib, monkeypatch):
    monkeypatch.setattr(lib.os, 'geteuid', lambda: 65534)
    db = MagicMock()
    with pytest.raises(SystemExit) as failure:
        lib.refresh_console_state(db, '1')
    assert failure.value.code == lib.ERR_CMD
    db.db.set.assert_not_called()


def test_process_scan_filters_executable_names(lib, monkeypatch):
    command = MagicMock(return_value='')
    monkeypatch.setattr(lib.SysInfoProvider, 'run_command', command)
    assert lib.SysInfoProvider.list_active_console_processes() == {}
    assert command.call_args.args[0] == ['ps', '-C', 'picocom', '-C', 'minicom', '-o', 'pid,lstart,cmd']


@pytest.mark.parametrize('uid', [0, 65534])
def test_session_refresh_uses_fixed_command_no_pid_or_state(lib, monkeypatch, uid):
    monkeypatch.setattr(lib.os, 'geteuid', lambda: uid)
    run = MagicMock()
    monkeypatch.setattr(lib.subprocess, 'run', run)
    lib._refresh_session_state('1')
    expected = ['/usr/local/bin/consutil', 'refresh-state', '1']
    if uid:
        expected = ['/usr/bin/sudo', '-n'] + expected
    run.assert_called_once_with(expected, check=True, close_fds=True)


@pytest.fixture
def session(lib, monkeypatch):
    events = []
    child = MagicMock()
    child.wait.side_effect = lambda *args, **kwargs: events.append('wait/reap') or 0
    child.poll.return_value = 0
    handlers = {}
    def install(number, handler):
        previous = handlers.get(number, signal.SIG_DFL)
        handlers[number] = handler
        return previous
    def spawn(argv, **kwargs):
        events.append('successful exec')
        return child
    monkeypatch.setattr(lib.signal, 'signal', install)
    monkeypatch.setattr(lib.subprocess, 'Popen', spawn)
    monkeypatch.setattr(lib, '_refresh_session_state', lambda line: events.append('root refresh'))
    return child, events, handlers


def test_start_and_cleanup_follow_exec_and_reap(lib, session):
    child, events, handlers = session
    assert lib.run_console_session('1', 'picocom --quiet /dev/ttyUSB1-PTS') == 0
    assert events == ['successful exec', 'root refresh', 'wait/reap', 'root refresh']
    assert all(value == signal.SIG_DFL for value in handlers.values())
    child.terminate.assert_not_called()


def test_exec_failure_still_refreshes_idle_and_restores_handlers(lib, session, monkeypatch):
    _, events, handlers = session
    monkeypatch.setattr(lib.subprocess, 'Popen', MagicMock(side_effect=FileNotFoundError))
    with pytest.raises(FileNotFoundError):
        lib.run_console_session('1', '/missing/picocom /dev/ttyUSB1-PTS')
    assert events == ['root refresh']
    assert all(value == signal.SIG_DFL for value in handlers.values())


@pytest.mark.parametrize('number', [signal.SIGHUP, signal.SIGINT, signal.SIGTERM])
def test_signal_forwards_to_console_child(lib, session, number):
    child, _, handlers = session
    child.wait.side_effect = lambda: handlers[number](number, None) or 0
    assert lib.run_console_session('1', 'picocom /dev/ttyUSB1-PTS') == 0
    child.send_signal.assert_called_once_with(number)


def test_signal_during_spawn_is_forwarded_after_exec(lib, session, monkeypatch):
    child, events, handlers = session
    def spawn(*args, **kwargs):
        handlers[signal.SIGHUP](signal.SIGHUP, None)
        events.append('successful exec')
        return child
    monkeypatch.setattr(lib.subprocess, 'Popen', spawn)
    assert lib.run_console_session('1', 'picocom /dev/ttyUSB1-PTS') == 0
    child.send_signal.assert_called_once_with(signal.SIGHUP)


def test_failed_initial_refresh_terminates_console_before_final_refresh(lib, session, monkeypatch):
    child, _, _ = session
    child.poll.return_value = None
    refresh = MagicMock(side_effect=[RuntimeError('refresh failed'), None])
    monkeypatch.setattr(lib, '_refresh_session_state', refresh)
    with pytest.raises(RuntimeError, match='refresh failed'):
        lib.run_console_session('1', 'picocom /dev/ttyUSB1-PTS')
    child.terminate.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=5)
    assert refresh.call_count == 2


@pytest.mark.parametrize('status, expected', [(-15, 143), (-1, 129), (-2, 130), (0, 0), (4, 4)])
def test_session_preserves_shell_exit_status(lib, session, status, expected):
    child, _, _ = session
    child.wait.side_effect = None
    child.wait.return_value = status
    assert lib.run_console_session('1', 'picocom /dev/ttyUSB1-PTS') == expected
