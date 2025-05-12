bgp_v4_neighbors_output = \
"""
BGP neighbor is 10.0.0.57, remote AS 64600, local AS 65100, external link
 Description: ARISTA01T1
 Member of peer-group PEER_V4 for session parameters
  BGP version 4, remote router ID 100.1.0.29, local router ID 10.1.0.32
  BGP state = Established, up for 00:00:39
  Last read 00:00:00, Last write 00:00:00
  Hold time is 10, keepalive interval is 3 seconds
  Configured hold time is 10, keepalive interval is 3 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv4 Unicast: RX advertised IPv4 Unicast and received
    Route refresh: advertised and received(new)
    Address Family IPv4 Unicast: advertised and received
    Hostname Capability: advertised (name: vlab-01,domain name: n/a) not received
    Graceful Restart Capability: advertised and received
      Remote Restart timer is 300 seconds
      Address families by peer:
        none
  Graceful restart information:
    End-of-RIB send: IPv4 Unicast
    End-of-RIB received: IPv4 Unicast
    Local GR Mode: Restart*
    Remote GR Mode: Helper
    R bit: False
    Timers:
      Configured Restart Time(sec): 240
      Received Restart Time(sec): 300
    IPv4 Unicast:
      F bit: False
      End-of-RIB sent: Yes
      End-of-RIB sent after update: No
      End-of-RIB received: Yes
      Timers:
        Configured Stale Path Time(sec): 360
        Configured Selection Deferral Time(sec): 360
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  2          1
    Notifications:          2          2
    Updates:             3203       3202
    Keepalives:            14         15
    Route Refresh:          0          0
    Capability:             0          0
    Total:               3221       3220
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv4 Unicast
  PEER_V4 peer-group member
  Update group 1, subgroup 1
  Packet Queue length 0
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_PEER_V4
  Route map for outgoing advertisements is *TO_BGP_PEER_V4
  6400 accepted prefixes

  Connections established 1; dropped 0
  Last reset 00:01:01,  No AFI/SAFI activated for peer
Local host: 10.0.0.56, Local port: 179
Foreign host: 10.0.0.57, Foreign port: 44731
Nexthop: 10.0.0.56
Nexthop global: fc00::71
Nexthop local: fe80::5054:ff:fea9:41c2
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 10
Estimated round trip time: 20 ms
Read thread: on  Write thread: on  FD used: 28
"""

bgp_v4_neighbors_output_vrf_all = \
"""
Instance default:
BGP neighbor is 10.0.0.57, remote AS 64600, local AS 65100, external link
 Description: ARISTA01T1
 Member of peer-group PEER_V4 for session parameters
  BGP version 4, remote router ID 100.1.0.29, local router ID 10.1.0.32
  BGP state = Established, up for 00:00:39
  Last read 00:00:00, Last write 00:00:00
  Hold time is 10, keepalive interval is 3 seconds
  Configured hold time is 10, keepalive interval is 3 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv4 Unicast: RX advertised IPv4 Unicast and received
    Route refresh: advertised and received(new)
    Address Family IPv4 Unicast: advertised and received
    Hostname Capability: advertised (name: vlab-01,domain name: n/a) not received
    Graceful Restart Capability: advertised and received
      Remote Restart timer is 300 seconds
      Address families by peer:
        none
  Graceful restart information:
    End-of-RIB send: IPv4 Unicast
    End-of-RIB received: IPv4 Unicast
    Local GR Mode: Restart*
    Remote GR Mode: Helper
    R bit: False
    Timers:
      Configured Restart Time(sec): 240
      Received Restart Time(sec): 300
    IPv4 Unicast:
      F bit: False
      End-of-RIB sent: Yes
      End-of-RIB sent after update: No
      End-of-RIB received: Yes
      Timers:
        Configured Stale Path Time(sec): 360
        Configured Selection Deferral Time(sec): 360
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  2          1
    Notifications:          2          2
    Updates:             3203       3202
    Keepalives:            14         15
    Route Refresh:          0          0
    Capability:             0          0
    Total:               3221       3220
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv4 Unicast
  PEER_V4 peer-group member
  Update group 1, subgroup 1
  Packet Queue length 0
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_PEER_V4
  Route map for outgoing advertisements is *TO_BGP_PEER_V4
  6400 accepted prefixes

  Connections established 1; dropped 0
  Last reset 00:01:01,  No AFI/SAFI activated for peer
Local host: 10.0.0.56, Local port: 179
Foreign host: 10.0.0.57, Foreign port: 44731
Nexthop: 10.0.0.56
Nexthop global: fc00::71
Nexthop local: fe80::5054:ff:fea9:41c2
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 10
Estimated round trip time: 20 ms
Read thread: on  Write thread: on  FD used: 28

Instance Vnet_90:
BGP neighbor is 192.168.109.11, remote AS 65100, local AS 64600, external link
 Description: vlab-01-4
 Member of peer-group PEER_V4 for session parameters
  BGP version 4, remote router ID 0.0.0.0, local router ID 192.168.109.10
  BGP state = Connect
  Last read 01:13:28, Last write never
  Hold time is 10 seconds, keepalive interval is 3 seconds
  Configured hold time is 10 seconds, keepalive interval is 3 seconds
  Graceful restart information:
    Local GR Mode: Helper*

    Remote GR Mode: NotApplicable

    R bit: False
    N bit: False
    Timers:
      Configured Restart Time(sec): 120
      Received Restart Time(sec): 0
      Configured LLGR Stale Path Time(sec): 0
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  0          0
    Notifications:          0          0
    Updates:                0          0
    Keepalives:             0          0
    Route Refresh:          0          0
    Capability:             0          0
    Total:                  0          0
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv4 Unicast
  PEER_V4 peer-group member
  Not part of any update group
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_PEER_V4
  Route map for outgoing advertisements is *TO_BGP_PEER_V4
  0 accepted prefixes

  Connections established 0; dropped 0
  Last reset 01:13:28,   Waiting for peer OPEN (n/a)
  External BGP neighbor may be up to 1 hops away.
BGP Connect Retry Timer in Seconds: 10
Next connect timer due in 8 seconds
Read thread: off  Write thread: off  FD used: 29
"""

