bgp_v4_network = \
"""
BGP table version is 6405, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*= 0.0.0.0/0        10.0.0.63                              0 64600 65534 6666 6667 i
*=                  10.0.0.61                              0 64600 65534 6666 6667 i
*=                  10.0.0.59                              0 64600 65534 6666 6667 i
*>                  10.0.0.57                              0 64600 65534 6666 6667 i
*> 10.1.0.32/32     0.0.0.0                  0         32768 i
*> 100.1.0.29/32    10.0.0.57                              0 64600 i
*> 100.1.0.30/32    10.0.0.59                              0 64600 i
*> 100.1.0.31/32    10.0.0.61                              0 64600 i
*> 100.1.0.32/32    10.0.0.63                              0 64600 i
*> 192.168.0.0/21   0.0.0.0                  0         32768 i
*= 192.168.8.0/25   10.0.0.63                              0 64600 65501 i
*=                  10.0.0.61                              0 64600 65501 i
*=                  10.0.0.59                              0 64600 65501 i
*>                  10.0.0.57                              0 64600 65501 i
*= 192.168.8.128/25 10.0.0.63                              0 64600 65501 i
*=                  10.0.0.61                              0 64600 65501 i
*=                  10.0.0.59                              0 64600 65501 i
*>                  10.0.0.57                              0 64600 65501 i
*= 192.168.16.0/25  10.0.0.63                              0 64600 65502 i
*=                  10.0.0.61                              0 64600 65502 i
*=                  10.0.0.59                              0 64600 65502 i
*>                  10.0.0.57                              0 64600 65502 i
*= 192.168.16.128/25
                    10.0.0.63                              0 64600 65502 i
*=                  10.0.0.61                              0 64600 65502 i
*=                  10.0.0.59                              0 64600 65502 i
*>                  10.0.0.57                              0 64600 65502 i
*= 192.168.24.0/25  10.0.0.63                              0 64600 65503 i
*=                  10.0.0.61                              0 64600 65503 i
*=                  10.0.0.59                              0 64600 65503 i
*>                  10.0.0.57                              0 64600 65503 i
*= 192.168.24.128/25
                    10.0.0.63                              0 64600 65503 i
*=                  10.0.0.61                              0 64600 65503 i
*=                  10.0.0.59                              0 64600 65503 i
*>                  10.0.0.57                              0 64600 65503 i
*= 192.168.32.0/25  10.0.0.63                              0 64600 65504 i
*=                  10.0.0.61                              0 64600 65504 i
*=                  10.0.0.59                              0 64600 65504 i
*>                  10.0.0.57                              0 64600 65504 i
"""

bgp_v4_network_ip_address = \
"""
BGP routing table entry for 193.11.248.128/25
Paths: (4 available, best #4, table default)
  Advertised to non peer-group peers:
  10.0.0.57 10.0.0.59 10.0.0.61 10.0.0.63
  64600 65534 64799 65515
    10.0.0.61 from 10.0.0.61 (100.1.0.31)
      Origin IGP, valid, external, multipath
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:41 2021
  64600 65534 64799 65515
    10.0.0.59 from 10.0.0.59 (100.1.0.30)
      Origin IGP, valid, external, multipath
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:19 2021
  64600 65534 64799 65515
    10.0.0.63 from 10.0.0.63 (100.1.0.32)
      Origin IGP, valid, external, multipath
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:16 2021
  64600 65534 64799 65515
    10.0.0.57 from 10.0.0.57 (100.1.0.29)
      Origin IGP, valid, external, multipath, best (Router ID)
    Community: 5060:12345
      Last update: Tue Apr 20 05:54:16 2021 
"""

bgp_v4_network_longer_prefixes_error = \
"""The parameter option: "longer-prefixes" only available if passing a network prefix
EX: 'show ip bgp network 10.0.0.0/24 longer-prefixes'
Aborted!
"""

