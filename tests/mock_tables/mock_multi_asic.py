# MONKEY PATCH!!!
from unittest import mock

from sonic_py_common import multi_asic
from utilities_common import multi_asic as multi_asic_util

mock_intf_table = {
    '': {
        'eth0': {
            2: [{'addr': '10.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '10.1.1.1'}],
            10: [{'addr': '3100::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]
        },
        'lo': {
            2: [{'addr': '127.0.0.1', 'netmask': '255.0.0.0', 'broadcast': '127.255.255.255'}],
            10: [{'addr': '::1', 'netmask':'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128'}]
        }
    },
    'asic0': {
        'Loopback0': {
            17: [{'addr': '62:a5:9d:f4:16:96', 'broadcast': 'ff:ff:ff:ff:ff:ff'}], 
            2: [{'addr': '40.1.1.1', 'netmask': '255.255.255.255', 'broadcast': '40.1.1.1'}], 
            10: [{'addr': 'fe80::60a5:9dff:fef4:1696%Loopback0', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]
        },
        'PortChannel0001': {
            17: [{'addr': '82:fd:d1:5b:45:2f', 'broadcast': 'ff:ff:ff:ff:ff:ff'}], 
            2: [{'addr': '20.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '20.1.1.1'}], 
            10: [{'addr': 'aa00::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'}, {'addr': 'fe80::80fd:d1ff:fe5b:452f', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]
        },
        'Loopback4096': {
            2: [{'addr': '1.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '1.1.1.1'}]
        },
        'veth@eth1': {
            2: [{'addr': '192.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '192.1.1.1'}]
        }
    },
    'asic1': {
        'Loopback0': {
            17: [{'addr': '62:a5:9d:f4:16:96', 'broadcast': 'ff:ff:ff:ff:ff:ff'}], 
            2: [{'addr': '40.1.1.1', 'netmask': '255.255.255.255', 'broadcast': '40.1.1.1'}], 
            10: [{'addr': 'fe80::60a5:9dff:fef4:1696%Loopback0', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]
        },
        'PortChannel0002': {
            17: [{'addr': '82:fd:d1:5b:45:2f', 'broadcast': 'ff:ff:ff:ff:ff:ff'}], 
            2: [{'addr': '30.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '30.1.1.1'}], 
            10: [{'addr': 'bb00::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'}, {'addr': 'fe80::80fd:abff:fe5b:452f', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]
        },
        'Loopback4096': {
            2: [{'addr': '2.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '2.1.1.1'}]
        },
        'veth@eth2': {
            2: [{'addr': '193.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '193.1.1.1'}]
        }
    }
}


def mock_get_num_asics():
    return 2


def mock_is_multi_asic():
    return True


def mock_get_namespace_list(namespace=None):
    if namespace:
        return [namespace]
    return ['asic0', 'asic1']


def mock_multi_asic_get_ip_intf_from_ns(namespace):
    interfaces = []
    try:
        interfaces = list(mock_intf_table[namespace].keys())
    except KeyError:
        pass
    return interfaces


def mock_multi_asic_get_ip_intf_addr_from_ns(namespace, iface):
    ipaddresses = []
    try:
        ipaddresses = mock_intf_table[namespace][iface]
    except KeyError:
        pass
    return ipaddresses


multi_asic.get_num_asics = mock_get_num_asics
multi_asic.is_multi_asic = mock_is_multi_asic
multi_asic.get_namespace_list = mock_get_namespace_list
multi_asic.get_namespaces_from_linux = mock_get_namespace_list
multi_asic_util.multi_asic_get_ip_intf_from_ns = mock_multi_asic_get_ip_intf_from_ns
multi_asic_util.multi_asic_get_ip_intf_addr_from_ns = mock_multi_asic_get_ip_intf_addr_from_ns
