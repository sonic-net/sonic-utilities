import pytest
import json
import logging
import os
import shutil
import importlib.machinery
import importlib.util

from unittest import mock

import clear.main as clear
import show.main as show

from click.testing import CliRunner
from utilities_common.cli import UserCache

from .mock_tables import dbconnector
from .utils import get_result_and_return_code
from .portstat_input import assert_show_output

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

logger = logging.getLogger(__name__)

SUCCESS = 0

intf_counters_before_clear = """\
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------  --------  --------  --------
Ethernet0        D        8  2000.00 MB/s     64.00%        10       100       N/A       10  1500.00 MB/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        4   204.80 KB/s        N/A         0     1,000       N/A       40   204.85 KB/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        6  1350.00 KB/s        N/A       100        10       N/A       60    13.37 MB/s        N/A       N/A       N/A       N/A
Ethernet9      N/A        0      0.00 B/s        N/A         0         0       N/A        0      0.00 B/s        N/A\
       N/A       N/A       N/A
"""

intf_counters_ethernet4 = """\
    IFACE    STATE    RX_OK       RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK       TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  -----------  ---------  --------  --------  --------  -------  -----------  ---------  --------  --------  --------
Ethernet4      N/A        4  204.80 KB/s        N/A         0     1,000       N/A       40  204.85 KB/s        N/A       N/A       N/A       N/A
"""

intf_counters_all = """\
    IFACE    STATE    RX_OK        RX_BPS       RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS       TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR    TRIM    TRIM_TX    TRIM_DRP
---------  -------  -------  ------------  -----------  ---------  --------  --------  --------  -------  ------------  -----------  ---------  --------  --------  --------  ------  ---------  ----------
Ethernet0        D        8  2000.00 MB/s  247000.00/s     64.00%        10       100       N/A       10  1500.00 MB/s  183000.00/s     48.00%       N/A       N/A       N/A       0          0           0
Ethernet4      N/A        4   204.80 KB/s     200.00/s        N/A         0     1,000       N/A       40   204.85 KB/s     201.00/s        N/A       N/A       N/A       N/A     100         50          50
Ethernet8      N/A        6  1350.00 KB/s    9000.00/s        N/A       100        10       N/A       60    13.37 MB/s    9000.00/s        N/A       N/A       N/A       N/A  20,000     10,000      10,000
Ethernet9      N/A        0      0.00 B/s       0.00/s        N/A         0         0       N/A        0      0.00 B/s       0.00/s        N/A       N/A       N/A       N/A     N/A        N/A         N/A
"""  # noqa: E501

intf_fec_counters = """\
    IFACE    STATE    FEC_CORR    FEC_UNCORR    FEC_SYMBOL_ERR    FEC_PRE_BER    FEC_POST_BER    FEC_PRE_BER_MAX    FLR(O)    FLR(P) (Accuracy)    FEC_MAX_T
---------  -------  ----------  ------------  ----------------  -------------  --------------  -----------------  --------  -------------------  -----------
Ethernet0        D     130,402             3                 4            N/A             N/A                N/A  4.21e-10       7.81e-10 (89%)         -1.0
Ethernet4      N/A     110,412             1                 0            N/A             N/A                N/A         0                    0          0.0
Ethernet8      N/A     100,317             0                 0            N/A             N/A                N/A         0       4.81e-10 (89%)          3.0
Ethernet9      N/A           0             0                 0            N/A             N/A                N/A       N/A                  N/A          N/A
"""  # noqa: E501

intf_fec_counters_nonzero = """\
    IFACE    STATE    FEC_CORR    FEC_UNCORR    FEC_SYMBOL_ERR    FEC_PRE_BER    FEC_POST_BER    FEC_PRE_BER_MAX    FLR(O)    FLR(P) (Accuracy)    FEC_MAX_T
---------  -------  ----------  ------------  ----------------  -------------  --------------  -----------------  --------  -------------------  -----------
Ethernet0        D     130,402             3                 4            N/A             N/A                N/A  4.21e-10       7.81e-10 (89%)           -1
Ethernet4      N/A     110,412             1                 0            N/A             N/A                N/A  0                           0            0
Ethernet8      N/A     100,317             0                 0            N/A             N/A                N/A  0              4.81e-10 (89%)            3
"""  # noqa: E501

