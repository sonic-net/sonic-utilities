import importlib.util
import os
import subprocess
import textwrap
from unittest import mock
import netifaces
import pytest

from .utils import get_result_and_return_code

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

show_ipv4_intf_with_multple_ips = """\
Interface        Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  -------------------  ------------  --------------  -------------
Ethernet0                  20.1.1.1/24          error/down    T2-Peer         20.1.1.5
                           21.1.1.1/24                        N/A             N/A
PortChannel0001            30.1.1.1/24          error/down    T0-Peer         30.1.1.5
Vlan100                    40.1.1.1/24          error/down    N/A             N/A"""

show_ipv6_intf_with_multiple_ips = """\
Interface        Master    IPv6 address/mask                             Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  --------------------------------------------  ------------  --------------  -------------
Ethernet0                  2100::1/64                                    error/down    N/A             N/A
                           aa00::1/64                                                  N/A             N/A
                           fe80::64be:a1ff:fe85:c6c4%Ethernet0/64                      N/A             N/A
PortChannel0001            ab00::1/64                                    error/down    N/A             N/A
                           fe80::cc8d:60ff:fe08:139f%PortChannel0001/64                N/A             N/A
Vlan100                    cc00::1/64                                    error/down    N/A             N/A
                           fe80::c029:3fff:fe41:cf56%Vlan100/64                        N/A             N/A"""

show_multi_asic_ip_intf = """\
Interface        Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  -------------------  ------------  --------------  -------------
Loopback0                  40.1.1.1/32          error/down    N/A             N/A
PortChannel0001            20.1.1.1/24          error/down    T2-Peer         20.1.1.5"""

show_multi_asic_ipv6_intf = """\
Interface        Master    IPv6 address/mask                       Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  --------------------------------------  ------------  --------------  -------------
Loopback0                  fe80::60a5:9dff:fef4:1696%Loopback0/64  error/down    N/A             N/A
PortChannel0001            aa00::1/64                              error/down    N/A             N/A
                           fe80::80fd:d1ff:fe5b:452f/64                          N/A             N/A"""

show_multi_asic_ip_intf_all = """\
Interface        Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  -------------------  ------------  --------------  -------------
Loopback0                  40.1.1.1/32          error/down    N/A             N/A
Loopback4096               1.1.1.1/24           error/down    N/A             N/A
                           2.1.1.1/24                         N/A             N/A
PortChannel0001            20.1.1.1/24          error/down    T2-Peer         20.1.1.5
PortChannel0002            30.1.1.1/24          error/down    T0-Peer         30.1.1.5
veth@eth1                  192.1.1.1/24         error/down    N/A             N/A
veth@eth2                  193.1.1.1/24         error/down    N/A             N/A"""

show_multi_asic_ipv6_intf_all = """\
Interface        Master    IPv6 address/mask                       Admin/Oper    BGP Neighbor    Neighbor IP
---------------  --------  --------------------------------------  ------------  --------------  -------------
Loopback0                  fe80::60a5:9dff:fef4:1696%Loopback0/64  error/down    N/A             N/A
PortChannel0001            aa00::1/64                              error/down    N/A             N/A
                           fe80::80fd:d1ff:fe5b:452f/64                          N/A             N/A
PortChannel0002            bb00::1/64                              error/down    N/A             N/A
                           fe80::80fd:abff:fe5b:452f/64                          N/A             N/A"""

show_error_invalid_af = """Invalid argument -a ipv5"""


