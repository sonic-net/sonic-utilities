import importlib.util
import json
import os
import shlex
import subprocess
from importlib.machinery import SourceFileLoader
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


def _tokenize(cmd):
    if isinstance(cmd, (list, tuple)):
        return list(cmd)
    return shlex.split(cmd if isinstance(cmd, str) else str(cmd))


def _is_ip_json_addr_show(tokens):
    if not tokens:
        return False

    try:
        ip_idx = max(i for i, token in enumerate(tokens) if token == "ip" or token.endswith("/ip"))
    except ValueError:
        return False

    window = tokens[ip_idx:]
    return "-j" in window and "show" in window and any(token in window for token in ("addr", "address"))


def _detect_family(tokens):
    if "-6" in tokens or "inet6" in " ".join(tokens):
        return "v6"
    return "v4"


def _load_ipintutil_module(module_name):
    ipintutil_path = os.path.join(scripts_path, "ipintutil")
    loader = SourceFileLoader(module_name, ipintutil_path)
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def mock_ip_and_sysfs(monkeypatch):
    topo = os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY", "")

    single_v4 = [
        {
            "ifname": "lo",
            "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}],
        },
        {
            "ifname": "eth0",
            "addr_info": [{"family": "inet", "local": "172.18.0.2", "prefixlen": 16}],
        },
        {
            "ifname": "Ethernet0",
            "addr_info": [
                {"family": "inet", "local": "20.1.1.1", "prefixlen": 24},
                {"family": "inet", "local": "21.1.1.1", "prefixlen": 24},
            ],
        },
        {
            "ifname": "PortChannel0001",
            "addr_info": [{"family": "inet", "local": "30.1.1.1", "prefixlen": 24}],
        },
        {
            "ifname": "Vlan100",
            "addr_info": [{"family": "inet", "local": "40.1.1.1", "prefixlen": 24}],
        },
    ]

    single_v6 = [
        {
            "ifname": "lo",
            "addr_info": [{"family": "inet6", "local": "::1", "prefixlen": 128}],
        },
        {
            "ifname": "eth0",
            "addr_info": [
                {
                    "family": "inet6",
                    "local": "fe80::64be:a1ff:fe85:c6c4",
                    "prefixlen": 64,
                }
            ],
        },
        {
            "ifname": "Ethernet0",
            "addr_info": [
                {"family": "inet6", "local": "2100::1", "prefixlen": 64},
                {"family": "inet6", "local": "aa00::1", "prefixlen": 64},
                {
                    "family": "inet6",
                    "local": "fe80::64be:a1ff:fe85:c6c4%Ethernet0",
                    "prefixlen": 64,
                },
            ],
        },
        {
            "ifname": "PortChannel0001",
            "addr_info": [
                {"family": "inet6", "local": "ab00::1", "prefixlen": 64},
                {
                    "family": "inet6",
                    "local": "fe80::cc8d:60ff:fe08:139f%PortChannel0001",
                    "prefixlen": 64,
                },
            ],
        },
        {
            "ifname": "Vlan100",
            "addr_info": [
                {"family": "inet6", "local": "cc00::1", "prefixlen": 64},
                {
                    "family": "inet6",
                    "local": "fe80::c029:3fff:fe41:cf56%Vlan100",
                    "prefixlen": 64,
                },
            ],
        },
    ]

    multi_v4 = [
        {
            "ifname": "lo",
            "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}],
        },
        {
            "ifname": "eth0",
            "addr_info": [{"family": "inet", "local": "172.18.0.2", "prefixlen": 16}],
        },
        {
            "ifname": "Loopback0",
            "addr_info": [{"family": "inet", "local": "40.1.1.1", "prefixlen": 32}],
        },
        {
            "ifname": "PortChannel0001",
            "addr_info": [{"family": "inet", "local": "20.1.1.1", "prefixlen": 24}],
        },
    ]

    multi_v6 = [
        {
            "ifname": "lo",
            "addr_info": [{"family": "inet6", "local": "::1", "prefixlen": 128}],
        },
        {
            "ifname": "eth0",
            "addr_info": [
                {
                    "family": "inet6",
                    "local": "fe80::80fd:d1ff:fe5b:452f",
                    "prefixlen": 64,
                }
            ],
        },
        {
            "ifname": "Loopback0",
            "addr_info": [
                {
                    "family": "inet6",
                    "local": "fe80::60a5:9dff:fef4:1696%Loopback0",
                    "prefixlen": 64,
                }
            ],
        },
        {
            "ifname": "PortChannel0001",
            "addr_info": [
                {"family": "inet6", "local": "aa00::1", "prefixlen": 64},
                {
                    "family": "inet6",
                    "local": "fe80::80fd:d1ff:fe5b:452f",
                    "prefixlen": 64,
                },
            ],
        },
    ]

    real_check_output = subprocess.check_output

    def fake_check_output(cmd, *args, **kwargs):
        tokens = _tokenize(cmd)

        if _is_ip_json_addr_show(tokens):
            family = _detect_family(tokens)
            if topo == "multi_asic":
                return json.dumps(multi_v6 if family == "v6" else multi_v4)
            return json.dumps(single_v6 if family == "v6" else single_v4)

        return real_check_output(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)


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


