import importlib
import os
import sys
from importlib import reload

from click.testing import CliRunner
import crm.main as crm
from utilities_common.db import Db

# Expected output for CRM

crm_show_summary = """\

Polling Interval: 300 second(s)

"""

crm_show_thresholds_acl_group = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
acl_group        percentage                     70                85

"""

crm_show_thresholds_acl_table = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
acl_table        percentage                     70                85

"""

crm_show_thresholds_all = """\

Resource Name         Threshold Type      Low Threshold    High Threshold
--------------------  ----------------  ---------------  ----------------
ipv4_route            percentage                     70                85
ipv6_route            percentage                     70                85
ipv4_nexthop          percentage                     70                85
ipv6_nexthop          percentage                     70                85
ipv4_neighbor         percentage                     70                85
ipv6_neighbor         percentage                     70                85
nexthop_group_member  percentage                     70                85
nexthop_group         percentage                     70                85
acl_table             percentage                     70                85
acl_group             percentage                     70                85
acl_entry             percentage                     70                85
acl_counter           percentage                     70                85
fdb_entry             percentage                     70                85
ipmc_entry            percentage                     70                85
snat_entry            percentage                     70                85
dnat_entry            percentage                     70                85
mpls_inseg            percentage                     70                85
mpls_nexthop          percentage                     70                85
srv6_nexthop          percentage                     70                85
srv6_my_sid_entry     percentage                     70                85

"""

crm_show_thresholds_fdb = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
fdb_entry        percentage                     70                85

"""

crm_show_thresholds_ipv4_neighbor = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv4_neighbor    percentage                     70                85

"""

crm_show_thresholds_ipv4_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv4_nexthop     percentage                     70                85

"""

crm_show_thresholds_ipv4_route = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv4_route       percentage                     70                85

"""

crm_show_thresholds_ipv6_neighbor = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv6_neighbor    percentage                     70                85

"""

crm_show_thresholds_ipv6_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv6_nexthop     percentage                     70                85

"""

crm_show_thresholds_ipv6_route= """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv6_route       percentage                     70                85

"""

crm_show_thresholds_nexthop_group_member = """\

Resource Name         Threshold Type      Low Threshold    High Threshold
--------------------  ----------------  ---------------  ----------------
nexthop_group_member  percentage                     70                85

"""

crm_show_thresholds_nexthop_group_object = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
nexthop_group    percentage                     70                85

"""

crm_show_thresholds_snat = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
snat_entry       percentage                     70                85

"""

crm_show_thresholds_dnat = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
dnat_entry       percentage                     70                85

"""

crm_show_thresholds_mpls_inseg = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
mpls_inseg       percentage                     70                85

"""

crm_show_thresholds_mpls_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
mpls_nexthop     percentage                     70                85

"""

crm_show_thresholds_ipmc = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipmc_entry       percentage                     70                85

"""

crm_show_thresholds_srv6_my_sid_entry = """\

Resource Name      Threshold Type      Low Threshold    High Threshold
-----------------  ----------------  ---------------  ----------------
srv6_my_sid_entry  percentage                     70                85

"""

crm_show_thresholds_srv6_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
srv6_nexthop     percentage                     70                85

"""

crm_new_show_summary = """\

Polling Interval: 30 second(s)

"""

crm_new_show_thresholds_acl_group = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
acl_group        percentage                     60                90

"""

crm_new_show_thresholds_acl_table = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
acl_table        percentage                     60                90

"""

crm_new_show_thresholds_fdb = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
fdb_entry        percentage                     60                90

"""

crm_new_show_thresholds_ipv4_neighbor = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv4_neighbor    percentage                     60                90

"""

crm_new_show_thresholds_ipv4_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv4_nexthop     percentage                     60                90

"""

crm_new_show_thresholds_ipv4_route = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv4_route       percentage                     60                90

"""

crm_new_show_thresholds_ipv6_neighbor = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv6_neighbor    percentage                     60                90

"""

