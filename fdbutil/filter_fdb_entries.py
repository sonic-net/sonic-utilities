import argparse
import json
import os
import sys
import syslog
import time
import traceback

from collections import defaultdict
from ipaddress import ip_address, ip_network, ip_interface

def get_vlan_cidr_map(filename):
    """
        Generate Vlan CIDR information from Config DB file

        fdb entries could be contaminated with foreigh Vlan entries as seen in the case of 
        FTOS fast conversion. SONiC Vlan CIDR configuration will be used to filter out
        those invalid Vlan entries out.

        Args:
            filename(str): Config DB data file

        Returns:
            vlan_cidr(dict) map of Vlan CIDR configuration for SONiC device
    """
    with open(filename, 'r') as fp:
        config_db_entries = json.load(fp)

    vlan_cidr = defaultdict()
    if "VLAN_INTERFACE" in config_db_entries and "VLAN" in config_db_entries:
        for vlan_key in config_db_entries["VLAN_INTERFACE"]:
            if '|' not in vlan_key:
                continue
            vlan, cidr = tuple(vlan_key.split('|'))
            if vlan in config_db_entries["VLAN"]:
                if vlan not in vlan_cidr:
                    vlan_cidr[vlan] = {4: ip_address("0.0.0.0"), 6: ip_address("::")}
                vlan_cidr[vlan][ip_interface(cidr).version] = ip_interface(cidr).network

    return vlan_cidr

def get_arp_entries_map(arp_filename, config_db_filename):
    """
        Generate map for ARP entries

        ARP entry map is using the MAC as a key for the arp entry. The map key is reformated in order
        to match FDB table formatting

        Args:
            arp_filename(str): ARP entry file name
            config_db_filename(str): Config DB file name

        Returns:
            arp_map(dict) map of ARP entries using MAC as key.
    """
    vlan_cidr = get_vlan_cidr_map(config_db_filename)

    with open(arp_filename, 'r') as fp:
        arp_entries = json.load(fp)

    arp_map = defaultdict()
    for arp in arp_entries:
        for key, config in arp.items():
            if "NEIGH_TABLE" not in key:
                continue
            table, vlan, ip = tuple(key.split(':', 2)) # split with max of 2 is used here because IPv6 addresses contain ':' causing a creation of a non tuple object 
            if "NEIGH_TABLE" in table and vlan in vlan_cidr \
                and ip_address(ip) in ip_network(vlan_cidr[vlan][ip_interface(ip).version]) \
                and "neigh" in config:
                arp_map[config["neigh"].replace(':', '-').upper()] = ""

    return arp_map

def filter_fdb_entries(fdb_filename, arp_filename, config_db_filename, backup_file):
    """
        Filter FDB entries based on MAC presence into ARP entries

        FDB entries that do not have MAC entry in the ARP table are filtered out. New FDB entries
        file will be created if it has fewer entries than original one.

        Args:
            fdb_filename(str): FDB entries file name
            arp_filename(str): ARP entry file name
            config_db_filename(str): Config DB file name
            backup_file(bool): Create backup copy of FDB file before creating new one

        Returns:
            None
    """
    arp_map = get_arp_entries_map(arp_filename, config_db_filename)

    with open(fdb_filename, 'r') as fp:
        fdb_entries = json.load(fp)

    def filter_fdb_entry(fdb_entry):
        for key, _ in fdb_entry.items():
            if 'FDB_TABLE' in key:
                return key.split(':')[-1].upper() in arp_map

        # malformed entry, default to False so it will be deleted
        return False

    new_fdb_entries = list(filter(filter_fdb_entry, fdb_entries))

    if len(new_fdb_entries) < len(fdb_entries):
        if backup_file:
            os.rename(fdb_filename, fdb_filename + '-' + time.strftime("%Y%m%d-%H%M%S"))

        with open(fdb_filename, 'w') as fp:
            json.dump(new_fdb_entries, fp, indent=2, separators=(',', ': '))

def file_exists_or_raise(filename):
    """
        Check if file exists on the file system

        Args:
            filename(str): File name

        Returns:
            None

        Raises:
            Exception file does not exist
    """
    if not os.path.exists(filename):
        raise Exception("file '{0}' does not exist".format(filename))

def main(argv=sys.argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fdb', type=str, default='/tmp/fdb.json', help='fdb file name')
    parser.add_argument('-a', '--arp', type=str, default='/tmp/arp.json', help='arp file name')
    parser.add_argument('-c', '--config_db', type=str, default='/tmp/config_db.json', help='config db file name')
    parser.add_argument('-b', '--backup_file', type=bool, default=True, help='Back up old fdb entries file')
    args = parser.parse_args(argv[1:])

    fdb_filename = args.fdb
    arp_filename = args.arp
    config_db_filename = args.config_db
    backup_file = args.backup_file

    res = 0
    try:
        syslog.openlog('filter_fdb_entries')
        file_exists_or_raise(fdb_filename)
        file_exists_or_raise(arp_filename)
        file_exists_or_raise(config_db_filename)
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
    except KeyboardInterrupt:
        syslog.syslog(syslog.LOG_NOTICE, "SIGINT received. Quitting")
        res = 1
    else:
        filter_fdb_entries(fdb_filename, arp_filename, config_db_filename, backup_file)
    finally:
        syslog.closelog()

    return res
