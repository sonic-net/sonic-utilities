"""Keep mux local transport explicit, including when TCP metadata is unavailable."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('database', ['APPL_DB', 'STATE_DB'])
@pytest.mark.parametrize('namespace', ['', 'asic0', 'asic3'])
def test_local_connector_preserves_database_and_namespace(database, namespace):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'show/muxcable.py').read_text())
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'db_connect')
    requests = []
    result = object()

    def connect(*arguments):
        requests.append(arguments)
        return result

    # No SonicDBConfig API is supplied: this caller must not infer transport
    # from a port or require metadata merely to choose its local transport.
    scope = {'swsscommon': SimpleNamespace(DBConnector=connect),
             'REDIS_TIMEOUT_MSECS': 0, 'EMPTY_NAMESPACE': ''}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'muxcaller', 'exec'), scope)
    assert scope['db_connect'](database, namespace) is result
    assert requests == [(database, 0, False, namespace, True)]