crm_new_show_thresholds_ipv6_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv6_nexthop     percentage                     60                90

"""

crm_new_show_thresholds_ipv6_route= """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipv6_route       percentage                     60                90

"""

crm_new_show_thresholds_nexthop_group_member = """\

Resource Name         Threshold Type      Low Threshold    High Threshold
--------------------  ----------------  ---------------  ----------------
nexthop_group_member  percentage                     60                90

"""

crm_new_show_thresholds_nexthop_group_object = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
nexthop_group    percentage                     60                90

"""

crm_new_show_thresholds_snat = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
snat_entry       percentage                     60                90

"""

crm_new_show_thresholds_dnat = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
dnat_entry       percentage                     60                90

"""

crm_new_show_thresholds_mpls_inseg = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
mpls_inseg       percentage                     60                90

"""

crm_new_show_thresholds_mpls_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
mpls_nexthop     percentage                     60                90

"""

crm_new_show_thresholds_ipmc = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipmc_entry       percentage                     60                90

"""

crm_new_show_thresholds_srv6_my_sid_entry = """\

Resource Name      Threshold Type      Low Threshold    High Threshold
-----------------  ----------------  ---------------  ----------------
srv6_my_sid_entry  percentage                     60                90

"""

crm_new_show_thresholds_srv6_nexthop = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
srv6_nexthop     percentage                     60                90

"""

crm_new_show_thresholds_ipmc = """\

Resource Name    Threshold Type      Low Threshold    High Threshold
---------------  ----------------  ---------------  ----------------
ipmc_entry       percentage                     60                90

"""

crm_show_resources_acl_group = """\

Stage    Bind Point    Resource Name      Used Count    Available Count
-------  ------------  ---------------  ------------  -----------------
INGRESS  PORT          acl_group                  16                232
INGRESS  PORT          acl_table                   2                  3
INGRESS  LAG           acl_group                   8                232
INGRESS  LAG           acl_table                   0                  3
INGRESS  VLAN          acl_group                   0                232
INGRESS  VLAN          acl_table                   0                  6
INGRESS  RIF           acl_group                   0                232
INGRESS  RIF           acl_table                   0                  6
INGRESS  SWITCH        acl_group                   0                232
INGRESS  SWITCH        acl_table                   0                  6
EGRESS   PORT          acl_group                   0                232
EGRESS   PORT          acl_table                   0                  2
EGRESS   LAG           acl_group                   0                232
EGRESS   LAG           acl_table                   0                  2
EGRESS   VLAN          acl_group                   0                232
EGRESS   VLAN          acl_table                   0                  2
EGRESS   RIF           acl_group                   0                232
EGRESS   RIF           acl_table                   0                  2
EGRESS   SWITCH        acl_group                   0                232
EGRESS   SWITCH        acl_table                   0                  2

"""

crm_show_resources_acl_table = """\

Table ID         Resource Name      Used Count    Available Count
---------------  ---------------  ------------  -----------------
0x700000000063f  acl_entry                   0               2048
0x700000000063f  acl_counter                 0               2048
0x7000000000670  acl_entry                   0               1024
0x7000000000670  acl_counter                 0               1280

"""