def _iface_name_from_table_line(line):
    if not line.strip():
        return None
    if line.startswith("Interface ") or set(line.strip()) == {"-"}:
        return None

    parts = [part for part in line.split("  ") if part != ""]
    return parts[0].strip() if parts else None


def verify_output(output, expected_output):
    lines = output.splitlines()

    lo_hits = [line for line in lines if _iface_name_from_table_line(line) == "lo"]
    assert len(lo_hits) == 1

    eth0_hits = [line for line in lines if _iface_name_from_table_line(line) == "eth0"]
    assert len(eth0_hits) in (0, 1)

    filtered = []
    for line in lines:
        name = _iface_name_from_table_line(line)
        if name in ("eth0", "lo"):
            continue
        filtered.append(line)

    new_output = "\n".join(filtered).strip()
    assert new_output == expected_output


@pytest.mark.usefixtures("setup_teardown_single_asic")
class TestShowIpInt:
    def test_show_ip_intf_v4(self):
        return_code, result = get_result_and_return_code(["ipintutil"])
        assert return_code == 0
        verify_output(result, show_ipv4_intf_with_multple_ips)

    def test_show_ip_intf_v6(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-a", "ipv6"])
        assert return_code == 0
        verify_output(result, show_ipv6_intf_with_multiple_ips)

    def test_show_intf_invalid_af_option(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-a", "ipv5"])
        assert return_code == 1
        assert result == show_error_invalid_af


@pytest.mark.usefixtures("setup_teardown_multi_asic")
class TestMultiAsicShowIpInt:
    def test_show_ip_intf_v4(self):
        return_code, result = get_result_and_return_code(["ipintutil"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_asic0(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-n", "asic0"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_all(self):
        extra_ipv4 = json.dumps(
            [
                {
                    "ifname": "lo",
                    "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}],
                },
                {
                    "ifname": "eth0",
                    "addr_info": [{"family": "inet", "local": "172.18.0.2", "prefixlen": 16}],
                },
                {
                    "ifname": "Loopback0",
                    "addr_info": [{"family": "inet", "local": "40.1.1.1", "prefixlen": 32}],
                },
                {
                    "ifname": "Loopback4096",
                    "addr_info": [
                        {"family": "inet", "local": "1.1.1.1", "prefixlen": 24},
                        {"family": "inet", "local": "2.1.1.1", "prefixlen": 24},
                    ],
                },
                {
                    "ifname": "PortChannel0001",
                    "addr_info": [{"family": "inet", "local": "20.1.1.1", "prefixlen": 24}],
                },
                {
                    "ifname": "PortChannel0002",
                    "addr_info": [{"family": "inet", "local": "30.1.1.1", "prefixlen": 24}],
                },
                {
                    "ifname": "veth@eth1",
                    "addr_info": [{"family": "inet", "local": "192.1.1.1", "prefixlen": 24}],
                },
                {
                    "ifname": "veth@eth2",
                    "addr_info": [{"family": "inet", "local": "193.1.1.1", "prefixlen": 24}],
                },
            ]
        )

        real_check_output = subprocess.check_output

        def side_effect(cmd, *args, **kwargs):
            tokens = _tokenize(cmd)
            if _is_ip_json_addr_show(tokens):
                return extra_ipv4
            return real_check_output(cmd, *args, **kwargs)

        with mock.patch("subprocess.check_output", side_effect=side_effect):
            return_code, result = get_result_and_return_code(["ipintutil", "-d", "all"])

        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf_all)

    def test_show_ip_intf_v6(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-a", "ipv6"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_asic0(self):
        return_code, result = get_result_and_return_code(
            ["ipintutil", "-a", "ipv6", "-n", "asic0"]
        )
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_all(self):
        extra_ipv6 = json.dumps(
            [
                {
                    "ifname": "lo",
                    "addr_info": [{"family": "inet6", "local": "::1", "prefixlen": 128}],
                },
                {
                    "ifname": "eth0",
                    "addr_info": [
                        {
                            "family": "inet6",
                            "local": "fe80::80fd:d1ff:fe5b:452f",
                            "prefixlen": 64,
                        }
                    ],
                },
                {
                    "ifname": "Loopback0",
                    "addr_info": [
                        {
                            "family": "inet6",
                            "local": "fe80::60a5:9dff:fef4:1696%Loopback0",
                            "prefixlen": 64,
                        }
                    ],
                },
                {
                    "ifname": "PortChannel0001",
                    "addr_info": [
                        {"family": "inet6", "local": "aa00::1", "prefixlen": 64},
                        {
                            "family": "inet6",
                            "local": "fe80::80fd:d1ff:fe5b:452f",
                            "prefixlen": 64,
                        },
                    ],
                },
                {
                    "ifname": "PortChannel0002",
                    "addr_info": [
                        {"family": "inet6", "local": "bb00::1", "prefixlen": 64},
                        {
                            "family": "inet6",
                            "local": "fe80::80fd:abff:fe5b:452f",
                            "prefixlen": 64,
                        },
                    ],
                },
            ]
        )

        real_check_output = subprocess.check_output

        def side_effect(cmd, *args, **kwargs):
            tokens = _tokenize(cmd)
            if _is_ip_json_addr_show(tokens):
                return extra_ipv6
            return real_check_output(cmd, *args, **kwargs)

        with mock.patch("subprocess.check_output", side_effect=side_effect):
            return_code, result = get_result_and_return_code(
                ["ipintutil", "-a", "ipv6", "-d", "all"]
            )

        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf_all)


@pytest.mark.usefixtures("setup_teardown_fastpath")
class TestShowIpIntFastPath:
    def test_addr_show_ipv4(self):
        ipintutil = _load_ipintutil_module("ipintutil_v4")

        ip_output = json.dumps(
            [
                {
                    "ifname": "Ethernet0",
                    "addr_info": [{"family": "inet", "local": "20.1.1.1", "prefixlen": 24}],
                },
                {
                    "ifname": "PortChannel0001",
                    "addr_info": [{"family": "inet", "local": "30.1.1.1", "prefixlen": 24}],
                },
            ]
        )
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db
        ):
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_ipv6(self):
        ipintutil = _load_ipintutil_module("ipintutil_v6")

        ip_output = json.dumps(
            [
                {
                    "ifname": "Ethernet0",
                    "addr_info": [{"family": "inet6", "local": "2100::1", "prefixlen": 64}],
                },
                {
                    "ifname": "PortChannel0001",
                    "addr_info": [{"family": "inet6", "local": "ab00::1", "prefixlen": 64}],
                },
            ]
        )
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db
        ):
            result = ipintutil._addr_show("", netifaces.AF_INET6, "all")
            assert isinstance(result, dict)

    def test_addr_show_malformed_output(self):
        ipintutil = _load_ipintutil_module("ipintutil_malformed")

        malformed_output = "not a json\n"
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=malformed_output), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db
        ):
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_subprocess_error(self):
        ipintutil = _load_ipintutil_module("ipintutil_error")

        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        ), mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db):
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert result == {}

    def test_addr_show_with_namespace(self):
        ipintutil = _load_ipintutil_module("ipintutil_ns")

        ip_output = json.dumps(
            [
                {
                    "ifname": "Ethernet0",
                    "addr_info": [{"family": "inet", "local": "10.0.0.1", "prefixlen": 24}],
                }
            ]
        )
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db
        ):
            result = ipintutil._addr_show("asic0", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_get_ip_intfs_in_namespace_fast_path(self):
        ipintutil = _load_ipintutil_module("ipintutil_fast")

        ip_output = json.dumps(
            [
                {
                    "ifname": "Ethernet0",
                    "addr_info": [{"family": "inet", "local": "20.1.1.1", "prefixlen": 24}],
                },
                {
                    "ifname": "PortChannel0001",
                    "addr_info": [{"family": "inet", "local": "30.1.1.1", "prefixlen": 24}],
                },
            ]
        )
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db
        ), mock.patch("os.path.exists", return_value=True):
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "all")
            assert isinstance(result, dict)

    def test_skip_interface_filtering(self):
        ipintutil = _load_ipintutil_module("ipintutil_filter")

        ip_output = json.dumps(
            [
                {
                    "ifname": "eth0",
                    "addr_info": [
                        {"family": "inet", "local": "192.168.1.1", "prefixlen": 24}
                    ],
                },
                {
                    "ifname": "Loopback4096",
                    "addr_info": [{"family": "inet", "local": "1.1.1.1", "prefixlen": 32}],
                },
                {
                    "ifname": "veth123",
                    "addr_info": [{"family": "inet", "local": "10.0.0.1", "prefixlen": 24}],
                },
                {
                    "ifname": "Ethernet0",
                    "addr_info": [{"family": "inet", "local": "20.1.1.1", "prefixlen": 24}],
                },
            ]
        )
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db
        ), mock.patch("os.path.exists", return_value=True):
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "frontend")
            assert isinstance(result, dict)

    def test_get_ip_intfs_in_namespace_fast_path_parses_ip_json_and_filters(self):
        ipintutil = _load_ipintutil_module("ipintutil_parse_ip_json")

        ip_json = json.dumps(
            [
                {
                    "ifname": "lo",
                    "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}],
                },
                {
                    "ifname": "eth0",
                    "addr_info": [{"family": "inet", "local": "172.18.0.2", "prefixlen": 16}],
                },
                {
                    "ifname": "veth123@if8",
                    "addr_info": [{"family": "inet", "local": "10.0.0.1", "prefixlen": 24}],
                },
                {
                    "ifname": "Ethernet0",
                    "addr_info": [{"family": "inet", "local": "20.1.1.1", "prefixlen": 24}],
                },
                {
                    "ifname": "Ethernet1",
                    "addr_info": [{"family": "inet6", "local": "fe80::1", "prefixlen": 64}],
                },
                {
                    "ifname": "",
                    "addr_info": [{"family": "inet", "local": "99.9.9.9", "prefixlen": 32}],
                },
            ]
        )

        cfg = mock.MagicMock()
        cfg.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_json), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector", return_value=cfg
        ):
            ipintutil.get_if_admin_state = mock.MagicMock(return_value="up")
            ipintutil.get_if_oper_state = mock.MagicMock(return_value="down")
            ipintutil.get_if_master = mock.MagicMock(return_value="")
            ipintutil.get_bgp_peer = mock.MagicMock(
                return_value={"20.1.1.1": ["T2-Peer", "20.1.1.5"]}
            )

            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "asic0", "frontend")

        assert "Ethernet0" in result
        assert "eth0" not in result
        assert not any(key.startswith("veth") for key in result)
        assert result["Ethernet0"]["ipaddr"][0][1] == "20.1.1.1/24"
        assert result["Ethernet0"]["bgp_neighs"]["20.1.1.1/24"] == ["T2-Peer", "20.1.1.5"]
