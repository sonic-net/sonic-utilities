"""
Module holding the correct values for show CLI command outputs for the syslog_test.py
"""

show_syslog_empty="""\
SERVER IP    SOURCE IP    PORT    VRF
-----------  -----------  ------  -----
"""


show_syslog="""\
SERVER IP    SOURCE IP    PORT    VRF
-----------  -----------  ------  --------
2.2.2.2      1.1.1.1      514     default
3.3.3.3      1.1.1.1      514     mgmt
2222::2222   1111::1111   514     Vrf-Data
"""

show_syslog_rate_limit_host="""\
INTERVAL    BURST
----------  -------
100         20000
"""

show_syslog_rate_limit_container="""\
SERVICE    INTERVAL    BURST
---------  ----------  -------
bgp        150         30000
snmp       N/A         N/A
swss       N/A         30000
syncd      N/A         N/A
"""

show_syslog_rate_limit_container_bgp="""\
SERVICE    INTERVAL    BURST
---------  ----------  -------
bgp        150         30000
"""

show_syslog_rate_limit_container_swss="""\
SERVICE    INTERVAL    BURST
---------  ----------  -------
swss       N/A         30000
"""

show_syslog_rate_limit_container_syncd="""\
SERVICE    INTERVAL    BURST
---------  ----------  -------
syncd      N/A         N/A
"""
