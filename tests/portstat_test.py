import os
import shutil

from click.testing import CliRunner

import clear.main as clear
import show.main as show
from .utils import get_result_and_return_code
from utilities_common.cli import UserCache

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

intf_counters_before_clear = """\
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------  --------  --------  --------
Ethernet0        D        8  2000.00 MB/s     64.00%        10       100       N/A       10  1500.00 MB/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        4   204.80 KB/s        N/A         0     1,000       N/A       40   204.85 KB/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        6  1350.00 KB/s        N/A       100        10       N/A       60    13.37 MB/s        N/A       N/A       N/A       N/A
"""

intf_counters_ethernet4 = """\
    IFACE    STATE    RX_OK       RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK       TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  -----------  ---------  --------  --------  --------  -------  -----------  ---------  --------  --------  --------
Ethernet4      N/A        4  204.80 KB/s        N/A         0     1,000       N/A       40  204.85 KB/s        N/A       N/A       N/A       N/A
"""

intf_counters_all = """\
    IFACE    STATE    RX_OK        RX_BPS       RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS       TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  -----------  ---------  --------  --------  --------  -------  ------------  -----------  ---------  --------  --------  --------
Ethernet0        D        8  2000.00 MB/s  247000.00/s     64.00%        10       100       N/A       10  1500.00 MB/s  183000.00/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        4   204.80 KB/s     200.00/s        N/A         0     1,000       N/A       40   204.85 KB/s     201.00/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        6  1350.00 KB/s    9000.00/s        N/A       100        10       N/A       60    13.37 MB/s    9000.00/s        N/A       N/A       N/A       N/A
"""

intf_fec_counters = """\
    IFACE    STATE    FEC_CORR    FEC_UNCORR    FEC_SYMBOL_ERR
---------  -------  ----------  ------------  ----------------
Ethernet0        D     130,402             3                 4
Ethernet4      N/A     110,412             1                 0
Ethernet8      N/A     100,317             0                 0
"""

intf_fec_counters_fec_hist = """\
Symbol Errors Per Codeword      Codewords
----------------------------  -----------
BIN0                              1000000
BIN1                               900000
BIN2                               800000
BIN3                               700000
BIN4                               600000
BIN5                               500000
BIN6                               400000
BIN7                               300000
BIN8                                    0
BIN9                                    0
BIN10                                   0
BIN11                                   0
BIN12                                   0
BIN13                                   0
BIN14                                   0
BIN15                                   0
"""

intf_fec_counters_period = """\
The rates are calculated within 3 seconds period
    IFACE    STATE    FEC_CORR    FEC_UNCORR    FEC_SYMBOL_ERR
---------  -------  ----------  ------------  ----------------
Ethernet0        D           0             0                 0
Ethernet4      N/A           0             0                 0
Ethernet8      N/A           0             0                 0
"""

intf_counters_period = """\
The rates are calculated within 3 seconds period
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------  --------  --------  --------
Ethernet0        D        0  2000.00 MB/s     64.00%         0         0       N/A        0  1500.00 MB/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        0   204.80 KB/s        N/A         0         0       N/A        0   204.85 KB/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        0  1350.00 KB/s        N/A         0         0       N/A        0    13.37 MB/s        N/A       N/A       N/A       N/A
"""

intf_counter_after_clear = """\
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------  --------  --------  --------
Ethernet0        D        0  2000.00 MB/s     64.00%         0         0       N/A        0  1500.00 MB/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        0   204.80 KB/s        N/A         0         0       N/A        0   204.85 KB/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        0  1350.00 KB/s        N/A         0         0       N/A        0    13.37 MB/s        N/A       N/A       N/A       N/A"""

clear_counter = """\
Cleared counters"""

multi_asic_external_intf_counters = """\
    IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
Ethernet0        U        8  0.00 B/s      0.00%        10       100       N/A       10  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet4        U        4  0.00 B/s      0.00%         0     1,000       N/A       40  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

multi_asic_all_intf_counters = """\
         IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
--------------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
     Ethernet0        U        8  0.00 B/s      0.00%        10       100       N/A       10  0.00 B/s      0.00%       N/A       N/A       N/A
     Ethernet4        U        4  0.00 B/s      0.00%         0     1,000       N/A       40  0.00 B/s      0.00%       N/A       N/A       N/A
  Ethernet-BP0        U        6  0.00 B/s      0.00%         0     1,000       N/A       60  0.00 B/s      0.00%       N/A       N/A       N/A
  Ethernet-BP4        U        8  0.00 B/s      0.00%         0     1,000       N/A       80  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP256        U        8  0.00 B/s      0.00%        10       100       N/A       10  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP260        U        4  0.00 B/s      0.00%         0     1,000       N/A       40  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""
