"""Exercise actual mux Click commands without platform hardware."""

import ast
import configparser
import importlib.util
import os
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import click
from click.testing import CliRunner
import pytest


@pytest.fixture
def mux(monkeypatch):
    root = Path(__file__).parents[1]
    # Reuse the production abbreviation classes without unrelated DB imports.
    parsed = ast.parse((root / 'utilities_common/cli.py').read_text())
    groups = ast.Module(body=[node for node in parsed.body if isinstance(node, ast.ClassDef)
                              and node.name in ('Config', 'AliasedGroup', 'AbbreviationGroup')], type_ignores=[])
    cli = types.ModuleType('utilities_common.cli')
    cli.__dict__.update(click=click, configparser=configparser, os=os,
                        __file__=str(root / 'utilities_common/cli.py'), _config=None)
    exec(compile(groups, str(root / 'utilities_common/cli.py'), 'exec'), cli.__dict__)
    cli.pass_db = click.pass_obj
    common = types.ModuleType('utilities_common')
    common.__path__ = []
    common.platform_sfputil_helper = MagicMock()
    for name, value in {
        'utilities_common': common,
        'utilities_common.cli': cli,
        'utilities_common.general': types.SimpleNamespace(get_optional_value_for_key_in_config_tbl=MagicMock()),
        'sonic_py_common': types.SimpleNamespace(multi_asic=MagicMock()),
        'swsscommon': types.SimpleNamespace(swsscommon=MagicMock()),
        'swsscommon.swsscommon': types.SimpleNamespace(SonicV2Connector=MagicMock(), ConfigDBConnector=MagicMock()),
    }.items():
        monkeypatch.setitem(sys.modules, name, value)
    spec = importlib.util.spec_from_file_location('mux_display_auth', root / 'show/muxcable.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.os, 'geteuid', lambda: 65534)
    monkeypatch.setattr(module.os, 'execv', MagicMock())
    return module


QUERIES = [
    (['status'], ['status']),
    (['status', 'Ethernet0'], ['status', '--', 'Ethernet0']),
    (['status', '--json'], ['status', '--json']),
    (['status', 'Ethernet0', '--json'], ['status', '--json', '--', 'Ethernet0']),
    (['status', '--json', 'etp1/1'], ['status', '--json', '--', 'etp1/1']),
    (['sta', 'Ethernet0'], ['status', '--', 'Ethernet0']),
    (['status', 'all'], ['status', '--', 'all']),
    (['hwmode', 'muxdirection', 'all', '--json'], ['hwmode', 'muxdirection', '--json', '--', 'all']),
    (['firmware', 'version', '--active', 'all'], ['firmware', 'version', '--active', '--', 'all']),
    (['firmware', 'version', '--active', 'Ethernet0'], ['firmware', 'version', '--active', '--', 'Ethernet0']),
    (['hwmode', 'muxdirection'], ['hwmode', 'muxdirection']),
    (['hw', 'muxd', '--json', 'Ethernet0'], ['hwmode', 'muxdirection', '--json', '--', 'Ethernet0']),
    (['hwmode', 'switchmode'], ['hwmode', 'switchmode']),
    (['hwmode', 'switchmode', 'Ethernet0'], ['hwmode', 'switchmode', '--', 'Ethernet0']),
    (['firmware', 'version', 'Ethernet0'], ['firmware', 'version', '--', 'Ethernet0']),
    (['firm', 'ver', 'Ethernet0', '--active'], ['firmware', 'version', '--active', '--', 'Ethernet0']),
    (['queueinfo', 'Ethernet0', 'opaque [1, 2]; $(id)', '--json'], ['queueinfo', '--json', '--', 'Ethernet0']),
]
QUERIES += [([command, 'Ethernet0', target, '--json'], [command, '--json', '--', 'Ethernet0', target])
            for command in ('berinfo', 'eyeinfo', 'fecstatistics', 'pcsstatistics')
            for target in ('NIC', 'TORA', 'TORB', 'LOCAL')]
QUERIES += [([command, 'Ethernet0'], [command, '--', 'Ethernet0'])
            for command in ('alivecablestatus', 'event-log', 'get-fec-anlt-speed',
                            'health', 'resetcause', 'operationtime', 'queueinfo')]


@pytest.mark.parametrize('arguments, expected', QUERIES)
def test_ordinary_queries_use_fixed_canonical_argv(mux, arguments, expected):
    result = CliRunner().invoke(mux.muxcable, arguments, obj=object())
    assert result.exit_code == 0, result.output
    command = ['/usr/bin/sudo', '-n', '/usr/local/bin/show', 'muxcable', *expected]
    mux.os.execv.assert_called_once_with(command[0], command)


@pytest.mark.parametrize('arguments', [
    ['berinfo', 'Ethernet0', 'OTHER'], ['berinfo', 'Ethernet0'],
    ['health', 'Ethernet0\n--help'], ['health', 'Ethernet0 other'], ['health', ''],
    ['status', '--namespace', 'asic0'], ['firmware', 'activate', 'Ethernet0'],
    ['firmware', 'download', 'Ethernet0'], ['config', 'Ethernet0', 'extra'],
])
def test_invalid_forms_never_call_sudo(mux, arguments):
    result = CliRunner().invoke(mux.muxcable, arguments, obj=object())
    assert result.exit_code != 0
    mux.os.execv.assert_not_called()


@pytest.mark.parametrize('option', [[], ['set_mode,1'], ['reg_dump'], ['None']])
def test_vendor_debug_requires_explicit_administrator(mux, option):
    result = CliRunner().invoke(mux.muxcable, ['debugdumpregisters', 'Ethernet0', *option], obj=object())
    assert result.exit_code != 0
    assert 'require sudo show muxcable debugdumpregisters' in result.output
    mux.os.execv.assert_not_called()


def test_option_like_port_remains_one_argument_after_delimiter(mux):
    result = CliRunner().invoke(mux.muxcable, ['health', '--', '--help'], obj=object())
    assert result.exit_code == 0
    assert mux.os.execv.call_args.args[1][-2:] == ['--', '--help']


def test_root_executes_original_callback_and_preserves_result(mux, monkeypatch):
    monkeypatch.setattr(mux.os, 'geteuid', lambda: 0)
    callback = MagicMock(return_value=7)
    assert mux._run_query_as_root(callback)('db', port='Ethernet0') == 7
    callback.assert_called_once_with('db', port='Ethernet0')
    mux.os.execv.assert_not_called()


def test_exec_failure_propagates_without_running_query(mux):
    mux.os.execv.side_effect = FileNotFoundError('sudo absent')
    result = CliRunner().invoke(mux.muxcable, ['health', 'Ethernet0'], obj=object())
    assert result.exit_code != 0
    assert isinstance(result.exception, FileNotFoundError)
