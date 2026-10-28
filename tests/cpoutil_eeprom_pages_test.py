from types import SimpleNamespace

import pytest

from .cpoutil_test import coverage_environment as _coverage_environment
from .cpoutil_test import invoke_coverage, shared_port_mapping  # noqa: F401


coverage_environment = _coverage_environment


@pytest.fixture
def endpoints(coverage_environment):
    # conftest reloads platform modules between files; use the current classes.
    from sonic_platform_base.sonic_xcvr.codes.public.cmis import CmisCodes
    from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis import CmisMemMap
    from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis.pages.page import CmisPage

    cpo = coverage_environment
    els_map = CmisMemMap(CmisCodes)
    # Model an endpoint with remapped upper pages using public CMIS metadata.
    els_map.pages = [CmisPage(CmisCodes, page=page) for page in (0xB4, 0xB5, 0xB6)]
    maps = {'oe': CmisMemMap(CmisCodes), 'els': els_map}
    for name, attribute in (('oe', 'oe'), ('els', 'elsfp')):
        api = SimpleNamespace(
            xcvr_eeprom=SimpleNamespace(mem_map=maps[name], reader=cpo.read_eeprom),
            get_max_supported_banks=lambda: 1,
        )
        setattr(cpo, attribute, SimpleNamespace(
            get_api=lambda api=api: api, read_eeprom=cpo.read_eeprom, write_eeprom=cpo.write_eeprom))
    return cpo, maps


def command(operation, target, interface, page, offset=128, size=1):
    arguments = [operation]
    arguments += ['interface', '-p', 'Ethernet0', '--' + target] if interface else [target, '-i', '0']
    arguments += ['-n', hex(page), '-o', str(offset)]
    arguments += ['-s', str(size)] if operation == 'read-eeprom' else ['-d', '01' * size]
    return arguments


@pytest.mark.parametrize('operation', ['read-eeprom', 'write-eeprom'])
@pytest.mark.parametrize('interface', [False, True])
@pytest.mark.parametrize('target,page', [('oe', 0), ('oe', 0x11), ('els', 0xB4), ('els', 0xB5), ('els', 0xB6)])
def test_declared_page_is_accessible(endpoints, operation, interface, target, page):
    cpo, _ = endpoints
    result = invoke_coverage(command(operation, target, interface, page))
    assert result.exit_code == 0, result.output
    accesses = cpo.reads if operation == 'read-eeprom' else cpo.writes
    assert len(accesses) == 1


@pytest.mark.parametrize('operation', ['read-eeprom', 'write-eeprom'])
@pytest.mark.parametrize('interface', [False, True])
@pytest.mark.parametrize('target,page', [
    ('oe', 0x30), ('oe', 0xB4), ('els', 0), ('els', 0x10), ('els', 0xB0), ('els', 0xB8),
])
def test_undeclared_page_is_rejected_before_io(endpoints, operation, interface, target, page):
    cpo, _ = endpoints
    result = invoke_coverage(command(operation, target, interface, page))
    assert result.exit_code == 1, result.output
    assert 'is not declared' in result.output and 'valid pages:' in result.output
    assert cpo.reads == [] and cpo.writes == []


@pytest.mark.parametrize('operation', ['read-eeprom', 'write-eeprom'])
@pytest.mark.parametrize('lower,offset,size', [(False, 0, 1), (False, 127, 2), (True, 128, 1), (True, 127, 2)])
def test_page_half_is_enforced(endpoints, operation, lower, offset, size):
    from sonic_platform_base.sonic_xcvr.codes.public.cmis import CmisCodes
    from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis import CmisFlatMemMap

    cpo, maps = endpoints
    mem_map = CmisFlatMemMap(CmisCodes)
    mem_map.pages = [mem_map.pages[0 if lower else 1]]
    cpo.oe.get_api().xcvr_eeprom.mem_map = mem_map
    result = invoke_coverage(command(operation, 'oe', False, 0, offset, size))
    assert result.exit_code == 1, result.output
    assert 'does not cover offsets' in result.output
    assert cpo.reads == [] and cpo.writes == []


@pytest.mark.parametrize('operation', ['read-eeprom', 'write-eeprom'])
def test_page_zero_can_span_both_declared_halves(endpoints, operation):
    cpo, _ = endpoints
    result = invoke_coverage(command(operation, 'oe', False, 0, 120, 16))
    assert result.exit_code == 0, result.output
    assert len(cpo.reads if operation == 'read-eeprom' else cpo.writes) == 1


@pytest.mark.parametrize('operation', ['read-eeprom', 'write-eeprom'])
@pytest.mark.parametrize('pages', [None, []])
def test_missing_page_metadata_fails_closed(endpoints, operation, pages):
    cpo, _ = endpoints
    cpo.oe.get_api().xcvr_eeprom.mem_map.pages = pages
    result = invoke_coverage(command(operation, 'oe', False, 0))
    assert result.exit_code == 1, result.output
    assert 'EEPROM memory map is unavailable' in result.output
    assert cpo.reads == [] and cpo.writes == []