bgp_v4_network_bestpath = \
"""
BGP routing table entry for 193.11.248.128/25
Paths: (4 available, best #4, table default)
  Advertised to non peer-group peers:
  10.0.0.57 10.0.0.59 10.0.0.61 10.0.0.63
  64600 65534 64799 65515
    10.0.0.57 from 10.0.0.57 (100.1.0.29)
      Origin IGP, valid, external, multipath, best (Router ID)
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:15 2021
"""

bgp_v6_network = \
"""
BGP table version is 6407, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*= ::/0             fc00::7e                               0 64600 65534 6666 6667 i
*=                  fc00::7a                               0 64600 65534 6666 6667 i
*=                  fc00::76                               0 64600 65534 6666 6667 i
*>                  fc00::72                               0 64600 65534 6666 6667 i
*> 2064:100::1d/128 fc00::72                               0 64600 i
*> 2064:100::1e/128 fc00::76                               0 64600 i
*> 2064:100::1f/128 fc00::7a                               0 64600 i
*> 2064:100::20/128 fc00::7e                               0 64600 i
*= 20c0:a808::/64   fc00::7e                               0 64600 65501 i
*=                  fc00::7a                               0 64600 65501 i
*=                  fc00::76                               0 64600 65501 i
*>                  fc00::72                               0 64600 65501 i
*= 20c0:a808:0:80::/64
                    fc00::7e                               0 64600 65501 i
*=                  fc00::7a                               0 64600 65501 i
*=                  fc00::76                               0 64600 65501 i
*>                  fc00::72                               0 64600 65501 i
*= 20c0:a810::/64   fc00::7e                               0 64600 65502 i
*=                  fc00::7a                               0 64600 65502 i
*=                  fc00::76                               0 64600 65502 i
*>                  fc00::72                               0 64600 65502 i
*= 20c0:a810:0:80::/64
                    fc00::7e                               0 64600 65502 i
*=                  fc00::7a                               0 64600 65502 i
*=                  fc00::76                               0 64600 65502 i
*>                  fc00::72                               0 64600 65502 i
*= 20c0:a818::/64   fc00::7e                               0 64600 65503 i
*=                  fc00::7a                               0 64600 65503 i
*=                  fc00::76                               0 64600 65503 i
*>                  fc00::72                               0 64600 65503 i
*= 20c0:a818:0:80::/64
                    fc00::7e                               0 64600 65503 i
*=                  fc00::7a                               0 64600 65503 i
*=                  fc00::76                               0 64600 65503 i
*>                  fc00::72                               0 64600 65503 i
*= 20c0:a820::/64   fc00::7e                               0 64600 65504 i
*=                  fc00::7a                               0 64600 65504 i
*=                  fc00::76                               0 64600 65504 i
*>                  fc00::72                               0 64600 65504 i
*= 20c0:a820:0:80::/64
                    fc00::7e                               0 64600 65504 i
*=                  fc00::7a                               0 64600 65504 i
*=                  fc00::76                               0 64600 65504 i
*>                  fc00::72                               0 64600 65504 i 
"""

bgp_v6_network_ip_address = \
"""
BGP routing table entry for 20c0:a820:0:80::/64
Paths: (4 available, best #4, table default)
  Advertised to non peer-group peers:
  fc00::72 fc00::76 fc00::7a fc00::7e
  64600 65504
    fc00::7e from fc00::7e (100.1.0.32)
    (fe80::1850:e9ff:fef9:27cb) (prefer-global)
      Origin IGP, valid, external, multipath
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:17 2021
  64600 65504
    fc00::7a from fc00::7a (100.1.0.31)
    (fe80::1810:25ff:fe01:c153) (prefer-global)
      Origin IGP, valid, external, multipath
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:17 2021
  64600 65504
    fc00::76 from fc00::76 (100.1.0.30)
    (fe80::80a7:74ff:fee1:d66d) (prefer-global)
      Origin IGP, valid, external, multipath
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:17 2021
  64600 65504
    fc00::72 from fc00::72 (100.1.0.29)
    (fe80::90ec:bcff:fe4b:1e3e) (prefer-global)
      Origin IGP, valid, external, multipath, best (Router ID)
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:16 2021 
"""

