import os
import pytest
import subprocess
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

import show.main as show
from .utils import get_result_and_return_code

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

show_ipv4_intf_with_multple_ips = """\
Interface        Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  -------------------  ------------  --------------  -------------
Ethernet0                  20.1.1.1/24          up/up         T2-Peer         20.1.1.5
                           21.1.1.1/24                        N/A             N/A
PortChannel0001            30.1.1.1/24          up/up         T0-Peer         30.1.1.5
Vlan100                    40.1.1.1/24          up/up         N/A             N/A"""

show_ipv6_intf_with_multiple_ips = """\
Interface        Master    IPv6 address/mask                             Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  --------------------------------------------  ------------  --------------  -------------
Ethernet0                  2100::1/64                                    up/up         N/A             N/A
                           aa00::1/64                                                  N/A             N/A
                           fe80::64be:a1ff:fe85:c6c4%Ethernet0/64                      N/A             N/A
PortChannel0001            ab00::1/64                                    up/up         N/A             N/A
                           fe80::cc8d:60ff:fe08:139f%PortChannel0001/64                N/A             N/A
Vlan100                    cc00::1/64                                    up/up         N/A             N/A
                           fe80::c029:3fff:fe41:cf56%Vlan100/64                        N/A             N/A"""

show_multi_asic_ip_intf = """\
Interface        Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  -------------------  ------------  --------------  -------------
Loopback0                  40.1.1.1/32          up/up         N/A             N/A
PortChannel0001            20.1.1.1/24          up/up         T2-Peer         20.1.1.5"""

show_multi_asic_ipv6_intf = """\
Interface        Master    IPv6 address/mask                             Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  --------------------------------------------  ------------  --------------  -------------
Loopback0                  fe80::60a5:9dff:fef4:1696%Loopback0/64        up/up         N/A             N/A
PortChannel0001            aa00::1/64                                    up/up         N/A             N/A
                           fe80::80fd:d1ff:fe5b:452f%PortChannel0001/64                N/A             N/A"""

show_multi_asic_ip_intf_all = """\
Interface        Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  -------------------  ------------  --------------  -------------
Loopback0                  40.1.1.1/32          up/up         N/A             N/A
Loopback4096               1.1.1.1/24           up/up         N/A             N/A
                           2.1.1.1/24                         N/A             N/A
PortChannel0001            20.1.1.1/24          up/up         T2-Peer         20.1.1.5
PortChannel0002            30.1.1.1/24          up/up         T0-Peer         30.1.1.5
veth@eth1                  192.1.1.1/24         up/up         N/A             N/A
veth@eth2                  193.1.1.1/24         up/up         N/A             N/A"""

show_multi_asic_ipv6_intf_all = """\
Interface        Master    IPv6 address/mask                             Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  --------------------------------------------  ------------  --------------  -------------
Loopback0                  fe80::60a5:9dff:fef4:1696%Loopback0/64        up/up         N/A             N/A
PortChannel0001            aa00::1/64                                    up/up         N/A             N/A
                           fe80::80fd:d1ff:fe5b:452f%PortChannel0001/64                N/A             N/A
PortChannel0002            bb00::1/64                                    up/up         N/A             N/A
                           fe80::80fd:abff:fe5b:452f%PortChannel0002/64                N/A             N/A"""

show_error_invalid_af = """Invalid argument -a ipv5"""


@pytest.fixture(scope="class")
def setup_teardown_single_asic():
    os.environ["PATH"] += os.pathsep + scripts_path
    os.environ["UTILITIES_UNIT_TESTING"] = "2"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
    yield

    os.environ["UTILITIES_UNIT_TESTING"] = "0"


@pytest.fixture(scope="class")
def setup_teardown_multi_asic():
    os.environ["PATH"] += os.pathsep + scripts_path
    os.environ["UTILITIES_UNIT_TESTING"] = "2"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
    yield
    os.environ["UTILITIES_UNIT_TESTING"] = "0"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""