crm_show_resources_all = """\

Resource Name           Used Count    Available Count
--------------------  ------------  -----------------
ipv4_route                      58              98246
ipv6_route                      60              16324
ipv4_nexthop                     8              49086
ipv6_nexthop                     8              49086
ipv4_neighbor                    8               8168
ipv6_neighbor                    8               4084
nexthop_group_member             0              16384
nexthop_group                    0                512
fdb_entry                        0              32767
ipmc_entry                       0              24576
snat_entry                       0               1024
dnat_entry                       0               1024
mpls_inseg                       0               1024
mpls_nexthop                     0               1024
srv6_nexthop                     0               1024
srv6_my_sid_entry                0               1024


Stage    Bind Point    Resource Name      Used Count    Available Count
-------  ------------  ---------------  ------------  -----------------
INGRESS  PORT          acl_group                  16                232
INGRESS  PORT          acl_table                   2                  3
INGRESS  LAG           acl_group                   8                232
INGRESS  LAG           acl_table                   0                  3
INGRESS  VLAN          acl_group                   0                232
INGRESS  VLAN          acl_table                   0                  6
INGRESS  RIF           acl_group                   0                232
INGRESS  RIF           acl_table                   0                  6
INGRESS  SWITCH        acl_group                   0                232
INGRESS  SWITCH        acl_table                   0                  6
EGRESS   PORT          acl_group                   0                232
EGRESS   PORT          acl_table                   0                  2
EGRESS   LAG           acl_group                   0                232
EGRESS   LAG           acl_table                   0                  2
EGRESS   VLAN          acl_group                   0                232
EGRESS   VLAN          acl_table                   0                  2
EGRESS   RIF           acl_group                   0                232
EGRESS   RIF           acl_table                   0                  2
EGRESS   SWITCH        acl_group                   0                232
EGRESS   SWITCH        acl_table                   0                  2


Table ID         Resource Name      Used Count    Available Count
---------------  ---------------  ------------  -----------------
0x700000000063f  acl_entry                   0               2048
0x700000000063f  acl_counter                 0               2048
0x7000000000670  acl_entry                   0               1024
0x7000000000670  acl_counter                 0               1280

"""

crm_show_resources_fdb = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
fdb_entry                   0              32767

"""

crm_show_resources_ipv4_neighbor = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_neighbor               8               8168

"""

crm_show_resources_ipv4_nexthop = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_nexthop                8              49086

"""

crm_show_resources_ipv4_route = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_route                 58              98246

"""

crm_show_resources_ipv6_route = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_route                 60              16324

"""

crm_show_resources_ipv6_neighbor = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_neighbor               8               4084

"""

crm_show_resources_ipv6_nexthop = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_nexthop                8              49086

"""

crm_show_resources_nexthop_group_member = """\

Resource Name           Used Count    Available Count
--------------------  ------------  -----------------
nexthop_group_member             0              16384

"""

crm_show_resources_nexthop_group_object = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
nexthop_group               0                512

"""

crm_show_resources_snat = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
snat_entry                  0               1024

"""

crm_show_resources_dnat = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
dnat_entry                  0               1024

"""

crm_show_resources_mpls_inseg = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
mpls_inseg                  0               1024

"""

crm_show_resources_mpls_nexthop = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
mpls_nexthop                0               1024

"""

crm_show_resources_ipmc = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipmc_entry                  0              24576

"""

crm_show_resources_srv6_my_sid_entry = """\

Resource Name        Used Count    Available Count
-----------------  ------------  -----------------
srv6_my_sid_entry             0               1024

"""

crm_show_resources_srv6_nexthop = """\

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
srv6_nexthop                0               1024

"""
crm_multi_asic_show_resources_acl_group = """\

ASIC0

Stage    Bind Point    Resource Name      Used Count    Available Count
-------  ------------  ---------------  ------------  -----------------
INGRESS  PORT          acl_group                  16                232
INGRESS  PORT          acl_table                   2                  3
INGRESS  LAG           acl_group                   8                232
INGRESS  LAG           acl_table                   0                  3
INGRESS  VLAN          acl_group                   0                232
INGRESS  VLAN          acl_table                   0                  6
INGRESS  RIF           acl_group                   0                232
INGRESS  RIF           acl_table                   0                  6
INGRESS  SWITCH        acl_group                   0                232
INGRESS  SWITCH        acl_table                   0                  6
EGRESS   PORT          acl_group                   0                232
EGRESS   PORT          acl_table                   0                  2
EGRESS   LAG           acl_group                   0                232
EGRESS   LAG           acl_table                   0                  2
EGRESS   VLAN          acl_group                   0                232
EGRESS   VLAN          acl_table                   0                  2
EGRESS   RIF           acl_group                   0                232
EGRESS   RIF           acl_table                   0                  2
EGRESS   SWITCH        acl_group                   0                232
EGRESS   SWITCH        acl_table                   0                  2