bgp_v6_network_longer_prefixes_error = \
"""The parameter option: "longer-prefixes" only available if passing a network prefix
EX: 'show ipv6 bgp network fc00:1::/64 longer-prefixes'
Aborted!
"""

bgp_v6_network_longer_prefixes = \
"""
BGP table version is 6407, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*= 20c0:a820:0:80::/64
                    fc00::7e                               0 64600 65504 i
*=                  fc00::7a                               0 64600 65504 i
*=                  fc00::76                               0 64600 65504 i
*>                  fc00::72                               0 64600 65504 i

Displayed  1 routes and 25602 total paths 
"""

bgp_v6_network_bestpath = \
"""
BGP routing table entry for 20c0:a820:0:80::/64
Paths: (4 available, best #4, table default)
  Advertised to non peer-group peers:
  fc00::72 fc00::76 fc00::7a fc00::7e
  64600 65504
    fc00::72 from fc00::72 (100.1.0.29)
    (fe80::90ec:bcff:fe4b:1e3e) (prefer-global)
      Origin IGP, valid, external, multipath, best (Router ID)
      Community: 5060:12345
      Last update: Tue Apr 20 05:54:15 2021 
"""

multi_asic_bgp_network_err = \
"""Error: -n/--namespace option required. provide namespace from list ['asic0', 'asic1']"""

multi_asic_bgp_network_asic_unknown_err = \
  """Error: invalid namespace asic_unknown. provide namespace from list ['asic0', 'asic1']"""

bgp_v4_network_asic0 = \
"""
BGP table version is 11256, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
* i0.0.0.0/0        10.1.0.2                      100      0 65200 6666 6667 i
* i                 10.1.0.0                      100      0 65200 6666 6667 i
*=                  10.0.0.5                               0 65200 6666 6667 i
*>                  10.0.0.1                               0 65200 6666 6667 i
* i8.0.0.0/32       10.1.0.2                 0    100      0 i
* i                 10.1.0.0                 0    100      0 i
*                   0.0.0.0                  0         32768 ?
*>                  0.0.0.0                  0         32768 i
*=i8.0.0.1/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*=i8.0.0.2/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*=i8.0.0.3/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*>i8.0.0.4/32       10.1.0.0                 0    100      0 i
*>i8.0.0.5/32       10.1.0.2                 0    100      0 i
* i10.0.0.0/31      10.1.0.2                 0    100      0 ?
* i                 10.1.0.0                 0    100      0 ?
*>                  0.0.0.0                  0         32768 ?
* i10.0.0.4/31      10.1.0.2                 0    100      0 ?
* i                 10.1.0.0                 0    100      0 ?
*>                  0.0.0.0                  0         32768 ?
*=i10.0.0.8/31      10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.12/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.32/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.34/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.36/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.38/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.40/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.42/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.44/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
"""

bgp_v4_network_ip_address_asic0 = \
"""
 BGP routing table entry for 10.0.0.44/31
Paths: (2 available, best #2, table default, not advertised outside local AS)
  Not advertised to any peer
  Local
    10.1.0.2 from 10.1.0.2 (8.0.0.5)
      Origin incomplete, metric 0, localpref 100, valid, internal, multipath
      Community: local-AS
      Originator: 8.0.0.5, Cluster list: 8.0.0.5
      Last update: Thu Apr 22 02:13:31 2021

  Local
    10.1.0.0 from 10.1.0.0 (8.0.0.4)
      Origin incomplete, metric 0, localpref 100, valid, internal, multipath, best (Router ID)
      Community: local-AS
      Originator: 8.0.0.4, Cluster list: 8.0.0.4
      Last update: Thu Apr 22 02:13:31 2021
"""
bgp_v4_network_bestpath_asic0 = \
"""
BGP routing table entry for 10.0.0.44/31
Paths: (2 available, best #2, table default, not advertised outside local AS)
  Not advertised to any peer
  Local
    10.1.0.0 from 10.1.0.0 (8.0.0.4)
      Origin incomplete, metric 0, localpref 100, valid, internal, multipath, best (Router ID)
      Community: local-AS
      Originator: 8.0.0.4, Cluster list: 8.0.0.4
      Last update: Thu Apr 22 02:13:30 2021 
"""

