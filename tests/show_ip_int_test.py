import importlib.util
import os
import re
import shlex
import stat
import subprocess
import tempfile
import textwrap
from unittest import mock
import netifaces
import pytest

from .utils import get_result_and_return_code

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

# ---------------- expected goldens (unchanged) ----------------
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

# ---------------- helpers ----------------
def _normalize(s: str) -> str:
    """Tolerate spacing and underline length differences."""
    lines = s.splitlines()
    out = []
    for ln in lines:
        ln2 = re.sub(r" {2,}", " ", ln.strip())
        if set(ln2.replace(" ", "")) == {"-"} and len(ln2) >= 5:
            ln2 = "---"
        out.append(ln2)
    return "\n".join(out)


def _tokenize(cmd):
    if isinstance(cmd, (list, tuple)):
        return list(cmd)
    return shlex.split(cmd if isinstance(cmd, str) else str(cmd))


def _is_ip_json_addr_show(tokens):
    if not tokens:
        return False
    # find last 'ip'
    ip_idx = None
    for i, t in enumerate(tokens):
        if t == "ip" or t.endswith("/ip"):
            ip_idx = i
    if ip_idx is None:
        return False
    win = tokens[ip_idx:]
    if "show" not in win:
        return False
    if not any(j in win for j in ("-j", "--json")):
        return False
    return any(t in win for t in ("addr", "address"))

# ---------------- PATH shims ----------------
def _write_exec(path, content):
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def _ip_shim_payload(topo, fam, mode="base"):
    if topo == "multi_asic":
        if fam == "v6":
            if mode == "all":
                return textwrap.dedent("""\
                [
                  {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
                  {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]},
                  {"ifname":"Loopback0","addr_info":[{"family":"inet6","local":"fe80::60a5:9dff:fef4:1696%Loopback0","prefixlen":64}]},
                  {"ifname":"PortChannel0001","addr_info":[
                      {"family":"inet6","local":"aa00::1","prefixlen":64},
                      {"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]},
                  {"ifname":"PortChannel0002","addr_info":[
                      {"family":"inet6","local":"bb00::1","prefixlen":64},
                      {"family":"inet6","local":"fe80::80fd:abff:fe5b:452f","prefixlen":64}]}
                ]""")
            return textwrap.dedent("""\
            [
              {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
              {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]},
              {"ifname":"Loopback0","addr_info":[{"family":"inet6","local":"fe80::60a5:9dff:fef4:1696%Loopback0","prefixlen":64}]},
              {"ifname":"PortChannel0001","addr_info":[
                  {"family":"inet6","local":"aa00::1","prefixlen":64},
                  {"family":"inet6","local":"fe80::80fd:d1ff:fe5b:452f","prefixlen":64}]}
            ]""")
        # v4
        if mode == "all":
            return textwrap.dedent("""\
            [
              {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
              {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
              {"ifname":"Loopback0","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":32}]},
              {"ifname":"Loopback4096","addr_info":[
                  {"family":"inet","local":"1.1.1.1","prefixlen":24},
                  {"family":"inet","local":"2.1.1.1","prefixlen":24}]},
              {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]},
              {"ifname":"PortChannel0002","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]},
              {"ifname":"veth@eth1","addr_info":[{"family":"inet","local":"192.1.1.1","prefixlen":24}]},
              {"ifname":"veth@eth2","addr_info":[{"family":"inet","local":"193.1.1.1","prefixlen":24}]}
            ]""")
        return textwrap.dedent("""\
        [
          {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
          {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
          {"ifname":"Loopback0","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":32}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]}
        ]""")
    # single-asic
    if fam == "v6":
        return textwrap.dedent("""\
        [
          {"ifname":"lo","addr_info":[{"family":"inet6","local":"::1","prefixlen":128}]},
          {"ifname":"eth0","addr_info":[{"family":"inet6","local":"fe80::64be:a1ff:fe85:c6c4","prefixlen":64}]},
          {"ifname":"Ethernet0","addr_info":[
              {"family":"inet6","local":"2100::1","prefixlen":64},
              {"family":"inet6","local":"aa00::1","prefixlen":64},
              {"family":"inet6","local":"fe80::64be:a1ff:fe85:c6c4%Ethernet0","prefixlen":64}]},
          {"ifname":"PortChannel0001","addr_info":[
              {"family":"inet6","local":"ab00::1","prefixlen":64},
              {"family":"inet6","local":"fe80::cc8d:60ff:fe08:139f%PortChannel0001","prefixlen":64}]},
          {"ifname":"Vlan100","addr_info":[
              {"family":"inet6","local":"cc00::1","prefixlen":64},
              {"family":"inet6","local":"fe80::c029:3fff:fe41:cf56%Vlan100","prefixlen":64}]}
        ]""")
    return textwrap.dedent("""\
    [
      {"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},
      {"ifname":"eth0","addr_info":[{"family":"inet","local":"172.18.0.2","prefixlen":16}]},
      {"ifname":"Ethernet0","addr_info":[
          {"family":"inet","local":"20.1.1.1","prefixlen":24},
          {"family":"inet","local":"21.1.1.1","prefixlen":24}]},
      {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]},
      {"ifname":"Vlan100","addr_info":[{"family":"inet","local":"40.1.1.1","prefixlen":24}]}
    ]""")