ASIC1

Stage    Bind Point    Resource Name      Used Count    Available Count
-------  ------------  ---------------  ------------  -----------------
INGRESS  PORT          acl_group                  16                232
INGRESS  PORT          acl_table                   2                  3
INGRESS  LAG           acl_group                   8                232
INGRESS  LAG           acl_table                   0                  3
INGRESS  VLAN          acl_group                   0                232
INGRESS  VLAN          acl_table                   0                  6
INGRESS  RIF           acl_group                   0                232
INGRESS  RIF           acl_table                   0                  6
INGRESS  SWITCH        acl_group                   0                232
INGRESS  SWITCH        acl_table                   0                  6
EGRESS   PORT          acl_group                   0                232
EGRESS   PORT          acl_table                   0                  2
EGRESS   LAG           acl_group                   0                232
EGRESS   LAG           acl_table                   0                  2
EGRESS   VLAN          acl_group                   0                232
EGRESS   VLAN          acl_table                   0                  2
EGRESS   RIF           acl_group                   0                232
EGRESS   RIF           acl_table                   0                  2
EGRESS   SWITCH        acl_group                   0                232
EGRESS   SWITCH        acl_table                   0                  2

"""

crm_multi_asic_show_resources_acl_table = """\

ASIC0

Table ID         Resource Name      Used Count    Available Count
---------------  ---------------  ------------  -----------------
0x700000000063f  acl_entry                   0               2048
0x700000000063f  acl_counter                 0               2048
0x7000000000670  acl_entry                   0               1024
0x7000000000670  acl_counter                 0               1280


ASIC1

Table ID         Resource Name      Used Count    Available Count
---------------  ---------------  ------------  -----------------
0x700000000063f  acl_entry                   0               2048
0x700000000063f  acl_counter                 0               2048
0x7000000000670  acl_entry                   0               1024
0x7000000000670  acl_counter                 0               1280

"""

crm_multi_asic_show_resources_all = """\

ASIC0

Resource Name           Used Count    Available Count
--------------------  ------------  -----------------
ipv4_route                      58              98246
ipv6_route                      60              16324
ipv4_nexthop                     8              49086
ipv6_nexthop                     8              49086
ipv4_neighbor                    8               8168
ipv6_neighbor                    8               4084
nexthop_group_member             0              16384
nexthop_group                    0                512
fdb_entry                        0              32767
ipmc_entry                       0              24576
snat_entry                       0               1024
dnat_entry                       0               1024
mpls_inseg                       0               1024
mpls_nexthop                     0               1024
srv6_nexthop                     0               1024
srv6_my_sid_entry                0               1024


ASIC1

Resource Name           Used Count    Available Count
--------------------  ------------  -----------------
ipv4_route                      58              98246
ipv6_route                      60              16324
ipv4_nexthop                     8              49086
ipv6_nexthop                     8              49086
ipv4_neighbor                    8               8168
ipv6_neighbor                    8               4084
nexthop_group_member             0              16384
nexthop_group                    0                512
fdb_entry                        0              32767
ipmc_entry                       0              24576
snat_entry                       0               1024
dnat_entry                       0               1024
mpls_inseg                       0               1024
mpls_nexthop                     0               1024
srv6_nexthop                     0               1024
srv6_my_sid_entry                0               1024


ASIC0

