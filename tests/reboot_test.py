import os
import subprocess

import pytest

REBOOT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'reboot')

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
    result = subprocess.run(['bash', '-c', driver, 'reboot'] + list(args), capture_output=True, text=True)
    assert result.returncode != 99, 'parse_options not extracted from reboot: {}'.format(result.stderr)
    return result


def parsed_variables(result):
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


@pytest.mark.parametrize('args, error', [
    (['cause', 'history'], 'unexpected argument(s): cause history'),
    (['history'], 'unexpected argument(s): history'),
    (['-v', 'cause'], 'unexpected argument(s): cause'),
    (['--', 'cause'], 'unexpected argument(s): cause'),
    (['cause', '-f'], 'unexpected argument(s): cause -f'),
    ([''], 'unexpected argument(s): '),
    (['-x'], 'invalid option -x'),
    (['--force'], 'invalid option --'),
    (['-d'], 'option -d requires an argument'),
])
def test_invalid_arguments_are_rejected(args, error):
    result = run_parse_options(*args)

    assert result.returncode == 1
    assert error in result.stderr
    assert 'No reboot was initiated' in result.stderr
    # parse_options exited, so nothing after it ran
    assert parsed_variables(result) == {}


@pytest.mark.parametrize('args, expected', [
    ([], {}),
    (['--'], {}),
    (['-v'], {'VERBOSE': 'yes'}),
    (['-f'], {'REBOOT_FLAGS': ' -f'}),
    (['-vf'], {'VERBOSE': 'yes', 'REBOOT_FLAGS': ' -f'}),
    (['-b', '-v'], {'BLOCKING_MODE': 'yes', 'VERBOSE': 'yes'}),
    (['-d', 'DPU0'], {'REBOOT_DPU': 'yes', 'DPU_MODULE_NAME': 'DPU0'}),
    (['-p'], {'PRE_SHUTDOWN': 'yes'}),
])
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


# The root check comes right after argument parsing and before any reboot side
# effect. As a non-root user, it stops the real script even if parsing let the
# arguments through, so this test never runs as root.
@pytest.mark.skipif(os.geteuid() == 0, reason='runs the real reboot script, which must not run as root here')
class TestRebootScript:
    def run_reboot(self, tmp_path, *args):
        for name, body in (('sonic-cfggen', '#!/bin/bash\n'),
                           ('logname', '#!/bin/bash\necho admin\n'),
                           ('logger', '#!/bin/bash\n'),
                           ('reboot_smartswitch_helper', '# sourced by reboot\n')):
            stub = tmp_path / name
            stub.write_text(body)
            stub.chmod(0o755)
        env = os.environ.copy()
        env['PATH'] = f"{tmp_path}:{env.get('PATH', '')}"
        return subprocess.run(['bash', REBOOT_SCRIPT] + list(args), env=env, capture_output=True, text=True)

    def test_unexpected_arguments_stop_before_reboot(self, tmp_path):
        result = self.run_reboot(tmp_path, 'cause', 'history')

        assert result.returncode == 1
        assert 'unexpected argument(s): cause history' in result.stderr
        assert 'must be run as root' not in result.stderr

    def test_supported_options_reach_root_check(self, tmp_path):
        result = self.run_reboot(tmp_path, '-v')

        assert result.returncode == 1
        assert 'must be run as root' in result.stderr
