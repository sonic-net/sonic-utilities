import click
import utilities_common.cli as clicommon

from jsonpatch import JsonPatchConflict
from .validated_config_db_connector import ValidatedConfigDBConnector
from swsscommon.swsscommon import isInterfaceNameValid, IFACE_NAME_MAX_LEN

ADHOC_VALIDATION = True
#
# 'vxlan' group ('config vxlan ...')
#
@click.group()
def vxlan():
    pass

@vxlan.command('add')
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@click.argument('src_ip', metavar='<src_ip>', required=True)
@clicommon.pass_db
def add_vxlan(db, vxlan_name, src_ip):
    """Add VXLAN"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(src_ip):
            ctx.fail("{} invalid src ip address".format(src_ip))  
        if not isInterfaceNameValid(vxlan_name):
            ctx.fail("'vxlan_name' length should not exceed {} characters".format(IFACE_NAME_MAX_LEN))

    vxlan_keys = db.cfgdb.get_keys('VXLAN_TUNNEL')
    if not vxlan_keys:
      vxlan_count = 0
    else:
      vxlan_count = len(vxlan_keys)

    if(vxlan_count > 0):
        ctx.fail("VTEP already configured.")  

    fvs = {'src_ip': src_ip}
    try:
        config_db.set_entry('VXLAN_TUNNEL', vxlan_name, fvs)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan.command('del')
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@clicommon.pass_db
def del_vxlan(db, vxlan_name):
    """Del VXLAN"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    vxlan_keys = db.cfgdb.get_keys('VXLAN_TUNNEL')
    if vxlan_name not in vxlan_keys:
        ctx.fail("Vxlan tunnel {} does not exist".format(vxlan_name))

    vxlan_keys = db.cfgdb.get_keys('VXLAN_EVPN_NVO')
    if not vxlan_keys:
      vxlan_count = 0
    else:
      vxlan_count = len(vxlan_keys)

    if(vxlan_count > 0):
        ctx.fail("Please delete the EVPN NVO configuration.")  

    vxlan_keys = db.cfgdb.get_keys("VXLAN_TUNNEL_MAP|*")
    if not vxlan_keys:
      vxlan_count = 0
    else:
      vxlan_count = len(vxlan_keys)

    if(vxlan_count > 0):
        ctx.fail("Please delete all VLAN VNI mappings.")  

    vnet_table = db.cfgdb.get_table('VNET')
    vnet_keys = vnet_table.keys()
    for vnet_key in vnet_keys:
        if ('vxlan_tunnel' in vnet_table[vnet_key] and vnet_table[vnet_key]['vxlan_tunnel'] == vxlan_name):
            ctx.fail("Please delete all VNET configuration referencing the tunnel " + vxlan_name)

    try:
        config_db.set_entry('VXLAN_TUNNEL', vxlan_name, None)
    except JsonPatchConflict as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan.group('evpn_nvo')
def vxlan_evpn_nvo():
    pass

@vxlan_evpn_nvo.command('add')
@click.argument('nvo_name', metavar='<nvo_name>', required=True)
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@clicommon.pass_db
def add_vxlan_evpn_nvo(db, nvo_name, vxlan_name):
    """Add NVO"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    vxlan_keys = db.cfgdb.get_keys("VXLAN_EVPN_NVO|*")
    if not vxlan_keys:
      vxlan_count = 0
    else:
      vxlan_count = len(vxlan_keys)

    if(vxlan_count > 0):
        ctx.fail("EVPN NVO already configured")  

    if len(db.cfgdb.get_entry('VXLAN_TUNNEL', vxlan_name)) == 0:
        ctx.fail("VTEP {} not configured".format(vxlan_name))

    fvs = {'source_vtep': vxlan_name}
    try:
        config_db.set_entry('VXLAN_EVPN_NVO', nvo_name, fvs)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan_evpn_nvo.command('del')
@click.argument('nvo_name', metavar='<nvo_name>', required=True)
@clicommon.pass_db
def del_vxlan_evpn_nvo(db, nvo_name):
    """Del NVO"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    vxlan_keys = db.cfgdb.get_keys('VXLAN_TUNNEL_MAP')
    if not vxlan_keys:
      vxlan_count = 0
    else:
      vxlan_count = len(vxlan_keys)

    if(vxlan_count > 0):
        ctx.fail("Please delete all VLAN VNI mappings.")
    try:
        config_db.set_entry('VXLAN_EVPN_NVO', nvo_name, None)
    except JsonPatchConflict as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan.group('map')