bgp_v4_neighbors_output_invalid_vrf = \
"""
% No BGP neighbors found
"""

bgp_v4_neighbor_invalid = \
"""Error:  Bgp neighbor 20.1.1.1 not configured"""

bgp_v4_neighbor_invalid_address = \
"""Error: invalid_address is not valid ipv4 address"""

bgp_v4_neighbor_output_adv_routes = \
"""
BGP table version is 6405, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*> 0.0.0.0/0        0.0.0.0                                0 64600 65534 6666 6667 i
*> 10.1.0.32/32     0.0.0.0                  0         32768 i
*> 100.1.0.29/32    0.0.0.0                                0 64600 i
*> 100.1.0.30/32    0.0.0.0                                0 64600 i
*> 100.1.0.31/32    0.0.0.0                                0 64600 i
*> 100.1.0.32/32    0.0.0.0                                0 64600 i
*> 192.168.0.0/21   0.0.0.0                  0         32768 i
*> 192.168.8.0/25   0.0.0.0                                0 64600 65501 i
*> 192.168.8.128/25 0.0.0.0                                0 64600 65501 i
*> 192.168.16.0/25  0.0.0.0                                0 64600 65502 i
*> 192.168.16.128/25
                    0.0.0.0                                0 64600 65502 i
*> 192.168.24.0/25  0.0.0.0                                0 64600 65503 i
*> 192.168.24.128/25
                    0.0.0.0                                0 64600 65503 i
*> 192.168.32.0/25  0.0.0.0                                0 64600 65504 i
*> 192.168.32.128/25
                    0.0.0.0                                0 64600 65504 i
*> 192.168.40.0/25  0.0.0.0                                0 64600 65505 i
*> 192.168.40.128/25
                    0.0.0.0                                0 64600 65505 i
*> 192.168.48.0/25  0.0.0.0                                0 64600 65506 i
*> 192.168.48.128/25
                    0.0.0.0                                0 64600 65506 i
*> 192.168.56.0/25  0.0.0.0                                0 64600 65507 i
*> 192.168.56.128/25
                    0.0.0.0                                0 64600 65507 i
"""

bgp_v4_neighbor_output_recv_routes = \
"""
BGP table version is 6405, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*> 0.0.0.0/0        10.0.0.57                              0 64600 65534 6666 6667 i
*> 100.1.0.29/32    10.0.0.57                              0 64600 i
*> 192.168.8.0/25   10.0.0.57                              0 64600 65501 i
*> 192.168.8.128/25 10.0.0.57                              0 64600 65501 i
*> 192.168.16.0/25  10.0.0.57                              0 64600 65502 i
*> 192.168.16.128/25
                    10.0.0.57                              0 64600 65502 i
*> 192.168.24.0/25  10.0.0.57                              0 64600 65503 i
*> 192.168.24.128/25
                    10.0.0.57                              0 64600 65503 i
*> 192.168.32.0/25  10.0.0.57                              0 64600 65504 i
*> 192.168.32.128/25
                    10.0.0.57                              0 64600 65504 i
*> 192.168.40.0/25  10.0.0.57                              0 64600 65505 i
*> 192.168.40.128/25
                    10.0.0.57                              0 64600 65505 i
*> 192.168.48.0/25  10.0.0.57                              0 64600 65506 i
*> 192.168.48.128/25
                    10.0.0.57                              0 64600 65506 i
*> 192.168.56.0/25  10.0.0.57                              0 64600 65507 i
*> 192.168.56.128/25
                    10.0.0.57                              0 64600 65507 i 
"""

