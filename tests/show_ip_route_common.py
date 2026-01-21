#
# NON-MULTI_ASIC TEST SECTION
#

show_ip_route_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 1d11h20m
B>*0.0.0.0/0 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                 via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 1d11h20m
C>*8.0.0.0/32 is directly connected, Loopback4096, 1d11h21m
C>*10.0.0.0/31 is directly connected, PortChannel0002, 1d11h20m
C>*10.0.0.4/31 is directly connected, PortChannel0005, 1d11h20m
C>*10.1.0.32/32 is directly connected, Loopback0, 1d11h21m
B>*100.1.0.3/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.0/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                      via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.1/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                      via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.16/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.17/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.32/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.33/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.48/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.49/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.64/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.65/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.80/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.81/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.96/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.97/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.112/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.113/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.128/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.129/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.144/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.145/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.160/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.161/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.176/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.177/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.192/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.193/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.208/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.209/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.224/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.225/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.240/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
B>*192.168.0.241/32 [20/0] via 10.0.0.1, PortChannel0002, weight 1, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, weight 1, 1d11h20m
"""

show_specific_ip_route_expected_output = """\
Routing entry for 192.168.0.1/32
  Known via "bgp", distance 20, metric 0, best
  Last update 1d11h20m ago
  * 10.0.0.1, via PortChannel0002, weight 1
  * 10.0.0.5, via PortChannel0005, weight 1

"""

show_specific_recursive_route_expected_output = """\
Routing entry for 193.11.208.0/25
  Known via "bgp", distance 20, metric 0, best
  Last update 00:14:32 ago
  * 10.0.0.1, via PortChannel0002, weight 1
  * 10.0.0.5, via PortChannel0005, weight 1
  * 10.0.0.9 (recursive), weight 1
  * 10.0.0.1 (recursive), weight 1

"""

show_special_ip_route_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

C>*10.3.0.4/31 (blackhole)(vrf 2, PortChannel1014, inactive (recursive) 2d22h02m
C>*10.5.0.4/31 (ICMP unreachable) inactive 2d22h02m
C>*10.5.0.8/31 (ICMP admin-prohibited) inactive onlink, src 10.2.3.4 2d22h02m
C> 10.6.0.8/31 inactive 2d22h02m
C>q10.6.5.0/31 inactive 2d22h02m
C>r10.6.5.3/31 inactive 2d22h02m
C>*10.7.0.8/31 (ICMP admin-prohibited) inactive onlink, src 10.2.3.4, label IPv4 Explicit Null/OAM Alert/Extension/1212 2d22h02m
"""


show_ipv6_route_err_expected_output = """\
% Unknown command: show ipv6 route garbage
"""

show_ipv6_route_single_json_expected_output = """\
{
    "20c0:a8c7:0:81::/64": [
        {
            "destSelected": true,
            "distance": 20,
            "installed": true,
            "internalFlags": 8,
            "internalNextHopActiveNum": 2,
            "internalNextHopNum": 2,
            "internalStatus": 16,
            "metric": 0,
            "nexthops": [
                {
                    "active": true,
                    "afi": "ipv6",
                    "fib": true,
                    "flags": 3,
                    "interfaceIndex": 928,
                    "interfaceName": "PortChannel0011",
                    "ip": "fc00::e",
                    "weight": "1"
                },
                {
                    "active": true,
                    "afi": "ipv6",
                    "fib": true,
                    "flags": 3,
                    "interfaceIndex": 927,
                    "interfaceName": "PortChannel0008",
                    "ip": "fc00::a",
                    "weight": "1"
                }
            ],
            "prefix": "20c0:a8c7:0:81::/64",
            "protocol": "bgp",
            "selected": true,
            "table": 254,
            "uptime": "2d13h40m"
        }
    ]
}
"""

show_ipv6_route_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

