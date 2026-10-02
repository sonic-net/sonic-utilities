import argparse
import ast
import gzip
import os
import subprocess
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


def run_real_pipe(cmd0, *cmds):
    """Exercise the commands emitted by find_log, without mocking find/zgrep."""
    processes = []
    for cmd in (cmd0,) + cmds:
        previous = processes[-1] if processes else None
        process = subprocess.Popen(
            cmd, stdin=previous.stdout if previous else None,
            stdout=subprocess.PIPE, universal_newlines=True)
        if previous:
            previous.stdout.close()
        processes.append(process)
    output = processes[-1].communicate()[0]
    return [process.wait() for process in processes], output.rstrip('\n')


def load_find_log(reference):
    tree = ast.parse(SCRIPT.read_text(), filename=str(SCRIPT))
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in ('build_options', 'find_log')
    ]
    namespace = {
        'getstatusoutput_noshell_pipe': run_real_pipe,
        'reference_file': str(reference),
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SCRIPT), 'exec'), namespace)
    return namespace['find_log']


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


@pytest.mark.parametrize('field', [0, 2])
def test_storyteller_pipeline_rejects_log_file_symlink(tmp_path, field, capsys):
    logs = tmp_path / 'logs'
    logs.mkdir()
    outside = tmp_path / 'outside'
    outside.write_text('OUTSIDE_MARKER\n')
    (logs / 'syslog.1').write_text('INSIDE_MARKER\n')
    (logs / 'syslog.2').symlink_to(outside)
    reference = tmp_path / 'reference'
    reference.touch()
    os.utime(reference, (1, 1))

    load_find_log(reference)(str(logs), 'syslog', 'MARKER', field=field)

    output = capsys.readouterr().out
    assert 'INSIDE_MARKER' in output
    assert 'OUTSIDE_MARKER' not in output


@pytest.mark.parametrize('field', [0, 2])
def test_storyteller_pipeline_preserves_filename_spaces(tmp_path, field, monkeypatch, capsys):
    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / 'syslog other').write_text('INSIDE_MARKER\n')
    working = tmp_path / 'working'
    working.mkdir()
    (working / 'other').write_text('OUTSIDE_MARKER\n')
    monkeypatch.chdir(working)
    reference = tmp_path / 'reference'
    reference.touch()
    os.utime(reference, (1, 1))

    load_find_log(reference)(str(logs), 'syslog', 'MARKER', field=field)

    output = capsys.readouterr().out
    assert 'INSIDE_MARKER' in output
    assert 'OUTSIDE_MARKER' not in output


@pytest.mark.parametrize('field', [0, 2])
def test_storyteller_pipeline_no_match_reads_no_files(tmp_path, field, monkeypatch, capsys):
    logs = tmp_path / 'logs'
    logs.mkdir()
    working = tmp_path / 'working'
    working.mkdir()
    (working / 'syslog').write_text('OUTSIDE_MARKER\n')
    monkeypatch.chdir(working)
    reference = tmp_path / 'reference'
    reference.touch()
    os.utime(reference, (1, 1))

    load_find_log(reference)(str(logs), 'syslog', 'MARKER', field=field)

    assert 'OUTSIDE_MARKER' not in capsys.readouterr().out


@pytest.mark.parametrize('field', [0, 2])
def test_storyteller_pipeline_keeps_compressed_logs(tmp_path, field, capsys):
    logs = tmp_path / 'logs'
    logs.mkdir()
    older = logs / 'syslog.1.gz'
    newer = logs / 'syslog.2.gz'
    with gzip.open(older, 'wt') as stream:
        stream.write('OLDER_MARKER\n')
    with gzip.open(newer, 'wt') as stream:
        stream.write('NEWER_MARKER\n')
    os.utime(older, (10, 10))
    os.utime(newer, (20, 20))
    reference = tmp_path / 'reference'
    reference.touch()
    os.utime(reference, (1, 1))

    load_find_log(reference)(str(logs), 'syslog', 'MARKER', field=field)

    output = capsys.readouterr().out
    assert 'OLDER_MARKER' in output
    assert 'NEWER_MARKER' in output
    if field == 0:
        assert output.index('OLDER_MARKER') < output.index('NEWER_MARKER')