intf_fec_counters_period = """\
The rates are calculated within 3 seconds period
    IFACE    STATE    FEC_CORR    FEC_UNCORR    FEC_SYMBOL_ERR    FEC_PRE_BER    FEC_POST_BER    FEC_PRE_BER_MAX    FLR(O)    FLR(P) (Accuracy)    FEC_MAX_T
---------  -------  ----------  ------------  ----------------  -------------  --------------  -----------------  --------  -------------------  -----------
Ethernet0        D           0             0                 0            N/A             N/A                N/A  4.21e-10       7.81e-10 (89%)         -1.0
Ethernet4      N/A           0             0                 0            N/A             N/A                N/A         0                    0          0.0
Ethernet8      N/A           0             0                 0            N/A             N/A                N/A         0       4.81e-10 (89%)          3.0
Ethernet9      N/A           0             0                 0            N/A             N/A                N/A       N/A                  N/A          N/A
"""  # noqa: E501

intf_counters_period = """\
The rates are calculated within 3 seconds period
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------  --------  --------  --------
Ethernet0        D        0  2000.00 MB/s     64.00%         0         0       N/A        0  1500.00 MB/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        0   204.80 KB/s        N/A         0         0       N/A        0   204.85 KB/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        0  1350.00 KB/s        N/A         0         0       N/A        0    13.37 MB/s        N/A       N/A       N/A       N/A
Ethernet9      N/A        0      0.00 B/s        N/A         0         0       N/A        0      0.00 B/s        N/A\
       N/A       N/A       N/A
"""

intf_counter_after_clear = """\
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------  --------  --------  --------
Ethernet0        D        0  2000.00 MB/s     64.00%         0         0       N/A        0  1500.00 MB/s     48.00%       N/A       N/A       N/A
Ethernet4      N/A        0   204.80 KB/s        N/A         0         0       N/A        0   204.85 KB/s        N/A       N/A       N/A       N/A
Ethernet8      N/A        0  1350.00 KB/s        N/A         0         0       N/A        0    13.37 MB/s        N/A\
       N/A       N/A       N/A
Ethernet9      N/A        0      0.00 B/s        N/A         0         0       N/A        0      0.00 B/s        N/A\
       N/A       N/A       N/A"""

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
    IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR    TRIM    TRIM_TX    TRIM_DRP
---------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------  ------  ---------  ----------
Ethernet0        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A       0          0           0
Ethernet4        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     100         50          50

Reminder: Please execute 'show interface counters -d all' to include internal links

"""  # noqa: E501

multi_asic_intf_counters_printall = """\
         IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR    TRIM    TRIM_TX    TRIM_DRP
--------------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------  ------  ---------  ----------
     Ethernet0        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A       0          0           0
     Ethernet4        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     100         50          50
  Ethernet-BP0        U        6  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       60  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A
  Ethernet-BP4        U        8  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       80  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A
Ethernet-BP256        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A
Ethernet-BP260        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""  # noqa: E501

multi_asic_intf_counters_asic0_printall = """\
       IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR    TRIM    TRIM_TX    TRIM_DRP
------------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------  ------  ---------  ----------
   Ethernet0        U        8  0.00 B/s    0.00/s      0.00%        10       100       N/A       10  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A       0          0           0
   Ethernet4        U        4  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       40  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     100         50          50
Ethernet-BP0        U        6  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       60  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A
Ethernet-BP4        U        8  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       80  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""  # noqa: E501

multi_asic_intf_counters_bp0 = """\
       IFACE    STATE    RX_OK    RX_BPS    RX_PPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK    TX_BPS    TX_PPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR    TRIM    TRIM_TX    TRIM_DRP
------------  -------  -------  --------  --------  ---------  --------  --------  --------  -------  --------  --------  ---------  --------  --------  --------  ------  ---------  ----------
Ethernet-BP0        U        6  0.00 B/s    0.00/s      0.00%         0     1,000       N/A       60  0.00 B/s    0.00/s      0.00%       N/A       N/A       N/A     N/A        N/A         N/A

Reminder: Please execute 'show interface counters -d all' to include internal links