bgp_v6_neighbors_output = \
"""
BGP neighbor is fc00::72, remote AS 64600, local AS 65100, external link
 Description: ARISTA01T1
 Member of peer-group PEER_V6 for session parameters
  BGP version 4, remote router ID 100.1.0.29, local router ID 10.1.0.32
  BGP state = Established, up for 01:06:23
  Last read 00:00:02, Last write 00:00:00
  Hold time is 10, keepalive interval is 3 seconds
  Configured hold time is 10, keepalive interval is 3 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv6 Unicast: RX advertised IPv6 Unicast and received
    Route refresh: advertised and received(new)
    Address Family IPv6 Unicast: advertised and received
    Hostname Capability: advertised (name: vlab-01,domain name: n/a) not received
    Graceful Restart Capability: advertised and received
      Remote Restart timer is 300 seconds
      Address families by peer:
        none
  Graceful restart information:
    End-of-RIB send: IPv6 Unicast
    End-of-RIB received: IPv6 Unicast
    Local GR Mode: Restart*
    Remote GR Mode: Helper
    R bit: False
    Timers:
      Configured Restart Time(sec): 240
      Received Restart Time(sec): 300
    IPv6 Unicast:
      F bit: False
      End-of-RIB sent: Yes
      End-of-RIB sent after update: No
      End-of-RIB received: Yes
      Timers:
        Configured Stale Path Time(sec): 360
        Configured Selection Deferral Time(sec): 360
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  1          1
    Notifications:          0          0
    Updates:             3206       3202
    Keepalives:          1328       1329
    Route Refresh:          0          0
    Capability:             0          0
    Total:               4535       4532
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv6 Unicast
  PEER_V6 peer-group member
  Update group 2, subgroup 2
  Packet Queue length 0
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_PEER_V6
  Route map for outgoing advertisements is *TO_BGP_PEER_V6
  6400 accepted prefixes

  Connections established 1; dropped 0
  Last reset 01:06:46,  Waiting for peer OPEN
Local host: fc00::71, Local port: 59726
Foreign host: fc00::72, Foreign port: 179
Nexthop: 10.0.0.56
Nexthop global: fc00::71
Nexthop local: fe80::5054:ff:fea9:41c2
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 10
Estimated round trip time: 4 ms
Read thread: on  Write thread: on  FD used: 30
"""