bgp_v4_network_all_asic = \
  """
======== namespace asic0 ========

BGP table version is 11256, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
* i0.0.0.0/0        10.1.0.2                      100      0 65200 6666 6667 i
* i                 10.1.0.0                      100      0 65200 6666 6667 i
*=                  10.0.0.5                               0 65200 6666 6667 i
*>                  10.0.0.1                               0 65200 6666 6667 i
* i8.0.0.0/32       10.1.0.2                 0    100      0 i
* i                 10.1.0.0                 0    100      0 i
*                   0.0.0.0                  0         32768 ?
*>                  0.0.0.0                  0         32768 i
*=i8.0.0.1/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*=i8.0.0.2/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*=i8.0.0.3/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*>i8.0.0.4/32       10.1.0.0                 0    100      0 i
*>i8.0.0.5/32       10.1.0.2                 0    100      0 i
* i10.0.0.0/31      10.1.0.2                 0    100      0 ?
* i                 10.1.0.0                 0    100      0 ?
*>                  0.0.0.0                  0         32768 ?
* i10.0.0.4/31      10.1.0.2                 0    100      0 ?
* i                 10.1.0.0                 0    100      0 ?
*>                  0.0.0.0                  0         32768 ?
*=i10.0.0.8/31      10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.12/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.32/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.34/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.36/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.38/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.40/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.42/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.44/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?

======== namespace asic1 ========

BGP table version is 11256, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
* i0.0.0.0/0        10.1.0.2                      100      0 65200 6666 6667 i
* i                 10.1.0.0                      100      0 65200 6666 6667 i
*=                  10.0.0.5                               0 65200 6666 6667 i
*>                  10.0.0.1                               0 65200 6666 6667 i
* i8.0.0.0/32       10.1.0.2                 0    100      0 i
* i                 10.1.0.0                 0    100      0 i
*                   0.0.0.0                  0         32768 ?
*>                  0.0.0.0                  0         32768 i
*=i8.0.0.1/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*=i8.0.0.2/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*=i8.0.0.3/32       10.1.0.2                 0    100      0 i
*>i                 10.1.0.0                 0    100      0 i
*>i8.0.0.4/32       10.1.0.0                 0    100      0 i
*>i8.0.0.5/32       10.1.0.2                 0    100      0 i
* i10.0.0.0/31      10.1.0.2                 0    100      0 ?
* i                 10.1.0.0                 0    100      0 ?
*>                  0.0.0.0                  0         32768 ?
* i10.0.0.4/31      10.1.0.2                 0    100      0 ?
* i                 10.1.0.0                 0    100      0 ?
*>                  0.0.0.0                  0         32768 ?
*=i10.0.0.8/31      10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.12/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.32/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.34/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.36/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.38/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.40/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.42/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
*=i10.0.0.44/31     10.1.0.2                 0    100      0 ?
*>i                 10.1.0.0                 0    100      0 ?
"""