"""  # noqa: E501

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

WRED Green Dropped Packets..................... 17
WRED Yellow Dropped Packets.................... 33
WRED Red Dropped Packets....................... 51
WRED Total Dropped Packets..................... 101

Trimmed Packets................................ 100
Trimmed Sent Packets........................... 50
Trimmed Dropped Packets........................ 50

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
Ethernet12/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s      0.00%\
         0         0         0
"""

intf_counters_on_sup_no_counters = "Linecard Counter Table is not available.\n"

intf_counters_on_sup_partial_lc = "Not all linecards have published their counter values.\n"

intf_counters_on_sup_na = """\
       IFACE    STATE    RX_OK     RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK     TX_BPS    TX_UTIL\
    TX_ERR    TX_DRP    TX_OVR
------------  -------  -------  ---------  ---------  --------  --------  --------  -------  ---------  ---------\
  --------  --------  --------
 Ethernet1/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s      0.00%\
         0         0         0
 Ethernet2/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s      0.00%\
         0         0         0
Ethernet11/1      N/A      N/A        N/A        N/A       N/A       N/A       N/A      N/A        N/A        N/A\
       N/A       N/A       N/A
Ethernet12/1      N/A      N/A        N/A        N/A       N/A       N/A       N/A      N/A        N/A        N/A\
       N/A       N/A       N/A
"""

intf_counters_on_sup_packet_chassis = """\
       IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS\
    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
------------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------\
  ---------  --------  --------  --------
Ethernet-BP0      N/A        8  2000.00 MB/s        N/A        10       100       N/A       10  1500.00 MB/s\
        N/A       N/A       N/A       N/A
Ethernet-BP4      N/A        4   204.80 KB/s        N/A         0     1,000       N/A       40   204.85 KB/s\
        N/A       N/A       N/A       N/A
Ethernet-BP8      N/A        6  1350.00 KB/s        N/A       100        10       N/A       60    13.37 MB/s\
        N/A       N/A       N/A       N/A

Reminder: Please execute 'show interface counters -d all' to include internal links
"""

intf_counters_from_lc_on_sup_packet_chassis = """\
                  IFACE    STATE    RX_OK     RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK     TX_BPS\
    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
-----------------------  -------  -------  ---------  ---------  --------  --------  --------  -------  ---------\
  ---------  --------  --------  --------
     HundredGigE0/1/0/1        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s\
      0.00%         0         0         0
       FortyGigE0/2/0/2        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s\
      0.00%         0         0         0
FourHundredGigE0/3/0/10        U      100  10.00 B/s      0.00%         0         0         0      100  10.00 B/s\
      0.00%         0         0         0

Reminder: Please execute 'show interface counters -d all' to include internal links
"""

intf_counters_nonzero = """\
    IFACE    STATE    RX_OK        RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK        TX_BPS    TX_UTIL\
    TX_ERR    TX_DRP    TX_OVR
---------  -------  -------  ------------  ---------  --------  --------  --------  -------  ------------  ---------\
  --------  --------  --------
Ethernet0        D        8  2000.00 MB/s     64.00%        10       100       N/A       10  1500.00 MB/s     48.00%\
       N/A       N/A       N/A
Ethernet4      N/A        4   204.80 KB/s        N/A         0     1,000       N/A       40   204.85 KB/s        N/A\
       N/A       N/A       N/A
Ethernet8      N/A        6  1350.00 KB/s        N/A       100        10       N/A       60    13.37 MB/s        N/A\
       N/A       N/A       N/A
"""

intf_counter_after_clear_nonzero = """\
No non-zero statistics found for the specified interfaces."""

intf_rates = """\
    IFACE    STATE    RX_OK        RX_BPS       RX_PPS    RX_UTIL    TX_OK        TX_BPS       TX_PPS    TX_UTIL
---------  -------  -------  ------------  -----------  ---------  -------  ------------  -----------  ---------
Ethernet0        D        8  2000.00 MB/s  247000.00/s     64.00%       10  1500.00 MB/s  183000.00/s     48.00%
Ethernet4      N/A        4   204.80 KB/s     200.00/s        N/A       40   204.85 KB/s     201.00/s        N/A
Ethernet8      N/A        6  1350.00 KB/s    9000.00/s        N/A       60    13.37 MB/s    9000.00/s        N/A
Ethernet9      N/A        0      0.00 B/s       0.00/s        N/A        0      0.00 B/s       0.00/s        N/A
"""  # noqa: E501

