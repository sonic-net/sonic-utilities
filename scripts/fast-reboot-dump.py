#!/usr/bin/env python3

from swsscommon.swsscommon import SonicV2Connector
import json
import socket
import struct
import sys
import os
from fcntl import ioctl
import binascii
import argparse
import syslog
import traceback
import ipaddress
from builtins import str #for unicode conversion in python2


ARP_CHUNK = binascii.unhexlify('08060001080006040001') # defines a part of the packet for ARP Request
ARP_PAD = binascii.unhexlify('00' * 18)

def generate_neighbor_entries(filename, all_available_macs):
    db = SonicV2Connector(use_unix_socket_path=False)
    db.connect(db.APPL_DB, False)   # Make one attempt only

    arp_output = []
    neighbor_entries = []
    keys = db.keys(db.APPL_DB, 'NEIGH_TABLE:*')
    keys = [] if keys is None else keys
    for key in keys:
        vlan_name = key.split(':')[1]
        entry = db.get_all(db.APPL_DB, key)
        mac = entry['neigh'].lower()
        if (vlan_name, mac) not in all_available_macs:
            # FIXME: print me to log
            continue
        obj = {
          key: entry,
          'OP': 'SET'
        }
        arp_output.append(obj)

        ip_addr = key.split(':', 2)[2]
        neighbor_entries.append((vlan_name, mac, ip_addr))
        syslog.syslog(syslog.LOG_INFO, "Neighbor entry: [Vlan: %s, Mac: %s, Ip: %s]" % (vlan_name, mac, ip_addr))

    db.close(db.APPL_DB)

    with open(filename, 'w') as fp:
        json.dump(arp_output, fp, indent=2, separators=(',', ': '))

    return neighbor_entries

def is_mac_unicast(mac):
    first_octet = mac.split(':')[0]
    return int(first_octet, 16) & 0x01 == 0

def get_vlan_ifaces():
    vlans = []
    with open('/proc/net/dev') as fp:
        vlans = [line.split(':')[0].strip() for line in fp if 'Vlan' in line]

    return vlans

def get_bridge_port_id_2_port_id(db):
    bridge_port_id_2_port_id = {}
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = db.get_all(db.ASIC_DB, key)
        port_type = value['SAI_BRIDGE_PORT_ATTR_TYPE']
        if port_type != 'SAI_BRIDGE_PORT_TYPE_PORT':
            continue
        port_id = value['SAI_BRIDGE_PORT_ATTR_PORT_ID']
        # ignore admin status
        bridge_id = key.replace('ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:', '')
        bridge_port_id_2_port_id[bridge_id] = port_id

    return bridge_port_id_2_port_id

def get_lag_by_member(member_name, app_db):
    keys = app_db.keys(app_db.APPL_DB, 'LAG_MEMBER_TABLE:*')
    keys = [] if keys is None else keys
    for key in keys:
        _, lag_name, lag_member_name = key.split(":")
        if lag_member_name == member_name:
            return lag_name
    return None

