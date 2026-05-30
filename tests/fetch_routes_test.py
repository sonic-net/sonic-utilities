#!/usr/bin/env python3
"""
Tests for the text-streaming fetch_routes() and the intersection-based retry
logic in check_frr_pending_routes().

fetch_routes() runs:
    vtysh -c "show ip route"   (or "show ipv6 route")
and scans each output line with:
    r'^B>([qo])\\s+(\\S+)\\s'
  'q' → suppress-fib-pending (queued) → missing_routes
  'o' → offload failed           → failing_routes
  anything else is ignored.

check_frr_pending_routes() accumulates an intersection across
FRR_CHECK_RETRIES polls so only persistently stuck routes are mitigated.
"""

import sys
from unittest.mock import Mock, patch

sys.path.append("scripts")
import route_check  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(lines, exit_code=0):
    """Return a mock Popen whose stdout yields *lines* as an iterator."""
    mock_proc = Mock()
    mock_proc.stdout = iter(lines)
    mock_proc.wait = Mock(return_value=exit_code)
    mock_proc.__enter__ = Mock(return_value=mock_proc)
    mock_proc.__exit__ = Mock(return_value=False)
    return mock_proc


def _bgp_line(flag, prefix):
    """Build a realistic vtysh BGP route line with the given flag char."""
    return f"B>{flag} {prefix} [200/0] via 192.0.2.1, Ethernet0, weight 1, 00:01:00\n"


# ---------------------------------------------------------------------------
# TestFetchRoutes — text-based vtysh output parsing
# ---------------------------------------------------------------------------