B>*::/0 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *            via fc00::6, PortChannel0005, weight 1, 1d11h34m
K *::/0 [210/0] via fd00::1, eth0, 1d11h34m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                      via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                          via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:10::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:11::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:30::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:31::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:40::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:41::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:50::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:51::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:60::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:61::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:70::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:71::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:80::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:81::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:90::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:91::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:a0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:a1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:b0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:b1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:c0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:c1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:d0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:d1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:e0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:e1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:f0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:f1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                      via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                          via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:10::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:11::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:20::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:21::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:30::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:31::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:40::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:41::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:50::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:51::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:60::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:61::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:70::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:71::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:80::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:81::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:90::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:91::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:a0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:a1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:b0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:b1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:c0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:c1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:d0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:d1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:e0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:e1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:f0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:f1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
C>*2603:10e2:400::/128 is directly connected, Loopback4096, 1d11h34m
C>*fc00::/126 is directly connected, PortChannel0002, 1d11h34m
C>*fc00::4/126 is directly connected, PortChannel0005, 1d11h34m
C>*fc00:1::32/128 is directly connected, Loopback0, 1d11h34m
C>*fd00::/80 is directly connected, eth0, 1d11h34m
C *fe80::/64 is directly connected, PortChannel0002, 1d11h34m
C *fe80::/64 is directly connected, PortChannel0005, 1d11h34m
C *fe80::/64 is directly connected, Ethernet20, 1d11h34m
C *fe80::/64 is directly connected, Ethernet16, 1d11h34m
C *fe80::/64 is directly connected, Ethernet4, 1d11h34m
C *fe80::/64 is directly connected, Ethernet0, 1d11h34m
C *fe80::/64 is directly connected, Loopback4096, 1d11h34m
C *fe80::/64 is directly connected, Loopback0, 1d11h34m
C>*fe80::/64 is directly connected, eth0, 1d11h34m
"""

show_ipv6_route_alias_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

B>*::/0 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *            via fc00::6, PortChannel0005, weight 1, 1d11h34m
K *::/0 [210/0] via fd00::1, eth0, 1d11h34m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                      via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                          via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:10::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:11::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:30::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:31::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:40::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:41::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:50::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:51::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:60::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:61::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:70::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:71::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:80::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:81::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:90::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:91::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:a0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:a1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:b0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:b1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:c0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:c1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:d0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:d1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:e0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:e1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:f0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a800:0:f1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                      via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                          via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:10::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:11::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:20::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:21::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:30::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:31::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:40::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:41::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:50::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:51::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:60::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:61::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:70::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:71::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:80::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:81::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:90::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:91::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:a0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:a1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:b0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:b1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:c0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:c1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:d0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:d1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:e0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:e1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:f0::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
B>*20c0:a801:0:f1::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 1d11h34m
  *                           via fc00::6, PortChannel0005, weight 1, 1d11h34m
C>*2603:10e2:400::/128 is directly connected, Loopback4096, 1d11h34m
C>*fc00::/126 is directly connected, PortChannel0002, 1d11h34m
C>*fc00::4/126 is directly connected, PortChannel0005, 1d11h34m
C>*fc00:1::32/128 is directly connected, Loopback0, 1d11h34m
C>*fd00::/80 is directly connected, eth0, 1d11h34m
C *fe80::/64 is directly connected, PortChannel0002, 1d11h34m
C *fe80::/64 is directly connected, PortChannel0005, 1d11h34m
C *fe80::/64 is directly connected, etp6, 1d11h34m
C *fe80::/64 is directly connected, etp5, 1d11h34m
C *fe80::/64 is directly connected, etp2, 1d11h34m
C *fe80::/64 is directly connected, etp1, 1d11h34m
C *fe80::/64 is directly connected, Loopback4096, 1d11h34m
C *fe80::/64 is directly connected, Loopback0, 1d11h34m
C>*fe80::/64 is directly connected, eth0, 1d11h34m
"""

#
# MULTI ASIC TEST SECTION
#
show_ip_route_multi_asic_display_all_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

asic0:
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h00m
B>*0.0.0.0/0 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                 via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h00m
C>*8.0.0.0/32 is directly connected, Loopback4096, 2d22h00m
C>*10.0.0.0/31 is directly connected, PortChannel4001, 2d22h00m
C>*10.0.0.4/31 is directly connected, PortChannel0005, 2d22h00m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h00m
B>*100.1.0.3/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
B>*192.168.0.0/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.1/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.32/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.96/32 [20/0] via 10.0.0.5, Ethernet-BP4, weight 1, 2d22h00m
  *                       via 10.0.0.1, Ethernet-BP0, weight 1, 2d22h00m
