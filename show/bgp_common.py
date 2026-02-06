import copy
import ipaddress
import json

import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import device_info, multi_asic
from utilities_common import constants

'''
 show ip(v6) route helper methods start
 Helper routines to support print_ip_routes()
'''
def get_status_output_char(info, nhp_i):
    NH_F_IS_RECURSIVE = 2
    NH_F_IS_DUPLICATE = 5
    if "queued" in info:
        return "q"
    elif "failed" in info:
        return "r"
    elif "installed" in info:
        if info['nexthops'][nhp_i]['flags'] & (1 << NH_F_IS_RECURSIVE) or info['nexthops'][nhp_i]['flags'] & (1 << NH_F_IS_DUPLICATE):
            return " "
        else:
            return "*"

    return ""

def get_distance_metric_str(info):
    if info['protocol'] != "connected":
        return (" [{}/{}]".format(info['distance'], info['metric']))
    elif info['distance'] > 0 or info['metric'] > 0:
        return (" [{}/{}]".format(info['distance'], info['metric']))
    return ""

def get_mpls_label_strgs(label_list):
    mpls_label_code = { 0:"IPv4 Explicit Null", 1:"Router Alert", 2:"IPv6 Explicit Null",
                        3:"implicit-null", 4:"Reserved (4)", 5:"Reserved (5)",
                        6:"Reserved (6)", 7:"Entropy Label Indicator", 8:"Reserved (8)",
                        9:"Reserved (9)", 10:"Reserved (10)", 11:"Reserved (11)",
                        12:"Reserved (12)", 13:"Generic Associated Channel",
                        14:"OAM Alert", 15:"Extension"}
    label_str_2_return = ""
    for k in range(0, len(label_list)):
        # MPLS labels that has value 15 or lower has special interpretation
        if label_list[k] > 15:
            label_string = str(label_list[k])
        else:
            label_string = mpls_label_code[label_list[k]]
        if k == 0:
            label_str_2_return += label_string
        else:
            label_str_2_return += "/" + label_string
    return label_str_2_return

def get_nexthop_info_str(nxhp_info, filterByIp):
    str_2_return = ""
    if "ip" in nxhp_info:
        if filterByIp:
            str_2_return = "  * {}".format(nxhp_info['ip'])
        else:
            str_2_return = " via {},".format(nxhp_info['ip'])
        if "interfaceName" in nxhp_info:
            intfs = nxhp_info['interfaceName']
            if filterByIp:
                str_2_return += ", via {}".format(intfs)
            else:
                str_2_return += " {},".format(intfs)

    elif "directlyConnected" in nxhp_info:
        str_2_return = " is directly connected,"
        if "interfaceName" in nxhp_info:
            str_2_return += " {},".format(nxhp_info['interfaceName'])
    elif "unreachable" in nxhp_info:
        if "reject" in nxhp_info:
            str_2_return = " (ICMP unreachable)"
        elif "admin-prohibited" in nxhp_info:
            str_2_return = " (ICMP admin-prohibited)"
        elif "blackhole" in nxhp_info:
            str_2_return = " (blackhole)"

    if "vrf" in nxhp_info:
        str_2_return += "(vrf {}, {},".format(nxhp_info['vrf'], nxhp_info['interfaceName'])
    if "active" not in nxhp_info:
        str_2_return += " inactive"
    if "recursive" in nxhp_info:
        if device_info.is_voq_chassis():
            str_2_return = "  " + str_2_return + " recursive via iBGP"
        else:
            str_2_return += " (recursive)"
    if "onLink" in nxhp_info:
        str_2_return += " onlink"
    if "source" in nxhp_info:
        str_2_return += ", src {}".format(nxhp_info['source'])
    if "labels" in nxhp_info:
        # MPLS labels are stored as an array (list) in json if present. Need to print through each one in list
        str_2_return += ", label {}".format(get_mpls_label_strgs(nxhp_info['labels']))
    if "weight" in nxhp_info:
        if filterByIp:
            str_2_return += ", weight {}".format(nxhp_info['weight'])
        else:
            str_2_return += " weight {},".format(nxhp_info['weight'])
    return str_2_return