def verify_output(output, expected_output):
    lines = output.splitlines()
    ignored_intfs = ['eth0', 'lo']
    for intf in ignored_intfs:
        # the output should have line to display the ip address of eth0 and lo
        assert len([line for line in lines if line.startswith(intf)]) == 1

    new_output = '\n'.join([line for line in lines if not any(i in line for i in ignored_intfs)])
    print(new_output)
    assert new_output == expected_output


@pytest.mark.usefixtures('setup_teardown_single_asic')
class TestShowIpInt(object):

    def test_show_ip_intf_v4(self):
        return_code, result = get_result_and_return_code(["ipintutil"])
        assert return_code == 0
        verify_output(result, show_ipv4_intf_with_multple_ips)

    def test_show_ip_intf_v6(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv6'])

        assert return_code == 0
        verify_output(result, show_ipv6_intf_with_multiple_ips)

    def test_show_intf_invalid_af_option(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv5'])
        assert return_code == 1
        assert result == show_error_invalid_af


@pytest.mark.usefixtures('setup_teardown_multi_asic')
class TestMultiAsicShowIpInt(object):

    def test_show_ip_intf_v4(self):
        return_code, result = get_result_and_return_code(["ipintutil"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_asic0(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-n', 'asic0'])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_all(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-d', 'all'])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf_all)

    def test_show_ip_intf_v6(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv6'])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_asic0(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv6', '-n', 'asic0'])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_all(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv6', '-d', 'all'])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf_all)

    def test_show_intf_invalid_af_option(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv5'])
        assert return_code == 1
        assert result == show_error_invalid_af


class TestMultiAsicGetKernelIntfState:
    """
    Unit tests for the real utilities_common.multi_asic.multi_asic_get_kernel_intf_state.

    The integration tests in TestShowIpInt / TestMultiAsicShowIpInt monkey-patch
    this function entirely, so the real pyroute2-based implementation has zero
    coverage without these dedicated tests.  pyroute2.IPRoute (and the netns
    helpers) are mocked so no kernel privileges are required.
    """

    @staticmethod
    def _make_link(idx, name, flags, master=None, operstate="UP"):
        link = MagicMock()
        link.__getitem__ = MagicMock(
            side_effect={"index": idx, "flags": flags}.__getitem__)
        link.get_attr.side_effect = {
            "IFLA_IFNAME": name,
            "IFLA_MASTER": master,
            "IFLA_OPERSTATE": operstate,
        }.get
        return link

    @staticmethod
    def _make_addr(idx, local, prefixlen, address=None):
        addr = MagicMock()
        addr.__getitem__ = MagicMock(
            side_effect={"index": idx, "prefixlen": prefixlen}.__getitem__)
        addr.get_attr.side_effect = {
            "IFA_LOCAL": local,
            "IFA_ADDRESS": address if address is not None else local,
        }.get
        return addr

    @staticmethod
    def _ipr_class(links, addrs):
        """Return a mock IPRoute *class* whose instances yield the given data."""
        inst = MagicMock()
        inst.__enter__.return_value = inst
        inst.get_links.return_value = links
        inst.get_addr.return_value = addrs
        return MagicMock(return_value=inst)

    def test_default_namespace_ipv4(self):
        """Happy path: IPv4, default namespace -- links and addrs parsed correctly."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        ipr_cls = self._ipr_class(
            [self._make_link(1, "Ethernet0", 0x1043)],
            [self._make_addr(1, "10.0.0.1", 24)],
        )
        with patch("pyroute2.IPRoute", ipr_cls):
            links, addrs = multi_asic_get_kernel_intf_state("", netifaces.AF_INET)

        assert links == [{"index": 1, "name": "Ethernet0", "flags": 0x1043,
                          "master_idx": None, "operstate": "UP"}]
        assert addrs == [{"index": 1, "addr": "10.0.0.1", "prefixlen": 24}]

    def test_default_namespace_ipv6(self):
        """Happy path: IPv6, default namespace."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        ipr_cls = self._ipr_class(
            [self._make_link(1, "Ethernet0", 0x1043)],
            [self._make_addr(1, "2001:db8::1", 64)],
        )
        with patch("pyroute2.IPRoute", ipr_cls):
            links, addrs = multi_asic_get_kernel_intf_state("", netifaces.AF_INET6)

        assert len(links) == 1
        assert links[0]["name"] == "Ethernet0"
        assert addrs == [{"index": 1, "addr": "2001:db8::1", "prefixlen": 64}]

    def test_non_default_namespace_pushes_and_pops(self):
        """Non-default namespace: pushns before IPRoute open, popns in finally."""
        import netifaces
        import pyroute2
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        ipr_cls = self._ipr_class([], [])
        with patch("pyroute2.IPRoute", ipr_cls), \
             patch.object(pyroute2.netns, "pushns") as mock_push, \
             patch.object(pyroute2.netns, "popns") as mock_pop:
            multi_asic_get_kernel_intf_state("asic0", netifaces.AF_INET)

        mock_push.assert_called_once_with("asic0")
        mock_pop.assert_called_once()

    def test_link_missing_ifname_is_skipped(self):
        """Links where IFLA_IFNAME is None are silently ignored."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        bad_link = MagicMock()
        bad_link.__getitem__ = MagicMock(side_effect={"index": 1, "flags": 0}.get)
        bad_link.get_attr.return_value = None  # IFLA_IFNAME -> None

        ipr_cls = self._ipr_class([bad_link], [])
        with patch("pyroute2.IPRoute", ipr_cls):
            links, _ = multi_asic_get_kernel_intf_state("", netifaces.AF_INET)

        assert links == []

    def test_link_missing_operstate_defaults_to_unknown(self):
        """IFLA_OPERSTATE None -> operstate stored as 'UNKNOWN'."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        link = MagicMock()
        link.__getitem__ = MagicMock(side_effect={"index": 1, "flags": 0x1}.get)
        link.get_attr.side_effect = {
            "IFLA_IFNAME": "lo",
            "IFLA_MASTER": None,
            "IFLA_OPERSTATE": None,
        }.get

        ipr_cls = self._ipr_class([link], [])
        with patch("pyroute2.IPRoute", ipr_cls):
            links, _ = multi_asic_get_kernel_intf_state("", netifaces.AF_INET)

        assert links[0]["operstate"] == "UNKNOWN"

    def test_link_with_master_index(self):
        """IFLA_MASTER is stored as master_idx."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        ipr_cls = self._ipr_class(
            [self._make_link(2, "Ethernet0", 0x1043, master=10)], [])
        with patch("pyroute2.IPRoute", ipr_cls):
            links, _ = multi_asic_get_kernel_intf_state("", netifaces.AF_INET)

        assert links[0]["master_idx"] == 10

    def test_addr_falls_back_to_ifa_address(self):
        """When IFA_LOCAL is None the address is taken from IFA_ADDRESS."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        ipr_cls = self._ipr_class(
            [self._make_link(1, "lo", 0x1)],
            [self._make_addr(1, None, 32, address="127.0.0.1")],
        )
        with patch("pyroute2.IPRoute", ipr_cls):
            _, addrs = multi_asic_get_kernel_intf_state("", netifaces.AF_INET)

        assert addrs == [{"index": 1, "addr": "127.0.0.1", "prefixlen": 32}]

    def test_addr_with_no_ip_is_skipped(self):
        """Entries where both IFA_LOCAL and IFA_ADDRESS are None are dropped."""
        import netifaces
        from utilities_common.multi_asic import multi_asic_get_kernel_intf_state

        bad_addr = MagicMock()
        bad_addr.__getitem__ = MagicMock(
            side_effect={"index": 1, "prefixlen": 0}.get)
        bad_addr.get_attr.return_value = None  # IFA_LOCAL and IFA_ADDRESS -> None

        ipr_cls = self._ipr_class([self._make_link(1, "lo", 0x1)], [bad_addr])
        with patch("pyroute2.IPRoute", ipr_cls):
            _, addrs = multi_asic_get_kernel_intf_state("", netifaces.AF_INET)

        assert addrs == []