B>*192.168.0.97/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.192/32 [20/0] via 10.0.0.5, Ethernet-BP4, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel4001, weight 1, 2d22h00m
B>*192.168.0.193/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.208/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.209/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.224/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.225/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.240/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
B>*192.168.0.241/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
asic1:
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h01m
B>*0.0.0.0/0 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                 via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h01m
C>*8.0.0.1/32 is directly connected, Loopback4096, 2d22h01m
C>*10.0.0.0/31 is directly connected, PortChannel4009, 2d22h01m
C>*10.0.0.4/31 is directly connected, PortChannel0008, 2d22h01m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h01m
B>*100.1.0.3/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
B>*192.168.0.0/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                      via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.1/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                      via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.32/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                       via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.96/32 [20/0] via 10.0.0.8, Ethernet-BP260, weight 1, 2d22h01m
  *                       via 10.0.0.7, Ethernet-BP256, weight 1, 2d22h01m
B>*192.168.0.97/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                       via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.192/32 [20/0] via 10.0.0.8, Ethernet-BP260, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel4009, weight 1, 2d22h01m
B>*192.168.0.193/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.208/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.209/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.224/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.225/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
B>*192.168.0.240/32 [20/0] via 10.0.0.8, Ethernet-BP260, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel4009, weight 1, 2d22h01m
B>*192.168.0.241/32 [20/0] via 10.0.0.8, PortChannel0008, weight 1, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, weight 1, 2d22h01m
asic2:
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h02m
B>*0.0.0.0/0 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                 via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h02m
C>*8.0.0.2/32 is directly connected, Loopback4096, 2d22h02m
C>*10.0.0.0/31 is directly connected, PortChannel4001, 2d22h02m
C>*10.0.0.4/31 is directly connected, PortChannel1016, 2d22h02m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h02m
B>*100.1.0.3/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
B>*192.168.0.0/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                      via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.1/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                      via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.32/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                       via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.96/32 [20/0] via 10.0.0.16, Ethernet-BP24, weight 1, 2d22h02m
  *                       via 10.0.0.15, Ethernet-BP20, weight 1, 2d22h02m
B>*192.168.0.97/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                       via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.192/32 [20/0] via 10.0.0.16, Ethernet-BP24, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel4001, weight 1, 2d22h02m
B>*192.168.0.193/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.208/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.209/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.224/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.225/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.240/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
B>*192.168.0.241/32 [20/0] via 10.0.0.16, PortChannel1016, weight 1, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h02m
"""

show_ip_route_multi_asic_display_all_front_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h00m
B>*0.0.0.0/0 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                 via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                 via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                 via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h00m
C>*8.0.0.0/32 is directly connected, Loopback4096, 2d22h00m
C>*8.0.0.2/32 is directly connected, Loopback4096, 2d22h02m
C>*10.0.0.4/31 is directly connected, PortChannel0005, 2d22h00m
C>*10.0.0.4/31 is directly connected, PortChannel1016, 2d22h02m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h00m
B>*100.1.0.3/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                    via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.0/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                      via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                      via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.1/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                      via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                      via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.32/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                       via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                       via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.97/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                       via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                       via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.193/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.208/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.209/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.224/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.225/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.240/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
B>*192.168.0.241/32 [20/0] via 10.0.0.5, PortChannel0005, weight 1, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, weight 1, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, weight 1, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, weight 1, 2d22h00m
"""

show_ipv6_route_multi_asic_all_namesapce_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *::/0 [210/0] via fd00::1, eth0, 2d22h00m
B>*::/0 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *            via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *            via fc00::2, PortChannel1015, weight 1, 2d22h00m
  *            via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                       via fc00::2, PortChannel1015, weight 1, 2d22h00m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *                       via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*20c0:a800:0:1::/64 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *                          via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                          via fc00::2, PortChannel1015, weight 1, 2d22h00m
  *                          via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*20c0:a800:0:10::/64 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h00m
  *                           via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*20c0:a800:0:11::/64 [20/0] via fc00::6, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::6, PortChannel1015, weight 1, 2d22h00m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h00m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h00m
