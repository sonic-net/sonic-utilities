# MONKEY PATCH!!!
from unittest import mock

from sonic_py_common import multi_asic
from utilities_common import multi_asic as multi_asic_util

add_unknown_intf=False

mock_intf_table = {
    '': {
        'eth0': {
            2: [{'addr': '10.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '10.1.1.1'}],
            10: [{'addr': '3100::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]
        },
        'Ethernet0': {
            17: [{'addr': '82:fd:d1:5b:45:2f', 'broadcast': 'ff:ff:ff:ff:ff:ff'}],
            2: [
                    {'addr': '20.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '20.1.1.1'},
                    {'addr': '21.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '21.1.1.1'}
                ],
            10: [
                    {'addr': 'aa00::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'},
                    {'addr': '2100::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'},
                    {'addr': 'fe80::64be:a1ff:fe85:c6c4%Ethernet0', 'netmask': 'ffff:ffff:ffff:ffff::/64'}
                ]
        },
        'PortChannel0001': {
            17: [{'addr': '82:fd:d1:5b:45:2f', 'broadcast': 'ff:ff:ff:ff:ff:ff'}], 
            2: [{'addr': '30.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '30.1.1.1'}],
            10: [
                    {'addr': 'ab00::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'},
                    {'addr': 'fe80::cc8d:60ff:fe08:139f%PortChannel0001', 'netmask': 'ffff:ffff:ffff:ffff::/64'}
                ]
        },
        'Vlan100': {
            17: [{'addr': '82:fd:d1:5b:45:2f', 'broadcast': 'ff:ff:ff:ff:ff:ff'}], 
            2: [{'addr': '40.1.1.1', 'netmask': '255.255.255.0', 'broadcast': '30.1.1.1'}],
            10: [
                    {'addr': 'cc00::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'},
                    {'addr': 'fe80::c029:3fff:fe41:cf56%Vlan100', 'netmask': 'ffff:ffff:ffff:ffff::/64'}
                ]
        },
        'lo': {
            2: [{'addr': '127.0.0.1', 'netmask': '255.0.0.0', 'broadcast': '127.255.255.255'}],
            10: [{'addr': '::1', 'netmask':'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128'}]
        }
    }
}


def mock_get_num_asics():
    return 1

def mock_is_multi_asic():
    return False

def mock_get_namespace_list(namespace=None):
    return ['']


def mock_single_asic_get_ip_intf_from_ns(namespace):
    interfaces = []
    try:
        interfaces = list(mock_intf_table[namespace].keys())
        if add_unknown_intf:
            interfaces.append("unknownintf")
    except KeyError:
        pass
    return interfaces


def mock_single_asic_get_ip_intf_addr_from_ns(namespace, iface):
    ipaddresses = []
    try:
        ipaddresses = mock_intf_table[namespace][iface]
    except KeyError:
        if add_unknown_intf:
            raise ValueError("Unknow interface")
    return ipaddresses


def _mock_netmask_to_prefixlen(netmask):
    """
    Convert a netmask string from mock_intf_table into a prefix length.

    Accepts either dotted-decimal (IPv4, e.g. '255.255.255.0') or the
    'mask/len' form historically produced by netifaces for IPv6
    (e.g. 'ffff:ffff:ffff:ffff::/64').
    """
    if '/' in netmask:
        return int(netmask.split('/', 1)[-1])
    import netaddr
    return netaddr.IPAddress(netmask).netmask_bits()


def mock_single_asic_get_kernel_intf_state(namespace, af):
    """
    Synthesize the (links, addrs) tuple that the production helper
    ``multi_asic_get_kernel_intf_state`` returns by walking
    ``mock_intf_table``.  Interfaces are reported as admin-up / oper-up
    so the tests can exercise the rendered output without a real kernel.
    """
    table = mock_intf_table.get(namespace, {})
    links = []
    addrs = []
    # Stable, deterministic ifindex assignment for the mock so master_idx
    # could be resolved if a test ever sets one.
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
    return {'front_ns': [], 'back_ns': [], 'fabric_ns': []}


multi_asic.is_multi_asic = mock_is_multi_asic
multi_asic.get_num_asics = mock_get_num_asics
multi_asic.get_namespace_list = mock_get_namespace_list
multi_asic.get_all_namespaces = mock_get_all_namespaces
multi_asic.get_namespaces_from_linux = mock_get_namespace_list
multi_asic_util.multi_asic_get_ip_intf_from_ns = mock_single_asic_get_ip_intf_from_ns
multi_asic_util.multi_asic_get_ip_intf_addr_from_ns = mock_single_asic_get_ip_intf_addr_from_ns
multi_asic_util.multi_asic_get_kernel_intf_state = mock_single_asic_get_kernel_intf_state
multi_asic_util.multi_asic_get_ip_intf_addr_from_ns = mock_single_asic_get_ip_intf_addr_from_ns