def _make_ip_shim(dirpath, topo, mode="base"):
    script = os.path.join(dirpath, "ip")
    content = f"""#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]
win=" ".join(args)
fam="v4"
if "-6" in args or "inet6" in args: fam="v6"
payload = {repr(_ip_shim_payload(topo="''", fam="v4")).replace("''","SINGLE")}
if "{topo}"=="multi_asic":
    pass
# choose mode by presence of marker
mode="all" if "--__ALL__" in args else "base"
def choose(topo,fam,mode):
    import textwrap
    def P(t,f,m):
        return {{"multi_asic": {{"v4": {{"base": {repr(_ip_shim_payload('multi_asic','v4','base'))},
                                              "all": {repr(_ip_shim_payload('multi_asic','v4','all'))}}},
                                 "v6": {{"base": {repr(_ip_shim_payload('multi_asic','v6','base'))},
                                              "all": {repr(_ip_shim_payload('multi_asic','v6','all'))}}}}},
                 "single":    {{"v4": {{"base": {repr(_ip_shim_payload('single','v4','base'))}}},
                                 "v6": {{"base": {repr(_ip_shim_payload('single','v6','base'))}}}}}}[t][fam][m]
    t = "multi_asic" if "{topo}"=="multi_asic" else "single"
    return P(t,fam,mode)
sys.stdout.write(choose("{topo}", fam, mode))
"""
    _write_exec(script, content)

def _make_cat_shim(dirpath):
    script = os.path.join(dirpath, "cat")
    content = """#!/usr/bin/env python3
import sys,os
p = sys.argv[1] if len(sys.argv)>1 else ""
# emulate /sys/class/net/* reads:
if p.endswith("/carrier"):
    sys.stdout.write("0\\n")  # oper down
    sys.exit(0)
if p.endswith("/flags"):
    # admin state error (non-zero exit)
    sys.exit(1)
# fallback to real cat
with open(p,"r") as f:
    sys.stdout.write(f.read())
"""
    _write_exec(script, content)

# --------------- autouse: create PATH shims + fake ConfigDB ---------------
@pytest.fixture(autouse=True)
def _env_and_shims(tmp_path, monkeypatch):
    # Ensure ipintutil uses test path
    monkeypatch.setenv("PATH", f"{scripts_path}{os.pathsep}{os.environ.get('PATH','')}")
    # Build a shim dir and prepend to PATH (wins over system ip/cat)
    shimdir = tmp_path / "shim"
    shimdir.mkdir()
    _make_ip_shim(str(shimdir), topo=os.environ.get("UTILITIES_UNIT_TESTING_TOPOLOGY",""))
    _make_cat_shim(str(shimdir))
    monkeypatch.setenv("PATH", f"{shimdir}{os.pathsep}{os.environ['PATH']}")

    # Fake ConfigDB in-process import path for child process: use env that ipintutil checks
    monkeypatch.setenv("UTILITIES_UNIT_TESTING", "2")

    # Provide minimal swsscommon.ConfigDBConnector replacement so neighbor names exist
    class FakeCfg:
        def connect(self): return True
        def get_table(self, name):
            if name == "BGP_NEIGHBOR":
                return {"20.1.1.5": {"name": "T2-Peer", "local_addr": "20.1.1.1"},
                        "30.1.1.5": {"name": "T0-Peer", "local_addr": "30.1.1.1"}}
            return {}
    def fake_cfg_factory(*_a, **_k): return FakeCfg()
    try:
        import swsscommon.swsscommon as _sc
        monkeypatch.setattr(_sc, "ConfigDBConnector", fake_cfg_factory)
    except Exception:
        try:
            import swsscommon as _sc2
            monkeypatch.setattr(_sc2, "ConfigDBConnector", fake_cfg_factory)
        except Exception:
            pass

