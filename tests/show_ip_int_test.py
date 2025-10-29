import importlib.util
import io
import os
import sys
from unittest import mock

import pytest
from click.testing import CliRunner

import show.main as show
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
    Fast path test fixture - directly imports and tests functions to achieve coverage.
    """
    os.environ["PATH"] += os.pathsep + scripts_path
    os.environ["UTILITIES_UNIT_TESTING"] = "1"
    yield
    os.environ["UTILITIES_UNIT_TESTING"] = "0"


def verify_output(output, expected_output):
    lines = output.splitlines()
    ignored_intfs = ['eth0', 'lo']
    for intf in ignored_intfs:
        # the output should have line to display the ip address of eth0 and lo
        assert len([line for line in lines if line.startswith(intf)]) == 1

    new_output = '\n'.join([line for line in lines if not any(i in line for i in ignored_intfs)])
    print(new_output)
    assert new_output == expected_output


def verify_fastpath_output(output, expected_output):
    lines = output.splitlines()
    ignored_intfs = ['eth0', 'lo']
    for intf in ignored_intfs:
        # the output should have line to display the ip address of eth0 and lo
        assert len([line for line in lines if intf in line]) == 1

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


@pytest.mark.usefixtures('setup_teardown_fastpath')
class TestShowIpIntFastPath(object):
    """
    Test the fast path by directly importing and calling the functions.
    This achieves code coverage of the fast path without subprocess issues.
    """
    # Mock data for IPv4 and IPv6 tests
    IP_ADDR_V4_OUTPUT = """\
1: lo    inet 127.0.0.1/8 scope host lo
2: Ethernet0    inet 20.1.1.1/24 scope global Ethernet0
2: Ethernet0    inet 21.1.1.1/24 scope global Ethernet0
3: PortChannel0001    inet 30.1.1.1/24 scope global PortChannel0001
4: Vlan100    inet 40.1.1.1/24 scope global Vlan100
5: eth0    inet 10.0.0.1/24 scope global eth0
"""
    IP_ADDR_V6_OUTPUT = """\