bgp_v6_neighbors_output_vrf_all = \
"""
Instance default:
BGP neighbor is fc00::72, remote AS 64600, local AS 65100, external link
 Description: ARISTA01T1
 Member of peer-group PEER_V6 for session parameters
  BGP version 4, remote router ID 100.1.0.29, local router ID 10.1.0.32
  BGP state = Established, up for 01:06:23
  Last read 00:00:02, Last write 00:00:00
  Hold time is 10, keepalive interval is 3 seconds
  Configured hold time is 10, keepalive interval is 3 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv6 Unicast: RX advertised IPv6 Unicast and received
    Route refresh: advertised and received(new)
    Address Family IPv6 Unicast: advertised and received
    Hostname Capability: advertised (name: vlab-01,domain name: n/a) not received
    Graceful Restart Capability: advertised and received
      Remote Restart timer is 300 seconds
      Address families by peer:
        none
  Graceful restart information:
    End-of-RIB send: IPv6 Unicast
    End-of-RIB received: IPv6 Unicast
    Local GR Mode: Restart*
    Remote GR Mode: Helper
    R bit: False
    Timers:
      Configured Restart Time(sec): 240
      Received Restart Time(sec): 300
    IPv6 Unicast:
      F bit: False
      End-of-RIB sent: Yes
      End-of-RIB sent after update: No
      End-of-RIB received: Yes
      Timers:
        Configured Stale Path Time(sec): 360
        Configured Selection Deferral Time(sec): 360
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  1          1
    Notifications:          0          0
    Updates:             3206       3202
    Keepalives:          1328       1329
    Route Refresh:          0          0
    Capability:             0          0
    Total:               4535       4532
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv6 Unicast
  PEER_V6 peer-group member
  Update group 2, subgroup 2
  Packet Queue length 0
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_PEER_V6
  Route map for outgoing advertisements is *TO_BGP_PEER_V6
  6400 accepted prefixes

  Connections established 1; dropped 0
  Last reset 01:06:46,  Waiting for peer OPEN
Local host: fc00::71, Local port: 59726
Foreign host: fc00::72, Foreign port: 179
Nexthop: 10.0.0.56
Nexthop global: fc00::71
Nexthop local: fe80::5054:ff:fea9:41c2
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 10
Estimated round trip time: 4 ms
Read thread: on  Write thread: on  FD used: 30

Instance Vnet_90:
BGP neighbor is fc0a::ff, remote AS 64600, local AS 64600, internal link
  Local Role: undefined
  Remote Role: undefined
 Description: exabgp
 Member of peer-group PEER_V6 for session parameters
  BGP version 4, remote router ID 0.0.0.0, local router ID 100.1.0.32
  BGP state = Active
  Last read 1d10h05m, Last write never
  Hold time is 10 seconds, keepalive interval is 3 seconds
  Configured hold time is 10 seconds, keepalive interval is 3 seconds
  Configured tcp-mss is 0, synced tcp-mss is 0
  Configured conditional advertisements interval is 60 seconds
  Graceful restart information:
    Local GR Mode: Helper*

    Remote GR Mode: NotApplicable

    R bit: False
    N bit: False
    Timers:
      Configured Restart Time(sec): 120
      Received Restart Time(sec): 0
      Configured LLGR Stale Path Time(sec): 0
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  0          0
    Notifications:          0          0
    Updates:                0          0
    Keepalives:             0          0
    Route Refresh:          0          0
    Capability:             0          0
    Total:                  0          0
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv6 Unicast
  PEER_V6 peer-group member
  Not part of any update group
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_PEER_V6
  Route map for outgoing advertisements is *TO_BGP_PEER_V6
  0 accepted prefixes

  Connections established 0; dropped 0
  Last reset 1d10h05m,   Waiting for peer OPEN (n/a)
  Internal BGP neighbor may be up to 255 hops away.
BGP Connect Retry Timer in Seconds: 10
Next connect timer due in 6 seconds
Read thread: off  Write thread: off  FD used: -1
"""

bgp_v6_neighbors_output_invalid_vrf = \
"""
% No BGP neighbors found
"""

bgp_v6_neighbor_output_adv_routes = \
"""
BGP table version is 6407, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*> ::/0             ::                                     0 64600 65534 6666 6667 i
*> 2064:100::1d/128 ::                                     0 64600 i
*> 2064:100::1e/128 ::                                     0 64600 i
*> 2064:100::1f/128 ::                                     0 64600 i
*> 2064:100::20/128 ::                                     0 64600 i
*> 20c0:a808::/64   ::                                     0 64600 65501 i
*> 20c0:a808:0:80::/64
                    ::                                     0 64600 65501 i
*> 20c0:a810::/64   ::                                     0 64600 65502 i
*> 20c0:a810:0:80::/64
                    ::                                     0 64600 65502 i
*> 20c0:a818::/64   ::                                     0 64600 65503 i
*> 20c0:a818:0:80::/64
                    ::                                     0 64600 65503 i
*> 20c0:a820::/64   ::                                     0 64600 65504 i
*> 20c0:a820:0:80::/64
                    ::                                     0 64600 65504 i
*> 20c0:a828::/64   ::                                     0 64600 65505 i
*> 20c0:a828:0:80::/64
                    ::                                     0 64600 65505 i
*> 20c0:a830::/64   ::                                     0 64600 65506 i
*> 20c0:a830:0:80::/64
                    ::                                     0 64600 65506 i
*> 20c0:a838::/64   ::                                     0 64600 65507 i
*> 20c0:a838:0:80::/64
                    ::                                     0 64600 65507 i
*> 20c0:a840::/64   ::                                     0 64600 65508 i
*> 20c0:a840:0:80::/64
                    ::                                     0 64600 65508 i
*> 20c0:a848::/64   ::                                     0 64600 65509 i
*> 20c0:a848:0:80::/64
                    ::                                     0 64600 65509 i
*> 20c0:a850::/64   ::                                     0 64600 65510 i
*> 20c0:a850:0:80::/64
                    ::                                     0 64600 65510 i
*> 20c0:a858::/64   ::                                     0 64600 65511 i
*> 20c0:a858:0:80::/64
                    ::                                     0 64600 65511 i
*> 20c0:a860::/64   ::                                     0 64600 65512 i
*> 20c0:a860:0:80::/64
                    ::                                     0 64600 65512 i
*> 20c0:a868::/64   ::                                     0 64600 65513 i
*> 20c0:a868:0:80::/64
                    ::                                     0 64600 65513 i
"""

