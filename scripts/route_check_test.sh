#!/usr/bin/env bash

# add a route, interface & route-entry to simulate error
#
sonic-db-cli APPL_DB hmset "ROUTE_TABLE:20c0:d9b8:99:80::/64" "nexthop" "fc00::72,fc00::76,fc00::7a,fc00::7e" "ifname" "PortChannel01,PortChannel02,PortChannel03,PortChannel04" > /dev/null
sonic-db-cli ASIC_DB hmset "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"192.193.120.255/25\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000022\"}" "SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID" "oid:0x5000000000614" > /dev/null
sonic-db-cli APPL_DB hmset  "INTF_TABLE:PortChannel01:10.0.0.99/31" "scope" "global" "family" "IPv4" > /dev/null

echo "------"
echo "expect errors!"
echo "Running Route Check..."
./route_check.py
echo "return value: $?"

sonic-db-cli APPL_DB del "ROUTE_TABLE:20c0:d9b8:99:80::/64" > /dev/null
sonic-db-cli ASIC_DB del "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"192.193.120.255/25\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000022\"}" > /dev/null
sonic-db-cli APPL_DB del "INTF_TABLE:PortChannel01:10.0.0.99/31" > /dev/null

# add standalone tunnel route to simulate unreachable neighbor scenario on dual ToR
# in this scenario, we expect the route mismatch to be ignored
sonic-db-cli APPL_DB hmset "NEIGH_TABLE:Vlan1000:fc02:1000::99" "neigh" "00:00:00:00:00:00" "family" "IPv6" > /dev/null
sonic-db-cli ASIC_DB hmset 'ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{"dest":"fc02:1000::99/128","switch_id":"oid:0x21000000000000","vr":"oid:0x300000000007c"}' "SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID" "oid:0x400000000167d" "SAI_ROUTE_ENTRY_ATTR_PACKET_ACTION" "SAI_PACKET_ACTION_FORWARD" > /dev/null

echo "------"
echo "expect success on dualtor, expect error on all other devices!"
echo "Running Route Check..."
./route_check.py
echo "return value: $?"

sonic-db-cli APPL_DB del "NEIGH_TABLE:Vlan1000:fc02:1000::99" > /dev/null
sonic-db-cli ASIC_DB del 'ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{"dest":"fc02:1000::99/128","switch_id":"oid:0x21000000000000","vr":"oid:0x300000000007c"}' > /dev/null

echo "------"
echo "expect success!"
echo "Running Route Check..."
./route_check.py
echo "return value: $?"
