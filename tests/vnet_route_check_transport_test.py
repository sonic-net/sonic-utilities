"""Exercise local VNET callers without deriving transport from TCP metadata."""

import importlib.util
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def vnet():
    path = Path(__file__).resolve().parents[1] / 'scripts/vnet_route_check.py'
    spec = importlib.util.spec_from_file_location('vnet_route_check', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('function_name,database,arguments', [
    ('check_vnet_cfg', 'APPL_DB', ()),
    ('get_vnet_intfs', 'APPL_DB', ()),
    ('get_all_rifs_oids', 'COUNTERS_DB', ()),
    ('get_vrf_entries', 'ASIC_DB', ()),
    ('filter_out_vnet_ip2me_routes', 'APPL_DB', ({},)),
    ('get_vnet_routes_from_app_db', 'APPL_DB', ()),
    ('get_vnet_routes_from_asic_db', 'ASIC_DB', ()),
    ('filter_active_vnet_routes', 'STATE_DB', ({},)),
    ('main', 'ASIC_DB', ()),
])
def test_local_socket_failure_propagates_without_tcp_fallback(
        vnet, function_name, database, arguments):
    with mock.patch.object(vnet.swsscommon.SonicDBConfig, 'getDbPort',
                           side_effect=RuntimeError('transport must be explicit')) as get_port, \
            mock.patch.object(vnet.swsscommon, 'DBConnector',
                              side_effect=RuntimeError('local socket unavailable')) as connector, \
            mock.patch('sys.argv', ['vnet_route_check.py']):
        if function_name == 'main':
            vnet.check_vnet_cfg = mock.Mock(return_value=True)
        with pytest.raises(RuntimeError, match='local socket unavailable'):
            getattr(vnet, function_name)(*arguments)

    get_port.assert_not_called()
    connector.assert_called_once_with(database, 0, False)
