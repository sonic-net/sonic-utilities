import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate
import ipaddress

#
# 'vnet' command ("show vnet")
#
@click.group(cls=clicommon.AliasedGroup)
def vnet():
    """Show vnet related information"""
    pass


@vnet.command()
@click.argument('args', metavar='[community:string]', required=False)
def advertised_routes(args):
    """Show vnet advertised-routes [community string XXXX:XXXX]"""
    state_db = SonicV2Connector()
    state_db.connect(state_db.STATE_DB)
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)
    community_filter = ''
    profile_filter = 'NO_PROFILE'
    if args and len(args) > 0:
        community_filter = args

    bgp_profile_keys = appl_db.keys(appl_db.APPL_DB, "BGP_PROFILE_TABLE:*")
    bgp_profile_keys = natsorted(bgp_profile_keys) if bgp_profile_keys else []
    profiles = {}
    for  profilekey in bgp_profile_keys:
        val = appl_db.get_all(appl_db.APPL_DB, profilekey)
        if val:
            community_id = val.get('community_id')
            profiles[profilekey.split(':')[1]] = community_id
            if community_filter and community_filter == community_id:
                profile_filter = profilekey.split(':')[1]
                break;

    adv_table_keys = state_db.keys(state_db.STATE_DB, "ADVERTISE_NETWORK_TABLE|*")
    adv_table_keys = natsorted(adv_table_keys) if adv_table_keys else []
    header = ['Prefix', 'Profile', 'Community Id']
    table = []
    for k in adv_table_keys:
        ip = k.split('|')[1]
        val = state_db.get_all(appl_db.STATE_DB, k)
        profile = val.get('profile') if val else 'NA'
        if community_filter:
            if profile == profile_filter:
                r = []
                r.append(ip)
                r.append(profile)
                r.append(community_filter)
                table.append(r)
        else:
            r = []
            r.append(ip)
            r.append(profile)
            if profile in profiles.keys():
                r.append(profiles[profile])
            table.append(r)
    click.echo(tabulate(table, header))


@vnet.command()
@click.argument('vnet_name', required=True)
def name(vnet_name):
    """Show vnet name <vnet name> information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vnet name', 'vxlan tunnel', 'vni', 'peer list']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_entry('VNET', vnet_name)

    def tablelize(vnet_key, vnet_data):
        table = []
        if vnet_data:
            r = []
            r.append(vnet_key)
            r.append(vnet_data.get('vxlan_tunnel'))
            r.append(vnet_data.get('vni'))
            r.append(vnet_data.get('peer_list'))
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_name, vnet_data), header))


@vnet.command()
def brief():
    """Show vnet brief information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vnet name', 'vxlan tunnel', 'vni', 'peer list']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_table('VNET')
    vnet_keys = natsorted(list(vnet_data.keys()))

    def tablelize(vnet_keys, vnet_data):
        table = []
        for k in vnet_keys:
            r = []
            r.append(k)
            r.append(vnet_data[k].get('vxlan_tunnel'))
            r.append(vnet_data[k].get('vni'))
            r.append(vnet_data[k].get('peer_list'))
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_keys, vnet_data), header))