multi_asic_intf_counters_asic0 = """\
       IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
------------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
   Ethernet0        U        8  0.00 B/s      0.00%        10       100       N/A       10  0.00 B/s      0.00%       N/A       N/A       N/A
   Ethernet4        U        4  0.00 B/s      0.00%         0     1,000       N/A       40  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP0        U        6  0.00 B/s      0.00%         0     1,000       N/A       60  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP4        U        8  0.00 B/s      0.00%         0     1,000       N/A       80  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

multi_asic_external_intf_counters_printall = """\
    IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------
Ethernet0        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
Ethernet4        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

multi_asic_intf_counters_printall = """\
         IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
--------------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------
     Ethernet0        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
     Ethernet4        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
  Ethernet-BP0        U        6  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       60  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
  Ethernet-BP4        U        8  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       80  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
Ethernet-BP256        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
Ethernet-BP260        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

multi_asic_intf_counters_asic0_printall = """\
       IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
------------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------
   Ethernet0        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
   Ethernet4        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
Ethernet-BP0        U        6  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       60  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A
Ethernet-BP4        U        8  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       80  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""
multi_asic_intf_counters_period = """\
The rates are calculated within 3 seconds period
    IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
Ethernet0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

multi_asic_intf_counters_period_all = """\
The rates are calculated within 3 seconds period
         IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
--------------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
     Ethernet0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
     Ethernet4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
  Ethernet-BP0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
  Ethernet-BP4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP256        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP260        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

multi_asic_intf_counter_period_asic_all = """\
The rates are calculated within 3 seconds period
       IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
------------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
   Ethernet0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
   Ethernet4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""

mutli_asic_intf_counters_after_clear = """\
         IFACE    STATE    RX_OK    RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
--------------  -------  -------  --------  ---------  --------  --------  --------  -------  --------  ---------  --------  --------  --------
     Ethernet0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
     Ethernet4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
  Ethernet-BP0        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
  Ethernet-BP4        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP256        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A
Ethernet-BP260        U        0  0.00 B/s      0.00%         0         0       N/A        0  0.00 B/s      0.00%       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links
"""

intf_invalid_asic_error = """ValueError: Unknown Namespace asic99"""

intf_counters_detailed = """\
Packets Received 64 Octets..................... 0
Packets Received 65-127 Octets................. 0
Packets Received 128-255 Octets................ 0
Packets Received 256-511 Octets................ 0
Packets Received 512-1023 Octets............... 0
Packets Received 1024-1518 Octets.............. 0
Packets Received 1519-2047 Octets.............. 0
Packets Received 2048-4095 Octets.............. 0
Packets Received 4096-9216 Octets.............. 0
Packets Received 9217-16383 Octets............. 0

Total Packets Received Without Errors.......... 4
Unicast Packets Received....................... 4
Multicast Packets Received..................... 0
Broadcast Packets Received..................... 0

Jabbers Received............................... 0
Fragments Received............................. 0
Undersize Received............................. 0
Overruns Received.............................. 0

Packets Transmitted 64 Octets.................. 0
Packets Transmitted 65-127 Octets.............. 0
Packets Transmitted 128-255 Octets............. 0
Packets Transmitted 256-511 Octets............. 0
Packets Transmitted 512-1023 Octets............ 0
Packets Transmitted 1024-1518 Octets........... 0
Packets Transmitted 1519-2047 Octets........... 0
Packets Transmitted 2048-4095 Octets........... 0
Packets Transmitted 4096-9216 Octets........... 0
Packets Transmitted 9217-16383 Octets.......... 0

Total Packets Transmitted Successfully......... 40
Unicast Packets Transmitted.................... 40
Multicast Packets Transmitted.................. 0
Broadcast Packets Transmitted.................. 0
Time Since Counters Last Cleared............... None
"""

intf_counters_on_sup = """\
       IFACE    STATE    RX_OK     RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK     TX_BPS    TX_UTIL\
    TX_ERR    TX_DRP    TX_OVR
------------  -------  -------  ---------  ---------  --------  --------  --------  -------  ---------  ---------\
  --------  --------  --------
 Ethernet1/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s      0.00%\
         0         0         0
 Ethernet2/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s      0.00%\
         0         0         0
Ethernet11/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s      0.00%\
         0         0         0
