"""
Module holding the correct values for show CLI command outputs for the nvgre_tunnel_test.py
"""


show_nvgre_tunnel="""\
TUNNEL NAME    SRC IP
-------------  --------
tunnel_1       10.0.0.1
"""


show_nvgre_tunnel_empty="""\
TUNNEL NAME    SRC IP
-------------  --------
"""


show_nvgre_tunnels="""\
TUNNEL NAME    SRC IP
-------------  --------
tunnel_1       10.0.0.1
tunnel_2       10.0.0.2
"""


show_nvgre_tunnel_maps="""\
TUNNEL NAME    TUNNEL MAP NAME    VLAN ID    VSID
-------------  -----------------  ---------  ------
tunnel_1       Vlan1000           1000       5000
tunnel_1       Vlan2000           2000       6000
"""


show_nvgre_tunnel_map_empty="""\
TUNNEL NAME    TUNNEL MAP NAME    VLAN ID    VSID
-------------  -----------------  ---------  ------
"""