Stage    Bind Point    Resource Name      Used Count    Available Count
-------  ------------  ---------------  ------------  -----------------
INGRESS  PORT          acl_group                  16                232
INGRESS  PORT          acl_table                   2                  3
INGRESS  LAG           acl_group                   8                232
INGRESS  LAG           acl_table                   0                  3
INGRESS  VLAN          acl_group                   0                232
INGRESS  VLAN          acl_table                   0                  6
INGRESS  RIF           acl_group                   0                232
INGRESS  RIF           acl_table                   0                  6
INGRESS  SWITCH        acl_group                   0                232
INGRESS  SWITCH        acl_table                   0                  6
EGRESS   PORT          acl_group                   0                232
EGRESS   PORT          acl_table                   0                  2
EGRESS   LAG           acl_group                   0                232
EGRESS   LAG           acl_table                   0                  2
EGRESS   VLAN          acl_group                   0                232
EGRESS   VLAN          acl_table                   0                  2
EGRESS   RIF           acl_group                   0                232
EGRESS   RIF           acl_table                   0                  2
EGRESS   SWITCH        acl_group                   0                232
EGRESS   SWITCH        acl_table                   0                  2


ASIC1

Stage    Bind Point    Resource Name      Used Count    Available Count
-------  ------------  ---------------  ------------  -----------------
INGRESS  PORT          acl_group                  16                232
INGRESS  PORT          acl_table                   2                  3
INGRESS  LAG           acl_group                   8                232
INGRESS  LAG           acl_table                   0                  3
INGRESS  VLAN          acl_group                   0                232
INGRESS  VLAN          acl_table                   0                  6
INGRESS  RIF           acl_group                   0                232
INGRESS  RIF           acl_table                   0                  6
INGRESS  SWITCH        acl_group                   0                232
INGRESS  SWITCH        acl_table                   0                  6
EGRESS   PORT          acl_group                   0                232
EGRESS   PORT          acl_table                   0                  2
EGRESS   LAG           acl_group                   0                232
EGRESS   LAG           acl_table                   0                  2
EGRESS   VLAN          acl_group                   0                232
EGRESS   VLAN          acl_table                   0                  2
EGRESS   RIF           acl_group                   0                232
EGRESS   RIF           acl_table                   0                  2
EGRESS   SWITCH        acl_group                   0                232
EGRESS   SWITCH        acl_table                   0                  2


ASIC0

Table ID         Resource Name      Used Count    Available Count
---------------  ---------------  ------------  -----------------
0x700000000063f  acl_entry                   0               2048
0x700000000063f  acl_counter                 0               2048
0x7000000000670  acl_entry                   0               1024
0x7000000000670  acl_counter                 0               1280


ASIC1

Table ID         Resource Name      Used Count    Available Count
---------------  ---------------  ------------  -----------------
0x700000000063f  acl_entry                   0               2048
0x700000000063f  acl_counter                 0               2048
0x7000000000670  acl_entry                   0               1024
0x7000000000670  acl_counter                 0               1280

"""

crm_multi_asic_show_resources_fdb = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
fdb_entry                   0              32767


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
fdb_entry                   0              32767

"""

crm_multi_asic_show_resources_ipv4_neighbor = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_neighbor               8               8168


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_neighbor               8               8168

"""

crm_multi_asic_show_resources_ipv4_nexthop = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_nexthop                8              49086


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_nexthop                8              49086

"""

crm_multi_asic_show_resources_ipv4_route = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_route                 58              98246


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv4_route                 58              98246

"""

crm_multi_asic_show_resources_ipv6_route = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_route                 60              16324


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_route                 60              16324

"""

crm_multi_asic_show_resources_ipv6_neighbor = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_neighbor               8               4084


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_neighbor               8               4084

"""

crm_multi_asic_show_resources_ipv6_nexthop = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_nexthop                8              49086


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipv6_nexthop                8              49086

"""

crm_multi_asic_show_resources_nexthop_group_member = """\

ASIC0

Resource Name           Used Count    Available Count
--------------------  ------------  -----------------
nexthop_group_member             0              16384


ASIC1

Resource Name           Used Count    Available Count
--------------------  ------------  -----------------
nexthop_group_member             0              16384

"""

crm_multi_asic_show_resources_nexthop_group_object = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
nexthop_group               0                512


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
nexthop_group               0                512

