#!/usr/bin/env python3
"""
Tests for intersection-based retry logic in check_frr_pending_routes().
"""

import sys
from unittest.mock import patch

sys.path.append("scripts")
import route_check  # noqa: E402


def _miss(*prefixes, protocol='bgp'):
    return [{'prefix': p, 'protocol': protocol} for p in prefixes]


class TestCheckFrrPendingRoutes:
    def setup_method(self):
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    def test_clears_on_first_poll_no_mitigation(self):
        with patch.object(route_check, "get_frr_routes_parallel",
                          return_value=([], [])) as mock_poll:
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == []
        assert failed == []
        assert mock_poll.call_count == 1

    def test_all_stuck_every_poll_all_mitigated(self):
        always_stuck = (_miss("10.0.0.0/24", "10.1.0.0/24"), [])
        with patch.object(route_check, "get_frr_routes_parallel",
                          return_value=always_stuck):
            missed, failed = route_check.check_frr_pending_routes(None)
        assert {e['prefix'] for e in missed} == {"10.0.0.0/24", "10.1.0.0/24"}
        assert failed == []

    def test_converging_route_not_mitigated(self):
        side_effects = [
            (_miss("10.0.0.0/24", "10.1.0.0/24"), []),
            (_miss("10.0.0.0/24"), []),
            (_miss("10.0.0.0/24"), []),
        ]
        with patch.object(route_check, "get_frr_routes_parallel",
                          side_effect=side_effects):
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == _miss("10.0.0.0/24")
        assert failed == []

    def test_all_converge_mid_retry(self):
        side_effects = [
            (_miss("10.0.0.0/24"), []),
            ([], []),
        ]
        with patch.object(route_check, "get_frr_routes_parallel",
                          side_effect=side_effects) as mock_poll:
            missed, failed = route_check.check_frr_pending_routes(None)
        assert missed == []
        assert failed == []
        assert mock_poll.call_count == 2

    def test_failed_routes_intersection(self):
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
