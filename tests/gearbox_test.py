import sys
import os
import json
import subprocess
import importlib.machinery
import importlib.util
from contextlib import redirect_stdout
from io import StringIO
from click.testing import CliRunner
from unittest import TestCase, mock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

from .mock_tables import dbconnector
from utilities_common.cli import UserCache  # noqa: E402

import show.main as show

# Load gearboxutil script as a module for direct function testing
# spec_from_file_location returns None for extensionless scripts; use SourceFileLoader explicitly
_gearboxutil_loader = importlib.machinery.SourceFileLoader(
    "gearboxutil", os.path.join(scripts_path, "gearboxutil"))
_gearboxutil_spec = importlib.util.spec_from_loader("gearboxutil", _gearboxutil_loader)
gearboxutil = importlib.util.module_from_spec(_gearboxutil_spec)
_gearboxutil_loader.exec_module(gearboxutil)


def _gearbox_snapshot_path():
    return os.path.join(UserCache("portstat").get_directory(), "gearbox")


def _remove_gearbox_snapshot():
    if os.path.exists(_gearbox_snapshot_path()):
        os.remove(_gearbox_snapshot_path())


class TestGearbox(TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def setUp(self):
        self.runner = CliRunner()

    def test_gearbox_phys_status_validation(self):
        result = self.runner.invoke(show.cli.commands["gearbox"].commands["phys"].commands["status"], [])
        print(result.output, file=sys.stderr)
        expected_output = (
            "PHY Id     Name    Firmware\n"
            "--------  -------  ----------\n"
            "       1  sesto-1        v0.2\n"
            "       2  sesto-2        v0.3"
        )
        self.assertEqual(result.output.strip(), expected_output)

    def test_gearbox_interfaces_status_validation(self):
        result = self.runner.invoke(show.cli.commands["gearbox"].commands["interfaces"].commands["status"], [])
        print(result.output, file=sys.stderr)
        expected_output = (
            "PHY Id    Interface        MAC Lanes    MAC Lane Speed        PHY Lanes    PHY Lane Speed    Line Lanes    Line Lane Speed    Oper    Admin\n"
            "--------  -----------  ---------------  ----------------  ---------------  ----------------  ------------  -----------------  ------  -------\n"
            "       1  Ethernet200  200,201,202,203               25G  300,301,302,303               25G       304,305                50G    down       up"
        )
        self.assertEqual(result.output.strip(), expected_output)

    def test_gearbox_interfaces_fec_stats(self):
        result = self.runner.invoke(
            show.cli.commands["gearbox"].commands["interfaces"].commands["fec-stats"], ["Ethernet0"])
        print(result.output, file=sys.stderr)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("FEC_CORR", result.output)
        self.assertIn("Ethernet0 Line", result.output)
        self.assertIn("Ethernet0 System", result.output)

    def test_gearbox_interfaces_fec_histogram(self):
        result = self.runner.invoke(
            show.cli.commands["gearbox"].commands["interfaces"].commands["fec-histogram"], ["Ethernet0"])
        print(result.output, file=sys.stderr)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Ethernet0", result.output)
        self.assertIn("BIN0", result.output)
        self.assertIn("BIN15", result.output)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"


class TestFormatBer(TestCase):
    def test_normal_value(self):
        self.assertEqual(gearboxutil.format_ber("6.05e-10"), "6.05e-10")

    def test_small_nonzero_value(self):
        self.assertEqual(gearboxutil.format_ber("0.000000000605"), "6.05e-10")

    def test_zero(self):
        self.assertEqual(gearboxutil.format_ber("0"), "0.00e+00")

    def test_na_passthrough(self):
        self.assertEqual(gearboxutil.format_ber("N/A"), "N/A")

    def test_minus_one_passthrough(self):
        self.assertEqual(gearboxutil.format_ber("-1"), "-1")

    def test_non_numeric_passthrough(self):
        self.assertEqual(gearboxutil.format_ber("invalid"), "invalid")


class TestInterfaceFecStats(TestCase):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        dbconnector.load_database_config()
        # These tests expect lifetime values; drop any snapshot left by an earlier 'portstat -c'
        _remove_gearbox_snapshot()

    def _capture(self, port_name=None, display_type='stats'):
        buf = StringIO()
        with redirect_stdout(buf):
            gearboxutil.InterfaceFecStats(port_name=port_name, display_type=display_type)
        return buf.getvalue()

    def test_fec_stats_all_ports_headers(self):
        output = self._capture(display_type='stats')
        for col in ['GB IFACE', 'STATE', 'FEC_CORR', 'FEC_UNCORR', 'FEC_SYMBOL_ERR',
                    'FEC_PRE_BER', 'FEC_POST_BER', 'FEC_PRE_BER_MAX', 'FEC_MAX_T']:
            self.assertIn(col, output)

    def test_fec_stats_all_ports_contains_ethernet0(self):
        output = self._capture(display_type='stats')
        self.assertIn("Ethernet0", output)

    def test_fec_stats_formatted_ber(self):
        output = self._capture(display_type='stats')
        self.assertIn("6.05e-10", output)

    def test_fec_stats_specific_port(self):
        output = self._capture(port_name="Ethernet0", display_type='stats')
        self.assertIn("Ethernet0", output)
        self.assertIn("FEC_CORR", output)

    def test_fec_stats_invalid_port(self):
        output = self._capture(port_name="EthernetInvalid", display_type='stats')
        self.assertIn("Error", output)
        self.assertIn("EthernetInvalid", output)

    def test_fec_stats_state_uses_system_and_line_oper_status(self):
        # Mock has system_oper_status=up -> 'U' and line_oper_status=down -> 'D'
        # Verifies get_port_state reads the correct per-side field, not generic oper_status
        output = self._capture(port_name="Ethernet0", display_type='stats')
        lines = [row for row in output.splitlines() if "Ethernet0" in row]
        system_line = next((row for row in lines if "System" in row), None)
        line_line = next((row for row in lines if "Line" in row), None)
        self.assertIsNotNone(system_line, "Expected a System row in fec-stats output")
        self.assertIsNotNone(line_line, "Expected a Line row in fec-stats output")
        self.assertIn("U", system_line, "System side should show U (system_oper_status=up)")
        self.assertIn("D", line_line, "Line side should show D (line_oper_status=down)")

    def test_fec_histogram_all_ports_bins(self):
        output = self._capture(display_type='histogram')
        self.assertIn("Ethernet0", output)
        for i in range(16):
            self.assertIn(f"BIN{i}", output)

    def test_fec_histogram_specific_port(self):
        output = self._capture(port_name="Ethernet0", display_type='histogram')
        self.assertIn("Ethernet0", output)
        self.assertIn("BIN0", output)

    def test_fec_histogram_invalid_port(self):
        output = self._capture(port_name="EthernetInvalid", display_type='histogram')
        self.assertIn("Error", output)

    def test_fec_histogram_last_updated_header(self):
        output = self._capture(port_name="Ethernet0", display_type='histogram')
        self.assertIn("Last Updated", output)

    def test_fec_histogram_timestamp_formatted(self):
        # Mock has S0_TIMESTAMP set to a non-zero ms value; format it the same way the script does
        from datetime import datetime as _dt
        ts_ms = 1716579600000
        expected = _dt.fromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
        output = self._capture(port_name="Ethernet0", display_type='histogram')
        self.assertIn(expected, output)

    def test_fec_histogram_zero_and_missing_timestamps_render_na(self):
        # S1_TIMESTAMP is "0" (sentinel) and S2..S15 have no *_TIMESTAMP entry; all must render as N/A
        output = self._capture(port_name="Ethernet0", display_type='histogram')
        self.assertIn("N/A", output)

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"


def _fec_rows(output):
    """Return {'<port> <side>': [columns after the interface name]} from fec-stats output"""
    rows = {}
    for line in output.splitlines():
        if line.startswith("Ethernet"):
            tokens = line.split()
            rows[" ".join(tokens[:2])] = tokens[2:]
    return rows


class TestGearboxCountersSinceClear(TestCase):
    """'sonic-clear counters' (portstat -c) saves the gearbox FEC counters; gearboxutil shows them relative to it"""

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        dbconnector.load_database_config()

    def setUp(self):
        _remove_gearbox_snapshot()

    def tearDown(self):
        _remove_gearbox_snapshot()

    def _show(self, display_type, port_name="Ethernet0"):
        buf = StringIO()
        with redirect_stdout(buf):
            gearboxutil.InterfaceFecStats(port_name=port_name, display_type=display_type)
        return buf.getvalue()

    def _write_snapshot(self, ports, namespace=""):
        with open(_gearbox_snapshot_path(), "w") as f:
            json.dump({"time": "2026-11-17T10:00:00", "namespaces": {namespace: ports}}, f)

    def test_no_snapshot_shows_lifetime_values(self):
        output = self._show("stats")
        self.assertNotIn("Last cached time", output)
        system = _fec_rows(output)["Ethernet0 System"]
        self.assertEqual(system[1], "1,234,567")
        self.assertEqual(system[-1], "42")

    def test_after_portstat_clear_counters_are_zero(self):
        env = dict(os.environ, UTILITIES_UNIT_TESTING="2")
        subprocess.run([sys.executable, os.path.join(scripts_path, "portstat"), "-c"],
                       env=env, check=True, capture_output=True)

        stats = self._show("stats")
        self.assertIn("Last cached time was", stats)
        for side, columns in _fec_rows(stats).items():
            self.assertEqual(columns[1:4], ["0", "0", "0"], side)
            self.assertEqual(columns[-1], "-1", side)

        histogram = self._show("histogram")
        bins = [line.split() for line in histogram.splitlines() if line.startswith("BIN")]
        self.assertEqual(len(bins), 32)  # 16 bins x (system, line)
        self.assertTrue(all(row[1] == "0" for row in bins))

    def test_counters_since_snapshot(self):
        # 100 corrected frames, and codewords in BIN0/BIN1, on the system side since the clear
        self._write_snapshot({
            "Ethernet0_system": {
                "SAI_PORT_STAT_IF_IN_FEC_CORRECTABLE_FRAMES": "1234467",
                "SAI_PORT_STAT_IF_IN_FEC_NOT_CORRECTABLE_FRAMES": "3",
                "SAI_PORT_STAT_IF_IN_FEC_SYMBOL_ERRORS": "1024",
                "SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S0": "26751321840084",
                "SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S1": "5600",
            },
        })
        rows = _fec_rows(self._show("stats"))
        self.assertEqual(rows["Ethernet0 System"][1:4], ["100", "0", "0"])
        self.assertEqual(rows["Ethernet0 System"][-1], "1")
        # A port missing from the snapshot is shown against zero
        self.assertEqual(rows["Ethernet0 Line"][-1], "0")

        system_histogram = self._show("histogram").split("Ethernet0 System")[1]
        bin1 = next(line.split() for line in system_histogram.splitlines() if line.startswith("BIN1 "))
        self.assertEqual(bin1[1], "78")

    def test_snapshot_of_another_namespace_is_ignored(self):
        self._write_snapshot({"Ethernet0_system": {}}, namespace="asic0")
        self.assertNotIn("Last cached time", self._show("stats"))

    def test_snapshot_of_selected_namespace_is_used(self):
        # A namespace-aware gearboxutil sets InterfaceFecStats.namespace; that namespace's snapshot is used
        self._write_snapshot({"Ethernet0_system": {"SAI_PORT_STAT_IF_IN_FEC_CORRECTABLE_FRAMES": "1234467"}},
                             namespace="asic0")
        with mock.patch.object(gearboxutil.InterfaceFecStats, "namespace", "asic0", create=True):
            output = self._show("stats")
        self.assertIn("Last cached time", output)
        self.assertEqual(_fec_rows(output)["Ethernet0 System"][1], "100")

    def test_unreadable_snapshot_is_ignored(self):
        with open(_gearbox_snapshot_path(), "w") as f:
            f.write("not json")
        self.assertNotIn("Last cached time", self._show("stats"))

    def test_helpers(self):
        self.assertEqual(gearboxutil.counter_diff("150", "100"), "50")
        self.assertEqual(gearboxutil.counter_diff("100", None), "100")
        self.assertEqual(gearboxutil.counter_diff("10", "100"), "0")
        self.assertEqual(gearboxutil.counter_diff("N/A", "100"), "N/A")

        def bins(values):
            return {gearboxutil.FEC_HISTOGRAM_BINS[i]: v for i, v in enumerate(values)}
        old = bins(["100"] * 16)
        self.assertEqual(gearboxutil.get_fec_max_t_since_snapshot(bins(["100"] * 16), old, "5"), "-1")
        self.assertEqual(gearboxutil.get_fec_max_t_since_snapshot(
            bins(["200"] + ["100"] * 6 + ["101"] + ["100"] * 8), old, "5"), "7")
        self.assertEqual(gearboxutil.get_fec_max_t_since_snapshot({}, old, "5"), "5")

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
