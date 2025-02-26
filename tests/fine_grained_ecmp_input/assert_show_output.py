"""
Module holding the correct values for show CLI command outputs for the fine_grained_ecmp_test.py
"""

show_fg_nhg = """\
NAME        BUCKET SIZE  MATCH MODE     MAX NEXT HOPS
--------  -------------  -------------  ---------------
fg_grp_2             30  nexthop-based  N/A
"""

show_fg_nhg_empty = """\
NAME    BUCKET SIZE    MATCH MODE    MAX NEXT HOPS
------  -------------  ------------  ---------------
"""

show_fg_nhg_members = """\
NEXT HOP IP    FG NHG      BANK  LINK
-------------  --------  ------  ------
10.10.20.1     fg_grp_1       0  N/A
10.10.20.2     fg_grp_1       1  N/A
"""

show_fg_nhg_members_empty = """\
NEXT HOP IP    FG NHG    BANK    LINK
-------------  --------  ------  ------
"""

show_fg_nhg_prefix = """\
IP PREFIX        FG NHG
---------------  --------
192.168.11.0/24  fg_grp_1
"""

show_fg_nhg_prefix_empty = """\
IP PREFIX    FG NHG
-----------  --------
"""
