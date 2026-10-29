"""Check direct callers that choose TCP or Unix from database metadata."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'clear/orchagent.py',
    'show/orchagent.py',
)


def metadata_calls():
    for name in FILES:
        tree = ast.parse((ROOT / name).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or len(node.args) < 3:
                continue
            if ast.unparse(node.func) != "swsscommon.DBConnector":
                continue
            if isinstance(node.args[2], ast.Compare):
                yield pytest.param(node, id="{}:{}".format(name, node.lineno))


def test_audited_callers_do_not_force_local_tcp():
    for name in FILES:
        tree = ast.parse((ROOT / name).read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and len(node.args) >= 3
                    and ast.unparse(node.func) == "swsscommon.DBConnector"
                    and isinstance(node.args[2], ast.Constant)
                    and node.args[2].value is True):
                database = ast.literal_eval(node.args[0])
                assert database in ("CHASSIS_STATE_DB", "CHASSIS_APP_DB"), (
                    "{}:{} still forces TCP for {}".format(name, node.lineno, database))


@pytest.mark.parametrize("call", list(metadata_calls()))
@pytest.mark.parametrize("port", [0, 6379, 6400, None])
def test_direct_call_uses_its_database_and_namespace(call, port):
    # Evaluate the actual constructor expression without importing the CLI or
    # running its other actions. The native connector has separate real tests.
    names = {node.id: "value:" + node.id for node in ast.walk(call)
             if isinstance(node, ast.Name)}

    def evaluate(node):
        return eval(compile(ast.Expression(node), "caller", "eval"), names)

    database = evaluate(call.args[0])
    namespace = evaluate(call.args[3]) if len(call.args) > 3 else ""
    connections = []

    def get_port(actual_database, actual_namespace):
        assert (actual_database, actual_namespace) == (database, namespace)
        if port is None:
            raise RuntimeError("database metadata unavailable")
        return port

    names["swsscommon"] = SimpleNamespace(
        DBConnector=lambda *args: connections.append(args),
        SonicDBConfig=SimpleNamespace(getDbPort=get_port),
    )
    if port is None:
        with pytest.raises(RuntimeError, match="metadata unavailable"):
            evaluate(call)
        assert connections == []
    else:
        evaluate(call)
        assert len(connections) == 1
        assert connections[0][0] == database
        assert connections[0][2] is (port != 0)
        if len(call.args) > 3:
            assert connections[0][3] == namespace


@pytest.mark.parametrize('namespace', ['', 'asic0', 'asic3'])
@pytest.mark.parametrize('initialized', [False, True])
@pytest.mark.parametrize('port', [0, 6379])
def test_clear_initializes_namespace_metadata_before_selecting_transport(namespace, initialized, port):
    tree = ast.parse((ROOT / 'clear/orchagent.py').read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_send_clear')
    statements = []
    for node in function.body:
        statements.append(node)
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'db'
                                               for target in node.targets):
            break
    state = {'initialized': initialized, 'initializations': 0}
    calls = []

    def initialize():
        state['initializations'] += 1
        state['initialized'] = True

    def get_port(database, selected_namespace):
        assert (database, selected_namespace) == ('APPL_DB', namespace)
        assert not namespace or state['initialized'], 'Namespace metadata was read before initialization'
        return port

    values = dict(namespace=namespace, REDIS_TIMEOUT_MSECS=0,
                  swsscommon=SimpleNamespace(
                      DBConnector=lambda *args: calls.append(args),
                      SonicDBConfig=SimpleNamespace(
                          isGlobalInit=lambda: state['initialized'],
                          initializeGlobalConfig=initialize, getDbPort=get_port)))
    code = compile(ast.Module(body=statements, type_ignores=[]), 'clear-init', 'exec')
    exec(code, values)
    exec(code, values)
    assert calls == [('APPL_DB', 0, port != 0, namespace)] * 2
    assert state['initializations'] == int(bool(namespace) and not initialized)
