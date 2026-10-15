"""CPO platforms must use cpoutil before sfputil initializes hardware."""
import sys
from unittest import mock

import pytest
from click.testing import CliRunner

sys.modules['sonic_platform'] = mock.MagicMock()
import sfputil.main as sfputil  # noqa: E402


@pytest.fixture
def initialization(monkeypatch):
    calls = []
    for target, names in (
            (sfputil, ('load_platform_chassis', 'load_sfputilhelper', 'load_port_config')),
            (sfputil.platform_sfputil_helper,
             ('load_platform_sfputil', 'load_chassis', 'platform_sfputil_read_porttab_mappings'))):
        for name in names:
            function = mock.Mock(return_value=True)
            monkeypatch.setattr(target, name, function)
            calls.append(function)
    monkeypatch.setattr(sfputil.os, 'geteuid', lambda: 0)
    return calls


@pytest.mark.parametrize('cpo_data', [{}, {'oes': {'oe0': {'index': 0}}}])
@pytest.mark.parametrize('arguments', [
    ['show', 'presence'],
    ['reset', 'Ethernet0'],
    ['read-eeprom', '-p', 'Ethernet0'],
    ['write-eeprom', '-p', 'Ethernet0', '--data', '01'],
    ['firmware', 'show', 'Ethernet0'],
    ['debug', 'loopback', 'Ethernet0', 'host-side-input', 'enable'],
    ['version'],
])
def test_cpo_commands_stop_before_initialization(monkeypatch, initialization, cpo_data, arguments):
    detector = mock.Mock(return_value=cpo_data)
    monkeypatch.setattr(sfputil.device_info, 'get_cpo_data', detector)

    result = CliRunner().invoke(sfputil.cli, arguments)

    assert result.exit_code == sfputil.ERROR_NOT_IMPLEMENTED
    assert result.output == (
        'cpo.json detected, current device is cpo device, please use cpoutil instead\n'
    )
    detector.assert_called_once_with()
    for function in initialization:
        function.assert_not_called()


def test_non_cpo_command_continues(monkeypatch, initialization):
    monkeypatch.setattr(sfputil.device_info, 'get_cpo_data', lambda: None)

    result = CliRunner().invoke(sfputil.cli, ['version'])

    assert result.exit_code == 0
    assert result.output == 'sfputil version {}\n'.format(sfputil.VERSION)
    for function in initialization:
        function.assert_called_once_with()


def test_help_does_not_detect_cpo_or_initialize_hardware(monkeypatch, initialization):
    detector = mock.Mock()
    monkeypatch.setattr(sfputil.device_info, 'get_cpo_data', detector)

    result = CliRunner().invoke(sfputil.cli, ['--help'])

    assert result.exit_code == 0
    assert 'Usage:' in result.output
    detector.assert_not_called()
    for function in initialization:
        function.assert_not_called()