"""

crm_multi_asic_show_resources_snat = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
snat_entry                  0               1024


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
snat_entry                  0               1024

"""

crm_multi_asic_show_resources_dnat = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
dnat_entry                  0               1024


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
dnat_entry                  0               1024

"""

crm_multi_asic_show_resources_mpls_inseg = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
mpls_inseg                  0               1024


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
mpls_inseg                  0               1024

"""

crm_multi_asic_show_resources_mpls_nexthop = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
mpls_nexthop                0               1024


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
mpls_nexthop                0               1024

"""

crm_multi_asic_show_resources_ipmc = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipmc_entry                  0              24576


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
ipmc_entry                  0              24576

"""

crm_multi_asic_show_resources_srv6_my_sid_entry = """\

ASIC0

Resource Name        Used Count    Available Count
-----------------  ------------  -----------------
srv6_my_sid_entry             0               1024


ASIC1

Resource Name        Used Count    Available Count
-----------------  ------------  -----------------
srv6_my_sid_entry             0               1024

"""

crm_multi_asic_show_resources_srv6_nexthop = """\

ASIC0

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
srv6_nexthop                0               1024


ASIC1

Resource Name      Used Count    Available Count
---------------  ------------  -----------------
srv6_nexthop                0               1024

"""

crm_config_interval_too_big = "Error: Invalid value for 'INTERVAL': 30000 is not in the range 1<=x<=9999."