1: lo    inet6 ::1/128 scope host
2: Ethernet0    inet6 2100::1/64 scope global
2: Ethernet0    inet6 aa00::1/64 scope global
2: Ethernet0    inet6 fe80::64be:a1ff:fe85:c6c4/64 scope link
3: PortChannel0001    inet6 ab00::1/64 scope global
3: PortChannel0001    inet6 fe80::cc8d:60ff:fe08:139f/64 scope link
4: Vlan100    inet6 cc00::1/64 scope global
4: Vlan100    inet6 fe80::c029:3fff:fe41:cf56/64 scope link
5: eth0    inet6 fe80::42:c6ff:fe52:832c/64 scope link
"""
    BGP_NEIGHBORS = {
        '20.1.1.1': {'local_addr': '20.1.1.1', 'neighbor': '20.1.1.5', 'name': 'T2-Peer'},
        '30.1.1.1': {'local_addr': '30.1.1.1', 'neighbor': '30.1.1.5', 'name': 'T0-Peer'}
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_stubs(self):
        """Provide lightweight stubs for external modules if they are absent."""
        import types
        # sonic_py_common.multi_asic stubs
        if 'sonic_py_common' not in sys.modules:
            sonic_py_common = types.ModuleType('sonic_py_common')
            spc_multi_asic = types.ModuleType('multi_asic')
            spc_multi_asic.is_port_internal = lambda iface, ns=None: False
            spc_multi_asic.is_port_channel_internal = lambda iface, ns=None: False
            spc_multi_asic.is_multi_asic = lambda: False
            spc_multi_asic.get_all_namespaces = lambda: {'front_ns': [], 'back_ns': [], 'fabric_ns': []}
            sonic_py_common.multi_asic = spc_multi_asic
            sys.modules['sonic_py_common'] = sonic_py_common
            sys.modules['sonic_py_common.multi_asic'] = spc_multi_asic

        # utilities_common stubs
        if 'utilities_common' not in sys.modules:
            utilities_common = types.ModuleType('utilities_common')
            uc_constants = types.ModuleType('constants')
            uc_constants.DISPLAY_ALL = 'all'
            uc_constants.DISPLAY_EXTERNAL = 'frontend'
            uc_constants.DEFAULT_NAMESPACE = ''
            utilities_common.constants = uc_constants
            uc_general = types.ModuleType('general')
            uc_general.load_db_config = lambda: None
            utilities_common.general = uc_general
            uc_multi_asic = types.ModuleType('multi_asic')

            class _UC_MultiAsic:
                def __init__(self, namespace_option=None, display_option='all', db=None):
                    self.namespace_option = namespace_option
                    self.display_option = display_option
                    self.is_multi_asic = False
                    self.db = db

                def get_ns_list_based_on_options(self):
                    return ['']
            uc_multi_asic.MultiAsic = _UC_MultiAsic
            utilities_common.multi_asic = uc_multi_asic
            sys.modules['utilities_common'] = utilities_common
            sys.modules['utilities_common.constants'] = uc_constants
            sys.modules['utilities_common.general'] = uc_general
            sys.modules['utilities_common.multi_asic'] = uc_multi_asic

        # swsscommon stub
        if 'swsscommon' not in sys.modules:
            swsscommon_root = types.ModuleType('swsscommon')
            swsscommon_inner = types.ModuleType('swsscommon')

            class _StubCfgDB:
                def connect(self): pass
                def get_table(self, name): return {}
            swsscommon_inner.ConfigDBConnector = _StubCfgDB
            swsscommon_root.swsscommon = swsscommon_inner
            sys.modules['swsscommon'] = swsscommon_root
            sys.modules['swsscommon.swsscommon'] = swsscommon_inner

        # netaddr stub
        if 'netaddr' not in sys.modules:
            netaddr_stub = types.ModuleType('netaddr')

            class IPAddress:
                def __init__(self, addr): self.addr = addr
                def netmask_bits(self): return 24
            netaddr_stub.IPAddress = IPAddress
            sys.modules['netaddr'] = netaddr_stub

    def _run_fast_path_test(self, ip_version, ip_addr_output, expected_output):
        """Helper to run fast path test for a given IP version."""
        import netifaces
        from importlib.machinery import SourceFileLoader

        # Import the script as a module
        ipintutil_path = os.path.join(scripts_path, 'ipintutil')
        loader = SourceFileLoader("ipintutil", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        def mock_check_output(cmd, *args, **kwargs):
            if "ip -o addr show" in cmd:
                return ip_addr_output
            return ""

        def mock_popen(cmd, *args, **kwargs):
            mock_proc = mock.MagicMock()
            # Simulate the behavior of reading a sysfs file on Linux.
            # The result is bytes and includes a newline.
            if 'operstate' in cmd[-1]:
                mock_proc.communicate.return_value = (b'up\n', b'')
            elif 'ifconfig' in cmd:
                mock_proc.communicate.return_value = (b'0x1043', b'')
            else:
                mock_proc.communicate.return_value = (b'1', b'')
            mock_proc.wait.return_value = 0
            return mock_proc

        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = self.BGP_NEIGHBORS

        mock_multi_asic_device = mock.MagicMock()
        mock_multi_asic_device.is_multi_asic = False
        mock_multi_asic_device.get_ns_list_based_on_options.return_value = ['']

        with mock.patch('subprocess.check_output', side_effect=mock_check_output), \
             mock.patch('subprocess.Popen', side_effect=mock_popen), \
             mock.patch('swsscommon.swsscommon.ConfigDBConnector', return_value=mock_config_db), \
             mock.patch('utilities_common.general.load_db_config'), \
             mock.patch('utilities_common.multi_asic.MultiAsic', return_value=mock_multi_asic_device), \
             mock.patch('os.path.exists', return_value=True):

            loader.exec_module(ipintutil)

            captured_output = io.StringIO()
            sys.stdout = captured_output

            with mock.patch.object(ipintutil, 'get_if_admin_state', return_value='error'):
                family = netifaces.AF_INET if ip_version == 'ipv4' else netifaces.AF_INET6
                ip_intfs = ipintutil.get_ip_intfs_in_namespace(family, '', 'all')
                ipintutil.display_ip_intfs(ip_intfs, ip_version)

            sys.stdout = sys.__stdout__
            result = captured_output.getvalue()
            print(result)
            verify_fastpath_output(result, expected_output)

    def test_show_ip_intf_v4_fast_path(self):
        self._run_fast_path_test('ipv4', self.IP_ADDR_V4_OUTPUT, show_ipv4_intf_with_multple_ips)

    def test_show_ip_intf_v6_fast_path(self):
        self._run_fast_path_test('ipv6', self.IP_ADDR_V6_OUTPUT, show_ipv6_intf_with_multiple_ips)