def get_map_host_port_id_2_iface_name(asic_db):
    host_port_id_2_iface = {}
    keys = asic_db.keys(asic_db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = asic_db.get_all(asic_db.ASIC_DB, key)
        if value['SAI_HOSTIF_ATTR_TYPE'] != 'SAI_HOSTIF_TYPE_NETDEV':
            continue
        port_id = value['SAI_HOSTIF_ATTR_OBJ_ID']
        iface_name = value['SAI_HOSTIF_ATTR_NAME']
        host_port_id_2_iface[port_id] = iface_name
    
    return host_port_id_2_iface

def get_map_lag_port_id_2_portchannel_name(asic_db, app_db, host_port_id_2_iface):
    lag_port_id_2_iface = {}
    keys = asic_db.keys(asic_db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = asic_db.get_all(asic_db.ASIC_DB, key)
        lag_id = value['SAI_LAG_MEMBER_ATTR_LAG_ID']
        if lag_id in lag_port_id_2_iface:
            continue
        member_id = value['SAI_LAG_MEMBER_ATTR_PORT_ID']
        member_name = host_port_id_2_iface[member_id]
        lag_name = get_lag_by_member(member_name, app_db)
        if lag_name is not None:
            lag_port_id_2_iface[lag_id] = lag_name

    return lag_port_id_2_iface

def get_map_port_id_2_iface_name(asic_db, app_db):
    port_id_2_iface = {}
    host_port_id_2_iface = get_map_host_port_id_2_iface_name(asic_db)
    port_id_2_iface.update(host_port_id_2_iface)
    lag_port_id_2_iface = get_map_lag_port_id_2_portchannel_name(asic_db, app_db, host_port_id_2_iface)
    port_id_2_iface.update(lag_port_id_2_iface)

    return port_id_2_iface

def get_map_bridge_port_id_2_iface_name(asic_db, app_db):
    bridge_port_id_2_port_id = get_bridge_port_id_2_port_id(asic_db)
    port_id_2_iface = get_map_port_id_2_iface_name(asic_db, app_db)

    bridge_port_id_2_iface_name = {}

    for bridge_port_id, port_id in bridge_port_id_2_port_id.items():
        if port_id in port_id_2_iface:
            bridge_port_id_2_iface_name[bridge_port_id] = port_id_2_iface[port_id]
        else:
            print("Not found")

    return bridge_port_id_2_iface_name

def get_vlan_oid_by_vlan_id(db, vlan_id):
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_VLAN:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = db.get_all(db.ASIC_DB, key)
        if 'SAI_VLAN_ATTR_VLAN_ID' in value and int(value['SAI_VLAN_ATTR_VLAN_ID']) == vlan_id:
            return key.replace('ASIC_STATE:SAI_OBJECT_TYPE_VLAN:', '')

    raise Exception('Not found bvi oid for vlan_id: %d' % vlan_id)

def get_fdb(db, vlan_name, vlan_id, bridge_id_2_iface):
    fdb_types = {
      'SAI_FDB_ENTRY_TYPE_DYNAMIC': 'dynamic',
      'SAI_FDB_ENTRY_TYPE_STATIC' : 'static'
    }

    bvid = get_vlan_oid_by_vlan_id(db, vlan_id)
    available_macs = set()
    map_mac_ip = {}
    fdb_entries = []
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{*\"bvid\":\"%s\"*}' % bvid)
    keys = [] if keys is None else keys
    for key in keys:
        key_obj = json.loads(key.replace('ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:', ''))
        mac = str(key_obj['mac'])
        if not is_mac_unicast(mac):
            continue
        available_macs.add((vlan_name, mac.lower()))
        fdb_mac = mac.replace(':', '-')
        # get attributes
        value = db.get_all(db.ASIC_DB, key)
        fdb_type = fdb_types[value['SAI_FDB_ENTRY_ATTR_TYPE']]
        if value['SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID'] not in bridge_id_2_iface:
            continue
        fdb_port = bridge_id_2_iface[value['SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID']]

        obj = {
          'FDB_TABLE:Vlan%d:%s' % (vlan_id, fdb_mac) : {
            'type': fdb_type,
            'port': fdb_port,
          },
          'OP': 'SET'
        }

        fdb_entries.append(obj)
        map_mac_ip[mac.lower()] = fdb_port

    return fdb_entries, available_macs, map_mac_ip

def generate_fdb_entries(filename):
    asic_db = SonicV2Connector(use_unix_socket_path=False)
    app_db = SonicV2Connector(use_unix_socket_path=False)
    asic_db.connect(asic_db.ASIC_DB, False)   # Make one attempt only
    app_db.connect(app_db.APPL_DB, False)   # Make one attempt only

    vlan_ifaces = get_vlan_ifaces()

    fdb_entries, all_available_macs, map_mac_ip_per_vlan = generate_fdb_entries_logic(asic_db, app_db, vlan_ifaces)

    asic_db.close(asic_db.ASIC_DB)
    app_db.close(app_db.APPL_DB)

    with open(filename, 'w') as fp:
        json.dump(fdb_entries, fp, indent=2, separators=(',', ': '))

    return all_available_macs, map_mac_ip_per_vlan

def generate_fdb_entries_logic(asic_db, app_db, vlan_ifaces):
    fdb_entries = []
    all_available_macs = set()
    map_mac_ip_per_vlan = {}

    bridge_id_2_iface = get_map_bridge_port_id_2_iface_name(asic_db, app_db)

    for vlan in vlan_ifaces:
        vlan_id = int(vlan.replace('Vlan', ''))
        fdb_entry, available_macs, map_mac_ip_per_vlan[vlan] = get_fdb(asic_db, vlan, vlan_id, bridge_id_2_iface)
        all_available_macs |= available_macs
        fdb_entries.extend(fdb_entry)

    return fdb_entries, all_available_macs, map_mac_ip_per_vlan

def get_if(iff, cmd):
    s = socket.socket()
    ifreq = ioctl(s, cmd, struct.pack("16s16x",bytes(iff.encode())))
    s.close()
    return ifreq

def get_iface_mac_addr(iff):
    SIOCGIFHWADDR = 0x8927          # Get hardware address
    return get_if(iff, SIOCGIFHWADDR)[18:24]

def get_iface_ip_addr(iff):
    SIOCGIFADDR = 0x8915            # Get ip address
    return get_if(iff, SIOCGIFADDR)[20:24]

def send_arp(s, src_mac, src_ip, dst_mac_s, dst_ip_s):
    # convert dst_mac in binary
    dst_ip = socket.inet_aton(dst_ip_s)

    # convert dst_ip in binary
    dst_mac = binascii.unhexlify(dst_mac_s.replace(':', ''))

    # make ARP packet
    pkt = dst_mac + src_mac + ARP_CHUNK + src_mac + src_ip + dst_mac + dst_ip + ARP_PAD

    # send it
    s.send(pkt)

    return

def send_ndp(s, src_mac, src_ip, dst_mac_s, dst_ip_s):
    #TODO: Implement send in neighbor solicitation format

    return

def send_garp_nd(neighbor_entries, map_mac_ip_per_vlan):
    ETH_P_ALL = 0x03

    # generate source ip addresses for arp packets
    src_ip_addrs = {vlan_name:get_iface_ip_addr(vlan_name) for vlan_name,_,_ in neighbor_entries}

    # generate source mac addresses for arp packets
    src_ifs = {map_mac_ip_per_vlan[vlan_name][dst_mac] for vlan_name, dst_mac, _ in neighbor_entries}
    src_mac_addrs = {src_if:get_iface_mac_addr(src_if) for src_if in src_ifs}

    # open raw sockets for all required interfaces
    sockets = {}
    for src_if in src_ifs:
        sockets[src_if] = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        sockets[src_if].bind((src_if, 0))

    # send arp/ndp packets
    for vlan_name, dst_mac, dst_ip in neighbor_entries:
        src_if = map_mac_ip_per_vlan[vlan_name][dst_mac]
        if ipaddress.ip_interface(str(dst_ip)).ip.version == 4:
            send_arp(sockets[src_if], src_mac_addrs[src_if], src_ip_addrs[vlan_name], dst_mac, dst_ip)
        else:
            send_ndp(sockets[src_if], src_mac_addrs[src_if], src_ip_addrs[vlan_name], dst_mac, dst_ip)

    # close the raw sockets
    for s in sockets.values():
        s.close()

    return

def get_default_entries(db, route):
    key = 'ROUTE_TABLE:%s' % route
    keys = db.keys(db.APPL_DB, key)
    if keys is None:
        return None

    entry = db.get_all(db.APPL_DB, key)
    obj = {
        key: entry,
        'OP': 'SET'
    }

    return obj

def generate_default_route_entries(filename):
    db = SonicV2Connector(unix_socket_path=False)
    db.connect(db.APPL_DB, False)   # Make one attempt only

    default_routes_output = []

    ipv4_default = get_default_entries(db, '0.0.0.0/0')
    if ipv4_default is not None:
        default_routes_output.append(ipv4_default)

    ipv6_default = get_default_entries(db, '::/0')
    if ipv6_default is not None:
        default_routes_output.append(ipv6_default)

    db.close(db.APPL_DB)

    with open(filename, 'w') as fp:
        json.dump(default_routes_output, fp, indent=2, separators=(',', ': '))

def generate_media_config(filename):
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.APPL_DB, False)   # Make one attempt only
    media_config= []
    port_serdes_keys = ["preemphasis", "idriver", "ipredriver", "pre1", "pre2", "pre3", "main", "post1", "post2", "post3","attn"]
    keys = db.keys(db.APPL_DB, 'PORT_TABLE:*')
    keys = [] if keys is None else keys
    for key in keys:
        entry = db.get_all(db.APPL_DB, key)
        media_attributes = {}
        for attr in entry.keys():
            if attr in port_serdes_keys:
                media_attributes[attr] = entry[attr]
        obj = {
          '%s' % (key) : media_attributes,
          'OP': 'SET'
        }
        media_config.append(obj)

    db.close(db.APPL_DB)

    with open(filename, 'w') as fp:
        json.dump(media_config, fp, indent=2, separators=(',', ': '))

    return media_config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--target', type=str, default='/tmp', help='target directory for files')
    args = parser.parse_args()
    root_dir = args.target
    if not os.path.isdir(root_dir):
        print("Target directory '%s' not found" % root_dir)
        return 3
    all_available_macs, map_mac_ip_per_vlan = generate_fdb_entries(root_dir + '/fdb.json')
    neighbor_entries = generate_neighbor_entries(root_dir + '/arp.json', all_available_macs)
    generate_default_route_entries(root_dir + '/default_routes.json')
    generate_media_config(root_dir + '/media_config.json')
    send_garp_nd(neighbor_entries, map_mac_ip_per_vlan)
    return 0

if __name__ == '__main__':
    res = 0
    try:
        syslog.openlog('fast-reboot-dump')
        res = main()
    except KeyboardInterrupt:
        syslog.syslog(syslog.LOG_NOTICE, "SIGINT received. Quitting")
        res = 1
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
        res = 2
    finally:
        syslog.closelog()
    try:
        sys.exit(res)
    except SystemExit:
        os._exit(res)
