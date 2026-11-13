"""
Module holding the correct values for show CLI command outputs for the syslog_test.py
"""

show_syslog_empty="""\
SERVER IP    SOURCE IP    PORT    VRF    PROTOCOL    TLS PROFILE ID    PERMITTED PEERS
-----------  -----------  ------  -----  ----------  ----------------  -----------------
"""


show_syslog="""\
SERVER IP    SOURCE IP    PORT    VRF       PROTOCOL    TLS PROFILE ID    PERMITTED PEERS
-----------  -----------  ------  --------  ----------  ----------------  -----------------
2.2.2.2      1.1.1.1      514     default   udp         N/A               N/A
3.3.3.3      1.1.1.1      514     mgmt      udp         N/A               N/A
2222::2222   1111::1111   514     Vrf-Data  udp         N/A               N/A
"""

show_syslog_tls_state="""\
SERVER IP    TLS APPLIED    FAILURE REASON
-----------  -------------  --------------------
10.0.0.5     true           NONE
10.0.0.6     false          RSYSLOG_APPLY_FAILED
10.0.0.7     N/A            N/A
10.0.0.8     false          NO_CERTIFICATE
10.0.0.9     false          NO_PERMITTED_PEERS
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
