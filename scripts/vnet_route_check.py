#!/usr/bin/env python

import sys
import json
import syslog
import subprocess
import argparse
from swsscommon import swsscommon

''' vnet_route_check.py: tool that verifies VNET routes consistancy between SONiC and vendor SDK DBs.

Logically VNET route verification logic consists of 3 parts:
1. Get VNET routes entries that are missed in ASIC_DB but present in APP_DB.
2. Get VNET routes entries that are missed in APP_DB but present in ASIC_DB.
3. Get VNET routes entries that are missed in SDK but present in ASIC_DB.

Returns 0 if there is no inconsistancy found and all VNET routes are aligned in all DBs.
Returns -1 if there is incosistancy found and prints differences between DBs in JSON format to standart output.

Format of differences output:
{
    "results": {
        "missed_in_asic_db_routes": {
            "<vnet_name>": {
                "routes": [
                    "<pfx>/<pfx_len>"
                ]
            }
        },
        "missed_in_app_db_routes": {
            "<vnet_name>": {
                "routes": [
                    "<pfx>/<pfx_len>"
                ]
            }
        },
        "missed_in_sdk_routes": {
            "<vnet_name>": {
                "routes": [
                    "<pfx>/<pfx_len>"
                ]
            }
        }
    }
}
'''


RC_OK = 0
RC_ERR = -1
default_vrf_oid = ""

report_level = syslog.LOG_ERR
write_to_syslog = True


def set_level(lvl, log_to_syslog):
    global report_level
    global write_to_syslog

    write_to_syslog = log_to_syslog
    report_level = lvl


def print_message(lvl, *args):
    if (lvl <= report_level):
        msg = ""
        for arg in args:
            msg += " " + str(arg)
        print(msg)
        if write_to_syslog:
            syslog.syslog(lvl, msg)


def check_vnet_cfg():
    ''' Returns True if VNET is configured in APP_DB or False if no VNET configuration.
    '''
    db = swsscommon.DBConnector('APPL_DB', 0, True)

    vnet_db_keys = swsscommon.Table(db, 'VNET_TABLE').getKeys()

    return True if vnet_db_keys else False


