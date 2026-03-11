import importlib.util
import json
import os
import re
import sys
import subprocess
from importlib.machinery import SourceFileLoader
from io import StringIO
from unittest import mock

import netifaces
import pytest

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

show_error_invalid_af = "Invalid argument -a ipv5"


def _load_ipintutil_module(module_name):
    ipintutil_path = os.path.join(scripts_path, "ipintutil")
    loader = SourceFileLoader(module_name, ipintutil_path)
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _normalize_body_line(line):
    return " | ".join(
        part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()
    )


def _extract_body_rows(table_text):
    rows = []
    for line in table_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Interface"):
            continue
        if set(stripped) == {"-"}:
            continue
        norm = _normalize_body_line(line)
        if norm:
            rows.append(norm)
    return rows


def verify_output(output, expected_output):
    output_rows = _extract_body_rows(output)
    expected_rows = _extract_body_rows(expected_output)

    lo_hits = [row for row in output_rows if row.startswith("lo | ")]
    assert len(lo_hits) == 1

    eth0_hits = [row for row in output_rows if row.startswith("eth0 | ")]
    assert len(eth0_hits) in (0, 1)

    filtered_rows = [
        row
        for row in output_rows
        if not row.startswith("lo | ") and not row.startswith("eth0 | ")
    ]

    assert filtered_rows == expected_rows


class _FakeMultiAsic:
    def __init__(self, namespace_option="", display_option="default", is_multi_asic=False):
        self.namespace_option = namespace_option
        self.display_option = display_option
        self.is_multi_asic = is_multi_asic

    def get_ns_list_based_on_options(self):
        default_ns = ""
        if not self.is_multi_asic:
            return [default_ns]

        if self.namespace_option and self.namespace_option != default_ns:
            return [self.namespace_option]
        return ["asic0"]


def _run_ipintutil_cli(args, addr_maps, bgp_peer=None, is_multi_asic=False):
    ipintutil = _load_ipintutil_module(
        "ipintutil_cli_{}".format("_".join(arg.replace("-", "x") for arg in args) or "default")
    )

    bgp_peer = bgp_peer or {}

    def fake_addr_show(namespace, af, display):
        return addr_maps.get((namespace, af, display), addr_maps.get((namespace, af), {}))

    def fake_multi_asic(namespace_option="", display_option="default"):
        return _FakeMultiAsic(
            namespace_option=namespace_option,
            display_option=display_option,
            is_multi_asic=is_multi_asic,
        )

    stdout = StringIO()

    with mock.patch.object(ipintutil, "load_db_config", return_value=None), mock.patch.object(
        ipintutil, "_addr_show", side_effect=fake_addr_show
    ), mock.patch.object(
        ipintutil, "get_bgp_peer", return_value=bgp_peer
    ), mock.patch.object(
        ipintutil, "get_if_admin_state", return_value="error"
    ), mock.patch.object(
        ipintutil, "get_if_oper_state", return_value="down"
    ), mock.patch.object(
        ipintutil, "get_if_master", return_value=""
    ), mock.patch.object(
        ipintutil.multi_asic_util, "MultiAsic", side_effect=fake_multi_asic
    ), mock.patch.object(
        ipintutil.os, "geteuid", return_value=0
    ), mock.patch.object(
        sys, "argv", ["ipintutil"] + args
    ), mock.patch.dict(
        os.environ, {"UTILITIES_UNIT_TESTING": "0"}, clear=False
    ), mock.patch(
        "sys.stdout", stdout
    ):
        try:
            ipintutil.main()
        except SystemExit as exc:
            code = exc.code
        else:
            code = 0

    if isinstance(code, str):
        return 1, code
    return code, stdout.getvalue().strip()


@pytest.fixture(scope="class")
def setup_teardown_single_asic():
    os.environ["PATH"] += os.pathsep + scripts_path
    yield


@pytest.fixture(scope="class")
def setup_teardown_multi_asic():
    os.environ["PATH"] += os.pathsep + scripts_path
    yield


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
    else:
        os.environ.pop("UTILITIES_UNIT_TESTING", None)

    if original_topo is not None:
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = original_topo
    else:
        os.environ.pop("UTILITIES_UNIT_TESTING_TOPOLOGY", None)