"""

intf_counters_on_sup_no_counters = "Linecard Counter Table is not available.\n"

intf_counters_on_sup_partial_lc = "Not all linecards have published their counter values.\n"

TEST_PERIOD = 3


def remove_tmp_cnstat_file():
    # remove the tmp portstat
    cache = UserCache("portstat")
    cache.remove_all()


def verify_after_clear(output, expected_out):
    lines = output.splitlines()
    assert lines[0].startswith('Last cached time was') == True
    # ignore the first line as it has time stamp and is diffcult to compare
    new_output = '\n'.join(lines[1:])
    assert new_output == expected_out


class TestPortStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        remove_tmp_cnstat_file()

    def test_show_intf_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_before_clear

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_before_clear

    def test_show_intf_counters_ethernet4(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], ["-i", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_ethernet4

        return_code, result = get_result_and_return_code(
            ['portstat', '-i', 'Ethernet4'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_ethernet4

    def test_show_intf_counters_all(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], ["--printall"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_all

        return_code, result = get_result_and_return_code(['portstat', '-a'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_all

    def test_show_intf_fec_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["fec-stats"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_fec_counters

        return_code, result = get_result_and_return_code(['portstat', '-f'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_fec_counters

    def test_show_intf_counters_fec_histogram(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["fec-histogram"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_fec_counters_fec_hist

    def test_show_intf_fec_counters_period(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["fec-stats"],
                                ["-p {}".format(TEST_PERIOD)])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_fec_counters_period

        return_code, result = get_result_and_return_code(
            ['portstat', '-f', '-p', str(TEST_PERIOD)])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_fec_counters_period



    def test_show_intf_counters_period(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"], [
                               "-p {}".format(TEST_PERIOD)])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_period

        return_code, result = get_result_and_return_code(
            ['portstat', '-p', str(TEST_PERIOD)])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_period

    def test_show_intf_counters_detailed(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["detailed"], ["Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_detailed

        return_code, result = get_result_and_return_code(['portstat', '-l', '-i', 'Ethernet4'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_detailed

    def test_clear_intf_counters(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.rstrip() == clear_counter

        return_code, result = get_result_and_return_code(['portstat', '-c'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result.rstrip() == clear_counter

        # check counters after clear
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        verify_after_clear(result.output, intf_counter_after_clear)

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        verify_after_clear(result, intf_counter_after_clear)

    def test_show_intf_counters_on_sup(self):
        remove_tmp_cnstat_file()
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_on_sup

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_on_sup
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"

    def test_show_intf_counters_on_sup_no_counters(self):
        remove_tmp_cnstat_file()
        os.system("cp {} /tmp/".format(os.path.join(test_path, "mock_tables/chassis_state_db.json")))
        os.system("cp {} {}".format(os.path.join(test_path, "portstat_db/on_sup_no_counters/chassis_state_db.json"),
                                    os.path.join(test_path, "mock_tables/chassis_state_db.json")))
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_on_sup_no_counters

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_on_sup_no_counters

        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.system("cp /tmp/chassis_state_db.json {}"
                  .format(os.path.join(test_path, "mock_tables/chassis_state_db.json")))

    def test_show_intf_counters_on_sup_partial_lc(self):
        remove_tmp_cnstat_file()
        os.system("cp {} /tmp/".format(os.path.join(test_path, "mock_tables/chassis_state_db.json")))
        os.system("cp {} {}".format(os.path.join(test_path, "portstat_db/on_sup_partial_lc/chassis_state_db.json"),
                                    os.path.join(test_path, "mock_tables/chassis_state_db.json")))
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_on_sup_partial_lc

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_on_sup_partial_lc

        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.system("cp /tmp/chassis_state_db.json {}"
                  .format(os.path.join(test_path, "mock_tables/chassis_state_db.json")))

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        remove_tmp_cnstat_file()
        os.system("cp /tmp/chassis_state_db.json {}"
                  .format(os.path.join(test_path, "mock_tables/chassis_state_db.json")))


class TestMultiAsicPortStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        remove_tmp_cnstat_file()

    def test_multi_show_intf_counters(self):
        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_external_intf_counters

    def test_multi_show_intf_counters_all(self):
        return_code, result = get_result_and_return_code(['portstat', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_all_intf_counters

    def test_multi_show_intf_counters_asic(self):
        return_code, result = get_result_and_return_code(['portstat', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_external_intf_counters

    def test_multi_show_intf_counters_asic_all(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-n', 'asic0', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_asic0

    def test_multi_show_external_intf_counters_printall(self):
        return_code, result = get_result_and_return_code(['portstat', '-a'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_external_intf_counters_printall

    def test_multi_show_intf_counters_printall(self):
        return_code, result = get_result_and_return_code(['portstat', '-a', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_printall

    def test_multi_show_intf_counters_printall_asic(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '--a', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_external_intf_counters_printall

    def test_multi_show_intf_counters_printall_asic_all(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-a', '-n', 'asic0', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_asic0_printall

    def test_multi_show_intf_counters_period(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-p', str(TEST_PERIOD)])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_period

    def test_multi_show_intf_counters_period_all(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-p', str(TEST_PERIOD), '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_period_all

    def test_multi_show_intf_counters_period_asic(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-p', str(TEST_PERIOD), '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_period

    def test_multi_show_intf_counters_period_asic_all(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-p', str(TEST_PERIOD), '-n', 'asic0', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counter_period_asic_all

    def test_multi_asic_clear_intf_counters(self):
        return_code, result = get_result_and_return_code(['portstat', '-c'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result.rstrip() == clear_counter

        # check stats for all the interfaces are cleared
        return_code, result = get_result_and_return_code(['portstat', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        verify_after_clear(result, mutli_asic_intf_counters_after_clear)

    def test_multi_asic_invalid_asic(self):
        return_code, result = get_result_and_return_code(['portstat', '-n', 'asic99'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == intf_invalid_asic_error

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        remove_tmp_cnstat_file()