class TestFetchRoutes:

    def setup_method(self):
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    # --- basic flag detection ---

    def test_healthy_route_ignored(self):
        """B>* (active/installed) must not appear in either return list."""
        lines = [_bgp_line("*", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_queued_route_in_missing(self):
        """B>q (suppress-fib-pending / queued) → prefix lands in missing_routes."""
        lines = [_bgp_line("q", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == (["10.0.0.0/24"], [])

    def test_offload_failed_route_in_failing(self):
        """B>o (offload failed) → prefix lands in failing_routes."""
        lines = [_bgp_line("o", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], ["10.0.0.0/24"])

    def test_non_bgp_routes_ignored(self):
        """Non-BGP protocol lines (OSPF, static, connected) are all ignored."""
        lines = [
            "O>* 10.0.0.1/32 [110/20] via 192.0.2.1, Ethernet0\n",   # OSPF
            "S>* 10.0.0.2/32 [1/0] directly connected, Ethernet0\n",  # static
            "C>* 192.168.0.0/24 is directly connected, Ethernet0\n",  # connected
        ]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_non_selected_bgp_ignored(self):
        """BGP line without '>' (not selected as best route) must not match."""
        lines = ["B   q 10.0.0.0/24 [200/0] via 192.0.2.1, Ethernet0\n"]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            result = route_check.fetch_routes()
        assert result == ([], [])

    # --- multi-route output ---

    def test_mixed_flags_multiple_routes(self):
        """Mix of *, q, and o lines → correct split between the two output lists."""
        lines = [
            _bgp_line("*", "10.0.0.0/24"),   # healthy  → skip
            _bgp_line("q", "10.1.0.0/24"),   # queued   → missing
            _bgp_line("o", "10.2.0.0/24"),   # failed   → failing
            _bgp_line("q", "10.3.0.0/24"),   # queued   → missing
        ]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes()
        assert set(missing) == {"10.1.0.0/24", "10.3.0.0/24"}
        assert failing == ["10.2.0.0/24"]

    def test_many_queued_routes(self):
        """100 B>q lines → 100 entries in missing_routes, failing_routes empty."""
        lines = [_bgp_line("q", f"10.{i}.0.0/16") for i in range(100)]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes()
        assert set(missing) == {f"10.{i}.0.0/16" for i in range(100)}
        assert len(missing) == 100
        assert failing == []

    def test_empty_output(self):
        """Empty vtysh output (healthy device) → ([], [])."""
        with patch("route_check.subprocess.Popen", return_value=_make_proc([])):
            result = route_check.fetch_routes()
        assert result == ([], [])

    def test_header_and_blank_lines_ignored(self):
        """vtysh legend, VRF header, and blank lines don't match the regex."""
        lines = [
            "Codes: K - kernel route, C - connected, S - static, R - RIP,\n",
            "       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,\n",
            "\n",
            "VRF default:\n",
            _bgp_line("q", "10.0.0.0/24"),
        ]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes()
        assert missing == ["10.0.0.0/24"]
        assert failing == []

    # --- command construction ---

    def test_ipv4_command(self):
        """Default call constructs 'show ip route' (no 'json' suffix)."""
        with patch("route_check.subprocess.Popen",
                   return_value=_make_proc([])) as mock_popen:
            route_check.fetch_routes(ipv6=False)
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sudo", "vtysh", "-c", "show ip route"]

    def test_ipv6_command(self):
        """ipv6=True constructs 'show ipv6 route' (no 'json' suffix)."""
        with patch("route_check.subprocess.Popen",
                   return_value=_make_proc([])) as mock_popen:
            route_check.fetch_routes(ipv6=True)
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sudo", "vtysh", "-c", "show ipv6 route"]

    def test_ipv6_route_parsing(self):
        """B>q line with an IPv6 prefix is extracted correctly."""
        lines = ["B>q 2001:db8::/32 [200/0] via fe80::1, Ethernet0\n"]
        with patch("route_check.subprocess.Popen", return_value=_make_proc(lines)):
            missing, failing = route_check.fetch_routes(ipv6=True)
        assert missing == ["2001:db8::/32"]
        assert failing == []

    # --- error handling ---

    def test_nonzero_exit_code_still_returns_routes(self):
        """Non-zero vtysh exit is logged; routes collected so far are still returned."""
        lines = [_bgp_line("q", "10.0.0.0/24")]
        with patch("route_check.subprocess.Popen",
                   return_value=_make_proc(lines, exit_code=1)):
            result = route_check.fetch_routes()
        assert result == (["10.0.0.0/24"], [])

    def test_file_not_found_returns_empty(self):
        """FileNotFoundError (vtysh absent) → ([], []) with no exception raised."""
        with patch("route_check.subprocess.Popen",
                   side_effect=FileNotFoundError("vtysh not found")):
            result = route_check.fetch_routes()
        assert result == ([], [])


# ---------------------------------------------------------------------------
# TestCheckFrrPendingRoutes — intersection-based retry logic
# ---------------------------------------------------------------------------

class TestCheckFrrPendingRoutes:
    """
    check_frr_pending_routes() calls get_frr_routes_parallel() up to
    FRR_CHECK_RETRIES times and intersects results across iterations so that
    only routes stuck in *every* poll are forwarded for mitigation.
    """

    def setup_method(self):
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    def test_clears_on_first_poll_no_mitigation(self):
        """First poll returns empty → no mitigation; loop exits after one call."""
        with patch.object(route_check, "get_frr_routes_parallel",
                          return_value=([], [])) as mock_poll:
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == []
        assert failed == []
        assert mock_poll.call_count == 1

    def test_all_stuck_every_poll_all_mitigated(self):
        """Same routes returned in every iteration → all survive the intersection."""
        always_stuck = (["10.0.0.0/24", "10.1.0.0/24"], [])
        with patch.object(route_check, "get_frr_routes_parallel",
                          return_value=always_stuck):
            missed, failed = route_check.check_frr_pending_routes(None)
        assert set(missed) == {"10.0.0.0/24", "10.1.0.0/24"}
        assert failed == []

    def test_converging_route_not_mitigated(self):
        """A route that disappears between iterations is removed from the intersection."""
        # iter 0: A + B stuck; iter 1: only A; iter 2: only A
        side_effects = [
            (["10.0.0.0/24", "10.1.0.0/24"], []),
            (["10.0.0.0/24"], []),
            (["10.0.0.0/24"], []),
        ]
        with patch.object(route_check, "get_frr_routes_parallel",
                          side_effect=side_effects):
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == ["10.0.0.0/24"]
        assert failed == []

    def test_all_converge_mid_retry(self):
        """All routes clear before retries are exhausted → empty result, early exit."""
        side_effects = [
            (["10.0.0.0/24"], []),   # iter 0: stuck
            ([], []),                # iter 1: clear → break
        ]
        with patch.object(route_check, "get_frr_routes_parallel",
                          side_effect=side_effects) as mock_poll:
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == []
        assert failed == []
        assert mock_poll.call_count == 2

    def test_failed_routes_intersection(self):
        """Intersection logic is applied to failing_routes symmetrically."""
        # iter 0: two failing; iter 1: one cleared; iter 2: one still failing
        side_effects = [
            ([], ["10.0.0.0/24", "10.1.0.0/24"]),
            ([], ["10.0.0.0/24"]),
            ([], ["10.0.0.0/24"]),
        ]
        with patch.object(route_check, "get_frr_routes_parallel",
                          side_effect=side_effects):
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == []
        assert failed == ["10.0.0.0/24"]
