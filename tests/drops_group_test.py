import os
import sys
import importlib

import shutil
from click.testing import CliRunner
from utilities_common.cli import UserCache

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import show.main as show
import clear.main as clear

expected_counter_capabilities = """\
Counter Type           Total
-------------------  -------
PORT_INGRESS_DROPS         4
SWITCH_EGRESS_DROPS        2

PORT_INGRESS_DROPS
        IP_HEADER_ERROR
        NO_L3_HEADER

SWITCH_EGRESS_DROPS
        ACL_ANY
        L2_ANY
        L3_ANY
"""

expected_counter_configuration = """\
Counter            Alias              Group         Type                 Reasons    Description
-----------------  -----------------  ------------  -------------------  ---------  --------------------------------------------------
DEBUG_0            DEBUG_0            N/A           PORT_INGRESS_DROPS   None       N/A
DEBUG_1            SWITCH_DROPS       PACKET_DROPS  SWITCH_EGRESS_DROPS  None       Outgoing packet drops, tracked at the switch level
DEBUG_2            DEBUG_2            N/A           PORT_INGRESS_DROPS   None
lowercase_counter  lowercase_counter  N/A           SWITCH_EGRESS_DROPS  None       N/A
"""

expected_counter_configuration_with_group = """\
Counter    Alias         Group         Type                 Reasons    Description
---------  ------------  ------------  -------------------  ---------  --------------------------------------------------
DEBUG_1    SWITCH_DROPS  PACKET_DROPS  SWITCH_EGRESS_DROPS  None       Outgoing packet drops, tracked at the switch level
"""

expected_counts = """\
    IFACE    STATE    RX_ERR    RX_DROPS    TX_ERR    TX_DROPS    DEBUG_0    DEBUG_2
---------  -------  --------  ----------  --------  ----------  ---------  ---------
Ethernet0        D        10         100         0           0         80         20
Ethernet4      N/A         0        1000         0           0        800        100
Ethernet8      N/A       100          10         0           0         10          0

          DEVICE    SWITCH_DROPS    lowercase_counter
----------------  --------------  -------------------
sonic_drops_test            1000                    0
"""

expected_counts_voq = """\
       SWITCH-ID    PKT_INTEGRITY_ERR
----------------  -------------------
sonic_drops_test                  500

    IFACE    STATE    RX_ERR    RX_DROPS    TX_ERR    TX_DROPS    DEBUG_0    DEBUG_2
---------  -------  --------  ----------  --------  ----------  ---------  ---------
Ethernet0        D        10         100         0           0         80         20
Ethernet4      N/A         0        1000         0           0        800        100
Ethernet8      N/A       100          10         0           0         10          0

          DEVICE    SWITCH_DROPS    lowercase_counter
----------------  --------------  -------------------
sonic_drops_test            1000                    0
"""
expected_counts_with_group = """
          DEVICE    SWITCH_DROPS
----------------  --------------
sonic_drops_test            1000
"""

expected_counts_with_type = """\
    IFACE    STATE    RX_ERR    RX_DROPS    DEBUG_0    DEBUG_2
---------  -------  --------  ----------  ---------  ---------
Ethernet0        D        10         100         80         20
Ethernet4      N/A         0        1000        800        100
Ethernet8      N/A       100          10         10          0
"""

expected_counts_with_clear = """\
    IFACE    STATE    RX_ERR    RX_DROPS    TX_ERR    TX_DROPS    DEBUG_0    DEBUG_2
---------  -------  --------  ----------  --------  ----------  ---------  ---------
Ethernet0        D         0           0         0           0          0          0
Ethernet4      N/A         0           0         0           0          0          0
Ethernet8      N/A         0           0         0           0          0          0

          DEVICE    SWITCH_DROPS    lowercase_counter
----------------  --------------  -------------------
sonic_drops_test               0                    0
"""


def remove_tmp_dropstat_file():
    # remove the tmp portstat
    cache = UserCache("dropstat")
    cache.remove_all()

class TestDropCounters(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        remove_tmp_dropstat_file()
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_capabilities(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["capabilities"], [])
        print(result.output)
        assert result.output == expected_counter_capabilities

    def test_show_configuration(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["configuration"], [])
        print(result.output)
        assert result.output == expected_counter_configuration

    def test_show_configuration_with_group(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["configuration"], ["-g", "PACKET_DROPS"])
        print(result.output)
        assert result.output == expected_counter_configuration_with_group

    def test_show_counts(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["counts"], [])
        print(result.output)
        assert result.output == expected_counts

    def test_show_counts_voq(self):
        runner = CliRunner()
        os.environ["VOQ_DROP_COUNTER_TESTING"] = "1"
        result = runner.invoke(show.cli.commands["dropcounters"].commands["counts"], [])
        os.environ["VOQ_DROP_COUNTER_TESTING"] = "0"
        print(result.output)
        assert result.output == expected_counts_voq

    def test_show_counts_with_group(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["counts"], ["-g", "PACKET_DROPS"])
        print(result.output)
        assert result.output == expected_counts_with_group

    def test_show_counts_with_type(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["counts"], ["-t", "PORT_INGRESS_DROPS"])
        print(result.output)
        assert result.output == expected_counts_with_type

    def test_show_counts_with_clear(self):
        runner = CliRunner()
        runner.invoke(clear.cli.commands["dropcounters"])
        result = runner.invoke(show.cli.commands["dropcounters"].commands["counts"], [])
        print(result.output)
        assert result.output == expected_counts_with_clear

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"


class TestDropCountersMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        remove_tmp_dropstat_file()
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import show.dropcounters
        importlib.reload(show.dropcounters)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_show_capabilities(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["capabilities"], ['-n', 'asic0'])
        print(result.output)
        assert result.output == "For namespace: asic0\n" + expected_counter_capabilities

    def test_show_configuration(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["configuration"], ['-n', 'asic0'])
        print(result.output)
        assert result.output == "For namespace: asic0\n" + expected_counter_configuration

    def test_show_configuration_with_group(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["dropcounters"].commands["configuration"],
                               ["-g", "PACKET_DROPS", '-n', 'asic0'])
        print(result.output)
        assert result.output == "For namespace: asic0\n" + expected_counter_configuration_with_group

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()
