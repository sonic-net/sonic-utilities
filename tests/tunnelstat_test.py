import sys
import os
import traceback

from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import clear.main as clear
import show.main as show
from .mock_tables import dbconnector

show_vxlan_counters_output = """\
  IFACE    RX_PKTS    RX_BYTES      RX_PPS    TX_PKTS    TX_BYTES    TX_PPS
-------  ---------  ----------  ----------  ---------  ----------  --------
  vtep1        452       81922  20523.00/s        154       23434  201.00/s
"""

show_vxlan_counters_clear_output = """\
  IFACE    RX_PKTS    RX_BYTES      RX_PPS    TX_PKTS    TX_BYTES    TX_PPS
-------  ---------  ----------  ----------  ---------  ----------  --------
  vtep1          0           0  20523.00/s          0           0  201.00/s
"""

show_vxlan_counters_interface_output = """\
vtep1
-----

        RX:
               452 packets
             81922 bytes
        TX:
               154 packets
             23434 bytes
"""

show_vxlan_counters_clear_interface_output = """\
vtep1
-----

        RX:
                 0 packets
                 0 bytes
        TX:
                 0 packets
                 0 bytes
"""


class TestTunnelstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def test_no_param(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_vxlan_counters_output

    def test_single_tunnel(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], ["vtep1"])
        expected = show_vxlan_counters_interface_output
        assert result.output == expected

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["tunnelcounters"], [])
        print(result.stdout)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], [])
        print(result.stdout)
        expected = show_vxlan_counters_clear_output

        # remove the counters snapshot
        show.run_command(['tunnelstat', '-D'])
        for line in expected:
            assert line in result.output

    def test_clear_interface(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["tunnelcounters"], [])
        print(result.stdout)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], ["vtep1"])
        print(result.stdout)
        expected = show_vxlan_counters_clear_interface_output

        # remove the counters snapshot
        show.run_command(['tunnelstat', '-D'])
        for line in expected:
            assert line in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