C>*2603:10e2:400::/128 is directly connected, Loopback4096, 2d22h00m
C>*2603:10e2:400::2/128 is directly connected, Loopback4096, 2d22h02m
C>*fc00::4/126 is directly connected, PortChannel0005, 2d22h00m
C>*fc00::4/126 is directly connected, PortChannel1016, 2d22h02m
C>*fc00:1::32/128 is directly connected, Loopback0, 2d22h00m
C>*fd00::/80 is directly connected, eth0, 2d22h00m
C>*fe80::/64 is directly connected, eth0, 2d22h00m
C *fe80::/64 is directly connected, Loopback0, 2d22h00m
C *fe80::/64 is directly connected, Loopback4096, 2d22h00m
C *fe80::/64 is directly connected, Ethernet16, 2d22h00m
C *fe80::/64 is directly connected, Ethernet20, 2d22h00m
C *fe80::/64 is directly connected, PortChannel0005, 2d22h00m
C *fe80::/64 is directly connected, PortChannel1016, 2d22h02m
C *fe80::/64 is directly connected, Ethernet24, 2d22h02m
"""

show_ipv6_route_multi_asic_all_namesapce_alias_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *::/0 [210/0] via fd00::1, eth0, 2d22h00m
B>*::/0 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *            via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *            via fc00::2, PortChannel1015, weight 1, 2d22h00m
  *            via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                       via fc00::2, PortChannel1015, weight 1, 2d22h00m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *                       via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*20c0:a800:0:1::/64 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *                          via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                          via fc00::2, PortChannel1015, weight 1, 2d22h00m
  *                          via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*20c0:a800:0:10::/64 [20/0] via fc00::6, PortChannel0005, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h00m
  *                           via fc00::6, PortChannel1016, weight 1, 2d22h00m
B>*20c0:a800:0:11::/64 [20/0] via fc00::6, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::6, PortChannel1015, weight 1, 2d22h00m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h00m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel0002, weight 1, 2d22h00m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h00m
C>*2603:10e2:400::/128 is directly connected, Loopback4096, 2d22h00m
C>*2603:10e2:400::2/128 is directly connected, Loopback4096, 2d22h02m
C>*fc00::4/126 is directly connected, PortChannel0005, 2d22h00m
C>*fc00::4/126 is directly connected, PortChannel1016, 2d22h02m
C>*fc00:1::32/128 is directly connected, Loopback0, 2d22h00m
C>*fd00::/80 is directly connected, eth0, 2d22h00m
C>*fe80::/64 is directly connected, eth0, 2d22h00m
C *fe80::/64 is directly connected, Loopback0, 2d22h00m
C *fe80::/64 is directly connected, Loopback4096, 2d22h00m
C *fe80::/64 is directly connected, Ethernet1/5, 2d22h00m
C *fe80::/64 is directly connected, Ethernet1/6, 2d22h00m
C *fe80::/64 is directly connected, PortChannel0005, 2d22h00m
C *fe80::/64 is directly connected, PortChannel1016, 2d22h02m
C *fe80::/64 is directly connected, Ethernet1/7, 2d22h02m
"""

show_ipv6_route_multi_asic_single_namesapce_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *::/0 [210/0] via fd00::1, eth0, 2d22h02m
B>*::/0 [20/0] via fc00::6, PortChannel1016, weight 1, 2d22h02m
  *            via fc00::2, PortChannel1015, weight 1, 2d22h02m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel1015, weight 1, 2d22h02m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel1016, weight 1, 2d22h02m
B>*20c0:a800:0:1::/64 [20/0] via fc00::6, PortChannel1016, weight 1, 2d22h02m
  *                          via fc00::2, PortChannel1015, weight 1, 2d22h02m
B>*20c0:a800:0:10::/64 [20/0] via fc00::6, PortChannel1016, weight 1, 2d22h02m
  *                           via fc00::2, PortChannel1015, weight 1, 2d22h02m
B>*20c0:a800:0:11::/64 [20/0] via fc00::6, PortChannel1015, weight 1, 2d22h02m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel1015, weight 1, 2d22h02m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel1015, weight 1, 2d22h02m
C>*2603:10e2:400::2/128 is directly connected, Loopback4096, 2d22h02m
C>*fc00::4/126 is directly connected, PortChannel1016, 2d22h02m
C>*fc00:1::32/128 is directly connected, Loopback0, 2d22h02m
C>*fd00::/80 is directly connected, eth0, 2d22h02m
C>*fe80::/64 is directly connected, eth0, 2d22h02m
C *fe80::/64 is directly connected, Loopback0, 2d22h02m
C *fe80::/64 is directly connected, Loopback4096, 2d22h02m
C *fe80::/64 is directly connected, Ethernet24, 2d22h02m
C *fe80::/64 is directly connected, Ethernet20, 2d22h02m
C *fe80::/64 is directly connected, PortChannel1016, 2d22h02m
"""

show_ip_route_multi_asic_invalid_namesapce_err_output = """\
namespace 'asic7' is not valid. valid name spaces are:
['asic0', 'asic1', 'asic2']
"""

show_ip_route_multi_asic_invalid_display_err_output = """\
dislay option 'everything' is not a valid option.
"""

show_ip_route_multi_asic_specific_route_output = """\
Routing entry for 10.0.0.4/31
  Known via "connected", distance 0, metric 0, best
  Last update 2d22h00m ago
  * directly connected, PortChannel0005