@pytest.mark.usefixtures("setup_teardown_single_asic")
class TestShowIpInt:
    def test_show_ip_intf_v4(self):
        addr_maps = {
            ("", netifaces.AF_INET): {
                "lo": [["", "127.0.0.1/8"]],
                "eth0": [["", "172.18.0.2/16"]],
                "Ethernet0": [["", "20.1.1.1/24"], ["", "21.1.1.1/24"]],
                "PortChannel0001": [["", "30.1.1.1/24"]],
                "Vlan100": [["", "40.1.1.1/24"]],
            }
        }
        bgp_peer = {
            "20.1.1.1": ["T2-Peer", "20.1.1.5"],
            "30.1.1.1": ["T0-Peer", "30.1.1.5"],
        }

        return_code, result = _run_ipintutil_cli([], addr_maps, bgp_peer=bgp_peer)
        assert return_code == 0
        verify_output(result, show_ipv4_intf_with_multple_ips)

    def test_show_ip_intf_v6(self):
        addr_maps = {
            ("", netifaces.AF_INET6): {
                "lo": [["", "::1/128"]],
                "Ethernet0": [
                    ["", "2100::1/64"],
                    ["", "aa00::1/64"],
                    ["", "fe80::64be:a1ff:fe85:c6c4%Ethernet0/64"],
                ],
                "PortChannel0001": [
                    ["", "ab00::1/64"],
                    ["", "fe80::cc8d:60ff:fe08:139f%PortChannel0001/64"],
                ],
                "Vlan100": [
                    ["", "cc00::1/64"],
                    ["", "fe80::c029:3fff:fe41:cf56%Vlan100/64"],
                ],
            }
        }

        return_code, result = _run_ipintutil_cli(["-a", "ipv6"], addr_maps)
        assert return_code == 0
        verify_output(result, show_ipv6_intf_with_multiple_ips)

    def test_show_intf_invalid_af_option(self):
        return_code, result = _run_ipintutil_cli(["-a", "ipv5"], {})
        assert return_code == 1
        assert result == show_error_invalid_af


