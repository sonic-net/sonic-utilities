#!/usr/bin/env python3
"""
Tests for the text-streaming fetch_routes() implementation.

fetch_routes() runs:
    vtysh -c "show ip route"   (or "show ipv6 route")
and scans each output line with:
    r'^B>([qo])\\s+(\\S+)\\s'
  'q' → suppress-fib-pending (queued) → missing_routes
  'o' → offload failed           → failing_routes
  anything else is ignored.
"""

import sys
from unittest.mock import Mock, patch

sys.path.append("scripts")
import route_check  # noqa: E402


def _missing(prefix, protocol='bgp'):
    return {'prefix': prefix, 'protocol': protocol}


def _missing_prefixes(routes):
    return {e['prefix'] for e in routes}


def _make_proc(lines, exit_code=0):
    mock_proc = Mock()
    mock_proc.stdout = iter(lines)
    mock_proc.wait = Mock(return_value=exit_code)
    mock_proc.__enter__ = Mock(return_value=mock_proc)
    mock_proc.__exit__ = Mock(return_value=False)
    return mock_proc


def _bgp_line(flag, prefix):
    return f"B>{flag} {prefix} [200/0] via 192.0.2.1, Ethernet0, weight 1, 00:01:00\n"


class TestFetchRoutes:

    def setup_method(self):
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    def test_healthy_route_ignored(self):
        lines = [_bgp_line("*", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_queued_route_in_missing(self):
        lines = [_bgp_line("q", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([_missing("10.0.0.0/24")], [])

    def test_offload_failed_route_in_failing(self):
        lines = [_bgp_line("o", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], ["10.0.0.0/24"])

    def test_non_bgp_routes_ignored(self):
        lines = [
            "O>* 10.0.0.1/32 [110/20] via 192.0.2.1, Ethernet0\n",
            "S>* 10.0.0.2/32 [1/0] directly connected, Ethernet0\n",
            "C>* 192.168.0.0/24 is directly connected, Ethernet0\n",
        ]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_non_selected_bgp_ignored(self):
        lines = ["B   q 10.0.0.0/24 [200/0] via 192.0.2.1, Ethernet0\n"]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_mixed_flags_multiple_routes(self):
        lines = [
            _bgp_line("*", "10.0.0.0/24"),
            _bgp_line("q", "10.1.0.0/24"),
            _bgp_line("o", "10.2.0.0/24"),
            _bgp_line("q", "10.3.0.0/24"),
        ]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes()
        assert _missing_prefixes(missing) == {"10.1.0.0/24", "10.3.0.0/24"}
        assert failing == ["10.2.0.0/24"]

    def test_many_queued_routes(self):
        lines = [_bgp_line("q", f"10.{i}.0.0/16") for i in range(100)]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes()
        assert _missing_prefixes(missing) == {f"10.{i}.0.0/16" for i in range(100)}
        assert len(missing) == 100
        assert failing == []

    def test_empty_output(self):
        with patch("route_check.subprocess.Popen", return_value=_make_proc([])):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_header_and_blank_lines_ignored(self):
        lines = [
            "Codes: K - kernel route, C - connected, S - static, R - RIP,\n",
            "       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,\n",
            "\n",
            "VRF default:\n",
            _bgp_line("q", "10.0.0.0/24"),
        ]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes()
        assert missing == [_missing("10.0.0.0/24")]
        assert failing == []

    def test_ipv4_command(self):
        with patch("route_check.subprocess.Popen",
                   return_value=_make_proc([])) as mock_popen:
            route_check.fetch_routes(ipv6=False)
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sudo", "vtysh", "-c", "show ip route"]

    def test_ipv6_command(self):
        with patch("route_check.subprocess.Popen",
                   return_value=_make_proc([])) as mock_popen:
            route_check.fetch_routes(ipv6=True)
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sudo", "vtysh", "-c", "show ipv6 route"]

    def test_ipv6_route_parsing(self):
        lines = ["B>q 2001:db8::/32 [200/0] via fe80::1, Ethernet0\n"]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes(ipv6=True)
        assert missing == [_missing("2001:db8::/32")]
        assert failing == []

    def test_nonzero_exit_code_still_returns_routes(self):
        lines = [_bgp_line("q", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen",
                   return_value=_make_proc(lines, exit_code=1)):
            result = route_check.fetch_routes()
        assert result == ([_missing("10.0.0.0/24")], [])

    def test_file_not_found_returns_empty(self):
        with patch("route_check.subprocess.Popen",
                   side_effect=FileNotFoundError("vtysh not found")):
            result = route_check.fetch_routes()
        assert result == ([], [])
