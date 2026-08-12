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


def _mock_netmask_to_prefixlen(netmask):
    """
    Convert a netmask string from mock_intf_table into a prefix length.
    Accepts dotted-decimal IPv4 or 'mask/len' IPv6 forms.
    """
    if '/' in netmask:
        return int(netmask.split('/', 1)[-1])
    import netaddr
    return netaddr.IPAddress(netmask).netmask_bits()


def mock_multi_asic_get_kernel_intf_state(namespace, af):
    """
    Synthesize the (links, addrs) tuple that the production helper
    ``multi_asic_get_kernel_intf_state`` returns by walking
    ``mock_intf_table`` for the given namespace.
    """
    table = mock_intf_table.get(namespace, {})
    links = []
    addrs = []
    for idx, iface in enumerate(table.keys(), start=1):
        links.append({
            'index': idx,
            'name': iface,
            # IFF_UP | IFF_BROADCAST | IFF_RUNNING — admin will be 'up'.
            'flags': 0x1043,
            'master_idx': None,
            'operstate': 'UP',
        })
        for fam_key, entries in table[iface].items():
            if fam_key != af:
                continue
            for entry in entries:
                ip_str = entry.get('addr', '')
                # Strip the %iface zone id from link-local IPv6 addresses
                # in the mock data — production netlink never includes it
                # and ipintutil re-appends it when rendering.
                if '%' in ip_str:
                    ip_str = ip_str.split('%', 1)[0]
                netmask = entry.get('netmask', '')
                try:
                    prefixlen = _mock_netmask_to_prefixlen(netmask)
                except (OSError, ValueError):
                    continue
                addrs.append({
                    'index': idx,
                    'addr': ip_str,
                    'prefixlen': prefixlen,
                })
    return links, addrs


def mock_get_all_namespaces():
    return {'front_ns': ['asic0'], 'back_ns': ['asic1'], 'fabric_ns': []}


multi_asic.get_num_asics = mock_get_num_asics
multi_asic.is_multi_asic = mock_is_multi_asic
multi_asic.get_namespace_list = mock_get_namespace_list
multi_asic.get_all_namespaces = mock_get_all_namespaces
multi_asic.get_namespaces_from_linux = mock_get_namespace_list
multi_asic_util.multi_asic_get_ip_intf_from_ns = mock_multi_asic_get_ip_intf_from_ns
multi_asic_util.multi_asic_get_ip_intf_addr_from_ns = mock_multi_asic_get_ip_intf_addr_from_ns
multi_asic_util.multi_asic_get_kernel_intf_state = mock_multi_asic_get_kernel_intf_state