def get_ip_value(ipn):
    ip_intf = ipaddress.ip_interface(ipn[0])
    return ip_intf.ip

def print_ip_routes(route_info, filter_by_ip):
    """
    Sample Entry output
    B>*172.16.8.2/32 [20/0] via 10.0.0.47, Ethernet92, 03:33:01
    B>*192.168.114.96/32 [20/0] via 10.0.0.1, PortChannel0002, 03:30:39
      *                         via 10.0.0.5, PortChannel0005, 03:30:39
      *                         via 10.0.0.9, PortChannel0008, 03:30:39
      *                         via 10.0.0.13, PortChannel0011, 03:30:39
      *                         via 10.0.0.17, PortChannel0014, 03:30:39
      *                         via 10.0.0.21, PortChannel0017, 03:30:39
      *                         via 10.0.0.25, PortChannel0020, 03:30:39
      *                         via 10.0.0.29, PortChannel0023, 03:30:39
    B 10.0.107.0/31 [200/0] via 10.0.107.1, inactive 00:10:15
    K>*0.0.0.0/0 [0/0] via 10.3.146.1, eth0, 00:25:22
    B 0.0.0.0/0 [20/0] via 10.0.0.1, PortChannel0002, 03:31:52
                      via 10.0.0.5, PortChannel0005, 03:31:52
                      via 10.0.0.9, PortChannel0008, 03:31:52
                      via 10.0.0.13, PortChannel0011, 03:31:52
                      via 10.0.0.17, PortChannel0014, 03:31:52
                      via 10.0.0.21, PortChannel0017, 03:31:52
                      via 10.0.0.25, PortChannel0020, 03:31:52
                      via 10.0.0.29, PortChannel0023, 03:31:52
    S 0.0.0.0/0 [200/0] via 10.3.146.1, eth0, 03:35:18
    C>*10.0.0.62/31 is directly connected, Ethernet124, 03:34:00

    if filter_by_ip is set it means the user requested the output based on given ip address
    Routing entry for 0.0.0.0/0
      Known via "static", distance 200, metric 0
      Last update 03:46:05 ago
        10.3.146.1 inactive

    Routing entry for 0.0.0.0/0
      Known via "bgp", distance 20, metric 0, best
        Last update 03:46:05 ago
        * 10.0.0.1, via PortChannel0002
        * 10.0.0.5, via PortChannel0005

    Routing entry for 0.0.0.0/0
      Known via "kernel", distance 210, metric 0
        Last update 03:46:36 ago
        * 240.127.1.1, via eth0

    This method is following what zebra_vty.c does when handling the route parsing printing
    The route_info is a json file which is treated as a dictionary of a bunch of route + info
    This interpretation is based on FRR 7.2 branch. If we later moved on to a new branch, we may
    have to rexamine if there are any changes made that may impact the parsing logic
    """
    proto_code = {"system":'X', "kernel":'K', "connected":'C', "static":'S',
                  "rip":'R', "ripng":'R', "ospf":'O', "ospf6":'O', "isis":'I',
                  "bgp":'B', "pim":'P', "hsls":'H', "olsr":'o', "babel":'A'}
    for route, info in sorted(route_info.items(), key=get_ip_value):
        for i in range(0, len(info)):
            if filter_by_ip:
                print("Routing entry for {}".format(str(route)))
                str_2_print = '  Known via "{}", distance {}, metric {}'.format(info[i]['protocol'], info[i]['distance'], info[i]['metric'])
                if "selected" in info[i]:
                    str_2_print += ", best"
                print(str_2_print)
                print("  Last update {} ago".format(info[i]['uptime']))
                for j in range(0, len(info[i]['nexthops'])):
                    if "directlyConnected" in info[i]['nexthops'][j]:
                        print("  * directly connected, {}\n".format(info[i]['nexthops'][j]['interfaceName']))
                    else:
                        str_2_print = get_nexthop_info_str(info[i]['nexthops'][j], True)
                        print(str_2_print)
                print("")
            else:
                str_2_print = ""
                str_2_print += proto_code[info[i]['protocol']]
                if "instance" in info[i]:
                    str_2_print += "[" + str(info[i]['instance']) + "]"
                if "selected" in info[i]:
                    str_2_print += ">"
                else:
                    str_2_print += " "
                for j in range(0, len(info[i]['nexthops'])):
                    if j != 0:
                        str_2_print = "  "
                    str_2_print += get_status_output_char(info[i], j)
                    # on 1st nexhop print the prefix and distance/metric if appropriate.
                    # on all subsequent nexthop replace the prefix and distance/metric by empty spaces only.
                    if j == 0:
                        str_2_print += info[i]['prefix'] + get_distance_metric_str(info[i])
                        str_length = len(str_2_print)
                    else:
                        # For all subsequent nexthops skip the spacing to not repeat the prefix section
                        str_2_print += " "*(str_length - 3)
                    # Get the nexhop info portion of the string
                    str_2_print += get_nexthop_info_str(info[i]['nexthops'][j], False)
                    # add uptime at the end of the string
                    str_2_print += " {}".format(info[i]['uptime'])
                    # print out this string
                    print(str_2_print)


