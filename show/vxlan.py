import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate

#
# 'vxlan' command ("show vxlan")
#
@click.group(cls=clicommon.AliasedGroup)
def vxlan():
    """Show vxlan related information"""
    pass

@vxlan.command()
@click.argument('vxlan_name', required=True)
def name(vxlan_name):
    """Show vxlan name <vxlan_name> information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vxlan tunnel name', 'source ip', 'destination ip', 'tunnel map name', 'tunnel map mapping(vni -> vlan)']

    # Fetching data from config_db for VXLAN TUNNEL
    vxlan_data = config_db.get_entry('VXLAN_TUNNEL', vxlan_name)

    table = []
    if vxlan_data:
        r = []
        r.append(vxlan_name)
        r.append(vxlan_data.get('src_ip'))
        r.append(vxlan_data.get('dst_ip'))
        vxlan_map_keys = config_db.keys(config_db.CONFIG_DB,
                                        'VXLAN_TUNNEL_MAP{}{}{}*'.format(config_db.KEY_SEPARATOR, vxlan_name, config_db.KEY_SEPARATOR))
        if vxlan_map_keys:
            for key in natsorted(vxlan_map_keys):
                vxlan_map_mapping = config_db.get_all(config_db.CONFIG_DB, key)
                r.append(key.split(config_db.KEY_SEPARATOR, 2)[2])
                r.append("{} -> {}".format(vxlan_map_mapping.get('vni'), vxlan_map_mapping.get('vlan')))
                table.append(r)
                r = []
                r.append(' ')
                r.append(' ')
                r.append(' ')
        else:
            table.append(r)

    click.echo(tabulate(table, header))

@vxlan.command()
def tunnel():
    """Show vxlan tunnel information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vxlan tunnel name', 'source ip', 'destination ip', 'tunnel map name', 'tunnel map mapping(vni -> vlan)']

    # Fetching data from config_db for VXLAN TUNNEL
    vxlan_data = config_db.get_table('VXLAN_TUNNEL')
    vxlan_keys = natsorted(list(vxlan_data.keys()))

    table = []
    for k in vxlan_keys:
        r = []
        r.append(k)
        r.append(vxlan_data[k].get('src_ip'))
        r.append(vxlan_data[k].get('dst_ip'))
        vxlan_map_keys = config_db.keys(config_db.CONFIG_DB,
                                        'VXLAN_TUNNEL_MAP{}{}{}*'.format(config_db.KEY_SEPARATOR, k, config_db.KEY_SEPARATOR))
        if vxlan_map_keys:
            for key in natsorted(vxlan_map_keys):
                vxlan_map_mapping = config_db.get_all(config_db.CONFIG_DB, key)
                r.append(key.split(config_db.KEY_SEPARATOR, 2)[2])
                r.append("{} -> {}".format(vxlan_map_mapping.get('vni'), vxlan_map_mapping.get('vlan')))
                table.append(r)
                r = []
                r.append(' ')
                r.append(' ')
                r.append(' ')
        else:
            table.append(r)

    click.echo(tabulate(table, header))

@vxlan.command()
def interface():
    """Show VXLAN VTEP Information"""

    config_db = ConfigDBConnector()
    config_db.connect()

    # Fetching VTEP keys from config DB
    click.secho('VTEP Information:\n', bold=True, underline=True)
    vxlan_table = config_db.get_table('VXLAN_TUNNEL')
    vxlan_keys = vxlan_table.keys()
    vtep_sip = '0.0.0.0'
    if vxlan_keys is not None:
      for key in natsorted(vxlan_keys):
          key1 = key.split('|',1)
          vtepname = key1.pop();
          if 'src_ip' in vxlan_table[key]:
            vtep_sip = vxlan_table[key]['src_ip']
          if vtep_sip != '0.0.0.0':
             output = '\tVTEP Name : ' + vtepname + ', SIP  : ' + vxlan_table[key]['src_ip']
          else:
             output = '\tVTEP Name : ' + vtepname

          click.echo(output)

    if vtep_sip != '0.0.0.0':
       vxlan_table = config_db.get_table('VXLAN_EVPN_NVO')
       vxlan_keys = vxlan_table.keys()
       if vxlan_keys is not None:
         for key in natsorted(vxlan_keys):
             key1 = key.split('|',1)
             vtepname = key1.pop();
             output = '\tNVO Name  : ' + vtepname + ',  VTEP : ' + vxlan_table[key]['source_vtep']
             click.echo(output)

       vxlan_keys = config_db.keys('CONFIG_DB', "LOOPBACK_INTERFACE|*")
       loopback = 'Not Configured'
       if vxlan_keys is not None:
         for key in natsorted(vxlan_keys):
             key1 = key.split('|',2)
             if len(key1) == 3 and key1[2] == vtep_sip+'/32':
                loopback = key1[1]
                break
         output = '\tSource interface  : ' + loopback
         if vtep_sip != '0.0.0.0':
            click.echo(output)