def vxlan_map():
    pass

@vxlan_map.command('add')
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@click.argument('vlan', metavar='<vlan_id>', required=True)
@click.argument('vni', metavar='<vni>', required=True)
@clicommon.pass_db
def add_vxlan_map(db, vxlan_name, vlan, vni):
    """Add VLAN-VNI map entry"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if not vlan.isdigit():
        ctx.fail("Invalid vlan {}. Only valid vlan is accepted".format(vni))
    if clicommon.is_vlanid_in_range(int(vlan)) is False:
        ctx.fail(" Invalid Vlan Id , Valid Range : 1 to 4094 ")
    if not vni.isdigit():
        ctx.fail("Invalid VNI {}. Only valid VNI is accepted".format(vni))
    if clicommon.vni_id_is_valid(int(vni)) is False:
        ctx.fail("Invalid VNI {}. Valid range [1 to 16777215].".format(vni))

    vlan_name = "Vlan" + vlan

    if len(db.cfgdb.get_entry('VXLAN_TUNNEL', vxlan_name)) == 0:
        ctx.fail("VTEP {} not configured".format(vxlan_name))

    if len(db.cfgdb.get_entry('VLAN', vlan_name)) == 0:
        ctx.fail("{} not configured".format(vlan_name))

    vxlan_table = db.cfgdb.get_table('VXLAN_TUNNEL_MAP')
    vxlan_keys = vxlan_table.keys()
    if vxlan_keys is not None:
      for key in vxlan_keys:
        if (vxlan_table[key]['vlan'] == vlan_name):
           ctx.fail(" Vlan Id already mapped ")
        if (vxlan_table[key]['vni'] == vni):
           ctx.fail(" VNI Id already mapped ")

    fvs = {'vni': vni,
           'vlan' : vlan_name}
    mapname = vxlan_name + '|' + 'map_' + vni + '_' + vlan_name
    try:
        config_db.set_entry('VXLAN_TUNNEL_MAP', mapname, fvs)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan_map.command('del')
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@click.argument('vlan', metavar='<vlan_id>', required=True)
@click.argument('vni', metavar='<vni>', required=True)
@clicommon.pass_db
def del_vxlan_map(db, vxlan_name, vlan, vni):
    """Del VLAN-VNI map entry"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if not vlan.isdigit():
        ctx.fail("Invalid vlan {}. Only valid vlan is accepted".format(vni))
    if clicommon.is_vlanid_in_range(int(vlan)) is False:
        ctx.fail(" Invalid Vlan Id , Valid Range : 1 to 4094 ")
    if not vni.isdigit():
        ctx.fail("Invalid VNI {}. Only valid VNI is accepted".format(vni))
    if clicommon.vni_id_is_valid(int(vni)) is False:
        ctx.fail("Invalid VNI {}. Valid range [1 to 16777215].".format(vni))

    if len(db.cfgdb.get_entry('VXLAN_TUNNEL', vxlan_name)) == 0:
        ctx.fail("VTEP {} not configured".format(vxlan_name))
    found = 0
    vrf_table = db.cfgdb.get_table('VRF')
    vrf_keys = vrf_table.keys()
    if vrf_keys is not None:
      for vrf_key in vrf_keys:
        if ('vni' in vrf_table[vrf_key] and vrf_table[vrf_key]['vni'] == vni):
           found = 1
           break

    if (found == 1):
        ctx.fail("VNI mapped to vrf {}, Please remove VRF VNI mapping".format(vrf_key))

    mapname = vxlan_name + '|' + 'map_' + vni + '_' + vlan
    db.cfgdb.set_entry('VXLAN_TUNNEL_MAP', mapname, None)
    mapname = vxlan_name + '|' + 'map_' + vni + '_Vlan' + vlan
    try:
        config_db.set_entry('VXLAN_TUNNEL_MAP', mapname, None)
    except JsonPatchConflict as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan.group('map_range')
def vxlan_map_range():
    pass

