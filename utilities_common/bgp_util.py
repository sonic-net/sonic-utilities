import ipaddress
import json
import re
import sys

import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from natsort import natsorted
from sonic_py_common import multi_asic, device_info
from tabulate import tabulate
from utilities_common import constants


def get_namespace_for_bgp_neighbor(neighbor_ip):
    namespace_list = multi_asic.get_namespace_list()
    for namespace in namespace_list:
        if is_bgp_neigh_present(neighbor_ip, namespace):
            return namespace

    # neighbor IP not present in any namespace
    raise ValueError(
                 ' Bgp neighbor {} not configured'.format(neighbor_ip))


def is_bgp_neigh_present(neighbor_ip, namespace=multi_asic.DEFAULT_NAMESPACE):
    config_db = multi_asic.connect_config_db_for_ns(namespace)
    #check the internal
    bgp_session = config_db.get_entry(multi_asic.BGP_NEIGH_CFG_DB_TABLE,
                                      neighbor_ip)
    if bgp_session:
        return True

    bgp_session = config_db.get_entry(
        multi_asic.BGP_INTERNAL_NEIGH_CFG_DB_TABLE, neighbor_ip)
    if bgp_session:
        return True
    return False


def is_ipv4_address(ip_address):
    """
    Checks if given ip is ipv4
    :param ip_address: str ipv4
    :return: bool
    """
    try:
        ipaddress.IPv4Address(ip_address)
        return True
    except ipaddress.AddressValueError as err:
        return False


def is_ipv6_address(ip_address):
    """
    Checks if given ip is ipv6
    :param ip_address: str ipv6
    :return: bool
    """
    try:
        ipaddress.IPv6Address(ip_address)
        return True
    except ipaddress.AddressValueError as err:
        return False


def get_dynamic_neighbor_subnet(db):
    """
    Returns dict of description and subnet info from bgp_peer_range table
    :param db: config_db
    """
    dynamic_neighbor = {}
    v4_subnet = {}
    v6_subnet = {}
    neighbor_data = db.get_table('BGP_PEER_RANGE')
    try:
        for entry in neighbor_data:
            new_key = neighbor_data[entry]['ip_range'][0]
            new_value = neighbor_data[entry]['name']
            if is_ipv4_address(neighbor_data[entry]['src_address']):
                v4_subnet[new_key] = new_value
            elif is_ipv6_address(neighbor_data[entry]['src_address']):
                v6_subnet[new_key] = new_value
        dynamic_neighbor[constants.IPV4] = v4_subnet
        dynamic_neighbor[constants.IPV6] = v6_subnet
        return dynamic_neighbor
    except Exception:
        return neighbor_data


def get_bgp_neighbors_dict(namespace=multi_asic.DEFAULT_NAMESPACE):
    """
    Uses config_db to get the bgp neighbors and names in dictionary format
    :return:
    """
    dynamic_neighbors = {}
    config_db = multi_asic.connect_config_db_for_ns(namespace)
    static_neighbors = get_neighbor_dict_from_table(config_db, 'BGP_NEIGHBOR')
    static_internal_neighbors = get_neighbor_dict_from_table(config_db, 'BGP_INTERNAL_NEIGHBOR')
    static_neighbors.update(static_internal_neighbors)
    static_internal_neighbors = get_neighbor_dict_from_table(config_db, 'BGP_VOQ_CHASSIS_NEIGHBOR')
    static_neighbors.update(static_internal_neighbors)
    bgp_monitors = get_neighbor_dict_from_table(config_db, 'BGP_MONITORS')
    static_neighbors.update(bgp_monitors)
    dynamic_neighbors = get_dynamic_neighbor_subnet(config_db)
    return static_neighbors, dynamic_neighbors


def get_external_bgp_neighbors_dict(namespace=multi_asic.DEFAULT_NAMESPACE):
    """
    Uses config_db to get the external bgp neighbors and names in dictionary format
    :return: dictionary of external bgp neighbors
    """
    config_db = multi_asic.connect_config_db_for_ns(namespace)
    external_neighbors = get_neighbor_dict_from_table(config_db, 'BGP_NEIGHBOR')
    bgp_monitors = get_neighbor_dict_from_table(config_db, 'BGP_MONITORS')
    external_neighbors.update(bgp_monitors)
    return external_neighbors


