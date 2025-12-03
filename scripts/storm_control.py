#!/usr/bin/env python3

############################################
#
# script to test storm_control functionality
#
############################################

import argparse
import sys
import os

# mock the redis for unit test purposes #
try:
    if os.environ["UTILITIES_UNIT_TESTING"] == "2":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        test_path = os.path.join(modules_path, "tests")
        sys.path.insert(0, modules_path)
        sys.path.insert(0, test_path)
        import mock_tables.dbconnector

except KeyError:
    pass

from natsort import natsorted
from tabulate import tabulate
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from utilities_common.general import load_db_config

STORM_TABLE_NAME = "PORT_STORM_CONTROL"

class storm_control(object):
    def __init__(self):
        self.config_db = ConfigDBConnector()
        self.config_db.connect()
        self.db = SonicV2Connector(use_unix_socket_path=False)
        self.db.connect(self.db.CONFIG_DB)
    def show_storm_config(self, port):
        header = ['Interface Name', 'Storm Type', 'Rate (kbps)']
        storm_type_list = ['broadcast','unknown-unicast','unknown-multicast']
        body = []
        configs = self.db.get_table(STORM_TABLE_NAME)
        if not configs:
            return
        storm_configs = natsorted(configs)
        if port is not None:
            for storm_type in storm_type_list:
                storm_key = port + '|' + storm_type
                data = self.db.get_entry(STORM_TABLE_NAME, storm_key)
                if data:
                    kbps = data['kbps']
                    body.append([port, storm_type, kbps])
        else:
            for storm_key in storm_configs:
                interface_name = storm_key[0]
                storm_type = storm_key[1]
                data = self.db.get_entry(STORM_TABLE_NAME, storm_key)
                if data:
                    kbps = data['kbps']
                    body.append([interface_name, storm_type, kbps])
        print(tabulate(body,header,tablefmt="grid")) 

    def validate_interface(self, port):
        if not (port.startswith("Eth")):
            return False
        return True

    def validate_kbps(self, kbps):
        return True

    def add_storm_config(self, port, storm_type, kbps):
        if not validate_interface(port):
            print ("Invalid Interface:{}".format(port))
            return False
        if not validate_kbps(kbps):
            print ("Invalid kbps value:{}".format(kbps))
            return False
        key = port + '|' + storm_type
        entry = self.db.get_entry(STORM_TABLE_NAME,key)
        if len(entry) == 0:
            self.db.set_entry(STORM_TABLE_NAME, key, {'kbps':kbps})
        else:
            kbps_value = int(entry.get('kbps',0))
            if kbps_value != kbps:
                self.db.mod_entry(STORM_TABLE_NAME, key, {'kbps':kbps})
        return True

    def del_storm_config(self, port, storm_type):
        if not validate_interface(port):
            print ("Invalid Interface:{}".format(port))
            return False
        key = port_name + '|' + storm_type
        entry = self.db.get_entry(STORM_TABLE_NAME, key)
        if len(entry):
            self.db.set_entry(STORM_TABLE_NAME, key, None)
        return True

def main():
    parser  = argparse.ArgumentParser(description='Configure and Display storm-control configuration',
                                        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-l', '--list', action='store_true', help='show storm-control configuration', default=False)
    parser.add_argument('-p', '--port', type=str, help='port name (e.g. Ethernet0)', required=True, default=None)
    parser.add_argument('-t', '--storm-type', type=str, help='storm-type (broadcast, unknown-unicast, unknown-multicast)', required=True, default=None)
    parser.add_argument('-r', '--rate-kbps', type=int, help='kbps value', required=True, default=None)
    parser.add_argument('-d', '--delete', help='delete storm-control')
    parser.add_argument('-f', '--filename', help='file used by mock test', type=str, default=None)
    args = parser.parse_args()

    # Load database config files
    load_db_config()
    try:
        storm = storm_control()
        if args.list:
            input_port=""
            if args.port:
                input_port = args.port
            storm.show_storm_config(input_port)
        elif args.port and args.storm_type and args.rate_kbps:
            if args.delete:
                storm.del_storm_config(args.port, args.storm_type)
            else:
                storm.add_storm_config(args.port, args.storm_type, args.rate_kbps)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        try:
            if os.environ["UTILITIES_UNIT_TESTING"] == "1" or os.environ["UTILITIES_UNIT_TESTING"] == "2":
                print(str(e), file=sys.stdout)
        except KeyError:
            print(str(e), file=sys.stderr)

        sys.exit(1)

if __name__ == "__main__":
    main()
