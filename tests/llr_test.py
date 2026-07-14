import json
import os
import re
import sys

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

import pytest  # noqa: E402
from unittest import mock  # noqa: E402

from click.testing import CliRunner  # noqa: E402
from utilities_common.db import Db  # noqa: E402
from utilities_common.cli import UserCache  # noqa: E402

import show.main as show  # noqa: E402
import config.main as config  # noqa: E402
import counterpoll.main as counterpoll  # noqa: E402
import clear.main as clear  # noqa: E402


###############################################################################
# Helpers
###############################################################################

def _make_config_obj():
    """Return a context object matching what config/main.py injects."""
    return Db()


def _del_llr_cached_stats():
    """Remove cached llrstat baseline files."""
    cache = UserCache("llrstat")
    cache.remove_all()


###############################################################################
# show llr interface
###############################################################################

class TestShowLlrInterface(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_llr_interface_all(self):
        """All interfaces — both Ethernet0/4 from APPL_DB and Ethernet8 from CONFIG_DB."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["interface"], []
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "Ethernet4" in result.output
        assert "Ethernet8" in result.output
        assert "static" in result.output
        assert "enabled" in result.output
        assert "disabled" in result.output
        assert "llr_800000_40m_profile" in result.output
        assert "llr_400000_5m_profile" in result.output

    def test_show_llr_interface_specific(self):
        """Single port filter — only Ethernet0 rows present."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["interface"], ["Ethernet0"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "Ethernet4" not in result.output
        assert "llr_800000_40m_profile" in result.output

    def test_show_llr_interface_config_db_only(self):
        """Port in CONFIG_DB but not APPL_DB — profile shows as dash."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["interface"], ["Ethernet8"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet8" in result.output
        assert "static" in result.output
        # Profile column should show "-" for CONFIG_DB-only entries
        eth8_lines = [line for line in result.output.split('\n') if 'Ethernet8' in line]
        assert any('-' in line for line in eth8_lines)

    def test_show_llr_interface_invalid(self):
        """Invalid interface — error message, no traceback."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["interface"], ["EthernetXXX"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "not found" in result.output
        assert "EthernetXXX" in result.output


###############################################################################
# show llr profile
###############################################################################

class TestShowLlrProfile(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_llr_profile_all(self):
        """Both profiles must appear with key attributes."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["profile"], []
        )
        print(result.output)
        assert result.exit_code == 0
        assert "llr_800000_40m_profile" in result.output
        assert "llr_400000_5m_profile" in result.output
        assert "264" in result.output    # max_outstanding_frames for 800G profile
        assert "115" in result.output    # max_outstanding_frames for 400G profile
        assert "135000" in result.output  # max_outstanding_bytes for 800G
        assert "best_effort" in result.output

    def test_show_llr_profile_specific(self):
        """Single profile filter — only 800G profile rows."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["profile"],
            ["llr_800000_40m_profile"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "llr_800000_40m_profile" in result.output
        assert "llr_400000_5m_profile" not in result.output
        assert "264" in result.output

    def test_show_llr_profile_invalid(self):
        """Nonexistent profile — error message."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["profile"],
            ["nonexistent_profile"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "not found" in result.output


###############################################################################
# show llr counters
###############################################################################

class TestShowLlrCounters(object):
    @classmethod
    def setup_class(cls):
        cls._original_path = os.environ.get("PATH", "")
        if scripts_path not in cls._original_path.split(os.pathsep):
            os.environ["PATH"] = cls._original_path + os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        _del_llr_cached_stats()

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = cls._original_path
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_llr_counters_all(self):
        """Counter summary for all configured ports."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["counters"], []
        )
        print(result.output)
        assert result.exit_code == 0
        # Both ports present in output
        assert "Ethernet0" in result.output
        assert "Ethernet4" in result.output
        # Known TX counter values for Ethernet0 — scoped to Ethernet0 rows
        eth0_lines = [line for line in result.output.split('\n') if 'Ethernet0' in line]
        assert any('15000' in line for line in eth0_lines), "15000 not found in Ethernet0 row"
        assert any('35000' in line for line in eth0_lines), "35000 not found in Ethernet0 row"
        # Unsupported RX counters shown as N/A
        assert "N/A" in result.output

    def test_show_llr_counters_interface(self):
        """Counter summary filtered to a single port via --interface."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["counters"],
            ["--interface", "Ethernet0"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "Ethernet4" not in result.output
        assert "N/A" in result.output

    def test_show_llr_counters_invalid_interface(self):
        """Counter summary for a port not in LLR config — error message."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["counters"],
            ["--interface", "EthernetXXX"]
        )
        print(result.output)
        assert "not found" in result.output


###############################################################################
# show llr counters detailed
###############################################################################

class TestShowLlrCountersDetailed(object):
    @classmethod
    def setup_class(cls):
        cls._original_path = os.environ.get("PATH", "")
        if scripts_path not in cls._original_path.split(os.pathsep):
            os.environ["PATH"] = cls._original_path + os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        _del_llr_cached_stats()

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = cls._original_path
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_llr_counters_detailed_all(self):
        """Detailed counters for all ports."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["counters"].commands["detailed"], []
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "Ethernet4" in result.output
        # A few label strings that appear in detailed output
        assert "LLR_INIT" in result.output
        assert "N/A" in result.output      # unsupported counters

    def test_show_llr_counters_detailed_interface(self):
        """Detailed counters for a specific port."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["counters"].commands["detailed"],
            ["Ethernet0"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "LLR Counters - Ethernet0" in result.output
        assert "Ethernet4" not in result.output
        # TX counters are all supported → values appear in the Ethernet0 section.
        # Only Ethernet0 is displayed so any line containing these values is in scope.
        assert re.search(r'\b15000\b', result.output), "15000 not found in detailed output"
        assert re.search(r'\b35000\b', result.output), "35000 not found in detailed output"
        # RX counters beyond first 4 are not supported → N/A
        assert "N/A" in result.output

    def test_show_llr_counters_detailed_invalid_interface(self):
        """Detailed counters for unknown port — error message."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["counters"].commands["detailed"],
            ["EthernetXXX"]
        )
        print(result.output)
        assert "not found" in result.output


###############################################################################
# config llr interface
###############################################################################

class TestConfigLlrInterface(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    @pytest.mark.parametrize("state", ["enabled", "disabled"])
    def test_config_llr_interface_local(self, state):
        """config llr interface local <Ethernet0> {enabled|disabled}."""
        runner = CliRunner()
        obj = _make_config_obj()
        result = runner.invoke(
            config.config.commands["llr"].commands["interface"].commands["local"],
            ["Ethernet0", state],
            obj=obj
        )
        print(result.output)
        assert result.exit_code == 0
        table = obj.cfgdb.get_table("LLR_PORT")
        assert table.get("Ethernet0", {}).get("llr_local") == state

    @pytest.mark.parametrize("state", ["enabled", "disabled"])
    def test_config_llr_interface_remote(self, state):
        """config llr interface remote <Ethernet0> {enabled|disabled}."""
        runner = CliRunner()
        obj = _make_config_obj()
        result = runner.invoke(
            config.config.commands["llr"].commands["interface"].commands["remote"],
            ["Ethernet0", state],
            obj=obj
        )
        print(result.output)
        assert result.exit_code == 0
        table = obj.cfgdb.get_table("LLR_PORT")
        assert table.get("Ethernet0", {}).get("llr_remote") == state

    def test_config_llr_interface_mode(self):
        """config llr interface mode <Ethernet0> static."""
        runner = CliRunner()
        obj = _make_config_obj()
        result = runner.invoke(
            config.config.commands["llr"].commands["interface"].commands["mode"],
            ["Ethernet0", "static"],
            obj=obj
        )
        print(result.output)
        assert result.exit_code == 0
        table = obj.cfgdb.get_table("LLR_PORT")
        assert table.get("Ethernet0", {}).get("llr_mode") == "static"

    def test_config_llr_no_capability(self):
        """Capability absent - command must error with 'not supported'."""
        runner = CliRunner()
        obj = _make_config_obj()
        with mock.patch("config.llr.is_llr_capable", return_value=False):
            result = runner.invoke(
                config.config.commands["llr"].commands["interface"].commands["mode"],
                ["Ethernet0", "static"],
                obj=obj
            )
        print(result.output)
        assert result.exit_code != 0
        assert "not supported" in result.output

    def test_config_llr_invalid_interface(self):
        """Invalid port - command must error with 'does not exist'."""
        runner = CliRunner()
        obj = _make_config_obj()
        result = runner.invoke(
            config.config.commands["llr"].commands["interface"].commands["mode"],
            ["EthernetXXX", "static"],
            obj=obj
        )
        print(result.output)
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_config_llr_local_remote_mode_validation(self):
        """local/remote: allowed when mode absent (YANG default static),
        rejected when mode is non-static."""
        runner = CliRunner()

        # --- mode absent → defaults to static, should succeed ---
        obj = _make_config_obj()
        obj.cfgdb.mod_entry("LLR_PORT", "Ethernet0", None)
        for subcmd in ("local", "remote"):
            result = runner.invoke(
                config.config.commands["llr"].commands["interface"].commands[subcmd],
                ["Ethernet0", "enabled"],
                obj=obj
            )
            print(result.output)
            assert result.exit_code == 0, \
                "{} should succeed when llr_mode is absent".format(subcmd)

        # --- mode explicitly non-static → should error ---
        obj = _make_config_obj()
        obj.cfgdb.mod_entry("LLR_PORT", "Ethernet0",
                            {"llr_mode": "dynamic"})
        for subcmd in ("local", "remote"):
            result = runner.invoke(
                config.config.commands["llr"].commands["interface"].commands[subcmd],
                ["Ethernet0", "enabled"],
                obj=obj
            )
            print(result.output)
            assert result.exit_code != 0, \
                "{} should fail when llr_mode is dynamic".format(subcmd)
            assert "only applicable" in result.output


###############################################################################
# counterpoll llr
###############################################################################

class TestCounterpollLlr(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    @pytest.mark.parametrize("status", ["enable", "disable"])
    def test_llr_counter_status(self, status):
        """counterpoll llr {enable|disable} updates FLEX_COUNTER_STATUS."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            counterpoll.cli.commands["llr"].commands[status], [],
            obj=db.cfgdb
        )
        print(result.output)
        assert result.exit_code == 0
        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        assert table.get("LLR", {}).get("FLEX_COUNTER_STATUS") == status

    def test_llr_counter_interval_valid(self):
        """counterpoll llr interval 10000 — accepted within range."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            counterpoll.cli.commands["llr"].commands["interval"],
            ["10000"],
            obj=db.cfgdb
        )
        print(result.output)
        assert result.exit_code == 0
        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        assert table.get("LLR", {}).get("POLL_INTERVAL") == "10000"

    def test_llr_counter_interval_too_low(self):
        """counterpoll llr interval 50 — rejected (below 100 ms minimum)."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            counterpoll.cli.commands["llr"].commands["interval"],
            ["50"],
            obj=db.cfgdb
        )
        print(result.output)
        assert result.exit_code == 2

    def test_llr_counter_interval_too_high(self):
        """counterpoll llr interval 40000 — rejected (above 30000 ms maximum)."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            counterpoll.cli.commands["llr"].commands["interval"],
            ["40000"],
            obj=db.cfgdb
        )
        print(result.output)
        assert result.exit_code == 2

    def test_counterpoll_show_includes_llr(self):
        """counterpoll show lists LLR_STAT with configured interval."""
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["show"], [])
        print(result.output)
        assert result.exit_code == 0
        assert "LLR_STAT" in result.output
        assert re.search(r'LLR_STAT.*10000', result.output), "LLR_STAT row does not contain 10000"

    def test_counterpoll_llr_no_capability(self):
        """counterpoll llr enable rejects when LLR_CAPABLE is not true."""
        runner = CliRunner()
        with mock.patch("counterpoll.main.is_llr_capable", return_value=False):
            result = runner.invoke(
                counterpoll.cli.commands["llr"], ["enable"]
            )
        print(result.output)
        assert result.exit_code != 0
        assert "not supported" in result.output


###############################################################################
# sonic-clear llr counters
###############################################################################

class TestClearLlrCounters(object):
    @classmethod
    def setup_class(cls):
        cls._original_path = os.environ.get("PATH", "")
        if scripts_path not in cls._original_path.split(os.pathsep):
            os.environ["PATH"] = cls._original_path + os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        _del_llr_cached_stats()

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = cls._original_path
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        _del_llr_cached_stats()

    def test_clear_llr_counters_all(self):
        """sonic-clear llr counters — clear all ports."""
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["llr"].commands["counters"], []
        )
        print(result.output)
        assert result.exit_code == 0
        assert "LLR counters cleared" in result.output

    def test_clear_llr_counters_interface(self):
        """sonic-clear llr counters interface Ethernet0 — clear single port."""
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["llr"].commands["counters"].commands["interface"],
            ["Ethernet0"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "LLR counters cleared for Ethernet0" in result.output

    def test_clear_llr_counters_interface_invalid(self):
        """sonic-clear llr counters interface EthernetXXX — error for unknown port."""
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["llr"].commands["counters"].commands["interface"],
            ["EthernetXXX"]
        )
        print(result.output)
        assert "not found" in result.output

    def test_clear_llr_counters_interface_preserves_others(self):
        """A per-interface clear must refresh only that interface's baseline
        and leave the other interfaces' cached baseline untouched."""
        runner = CliRunner()

        # Start from a clean cache so this test is self-contained.
        _del_llr_cached_stats()
        try:
            # Clear all first so the baseline holds every LLR port.
            result = runner.invoke(
                clear.cli.commands["llr"].commands["counters"], []
            )
            print(result.output)
            assert result.exit_code == 0

            baseline_file = os.path.join(
                UserCache("llrstat").get_directory(), "llrstat"
            )
            with open(baseline_file) as f:
                baseline_all = json.load(f)
            assert "Ethernet0" in baseline_all
            assert "Ethernet4" in baseline_all

            # Overwrite both interfaces' cached values with a recognizable
            # sentinel so we can tell which entries actually get refreshed by
            # the subsequent per-interface clear.  A string marker is used
            # deliberately: real counter values are numeric, so the sentinel
            # can never collide with a re-snapshotted value.
            sentinel = {k: "SENTINEL" for k in baseline_all["Ethernet0"]}
            assert sentinel, "expected non-empty LLR counters in the baseline"
            baseline_all["Ethernet0"] = dict(sentinel)
            baseline_all["Ethernet4"] = dict(sentinel)
            with open(baseline_file, "w") as f:
                json.dump(baseline_all, f)

            # Clear only Ethernet0.
            result = runner.invoke(
                clear.cli.commands["llr"].commands["counters"].commands["interface"],
                ["Ethernet0"]
            )
            print(result.output)
            assert result.exit_code == 0

            with open(baseline_file) as f:
                baseline_after = json.load(f)
            # Ethernet4 must be preserved and untouched,
            assert baseline_after.get("Ethernet4") == sentinel

            # Ethernet0 must have been refreshed to the real counter values.
            assert "Ethernet0" in baseline_after
            assert baseline_after["Ethernet0"] != sentinel
        finally:
            _del_llr_cached_stats()