def merge_to_combined_route(combined_route, route, new_info_l):
    # The following protocols do not have multi-nexthops. mbrship test with small list is faster than small set
    # If other protocol are also single nexthop not in this list just add them
    single_nh_proto = ["connected"]
    # check if this route already exists. if so, combine nethops and update the count
    if route in combined_route:
        while len(new_info_l):
            new_info = new_info_l.pop()
            proto_matched = False
            skip_this_new_info = False
            for j in range(0, len(combined_route[route])):
                if new_info['protocol'] == combined_route[route][j]['protocol']:
                    proto_matched = True
                    if new_info['protocol'] in single_nh_proto:
                        # For single nexhop protocols handling differs where it should be either not added or add ASIS
                        # If this is new, need to add the new_info. else skip this new_info
                        if combined_route[route][j]['nexthops'][0]['interfaceName'] == new_info['nexthops'][0]['interfaceName']:
                            skip_this_new_info = True
                            break
                    else:
                        # protocol may contain multiple nexthops. Need to filter by nexthops
                        additional_nh_l = []
                        while len(new_info['nexthops']):
                            nh = new_info['nexthops'].pop()
                            found = False
                            for y in range(0, len(combined_route[route][j]['nexthops'])):
                                if "interfaceName" in nh and "interfaceName" in combined_route[route][j]['nexthops'][y]:
                                    if nh['interfaceName'] == combined_route[route][j]['nexthops'][y]['interfaceName']:
                                        found = True
                                        break
                                if device_info.is_voq_chassis():
                                    if nh['ip'] == combined_route[route][j]['nexthops'][y]['ip']:
                                        if 'interfaceName' not in combined_route[route][j]['nexthops'][y]:
                                            combined_route[route][j]['nexthops'][y] = nh
                                        found = True
                                        break
                                elif "active" not in nh and "active" not in combined_route[route][j]['nexthops'][y]:
                                    if nh['ip'] == combined_route[route][j]['nexthops'][y]['ip']:
                                        found = True
                                        break
                            if not found:
                                additional_nh_l.append(copy.deepcopy(nh))

                        if len(additional_nh_l) > 0:
                            combined_route[route][j]['internalNextHopNum'] + len(additional_nh_l)
                            if combined_route[route][j]['internalNextHopActiveNum'] > 0 and new_info['internalNextHopActiveNum'] > 0:
                                combined_route[route][j]['internalNextHopActiveNum'] + len(additional_nh_l)
                            combined_route[route][j]['nexthops'] += additional_nh_l
                        # the nexhops merged, no need to add the new_info
                        skip_this_new_info = True
                        break
            if not proto_matched or not skip_this_new_info:
                # This new_info is unique and should be added to the route
                combined_route[route].append(new_info)
    else:
        combined_route[route] = new_info_l