@vnet.command()
@click.argument('vnet_alias', required=False)
def alias(vnet_alias):
    """Show vnet alias to name information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['Alias', 'Name']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_table('VNET')
    vnet_keys = natsorted(list(vnet_data.keys()))

    def tablelize(vnet_keys, vnet_data, vnet_alias):
        table = []
        for k in vnet_keys:
            r = []
            if vnet_alias is not None:
                if vnet_data[k].get('guid') == vnet_alias:
                    r.append(vnet_data[k].get('guid'))
                    r.append(k)
                    table.append(r)
                    return table
                else:
                    continue

            r.append(vnet_data[k].get('guid'))
            r.append(k)
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_keys, vnet_data, vnet_alias), header))


@vnet.command()
def interfaces():
    """Show vnet interfaces information"""
    config_db = ConfigDBConnector()
    config_db.connect()

    header = ['vnet name', 'interfaces']

    # Fetching data from config_db for interfaces
    intfs_data = config_db.get_table("INTERFACE")
    vlan_intfs_data = config_db.get_table("VLAN_INTERFACE")
    sub_intfs_data = config_db.get_table("VLAN_SUB_INTERFACE")
    portchannel_intfs_data = config_db.get_table("PORTCHANNEL_INTERFACE")
    loopback_intfs_data = config_db.get_table("LOOPBACK_INTERFACE")

    vnet_intfs = {}
    for k, v in intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in vlan_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]
    
    for k, v in sub_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in portchannel_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]
    
    for k, v in loopback_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    table = []
    for k, v in vnet_intfs.items():
        r = []
        r.append(k)
        r.append(",".join(natsorted(v)))
        table.append(r)

    click.echo(tabulate(table, header))


@vnet.command()
def neighbors():
    """Show vnet neighbors information"""
    config_db = ConfigDBConnector()
    config_db.connect()

    header = ['<vnet_name>', 'neighbor', 'mac_address', 'interfaces']

    # Fetching data from config_db for interfaces
    intfs_data = config_db.get_table("INTERFACE")
    vlan_intfs_data = config_db.get_table("VLAN_INTERFACE")

    vnet_intfs = {}
    for k, v in intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in vlan_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    # Fetching data from appl_db for neighbors
    nbrs = appl_db.keys(appl_db.APPL_DB, "NEIGH_TABLE:*")
    nbrs_data = {}
    for nbr in nbrs if nbrs else []:
        tbl, intf, ip = nbr.split(":", 2)
        mac = appl_db.get(appl_db.APPL_DB, nbr, 'neigh')
        if intf in nbrs_data:
            nbrs_data[intf].append((ip, mac))
        else:
            nbrs_data[intf] = [(ip, mac)]

    table = []
    for k, v in vnet_intfs.items():
        v = natsorted(v)
        header[0] = k
        table = []
        for intf in v:
            if intf in nbrs_data:
                for ip, mac in nbrs_data[intf]:
                    r = ["", ip, mac, intf]
                    table.append(r)
        click.echo(tabulate(table, header))
        click.echo()

    if not bool(vnet_intfs):
        click.echo(tabulate(table, header))

@vnet.command()
@click.argument('args', metavar='[IPADDRESS]', nargs=1, required=False)
def endpoint(args):
    """Show Vxlan tunnel endpoint status"""
    """Specify IPv4 or IPv6 address for detail"""

    state_db = SonicV2Connector()
    state_db.connect(state_db.STATE_DB)
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)
    filter_by_ip = ''
    if args and len(args) > 0:
        try:
            filter_by_ip = ipaddress.ip_network(args)
        except ValueError:
            # Not ip address just ignore it
            print ("wrong parameter",args)
            return
    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []
    bfd_keys = state_db.keys(state_db.STATE_DB, "BFD_SESSION_TABLE|*")
    if not filter_by_ip:
        header = ['Endpoint', 'Endpoint Monitor', 'prefix count', 'status']
        prefix_count = {}
        monitor_dict = {}
        table = []
        for k in vnet_rt_keys:
            val = appl_db.get_all(appl_db.APPL_DB, k)
            endpoints = val.get('endpoint').split(',') if 'endpoint' in val else []
            if 'endpoint_monitor' in val:
                monitors = val.get('endpoint_monitor').split(',')
            else:
                continue
            for idx, endpoint in enumerate(endpoints):
                monitor_dict[endpoint] = monitors[idx]
                if endpoint not in prefix_count:
                    prefix_count[endpoint] = 0
                prefix_count[endpoint] += 1
        for endpoint in prefix_count:
            r = []
            r.append(endpoint)
            r.append(monitor_dict[endpoint])
            r.append(prefix_count[endpoint])
            bfd_session_key = "BFD_SESSION_TABLE|default|default|" + monitor_dict[endpoint]
            if bfd_session_key in bfd_keys:
                val_state = state_db.get_all(state_db.STATE_DB, bfd_session_key)
                r.append(val_state.get('state'))
            else:
                r.append('Unknown')
            table.append(r)
    else:
        table = []
        header = ['Endpoint', 'Endpoint Monitor', 'prefix', 'status']
        state = 'Unknown'
        prefix = []
        monitor_list = []
        have_status = False
        for k in vnet_rt_keys:
            val = appl_db.get_all(appl_db.APPL_DB, k)
            endpoints = val.get('endpoint').split(',')
            monitors = val.get('endpoint_monitor').split(',')
            for idx, endpoint in enumerate(endpoints):
                if args == endpoint:
                    prefix.append(k.split(":", 2)[2]) 
                    if not have_status:
                        bfd_session_key = "BFD_SESSION_TABLE|default|default|" + monitors[idx]
                        if bfd_session_key in bfd_keys:
                            val_state = state_db.get_all(state_db.STATE_DB, bfd_session_key)
                            state = val_state.get('state')
                            have_status = True
                            monitor_list.append( monitors[idx])
                            break
        if prefix:
            r = []
            r.append(args)
            r.append(monitor_list)
            r.append(prefix)
            r.append(state)
            table.append(r)
    click.echo(tabulate(table, header))


@vnet.group()
def routes():
    """Show vnet routes related information"""
    pass

def pretty_print(table, r, epval, mac_addr, vni, state):
    endpoints = epval.split(',')
    row_width = 3
    max_len = 0
    for ep in endpoints:
        max_len = len(ep) if len(ep) > max_len else max_len
    if max_len > 15:
        row_width = 2
    iter = 0
    while iter < len(endpoints):
        if iter +row_width > len(endpoints):
            r.append(",".join(endpoints[iter:]))
        else:
            r.append(",".join(endpoints[iter:iter + row_width]))
        if iter == 0:
            r.append(mac_addr)
            r.append(vni)
            r.append(state)
        else:
            r.extend(["", "", ""])
        iter += row_width
        table.append(r)
        r = ["",""]

@routes.command()
def all():
    """Show all vnet routes"""
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)
    state_db = SonicV2Connector()
    state_db.connect(state_db.STATE_DB)
    header = ['vnet name', 'prefix', 'nexthop', 'interface']

    # Fetching data from appl_db for VNET ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('nexthop'))
        r.append(val.get('ifname'))
        table.append(r)

    click.echo(tabulate(table, header))

    click.echo()

    header = ['vnet name', 'prefix', 'endpoint', 'mac address', 'vni', 'status']

    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        state_db_key = '|'.join(k.split(":",2))
        val = appl_db.get_all(appl_db.APPL_DB, k)
        val_state = state_db.get_all(state_db.STATE_DB, state_db_key)
        epval = val.get('endpoint')
        if len(epval) < 40:
            r.append(epval)
            r.append(val.get('mac_address'))
            r.append(val.get('vni'))
            if val_state:
                r.append(val_state.get('state'))
            table.append(r)
            continue
        state = val_state.get('state') if val_state else ""
        pretty_print(table, r, epval, val.get('mac_address'), val.get('vni'), state )

    click.echo(tabulate(table, header))


@routes.command()
def tunnel():
    """Show vnet tunnel routes"""
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    header = ['vnet name', 'prefix', 'endpoint', 'mac address', 'vni']

    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('endpoint'))
        r.append(val.get('mac_address'))
        r.append(val.get('vni'))
        table.append(r)

    click.echo(tabulate(table, header))