def get_bgp_neighbor_ip_to_name(ip, static_neighbors, dynamic_neighbors):
    """
    return neighbor name for the ip provided
    :param ip: ip address str
    :param static_neighbors: statically defined bgp neighbors dict
    :param dynamic_neighbors: subnet of dynamically defined neighbors dict
    :return: name of neighbor
    """
    if ip in static_neighbors:
        return static_neighbors[ip]
    elif is_ipv4_address(ip):
        for subnet in dynamic_neighbors[constants.IPV4]:
            if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(subnet):
                return dynamic_neighbors[constants.IPV4][subnet]
    elif is_ipv6_address(ip):
        for subnet in dynamic_neighbors[constants.IPV6]:
            if ipaddress.IPv6Address(ip) in ipaddress.IPv6Network(subnet):
                return dynamic_neighbors[constants.IPV6][subnet]
    else:
        return "NotAvailable"


def get_bgp_summary_extended(command_output):
    """
    Adds Neighbor name to the show ip[v6] bgp summary command
    :param command: command to get bgp summary
    """
    static_neighbors, dynamic_neighbors = get_bgp_neighbors_dict()
    modified_output = []
    my_list = iter(command_output.splitlines())
    for element in my_list:
        if element.startswith("Neighbor"):
            element = "{}\tNeighborName".format(element)
            modified_output.append(element)
        elif not element or element.startswith("Total number "):
            modified_output.append(element)
        elif re.match(r"(\*?([0-9A-Fa-f]{1,4}:|\d+.\d+.\d+.\d+))", element.split()[0]):
            first_element = element.split()[0]
            ip = first_element[1:] if first_element.startswith(
                "*") else first_element
            name = get_bgp_neighbor_ip_to_name(ip,
                                               static_neighbors,
                                               dynamic_neighbors)
            if len(element.split()) == 1:
                modified_output.append(element)
                element = next(my_list)
            element = "{}\t{}".format(element, name)
            modified_output.append(element)
        else:
            modified_output.append(element)
    click.echo("\n".join(modified_output))


def get_neighbor_dict_from_table(db, table_name):
    """
    returns a dict with bgp neighbor ip as key and neighbor name as value
    :param table_name: config db table name
    :param db: config_db
    """
    neighbor_dict = {}
    neighbor_data = db.get_table(table_name)
    try:
        for entry in neighbor_data:
            neighbor_dict[entry] = neighbor_data[entry].get(
                'name') if 'name' in neighbor_data[entry] else 'NotAvailable'
        return neighbor_dict
    except Exception:
        return neighbor_dict


def run_bgp_command(vtysh_cmd, bgp_namespace=multi_asic.DEFAULT_NAMESPACE, vtysh_shell_cmd=constants.VTYSH_COMMAND):
    bgp_instance_id = []
    output = None
    if bgp_namespace is not multi_asic.DEFAULT_NAMESPACE:
        bgp_instance_id = ['-n', str(multi_asic.get_asic_id_from_name(bgp_namespace))]

    cmd = ['sudo', vtysh_shell_cmd] + bgp_instance_id + ['-c', vtysh_cmd]
    try:
        output, ret = clicommon.run_command(cmd, return_cmd=True)
        if ret != 0:
            click.echo(output.rstrip('\n'))
            sys.exit(ret)
    except Exception:
        ctx = click.get_current_context()
        ctx.fail("Unable to get summary from bgp {}".format(bgp_instance_id))

    return output