@vxlan.command()
@click.argument('count', required=False)
def vlanvnimap(count):
    """Show VLAN VNI Mapping Information"""

    header = ['VLAN', 'VNI']
    body = []

    config_db = ConfigDBConnector()
    config_db.connect()

    if count is not None:
      vxlan_keys = config_db.keys('CONFIG_DB', "VXLAN_TUNNEL_MAP|*")

      if not vxlan_keys:
        vxlan_count = 0
      else:
        vxlan_count = len(vxlan_keys)

      output = 'Total count : '
      output += ('%s\n' % (str(vxlan_count)))
      click.echo(output)
    else:
       vxlan_table = config_db.get_table('VXLAN_TUNNEL_MAP')
       vxlan_keys = vxlan_table.keys()
       num=0
       if vxlan_keys is not None:
         for key in natsorted(vxlan_keys):
             body.append([vxlan_table[key]['vlan'], vxlan_table[key]['vni']])
             num += 1
       click.echo(tabulate(body, header, tablefmt="grid"))
       output = 'Total count : '
       output += ('%s\n' % (str(num)))
       click.echo(output)

@vxlan.command()
def vrfvnimap():
    """Show VRF VNI Mapping Information"""

    header = ['VRF', 'VNI']
    body = []

    config_db = ConfigDBConnector()
    config_db.connect()

    vrf_table = config_db.get_table('VRF')
    vrf_keys = vrf_table.keys()
    num=0
    if vrf_keys is not None:
      for key in natsorted(vrf_keys):
          if ('vni' in vrf_table[key]):
              body.append([key, vrf_table[key]['vni']])
              num += 1
    click.echo(tabulate(body, header, tablefmt="grid"))
    output = 'Total count : '
    output += ('%s\n' % (str(num)))
    click.echo(output)

@vxlan.command()
@click.argument('count', required=False)
def remotevtep(count):
    """Show All Remote VTEP Information"""

    if (count is not None) and (count != 'count'):
        click.echo("Unacceptable argument {}".format(count))
        return

    header = ['SIP', 'DIP', 'Creation Source', 'OperStatus']
    body = []
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.STATE_DB)

    vxlan_keys = db.keys(db.STATE_DB, 'VXLAN_TUNNEL_TABLE|*')

    if vxlan_keys is not None:
        vxlan_count = len(vxlan_keys)
    else:
        vxlan_count = 0

    if (count is not None):
        output = 'Total count : '
        output += ('%s\n' % (str(vxlan_count)))
        click.echo(output)
    else:
        num = 0
        if vxlan_keys is not None:
           for key in natsorted(vxlan_keys):
                vxlan_table = db.get_all(db.STATE_DB, key);
                if vxlan_table is None:
                   continue
                body.append([vxlan_table['src_ip'], vxlan_table['dst_ip'], vxlan_table['tnl_src'], 'oper_' + vxlan_table['operstatus']])
                num += 1
        click.echo(tabulate(body, header, tablefmt="grid"))
        output = 'Total count : '
        output += ('%s\n' % (str(num)))
        click.echo(output)

@vxlan.command()
@click.argument('remote_vtep_ip', required=True)
@click.argument('count', required=False)
def remotevni(remote_vtep_ip, count):
    """Show Vlans extended to the remote VTEP"""

    if (remote_vtep_ip != 'all') and (clicommon.is_ipaddress(remote_vtep_ip ) is False):
        click.echo("Remote VTEP IP {} invalid format".format(remote_vtep_ip))
        return

    header = ['VLAN', 'RemoteVTEP', 'VNI']
    body = []
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.APPL_DB)

    if(remote_vtep_ip == 'all'):
      vxlan_keys = db.keys(db.APPL_DB, 'VXLAN_REMOTE_VNI_TABLE:*')
    else:
      vxlan_keys = db.keys(db.APPL_DB, 'VXLAN_REMOTE_VNI_TABLE:*' + remote_vtep_ip + '*')

    if count is not None:
      if not vxlan_keys:
        vxlan_count = 0
      else:
        vxlan_count = len(vxlan_keys)

      output = 'Total count : '
      output += ('%s\n' % (str(vxlan_count)))
      click.echo(output)
    else:
      num = 0
      if vxlan_keys is not None:
        for key in natsorted(vxlan_keys):
            key1 = key.split(':', 2)
            rmtip = key1[2];
            #if remote_vtep_ip != 'all' and rmtip != remote_vtep_ip:
            #   continue
            vxlan_table = db.get_all(db.APPL_DB, key);
            if vxlan_table is None:
             continue
            body.append([key1[1], rmtip, vxlan_table['vni']])
            num += 1
      click.echo(tabulate(body, header, tablefmt="grid"))
      output = 'Total count : '
      output += ('%s\n' % (str(num)))
      click.echo(output)