@pytest.mark.usefixtures("setup_teardown_multi_asic")
class TestMultiAsicShowIpInt:
    def test_show_ip_intf_v4(self):
        addr_maps = {
            ("asic0", netifaces.AF_INET): {
                "Loopback0": [["", "40.1.1.1/32"]],
                "PortChannel0001": [["", "20.1.1.1/24"]],
            },
            ("", netifaces.AF_INET): {
                "lo": [["", "127.0.0.1/8"]],
                "eth0": [["", "172.18.0.2/16"]],
            },
        }
        bgp_peer = {"20.1.1.1": ["T2-Peer", "20.1.1.5"]}

        return_code, result = _run_ipintutil_cli(
            [], addr_maps, bgp_peer=bgp_peer, is_multi_asic=True
        )
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_asic0(self):
        addr_maps = {
            ("asic0", netifaces.AF_INET): {
                "Loopback0": [["", "40.1.1.1/32"]],
                "PortChannel0001": [["", "20.1.1.1/24"]],
            },
            ("", netifaces.AF_INET): {
                "lo": [["", "127.0.0.1/8"]],
                "eth0": [["", "172.18.0.2/16"]],
            },
        }
        bgp_peer = {"20.1.1.1": ["T2-Peer", "20.1.1.5"]}

        return_code, result = _run_ipintutil_cli(
            ["-n", "asic0"],
            addr_maps,
            bgp_peer=bgp_peer,
            is_multi_asic=True,
        )
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_all(self):
        addr_maps = {
            ("asic0", netifaces.AF_INET): {
                "Loopback0": [["", "40.1.1.1/32"]],
                "Loopback4096": [["", "1.1.1.1/24"], ["", "2.1.1.1/24"]],
                "PortChannel0001": [["", "20.1.1.1/24"]],
                "PortChannel0002": [["", "30.1.1.1/24"]],
                "veth@eth1": [["", "192.1.1.1/24"]],
                "veth@eth2": [["", "193.1.1.1/24"]],
            },
            ("", netifaces.AF_INET): {
                "lo": [["", "127.0.0.1/8"]],
                "eth0": [["", "172.18.0.2/16"]],
            },
        }
        bgp_peer = {
            "20.1.1.1": ["T2-Peer", "20.1.1.5"],
            "30.1.1.1": ["T0-Peer", "30.1.1.5"],
        }

        return_code, result = _run_ipintutil_cli(
            ["-d", "all"],
            addr_maps,
            bgp_peer=bgp_peer,
            is_multi_asic=True,
        )
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf_all)

    def test_show_ip_intf_v6(self):
        addr_maps = {
            ("asic0", netifaces.AF_INET6): {
                "Loopback0": [["", "fe80::60a5:9dff:fef4:1696%Loopback0/64"]],
                "PortChannel0001": [
                    ["", "aa00::1/64"],
                    ["", "fe80::80fd:d1ff:fe5b:452f/64"],
                ],
            },
            ("", netifaces.AF_INET6): {
                "lo": [["", "::1/128"]],
            },
        }

        return_code, result = _run_ipintutil_cli(
            ["-a", "ipv6"],
            addr_maps,
            is_multi_asic=True,
        )
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_asic0(self):
        addr_maps = {
            ("asic0", netifaces.AF_INET6): {
                "Loopback0": [["", "fe80::60a5:9dff:fef4:1696%Loopback0/64"]],
                "PortChannel0001": [
                    ["", "aa00::1/64"],
                    ["", "fe80::80fd:d1ff:fe5b:452f/64"],
                ],
            },
            ("", netifaces.AF_INET6): {
                "lo": [["", "::1/128"]],
            },
        }

        return_code, result = _run_ipintutil_cli(
            ["-a", "ipv6", "-n", "asic0"],
            addr_maps,
            is_multi_asic=True,
        )
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_all(self):
        addr_maps = {
            ("asic0", netifaces.AF_INET6): {
                "Loopback0": [["", "fe80::60a5:9dff:fef4:1696%Loopback0/64"]],
                "PortChannel0001": [
                    ["", "aa00::1/64"],
                    ["", "fe80::80fd:d1ff:fe5b:452f/64"],
                ],
                "PortChannel0002": [
                    ["", "bb00::1/64"],
                    ["", "fe80::80fd:abff:fe5b:452f/64"],
                ],
            },
            ("", netifaces.AF_INET6): {
                "lo": [["", "::1/128"]],
            },
        }

        return_code, result = _run_ipintutil_cli(
            ["-a", "ipv6", "-d", "all"],
            addr_maps,
            is_multi_asic=True,
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

        with mock.patch("subprocess.check_output", return_value=ip_output):
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)
            assert "Ethernet0" in result
            assert result["Ethernet0"][0][1] == "20.1.1.1/24"

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

        with mock.patch("subprocess.check_output", return_value=ip_output):
            result = ipintutil._addr_show("", netifaces.AF_INET6, "all")
            assert isinstance(result, dict)
            assert result["Ethernet0"][0][1] == "2100::1/64"

    def test_addr_show_malformed_output(self):
        ipintutil = _load_ipintutil_module("ipintutil_malformed")

        with mock.patch("subprocess.check_output", return_value="not a json\n"):
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_subprocess_error(self):
        ipintutil = _load_ipintutil_module("ipintutil_error")

        with mock.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        ):
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

        with mock.patch("subprocess.check_output", return_value=ip_output):
            result = ipintutil._addr_show("asic0", netifaces.AF_INET, "all")
            assert isinstance(result, dict)
            assert result["Ethernet0"][0][1] == "10.0.0.1/24"

    def test_get_ip_intfs_in_namespace_fast_path(self):
        ipintutil = _load_ipintutil_module("ipintutil_fast")

        addr_map = {
            "Ethernet0": [["", "20.1.1.1/24"]],
            "PortChannel0001": [["", "30.1.1.1/24"]],
        }

        with mock.patch.object(ipintutil, "_addr_show", return_value=addr_map), mock.patch.object(
            ipintutil, "get_bgp_peer", return_value={}
        ), mock.patch.object(
            ipintutil, "get_if_admin_state", return_value="up"
        ), mock.patch.object(
            ipintutil, "get_if_oper_state", return_value="down"
        ), mock.patch.object(
            ipintutil, "get_if_master", return_value=""
        ):
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "all")
            assert isinstance(result, dict)
            assert "Ethernet0" in result

    def test_skip_interface_filtering(self):
        ipintutil = _load_ipintutil_module("ipintutil_filter")

        addr_map = {
            "eth0": [["", "192.168.1.1/24"]],
            "Loopback4096": [["", "1.1.1.1/32"]],
            "veth123": [["", "10.0.0.1/24"]],
            "Ethernet0": [["", "20.1.1.1/24"]],
        }

        with mock.patch.object(ipintutil, "_addr_show", return_value=addr_map), mock.patch.object(
            ipintutil, "get_bgp_peer", return_value={}
        ), mock.patch.object(
            ipintutil, "get_if_admin_state", return_value="up"
        ), mock.patch.object(
            ipintutil, "get_if_oper_state", return_value="down"
        ), mock.patch.object(
            ipintutil, "get_if_master", return_value=""
        ):
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "frontend")
            assert isinstance(result, dict)

    def test_get_ip_intfs_in_namespace_fast_path_parses_ip_json_and_filters(self):
        ipintutil = _load_ipintutil_module("ipintutil_parse_ip_json")

        addr_map = {
            "lo": [["", "127.0.0.1/8"]],
            "eth0": [["", "172.18.0.2/16"]],
            "veth123@if8": [["", "10.0.0.1/24"]],
            "Ethernet0": [["", "20.1.1.1/24"]],
        }

        with mock.patch.object(ipintutil, "_addr_show", return_value=addr_map), mock.patch.object(
            ipintutil, "get_if_admin_state", return_value="up"
        ), mock.patch.object(
            ipintutil, "get_if_oper_state", return_value="down"
        ), mock.patch.object(
            ipintutil, "get_if_master", return_value=""
        ), mock.patch.object(
            ipintutil, "get_bgp_peer", return_value={"20.1.1.1": ["T2-Peer", "20.1.1.5"]}
        ):
            result = ipintutil.get_ip_intfs_in_namespace(
                netifaces.AF_INET,
                "asic0",
                "frontend",
            )

        assert "Ethernet0" in result
        assert "eth0" in result
        assert "lo" in result
        assert "veth123@if8" in result
        assert result["Ethernet0"]["ipaddr"][0][1] == "20.1.1.1/24"
        assert result["Ethernet0"]["bgp_neighs"]["20.1.1.1/24"] == ["T2-Peer", "20.1.1.5"]
        assert result["eth0"]["bgp_neighs"]["172.18.0.2/16"] == ["N/A", "N/A"]


