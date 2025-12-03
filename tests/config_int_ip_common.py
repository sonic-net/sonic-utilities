show_ip_route_with_static_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup

VRF Vrf11:
S>* 20.0.0.1/32 [1/0] is directly connected, Ethernet2, weight 1, 00:40:18

VRF default:
S>* 0.0.0.0/0 [200/0] via 192.168.111.3, eth0, weight 1, 19:51:57
S>* 20.0.0.1/32 [1/0] is directly connected, Ethernet4 (vrf Vrf11), weight 1, 00:38:52
S>* 20.0.0.4/32 [1/0] is directly connected, PortChannel2, weight 1, 00:38:52
S>* 20.0.0.8/32 [1/0] is directly connected, Vlan2, weight 1, 00:38:52
"""

show_ipv6_route_with_static_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIPng,
       O - OSPFv3, I - IS-IS, B - BGP, N - NHRP, T - Table,
       v - VNC, V - VNC-Direct, A - Babel, D - SHARP, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup

VRF Vrf11:
S>* fe80::/24 [1/0] is directly connected, Vlan4, weight 1, 00:00:04

VRF default:
S>* 20c0:a800:0:21::/64 [20/0] is directly connected, PortChannel4, 2d22h02m
S>* fe80::/32 [1/0] is directly connected, Ethernet8 (vrf Vrf11), weight 1, 00:00:04
"""