from unittest import mock

import pytest
from click.testing import CliRunner

import cpoutil.main as cpoutil
from .cpoutil_test import coverage_environment as _coverage_environment
from .cpoutil_test import hooked as _hooked
from .cpoutil_test import invoke_coverage, shared_port_mapping  # noqa: F401


coverage_environment = _coverage_environment
hooked = _hooked
COMMANDS = [
    (('show', 'interface', 'presence'), (), False),
    (('show', 'interface', 'map'), (), False),
    (('show', 'interface', 'dom'), (), False),
    (('show', 'interface', 'tx-disable'), (), False),
    (('show', 'interface', 'lane-status'), (), False),
    (('show', 'interface', 'speed', 'application'), (), False),
    (('config', 'interface', 'tx-disable'), ('true',), True),
    (('read-eeprom', 'interface'), ('--oe', '-n', '0', '-o', '128', '-s', '1'), True),
    (('write-eeprom', 'interface'), ('--oe', '-n', '0', '-o', '128', '-d', '01'), True),
]


@pytest.mark.parametrize('path,tail,required', COMMANDS)
@pytest.mark.parametrize('option', ['-p', '--port'])
def test_port_option_selects_interface(hooked, path, tail, required, option):
    result = invoke_coverage(list(path) + [option, 'Ethernet0'] + list(tail))
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('path,tail,required', [item for item in COMMANDS if not item[2]])
def test_show_without_port_keeps_global_query(hooked, path, tail, required):
    result = invoke_coverage(list(path) + list(tail))
    assert result.exit_code == 0, result.output
    assert 'Ethernet0' in result.output


@pytest.mark.parametrize('path,tail,required', [item for item in COMMANDS if item[2]])
def test_required_port_is_checked_before_platform_load(monkeypatch, path, tail, required):
    load = mock.Mock(side_effect=AssertionError('Invalid command must not initialize hardware'))
    monkeypatch.setattr(cpoutil, 'initialize_platform', load)
    result = invoke_coverage(list(path) + list(tail))
    assert result.exit_code == 2, result.output
    assert "Missing option '-p' / '--port'" in result.output
    load.assert_not_called()


@pytest.mark.parametrize('path,tail,required', COMMANDS)
def test_positional_port_is_rejected_before_platform_load(monkeypatch, path, tail, required):
    load = mock.Mock(side_effect=AssertionError('Invalid command must not initialize hardware'))
    monkeypatch.setattr(cpoutil, 'initialize_platform', load)
    result = invoke_coverage(list(path) + ['Ethernet0'] + list(tail))
    assert result.exit_code == 2, result.output
    load.assert_not_called()


@pytest.mark.parametrize('path,tail,required', COMMANDS)
def test_port_option_requires_a_value(monkeypatch, path, tail, required):
    load = mock.Mock(side_effect=AssertionError('Invalid command must not initialize hardware'))
    monkeypatch.setattr(cpoutil, 'initialize_platform', load)
    result = invoke_coverage(list(path) + ['-p'])
    assert result.exit_code == 2, result.output
    assert "Option '-p' requires an argument" in result.output
    load.assert_not_called()


@pytest.mark.parametrize('path,tail,required', COMMANDS)
def test_help_describes_port_option(monkeypatch, path, tail, required):
    load = mock.Mock(side_effect=AssertionError('Help must not initialize hardware'))
    monkeypatch.setattr(cpoutil, 'initialize_platform', load)
    result = invoke_coverage(list(path) + ['--help'])
    assert result.exit_code == 0, result.output
    assert '-p, --port PORT' in result.output
    assert ('[required]' in result.output) == required
    load.assert_not_called()


@pytest.mark.parametrize('path,tail,required', COMMANDS)
def test_bash_completion_lists_port_option(monkeypatch, path, tail, required):
    load = mock.Mock(side_effect=AssertionError('Completion must not initialize hardware'))
    monkeypatch.setattr(cpoutil, 'initialize_platform', load)
    words = ['cpoutil', *path, '-']
    result = CliRunner().invoke(cpoutil.cli, [], prog_name='cpoutil', env={
        '_CPOUTIL_COMPLETE': 'bash_complete', 'COMP_WORDS': ' '.join(words),
        'COMP_CWORD': str(len(words) - 1),
    })
    assert result.exit_code == 0, result.output
    assert 'plain,-p' in result.output and 'plain,--port' in result.output
    load.assert_not_called()