bgp_v6_neighbor_output_recv_routes = \
"""
BGP table version is 6407, local router ID is 10.1.0.32, vrf id 0
Default local pref 100, local AS 65100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete

   Network          Next Hop            Metric LocPrf Weight Path
*> ::/0             fc00::72                               0 64600 65534 6666 6667 i
*> 2064:100::1d/128 fc00::72                               0 64600 i
*> 20c0:a808::/64   fc00::72                               0 64600 65501 i
*> 20c0:a808:0:80::/64
                    fc00::72                               0 64600 65501 i
*> 20c0:a810::/64   fc00::72                               0 64600 65502 i
*> 20c0:a810:0:80::/64
                    fc00::72                               0 64600 65502 i
*> 20c0:a818::/64   fc00::72                               0 64600 65503 i
*> 20c0:a818:0:80::/64
                    fc00::72                               0 64600 65503 i
*> 20c0:a820::/64   fc00::72                               0 64600 65504 i
*> 20c0:a820:0:80::/64
                    fc00::72                               0 64600 65504 i
*> 20c0:a828::/64   fc00::72                               0 64600 65505 i
*> 20c0:a828:0:80::/64
                    fc00::72                               0 64600 65505 i
*> 20c0:a830::/64   fc00::72                               0 64600 65506 i
*> 20c0:a830:0:80::/64
                    fc00::72                               0 64600 65506 i
*> 20c0:a838::/64   fc00::72                               0 64600 65507 i
*> 20c0:a838:0:80::/64
                    fc00::72                               0 64600 65507 i
*> 20c0:a840::/64   fc00::72                               0 64600 65508 i
*> 20c0:a840:0:80::/64
                    fc00::72                               0 64600 65508 i
*> 20c0:a848::/64   fc00::72                               0 64600 65509 i
*> 20c0:a848:0:80::/64
                    fc00::72                               0 64600 65509 i
*> 20c0:a850::/64   fc00::72                               0 64600 65510 i
*> 20c0:a850:0:80::/64
                    fc00::72                               0 64600 65510 i
*> 20c0:a858::/64   fc00::72                               0 64600 65511 i
*> 20c0:a858:0:80::/64
                    fc00::72                               0 64600 65511 i
*> 20c0:a860::/64   fc00::72                               0 64600 65512 i
*> 20c0:a860:0:80::/64
                    fc00::72                               0 64600 65512 i
*> 20c0:a868::/64   fc00::72                               0 64600 65513 i
*> 20c0:a868:0:80::/64
                    fc00::72                               0 64600 65513 i
"""

bgp_v6_neighbor_invalid  = \
"""Error:  Bgp neighbor aa00::72 not configured"""

bgp_v6_neighbor_invalid_address = \
"""Error: 20.1.1.1 is not valid ipv6 address"""

