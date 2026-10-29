"""
Module holding the correct values for show CLI command outputs for the syslog_test.py
"""

show_syslog_empty="""\
SERVER IP    SOURCE IP    PORT    VRF    PROTOCOL    TLS PROFILE ID    PERMITTED PEERS    TLS APPLIED    FAILURE REASON
-----------  -----------  ------  -----  ----------  ----------------  -----------------  -------------  ----------------
"""


show_syslog="""\
SERVER IP    SOURCE IP    PORT    VRF       PROTOCOL    TLS PROFILE ID    PERMITTED PEERS    TLS APPLIED    FAILURE REASON
-----------  -----------  ------  --------  ----------  ----------------  -----------------  -------------  ----------------
2.2.2.2      1.1.1.1      514     default   udp         N/A               N/A                N/A            N/A
3.3.3.3      1.1.1.1      514     mgmt      udp         N/A               N/A                N/A            N/A
2222::2222   1111::1111   514     Vrf-Data  udp         N/A               N/A                N/A            N/A
"""

show_syslog_tls="""\
SERVER IP    SOURCE IP    PORT    VRF      PROTOCOL    TLS PROFILE ID    PERMITTED PEERS                             TLS APPLIED    FAILURE REASON
-----------  -----------  ------  -------  ----------  ----------------  ------------------------------------------  -------------  --------------------
2.2.2.2      1.1.1.1      514     default  udp         N/A               N/A                                         N/A            N/A
10.0.0.5     N/A          6514    N/A      tls         siem-east         syslog-east.example.com                     true           NONE
10.0.0.6     N/A          6514    N/A      tls         siem-west         syslog-west.example.com,*.west.example.com  false          RSYSLOG_APPLY_FAILED
10.0.0.7     N/A          6514    N/A      tls         siem-new          syslog-new.example.com                      N/A            N/A
10.0.0.8     N/A          6514    N/A      tls         no-certs          syslog-nocerts.example.com                  false          NO_CERTIFICATE
10.0.0.9     N/A          6514    N/A      tls         no-peers          N/A                                         false          NO_PERMITTED_PEERS
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