Routing entry for 10.0.0.4/31
  Known via "connected", distance 0, metric 0, best
  Last update 2d22h02m ago
  * directly connected, PortChannel1016


"""

show_ipv6_route_multi_asic_specific_route_output = """\
Routing entry for 2603:10e2:400::/128
  Known via "connected", distance 0, metric 0, best
  Last update 2d22h00m ago
  * directly connected, Loopback4096


"""

show_ipv6_route_multi_asic_json_output = """\
{
    "2603:10e2:400::/128": [
        {
            "destSelected": true,
            "distance": 0,
            "installed": true,
            "internalFlags": 8,
            "internalNextHopActiveNum": 1,
            "internalNextHopNum": 1,
            "internalStatus": 16,
            "metric": 0,
            "nexthops": [
                {
                    "active": true,
                    "directlyConnected": true,
                    "fib": true,
                    "flags": 3,
                    "interfaceIndex": 726,
                    "interfaceName": "Loopback4096"
                }
            ],
            "prefix": "2603:10e2:400::/128",
            "protocol": "connected",
            "selected": true,
            "table": 254,
            "uptime": "2d22h00m"
        }
    ]
}
"""

show_ip_route_summary_expected_output = """\
asic0:
Route Source         Routes               FIB  (vrf default)
kernel               1                    1
connected            6                    6
static               1                    0
ebgp                 6371                 6371
ibgp                 88                   88
------
Totals               6467                 6466

asic2:
Route Source         Routes               FIB  (vrf default)
kernel               1                    1
connected            14                   14
static               1                    0
ebgp                 42                   42
ibgp                 6409                 6409
------
Totals               6467                 6466

"""

SHOW_IP_ROUTE_REMOTE_LC = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

B> 0.0.0.0/0 [200/0]   via 20.1.24.128, recursive via iBGP 04w0d12h
                       via 20.1.16.128, recursive via iBGP 04w0d12h
                       via 20.1.8.128, recursive via iBGP 04w0d12h
                       via 20.1.0.128, recursive via iBGP 04w0d12h
"""

SHOW_IP_ROUTE_LC = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

B>*0.0.0.0/0 [20/0] via 20.1.24.128, PortChannel13, 04w0d11h
  *                 via 20.1.16.128, PortChannel9, 04w0d11h
  *                 via 20.1.8.128, PortChannel5, 04w0d11h
  *                 via 20.1.0.128, PortChannel1, 04w0d11h
"""

SHOW_IP_ROUTE_REMOTE_LC_DEFAULT_ROUTE = """\
Routing entry for 0.0.0.0/0
  Known via "bgp", distance 200, metric 0, best
  Last update 04w0d12h ago
    * 20.1.24.128 recursive via iBGP
    * 20.1.16.128 recursive via iBGP
    * 20.1.8.128 recursive via iBGP
    * 20.1.0.128 recursive via iBGP

"""

SHOW_IP_ROUTE_LC_DEFAULT_ROUTE = """\
Routing entry for 0.0.0.0/0
  Known via "bgp", distance 20, metric 0, best
  Last update 04w0d11h ago
  * 20.1.24.128, via PortChannel13
  * 20.1.16.128, via PortChannel9
  * 20.1.8.128, via PortChannel5
  * 20.1.0.128, via PortChannel1

"""

SHOW_IP_ROUTE_LC_DEFAULT_ROUTE_2 = """\
Routing entry for 0.0.0.0/0
  Known via "bgp", distance 20, metric 0, best
  Last update 01:01:51 ago
  * 10.0.0.7, via PortChannel106
  * 10.0.0.1, via PortChannel102

"""