bgp_v6_network_asic0 = \
"""
BGP table version is 12849, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
* i::/0             2603:10e2:400:1::1
                                                  100      0 65200 6666 6667 i
* i                 2603:10e2:400:1::5
                                                  100      0 65200 6666 6667 i
*=                  fc00::6                                0 65200 6666 6667 i
*>                  fc00::2                                0 65200 6666 6667 i
* i2064:100::1/128  2603:10e2:400:1::1
                                                  100      0 65200 i
* i                 2603:10e2:400:1::5
                                                  100      0 65200 i
*>                  fc00::2                                0 65200 i
* i2064:100::3/128  2603:10e2:400:1::1
                                                  100      0 65200 i
* i                 2603:10e2:400:1::5
                                                  100      0 65200 i
*>                  fc00::6                                0 65200 i
*=i2064:100::5/128  2603:10e2:400:1::5
                                                  100      0 65200 i
*>i                 2603:10e2:400:1::1
                                                  100      0 65200 i
*>i2064:100::7/128  2603:10e2:400:1::1
                                                  100      0 65200 i
*=i                 2603:10e2:400:1::5
                                                  100      0 65200 i
*>i20c0:a800::/64   2603:10e2:400:1::1
                                                  100      0 64004 i
*=i                 2603:10e2:400:1::5
                                                  100      0 64004 i
*>i20c0:a800:0:80::/64
                    2603:10e2:400:1::1
                                                  100      0 64004 i
*=i                 2603:10e2:400:1::5
                                                  100      0 64004 i
*>i20c0:a808::/64   2603:10e2:400:1::1
                                                  100      0 64004 i
*=i                 2603:10e2:400:1::5
                                                  100      0 64004 i 
"""

bgp_v6_network_ip_address_asic0 = \
"""
BGP routing table entry for 20c0:a808:0:80::/64
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  fc00::2 fc00::6
  64004
    2603:10e2:400:1::1 from 2603:10e2:400:1::1 (8.0.0.4)
      Origin IGP, localpref 100, valid, internal, multipath, best (Router ID)
      Community: 8075:8823
      Originator: 8.0.0.4, Cluster list: 8.0.0.4
      Last update: Thu Apr 22 02:13:31 2021

  64004
    2603:10e2:400:1::5 from 2603:10e2:400:1::5 (8.0.0.5)
      Origin IGP, localpref 100, valid, internal, multipath
      Community: 8075:8823
      Originator: 8.0.0.5, Cluster list: 8.0.0.5
      Last update: Thu Apr 22 02:13:31 2021
"""

bgp_v6_network_ip_address_asic0_bestpath = \
"""
BGP routing table entry for 20c0:a808:0:80::/64
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  fc00::2 fc00::6
  64004
    2603:10e2:400:1::1 from 2603:10e2:400:1::1 (8.0.0.4)
      Origin IGP, localpref 100, valid, internal, multipath, best (Router ID)
      Community: 8075:8823
      Originator: 8.0.0.4, Cluster list: 8.0.0.4
      Last update: Thu Apr 22 02:13:30 2021
"""


def mock_show_bgp_network_single_asic(request):
    param = request.param
    if param == 'bgp_v4_network':
        return bgp_v4_network
    elif param == 'bgp_v4_network_ip_address':
        return bgp_v4_network_ip_address
    elif param == 'bgp_v4_network_bestpath':
        return bgp_v4_network_bestpath
    elif param == 'bgp_v6_network':
        return bgp_v6_network
    elif param == 'bgp_v6_network_ip_address':
        return bgp_v6_network_ip_address
    elif param == 'bgp_v6_network_longer_prefixes':
        return bgp_v6_network_longer_prefixes
    elif param == 'bgp_v6_network_bestpath':
        return bgp_v6_network_bestpath
    else:
        return ""


def mock_show_bgp_network_multi_asic(param):
    if param == "bgp_v4_network_asic0":
        return bgp_v4_network_asic0
    elif param == 'bgp_v4_network_ip_address_asic0':
        return bgp_v4_network_ip_address_asic0
    elif param == 'bgp_v4_network_bestpath_asic0':
        return bgp_v4_network_bestpath_asic0
    if param == "bgp_v6_network_asic0":
        return bgp_v4_network_asic0
    elif param == 'bgp_v6_network_ip_address_asic0':
        return bgp_v6_network_ip_address_asic0
    elif param == 'bgp_v6_network_bestpath_asic0':
        return bgp_v6_network_ip_address_asic0_bestpath
    elif param == "bgp_v4_network_all_asic":
        # this is mocking the output of a single LC
        return bgp_v4_network_asic0
    else:
        return ''


