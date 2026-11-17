from types import SimpleNamespace
from unittest import mock

from click.testing import CliRunner
import pytest

import sfputil.main as main
import sfputil.debug as debug
from sfputil.port import is_cpo_port


@pytest.fixture
def platform(monkeypatch):
    sfp = mock.Mock()
    sfp.get_presence.return_value = False
    chassis = mock.Mock()
    chassis.get_cpo.side_effect = lambda index: object() if index == 1 else None
    chassis.get_sfp.side_effect = lambda index: sfp if index == 2 else pytest.fail('SFP API used on CPO')
    mapping = {'Ethernet0': [1], 'Ethernet8': [2], 'Ethernet16': [3, 1]}
    helper = mock.Mock()
    helper.logical = list(mapping)
    helper.is_logical_port.side_effect = lambda port: port in mapping
    helper.get_logical_to_physical.side_effect = lambda port: mapping.get(port)
    monkeypatch.setattr(main, 'platform_chassis', chassis)
    monkeypatch.setattr(main, 'platform_sfputil', helper)
    monkeypatch.setattr(main.os, 'geteuid', lambda: 0)
    for name in ('load_platform_chassis', 'load_sfputilhelper', 'load_port_config'):
        monkeypatch.setattr(main, name, lambda: True)
    common = main.platform_sfputil_helper
    monkeypatch.setattr(common, 'platform_chassis', chassis)
    for name in ('load_platform_sfputil', 'load_chassis', 'platform_sfputil_read_porttab_mappings'):
        monkeypatch.setattr(common, name, lambda: True)
    monkeypatch.setattr(main, 'is_port_type_rj45', lambda port: False)
    monkeypatch.setattr(debug, 'get_validated_physical_port_list', lambda port: mapping[port])
    return SimpleNamespace(chassis=chassis, helper=helper, sfp=sfp)


@pytest.mark.parametrize('error', [NotImplementedError, AttributeError, IndexError])
def test_legacy_chassis(error):
    chassis = mock.Mock()
    chassis.get_cpo.side_effect = error
    assert not is_cpo_port(1, chassis)
    chassis.get_sfp.assert_not_called()


def test_no_get_cpo_method():
    assert not is_cpo_port(1, object())


def test_does_not_hide_unexpected_errors():
    chassis = mock.Mock()
    chassis.get_cpo.side_effect = RuntimeError('bad topology')
    with pytest.raises(RuntimeError):
        is_cpo_port(1, chassis)


def test_filter_mixed_and_ganged_ports(platform):
    assert main.filter_cpo_ports(
        platform.helper.logical, platform.helper.get_logical_to_physical, platform.chassis
    ) == ['Ethernet8']
    platform.chassis.get_sfp.assert_not_called()


def test_cpo_detection_ignores_get_sfp_bridge(platform):
    assert is_cpo_port(1, platform.chassis)
    assert not is_cpo_port(2, platform.chassis)
    platform.chassis.get_sfp.assert_not_called()


@pytest.mark.parametrize('args', [
    ['show', 'presence', '-p', 'Ethernet0'],
    ['show', 'eeprom', '-p', 'Ethernet0'],
    ['show', 'eeprom-hexdump', '-p', 'Ethernet0'],
    ['show', 'lpmode', '-p', 'Ethernet0'],
    ['show', 'error-status', '-p', 'Ethernet0'],
    ['reset', 'Ethernet0'],
    ['lpmode', 'on', 'Ethernet0'],
    ['read-eeprom', '-p', 'Ethernet0', '-n', '0', '-o', '0', '-s', '1'],
    ['write-eeprom', '-p', 'Ethernet0', '-n', '0', '-o', '0', '--data', '01'],
    ['debug', 'loopback', 'Ethernet0', 'host-side-input', 'enable'],
    ['debug', 'loopback-capability', 'Ethernet0'],
])
def test_explicit_cpo_rejected_before_sfp_access(platform, args):
    result = CliRunner().invoke(main.cli, args)
    assert result.exit_code != 0
    assert 'CPO port; please use cpoutil' in result.output, (args, result.output, result.exception)
    platform.chassis.get_sfp.assert_not_called()


def test_global_presence_and_empty_sfp(platform):
    result = CliRunner().invoke(main.cli, ['show', 'presence'])
    assert result.exit_code == 0, result.exception
    assert 'Ethernet8' in result.output and 'Not present' in result.output
    assert 'Ethernet0' not in result.output and 'Ethernet16' not in result.output
    platform.chassis.get_sfp.assert_called_once_with(2)


def test_version_works_with_cpo_config(platform, monkeypatch):
    detector = mock.Mock(side_effect=AssertionError('must not inspect cpo.json'))
    monkeypatch.setattr(main.device_info, 'get_cpo_data', detector)
    result = CliRunner().invoke(main.cli, ['version'])
    assert result.exit_code == 0
    detector.assert_not_called()


def test_invalid_port_keeps_existing_error(platform):
    result = CliRunner().invoke(main.cli, ['show', 'presence', '-p', 'Ethernet100'])
    assert result.exit_code == main.ERROR_INVALID_PORT
    assert 'invalid port' in result.output.lower()


def test_no_cpo_platform_preserves_all_ports(platform):
    platform.chassis.get_cpo.side_effect = NotImplementedError
    assert main.filter_cpo_ports(
        platform.helper.logical, platform.helper.get_logical_to_physical, platform.chassis
    ) == platform.helper.logical


def test_debug_global_filter(platform, monkeypatch):
    monkeypatch.setattr(debug, 'get_logical_list', lambda: platform.helper.logical)
    assert debug.filter_cpo_ports(
        debug.get_logical_list(), debug.get_validated_physical_port_list, platform.chassis
    ) == ['Ethernet8']


def test_debug_sfp_delegates_unchanged(platform, monkeypatch):
    original = mock.Mock(return_value=platform.sfp)
    monkeypatch.setattr(debug, '_get_sfp_object', original)
    assert debug.get_sfp_object('Ethernet8') is platform.sfp
    original.assert_called_once_with('Ethernet8')
