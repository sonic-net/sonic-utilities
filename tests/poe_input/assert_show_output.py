"""
Module holding the correct values for show CLI command outputs for the poe_test.py
"""

show_poe_interface_configuration = """\
Port       En/Dis      Power limit  Priority
---------  --------  -------------  ----------
Ethernet0  enable              100  high
Ethernet4  disable             100  low
Ethernet8  enable              200  crit
"""

show_poe_interface_configuration_ethernet0_disable = """\
Port       En/Dis      Power limit  Priority
---------  --------  -------------  ----------
Ethernet0  disable             100  high
Ethernet4  disable             100  low
Ethernet8  enable              200  crit
"""

show_poe_interface_configuration_ethernet0_power_limit_200 = """\
Port       En/Dis      Power limit  Priority
---------  --------  -------------  ----------
Ethernet0  enable              200  high
Ethernet4  disable             100  low
Ethernet8  enable              200  crit
"""


show_poe_interface_configuration_ethernet0_priority_low = """\
Port       En/Dis      Power limit  Priority
---------  --------  -------------  ----------
Ethernet0  enable              100  low
Ethernet4  disable             100  low
Ethernet8  enable              200  crit
"""

show_poe_interface_configuration_ethernet0_priority_high = """\
Port       En/Dis      Power limit  Priority
---------  --------  -------------  ----------
Ethernet0  enable              100  high
Ethernet4  disable             100  low
Ethernet8  enable              200  crit
"""

show_poe_interface_configuration_ethernet0_priority_crit = """\
Port       En/Dis      Power limit  Priority
---------  --------  -------------  ----------
Ethernet0  enable              100  crit
Ethernet4  disable             100  low
Ethernet8  enable              200  crit
"""

show_poe_interface_status = """\
Port        Status      En/Dis    Priority    Protocol      Class A    Class B    PWR Consump    PWR limit    \
Voltage    Current
----------  ----------  --------  ----------  ------------  ---------  ---------  -------------  -----------  \
---------  ---------
Ethernet0   off         disable   high        IEEE_802.3at  1          1          12.500 W       25.500 W     \
50.000 V   0.250 A
Ethernet4   delivering  enable    crit        IEEE_802.3af  2          2          15.500 W       30.500 W     \
47.123 V   0.329 A
Ethernet8   searching   enable    low         IEEE_802.3at  3          3          8.500 W        30.500 W     \
40.000 V   0.212 A
Ethernet12  fault       N/A       N/A         N/A           N/A        N/A        N/A            N/A          \
N/A        N/A
"""

show_poe_pse_status = """\
  Id  Status       Temperature    SW ver    HW ver
----  -----------  -------------  --------  --------
   0  active       40.000 C       1.0.0     1.1.0
   1  fail         30.000 C       2.0.0     2.2.0
   2  not present  N/A            N/A       N/A
   3  N/A          N/A            N/A       N/A
"""

show_poe_status = """\
  Id    PoE ports  Total power    Power consump    Power available    Power limit mode    HW info    Version
----  -----------  -------------  ---------------  -----------------  ------------------  ---------  ---------
   1           10  100.000 W      20.000 W         80.000 W           port                HW INFO 1  1.0.0
   2           20  200.000 W      40.000 W         160.000 W          class               HW INFO 2  2.0.0
   3           30  300.000 W      60.000 W         240.000 W          port                HW INFO 3  3.0.0
   4           40  N/A            N/A              N/A                N/A                 N/A        N/A
"""
