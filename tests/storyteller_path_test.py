import argparse
import ast
import os
import sys
from pathlib import Path
from shlex import quote
from types import SimpleNamespace

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


def load_main(validator, calls):
    tree = ast.parse(SCRIPT.read_text(), filename=str(SCRIPT))
    main = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'main'
    )
    namespace = {
        'os': SimpleNamespace(geteuid=lambda: 0),
        'argparse': argparse,
        'validate_log_args': validator,
        'quote': quote,
        'build_regex': lambda category: category,
        'configure_time_filter': lambda since: None,
        'find_log': lambda *args: calls.append(args),
    }
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(SCRIPT), 'exec'), namespace)
    return namespace['main']


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


def test_storyteller_main_uses_validated_directory(tmp_path, monkeypatch):
    allowed = tmp_path / 'logs'
    allowed.mkdir()
    validator = load_validator()
    validator.__globals__['ALLOWED_LOG_DIR'] = str(allowed)
    calls = []
    monkeypatch.setattr(sys, 'argv', ['storyteller', '--logpath', str(allowed), '--log', 'syslog'])

    load_main(validator, calls)()

    assert len(calls) == 1
    assert calls[0][0:2] == (str(allowed), 'syslog')


def test_storyteller_main_reports_invalid_prefix(tmp_path, monkeypatch, capsys):
    allowed = tmp_path / 'logs'
    allowed.mkdir()
    validator = load_validator()
    validator.__globals__['ALLOWED_LOG_DIR'] = str(allowed)
    calls = []
    monkeypatch.setattr(sys, 'argv', ['storyteller', '--logpath', str(allowed), '--log', 'subdir/log'])

    with pytest.raises(SystemExit) as exc:
        load_main(validator, calls)()

    assert exc.value.code == 2
    assert '--log must be a nonempty file-name prefix' in capsys.readouterr().err
    assert not calls
