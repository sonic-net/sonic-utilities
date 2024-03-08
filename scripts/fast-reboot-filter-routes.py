#!/usr/bin/env python3

import json
import sys
import os
import utilities_common.cli as clicommon
import syslog
import traceback
from swsscommon.swsscommon import ConfigDBConnector

ROUTE_IDX = 1

def get_connected_routes():
    cmd = ['sudo', 'vtysh', '-c', "show ip route connected json"]
    connected_routes = []
    output, ret = clicommon.run_command(cmd, return_cmd=True)
    if ret != 0:
        raise Exception("Failed to execute {}: {}".format(" ".join(cmd), output.rstrip('\n')))
    if output is not None:
        route_info = json.loads(output)
        for route in route_info.keys():
            connected_routes.append(route)

    return connected_routes

def get_route(db, route):
    key = 'ROUTE_TABLE:%s' % route
    val = db.keys(db.APPL_DB, key)
    if val:
        return val[0].split(":", 1)[ROUTE_IDX]
    else:
        return None

def generate_default_route_entries():
    db = ConfigDBConnector()
    db.db_connect(db.APPL_DB)

    default_routes = []

    ipv4_default = get_route(db, '0.0.0.0/0')
    if ipv4_default is not None:
        default_routes.append(ipv4_default)

    ipv6_default = get_route(db, '::/0')
    if ipv6_default is not None:
        default_routes.append(ipv6_default)

    return default_routes

def filter_routes(preserved_routes):
    db = ConfigDBConnector()
    db.db_connect(db.APPL_DB)

    key = 'ROUTE_TABLE:*'
    routes = db.keys(db.APPL_DB, key)

    for route in routes:
        stripped_route = route.split(":", 1)[ROUTE_IDX]
        if stripped_route not in preserved_routes:
            db.delete(db.APPL_DB, route)

def main():
    default_routes = generate_default_route_entries()
    connected_routes = get_connected_routes()
    preserved_routes = set(default_routes + connected_routes)
    filter_routes(preserved_routes)
    return 0

if __name__ == '__main__':
    res = 0
    try:
        syslog.openlog('fast-reboot-filter-routes')
        res = main()
    except KeyboardInterrupt:
        syslog.syslog(syslog.LOG_NOTICE, "SIGINT received. Quitting")
        res = 1
    except Exception as e:
        print(e)
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
        res = 2
    finally:
        syslog.closelog()
    try:
        sys.exit(res)
    except SystemExit:
        os._exit(res)