testData = {
    'bgp_v4_network': {
        'args': [],
        'rc': 0,
        'rc_output': bgp_v4_network
    },
    'bgp_v4_network_ip_address': {
        'args': [' 193.11.248.128/25'],
        'rc': 0,
        'rc_output': bgp_v4_network_ip_address
    },
    'bgp_v4_network_bestpath': {
        'args': [' 193.11.248.128/25', 'bestpath'],
        'rc': 0,
        'rc_output': bgp_v4_network_bestpath
    },
    'bgp_v4_network_longer_prefixes_error': {
        'args': [' 193.11.248.128', 'longer-prefixes'],
        'rc': 1,
        'rc_output': bgp_v4_network_longer_prefixes_error
    },
    'bgp_v4_network_all_asic_on_single_asic': {
        'args': ['-nall'],
        'rc': 0,
        'rc_output': bgp_v4_network
    },
    'bgp_v6_network': {
        'args': [],
        'rc': 0,
        'rc_output': bgp_v6_network
    },
    'bgp_v6_network_ip_address': {
        'args': [' 20c0:a820:0:80::/64'],
        'rc': 0,
        'rc_output': bgp_v6_network_ip_address
    },
    'bgp_v6_network_bestpath': {
        'args': [' 20c0:a820:0:80::/64', 'bestpath'],
        'rc': 0,
        'rc_output': bgp_v6_network_bestpath
    },
    'bgp_v6_network_longer_prefixes_error': {
        'args': [' 20c0:a820:0:80::', 'longer-prefixes'],
        'rc': 1,
        'rc_output': bgp_v6_network_longer_prefixes_error
    },
    'bgp_v6_network_longer_prefixes': {
        'args': [' 20c0:a820:0:80::/64', 'longer-prefixes'],
        'rc': 0,
        'rc_output': bgp_v6_network_longer_prefixes
    },
    'bgp_v4_network_multi_asic': {
        'args': [],
        'rc': 2,
        'rc_err_msg': multi_asic_bgp_network_err
    },
    'bgp_v4_network_asic0': {
        'args': ['-nasic0'],
        'rc': 0,
        'rc_output': bgp_v4_network_asic0
    },
    'bgp_v4_network_ip_address_asic0': {
        'args': ['-nasic0', '10.0.0.44'],
        'rc': 0,
        'rc_output': bgp_v4_network_ip_address_asic0
    },
    'bgp_v4_network_bestpath_asic0': {
        'args': ['-nasic0', '10.0.0.44', 'bestpath'],
        'rc': 0,
        'rc_output': bgp_v4_network_bestpath_asic0
    },
    'bgp_v4_network_all_asic': {
        'args': ['-nall'],
        'rc': 0,
        'rc_output': bgp_v4_network_all_asic
    },
    'bgp_v4_network_asic_unknown': {
        'args': ['-nasic_unknown'],
        'rc': 2,
        'rc_err_msg': multi_asic_bgp_network_asic_unknown_err
    },
    'bgp_v6_network_multi_asic': {
        'args': [],
        'rc': 2,
        'rc_err_msg': multi_asic_bgp_network_err
    },
    'bgp_v6_network_asic0': {
        'args': ['-nasic0'],
        'rc': 0,
        'rc_output': bgp_v4_network_asic0
    },
    'bgp_v6_network_ip_address_asic0': {
        'args': ['-nasic0', '20c0:a808:0:80::/64'],
        'rc': 0,
        'rc_output': bgp_v6_network_ip_address_asic0
    },
    'bgp_v6_network_bestpath_asic0': {
        'args': ['-nasic0', '20c0:a808:0:80::/64', 'bestpath'],
        'rc': 0,
        'rc_output': bgp_v6_network_ip_address_asic0_bestpath
    }
}