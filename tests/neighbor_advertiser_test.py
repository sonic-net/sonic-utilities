import os
import subprocess
import sys
from unittest import mock

import pytest
from swsscommon.swsscommon import ConfigDBConnector
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

# Load the file under test
neighbor_advertiser_path = os.path.join(scripts_path, 'neighbor_advertiser')
neighbor_advertiser = load_module_from_source('neighbor_advertiser', neighbor_advertiser_path)


class TestNeighborAdvertiser(object):
    @pytest.fixture
    def set_up(self):
        neighbor_advertiser.connect_config_db()
        neighbor_advertiser.connect_app_db()

    def test_neighbor_advertiser_slice(self, set_up):
        neighbor_advertiser.get_link_local_addr = mock.MagicMock(return_value='fe80::1e34:daff:fe1e:2800')
        output = neighbor_advertiser.construct_neighbor_advertiser_slice()
        expected_output = dict(
            {
                'respondingSchemes': {'durationInSec': 300},
                'switchInfo': {'ipv6Addr': '', 'hwSku': 'Mellanox-SN3800-D112C8', 'ipv4Addr': '', 'name': 'sonic-switch'},
                'vlanInterfaces': [{
                        'ipv4AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': '192.168.0.1', 'ipPrefixLen': '32'}
                        ],
                        'ipv6AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fc02:1000::1', 'ipPrefixLen': '128'},
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fe80::1e34:daff:fe1e:2800', 'ipPrefixLen': '128'}
                        ],
                        'vxlanId': '1000',
                        'vlanId': '1000',
                        'vxlanPort': '13550'
                    },
                    {
                        'ipv4AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': '192.168.0.10', 'ipPrefixLen': '21'}
                        ],
                        'ipv6AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fc02:1011::1', 'ipPrefixLen': '64'},
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fe80::1e34:daff:fe1e:2800', 'ipPrefixLen': '128'}
                        ],
                        'vxlanId': '2000',
                        'vlanId': '2000',
                        'vxlanPort': '13550'
                    }]
            }
        )
        assert output == expected_output

    def test_set_vxlan(self, set_up):
        assert(neighbor_advertiser.check_existing_tunnel())
        neighbor_advertiser.add_vxlan_tunnel_map()
        tunnel_mapping = neighbor_advertiser.config_db.get_table('VXLAN_TUNNEL_MAP')
        expected_mapping = {("vtep1", "map_1"): {"vni": "1000", "vlan": "Vlan1000"}, ("vtep1", "map_2"): {"vni": "2000", "vlan": "Vlan2000"}}
        for key in expected_mapping.keys():
            assert(key in tunnel_mapping.keys())
            assert(expected_mapping[key] == tunnel_mapping[key])

    def test_add_vxlan_tunnel_sets_pipe_ttl_mode(self):
        config_db = mock.MagicMock()
        with mock.patch.object(neighbor_advertiser, 'get_loopback_addr', return_value='10.0.0.1'), \
                mock.patch.object(neighbor_advertiser, 'config_db', config_db):
            neighbor_advertiser.add_vxlan_tunnel('10.0.0.2')

        config_db.set_entry.assert_called_once_with(
            'VXLAN_TUNNEL',
            neighbor_advertiser.VXLAN_TUNNEL_NAME,
            {
                'src_ip': '10.0.0.1',
                'dst_ip': '10.0.0.2',
                'ttl_mode': 'pipe'
            }
        )

    def test_reset_skips_when_mirror_session_missing(self):
        config_db = mock.MagicMock()
        config_db.get_entry.return_value = {}
        with mock.patch.object(sys, 'argv', ['neighbor_advertiser', '-m', 'reset']), \
                mock.patch.object(neighbor_advertiser, 'connect_config_db'), \
                mock.patch.object(neighbor_advertiser, 'connect_app_db'), \
                mock.patch.object(neighbor_advertiser, 'config_db', config_db), \
                mock.patch.object(neighbor_advertiser.log, 'log_info') as mock_log_info, \
                mock.patch.object(neighbor_advertiser, 'reset_mirror_tunnel') as mock_reset_mirror, \
                mock.patch.object(neighbor_advertiser, 'reset_vxlan_tunnel') as mock_reset_vxlan:
            with pytest.raises(SystemExit) as exc_info:
                neighbor_advertiser.main()

        assert exc_info.value.code == 0
        config_db.get_entry.assert_called_once_with('MIRROR_SESSION', neighbor_advertiser.MIRROR_SESSION_NAME)
        mock_log_info.assert_called_once_with(
            'Mirror session {} does not exist, skipping reset'.format(neighbor_advertiser.MIRROR_SESSION_NAME)
        )
        mock_reset_mirror.assert_not_called()
        mock_reset_vxlan.assert_not_called()

    def test_reset_runs_when_mirror_session_exists(self):
        config_db = mock.MagicMock()
        config_db.get_entry.return_value = {'dst_ip': '10.1.1.2'}
        call_order = mock.Mock()
        with mock.patch.object(sys, 'argv', ['neighbor_advertiser', '-m', 'reset']), \
                mock.patch.object(neighbor_advertiser, 'connect_config_db'), \
                mock.patch.object(neighbor_advertiser, 'connect_app_db'), \
                mock.patch.object(neighbor_advertiser, 'config_db', config_db), \
                mock.patch.object(neighbor_advertiser, 'reset_mirror_tunnel', call_order.reset_mirror_tunnel), \
                mock.patch.object(neighbor_advertiser, 'reset_vxlan_tunnel', call_order.reset_vxlan_tunnel):
            with pytest.raises(SystemExit) as exc_info:
                neighbor_advertiser.main()

        assert exc_info.value.code == 0
        config_db.get_entry.assert_called_once_with('MIRROR_SESSION', neighbor_advertiser.MIRROR_SESSION_NAME)
        assert call_order.mock_calls == [
            mock.call.reset_mirror_tunnel(),
            mock.call.reset_vxlan_tunnel(),
        ]