@vxlan_map_range.command('add')
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@click.argument('vlan_start', metavar='<vlan_start>', required=True, type=int)
@click.argument('vlan_end', metavar='<vlan_end>', required=True, type=int)
@click.argument('vni_start', metavar='<vni_start>', required=True, type=int)
@clicommon.pass_db
def add_vxlan_map_range(db, vxlan_name, vlan_start, vlan_end, vni_start):
    """Add Range of vlan-vni mappings"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()
    if clicommon.is_vlanid_in_range(vlan_start) is False:
        ctx.fail(" Invalid Vlan Id , Valid Range : 1 to 4094 ")
    if clicommon.is_vlanid_in_range(vlan_end) is False:
        ctx.fail(" Invalid Vlan Id , Valid Range : 1 to 4094 ")
    if (vlan_start > vlan_end):
       ctx.fail("vlan_end should be greater or equal to vlan_start")
    if clicommon.vni_id_is_valid(vni_start) is False:
        ctx.fail("Invalid VNI {}. Valid range [1 to 16777215].".format(vni_start))
    if clicommon.vni_id_is_valid(vni_start+vlan_end-vlan_start) is False:
        ctx.fail("Invalid VNI End {}. Valid range [1 to 16777215].".format(vni_start))

    if len(db.cfgdb.get_entry('VXLAN_TUNNEL', vxlan_name)) == 0:
        ctx.fail("VTEP {} not configured".format(vxlan_name))
    vlan_end = vlan_end + 1
    vxlan_table = db.cfgdb.get_table('VXLAN_TUNNEL_MAP')
    vxlan_keys = vxlan_table.keys()

    for vid in range (vlan_start, vlan_end):
       vlan_name = 'Vlan{}'.format(vid)
       vnid = vni_start+vid-vlan_start
       vni_name = '{}'.format(vnid)
       match_found = 'no'
       if len(db.cfgdb.get_entry('VLAN', vlan_name)) == 0:
         click.echo("{} not configured".format(vlan_name))
         continue
       if vxlan_keys is not None:
          for key in vxlan_keys:
            if (vxlan_table[key]['vlan'] == vlan_name):
              print(vlan_name + " already mapped")
              match_found = 'yes'
              break
            if (vxlan_table[key]['vni'] == vni_name):
              print("VNI:" + vni_name + " already mapped ")
              match_found = 'yes'
              break
       if (match_found == 'yes'):
         continue
       fvs = {'vni': vni_name,
              'vlan' : vlan_name}
       mapname = vxlan_name + '|' + 'map_' + vni_name + '_' + vlan_name
       try:
           config_db.set_entry('VXLAN_TUNNEL_MAP', mapname, fvs)
       except ValueError as e:
           ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vxlan_map_range.command('del')
@click.argument('vxlan_name', metavar='<vxlan_name>', required=True)
@click.argument('vlan_start', metavar='<vlan_start>', required=True, type=int)
@click.argument('vlan_end', metavar='<vlan_end>', required=True, type=int)
@click.argument('vni_start', metavar='<vni_start>', required=True, type=int)
@clicommon.pass_db
def del_vxlan_map_range(db, vxlan_name, vlan_start, vlan_end, vni_start):
    """Del Range of vlan-vni mappings"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    if clicommon.is_vlanid_in_range(vlan_start) is False:
        ctx.fail(" Invalid Vlan Id , Valid Range : 1 to 4094 ")
    if clicommon.is_vlanid_in_range(vlan_end) is False:
        ctx.fail(" Invalid Vlan Id , Valid Range : 1 to 4094 ")
    if (vlan_start > vlan_end):
       ctx.fail("vlan_end should be greater or equal to vlan_start")
    if clicommon.vni_id_is_valid(vni_start) is False:
        ctx.fail("Invalid VNI {}. Valid range [1 to 16777215].".format(vni_start))
    if clicommon.vni_id_is_valid(vni_start+vlan_end-vlan_start) is False:
        ctx.fail("Invalid VNI End {}. Valid range [1 to 16777215].".format(vni_start))

    if len(db.cfgdb.get_entry('VXLAN_TUNNEL', vxlan_name)) == 0:
        ctx.fail("VTEP {} not configured".format(vxlan_name))

    vlan_end = vlan_end + 1
    for vid in range (vlan_start, vlan_end):
       vlan_name = 'Vlan{}'.format(vid)
       vnid = vni_start+vid-vlan_start
       vni_name = '{}'.format(vnid)
       if clicommon.is_vni_vrf_mapped(db, vni_name) is False:
           print("Skipping Vlan {} VNI {} mapped delete. ".format(vlan_name, vni_name))
           continue

       mapname = vxlan_name + '|' + 'map_' + vni_name + '_' + vlan_name
       try:
           config_db.set_entry('VXLAN_TUNNEL_MAP', mapname, None)
       except JsonPatchConflict as e:
           ctx.fail("Invalid ConfigDB. Error: {}".format(e))