class TestCrm(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_crm_show_summary(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'summary'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_summary
        result = runner.invoke(crm.cli, ['config', 'polling', 'interval', '30'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'summary'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_summary

    def test_crm_config_polling_interval(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['config', 'polling', 'interval', '10'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        result = runner.invoke(crm.cli, ['config', 'polling', 'interval', '30000'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 2
        assert crm_config_interval_too_big in result.output


    def test_crm_show_thresholds_acl_group(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'group'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_acl_group
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'group', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'group', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'group'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_acl_group

    def test_crm_show_thresholds_acl_table(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'table'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_acl_table
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'table', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'table', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'table'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_acl_table

    def test_crm_show_thresholds_all(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'all'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_all

    def test_crm_show_thresholds_fdb(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'fdb'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_fdb
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'fdb', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'fdb', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'fdb'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_fdb

    def test_crm_show_thresholds_ipv4_neighbor(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv4_neighbor
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'neighbor', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'neighbor', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv4_neighbor

    def test_crm_show_thresholds_ipv4_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv4_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv4_nexthop

    def test_crm_show_thresholds_ipv4_route(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv4_route
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv4_route

    def test_crm_show_thresholds_ipv6_neighbor(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv6_neighbor
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv6_neighbor

    def test_crm_show_thresholds_ipv6_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv6_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv6_nexthop

    def test_crm_show_thresholds_ipv6_route(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv6_route
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'route', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'route', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv6_route

    def test_crm_show_thresholds_nexthop_group_member(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'member'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_nexthop_group_member
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'member', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'member', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'member'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_nexthop_group_member

    def test_crm_show_thresholds_nexthop_group_object(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'object'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_nexthop_group_object
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'object', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'object', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'object'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_nexthop_group_object

    def test_crm_show_thresholds_snat(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'snat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_snat
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'snat', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'snat', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'snat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_snat

    def test_crm_show_thresholds_dnat(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'dnat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_dnat
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'dnat', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'dnat', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'dnat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_dnat

    def test_crm_show_thresholds_mpls_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_mpls_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_mpls_nexthop

    def test_crm_show_thresholds_mpls_inseg(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'inseg'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_mpls_inseg
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'inseg', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'inseg', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'inseg'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_mpls_inseg

    def test_crm_show_thresholds_ipmc(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipmc'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipmc
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipmc', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipmc', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipmc'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipmc

    def test_crm_show_resources_acl_group(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'acl', 'group'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_acl_group

    def test_crm_show_resources_acl_table(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'acl', 'table'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_acl_table

    def test_crm_show_resources_all(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'all'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_all

    def test_crm_show_resources_fdb(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'fdb'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_fdb

    def test_crm_show_resources_ipv4_neighbor(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv4', 'neighbor'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipv4_neighbor

    def test_crm_show_resources_ipv4_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv4', 'nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipv4_nexthop

    def test_crm_show_resources_ipv4_route(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv4', 'route'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipv4_route

    def test_crm_show_resources_ipv6_route(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv6', 'route'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipv6_route

    def test_crm_show_resources_ipv6_neighbor(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv6', 'neighbor'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipv6_neighbor

    def test_crm_show_resources_ipv6_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv6', 'nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipv6_nexthop

    def test_crm_show_resources_nexthop_group_member(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'nexthop', 'group', 'member'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_nexthop_group_member

    def test_crm_show_resources_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'nexthop', 'group', 'object'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_nexthop_group_object

    def test_crm_show_resources_snat(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'snat'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_snat

    def test_crm_show_resources_dnat(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'dnat'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_dnat

    def test_crm_show_resources_mpls_inseg(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'mpls', 'inseg'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_mpls_inseg

    def test_crm_show_resources_mpls_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'mpls', 'nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_mpls_nexthop

    def test_crm_show_resources_ipmc(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipmc'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_ipmc

    def test_crm_show_resources_srv6_my_sid_entry(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'srv6-my-sid-entry'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_srv6_my_sid_entry

    def test_crm_show_resources_srv6_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'srv6-nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_resources_srv6_nexthop

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

class TestCrmMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_crm_show_summary(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'summary'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_summary
        result = runner.invoke(crm.cli, ['config', 'polling', 'interval', '30'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'summary'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_summary

    def test_crm_show_thresholds_acl_group(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'group'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_acl_group
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'group', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'group', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'group'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_acl_group

    def test_crm_show_thresholds_acl_table(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'table'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_acl_table
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'table', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'acl', 'table', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'acl', 'table'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_acl_table

    def test_crm_show_thresholds_all(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'all'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_all

    def test_crm_show_thresholds_fdb(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'fdb'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_fdb
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'fdb', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'fdb', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'fdb'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_fdb

    def test_crm_show_thresholds_ipv4_neighbor(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv4_neighbor
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'neighbor', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'neighbor', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv4_neighbor

    def test_crm_show_thresholds_ipv4_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv4_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv4_nexthop

    def test_crm_show_thresholds_ipv4_route(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv4_route
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv4', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv4_route

    def test_crm_show_thresholds_ipv6_neighbor(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv6_neighbor
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'neighbor'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv6_neighbor

    def test_crm_show_thresholds_ipv6_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv6_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv6_nexthop

    def test_crm_show_thresholds_ipv6_route(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipv6_route
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'route', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'route', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipv6', 'route'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipv6_route

    def test_crm_show_thresholds_nexthop_group_member(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'member'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_nexthop_group_member
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'member', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'member', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'member'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_nexthop_group_member

    def test_crm_show_thresholds_nexthop_group_object(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'object'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_nexthop_group_object
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'object', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'nexthop', 'group', 'object', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'nexthop', 'group', 'object'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_nexthop_group_object

    def test_crm_show_thresholds_snat(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'snat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_snat
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'snat', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'snat', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'snat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_snat

    def test_crm_show_thresholds_dnat(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'dnat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_dnat
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'dnat', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'dnat', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'dnat'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_dnat

    def test_crm_show_thresholds_mpls_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_mpls_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_mpls_nexthop

    def test_crm_show_thresholds_mpls_inseg(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'inseg'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_mpls_inseg
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'inseg', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'mpls', 'inseg', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'mpls', 'inseg'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_mpls_inseg

    def test_crm_show_thresholds_ipmc(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipmc'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_ipmc
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipmc', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipmc', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'ipmc'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_ipmc


    def test_crm_show_thresholds_srv6_nexthop(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'srv6-nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_srv6_nexthop
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'srv6-nexthop', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'srv6-nexthop', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'srv6-nexthop'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_srv6_nexthop

    def test_crm_show_thresholds_srv6_my_sid_entry(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'srv6-my-sid-entry'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_show_thresholds_srv6_my_sid_entry
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'srv6-my-sid-entry', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'srv6-my-sid-entry', 'low', '60'], obj=db)
        print(sys.stderr, result.output)
        result = runner.invoke(crm.cli, ['show', 'thresholds', 'srv6-my-sid-entry'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_new_show_thresholds_srv6_my_sid_entry

    def test_crm_multi_asic_show_resources_acl_group(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'acl', 'group'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_acl_group

    def test_crm_multi_asic_show_resources_acl_table(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'acl', 'table'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_acl_table

    def test_crm_multi_asic_show_resources_all(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'all'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_all

    def test_crm_multi_asic_show_resources_fdb(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'fdb'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_fdb

    def test_crm_multi_asic_show_resources_ipv4_neighbor(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv4', 'neighbor'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipv4_neighbor

    def test_crm_multi_asic_show_resources_ipv4_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv4', 'nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipv4_nexthop

    def test_crm_multi_asic_show_resources_ipv4_route(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv4', 'route'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipv4_route

    def test_crm_multi_asic_show_resources_ipv6_route(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv6', 'route'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipv6_route

    def test_crm_multi_asic_show_resources_ipv6_neighbor(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv6', 'neighbor'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipv6_neighbor

    def test_crm_multi_asic_show_resources_ipv6_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipv6', 'nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipv6_nexthop

    def test_crm_multi_asic_show_resources_nexthop_group_member(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'nexthop', 'group', 'member'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_nexthop_group_member

    def test_crm_multi_asic_show_resources_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'nexthop', 'group', 'object'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_nexthop_group_object

    def test_crm_multi_asic_show_resources_snat(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'snat'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_snat

    def test_crm_multi_asic_show_resources_dnat(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'dnat'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_dnat

    def test_crm_multi_asic_show_resources_mpls_inseg(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'mpls', 'inseg'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_mpls_inseg

    def test_crm_multi_asic_show_resources_mpls_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'mpls', 'nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_mpls_nexthop

    def test_crm_multi_asic_show_resources_ipmc(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'ipmc'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_ipmc

    def test_crm_multi_asic_show_resources_srv6_my_sid_entry(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'srv6-my-sid-entry'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_srv6_my_sid_entry

    def test_crm_multi_asic_show_resources_srv6_nexthop(self):
        runner = CliRunner()
        result = runner.invoke(crm.cli, ['show', 'resources', 'srv6-nexthop'])
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        assert result.output == crm_multi_asic_show_resources_srv6_nexthop

    def test_crm_config_thresholds_percentage_over_100(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'high', '150'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 1
        assert "Error: Invalid value for threshold: 150. Percentage threshold must be <= 100." in result.output
        
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'low', '101'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 1
        assert "Error: Invalid value for threshold: 101. Percentage threshold must be <= 100." in result.output

    def test_crm_config_thresholds_low_greater_than_high(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'high', '90'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'low', '95'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 1
        assert "Error: Invalid value for threshold: 95. Low threshold must be less than high threshold (90)." in result.output

    def test_crm_config_thresholds_high_less_than_low(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'route', 'low', '50'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'route', 'high', '40'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 1
        assert "Error: Invalid value for threshold: 40. High threshold must be greater than low threshold (50)." in result.output

    def test_crm_config_thresholds_valid_values(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'high', '100'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv4', 'route', 'low', '50'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'low', '30'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
        
        result = runner.invoke(crm.cli, ['config', 'thresholds', 'ipv6', 'neighbor', 'high', '80'], obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()
