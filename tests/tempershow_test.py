"""Unit tests for the ``tempershow`` script's port-name mapping.

These focus on ``_build_port_index_map`` / ``_sfp_display_name``, which
translate a logical port name (e.g. ``Ethernet0``) into the legacy
``xSFP module <N> Temp`` label. The mapping is built directly from the port
config via ``portconfig.get_port_config`` instead of loading the heavy
``sonic_platform_base``/``sonic_xcvr`` stack, so these tests pin both the
correctness of the labels and the lightweight code path.
"""
from unittest import mock

from .utils import load_source

tempershow = load_source('tempershow', 'scripts/tempershow', cache_module=True)


def _patch_env(get_port_config, is_multi_asic=False, num_asics=1):
    """Context managers to drive _build_port_index_map deterministically."""
    return (
        mock.patch.object(tempershow, 'get_port_config', get_port_config),
        mock.patch.object(tempershow.multi_asic, 'is_multi_asic',
                          return_value=is_multi_asic),
        mock.patch.object(tempershow.multi_asic, 'get_num_asics',
                          return_value=num_asics),
        mock.patch.object(tempershow.device_info, 'get_platform_and_hwsku',
                          return_value=('x86_64-mlnx_msn2700-r0', 'ACS-MSN2700')),
    )


class TestBuildPortIndexMap:
    def test_single_asic_uses_index_column(self):
        ports = {
            'Ethernet0': {'lanes': '0,1,2,3', 'alias': 'etp1', 'index': '1'},
            'Ethernet4': {'lanes': '4,5,6,7', 'alias': 'etp2', 'index': '2'},
            # No 'index' -> skipped (e.g. internal/backplane port).
            'Ethernet-BP0': {'lanes': '9', 'role': 'Int'},
        }
        get_port_config = mock.Mock(return_value=(ports, {}, {}))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            result = tempershow.TemperShow._build_port_index_map()
        assert result == {'Ethernet0': 1, 'Ethernet4': 2}

    def test_multi_asic_merges_all_namespaces(self):
        cfgs = {
            'asic0': {'Ethernet0': {'index': '1'}, 'Ethernet4': {'index': '2'}},
            'asic1': {'Ethernet8': {'index': '1'}, 'Ethernet12': {'index': '2'}},
        }

        def fake_get_port_config(hwsku, platform, asic_name=None):
            return (cfgs.get(asic_name, {}), {}, {})

        p1, p2, p3, p4 = _patch_env(fake_get_port_config, is_multi_asic=True,
                                    num_asics=2)
        with p1, p2, p3, p4:
            result = tempershow.TemperShow._build_port_index_map()
        assert result == {
            'Ethernet0': 1, 'Ethernet4': 2, 'Ethernet8': 1, 'Ethernet12': 2,
        }

    def test_returns_empty_when_portconfig_unavailable(self):
        with mock.patch.object(tempershow, 'get_port_config', None):
            assert tempershow.TemperShow._build_port_index_map() == {}

    def test_get_port_config_failure_is_swallowed(self):
        get_port_config = mock.Mock(side_effect=RuntimeError('no db'))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            assert tempershow.TemperShow._build_port_index_map() == {}

    def test_invalid_index_value_is_skipped(self):
        ports = {'Ethernet0': {'index': '1'}, 'EthernetX': {'index': 'NaN'}}
        get_port_config = mock.Mock(return_value=(ports, {}, {}))
        p1, p2, p3, p4 = _patch_env(get_port_config)
        with p1, p2, p3, p4:
            assert tempershow.TemperShow._build_port_index_map() == {'Ethernet0': 1}


class TestSfpDisplayName:
    @staticmethod
    def _instance(port_index_map):
        # Bypass __init__ so no STATE_DB connection is needed.
        inst = tempershow.TemperShow.__new__(tempershow.TemperShow)
        inst._port_index_map = port_index_map
        return inst

    def test_maps_logical_name_to_legacy_label(self):
        inst = self._instance({'Ethernet0': 1, 'Ethernet8': 3})
        assert inst._sfp_display_name('Ethernet0') == 'xSFP module 1 Temp'
        assert inst._sfp_display_name('Ethernet8') == 'xSFP module 3 Temp'

    def test_unknown_port_falls_back_to_logical_name(self):
        inst = self._instance({'Ethernet0': 1})
        assert inst._sfp_display_name('Ethernet999') == 'Ethernet999'

    def test_empty_map_falls_back_to_logical_name(self):
        inst = self._instance({})
        assert inst._sfp_display_name('Ethernet0') == 'Ethernet0'