def process_route_info(route_info, device, filter_back_end, print_ns_str, asic_cnt, ns_str, combined_route, back_end_intf_set):
    new_route = {}
    for route, info in route_info.items():
        new_info_l = []
        new_info_cnt = 0
        while len(info):
            new_info = info.pop()
            new_nhop_l = []
            del_cnt = 0
            while len(new_info['nexthops']):
                nh = new_info['nexthops'].pop()
                if filter_back_end and back_end_intf_set != None and "interfaceName" in nh:
                    if nh['interfaceName'] in back_end_intf_set or nh['interfaceName'].startswith('Ethernet-IB'):
                        del_cnt += 1
                    else:
                        new_nhop_l.append(copy.deepcopy(nh))
                else:
                    new_nhop_l.append(copy.deepcopy(nh))
            # use the new filtered nhop list if it is not empty. if empty nexthop , this route is filtered out completely
            if len(new_nhop_l) > 0:
                new_info['nexthops'] = copy.deepcopy(new_nhop_l)
                new_info_cnt += 1
                # in case there are any nexthop that were deleted, we will need to adjust the nexhopt counts as well
                if del_cnt > 0:
                    internalNextHopNum = new_info['internalNextHopNum'] - del_cnt
                    new_info['internalNextHopNum'] = internalNextHopNum
                    internalNextHopActiveNum = new_info['internalNextHopActiveNum'] - del_cnt
                    new_info['internalNextHopActiveNum'] = internalNextHopActiveNum
                new_info_l.append(copy.deepcopy(new_info))
        if new_info_cnt:
            if asic_cnt > 1:
                if filter_back_end:
                    merge_to_combined_route(combined_route, route, new_info_l)
                else:
                    new_route[route] = copy.deepcopy(new_info_l)
            else:
                new_route[route] = copy.deepcopy(new_info_l)
    if new_route:
        if print_ns_str:
            combined_route['{}'.format(ns_str)] = copy.deepcopy(new_route)
        else:
            combined_route.update(copy.deepcopy(new_route))

def print_show_ip_route_hdr():
    # This prints out the show ip route header based on FRR 7.2 version.
    # Please note that if we moved to future versions, we may heva to make changes to this
    print("Codes: K - kernel route, C - connected, S - static, R - RIP,")
    print("       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,")
    print("       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,")
    print("       F - PBR, f - OpenFabric,")
    print("       > - selected route, * - FIB route, q - queued route, r - rejected route\n")