intf_rates_nonzero = """\
    IFACE    STATE    RX_OK        RX_BPS       RX_PPS    RX_UTIL    TX_OK        TX_BPS       TX_PPS    TX_UTIL
---------  -------  -------  ------------  -----------  ---------  -------  ------------  -----------  ---------
Ethernet0        D        8  2000.00 MB/s  247000.00/s     64.00%       10  1500.00 MB/s  183000.00/s     48.00%
Ethernet4      N/A        4   204.80 KB/s     200.00/s        N/A       40   204.85 KB/s     201.00/s        N/A
Ethernet8      N/A        6  1350.00 KB/s    9000.00/s        N/A       60    13.37 MB/s    9000.00/s        N/A
"""  # noqa: E501

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


def _backup_mock_file(fname, suffix=".bak"):
    """Backup a file in the per-worker mock_tables dir."""
    src = os.path.join(dbconnector.INPUT_DIR, fname)
    dst = os.path.join(dbconnector.INPUT_DIR, fname + suffix)
    shutil.copyfile(src, dst)


def _restore_mock_file(fname, suffix=".bak"):
    """Restore a backed-up file in the per-worker mock_tables dir."""
    src = os.path.join(dbconnector.INPUT_DIR, fname + suffix)
    dst = os.path.join(dbconnector.INPUT_DIR, fname)
    shutil.copyfile(src, dst)


def _replace_mock_file(subdir, fname):
    """Replace a mock file with a test-specific version."""
    src = os.path.join(test_path, subdir, fname)
    dst = os.path.join(dbconnector.INPUT_DIR, fname)
    shutil.copyfile(src, dst)


class TestPortStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "0"
        _backup_mock_file("counters_db.json", ".orig")
        _replace_mock_file("portstat_db", "counters_db.json")
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
        with mock.patch('show.interfaces.clicommon.run_command') as mock_run:
            result = runner.invoke(
                show.cli.commands["interfaces"].commands["counters"].commands["fec-histogram"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        invoked_cmd = mock_run.call_args[0][0]
        assert invoked_cmd[:2] == ['portstat', '-fh']
        assert '-i' in invoked_cmd
        assert invoked_cmd[invoked_cmd.index('-i') + 1] == 'Ethernet0'
        assert '--relative-timestamp' in invoked_cmd

    def test_show_intf_counters_fec_histogram_multi_asic_and_namespace(self):
        runner = CliRunner()
        with mock.patch('show.interfaces.clicommon.run_command') as mock_run, \
                mock.patch('show.interfaces.multi_asic.is_multi_asic', return_value=True):
            result = runner.invoke(
                show.cli.commands["interfaces"].commands["counters"].commands["fec-histogram"],
                ["Ethernet0", "-n", "asic0", "-d", "all"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        invoked_cmd = mock_run.call_args[0][0]
        assert '-s' in invoked_cmd
        assert invoked_cmd[invoked_cmd.index('-s') + 1] == 'all'
        assert '-n' in invoked_cmd
        assert invoked_cmd[invoked_cmd.index('-n') + 1] == 'asic0'

    def test_show_intf_counters_fec_histogram_invalid_interface(self):
        runner = CliRunner()
        with mock.patch('show.interfaces.clicommon.run_command') as mock_run:
            result = runner.invoke(
                show.cli.commands["interfaces"].commands["counters"].commands["fec-histogram"],
                ["Ethernet_Bogus"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "does not exist" in result.output
        assert mock_run.call_count == 0

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

    def test_show_intf_rates(self):
        return_code, result = get_result_and_return_code(['portstat', '-R'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_rates

    @pytest.mark.parametrize("intf_fs", [
        "Ethernet320-Ethernet376",  # range bounds not numeric
        "Ethernet0-",               # missing end of range
        "Ethernet0-foo",            # non-numeric end of range
        "Eth0-3",                   # range with unsupported prefix
        "Ethernet8-4",              # start of range greater than the end
    ])
    def test_show_intf_counters_malformed_range(self, intf_fs):
        return_code, result = get_result_and_return_code(['portstat', '-i', intf_fs])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert "Error: Invalid interface range" in result

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

    @staticmethod
    def _load_portstat_script():
        # The portstat script is extensionless; load it directly via
        # SourceFileLoader so its module-level symbols are reachable.
        path = os.path.join(scripts_path, 'portstat')
        loader = importlib.machinery.SourceFileLoader('portstat_script', path)
        spec = importlib.util.spec_from_loader('portstat_script', loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def test_clear_fec_rate_aggregates(self):
        # Verify _clear_fec_rate_aggregates issues an HDEL for every port OID
        # in COUNTERS_PORT_NAME_MAP, targeting exactly the FEC rate/window
        # aggregate fields declared in scripts/portstat.
        portstat_script = self._load_portstat_script()
        expected_fields = portstat_script.FEC_RATE_AGGREGATE_FIELDS
        assert len(expected_fields) == 10

        port_name_map = {
            'Ethernet0': 'oid:0x1000000000001',
            'Ethernet4': 'oid:0x1000000000002',
            'Ethernet8': 'oid:0x1000000000003',
        }

        mock_db = mock.MagicMock()
        mock_db.COUNTERS_DB = 'COUNTERS_DB'
        mock_db.get_all.return_value = port_name_map
        mock_redis = mock.MagicMock()
        mock_db.get_redis_client.return_value = mock_redis

        mock_portstat = mock.MagicMock()
        mock_portstat.multi_asic.get_ns_list_based_on_options.return_value = ['']
        mock_portstat.get_db_client.return_value = mock_db

        portstat_script._clear_fec_rate_aggregates(mock_portstat)

        assert mock_redis.hdel.call_count == len(port_name_map)
        called_keys = set()
        for call in mock_redis.hdel.call_args_list:
            key = call[0][0]
            fields = call[0][1:]
            called_keys.add(key)
            assert tuple(fields) == tuple(expected_fields)
        assert called_keys == {'RATES:' + oid for oid in port_name_map.values()}

    def test_clear_fec_rate_aggregates_ns_list_exception(self):
        # If enumerating namespaces fails, the helper must warn and return
        # rather than raising out of the clear path.
        portstat_script = self._load_portstat_script()

        mock_portstat = mock.MagicMock()
        mock_portstat.multi_asic.get_ns_list_based_on_options.side_effect = Exception("boom")

        portstat_script._clear_fec_rate_aggregates(mock_portstat)

        mock_portstat.get_db_client.assert_not_called()

    def test_clear_fec_rate_aggregates_empty_port_map(self):
        # A namespace with no COUNTERS_PORT_NAME_MAP entries must be skipped
        # without issuing any HDEL.
        portstat_script = self._load_portstat_script()

        mock_db = mock.MagicMock()
        mock_db.COUNTERS_DB = 'COUNTERS_DB'
        mock_db.get_all.return_value = None

        mock_portstat = mock.MagicMock()
        mock_portstat.multi_asic.get_ns_list_based_on_options.return_value = ['']
        mock_portstat.get_db_client.return_value = mock_db

        portstat_script._clear_fec_rate_aggregates(mock_portstat)

        mock_db.get_redis_client.assert_not_called()

    def test_clear_fec_rate_aggregates_redis_exception(self):
        # A per-namespace redis failure must be warned about and must not
        # prevent other namespaces from being processed.
        portstat_script = self._load_portstat_script()

        mock_db = mock.MagicMock()
        mock_db.COUNTERS_DB = 'COUNTERS_DB'
        mock_db.get_all.return_value = {'Ethernet0': 'oid:0x1000000000001'}
        mock_db.get_redis_client.side_effect = Exception("redis down")

        mock_portstat = mock.MagicMock()
        mock_portstat.multi_asic.get_ns_list_based_on_options.return_value = ['asic0']
        mock_portstat.get_db_client.return_value = mock_db

        # Should not raise despite the redis failure.
        portstat_script._clear_fec_rate_aggregates(mock_portstat)

    def test_clear_counters_cache_contains_fec_bins(self):
        # After portstat -c, the per-user snapshot cache must contain all 16
        # fec_binN fields for every port so that subsequent diffs in
        # portstat -fh return zero.
        remove_tmp_cnstat_file()
        return_code, _ = get_result_and_return_code(['portstat', '-c'])
        assert return_code == 0

        cache_file = os.path.join(UserCache("portstat").get_directory(), "portstat")
        assert os.path.isfile(cache_file)
        with open(cache_file, 'r') as f:
            cnstat_cached = json.load(f)

        port_entries = [v for k, v in cnstat_cached.items() if k != 'time']
        assert port_entries, "cache contains no port entries"
        for entry in port_entries:
            for i in range(16):
                assert 'fec_bin{}'.format(i) in entry

    def test_show_intf_counters_fec_histogram_no_cache(self):
        # With no prior clear (no snapshot cache), portstat -fh must still
        # render successfully and display lifetime BIN values.
        remove_tmp_cnstat_file()
        return_code, result = get_result_and_return_code(
            ['portstat', '-fh', '-i', 'Ethernet0'])
        assert return_code == 0
        for i in range(16):
            assert 'BIN{}'.format(i) in result
        assert 'Last Updated' in result

    def test_show_intf_counters_fec_histogram_relative_timestamp_render(self):
        # The --relative-timestamp flag adds a Relative Time column to the
        # single-interface vertical view; the header renders regardless of
        # whether per-bin timestamps are present.
        remove_tmp_cnstat_file()
        return_code, result = get_result_and_return_code(
            ['portstat', '-fh', '-i', 'Ethernet0', '--relative-timestamp'])
        assert return_code == 0
        assert 'Last Updated' in result
        assert 'Relative Time' in result

    def test_format_relative_time(self):
        from utilities_common.portstat import format_relative_time
        now_ms = 1_700_000_000_000
        with mock.patch('utilities_common.portstat.time.time', return_value=now_ms / 1000.0):
            assert format_relative_time(now_ms - 5_000) == '5 seconds ago'
            assert format_relative_time(now_ms - 1_000) == '1 second ago'
            assert format_relative_time(now_ms - 120_000) == '2 minutes ago'
            assert format_relative_time(now_ms - 3 * 3600_000) == '3 hours ago'
            assert format_relative_time(now_ms - 2 * 86400_000) == '2 days ago'

    def test_print_fec_hist_vertical_interface_not_found(self, capsys):
        from utilities_common.portstat import Portstat
        portstat = Portstat.__new__(Portstat)
        portstat.print_fec_hist_vertical({}, {}, 'Ethernet0')
        assert "Interface Ethernet0 not found" in capsys.readouterr().out

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
        _backup_mock_file("chassis_state_db.json")
        _replace_mock_file("portstat_db/on_sup_no_counters", "chassis_state_db.json")
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
        _restore_mock_file("chassis_state_db.json")

    def test_show_intf_counters_on_sup_partial_lc(self):
        remove_tmp_cnstat_file()
        _backup_mock_file("chassis_state_db.json")
        _replace_mock_file("portstat_db/on_sup_partial_lc", "chassis_state_db.json")
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
        _restore_mock_file("chassis_state_db.json")

    def test_show_intf_counters_on_sup_na(self):
        remove_tmp_cnstat_file()
        _backup_mock_file("chassis_state_db.json")
        _replace_mock_file("portstat_db/on_sup_na", "chassis_state_db.json")
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_on_sup_na

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_on_sup_na

        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        _restore_mock_file("chassis_state_db.json")

    def test_show_intf_counters_on_sup_packet_chassis(self):
        _backup_mock_file("chassis_state_db.json")
        _replace_mock_file(
            "portstat_db/on_sup_packet_chassis", "chassis_state_db.json")
        _backup_mock_file("counters_db.json")
        _replace_mock_file(
            "portstat_db/on_sup_packet_chassis", "counters_db.json")
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "1"

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], ["-dall"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_on_sup_packet_chassis

        return_code, result = get_result_and_return_code(['portstat', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result.rstrip() == intf_counters_on_sup_packet_chassis.rstrip()
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "0"
        _restore_mock_file("chassis_state_db.json")
        _restore_mock_file("counters_db.json")

    def test_show_intf_counters_from_lc_on_sup_packet_chassis(self):
        _backup_mock_file("chassis_state_db.json")
        _replace_mock_file(
            "portstat_db/on_sup_packet_chassis", "chassis_state_db.json")
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "1"

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], ["-dfrontend"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_from_lc_on_sup_packet_chassis

        return_code, result = get_result_and_return_code(['portstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result.rstrip() == intf_counters_from_lc_on_sup_packet_chassis.rstrip()
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "0"
        _restore_mock_file("chassis_state_db.json")

    def test_show_intf_counters_nonzero(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"], ["--nonzero"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_counters_nonzero

        return_code, result = get_result_and_return_code(['portstat', '-nz'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_counters_nonzero

    def test_clear_intf_counters_nonzero(self):
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
            show.cli.commands["interfaces"].commands["counters"], ["--nonzero"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        verify_after_clear(result.output, intf_counter_after_clear_nonzero)

        return_code, result = get_result_and_return_code(['portstat', '-nz'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        verify_after_clear(result, intf_counter_after_clear_nonzero)

    def test_show_intf_fec_counters_nonzero(self):
        remove_tmp_cnstat_file()
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["fec-stats"], ["--nonzero"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == intf_fec_counters_nonzero

        return_code, result = get_result_and_return_code(['portstat', '-f', '-nz'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_fec_counters_nonzero

    def test_show_intf_rates_nonzero(self):
        remove_tmp_cnstat_file()
        return_code, result = get_result_and_return_code(['portstat', '-R', '-nz'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_rates_nonzero

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "0"
        remove_tmp_cnstat_file()
        _restore_mock_file("counters_db.json", ".orig")


class TestPortTrimStat(object):
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        remove_tmp_cnstat_file()

    @classmethod
    def teardown_class(cls):
        logger.info("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        remove_tmp_cnstat_file()

    @pytest.mark.parametrize(
        "output", [
            pytest.param(
                {
                    "plain": assert_show_output.trim_counters_all,
                    "json": assert_show_output.trim_counters_all_json
                },
                id="all"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_port_trim_counters(self, format, output):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["trim"],
            [] if format == "plain" else ["--json"]
        )
        logger.debug("result:\n{}".format(result.output))
        logger.debug("return_code:\n{}".format(result.exit_code))

        assert result.output == output[format]
        assert result.exit_code == SUCCESS

        cmd = ['portstat', '--trim']

        if format == "json":
            cmd.append('-j')

        return_code, result = get_result_and_return_code(cmd)
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == output[format]
        assert return_code == SUCCESS

    @pytest.mark.parametrize(
        "intf,output", [
            pytest.param(
                "Ethernet0",
                {
                    "plain": assert_show_output.trim_eth0_counters,
                    "json": assert_show_output.trim_eth0_counters_json
                },
                id="eth0"
            ),
            pytest.param(
                "Ethernet4",
                {
                    "plain": assert_show_output.trim_eth4_counters,
                    "json": assert_show_output.trim_eth4_counters_json
                },
                id="eth4"
            ),
            pytest.param(
                "Ethernet8",
                {
                    "plain": assert_show_output.trim_eth8_counters,
                    "json": assert_show_output.trim_eth8_counters_json
                },
                id="eth8"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_port_trim_counters_intf(self, format, intf, output):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["trim"],
            [intf] if format == "plain" else [intf, "--json"]
        )
        logger.debug("result:\n{}".format(result.output))
        logger.debug("return_code:\n{}".format(result.exit_code))

        assert result.output == output[format]
        assert result.exit_code == SUCCESS

        cmd = ['portstat', '--trim', '-i', intf]

        if format == "json":
            cmd.append('-j')

        return_code, result = get_result_and_return_code(cmd)
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == output[format]
        assert return_code == SUCCESS

    def test_show_port_trim_counters_period(self):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["trim"],
            ["-p", str(TEST_PERIOD)]
        )
        logger.debug("result:\n{}".format(result.output))
        logger.debug("return_code:\n{}".format(result.exit_code))

        assert result.output == assert_show_output.trim_counters_period
        assert result.exit_code == SUCCESS

        return_code, result = get_result_and_return_code(
            ['portstat', '--trim', '-p', str(TEST_PERIOD)]
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == assert_show_output.trim_counters_period
        assert return_code == SUCCESS

    def test_clear_port_trim_counters(self):
        # Clear counters
        return_code, result = get_result_and_return_code(
            ['portstat', '-c']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == assert_show_output.trim_counters_clear_msg
        assert return_code == SUCCESS

        # Verify updated stats
        return_code, result = get_result_and_return_code(
            ['portstat', '--trim']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        verify_after_clear(result, assert_show_output.trim_counters_clear_stat.rstrip())
        assert return_code == SUCCESS

        # Verify raw stats
        return_code, result = get_result_and_return_code(
            ['portstat', '--trim', '--raw']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == assert_show_output.trim_counters_all
        assert return_code == SUCCESS

        # Verify stats after snapshot cleanup
        return_code, result = get_result_and_return_code(
            ['portstat', '--trim', '-d']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == assert_show_output.trim_counters_all
        assert return_code == SUCCESS


class TestMultiAsicPortStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
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

    def test_multi_show_intf_counters_bp0(self):
        return_code, result = get_result_and_return_code(
            ['portstat', '-a', '-i', 'Ethernet-BP0', '-s', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_intf_counters_bp0

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
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        remove_tmp_cnstat_file()


class TestPortstatGetDbClient(object):
    """Test the get_db_client method for caching DB connections"""

    def test_get_db_client_creates_new_connection(self):
        """Test that get_db_client creates a new connection when none exists"""
        from unittest import mock
        from utilities_common.portstat import Portstat
        from utilities_common.constants import DEFAULT_NAMESPACE

        portstat = Portstat(namespace=DEFAULT_NAMESPACE, display_option='')

        with mock.patch('sonic_py_common.multi_asic.connect_to_all_dbs_for_ns') as mock_connect:
            mock_db_client = mock.MagicMock()
            mock_connect.return_value = mock_db_client

            result = portstat.get_db_client('asic0')

            mock_connect.assert_called_once_with('asic0')

            assert result == mock_db_client

            assert portstat.db_clients['asic0'] == mock_db_client

    def test_get_db_client_returns_cached_connection(self):
        """Test that get_db_client returns cached connection on subsequent calls"""
        from unittest import mock
        from utilities_common.portstat import Portstat
        from utilities_common.constants import DEFAULT_NAMESPACE

        portstat = Portstat(namespace=DEFAULT_NAMESPACE, display_option='')

        with mock.patch('sonic_py_common.multi_asic.connect_to_all_dbs_for_ns') as mock_connect:
            mock_db_client = mock.MagicMock()
            mock_connect.return_value = mock_db_client
            result1 = portstat.get_db_client('asic0')
            result2 = portstat.get_db_client('asic0')
            mock_connect.assert_called_once_with('asic0')

            assert result1 == result2
            assert result1 == mock_db_client

    def test_get_db_client_multiple_namespaces(self):
        """Test that get_db_client handles multiple namespaces correctly"""
        from unittest import mock
        from utilities_common.portstat import Portstat
        from utilities_common.constants import DEFAULT_NAMESPACE

        portstat = Portstat(namespace=DEFAULT_NAMESPACE, display_option='')

        with mock.patch('sonic_py_common.multi_asic.connect_to_all_dbs_for_ns') as mock_connect:
            mock_db_client_asic0 = mock.MagicMock()
            mock_db_client_asic1 = mock.MagicMock()

            def side_effect(ns):
                if ns == 'asic0':
                    return mock_db_client_asic0
                elif ns == 'asic1':
                    return mock_db_client_asic1

            mock_connect.side_effect = side_effect
            result_asic0 = portstat.get_db_client('asic0')
            result_asic1 = portstat.get_db_client('asic1')
            assert mock_connect.call_count == 2
            mock_connect.assert_any_call('asic0')
            mock_connect.assert_any_call('asic1')
            assert result_asic0 == mock_db_client_asic0
            assert result_asic1 == mock_db_client_asic1
            assert portstat.db_clients['asic0'] == mock_db_client_asic0
            assert portstat.db_clients['asic1'] == mock_db_client_asic1
