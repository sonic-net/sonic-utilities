import ast
import os
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent.parent / 'scripts' / 'storyteller'


def load_validator():
    tree = ast.parse(SCRIPT.read_text(), filename=str(SCRIPT))
    validator = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'validate_log_args'
    )
    namespace = {'os': os, 'ALLOWED_LOG_DIR': '/var/log'}
    exec(compile(ast.Module(body=[validator], type_ignores=[]), str(SCRIPT), 'exec'), namespace)
    return namespace['validate_log_args']


def test_storyteller_accepts_log_directory_and_prefix(tmp_path):
    allowed = tmp_path / 'logs'
    allowed.mkdir()
    validator = load_validator()
    validator.__globals__['ALLOWED_LOG_DIR'] = str(allowed)

    assert validator(str(allowed), 'syslog') == str(allowed)
    assert validator(str(allowed / 'nested'), 'syslog') == str(allowed / 'nested')


def test_storyteller_rejects_paths_outside_log_directory(tmp_path):
    allowed = tmp_path / 'logs'
    allowed.mkdir()
    outside = tmp_path / 'other'
    outside.mkdir()
    (allowed / 'link').symlink_to(outside, target_is_directory=True)
    validator = load_validator()
    validator.__globals__['ALLOWED_LOG_DIR'] = str(allowed)

    for path in (outside, allowed / '..' / 'other', allowed / 'link'):
        with pytest.raises(ValueError):
            validator(str(path), 'syslog')


@pytest.mark.parametrize('prefix', ['', '.', '..', 'subdir/log'])
def test_storyteller_rejects_invalid_log_prefix(prefix):
    validator = load_validator()
    with pytest.raises(ValueError):
        validator('/var/log', prefix)