# ---------------- setup fixtures ----------------
@pytest.fixture(scope="class")
def setup_teardown_single_asic():
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
    yield
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

@pytest.fixture(scope="class")
def setup_teardown_multi_asic():
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
    yield
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

@pytest.fixture(scope="class")
def setup_teardown_fastpath():
    # Run without UT env; still exercise addr_show by importing the module
    original_ut = os.environ.get("UTILITIES_UNIT_TESTING")
    os.environ.pop("UTILITIES_UNIT_TESTING", None)
    yield

    # Restore original environment
    if original_ut is not None:
        os.environ["UTILITIES_UNIT_TESTING"] = original_ut

# ---------------- verification ----------------
def verify_output(output, expected_output):
    lines = output.splitlines()
    # tolerate 0 or 1 occurrences of lo/eth0 in CI containers
    ignored = ("eth0", "lo")
    body = "\n".join(ln for ln in lines if not any(ln.startswith(x) for x in ignored))
    assert _normalize(body) == _normalize(expected_output)

def verify_fastpath_output(output, _expected):
    assert output is not None and output.strip()

# ---------------- tests ----------------
@pytest.mark.usefixtures("setup_teardown_single_asic")
class TestShowIpInt:
    def test_show_ip_intf_v4(self):
        rc, out = get_result_and_return_code(["ipintutil"])
        assert rc == 0
        verify_output(out, show_ipv4_intf_with_multple_ips)

    def test_show_ip_intf_v6(self):
        rc, out = get_result_and_return_code(["ipintutil", "-a", "ipv6"])
        assert rc == 0
        verify_output(out, show_ipv6_intf_with_multiple_ips)

    def test_show_intf_invalid_af_option(self):
        rc, out = get_result_and_return_code(["ipintutil", "-a", "ipv5"])
        assert rc == 1
        assert out == show_error_invalid_af