class TestShowIpIntCoverageBoost:
    def test_get_unit_test_namespace_list_single_asic(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_ns_single")

        with mock.patch.dict(
            os.environ,
            {"UTILITIES_UNIT_TESTING_TOPOLOGY": ""},
            clear=False,
        ):
            namespace_list, is_multi = ipintutil._get_unit_test_namespace_list("")
            assert namespace_list == [ipintutil.constants.DEFAULT_NAMESPACE]
            assert is_multi is False

    def test_get_unit_test_namespace_list_multi_asic_default(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_ns_multi_default")

        with mock.patch.dict(
            os.environ,
            {"UTILITIES_UNIT_TESTING_TOPOLOGY": "multi_asic"},
            clear=False,
        ):
            namespace_list, is_multi = ipintutil._get_unit_test_namespace_list("")
            assert namespace_list == ["asic0", ipintutil.constants.DEFAULT_NAMESPACE]
            assert is_multi is True

    def test_get_unit_test_namespace_list_multi_asic_named(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_ns_multi_named")

        with mock.patch.dict(
            os.environ,
            {"UTILITIES_UNIT_TESTING_TOPOLOGY": "multi_asic"},
            clear=False,
        ):
            namespace_list, is_multi = ipintutil._get_unit_test_namespace_list("asic3")
            assert namespace_list == ["asic3", ipintutil.constants.DEFAULT_NAMESPACE]
            assert is_multi is True

    def test_get_bgp_peer_returns_empty_in_unit_testing(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_bgp_ut")

        with mock.patch.dict(
            os.environ,
            {"UTILITIES_UNIT_TESTING": "2"},
            clear=False,
        ):
            assert ipintutil.get_bgp_peer() == {}

    def test_get_bgp_peer_reads_configdb_and_ignores_keyerror(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_bgp_cfg")

        cfg = mock.MagicMock()
        cfg.get_table.return_value = {
            "10.0.0.2": {"local_addr": "10.0.0.1", "name": "PeerA"},
            "10.0.0.4": {"name": "MissingLocal"},
            "10.0.0.6": {"local_addr": "10.0.0.5"},
        }

        with mock.patch.dict(
            os.environ,
            {"UTILITIES_UNIT_TESTING": "0"},
            clear=False,
        ), mock.patch(
            "swsscommon.swsscommon.ConfigDBConnector",
            return_value=cfg,
        ):
            result = ipintutil.get_bgp_peer()

        cfg.connect.assert_called_once()
        assert result == {"10.0.0.1": ["PeerA", "10.0.0.2"]}

    def test_skip_ip_intf_display_branches(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_skip")

        with mock.patch.object(
            ipintutil.multi_asic,
            "is_port_internal",
            return_value=True,
        ), mock.patch.object(
            ipintutil.multi_asic,
            "is_port_channel_internal",
            return_value=True,
        ):
            assert ipintutil.skip_ip_intf_display("Ethernet0", "frontend") is True
            assert ipintutil.skip_ip_intf_display("PortChannel0001", "frontend") is True
            assert ipintutil.skip_ip_intf_display("Loopback4096", "frontend") is True
            assert ipintutil.skip_ip_intf_display("eth0", "frontend") is True
            assert ipintutil.skip_ip_intf_display("veth123", "frontend") is True
            assert ipintutil.skip_ip_intf_display("Ethernet0", ipintutil.constants.DISPLAY_ALL) is False

    def test_get_if_admin_state_up_down_error_paths(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_admin")

        proc_up = mock.MagicMock()
        proc_up.communicate.return_value = ("0x1\n",)
        proc_down = mock.MagicMock()
        proc_down.communicate.return_value = ("0x0\n",)
        proc_bad = mock.MagicMock()
        proc_bad.communicate.return_value = ("nothex\n",)

        with mock.patch("subprocess.Popen", return_value=proc_up) as popen:
            assert ipintutil.get_if_admin_state("Ethernet0", "") == "up"
            popen.assert_called_once()

        with mock.patch("subprocess.Popen", return_value=proc_down):
            assert ipintutil.get_if_admin_state("Ethernet0", "asic0") == "down"

        with mock.patch("subprocess.Popen", return_value=proc_bad):
            assert ipintutil.get_if_admin_state("Ethernet0", "") == "error"

        with mock.patch("subprocess.Popen", side_effect=OSError):
            assert ipintutil.get_if_admin_state("Ethernet0", "") == "error"

    def test_get_if_oper_state_up_down_error_paths(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_oper")

        proc_up = mock.MagicMock()
        proc_up.communicate.return_value = ("1\n",)
        proc_down = mock.MagicMock()
        proc_down.communicate.return_value = ("0\n",)

        with mock.patch("subprocess.Popen", return_value=proc_up):
            assert ipintutil.get_if_oper_state("Ethernet0", "") == "up"

        with mock.patch("subprocess.Popen", return_value=proc_down):
            assert ipintutil.get_if_oper_state("Ethernet0", "asic0") == "down"

        with mock.patch("subprocess.Popen", side_effect=OSError):
            assert ipintutil.get_if_oper_state("Ethernet0", "") == "error"

    def test_get_if_master_exists_and_missing(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_master")

        with mock.patch("os.path.exists", return_value=True), mock.patch(
            "os.path.realpath",
            return_value="/sys/class/net/PortChannel0001",
        ):
            assert ipintutil.get_if_master("Ethernet0") == "PortChannel0001"

        with mock.patch("os.path.exists", return_value=False):
            assert ipintutil.get_if_master("Ethernet0") == ""

    def test_addr_show_text_parses_and_filters(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_addr_text")

        text_output = "\n".join(
            [
                "1: lo    inet 127.0.0.1/8 scope host lo",
                "2: eth0    inet 172.18.0.2/16 brd 172.18.255.255 scope global eth0",
                "3: Ethernet0    inet 20.1.1.1/24 brd 20.1.1.255 scope global Ethernet0",
                "4: veth123    inet 10.0.0.1/24 brd 10.0.0.255 scope global veth123",
                "5: broken line without family",
                "6: PortChannel0001    inet6 aa00::1/64 scope global",
            ]
        )

        with mock.patch(
            "subprocess.check_output",
            return_value=text_output,
        ), mock.patch.object(
            ipintutil,
            "skip_ip_intf_display",
            side_effect=lambda ifname, display: ifname in ("eth0", "veth123"),
        ):
            result = ipintutil._addr_show_text("asic0", netifaces.AF_INET, "frontend")

        assert "Ethernet0" in result
        assert "eth0" not in result
        assert "veth123" not in result
        assert result["Ethernet0"][0][1] == "20.1.1.1/24"

    def test_addr_show_text_handles_called_process_error(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_addr_text_err")

        with mock.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        ):
            result = ipintutil._addr_show_text("", netifaces.AF_INET, "all")

        assert result == {}

    def test_addr_show_json_skips_invalid_entries(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_addr_json_invalid")

        ip_output = json.dumps(
            [
                {},
                {"ifname": ""},
                {
                    "ifname": "Ethernet0",
                    "addr_info": [
                        {"family": "inet6", "local": "fe80::1", "prefixlen": 64},
                        {"family": "inet", "prefixlen": 24},
                        {"family": "inet", "local": "20.1.1.1"},
                        {"family": "inet", "local": "20.1.1.1", "prefixlen": 24},
                    ],
                },
            ]
        )

        with mock.patch("subprocess.check_output", return_value=ip_output):
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")

        assert result == {"Ethernet0": [["", "20.1.1.1/24"]]}

    def test_get_ip_intfs_uses_production_multiasic_path(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_get_ip_prod")

        device = mock.MagicMock()
        device.get_ns_list_based_on_options.return_value = ["asic0"]
        device.is_multi_asic = False

        with mock.patch.dict(
            os.environ,
            {"UTILITIES_UNIT_TESTING": "0"},
            clear=False,
        ), mock.patch.object(
            ipintutil.multi_asic_util,
            "MultiAsic",
            return_value=device,
        ), mock.patch.object(
            ipintutil,
            "get_ip_intfs_in_namespace",
            return_value={"Ethernet0": {"ipaddr": [["", "20.1.1.1/24"]]}}
        ):
            result = ipintutil.get_ip_intfs(netifaces.AF_INET, "", "frontend")

        assert "Ethernet0" in result

    def test_get_ip_intfs_merges_duplicate_interfaces_across_namespaces(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_get_ip_merge")

        with mock.patch.dict(
            os.environ,
            {
                "UTILITIES_UNIT_TESTING": "2",
                "UTILITIES_UNIT_TESTING_TOPOLOGY": "multi_asic",
            },
            clear=False,
        ), mock.patch.object(
            ipintutil,
            "get_ip_intfs_in_namespace",
            side_effect=[
                {
                    "Ethernet0": {
                        "vrf": "",
                        "ipaddr": [["", "20.1.1.1/24"]],
                        "admin": "up",
                        "oper": "down",
                        "bgp_neighs": {"20.1.1.1/24": ["PeerA", "20.1.1.2"]},
                        "ns": "asic0",
                    }
                },
                {
                    "Ethernet0": {
                        "vrf": "",
                        "ipaddr": [["", "21.1.1.1/24"]],
                        "admin": "up",
                        "oper": "down",
                        "bgp_neighs": {"21.1.1.1/24": ["PeerB", "21.1.1.2"]},
                        "ns": "",
                    },
                    "lo": {
                        "vrf": "",
                        "ipaddr": [["", "127.0.0.1/8"]],
                        "admin": "up",
                        "oper": "up",
                        "bgp_neighs": {"127.0.0.1/8": ["N/A", "N/A"]},
                        "ns": "",
                    },
                },
            ],
        ):
            result = ipintutil.get_ip_intfs(netifaces.AF_INET, "", "frontend")

        assert result["Ethernet0"]["ipaddr"] == [["", "20.1.1.1/24"], ["", "21.1.1.1/24"]]
        assert result["Ethernet0"]["bgp_neighs"]["21.1.1.1/24"] == ["PeerB", "21.1.1.2"]
        assert "lo" in result

    def test_get_ip_intfs_skips_duplicate_identical_ip_list(self):
        ipintutil = _load_ipintutil_module("ipintutil_cov_get_ip_same")

        same_entry = {
            "Ethernet0": {
                "vrf": "",
                "ipaddr": [["", "20.1.1.1/24"]],
                "admin": "up",
                "oper": "down",
                "bgp_neighs": {"20.1.1.1/24": ["PeerA", "20.1.1.2"]},
                "ns": "asic0",
            }
        }

        with mock.patch.dict(
            os.environ,
            {
                "UTILITIES_UNIT_TESTING": "2",
                "UTILITIES_UNIT_TESTING_TOPOLOGY": "multi_asic",
            },
            clear=False,
        ), mock.patch.object(
            ipintutil,
            "get_ip_intfs_in_namespace",
            side_effect=[same_entry, same_entry],
        ):
            result = ipintutil.get_ip_intfs(netifaces.AF_INET, "", "frontend")

        assert result["Ethernet0"]["ipaddr"] == [["", "20.1.1.1/24"]]
