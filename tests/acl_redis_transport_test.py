"""Exercise ACL display delegation without loading platform dependencies."""

from pathlib import Path
import runpy
import sys
import types
from unittest.mock import MagicMock

import click
from click.testing import CliRunner
import pytest


@pytest.fixture
def acl_commands(monkeypatch):
    cli = types.ModuleType('utilities_common.cli')
    cli.AliasedGroup = click.Group
    cli.run_command = MagicMock()
    package = types.ModuleType('utilities_common')
    package.cli = cli
    monkeypatch.setitem(sys.modules, 'utilities_common', package)
    monkeypatch.setitem(sys.modules, 'utilities_common.cli', cli)
    source = Path(__file__).resolve().parents[1] / 'show/acl.py'
    module = runpy.run_path(str(source))
    return module['acl'], cli.run_command


@pytest.mark.parametrize('arguments,expected', [
    (['table'], ['table']),
    (['table', 'DATAACL'], ['table', '--', 'DATAACL']),
    (['rule', 'DATAACL', 'RULE_1'], ['rule', '--', 'DATAACL', 'RULE_1']),
    (['table', '--', '--help'], ['table', '--', '--help']),
])
@pytest.mark.parametrize('uid', [0, 1000])
def test_acl_display_preserves_selected_read(acl_commands, monkeypatch, arguments, expected, uid):
    command, run = acl_commands
    monkeypatch.setattr('os.geteuid', lambda: uid)
    result = CliRunner().invoke(command, arguments)
    assert result.exit_code == 0, result.output
    prefix = ['acl-loader'] if uid == 0 else ['/usr/bin/sudo', '-n', '/usr/local/bin/acl-loader']
    run.assert_called_once_with(prefix + ['show', *expected], display_cmd=False)