@vxlan.command()
def l2nexthopgroup():
    header = ['NHG', 'Tunnels', 'LocalMembers']
    body = []
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.APPL_DB)
    nhg_keys = db.keys(db.APPL_DB, 'L2_NEXTHOP_GROUP_TABLE:*')
    if nhg_keys is not None:
        for key in natsorted(nhg_keys):
            tunnel = str()
            key1 = key.split(':')
            nhg = key1.pop()
            nhg_table = db.get_all(db.APPL_DB, key)
            if not nhg_table:
                continue
            r_vtep = nhg_table.get('remote_vtep')
            if r_vtep is None:
                nh_group = nhg_table.get('nexthop_group')
                if nh_group is not None:
                    groups = nh_group.split(",")
                    for g in groups:
                        tunnel += g.split(":")[1] + ","
            if_name = nhg_table.get('ifname')
            if len(tunnel):
                if_name = tunnel[:-1]
            body.append([nhg, r_vtep, if_name])
        click.echo(tabulate(body, header, tablefmt="grid"))

@vxlan.command()
@click.argument('remote_vtep_ip', required=True)
@click.argument('count', required=False)
def remotemac(remote_vtep_ip, count):
    """Show MACs pointing to the remote VTEP"""
    if (remote_vtep_ip != 'all') and (clicommon.is_ipaddress(remote_vtep_ip ) is False):
        click.echo("Remote VTEP IP {} invalid format".format(remote_vtep_ip))
        return

    header = ['VLAN', 'MAC', 'RemoteTunnel', 'VNI', 'Type']
    body = []
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.APPL_DB)

    vxlan_keys = db.keys(db.APPL_DB, 'VXLAN_FDB_TABLE:*')
    if ((count is not None) and (remote_vtep_ip == 'all')):
      if not vxlan_keys:
        vxlan_count = 0
      else:
        vxlan_count = len(vxlan_keys)

      output = 'Total count : '
      output += ('%s\n' % (str(vxlan_count)))
      click.echo(output)
    else:
      num = 0
      if vxlan_keys is not None:
        for key in natsorted(vxlan_keys):
            tunnel = list()
            key1 = key.split(':',2)
            mac = key1.pop();
            vlan = key1.pop();
            vxlan_table = db.get_all(db.APPL_DB, key);
            if vxlan_table is None:
                continue
            nh_group_id = vxlan_table.get('nexthop_group')
            if nh_group_id is not None:
                l2_nh_grp_tbl = db.get_all(db.APPL_DB, nh_group_id)
                if l2_nh_grp_tbl is not None:
                    nh_group = l2_nh_grp_tbl.get('nexthop_group')
                    if nh_group:
                        groups = nh_group.split(",")
                        for g in groups:
                            entry = db.get_all(db.APPL_DB, g)
                            rmtip = entry.get('remote_vtep')
                            if rmtip is not None:
                                tunnel.append(rmtip)
                    else:
                        rmtip = l2_nh_grp_tbl.get('remote_vtep')
            else:
                rmtip = vxlan_table.get('remote_vtep')
            if len(tunnel):
                rmtip = ""
                for t in tunnel:
                    rmtip+=t+"\n"
            if remote_vtep_ip != 'all' and rmtip != remote_vtep_ip or rmtip is None:
                continue
            if count is None:
                body.append([vlan, mac, rmtip, vxlan_table['vni'], vxlan_table['type']])
            num += 1
      if count is None:
         click.echo(tabulate(body, header, tablefmt="grid"))
      output = 'Total count : '
      output += ('%s\n' % (str(num)))
      click.echo(output)
@vxlan.command()
@click.argument('tunnel', required=False)
@click.option('-p', '--period')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(tunnel, period, verbose):
    """Show VxLAN counters"""

    cmd = ['tunnelstat', '-T', 'vxlan']
    if period is not None:
        cmd += ['-p', str(period)]
    if tunnel is not None:
        cmd += ['-i', str(tunnel)]

    clicommon.run_command(cmd, display_cmd=verbose)

