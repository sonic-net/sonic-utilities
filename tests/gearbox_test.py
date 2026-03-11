import sys
import os
import importlib.util
from contextlib import redirect_stdout
from io import StringIO
from click.testing import CliRunner
from unittest import TestCase

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

from .mock_tables import dbconnector

import show.main as show

# Load gearboxutil script as a module for direct function testing
_gearboxutil_spec = importlib.util.spec_from_file_location(
    "gearboxutil", os.path.join(scripts_path, "gearboxutil"))
gearboxutil = importlib.util.module_from_spec(_gearboxutil_spec)
_gearboxutil_spec.loader.exec_module(gearboxutil)

class TestGearbox(TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
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

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