'''
 handling multi-ASIC by gathering the output from specified/all name space into a dictionary via
 jason option and then filter out the json entries (by removing those next Hop that are
 back-end ASIC if display is for front-end only). If the entry itself has no more next Hop after filtering,
 then skip over that particular route entry.  Once completed, if the user chose "json" option,
 then just print out the dictionary in Json format accordingly. But if no "json" option specified,
 then print out the header and the decoded entry representation for each route accordingly.
 if user specified a namespace, then print everything.
 if user did not specify name space but specified display for all (include backend), then print each namespace
 without any filtering.  But if display is for front-end only, then do filter and combine all output(merge same
 routes from all namespace as additional nexthops)
 This code is based on FRR 7.2 branch. If we moved to a new version we may need to change here as well
'''
def show_routes(args, namespace, display, verbose, ipver):
    import utilities_common.bgp_util as bgp_util
    """Show IPv4/IPV6 routing table"""
    filter_back_end = False
    if display is None:
        if multi_asic.is_multi_asic():
            display = constants.DISPLAY_EXTERNAL
            filter_back_end = True
    else:
        if multi_asic.is_multi_asic():
            if display not in multi_asic_util.multi_asic_display_choices():
                print("dislay option '{}' is not a valid option.".format(display))
                return
            else:
                if display == constants.DISPLAY_EXTERNAL:
                    filter_back_end = True
        else:
            if display not in ['frontend', 'all']:
                print("dislay option '{}' is not a valid option.".format(display))
                return

    device = multi_asic_util.MultiAsic(display, namespace)
    arg_strg = ""
    found_json = 0
    found_other_parms = 0
    ns_l = []
    print_ns_str = False
    filter_by_ip = False
    asic_cnt = 0
    try:
        ns_l = device.get_ns_list_based_on_options()
    except ValueError:
        print("namespace '{}' is not valid. valid name spaces are:\n{}".format(namespace, multi_asic_util.multi_asic_ns_choices()))
        return
    asic_cnt = len(ns_l)
    if asic_cnt > 1 and display == constants.DISPLAY_ALL:
        print_ns_str = True
    if namespace is not None:
        if not multi_asic.is_multi_asic():
            print("namespace option is not applicable for non-multi-asic platform")
            return
    # build the filter set only if necessary
    if filter_back_end:
        back_end_intf_set = multi_asic.get_back_end_interface_set()
    else:
        back_end_intf_set = None
    # get all the other arguments except json that needs to be the last argument of the cmd if present
    # For Multi-ASIC platform the support for combining routes will be supported for "show ip/v6 route"
    # and optionally with specific IP address as parameter and the json option.  If any other option is
    # specified, the handling will always be handled by the specific namespace FRR.
    for arg in args:
        arg_strg += str(arg) + " "
        if str(arg) == "json":
            found_json = 1
        else:
            try:
                filter_by_ip = ipaddress.ip_network(arg)
            except ValueError:
                # Not ip address just ignore it
                found_other_parms = 1

    # using the same format for both multiasic or non-multiasic
    if not found_json and not found_other_parms:
        arg_strg += "json"

    combined_route = {}
    for ns in ns_l:
        # Need to add "ns" to form bgpX so it is sent to the correct bgpX docker to handle the request
        cmd = "show {} route {}".format(ipver, arg_strg)
        output = bgp_util.run_bgp_show_command(cmd, ns)
        # in case no output or something went wrong with user specified cmd argument(s) error it out
        # error from FRR always start with character "%"
        if output == "":
            return
        if output[0] == "%":
            # remove the "json" keyword that was added by this handler to show original cmd user specified 
            json_str = output[-5:-1]
            if json_str == "json":
                error_msg = output[:-5]
            else:
                error_msg = output
            print(error_msg)
            return

        # Multi-asic show ip route with additional parms are handled by going to FRR directly and get those outputs from each namespace
        if found_other_parms and not found_json:
            print("{}:".format(ns))
            print(output)
            continue

        route_info = json.loads(output)
        if filter_back_end or print_ns_str:
            # clean up the dictionary to remove all the nexthops that are back-end interface
            process_route_info(route_info, device, filter_back_end, print_ns_str, asic_cnt, ns, combined_route, back_end_intf_set)
        else:
            combined_route = route_info

    if not found_json:
        if len(combined_route) == 0:
            return

        #print out the header if this is not a json request
        if not filter_by_ip:
            print_show_ip_route_hdr()
        if print_ns_str:
            for name_space, ns_route in sorted(combined_route.items()):
                print("{}:".format(name_space))
                print_ip_routes(ns_route, filter_by_ip)
        else:
            print_ip_routes(combined_route, filter_by_ip)
    else:
        new_string = json.dumps(combined_route, sort_keys=True, indent=4)
        print(new_string)

'''
 show ip(v6) route helper methods end
'''
