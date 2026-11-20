import os
import subprocess
from pathlib import Path

import pytest

REBOOT_SCRIPT = Path(__file__).parents[1] / 'scripts' / 'reboot'

INVALID_ARGUMENTS = [
    (['cause', 'history'], 'unexpected argument(s): cause history'),
    (['history'], 'unexpected argument(s): history'),
    (['-v', 'cause'], 'unexpected argument(s): cause'),
    (['--', 'cause'], 'unexpected argument(s): cause'),
    (['cause', '-f'], 'unexpected argument(s): cause -f'),
    # An unquoted $@ at the parse_options call site would drop this argument
    ([''], 'unexpected argument(s): '),
    (['-x'], 'invalid option -x'),
    (['--force'], 'invalid option --'),
    (['-d'], 'option -d requires an argument'),
]

SUPPORTED_OPTIONS = [
    ([], {}),
    (['--'], {}),
    (['-v'], {'VERBOSE': 'yes'}),
    (['-f'], {'REBOOT_FLAGS': ' -f'}),
    (['-vf'], {'VERBOSE': 'yes', 'REBOOT_FLAGS': ' -f'}),
    (['-b', '-v'], {'BLOCKING_MODE': 'yes', 'VERBOSE': 'yes'}),
    (['-d', 'DPU0'], {'REBOOT_DPU': 'yes', 'DPU_MODULE_NAME': 'DPU0'}),
    (['-p'], {'PRE_SHUTDOWN': 'yes'}),
]

# reboot runs its main flow at the top level and cannot be sourced, so these
# tests extract the option parser with sed and call it directly.
PARSER_FUNCTIONS = ['show_help_and_exit', 'show_usage_error_and_exit', 'parse_options']
PARSED_VARIABLES = ['VERBOSE', 'REBOOT_FLAGS', 'REBOOT_DPU', 'DPU_MODULE_NAME', 'PRE_SHUTDOWN', 'BLOCKING_MODE']


def run_parse_options(*args):
    extract = ';'.join('/^function {}()/,/^}}/p'.format(name) for name in PARSER_FUNCTIONS)
    driver = (
        f'source <(grep -E "^declare -r EXIT_[A-Z_]+=[0-9]+$" "{REBOOT_SCRIPT}")\n'
        f'source <(sed -n \'{extract}\' "{REBOOT_SCRIPT}")\n'
        'declare -F parse_options > /dev/null || exit 99\n'
        'SCRIPT=$0\n'
        'parse_options "$@"\n'
        + ''.join(f'echo "{name}=${{{name}}}"\n' for name in PARSED_VARIABLES)
    )
    result = subprocess.run(['bash', '-c', driver, 'reboot'] + list(args),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 99, 'parse_options not extracted from reboot: {}'.format(result.stderr)
    return result


def parsed_variables(result):
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


@pytest.mark.parametrize('args, error', INVALID_ARGUMENTS)
def test_invalid_arguments_are_rejected(args, error):
    result = run_parse_options(*args)

    assert result.returncode == 1
    assert error in result.stderr
    assert 'No reboot was initiated' in result.stderr
    # parse_options exited, so nothing after it ran
    assert parsed_variables(result) == {}


@pytest.mark.parametrize('args, expected', SUPPORTED_OPTIONS)
def test_supported_options_are_accepted(args, expected):
    result = run_parse_options(*args)

    assert result.returncode == 0, result.stderr
    parsed = parsed_variables(result)
    assert {name: value for name, value in parsed.items() if value} == expected


@pytest.mark.parametrize('option', ['-h', '-?'])
def test_help_exits_successfully(option):
    result = run_parse_options(option)

    assert result.returncode == 0
    assert 'Usage reboot [options]' in result.stdout
    assert result.stderr == ''


# Exit status of the script copy below once parse_options has returned
PASSED_ARGUMENT_PARSING = 99


@pytest.fixture
def reboot_through_parsing(tmp_path):
    """Run the real top-level code of reboot up to and including its parse_options call.

    The copy ends right after that call. The root check, stopping services, writing the
    reboot cause and rebooting (/sbin/reboot, kexec, platform tools) are not in it, so
    the tests are safe as root and as a normal user, even if parsing accepts arguments
    it should reject.
    """
    if os.path.exists('/proc/vmcore') and os.path.getsize('/proc/vmcore') > 0:
        pytest.skip('reboot reboots at once in a kdump capture kernel, before parsing arguments')

    lines = REBOOT_SCRIPT.read_text().splitlines(keepends=True)
    calls = [number for number, line in enumerate(lines) if line.startswith('parse_options')]
    assert len(calls) == 1, 'expected one top-level parse_options call in reboot'
    script = tmp_path / 'reboot'
    script.write_text(''.join(lines[:calls[0] + 1]) + f'exit {PASSED_ARGUMENT_PARSING}\n')

    # Commands that reboot runs before parsing arguments
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in (('sonic-cfggen', '#!/bin/bash\n'),
                       ('logname', '#!/bin/bash\necho admin\n'),
                       ('reboot_smartswitch_helper', '# sourced by reboot\n')):
        stub = bin_dir / name
        stub.write_text(body)
        stub.chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ.get('PATH', '')}")

    def run(*args):
        return subprocess.run(['bash', str(script)] + list(args), env=env,
                              capture_output=True, text=True, timeout=10)
    return run


@pytest.mark.parametrize('args, error', INVALID_ARGUMENTS)
def test_script_stops_at_invalid_arguments(reboot_through_parsing, args, error):
    result = reboot_through_parsing(*args)

    # EXIT_ERROR from parse_options. PASSED_ARGUMENT_PARSING would mean that the
    # script went on towards the reboot.
    assert result.returncode == 1
    assert error in result.stderr
    assert 'No reboot was initiated' in result.stderr


@pytest.mark.parametrize('args', [args for args, _ in SUPPORTED_OPTIONS])
def test_script_continues_after_supported_options(reboot_through_parsing, args):
    result = reboot_through_parsing(*args)

    assert result.returncode == PASSED_ARGUMENT_PARSING, result.stderr