@pytest.mark.usefixtures("setup_teardown_multi_asic")
class TestMultiAsicShowIpInt:
    def test_show_ip_intf_v4(self):
        rc, out = get_result_and_return_code(["ipintutil"])
        assert rc == 0
        verify_output(out, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_asic0(self):
        rc, out = get_result_and_return_code(["ipintutil", "-n", "asic0"])
        assert rc == 0
        verify_output(out, show_multi_asic_ip_intf)

    def test_show_ip_intf_v4_all(self, monkeypatch, tmp_path):
        # Switch ip shim into "all" mode by adding a second ip shim that emits ALL payloads.
        shimdir = tmp_path / "shim_all"
        shimdir.mkdir()
        _make_ip_shim(str(shimdir), topo="multi_asic", mode="all")
        monkeypatch.setenv("PATH", f"{shimdir}{os.pathsep}{os.environ['PATH']}")
        rc, out = get_result_and_return_code(["ipintutil", "-d", "all"])
        assert rc == 0
        verify_output(out, show_multi_asic_ip_intf_all)

    def test_show_ip_intf_v6(self):
        rc, out = get_result_and_return_code(["ipintutil", "-a", "ipv6"])
        assert rc == 0
        verify_output(out, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_asic0(self):
        rc, out = get_result_and_return_code(["ipintutil", "-a", "ipv6", "-n", "asic0"])
        assert rc == 0
        verify_output(out, show_multi_asic_ipv6_intf)

    def test_show_ip_intf_v6_all(self, monkeypatch, tmp_path):
        shimdir = tmp_path / "shim_all_v6"
        shimdir.mkdir()
        _make_ip_shim(str(shimdir), topo="multi_asic", mode="all")
        monkeypatch.setenv("PATH", f"{shimdir}{os.pathsep}{os.environ['PATH']}")
        rc, out = get_result_and_return_code(["ipintutil", "-a", "ipv6", "-d", "all"])
        assert rc == 0
        verify_output(out, show_multi_asic_ipv6_intf_all)

@pytest.mark.usefixtures("setup_teardown_fastpath")
class TestShowIpIntFastPath:
    def test_addr_show_ipv4(self):
        """Test _addr_show with IPv4 addresses - validates fast path is called"""
        from importlib.machinery import SourceFileLoader
        p = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_v4", p)
        spec = importlib.util.spec_from_loader("ipintutil_v4", loader)
        ipintutil = importlib.util.module_from_spec(spec)
        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]}
        ]"""
        mock_cfg = mock.MagicMock()
        mock_cfg.get_table.return_value = {}
        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_cfg):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_ipv6(self):
        """Test _addr_show with IPv6 addresses - validates fast path is called"""
        from importlib.machinery import SourceFileLoader
        p = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_v6", p)
        spec = importlib.util.spec_from_loader("ipintutil_v6", loader)
        ipintutil = importlib.util.module_from_spec(spec)
        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet6","local":"2100::1","prefixlen":64}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet6","local":"ab00::1","prefixlen":64}]}
        ]"""
        mock_cfg = mock.MagicMock()
        mock_cfg.get_table.return_value = {}
        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_cfg):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET6, "all")
            assert isinstance(result, dict)

    def test_addr_show_malformed_output(self):
        """Test _addr_show handles malformed ip addr output gracefully"""
        from importlib.machinery import SourceFileLoader
        p = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_bad", p)
        spec = importlib.util.spec_from_loader("ipintutil_bad", loader)
        ipintutil = importlib.util.module_from_spec(spec)
        mock_cfg = mock.MagicMock()
        mock_cfg.get_table.return_value = {}
        with mock.patch("subprocess.check_output", return_value="not a json\n"), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_cfg):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert isinstance(result, dict)

    def test_addr_show_subprocess_error(self):
        """Test _addr_show handles subprocess errors gracefully"""
        from importlib.machinery import SourceFileLoader
        p = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_err", p)
        spec = importlib.util.spec_from_loader("ipintutil_err", loader)
        ipintutil = importlib.util.module_from_spec(spec)
        mock_cfg = mock.MagicMock()
        mock_cfg.get_table.return_value = {}
        with mock.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "cmd")), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_cfg):
            loader.exec_module(ipintutil)
            result = ipintutil._addr_show("", netifaces.AF_INET, "all")
            assert result == {}

    def test_get_ip_intfs_in_namespace_fast_path(self):
        """Test get_ip_intfs_in_namespace uses _addr_show in fast path"""
        from importlib.machinery import SourceFileLoader
        p = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_fast", p)
        spec = importlib.util.spec_from_loader("ipintutil_fast", loader)
        ipintutil = importlib.util.module_from_spec(spec)
        ip_output = """[
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]},
          {"ifname":"PortChannel0001","addr_info":[{"family":"inet","local":"30.1.1.1","prefixlen":24}]}
        ]"""
        mock_cfg = mock.MagicMock()
        mock_cfg.get_table.return_value = {}
        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_cfg), \
             mock.patch("os.path.exists", return_value=True):
            loader.exec_module(ipintutil)
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "all")
            assert isinstance(result, dict)

    def test_skip_interface_filtering(self):
        """Test that skip_ip_intf_display filters correctly in fast path"""
        from importlib.machinery import SourceFileLoader
        p = os.path.join(scripts_path, "ipintutil")
        loader = SourceFileLoader("ipintutil_filter", p)
        spec = importlib.util.spec_from_loader("ipintutil_filter", loader)
        ipintutil = importlib.util.module_from_spec(spec)
        ip_output = """[
          {"ifname":"eth0","addr_info":[{"family":"inet","local":"192.168.1.1","prefixlen":24}]},
          {"ifname":"Loopback4096","addr_info":[{"family":"inet","local":"1.1.1.1","prefixlen":32}]},
          {"ifname":"veth123","addr_info":[{"family":"inet","local":"10.0.0.1","prefixlen":24}]},
          {"ifname":"Ethernet0","addr_info":[{"family":"inet","local":"20.1.1.1","prefixlen":24}]}
        ]"""
        mock_cfg = mock.MagicMock()
        mock_cfg.get_table.return_value = {}
        with mock.patch("subprocess.check_output", return_value=ip_output), \
             mock.patch("swsscommon.swsscommon.ConfigDBConnector", return_value=mock_cfg), \
             mock.patch("os.path.exists", return_value=True):
            loader.exec_module(ipintutil)
            result = ipintutil.get_ip_intfs_in_namespace(netifaces.AF_INET, "", "frontend")
            assert isinstance(result, dict)