bgp_v4_neighbors_output_asic0 = \
"""
BGP neighbor is 10.0.0.1, remote AS 65200, local AS 65100, external link
 Description: ARISTA01T2
 Member of peer-group TIER2_V4 for session parameters
  BGP version 4, remote router ID 100.1.0.1, local router ID 10.1.0.32
  BGP state = Established, up for 04:41:19
  Last read 00:00:19, Last write 00:00:19
  Hold time is 180, keepalive interval is 60 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv4 Unicast: RX advertised IPv4 Unicast and received
    Route refresh: advertised and received(new)
    Address Family IPv4 Unicast: advertised and received
    Hostname Capability: advertised (name: str-n3164-acs-2,domain name: n/a) not received
    Graceful Restart Capabilty: advertised and received
      Remote Restart timer is 300 seconds
      Address families by peer:
        IPv4 Unicast(not preserved)
  Graceful restart information:
    End-of-RIB send: IPv4 Unicast
    End-of-RIB received: IPv4 Unicast
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  2          1
    Notifications:          2          0
    Updates:               43       3187
    Keepalives:           282        283
    Route Refresh:          0          0
    Capability:             0          0
    Total:                329       3471
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv4 Unicast
  TIER2_V4 peer-group member
  Update group 3, subgroup 3
  Packet Queue length 0
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_TIER2_V4
  Route map for outgoing advertisements is *TO_TIER2_V4
  6370 accepted prefixes
  Maximum prefixes allowed 12000 (warning-only)
  Threshold for warning message 90%

  Connections established 1; dropped 0
  Last reset 04:41:43,   No AFI/SAFI activated for peer
Local host: 10.0.0.0, Local port: 179
Foreign host: 10.0.0.1, Foreign port: 56376
Nexthop: 10.0.0.0
Nexthop global: fc00::1
Nexthop local: fe80::2be:75ff:fe3a:ef50
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 120
Read thread: on  Write thread: on  FD used: 25
"""
bgp_v4_neighbors_output_asic1 = \
"""
BGP neighbor is 10.1.0.1, remote AS 65100, local AS 65100, internal link
 Description: ASIC0
Hostname: sonic
 Member of peer-group INTERNAL_PEER_V4 for session parameters
  BGP version 4, remote router ID 10.1.0.32, local router ID 8.0.0.4
  BGP state = Established, up for 04:50:18
  Last read 00:00:03, Last write 00:00:03
  Hold time is 10, keepalive interval is 3 seconds
  Configured hold time is 10, keepalive interval is 3 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv4 Unicast: RX advertised IPv4 Unicast and received
    Route refresh: advertised and received(old & new)
    Address Family IPv4 Unicast: advertised and received
    Hostname Capability: advertised (name: str-n3164-acs-2,domain name: n/a) received (name: str-n3164-acs-2,domain name: n/a)
    Graceful Restart Capabilty: advertised and received
      Remote Restart timer is 240 seconds
      Address families by peer:
        IPv4 Unicast(preserved)
  Graceful restart information:
    End-of-RIB send: IPv4 Unicast
    End-of-RIB received: IPv4 Unicast
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  1          1
    Notifications:          0          0
    Updates:             6390       3194
    Keepalives:          5806       5806
    Route Refresh:          0          0
    Capability:             0          0
    Total:              12197       9001
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv4 Unicast
  INTERNAL_PEER_V4 peer-group member
  Update group 2, subgroup 2
  Packet Queue length 0
  Route-Reflector Client
  Inbound soft reconfiguration allowed
  NEXT_HOP is always this router
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_INTERNAL_PEER_V4
  Route map for outgoing advertisements is *TO_BGP_INTERNAL_PEER_V4
  6377 accepted prefixes

  Connections established 1; dropped 0
  Last reset 04:50:40,   Waiting for NHT
Local host: 10.1.0.0, Local port: 52802
Foreign host: 10.1.0.1, Foreign port: 179
Nexthop: 10.1.0.0
Nexthop global: 2603:10e2:400:1::1
Nexthop local: fe80::42:f0ff:fe7f:104
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 10
Read thread: on  Write thread: on  FD used: 17
"""
bgp_v4_neighbors_output_all_asics = bgp_v4_neighbors_output_asic0 + bgp_v4_neighbors_output_asic1

bgp_v6_neighbor_output_warning =\
"""bgp neighbor 2603:10e2:400:1::2 is present in namespace asic1 not in asic0"""

bgp_v6_neighbors_output_asic0  = \
"""
 BGP neighbor is fc00::2, remote AS 65200, local AS 65100, external link
 Description: ARISTA01T2
 Member of peer-group TIER2_V6 for session parameters
  BGP version 4, remote router ID 100.1.0.1, local router ID 10.1.0.32
  BGP state = Established, up for 13:26:44
  Last read 00:00:45, Last write 00:00:44
  Hold time is 180, keepalive interval is 60 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv6 Unicast: RX advertised IPv6 Unicast and received
    Route refresh: advertised and received(new)
    Address Family IPv6 Unicast: advertised and received
    Hostname Capability: advertised (name: str-n3164-acs-2,domain name: n/a) not received
    Graceful Restart Capabilty: advertised and received
      Remote Restart timer is 300 seconds
      Address families by peer:
        IPv6 Unicast(not preserved)
  Graceful restart information:
    End-of-RIB send: IPv6 Unicast
    End-of-RIB received: IPv6 Unicast
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  2          1
    Notifications:          2          0
    Updates:                5       3187
    Keepalives:           807        808
    Route Refresh:          0          0
    Capability:             0          0
    Total:                816       3996
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv6 Unicast
  TIER2_V6 peer-group member
  Update group 2, subgroup 2
  Packet Queue length 0
  Inbound soft reconfiguration allowed
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_TIER2_V6
  Route map for outgoing advertisements is *TO_TIER2_V6
  6370 accepted prefixes
  Maximum prefixes allowed 8000 (warning-only)
  Threshold for warning message 90%

  Connections established 1; dropped 0
  Last reset 13:27:08,   No AFI/SAFI activated for peer
Local host: fc00::1, Local port: 179
Foreign host: fc00::2, Foreign port: 57838
Nexthop: 10.0.0.0
Nexthop global: fc00::1
Nexthop local: fe80::2be:75ff:fe3a:ef50
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 120
Read thread: on  Write thread: on  FD used: 26
"""