def get_vnet_intfs():
    ''' Returns dictionary of VNETs and related VNET interfaces.
    Format: { <vnet_name>: [ <vnet_rif_name> ] }
    '''
    db = swsscommon.DBConnector('APPL_DB', 0, True)

    intfs_table = swsscommon.Table(db, 'INTF_TABLE')
    intfs_keys = swsscommon.Table(db, 'INTF_TABLE').getKeys()

    vnet_intfs = {}

    for intf_key in intfs_keys:
        intf_attrs = dict(intfs_table.get(intf_key)[1])

        if 'vnet_name' in intf_attrs:
            vnet_name = intf_attrs['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(intf_key)
            else:
                vnet_intfs[vnet_name] = [intf_key]

    return vnet_intfs


def get_all_rifs_oids():
    ''' Returns dictionary of all router interfaces and their OIDs.
    Format: { <rif_name>: <rif_oid> }
    '''
    db = swsscommon.DBConnector('COUNTERS_DB', 0, True)
    rif_table = swsscommon.Table(db, 'COUNTERS_RIF_NAME_MAP')

    rif_name_oid_map = dict(rif_table.get('')[1])

    return rif_name_oid_map


def get_vnet_rifs_oids():
    ''' Returns dictionary of VNET interfaces and their OIDs.
    Format: { <vnet_rif_name>: <vnet_rif_oid> }
    '''
    vnet_intfs = get_vnet_intfs()
    intfs_oids = get_all_rifs_oids()

    vnet_intfs = [vnet_intfs[k] for k in vnet_intfs]
    vnet_intfs = [val for sublist in vnet_intfs for val in sublist]

    vnet_rifs_oids_map = {}

    for intf_name in intfs_oids or {}:
        if intf_name in vnet_intfs:
            vnet_rifs_oids_map[intf_name] = intfs_oids[intf_name]

    return vnet_rifs_oids_map


def get_vrf_entries():
    ''' Returns dictionary of VNET interfaces and corresponding VRF OIDs.
    Format: { <vnet_rif_name>: <vrf_oid> }
    '''
    db = swsscommon.DBConnector('ASIC_DB', 0, True)
    rif_table = swsscommon.Table(db, 'ASIC_STATE')

    vnet_rifs_oids = get_vnet_rifs_oids()

    rif_vrf_map = {}
    for vnet_rif_name in vnet_rifs_oids:

        db_keys = rif_table.getKeys()

        for db_key in db_keys:
            if (db_key == f'SAI_OBJECT_TYPE_ROUTER_INTERFACE:{vnet_rifs_oids[vnet_rif_name]}'):
                rif_attrs = dict(rif_table.get(db_key)[1])
                rif_vrf_map[vnet_rif_name] = rif_attrs['SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID']

    return rif_vrf_map


def filter_out_vnet_ip2me_routes(vnet_routes):
    ''' Filters out IP2ME routes from the provided dictionary with VNET routes
    Format: { <vnet_name>: { 'routes': [ <pfx/pfx_len> ], 'vrf_oid': <oid> } }
    '''
    db = swsscommon.DBConnector('APPL_DB', 0, True)

    all_rifs_db_keys = swsscommon.Table(db, 'INTF_TABLE').getKeys()
    vnet_intfs = get_vnet_intfs()

    vnet_intfs = [vnet_intfs[k] for k in vnet_intfs]
    vnet_intfs = [val for sublist in vnet_intfs for val in sublist]

    vnet_ip2me_routes = []
    for rif in all_rifs_db_keys:
        rif_attrs = rif.split(':')
        # Skip RIF entries without IP prefix and prefix length (they have only one attribute - RIF name)
        if len(rif_attrs) == 1:
            continue

        # rif_attrs[0] - RIF name
        # rif_attrs[1] - IP prefix and prefix legth
        # IP2ME routes have '/32' prefix length so replace it and add to the list
        if rif_attrs[0] in vnet_intfs:
            rif_ip, _ = rif_attrs[1].split('/')
            ip2me_route = rif_ip + '/32'
            vnet_ip2me_routes.append(ip2me_route)

    for vnet, vnet_attrs in vnet_routes.items():
        for route in vnet_attrs['routes']:
            if route in vnet_ip2me_routes:
                vnet_attrs['routes'].remove(route)

        if not vnet_attrs['routes']:
            vnet_routes.pop(vnet)


def get_vnet_routes_from_app_db():
    ''' Returns dictionary of VNET routes configured per each VNET in APP_DB.
    Format: { <vnet_name>: { 'routes': [ <pfx/pfx_len> ], 'vrf_oid': <oid> } }
    '''
    db = swsscommon.DBConnector('APPL_DB', 0, True)

    vnet_intfs = get_vnet_intfs()
    vnet_vrfs = get_vrf_entries()

    vnet_route_table = swsscommon.Table(db, 'VNET_ROUTE_TABLE')
    vnet_route_tunnel_table = swsscommon.Table(db, 'VNET_ROUTE_TUNNEL_TABLE')

    vnet_routes_db_keys = vnet_route_table.getKeys() + vnet_route_tunnel_table.getKeys()

    vnet_routes = {}

    for vnet_route_db_key in vnet_routes_db_keys:
        vnet_route_list = vnet_route_db_key.split(':',1)
        vnet_name = vnet_route_list[0]
        vnet_route = vnet_route_list[1]

        if vnet_name not in vnet_routes:
            vnet_routes[vnet_name] = {}
            vnet_routes[vnet_name]['routes'] = []

            if vnet_name not in vnet_intfs:
                # this route has no vnet_intf and may be part of default VRF.
                vnet_table = swsscommon.Table(db, 'VNET_TABLE')
                scope_value = ""
                # "Vnet_v4_in_v4-0": [("vxlan_tunnel", "tunnel_v4"), ("scope", "default"), ("vni", "10000"), ("peer_list", "")]
                for key,value in vnet_table.get(vnet_name)[1]:
                    if key == "scope":
                        scope_value = value
                        break
                if scope_value == 'default':
                    vnet_routes[vnet_name]['vrf_oid'] = default_vrf_oid
                else:
                    assert "Non-default VRF route present without vnet interface."
            else:
                intf = vnet_intfs[vnet_name][0]
                vnet_routes[vnet_name]['vrf_oid'] = vnet_vrfs.get(intf, 'None')

        vnet_routes[vnet_name]['routes'].append(vnet_route)

    return vnet_routes


def get_vnet_routes_from_asic_db():
    ''' Returns dictionary of VNET routes configured per each VNET in ASIC_DB.
    Format: { <vnet_name>: { 'routes': [ <pfx/pfx_len> ], 'vrf_oid': <oid> } }
    '''
    db = swsscommon.DBConnector('ASIC_DB', 0, True)

    tbl = swsscommon.Table(db, 'ASIC_STATE')

    vnet_vrfs = get_vrf_entries()
    vnet_vrfs_oids = [vnet_vrfs[k] for k in vnet_vrfs]
    vnet_vrfs_oids.append(default_vrf_oid) 

    vnet_intfs = get_vnet_intfs()

    vrf_oid_to_vnet_map = {}
    vrf_oid_to_vnet_map[default_vrf_oid] = 'default_VRF'

    for vnet_name, vnet_rifs in vnet_intfs.items():
        for vnet_rif, vrf_oid in vnet_vrfs.items():
            if vnet_rif in vnet_rifs:
                vrf_oid_to_vnet_map[vrf_oid] = vnet_name

    routes_db_keys = tbl.getKeys()

    vnet_routes = {}

    for route_db_key in routes_db_keys:
        route_attrs = route_db_key.lower().split('\"', -1)

        if 'sai_object_type_route_entry' not in route_attrs[0]:
            continue

        # route_attrs[11] - VRF OID for the VNET route
        # route_attrs[3] - VNET route IP subnet
        vrf_oid = route_attrs[11]
        ip_addr = route_attrs[3]

        if vrf_oid in vnet_vrfs_oids:
            vnet_name = vrf_oid_to_vnet_map[vrf_oid]
            if vrf_oid_to_vnet_map[vrf_oid] not in vnet_routes:
                vnet_routes[vnet_name] = {}
                vnet_routes[vnet_name]['routes'] = []
                vnet_routes[vnet_name]['vrf_oid'] = vrf_oid

            vnet_routes[vnet_name]['routes'].append(ip_addr)

    filter_out_vnet_ip2me_routes(vnet_routes)

    return vnet_routes


def check_routes_with_default_vrf(vnet_name, vnet_attrs, routes_1, routes):
    for vnet_route in vnet_attrs['routes']:
        ispresent = False
        for vnet_name_other, vnet_attrs_other in routes_1.items():
            if vnet_route in vnet_attrs_other['routes']:
                ispresent = True
        if not ispresent:
            if vnet_name not in routes:
                routes[vnet_name] = {}
                routes[vnet_name]['routes'] = []
            routes[vnet_name]['routes'].append(vnet_route)

    return


def get_vnet_routes_diff(routes_1, routes_2, verify_default_vrf_routes = False):
    ''' Returns all routes present in routes_2 dictionary but missed in routes_1
    Format: { <vnet_name>: { 'routes': [ <pfx/pfx_len> ] } }
    '''

    routes = {}

    for vnet_name, vnet_attrs in routes_2.items():
        if vnet_attrs['vrf_oid'] == default_vrf_oid:
            if verify_default_vrf_routes:
                check_routes_with_default_vrf(vnet_name, vnet_attrs, routes_1, routes)
            else:
                continue
        else:
            if vnet_name not in routes_1:
                routes[vnet_name] =  vnet_attrs['routes'].copy()
            else:
                for vnet_route in vnet_attrs['routes']:
                    if vnet_route not in routes_1[vnet_name]['routes']:
                        if vnet_name not in routes:
                            routes[vnet_name] = {}
                            routes[vnet_name]['routes'] = []
                        routes[vnet_name]['routes'].append(vnet_route)

    return routes


def get_sdk_vnet_routes_diff(routes):
    ''' Returns all routes present in routes dictionary but missed in SAI/SDK
    Format: { <vnet_name>: { 'routes': [ <pfx/pfx_len> ], 'vrf_oid': <oid> } }
    '''
    routes_diff = {}

    res = subprocess.call(['docker', 'exec', 'syncd', 'test', '-f', '/usr/bin/vnet_route_check.py'])
    if res != 0:
        return routes_diff

    for vnet_name, vnet_routes in routes.items():
        vnet_routes = routes[vnet_name]["routes"]
        vnet_vrf_oid = routes[vnet_name]["vrf_oid"]

        res = subprocess.call(['docker', 'exec', 'syncd', "/usr/bin/vnet_route_check.py", vnet_vrf_oid, vnet_routes])
        if res:
            routes_diff[vnet_name] = {}
            routes_diff[vnet_name]['routes'] = res

    return routes_diff


def filter_active_vnet_routes(vnet_routes: dict):
    """ Filters a dictionary containing VNet routes configured for each VNet in APP_DB.
    For each VNet in "vnet_routes", only active routes are included in the returned dictionary.
    Format (for both input and output):
    { <vnet_name>: { 'routes': [ <pfx/pfx_len> ], 'vrf_oid': <oid> } }
    """
    state_db = swsscommon.DBConnector("STATE_DB", 0, True)
    vnet_route_tunnel_table = swsscommon.Table(state_db, "VNET_ROUTE_TUNNEL_TABLE")

    vnet_active_routes = {}
    for vnet_name, vnet_info in vnet_routes.items():
        active_routes = []
        for prefix in vnet_info["routes"]:
            key = f"{vnet_name}|{prefix}"
            exists, fvs = vnet_route_tunnel_table.get(key)
            if not exists:
                print_message(syslog.LOG_WARNING, f"VNET_ROUTE_TUNNEL_TABLE|{key} does not exist in STATE DB.")
                active_routes.append(prefix)  # Treating "prefix" as an active route
                continue
            for field, value in fvs:
                if field == "state" and value == "active":
                    active_routes.append(prefix)
                    break
        if len(active_routes) > 0:
            vnet_active_routes[vnet_name] = {"routes": active_routes, "vrf_oid": vnet_info["vrf_oid"]}

    return vnet_active_routes


def main():
    parser = argparse.ArgumentParser(
        description="A script that checks for VNet route mismatches between APP DB, ASIC DB, and SDK.")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Find routes missed in ASIC DB by checking both active and inactive routes in APP DB.")
    args = parser.parse_args()

    rc = RC_OK

    # Don't run VNET routes consistancy logic if there is no VNET configuration
    if not check_vnet_cfg():
        return rc
    asic_db = swsscommon.DBConnector('ASIC_DB', 0, True)
    virtual_router = swsscommon.Table(asic_db, 'ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER')
    global default_vrf_oid
    default_vrf_oid = ""
    vr_keys = virtual_router.getKeys()
    if vr_keys:
        default_vrf_oid = vr_keys[0]

    app_db_vnet_routes = get_vnet_routes_from_app_db()
    active_app_db_vnet_routes = filter_active_vnet_routes(app_db_vnet_routes)
    asic_db_vnet_routes = get_vnet_routes_from_asic_db()

    if args.all:
        missed_in_asic_db_routes = get_vnet_routes_diff(asic_db_vnet_routes, app_db_vnet_routes, True)
    else:
        missed_in_asic_db_routes = get_vnet_routes_diff(asic_db_vnet_routes, active_app_db_vnet_routes, True)
    missed_in_app_db_routes = get_vnet_routes_diff(app_db_vnet_routes, asic_db_vnet_routes)
    missed_in_sdk_routes = get_sdk_vnet_routes_diff(asic_db_vnet_routes)

    res = {}
    res['results'] = {}
    rc = RC_OK

    if missed_in_asic_db_routes:
        res['results']['missed_in_asic_db_routes'] = missed_in_asic_db_routes

    if missed_in_app_db_routes:
        res['results']['missed_in_app_db_routes'] = missed_in_app_db_routes

    if missed_in_sdk_routes:
        res['results']['missed_in_sdk_routes'] = missed_in_sdk_routes

    if res['results']:
        rc = RC_ERR
        print_message(syslog.LOG_ERR, json.dumps(res, indent=4))
        print_message(syslog.LOG_ERR, 'Vnet Route Mismatch reported')
        return rc, res
    return rc


if __name__ == "__main__":
    sys.exit(main())
