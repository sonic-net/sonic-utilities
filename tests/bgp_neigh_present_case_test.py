import mock
import pytest

import utilities_common.bgp_util as bgp_util


def test_canonical_neigh_ip_ipv6_case_and_compression():
    # Uppercase / expanded IPv6 forms must canonicalize to the same value as
    # the lowercase / compressed form a caller typically passes in.
    canon = bgp_util._canonical_neigh_ip
    assert canon("FC00::71") == canon("fc00::71")
    assert canon("FC00:0000::0071") == canon("fc00::71")
    # IPv4 is returned as-is (already canonical) and unaffected.
    assert canon("10.0.0.1") == "10.0.0.1"
    # Non-IP values (e.g. VRF names) pass through unchanged.
    assert canon("Vrf-red") == "Vrf-red"


class _FakeConfigDB(object):
    """Minimal ConfigDBConnector stub keyed exactly like redis (case-sensitive)."""

    def __init__(self, entries):
        # entries: {table: {key: value_dict}}; key may be str or tuple
        self._entries = entries

    def get_keys(self, table):
        return list(self._entries.get(table, {}).keys())

    def get_entry(self, table, key):
        return self._entries.get(table, {}).get(key, {})

    def get_table(self, table):
        return self._entries.get(table, {})


@pytest.mark.parametrize("query", ["fc00::71", "FC00::71", "fc00:0000::0071"])
def test_is_bgp_neigh_present_ipv6_uppercase_key(query):
    # CONFIG_DB stores the v6 neighbor key uppercase (as minigraph renders it).
    entries = {
        bgp_util.multi_asic.BGP_NEIGH_CFG_DB_TABLE: {
            "FC00::71": {"asn": "65100"},
        },
        bgp_util.multi_asic.BGP_INTERNAL_NEIGH_CFG_DB_TABLE: {},
        "BGP_PEER_RANGE": {},
    }
    fake = _FakeConfigDB(entries)
    with mock.patch.object(bgp_util.multi_asic, "connect_config_db_for_ns", return_value=fake):
        assert bgp_util.is_bgp_neigh_present(query) is True


def test_is_bgp_neigh_present_absent_returns_false():
    entries = {
        bgp_util.multi_asic.BGP_NEIGH_CFG_DB_TABLE: {"FC00::71": {"asn": "65100"}},
        bgp_util.multi_asic.BGP_INTERNAL_NEIGH_CFG_DB_TABLE: {},
        "BGP_PEER_RANGE": {},
    }
    fake = _FakeConfigDB(entries)
    with mock.patch.object(bgp_util.multi_asic, "connect_config_db_for_ns", return_value=fake):
        assert bgp_util.is_bgp_neigh_present("fc00::99") is False


def test_is_bgp_neigh_present_unified_mode_vrf_key_ipv6_case():
    # Unified routing config mode stores keys as (vrf, neighbor_ip) tuples.
    entries = {
        bgp_util.multi_asic.BGP_NEIGH_CFG_DB_TABLE: {
            ("default", "FC00::71"): {"asn": "65100"},
        },
        bgp_util.multi_asic.BGP_INTERNAL_NEIGH_CFG_DB_TABLE: {},
        "BGP_PEER_RANGE": {},
    }
    fake = _FakeConfigDB(entries)
    with mock.patch.object(bgp_util.multi_asic, "connect_config_db_for_ns", return_value=fake):
        assert bgp_util.is_bgp_neigh_present("fc00::71", vrf_name="all") is True
