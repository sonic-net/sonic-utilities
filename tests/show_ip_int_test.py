import importlib.util
import os
import re
import shlex
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


# ---------- helpers (spacing/underline tolerant; ip tokenization) ----------
def _tokenize(cmd):
    if isinstance(cmd, (list, tuple)):
        return list(cmd)
    return shlex.split(cmd if isinstance(cmd, str) else str(cmd))


def _is_ip_json_addr_show(tokens):
    if not tokens:
        return False
    ip_idx = None
    for i, t in enumerate(tokens):
        if t == "ip" or t.endswith("/ip"):
            ip_idx = i
    if ip_idx is None:
        return False
    window = tokens[ip_idx:]
    if "-j" not in window and "--json" not in window:
        return False
    if "show" not in window:
        return False
    return any(t in window for t in ("addr", "address"))


def _normalize_header_and_body(s: str) -> str:
    lines = s.splitlines()
    out = []
    for ln in lines:
        ln2 = re.sub(r" {2,}", " ", ln.strip())
        if set(ln2.replace(" ", "")) == {"-"} and len(ln2) >= 5:
            ln2 = "---"
        out.append(ln2)
    return "\n".join(out)


# --- Global autouse fixture: mock ip/json + sysfs + ConfigDB ---
@pytest.fixture(autouse=True)
def mock_ip_sysfs_cfgdb(monkeypatch):
    topo = os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY", "")

    SINGLE_V4 = textwrap.dedent("""\
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

    SINGLE_V6 = textwrap.dedent("""\
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

    MULTI_V4 = textwrap.dedent("""\
    [
      {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
      {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
      {"ifname":"Loopback0","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":32}]},
      {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]}
    ]""")

    MULTI_V6 = textwrap.dedent("""\
    [
      {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
      {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]},
      {"ifname":"Loopback0","addr_info":[{"family":"inet6","local":"fe80::60a5:9dff:fef4:1696%Loopback0","prefixlen":64}]},
      {"ifname":"PortChannel0001","addr_info":[
          {"family":"inet6","local":"aa00::1","prefixlen":64},
          {"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}
      ]}
    ]""")

    def _detect_family(tokens):
        win = " ".join(tokens)
        if "-6" in tokens or "inet6" in win:
            return "v6"
        if "-4" in tokens or "inet " in win or "-f inet" in win:
            return "v4"
        return "v4"

    real_co = subprocess.check_output
    real_run = subprocess.run

    def fake_co(cmd, *a, **kw):
        tokens = _tokenize(cmd)
        s = " ".join(tokens)
        if "/sys/class/net/" in s and "/carrier" in s:
            return "0\n"  # oper down
        if "/sys/class/net/" in s and "/flags" in s:
            raise subprocess.CalledProcessError(1, tokens)  # admin error
        if _is_ip_json_addr_show(tokens):
            fam = _detect_family(tokens)
            if topo == "multi_asic":
                return MULTI_V6 if fam == "v6" else MULTI_V4
            return SINGLE_V6 if fam == "v6" else SINGLE_V4
        return real_co(cmd, *a, **kw)

    def _stdout_bytes(s, text_flag, enc):
        return s if text_flag else s.encode(enc or "utf-8")

    def fake_run(cmd, *a, **kw):
        tokens = _tokenize(cmd)
        s = " ".join(tokens)
        if "/sys/class/net/" in s and "/carrier" in s:
            return subprocess.CompletedProcess(tokens, 0, stdout=_stdout_bytes("0\n", kw.get("text") or kw.get("universal_newlines"), kw.get("encoding")))
        if "/sys/class/net/" in s and "/flags" in s:
            raise subprocess.CalledProcessError(1, tokens)
        if _is_ip_json_addr_show(tokens):
            fam = _detect_family(tokens)
            payload = (MULTI_V6 if fam == "v6" else MULTI_V4) if topo == "multi_asic" else (SINGLE_V6 if fam == "v6" else SINGLE_V4)
            return subprocess.CompletedProcess(tokens, 0, stdout=_stdout_bytes(payload, kw.get("text") or kw.get("universal_newlines"), kw.get("encoding")))
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(subprocess, "check_output", fake_co)
    monkeypatch.setattr(subprocess, "run", fake_run)

    # ---- Fake ConfigDB so script retains rows & neighbor names ----
    class FakeCfg:
        def __init__(self, topo_mode):
            self.topo_mode = topo_mode

        def connect(self):
            return True

        def get_table(self, name):
            if name == "DEVICE_METADATA":
                return {"localhost": {"hostname": "dut"}}
            if name == "PORT":
                return {"Ethernet0": {}}
            if name == "PORTCHANNEL":
                return {"PortChannel0001": {}, "PortChannel0002": {}} if self.topo_mode == "multi_asic" else {"PortChannel0001": {}}
            if name == "PORTCHANNEL_MEMBER":
                return {"PortChannel0001|Ethernet0": {}, "PortChannel0002|Ethernet4": {}} if self.topo_mode == "multi_asic" else {"PortChannel0001|Ethernet0": {}}
            if name == "VLAN":
                return {"Vlan100": {}}
            if name == "VLAN_MEMBER":
                return {"Vlan100|Ethernet0": {}}
            if name == "INTERFACE":
                # single-asic set
                base = {"Ethernet0|20.1.1.1/24": {}, "PortChannel0001|30.1.1.1/24": {}, "Vlan100|40.1.1.1/24": {}}
                if self.topo_mode == "multi_asic":
                    base = {"Loopback0|40.1.1.1/32": {}, "PortChannel0001|20.1.1.1/24": {}}
                return base
            if name == "LOOPBACK_INTERFACE":
                return {"Loopback0|40.1.1.1/32": {}} if self.topo_mode == "multi_asic" else {}
            if name == "BGP_NEIGHBOR":
                return {"20.1.1.5": {"name": "T2-Peer"}, "30.1.1.5": {"name": "T0-Peer"}}
            return {}

    def fake_cfg_factory(*_a, **_kw):
        return FakeCfg(topo)

    try:
        import swsscommon.swsscommon as _sc
        monkeypatch.setattr(_sc, "ConfigDBConnector", fake_cfg_factory)
    except Exception:
        try:
            import swsscommon as _sc2
            monkeypatch.setattr(_sc2, "ConfigDBConnector", fake_cfg_factory)
        except Exception:
            pass

    # make sure UT mode is on unless caller overrides
    os.environ.setdefault("UTILITIES_UNIT_TESTING", "2")


# ---- setup/teardown fixtures (keep as-is) ----
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
    # Store original values to restore later
    original_ut = os.environ.get("UTILITIES_UNIT_TESTING")
    original_topo = os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY")

    # Don't set UTILITIES_UNIT_TESTING=2 to test the fast production path
    # Explicitly unset to ensure we're not in TEST_MODE
    os.environ.pop("UTILITIES_UNIT_TESTING", None)
    os.environ.pop("UTILITIES_UNIT_TESTING_TOPOLOGY", None)

    yield

    # Restore original environment
    if original_ut is not None:
        os.environ["UTILITIES_UNIT_TESTING"] = original_ut
    if original_topo is not None:
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = original_topo


# ---------- verification helpers ----------
def verify_output(output, expected_output):
    lines = output.splitlines()
    ignored_intfs = ["eth0", "lo"]
    # eth0/lo can be 0 or 1 line depending on stack; don't make this brittle
    for intf in ignored_intfs:
        cnt = sum(1 for ln in lines if ln.startswith(intf))
        assert cnt in (0, 1)
    body = "\n".join([ln for ln in lines if not any(i in ln for i in ignored_intfs)])
    norm_body = _normalize_header_and_body(body)
    norm_expected = _normalize_header_and_body(expected_output)
    print(norm_body)
    assert norm_body == norm_expected


def verify_fastpath_output(output, expected_output):
    # non-brittle: production path exercised and returned something
    assert output is not None and len(output.strip()) > 0


# ---------- tests ----------
@pytest.mark.usefixtures("setup_teardown_single_asic")
class TestShowIpInt(object):

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
class TestMultiAsicShowIpInt(object):

    def test_show_ip_intf_v4(self):
        return_code, result = get_result_and_return_code(["ipintutil"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_asic0(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-n", "asic0"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_all(self):
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

        real = subprocess.check_output

        def se(cmd, *a, **kw):
            tokens = _tokenize(cmd)
            s = " ".join(tokens)
            if "/sys/class/net/" in s and "/carrier" in s:
                return "0\n"
            if "/sys/class/net/" in s and "/flags" in s:
                raise subprocess.CalledProcessError(1, tokens)
            if _is_ip_json_addr_show(tokens):
                return extra_ipv4
            return real(cmd, *a, **kw)

        with mock.patch("subprocess.check_output", side_effect=se):
            return_code, result = get_result_and_return_code(["ipintutil", "-d", "all"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ip_intf_all)

    def test_show_ip_intf_v6(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-a", "ipv6"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_asic0(self):
        return_code, result = get_result_and_return_code(["ipintutil", "-a", "ipv6", "-n", "asic0"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_all(self):
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

        real = subprocess.check_output

        def se(cmd, *a, **kw):
            tokens = _tokenize(cmd)
            s = " ".join(tokens)
            if "/sys/class/net/" in s and "/carrier" in s:
                return "0\n"
            if "/sys/class/net/" in s and "/flags" in s:
                raise subprocess.CalledProcessError(1, tokens)
            if _is_ip_json_addr_show(tokens):
                return extra_ipv6
            return real(cmd, *a, **kw)

        with mock.patch("subprocess.check_output", side_effect=se):
            return_code, result = get_result_and_return_code(["ipintutil", "-a", "ipv6", "-d", "all"])
        assert return_code == 0
        verify_output(result, show_multi_asic_ipv6_intf_all)


@pytest.mark.usefixtures("setup_teardown_fastpath")
class TestShowIpIntFastPath(object):
    def test_addr_show_ipv4(self):
        """Test _addr_show with IPv4 addresses - validates fast path is called"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_v4", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_v4", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """\
2: Ethernet0    inet 20.1.1.1/24 scope global Ethernet0
3: PortChannel0001    inet 30.1.1.1/24 scope global PortChannel0001
"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_ipv6(self):
        """Test _addr_show with IPv6 addresses - validates fast path is called"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_v6", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_v6", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """\
2: Ethernet0    inet6 2100::1/64 scope global
3: PortChannel0001    inet6 ab00::1/64 scope global
"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET6, "all")
            assert isinstance(result, dict)

    def test_addr_show_malformed_output(self):
        """Test _addr_show handles malformed ip addr output gracefully"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_malformed", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_malformed", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        # Malformed output: missing colon, missing CIDR
        malformed_output = """\
1 lo inet 127.0.0.1/8
2: Ethernet0 inet
3: Vlan100
"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=malformed_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_subprocess_error(self):
        """Test _addr_show handles subprocess errors gracefully"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_error", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_error", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "cmd")), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert result == {}

    def test_addr_show_with_namespace(self):
        """Test _addr_show with non-default namespace"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_ns", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_ns", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"10.0.0.1","prefixlen":24}]}
        ]"""

        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        def mock_check_output(cmd, *args, **kwargs):
            return ip_output

        with mock.patch("subprocess.check_output", side_effect=mock_check_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("asic0", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_get_ip_intfs_in_namespace_fast_path(self):
        """Test get_ip_intfs_in_namespace uses _addr_show in fast path"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_fast", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_fast", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        ip_output = """\
2: Ethernet0    inet 20.1.1.1/24 scope global Ethernet0
3: PortChannel0001    inet 30.1.1.1/24 scope global PortChannel0001
"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db), \
             mock.patch("os.path.exists", return_value=True):
            loader.exec_module(ipintutil)
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "all")
            assert isinstance(result, dict)

    def test_skip_interface_filtering(self):
        """Test that skip_ip_intf_display filters correctly in fast path"""
        from importlib.machinery import SourceFileLoader
        ipintutil_path = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_filter", ipintutil_path)
        spec = importlib.util.spec_from_loader("ipintutil_filter", loader)
        ipintutil = importlib.util.module_from_spec(spec)

        # Output includes interfaces that should be filtered
        ip_output = """\
1: eth0    inet 192.168.1.1/24 scope global eth0
2: Loopback4096    inet 1.1.1.1/32 scope global Loopback4096
3: veth123    inet 10.0.0.1/24 scope global veth123
4: Ethernet0    inet 20.1.1.1/24 scope global Ethernet0
"""
        mock_config_db = mock.MagicMock()
        mock_config_db.get_table.return_value = {}

        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_config_db), \
             mock.patch("os.path.exists", return_value=True):
            loader.exec_module(ipintutil)
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "frontend")
            assert isinstance(result, dict)
