# Copyright 2026 Nexthop Systems Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the MST views of `show spanning_tree`.

The daemon publishes MST state to APPL_DB and the region lives only in
CONFIG_DB, so these drive the commands over fakes for both rather than over
the shared mock tables, which carry no MST keys.
"""
import fnmatch
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import show.main  # noqa: F401  (import side effects register the commands)
import show.stp as show_stp


APPL_DB = 0

REGION = {
    "name": "region1",
    "revision": "3",
    "max_hops": "20",
    "max_age": "20",
    "hello_time": "2",
    "forward_delay": "15",
    "hold_count": "6",
}

INSTANCE_0 = {
    "vlan@": "100,101,102,200",
    "bridge_address": "8000.0000.e8e4.9d10",
    "bridge_priority": "32768",
    "root_address": "8000.0000.e8e4.9d10",
    "regional_root_address": "8000.0000.e8e4.9d10",
    "root_path_cost": "0",
    "regional_root_cost": "0",
    "root_hello_time": "2",
    "root_forward_delay": "15",
    "root_max_age": "20",
    "hold_time": "6",
    "root_port": "Root",
    "remaining_hops": "20",
}

INSTANCE_2 = dict(INSTANCE_0, **{"vlan@": "300", "bridge_priority": "28672"})

PORT_0_ETH0 = {
    "port_number": "0",
    "priority": "128",
    "path_cost": "200",
    "port_state": "FORWARDING",
    "role": "DESIGNATED",
    "desig_cost": "0",
    "external_cost": "0",
    "desig_root": "8000.0000.e8e4.9d10",
    "desig_reg_root": "8000.0000.e8e4.9d10",
    "desig_bridge": "8000.0000.e8e4.9d10",
    "desig_port": "524288",
    "fwd_transitions": "1",
    "bpdu_sent": "2277",
    "bpdu_received": "2276",
}

PORT_2_ETH0 = dict(PORT_0_ETH0, **{"role": "ROOT", "port_state": "FORWARDING"})


class FakeApplDb:
    """Just enough SonicV2Connector for these views."""

    APPL_DB = APPL_DB

    def __init__(self, entries):
        self.entries = entries

    def connect(self, _db):
        pass

    def keys(self, _db, pattern):
        # Redis KEYS is glob, and the views rely on a leading '*' to skip the
        # producer-copy underscore, so match the same way rather than by prefix.
        return [k for k in self.entries if fnmatch.fnmatch(k, pattern)]

    def get_all(self, _db, key):
        return self.entries.get(key)


class FakeStateDb(FakeApplDb):
    STATE_DB = 6


class FakeCfgDb:
    def __init__(self, tables):
        self.tables = tables

    def connect(self):
        pass

    def get_entry(self, table, key):
        return self.tables.get(table, {}).get(key, {})

    def get_keys(self, table):
        return list(self.tables.get(table, {}).keys())


def appl_entries():
    return {
        "_STP_MST_INST_TABLE:0": dict(INSTANCE_0),
        "_STP_MST_INST_TABLE:2": dict(INSTANCE_2),
        "_STP_MST_PORT_TABLE:0:Ethernet0": dict(PORT_0_ETH0),
        "_STP_MST_PORT_TABLE:2:Ethernet0": dict(PORT_2_ETH0),
        "_STP_PORT_TABLE:Ethernet0": {"mst_boundary": "yes", "mst_boundary_proto": "rstp"},
    }


def cfg_tables(mode="mst"):
    return {
        "STP": {"GLOBAL": {"mode": mode}},
        "STP_MST": {"GLOBAL": dict(REGION)},
    }


@pytest.fixture
def run_mst():
    """Invoke a `show spanning_tree ...` command over the fakes."""
    def _run(args, appl=None, cfg=None, state=None):
        appl_db = FakeApplDb(appl if appl is not None else appl_entries())
        cfg_db = FakeCfgDb(cfg if cfg is not None else cfg_tables())
        state_db = FakeStateDb(state if state is not None else {})
        with patch("show.stp.connect_to_appl_db", return_value=appl_db), \
             patch("show.stp.connect_to_cfg_db", return_value=cfg_db), \
             patch("show.stp.connect_to_state_db", return_value=state_db):
            return CliRunner().invoke(show_stp.spanning_tree, args)
    return _run


class TestShowHeldInstances:
    # stpmgrd records in STATE_DB an instance the hardware had no room for;
    # the view lists it after the ones that run.
    def test_an_instance_the_hardware_refused_is_listed(self, run_mst):
        result = run_mst([], state={
            "STP_MST_INST_TABLE|5": {"instance_state": "unavailable",
                                     "reason": "hardware limit of 3 spanning tree instances reached"}})

        assert result.exit_code == 0, result.output
        assert "MST Instance 2" in result.output
        assert ("MST Instance 5 - no STP instance: hardware limit of 3 spanning tree instances reached"
                in result.output)

    def test_held_instances_are_listed_when_none_is_operational(self, run_mst):
        result = run_mst([], appl={}, state={
            "STP_MST_INST_TABLE|5": {"instance_state": "unavailable",
                                     "reason": "hardware limit of 1 spanning tree instances reached"}})

        assert result.exit_code == 0, result.output
        assert "No MST instances are operational" in result.output
        assert ("MST Instance 5 - no STP instance: hardware limit of 1 spanning tree instances reached"
                in result.output)

    def test_held_vlans_are_listed_when_no_vlan_is_operational(self, run_mst):
        result = run_mst([], appl={}, cfg=cfg_tables("pvst"), state={
            "STP_VLAN_TABLE|Vlan200": {"instance_state": "unavailable",
                                       "reason": "hardware limit of 1 spanning tree instances reached"},
            "STP_VLAN_TABLE|Vlan100": {"instance_state": "unavailable",
                                       "reason": "hardware limit of 1 spanning tree instances reached"}})

        assert result.exit_code == 0, result.output
        assert result.output.index("VLAN 100 - no STP instance") < result.output.index("VLAN 200 - no STP instance")

    def test_nothing_is_listed_when_every_instance_runs(self, run_mst):
        result = run_mst([])

        assert result.exit_code == 0, result.output
        assert "no STP instance" not in result.output


class TestShowMstRegion:
    def test_region_is_visible(self, run_mst):
        result = run_mst(["mst", "region"])

        assert result.exit_code == 0, result.output
        assert "region1" in result.output
        assert "Revision" in result.output
        # The instance-to-VLAN map is part of the region view.
        assert "100-102,200" in result.output
        assert "300" in result.output

    def test_region_reports_when_none_is_configured(self, run_mst):
        cfg = cfg_tables()
        cfg["STP_MST"] = {}
        result = run_mst(["mst", "region"], cfg=cfg)

        assert result.exit_code == 0, result.output
        assert "No MST region is configured" in result.output


class TestShowMstInstance:
    def test_instance_shows_the_mst_only_fields(self, run_mst):
        result = run_mst(["mst", "instance", "0"])

        assert result.exit_code == 0, result.output
        assert "MST Instance 0 (CIST)" in result.output
        # These four are what the default view omitted entirely.
        assert "Regional Root" in result.output
        assert "Regional Root Cost" in result.output
        assert "Bridge Priority" in result.output
        assert "HoldTime" in result.output

    def test_instance_detail_includes_the_designated_columns(self, run_mst):
        result = run_mst(["mst", "instance", "0"])

        assert result.exit_code == 0, result.output
        for label in ("Desig Root:", "Desig RegRoot:", "Desig Port:",
                      "External Cost:", "Fwd Transitions:", "BPDUs Sent:"):
            assert label in result.output
        assert "Boundary:" in result.output

    def test_msti_is_labelled_as_such(self, run_mst):
        result = run_mst(["mst", "instance", "2"])

        assert result.exit_code == 0, result.output
        assert "MST Instance 2 (MSTI)" in result.output

    def test_unknown_instance_is_refused(self, run_mst):
        result = run_mst(["mst", "instance", "7"])

        assert result.exit_code != 0
        assert "MST instance 7 is not operational" in result.output


class TestShowMstInterface:
    def test_interface_spans_every_instance(self, run_mst):
        result = run_mst(["mst", "interface", "Ethernet0"])

        assert result.exit_code == 0, result.output
        assert "0 (CIST)" in result.output
        assert "2 (MSTI)" in result.output
        assert "DESIGNATED" in result.output
        assert "ROOT" in result.output

    def test_unenrolled_interface_is_refused(self, run_mst):
        result = run_mst(["mst", "interface", "Ethernet99"])

        assert result.exit_code != 0
        assert "not enrolled in any MST instance" in result.output


class TestShowMstGating:
    def test_mst_commands_are_refused_in_pvst_mode(self, run_mst):
        result = run_mst(["mst", "region"], cfg=cfg_tables(mode="pvst"))

        assert result.exit_code != 0
        assert "not running in MST mode" in result.output

    def test_bare_mst_shows_region_and_instances(self, run_mst):
        result = run_mst(["mst"])

        assert result.exit_code == 0, result.output
        assert "MST Region" in result.output
        assert "MST Instance 0 (CIST)" in result.output
        assert "MST Instance 2 (MSTI)" in result.output

    def test_no_instances_says_so_rather_than_printing_nothing(self, run_mst):
        result = run_mst(["mst", "region"], appl={})

        assert result.exit_code == 0, result.output
        assert "No MST instances are operational" in result.output
