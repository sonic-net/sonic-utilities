"""
Module holding the correct values for show CLI command outputs for the dhcpv4_relay_test.py
"""

show_dhcpv4_relay_add = """\
NAME    SERVER VRF    SOURCE INTERFACE    LINK SELECTION    VRF SELECTION    SERVER ID OVERRIDE    AGENT RELAY MODE    MAX HOP COUNT    DHCPV4 SERVERS
------  ------------  ------------------  ----------------  ---------------  --------------------  ------------------  ---------------  ----------------
Vlan11  N/A           N/A                 N/A               N/A              N/A                   N/A                 N/A              192.168.11.12
"""

show_dhcpv4_relay_update = """\
NAME    SERVER VRF    SOURCE INTERFACE    LINK SELECTION    VRF SELECTION    SERVER ID OVERRIDE    AGENT RELAY MODE    MAX HOP COUNT    DHCPV4 SERVERS
------  ------------  ------------------  ----------------  ---------------  --------------------  ------------------  ---------------  ----------------
Vlan11  N/A           N/A                 N/A               N/A              N/A                   N/A                 N/A              192.168.11.13
"""

show_dhcpv4_relay_update_max_hop_count = """\
NAME    SERVER VRF    SOURCE INTERFACE    LINK SELECTION    VRF SELECTION    SERVER ID OVERRIDE    AGENT RELAY MODE      MAX HOP COUNT  DHCPV4 SERVERS
------  ------------  ------------------  ----------------  ---------------  --------------------  ------------------  ---------------  ----------------
Vlan11  N/A           N/A                 N/A               N/A              N/A                   N/A                               5  192.168.11.13
"""
