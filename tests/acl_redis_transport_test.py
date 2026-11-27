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
    (['table', 'EDGE ACL'], ['table', '--', 'EDGE ACL']),
    (['rule', 'DATAACL', 'RULE_1'], ['rule', '--', 'DATAACL', 'RULE_1']),
    (['rule', 'EDGE ACL', 'ALLOW SSH'], ['rule', '--', 'EDGE ACL', 'ALLOW SSH']),
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


@pytest.mark.parametrize('process_namespace,option,expected', [
    ('asic0', None, 'asic0'),
    ('asic0', 'asic1', 'asic1'),
    ('', None, ''),
])
@pytest.mark.parametrize('operation', ['add', 'remove'])
def test_acl_configuration_uses_selected_namespace(process_namespace, option, expected, operation):
    import ast

    source = Path(__file__).resolve().parents[1] / 'config/main.py'
    tree = ast.parse(source.read_text())
    name = 'add_table' if operation == 'add' else 'remove_table'
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    function.decorator_list = []
    databases = {namespace: {} for namespace in ['', 'asic0', 'asic1']}
    if operation == 'remove':
        for tables in databases.values():
            tables['OUTDATAACL'] = {'stage': 'egress'}

    class Connector:
        def __init__(self, namespace, **kwargs):
            self.namespace = namespace or ''

        def connect(self):
            pass

        def set_entry(self, table, key, value):
            if value is None:
                databases[self.namespace].pop(key, None)
            else:
                databases[self.namespace][key] = value

    parse = MagicMock(return_value={'stage': 'egress'})
    namespace = {'ConfigDBConnector': Connector, 'DEFAULT_NAMESPACE': '',
                 'multi_asic': types.SimpleNamespace(get_current_namespace=lambda: process_namespace),
                 'parse_acl_table_info': parse}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    if operation == 'add':
        namespace[name](None, 'OUTDATAACL', 'L3', None, 'PortChannel102', 'egress', option)
        parse.assert_called_once_with('OUTDATAACL', 'L3', None, 'PortChannel102', 'egress', expected)
    else:
        namespace[name]('OUTDATAACL', option)
    for selected, tables in databases.items():
        assert ('OUTDATAACL' in tables) == ((selected == expected) == (operation == 'add'))