###############################################################################
# Multi-ASIC tests
###############################################################################

class TestLlrMultiAsic(object):
    """Tests for `-n/--namespace` plumbing on a multi-asic platform.

    asic0 has LLR configuration (Ethernet0 in static mode); asic1 has none.
    """

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        # Switch the process into multi-asic state (patches
        # multi_asic.is_multi_asic, get_namespace_list, etc.)
        import importlib
        from tests.mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        # Reload mock tables with namespace config
        from tests.mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from tests.mock_tables import dbconnector
        dbconnector.load_database_config()

    def test_show_llr_interface_specific_namespace(self):
        """show llr interface -n asic0 — asic0 carries LLR config."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["interface"],
            ["-n", "asic0"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "static" in result.output

    def test_show_llr_interface_all_namespaces(self):
        """show llr interface (no -n) on multi-asic — iterates per-asic."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["interface"], []
        )
        print(result.output)
        assert result.exit_code == 0
        # Output should be tagged with the namespace name on multi-asic
        assert "asic0" in result.output
        assert "Ethernet0" in result.output

    def test_show_llr_profile_namespace(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["llr"].commands["profile"],
            ["-n", "asic0"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert "llr_800000_40m_profile" in result.output
        assert "264" in result.output           # max_outstanding_frames
        assert "135000" in result.output        # max_outstanding_bytes
        assert "2048" in result.output          # ctlos_spacing_bytes
        assert "best_effort" in result.output   # init_action / flush_action

    def test_config_llr_mode_namespace(self):
        """config llr interface mode Ethernet0 static -n asic0."""
        runner = CliRunner()
        obj = _make_config_obj()
        result = runner.invoke(
            config.config.commands["llr"].commands["interface"].commands["mode"],
            ["Ethernet0", "static", "-n", "asic0"],
            obj=obj
        )
        print(result.output)
        assert result.exit_code == 0
        cfgdb = obj.cfgdb_clients["asic0"]
        assert cfgdb.get_entry("LLR_PORT", "Ethernet0").get("llr_mode") == "static"

    def test_counterpoll_llr_namespace(self):
        """counterpoll llr enable -n asic0 — namespace option on the group."""
        runner = CliRunner()
        result = runner.invoke(
            counterpoll.cli.commands["llr"],
            ["-n", "asic0", "enable"]
        )
        print(result.output)
        assert result.exit_code == 0

    def test_clear_llr_counters_namespace(self):
        """sonic-clear llr counters -n asic0 — forwards -n to llrstat."""
        _del_llr_cached_stats()
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["llr"].commands["counters"],
            ["-n", "asic0"]
        )
        print(result.output)
        assert result.exit_code == 0

    def test_clear_llr_counters_all_namespaces(self):
        """sonic-clear llr counters (no -n) iterates all namespaces.

        On our mock multi-asic topology, only asic0 has LLR_PORT_TABLE entries,
        so clear output must include the asic0 namespace header and clear success.
        """
        _del_llr_cached_stats()
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["llr"].commands["counters"],
            []
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Namespace: asic0" in result.output
        assert "LLR counters cleared." in result.output