def run_bgp_show_command(vtysh_cmd, bgp_namespace=multi_asic.DEFAULT_NAMESPACE):
    output = run_bgp_command(vtysh_cmd, bgp_namespace, constants.RVTYSH_COMMAND)
    # handle the the alias mode in the following code
    if output is not None:
        if clicommon.get_interface_naming_mode() == "alias" and re.search("show ip|ipv6 route", vtysh_cmd):
            iface_alias_converter = clicommon.InterfaceAliasConverter()
            route_info =json.loads(output)
            for route, info in route_info.items():
                for i in range(0, len(info)):
                    if 'nexthops' in info[i]:
                        for j in range(0, len(info[i]['nexthops'])):
                            intf_name = ""
                            if 'interfaceName' in info[i]['nexthops'][j]:
                                intf_name  = info[i]['nexthops'][j]['interfaceName']
                                alias = iface_alias_converter.name_to_alias(intf_name)
                                if alias is not None:
                                    info[i]['nexthops'][j]['interfaceName'] = alias 
            output= json.dumps(route_info)
    return output


def get_bgp_summary_from_all_bgp_instances(af, namespace, display):

    device = multi_asic_util.MultiAsic(display, namespace)
    ctx = click.get_current_context()
    if af is constants.IPV4:
        vtysh_cmd = "show ip bgp summary json"
        key = 'ipv4Unicast'
    else:
        vtysh_cmd = "show bgp ipv6 summary json"
        key = 'ipv6Unicast'

    bgp_summary = {}
    cmd_output_json = {}

    for ns in device.get_ns_list_based_on_options():
        has_bgp_neighbors = True
        cmd_output = run_bgp_show_command(vtysh_cmd, ns)
        device.current_namespace = ns
        try:
            cmd_output_json = json.loads(cmd_output)
        except ValueError:
            ctx.fail("bgp summary from bgp container not in json format")

        # no bgp neighbors found so print basic device bgp info
        if key not in cmd_output_json:
            has_bgp_neighbors = False
        else:
            # for multi asic devices or chassis linecards, the output of 'show ip bgp summary json'
            # will have both internal and external bgp neighbors
            # So, check if the current namespace has external bgp neighbors.
            # If not, treat it as no bgp neighbors
            if (device.get_display_option() == constants.DISPLAY_EXTERNAL and
                (device_info.is_chassis() or multi_asic.is_multi_asic())):
                external_peers_list_in_cfg_db = get_external_bgp_neighbors_dict(
                    device.current_namespace).keys()
                if not external_peers_list_in_cfg_db:
                    has_bgp_neighbors = False

        if not has_bgp_neighbors:
            vtysh_bgp_json_cmd = "show ip bgp json"
            no_neigh_cmd_output = run_bgp_show_command(vtysh_bgp_json_cmd, ns)
            try:
                no_neigh_cmd_output_json = json.loads(no_neigh_cmd_output)
            except ValueError:
                ctx.fail("bgp summary from bgp container not in json format")

        out_cmd = cmd_output_json[key] if has_bgp_neighbors else no_neigh_cmd_output_json
        process_bgp_summary_json(bgp_summary, out_cmd, device, has_bgp_neighbors=has_bgp_neighbors)

    return bgp_summary


def display_bgp_summary(bgp_summary, af):
    '''
    Display the json output in the format display by FRR

    Args:
        bgp_summary ([dict]): [Bgp summary from all bgp instances in ]
        af: IPV4 or IPV6

    '''
    headers = ["Neighbhor", "V", "AS", "MsgRcvd", "MsgSent", "TblVer",
               "InQ", "OutQ", "Up/Down", "State/PfxRcd", "NeighborName"]

    try:
        click.echo("\nIP{} Unicast Summary:".format(af))
        # display the bgp instance information
        for router_info in bgp_summary['router_info']:
            for k in router_info:
                v = router_info[k]
                instance = "{}: ".format(k) if k != "" else ""
                click.echo(
                    "{}BGP router identifier {}, local AS number {} vrf-id {}" .format(
                        instance, v['router_id'], v['as'], v['vrf']))
                click.echo("BGP table version {}".format(v['tbl_ver']))

        click.echo("RIB entries {}, using {} bytes of memory"
                   .format(bgp_summary['ribCount'], bgp_summary['ribMemory']))
        click.echo(
            "Peers {}, using {} KiB of memory" .format(
                bgp_summary['peerCount'],
                bgp_summary['peerMemory']))
        click.echo("Peer groups {}, using {} bytes of memory" .format(
            bgp_summary['peerGroupCount'], bgp_summary['peerGroupMemory']))
        click.echo("\n")

        click.echo(tabulate(natsorted(bgp_summary['peers']), headers=headers))
        click.echo("\nTotal number of neighbors {}".
                   format(len(bgp_summary['peers'])))
    except KeyError as e:
        ctx = click.get_current_context()
        ctx.fail("{} missing in the bgp_summary".format(e.args[0]))