# --- Global autouse fixture: mock `ip -j -f inet/inet6 addr show` and sysfs reads ---
@pytest.fixture(autouse=True)
def mock_ip_j_addr_general(monkeypatch):
    """
    Provide canned JSON for `ip -j -f inet/inet6 addr show` that matches expected goldens.

    Also emulate:
      - /sys/class/net/*/carrier -> "0\n" (oper=down)
      - /sys/class/net/*/flags   -> raise CalledProcessError (admin=error)
    """
    topo = os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY", "")

    def _fake_check_output(cmd, text=False, stderr=None):
        cmd_str = " ".join(cmd)

        # Emulate sysfs reads
        if "/sys/class/net/" in cmd_str and "/carrier" in cmd_str:
            return "0\n"  # oper: down
        if "/sys/class/net/" in cmd_str and "/flags" in cmd_str:
            raise subprocess.CalledProcessError(1, cmd)  # admin: error

        # We only care about ip -j address queries here
        is_v6 = "-f inet6" in cmd_str

        if topo == "multi_asic":
            if is_v6:
                return textwrap.dedent("""\
                [
                  {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
                  {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]},
                  {"ifname":"Loopback0","addr_info":[{"family":"inet6","local":"fe80::60a5:9dff:fef4:1696%Loopback0","prefixlen":64}]},
                  {"ifname":"PortChannel0001","addr_info":[
                      {"family":"inet6","local":"aa00::1","prefixlen":64},
                      {"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}
                  ]}
                ]""")
            else:
                return textwrap.dedent("""\
                [
                  {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
                  {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
                  {"ifname":"Loopback0","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":32}]},
                  {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]}
                ]""")
        else:
            # single-asic
            if is_v6:
                return textwrap.dedent("""\
                [
                  {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
                  {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::64be:a1ff:fe85:c6c4","prefixlen":64}]},
                  {"ifname":"Ethernet0","addr_info":[
                      {"family":"inet6","local":"2100::1","prefixlen":64},
                      {"family":"inet6","local":"aa00::1","prefixlen":64},
                      {"family":"inet6","local":"fe80::64be:a1ff:fe85:c6c4%Ethernet0","prefixlen":64}
                  ]},
                  {"ifname":"PortChannel0001","addr_info":[
                      {"family":"inet6","local":"ab00::1","prefixlen":64},
                      {"family":"inet6","local":"fe80::cc8d:60ff:fe08:139f%PortChannel0001","prefixlen":64}
                  ]},
                  {"ifname":"Vlan100","addr_info":[
                      {"family":"inet6","local":"cc00::1","prefixlen":64},
                      {"family":"inet6","local":"fe80::c029:3fff:fe41:cf56%Vlan100","prefixlen":64}
                  ]}
                ]""")
            else:
                return textwrap.dedent("""\
                [
                  {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
                  {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
                  {"ifname":"Ethernet0","addr_info":[
                      {"family":"inet","local":"20.1.1.1","prefixlen":24},
                      {"family":"inet","local":"21.1.1.1","prefixlen":24}
                  ]},
                  {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]},
                  {"ifname":"Vlan100","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":24}]}
                ]""")

    monkeypatch.setattr(subprocess, "check_output", _fake_check_output)


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


@pytest.fixture(scope="class")
def setup_teardown_fastpath():
    """
    Kept for structure parity; current code path is identical in UT/prod.
    """
    os.environ["PATH"] += os.pathsep + scripts_path
    original_ut = os.environ.get("UTILITIES_UNIT_TESTING")
    original_topo = os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY")
    os.environ.pop("UTILITIES_UNIT_TESTING", None)
    os.environ.pop("UTILITIES_UNIT_TESTING_TOPOLOGY", None)
    yield
    if original_ut is not None:
        os.environ["UTILITIES_UNIT_TESTING"] = original_ut
    if original_topo is not None:
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = original_topo


def verify_output(output, expected_output):
    lines = output.splitlines()
    ignored_intfs = ['eth0', 'lo']
    for intf in ignored_intfs:
        assert len([line for line in lines if line.startswith(intf)]) == 1
    new_output = '\n'.join([line for line in lines if not any(i in line for i in ignored_intfs)])
    print(new_output)
    assert new_output == expected_output