bgp_v6_neighbors_output_asic1 = \
"""
 BGP neighbor is 2603:10e2:400:1::2, remote AS 65100, local AS 65100, internal link
 Description: ASIC0
Hostname: str-n3164-acs-2
 Member of peer-group INTERNAL_PEER_V6 for session parameters
  BGP version 4, remote router ID 10.1.0.32, local router ID 8.0.0.4
  BGP state = Established, up for 13:28:48
  Last read 00:00:02, Last write 00:00:02
  Hold time is 10, keepalive interval is 3 seconds
  Configured hold time is 10, keepalive interval is 3 seconds
  Neighbor capabilities:
    4 Byte AS: advertised and received
    AddPath:
      IPv6 Unicast: RX advertised IPv6 Unicast and received
    Route refresh: advertised and received(old & new)
    Address Family IPv6 Unicast: advertised and received
    Hostname Capability: advertised (name: str-n3164-acs-2,domain name: n/a) received (name: str-n3164-acs-2,domain name: n/a)
    Graceful Restart Capabilty: advertised and received
      Remote Restart timer is 240 seconds
      Address families by peer:
        IPv6 Unicast(preserved)
  Graceful restart information:
    End-of-RIB send: IPv6 Unicast
    End-of-RIB received: IPv6 Unicast
  Message statistics:
    Inq depth is 0
    Outq depth is 0
                         Sent       Rcvd
    Opens:                  1          1
    Notifications:          0          0
    Updates:             6380       4746
    Keepalives:         16176      16176
    Route Refresh:          0          0
    Capability:             0          0
    Total:              22557      20923
  Minimum time between advertisement runs is 0 seconds

 For address family: IPv6 Unicast
  INTERNAL_PEER_V6 peer-group member
  Update group 1, subgroup 1
  Packet Queue length 0
  Route-Reflector Client
  Inbound soft reconfiguration allowed
  NEXT_HOP is always this router
  Community attribute sent to this neighbor(all)
  Inbound path policy configured
  Outbound path policy configured
  Route map for incoming advertisements is *FROM_BGP_INTERNAL_PEER_V6
  Route map for outgoing advertisements is *TO_BGP_INTERNAL_PEER_V6
  6380 accepted prefixes

  Connections established 1; dropped 0
  Last reset 13:29:08,   No AFI/SAFI activated for peer
Local host: 2603:10e2:400:1::1, Local port: 179
Foreign host: 2603:10e2:400:1::2, Foreign port: 58984
Nexthop: 10.1.0.0
Nexthop global: 2603:10e2:400:1::1
Nexthop local: fe80::42:f0ff:fe7f:104
BGP connection: shared network
BGP Connect Retry Timer in Seconds: 10
Read thread: on  Write thread: on  FD used: 22
"""

bgp_v6_neighbors_output_all_asics = bgp_v6_neighbors_output_asic0 +\
     bgp_v6_neighbors_output_asic1


def mock_show_bgp_neighbor_multi_asic(param, namespace):
    if param == 'bgp_v4_neighbors_output_all_asics':
        if namespace == 'asic0':
            return bgp_v4_neighbors_output_asic0
        if namespace == 'asic1':
            return bgp_v4_neighbors_output_asic1
    if param == 'bgp_v6_neighbors_output_all_asics':
        if namespace == 'asic0':
            return bgp_v6_neighbors_output_asic0
        if namespace == 'asic1':
            return bgp_v6_neighbors_output_asic1
    if param == 'bgp_v4_neighbors_output_asic0':
        return bgp_v4_neighbors_output_asic0
    if param == 'bgp_v4_neighbors_output_asic1':
        return bgp_v4_neighbors_output_asic1
    elif param == 'bgp_v6_neighbors_output_all_asics':
        return bgp_v6_neighbors_output_all_asics
    if param == 'bgp_v6_neighbors_output_asic0':
        return bgp_v6_neighbors_output_asic0
    if param == 'bgp_v6_neighbors_output_asic1':
        return bgp_v6_neighbors_output_asic1
    else:
        return ""


def mock_show_bgp_neighbor_single_asic(request):
    if request.param == 'bgp_v4_neighbors_output':
        return bgp_v4_neighbors_output
    elif request.param == 'bgp_v6_neighbors_output':
        return bgp_v6_neighbors_output
    elif request.param == 'bgp_v4_neighbors_output_invalid_vrf':
        return bgp_v4_neighbors_output_invalid_vrf
    elif request.param == 'bgp_v6_neighbors_output_invalid_vrf':
        return bgp_v6_neighbors_output_invalid_vrf
    elif request.param == 'bgp_v4_neighbor_output_adv_routes':
        return bgp_v4_neighbor_output_adv_routes
    elif request.param == 'bgp_v4_neighbor_output_recv_routes':
        return bgp_v4_neighbor_output_recv_routes
    elif request.param == 'bgp_v6_neighbor_output_adv_routes':
        return bgp_v6_neighbor_output_adv_routes
    elif request.param == 'bgp_v6_neighbor_output_recv_routes':
        return bgp_v6_neighbor_output_recv_routes
    else:
        return ""