def process_bgp_summary_json(bgp_summary, cmd_output, device, has_bgp_neighbors=True):
    '''
    This function process the frr output in json format from a bgp
    instance and stores the need values in the a bgp_summary

    '''
    if has_bgp_neighbors:
        static_neighbors, dynamic_neighbors = get_bgp_neighbors_dict(
            device.current_namespace)
    try:
        # add all the router level fields
        if has_bgp_neighbors:
            # when there are bgp neighbors, fill information from the dict
            bgp_summary['peerCount'] = bgp_summary.get(
                'peerCount', 0) + cmd_output['peerCount']
            bgp_summary['peerMemory'] = bgp_summary.get(
                'peerMemory', 0) + cmd_output['peerMemory']
            bgp_summary['ribCount'] = bgp_summary.get(
                'ribCount', 0) + cmd_output['ribCount']
            bgp_summary['ribMemory'] = bgp_summary.get(
                'ribMemory', 0) + cmd_output['ribMemory']
            bgp_summary['peerGroupCount'] = bgp_summary.get(
                'peerGroupCount', 0) + cmd_output['peerGroupCount']
            bgp_summary['peerGroupMemory'] = bgp_summary.get(
                'peerGroupMemory', 0) + cmd_output['peerGroupMemory']
        else:
            # when there are no bgp neighbors, all values are zero
            bgp_summary['peerCount'] = bgp_summary.get(
                'peerCount', 0) + 0
            bgp_summary['peerMemory'] = bgp_summary.get(
                'peerCount', 0) + 0
            bgp_summary['ribCount'] = bgp_summary.get(
                'peerCount', 0) + 0
            bgp_summary['ribMemory'] = bgp_summary.get(
                'peerCount', 0) + 0
            bgp_summary['peerGroupCount'] = bgp_summary.get(
                'peerCount', 0) + 0
            bgp_summary['peerGroupMemory'] = bgp_summary.get(
                'peerCount', 0) + 0

        # store instance level field is seperate dict
        router_info = {}
        router_info['router_id'] = cmd_output['routerId']
        router_info['vrf'] = cmd_output['vrfId']
        router_info['as'] = cmd_output['as'] if has_bgp_neighbors else cmd_output['localAS']
        router_info['tbl_ver'] = cmd_output['tableVersion']
        bgp_summary.setdefault('router_info', []).append(
            {device.current_namespace: router_info})

        # store all the peers in the list
        if has_bgp_neighbors:
            for peer_ip, value in cmd_output['peers'].items():
                peers = []
                # if display option is 'frontend', internal bgp neighbors will not
                # be displayed
                if device.skip_display(constants.BGP_NEIGH_OBJ, peer_ip):
                    continue

                peers.append(peer_ip)
                peers.append(value['version'])
                peers.append(value['remoteAs'])
                peers.append(value['msgRcvd'])
                peers.append(value['msgSent'])
                peers.append(value['tableVersion'])
                peers.append(value['inq'])
                peers.append(value['outq'])
                peers.append(value['peerUptime'])
                if value['state'] == 'Established':
                    peers.append(value['pfxRcd'])
                else:
                    peers.append(value['state'])

                # Get the bgp neighbour name ans store it
                neigh_name = get_bgp_neighbor_ip_to_name(
                    peer_ip, static_neighbors, dynamic_neighbors)
                peers.append(neigh_name)

                bgp_summary.setdefault('peers', []).append(peers)
        else:
            if 'peers' not in bgp_summary:
                bgp_summary['peers'] = []             
    except KeyError as e:
        ctx = click.get_current_context()
        ctx.fail("{} missing in the bgp_summary".format(e.args[0]))