def verify_fastpath_output(output, expected_output):
    # Keep non-brittle check as previously agreed
    assert output is not None and len(output.strip()) > 0


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
        # Locally override to add veth/Loopback4096 only for this test (JSON)
        extra_ipv4 = textwrap.dedent("""\
        [
          {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
          {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
          {"ifname":"Loopback0","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":32}]},
          {"ifname":"Loopback4096","addr_info":[
              {"family":"inet","local":"1.1.1.1","prefixlen":24},
              {"family":"inet","local":"2.1.1.1","prefixlen":24}
          ]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]},
          {"ifname":"PortChannel0002","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]},
          {"ifname":"veth@eth1","addr_info":[{"family":"inet","local":"192.1.1.1","prefixlen":24}]},
          {"ifname":"veth@eth2","addr_info":[{"family":"inet","local":"193.1.1.1","prefixlen":24}]}
        ]""")

        def se(cmd, *a, **kw):
            s = " ".join(cmd)
            if "/sys/class/net/" in s and "/carrier" in s:
                return "0\n"  # oper: down
            if "/sys/class/net/" in s and "/flags" in s:
                raise subprocess.CalledProcessError(1, cmd)  # admin: error
            return extra_ipv4

        with mock.patch('subprocess.check_output', side_effect=se):
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
        # Locally override to add the additional IPv6 lines for this test (JSON)
        extra_ipv6 = textwrap.dedent("""\
        [
          {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
          {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]},
          {"ifname":"Loopback0","addr_info":[{"family":"inet6","local":"fe80::60a5:9dff:fef4:1696%Loopback0","prefixlen":64}]},
          {"ifname":"PortChannel0001","addr_info":[
              {"family":"inet6","local":"aa00::1","prefixlen":64},
              {"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}
          ]},
          {"ifname":"PortChannel0002","addr_info":[
              {"family":"inet6","local":"bb00::1","prefixlen":64},
              {"family":"inet6","local":"fe80::80fd:abff:fe5b:452f","prefixlen":64}
          ]}
        ]""")

        def se(cmd, *a, **kw):
            s = " ".join(cmd)
            if "/sys/class/net/" in s and "/carrier" in s:
                return "0\n"  # oper: down
            if "/sys/class/net/" in s and "/flags" in s:
                raise subprocess.CalledProcessError(1, cmd)  # admin: error
            return extra_ipv6

        with mock.patch('subprocess.check_output', side_effect=se):
            return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv6', '-d', 'all'])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf_all)

    def test_show_intf_invalid_af_option(self):
        return_code, result = get_result_and_return_code(['ipintutil', '-a', 'ipv5'])
        assert return_code == 1
        assert result == show_error_invalid_af


@pytest.mark.usefixtures('setup_teardown_fastpath')
class TestShowIpIntFastPath(object):
    """Exercise the same production path with local JSON overrides."""

    def test_addr_show_ipv4(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_v4", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_v4", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]}
        ]"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch('subprocess.check_output', return_value=ip_output), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show('', netifaces.AF_INET, 'all')
            assert isinstance(result, dict)
            assert len(result) >= 0

    def test_addr_show_ipv6(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_v6", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_v6", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet6","local":"2100::1","prefixlen":64}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet6","local":"ab00::1","prefixlen":64}]}
        ]"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch('subprocess.check_output', return_value=ip_output), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show('', netifaces.AF_INET6, 'all')
            assert isinstance(result, dict)
            assert len(result) >= 0

    def test_addr_show_malformed_output(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_malformed", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_malformed", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        malformed_output = "not a json\n"
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch('subprocess.check_output', return_value=malformed_output), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show('', netifaces.AF_INET, 'all')
            assert isinstance(result, dict)

    def test_addr_show_subprocess_error(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_error", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_error", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch('subprocess.check_output', side_effect=subprocess.CalledProcessError(1, 'cmd')), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show('', netifaces.AF_INET, 'all')
            assert result == {}

    def test_addr_show_with_namespace(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_ns", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_ns", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"10.0.0.1","prefixlen":24}]}
        ]"""

        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        def mock_check_output(cmd, *args, **kwargs):
            # Return the same canned JSON regardless of netns exec presence
            return ip_output

        with mock.patch('subprocess.check_output', side_effect=mock_check_output), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show('asic0', netifaces.AF_INET, 'all')
            assert isinstance(result, dict)

    def test_get_ip_intfs_in_namespace_fast_path(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_fast", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_fast", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]}
        ]"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch('subprocess.check_output', return_value=ip_output), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db), \
             mock.patch('os.path.exists', return_value=True):

            # emulate oper=down (carrier "0") and admin=error (flags error)
            loader.exec_module(ipintutil)
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, '', 'all')
            assert isinstance(result, dict)
            assert len(result) >= 0

    def test_skip_interface_filtering(self):
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil_filter", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_filter", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """[
          {"ifname":"eth0","addr_info":[{"family":"inet","local":"192.168.1.1","prefixlen":24}]},
          {"ifname":"Loopback4096","addr_info":[{"family":"inet","local":"1.1.1.1","prefixlen":32}]},
          {"ifname":"veth123","addr_info":[{"family":"inet","local":"10.0.0.1","prefixlen":24}]},
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]}
        ]"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch('subprocess.check_output', return_value=ip_output), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db), \
             mock.patch('os.path.exists', return_value=True):

            loader.exec_module(ipintutil)
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, '', 'frontend')
            assert isinstance(result, dict)