testData = {
    'bgp_v4_neighbors': {
        'vrf': 'default',
        'args': [],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output
    },
    'bgp_v4_neighbors_vrf': {
        'vrf': 'Vnet_90',
        'args': [],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output
    },
    'bgp_v4_neighbors_invalid_vrf': {
        'vrf': 'Vnet_invalid',
        'args': [],
        'rc': 2,
        'rc_output': bgp_v4_neighbors_output_invalid_vrf
    },
    'bgp_v4_neighbor_ip_address': {
        'vrf': 'default',
        'args': ['10.0.0.57'],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output
    },
    'bgp_v4_neighbor_invalid': {
        'vrf': 'default',
        'args': ['20.1.1.1'],
        'rc': 2,
        'rc_err_msg': bgp_v4_neighbor_invalid
    },
    'bgp_v4_neighbor_invalid_address': {
        'vrf': 'default',
        'args': ['invalid_address'],
        'rc': 2,
        'rc_err_msg': bgp_v4_neighbor_invalid_address
    },
    'bgp_v4_neighbor_adv_routes': {
        'vrf': 'default',
        'args': ["10.0.0.57", "advertised-routes"],
        'rc': 0,
        'rc_output': bgp_v4_neighbor_output_adv_routes
    },
    'bgp_v4_neighbor_recv_routes': {
        'vrf': 'default',
        'args': ["10.0.0.57", "received-routes"],
        'rc': 0,
        'rc_output': bgp_v4_neighbor_output_recv_routes
    },
    'bgp_v6_neighbors': {
        'vrf': 'default',
        'args': [],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output
    },
    'bgp_v6_neighbors_vrf': {
        'vrf': 'Vnet_90',
        'args': [],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output
    },
    'bgp_v6_neighbors_invalid_vrf': {
        'vrf': 'Vnet_invalid',
        'args': [],
        'rc': 2,
        'rc_output': bgp_v6_neighbors_output_invalid_vrf
    },
    'bgp_v6_neighbor_ip_address': {
        'vrf': 'default',
        'args': ['fc00::72'],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output
    },
    'bgp_v6_neighbor_invalid': {
        'vrf': 'default',
        'args': ['aa00::72'],
        'rc': 2,
        'rc_err_msg': bgp_v6_neighbor_invalid
    },
    'bgp_v6_neighbor_invalid_address': {
        'vrf': 'default',
        'args': ['20.1.1.1'],
        'rc': 2,
        'rc_err_msg': bgp_v6_neighbor_invalid_address
    },
    'bgp_v6_neighbor_adv_routes': {
        'vrf': 'default',
        'args': ["fc00::72", "advertised-routes"],
        'rc': 0,
        'rc_output': bgp_v6_neighbor_output_adv_routes
    },
    'bgp_v6_neighbor_recv_routes': {
        'vrf': 'default',
        'args': ["fc00::72", "received-routes"],
        'rc': 0,
        'rc_output': bgp_v6_neighbor_output_recv_routes
    },
    'bgp_v4_neighbors_multi_asic' : {
        'vrf': 'default',
        'args': [],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output_all_asics
    },
    'bgp_v4_neighbors_asic' : {
        'vrf': 'default',
        'args': ['-nasic1'],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output_asic1
    },
    'bgp_v4_neighbors_external' : {
        'vrf': 'default',
        'args': ['10.0.0.1'],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output_asic0
    },
    'bgp_v4_neighbors_internal' : {
        'vrf': 'default',
        'args': ['10.1.0.1'],
        'rc': 0,
        'rc_output': bgp_v4_neighbors_output_asic1
    },
    'bgp_v6_neighbors_multi_asic' : {
        'vrf': 'default',
        'args': [],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output_all_asics
    },
    'bgp_v6_neighbors_asic' : {
        'vrf': 'default',
        'args': ['-nasic0'],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output_asic0
    },
    'bgp_v6_neighbors_external' : {
        'vrf': 'default',
        'args': ['fc00::2'],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output_asic0
    },
    'bgp_v6_neighbors_internal' : {
        'vrf': 'default',
        'args': ['2603:10e2:400:1::2'],
        'rc': 0,
        'rc_output': bgp_v6_neighbors_output_asic1
    },
    'bgp_v6_neighbor_warning' : {
        'vrf': 'default',
        'args': ['2603:10e2:400:1::2', '-nasic0'],
        'rc': 0,
        'rc_warning_msg': bgp_v6_neighbor_output_warning
    },

}