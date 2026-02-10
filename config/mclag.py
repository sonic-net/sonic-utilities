
import click
from swsscommon.swsscommon import ConfigDBConnector
from .validated_config_db_connector import ValidatedConfigDBConnector
import ipaddress
from jsonpatch import JsonPatchConflict
from jsonpointer import JsonPointerException

ADHOC_VALIDATION = False
CFG_PORTCHANNEL_PREFIX = "PortChannel"
CFG_PORTCHANNEL_PREFIX_LEN = 11
CFG_PORTCHANNEL_MAX_VAL = 9999
CFG_PORTCHANNEL_NAME_TOTAL_LEN_MAX = 15
CFG_PORTCHANNEL_NO="<0-9999>"

def mclag_domain_id_valid(domain_id):
    """Check if the domain id is in acceptable range (between 1 and 4095)
    """

    if domain_id<1 or domain_id>4095:
        return False

    return True

def mclag_ka_session_dep_check(ka, session_tmout):
    """Check if the MCLAG Keepalive timer and session timeout values are multiples of each other and keepalive is < session timeout value 
    """
    if not session_tmout >= ( 3 * ka):
        return False, "MCLAG Keepalive:{} Session_timeout:{} values not satisfying session_timeout >= (3 * KA) ".format(ka, session_tmout)

    if session_tmout % ka:
        return False, "MCLAG keepalive:{} Session_timeout:{} Values not satisfying session_timeout should be a multiple of KA".format(ka, session_tmout)

    return True, ""


def mclag_ka_interval_valid(ka):
    """Check if the MCLAG Keepalive timer is in acceptable range (between 1 and 60)
    """
    if ka < 1 or ka > 60:
        return False, "Keepalive %s not in valid range[1-60]" % ka 
    return True, "" 

def mclag_session_timeout_valid(session_tmout):
    """Check if the MCLAG session timeout in valid range (between 3 and 3600)
    """
    if session_tmout < 3 or session_tmout > 3600:
        return False, "Session timeout %s not in valid range[3-3600]" % session_tmout
    return True, ""


def is_portchannel_name_valid(portchannel_name):
    """Port channel name validation
    """
    # Return True if Portchannel name is PortChannelXXXX (XXXX can be 0-9999)
    if portchannel_name[:CFG_PORTCHANNEL_PREFIX_LEN] != CFG_PORTCHANNEL_PREFIX :
        return False
    if (portchannel_name[CFG_PORTCHANNEL_PREFIX_LEN:].isdigit() is False or
          int(portchannel_name[CFG_PORTCHANNEL_PREFIX_LEN:]) > CFG_PORTCHANNEL_MAX_VAL) :
        return False
    if len(portchannel_name) > CFG_PORTCHANNEL_NAME_TOTAL_LEN_MAX:
        return False
    return True

def is_ipv4_addr_valid(addr):
    v4_invalid_list = [ipaddress.IPv4Address(str('0.0.0.0')), ipaddress.IPv4Address(str('255.255.255.255'))]
    try:
        ip = ipaddress.ip_address(str(addr))
        if (ip.version == 4):
            if (ip.is_reserved):
                click.echo ("{} Not Valid, Reason: IPv4 reserved address range.".format(addr))
                return False
            elif (ip.is_multicast):
                click.echo ("{} Not Valid, Reason: IPv4 Multicast address range.".format(addr))
                return False
            elif (ip in v4_invalid_list):
                click.echo ("{} Not Valid.".format(addr))
                return False
            else:
                return True

        else:
            click.echo ("{} Not Valid, Reason: Not an IPv4 address".format(addr))
            return False

    except ValueError:
        return False



def check_if_interface_is_valid(db, interface_name):
    from .main import interface_name_is_valid
    return interface_name_is_valid(db,interface_name)

def get_intf_vrf_bind_unique_ip(db, interface_name, interface_type):
    intfvrf = db.get_table(interface_type)
    if interface_name in intfvrf:
        if 'vrf_name' in intfvrf[interface_name]:
            return intfvrf[interface_name]['vrf_name']
        else:
            return ""
    else:
        return ""


######
#
# 'mclag' group ('config mclag ...')
#
@click.group()
@click.pass_context
def mclag(ctx):
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}


#mclag domain add 
@mclag.command('add')
@click.argument('domain_id', metavar='<domain_id>', required=True, type=int)
@click.argument('source_ip_addr', metavar='<source_ip_addr>', required=True)
@click.argument('peer_ip_addr', metavar='<peer_ip_addr>', required=True)
@click.argument('peer_ifname', metavar='<peer_ifname>', required=False)
@click.pass_context
def add_mclag_domain(ctx, domain_id, source_ip_addr, peer_ip_addr, peer_ifname):
    """Add MCLAG Domain"""
    if ADHOC_VALIDATION:
        if not mclag_domain_id_valid(domain_id):
            ctx.fail("{} invalid domain ID, valid range is 1 to 4095".format(domain_id))  
        if not is_ipv4_addr_valid(source_ip_addr):
            ctx.fail("{} invalid local ip address".format(source_ip_addr))
        if not is_ipv4_addr_valid(peer_ip_addr):
            ctx.fail("{} invalid peer ip address".format(peer_ip_addr))

    db = ValidatedConfigDBConnector(ctx.obj['db'])
    fvs = {}
    fvs['source_ip'] = str(source_ip_addr)
    fvs['peer_ip'] = str(peer_ip_addr)
    if ADHOC_VALIDATION:
        if peer_ifname is not None:
            if (peer_ifname.startswith("Ethernet") is False) and (peer_ifname.startswith("PortChannel") is False):
                ctx.fail("peer interface is invalid, should be Ethernet interface or portChannel !!")
            if (peer_ifname.startswith("Ethernet") is True) and (check_if_interface_is_valid(db, peer_ifname) is False):
                ctx.fail("peer Ethernet interface name is invalid. it is not present in port table of configDb!!")
            if (peer_ifname.startswith("PortChannel")) and (is_portchannel_name_valid(peer_ifname) is False):
                ctx.fail("peer PortChannel interface name is invalid !!")
    fvs['peer_link'] = str(peer_ifname)
    mclag_domain_keys = db.get_table('MCLAG_DOMAIN').keys()
    if len(mclag_domain_keys) == 0:
        try:
            db.set_entry('MCLAG_DOMAIN', domain_id, fvs)
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        domain_id = str(domain_id)
        if domain_id in mclag_domain_keys:
            try:
                db.mod_entry('MCLAG_DOMAIN', domain_id, fvs)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        else:
            ctx.fail("only one mclag Domain can be configured. Already one domain {} configured ".format(list(mclag_domain_keys)[0]))


#mclag domain delete
#MCLAG Domain del involves deletion of associated MCLAG Ifaces also
@mclag.command('del')
@click.argument('domain_id', metavar='<domain_id>', required=True, type=int)
@click.pass_context
def del_mclag_domain(ctx, domain_id):
    """Delete MCLAG Domain"""
    
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    
    if ADHOC_VALIDATION:
        if not mclag_domain_id_valid(domain_id):
            ctx.fail("{} invalid domain ID, valid range is 1 to 4095".format(domain_id))  
        
        entry = db.get_entry('MCLAG_DOMAIN', domain_id)
        if entry is None:
            ctx.fail("MCLAG Domain {} not configured ".format(domain_id))  

    click.echo("MCLAG Domain delete takes care of deleting all associated MCLAG Interfaces")

    #get all MCLAG Interface associated with this domain and delete
    interface_table_keys = db.get_table('MCLAG_INTERFACE').keys()

    #delete associated mclag interfaces
    for iface_domain_id, iface_name in interface_table_keys:
        if (int(iface_domain_id) == domain_id):
            try:
                db.set_entry('MCLAG_INTERFACE', (iface_domain_id, iface_name), None )
            except (JsonPointerException, JsonPatchConflict) as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    
    #delete mclag domain
    try:
        db.set_entry('MCLAG_DOMAIN', domain_id, None)
    except (JsonPointerException, JsonPatchConflict) as e:
        ctx.fail("Invalid ConfigDB. Error: MCLAG_DOMAIN {} failed to be deleted".format(domain_id))


#keepalive timeout config
@mclag.command('keepalive-interval')
@click.argument('domain_id', metavar='<domain_id>', required=True)
@click.argument('time_in_secs', metavar='<time_in_secs>', required=True, type=int)
@click.pass_context
def config_mclag_keepalive_timer(ctx, domain_id, time_in_secs):
    """Configure MCLAG Keepalive timer value in secs"""
    db = ctx.obj['db']

    entry = db.get_entry('MCLAG_DOMAIN', domain_id)
    if len(entry) == 0:
        ctx.fail("MCLAG Domain " + domain_id + " not configured, configure mclag domain first")

    status, error_info = mclag_ka_interval_valid(time_in_secs)
    if status is not True:
        ctx.fail(error_info)

    session_timeout_value = entry.get('session_timeout')
    
    if session_timeout_value is None:
        # assign default value
        int_sess_tmout = 15 
    else:
        int_sess_tmout = int(session_timeout_value)

    status, error_info = mclag_ka_session_dep_check(time_in_secs, int_sess_tmout) 
    if status is not True:
        ctx.fail(error_info)
   
    fvs = {}
    fvs['keepalive_interval'] = str(time_in_secs)
    db.mod_entry('MCLAG_DOMAIN', domain_id, fvs)


#session timeout config
@mclag.command('session-timeout')
@click.argument('domain_id', metavar='<domain_id>', required=True)
@click.argument('time_in_secs', metavar='<time_in_secs>', required=True, type=int)
@click.pass_context
def config_mclag_session_timeout(ctx, domain_id, time_in_secs):
    """Configure MCLAG Session timeout value in secs"""
    db = ctx.obj['db']
    entry = db.get_entry('MCLAG_DOMAIN', domain_id)
    if len(entry) == 0:
        ctx.fail("MCLAG Domain " + domain_id + " not configured, configure mclag domain first")

    status, error_info = mclag_session_timeout_valid(time_in_secs)
    if status is not True:
        ctx.fail(error_info)

    ka = entry.get('keepalive_interval')
    if ka is None:
        # assign default value
        int_ka = 1 
    else:
        int_ka = int(ka)

    status, error_info = mclag_ka_session_dep_check(int_ka, time_in_secs) 
    if status is not True:
        ctx.fail(error_info)
   
    fvs = {}
    fvs['session_timeout'] = str(time_in_secs)
    db.mod_entry('MCLAG_DOMAIN', domain_id, fvs)


#mclag interface config
@mclag.group('member')
@click.pass_context
def mclag_member(ctx):
    pass

@mclag_member.command('add')
@click.argument('domain_id', metavar='<domain_id>', required=True)
@click.argument('portchannel_names', metavar='<portchannel_names>', required=True)
@click.pass_context
def add_mclag_member(ctx, domain_id, portchannel_names):
    """Add member MCLAG interfaces from MCLAG Domain"""
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        entry = db.get_entry('MCLAG_DOMAIN', domain_id)
        if len(entry) == 0:
            ctx.fail("MCLAG Domain " + domain_id + " not configured, configure mclag domain first")

    portchannel_list = portchannel_names.split(",")
    for portchannel_name in portchannel_list:
        if ADHOC_VALIDATION:
            if is_portchannel_name_valid(portchannel_name) != True:
                ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'" .format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))
        try:
            db.set_entry('MCLAG_INTERFACE', (domain_id, portchannel_name), {'if_type':"PortChannel"} )
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@mclag_member.command('del')
@click.argument('domain_id', metavar='<domain_id>', required=True)
@click.argument('portchannel_names', metavar='<portchannel_names>', required=True)
@click.pass_context
def del_mclag_member(ctx, domain_id, portchannel_names):
    """Delete member MCLAG interfaces from MCLAG Domain"""
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    #split comma separated portchannel names
    portchannel_list = portchannel_names.split(",")
    for portchannel_name in portchannel_list:
        if ADHOC_VALIDATION:
            if is_portchannel_name_valid(portchannel_name) != True:
                ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'" .format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))
        try:
            db.set_entry('MCLAG_INTERFACE', (domain_id, portchannel_name), None )
        except (JsonPatchConflict, JsonPointerException) as e:
            ctx.fail("Failed to delete mclag member {} from mclag domain {}".format(portchannel_name, domain_id))

#mclag unique ip config
@mclag.group('unique-ip')
@click.pass_context
def mclag_unique_ip(ctx):
    """Configure Unique IP on MCLAG Vlan interface"""
    pass

@mclag_unique_ip.command('add')
@click.argument('interface_names', metavar='<interface_names>', required=True)
@click.pass_context
def add_mclag_unique_ip(ctx, interface_names):
    """Add Unique IP on MCLAG Vlan interface"""
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    mclag_domain_keys = db.get_table('MCLAG_DOMAIN').keys()
    if len(mclag_domain_keys) == 0:
        ctx.fail("MCLAG not configured. MCLAG should be configured.")

    #split comma separated interface names
    interface_list = interface_names.split(",")
    for interface_name in interface_list:
        if not interface_name.startswith("Vlan"):
            ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'" .format(interface_name, "Vlan", "vlan id"))
        #VRF should be configured after unique IP configuration
        intf_vrf = get_intf_vrf_bind_unique_ip(db, interface_name, "VLAN_INTERFACE")
        if intf_vrf:
            ctx.fail("%s is configured with Non default VRF, remove the VRF configuration and reconfigure after enabling unique IP configuration."%(str(interface_name)))

        #IP should be configured after unique IP configuration
        for k,v in db.get_table('VLAN_INTERFACE').items():
            if type(k) == tuple:
                (intf_name, ip) = k
                if intf_name == interface_name and ip != 0:
                    ctx.fail("%s is configured with IP %s, remove the IP configuration and reconfigure after enabling unique IP configuration."%(str(intf_name), str(ip)))
        try:
            db.set_entry('MCLAG_UNIQUE_IP', (interface_name), {'unique_ip':"enable"} )
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@mclag_unique_ip.command('del')
@click.argument('interface_names', metavar='<interface_names>', required=True)
@click.pass_context
def del_mclag_unique_ip(ctx, interface_names):
    """Delete Unique IP from MCLAG Vlan interface"""
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    #split comma separated interface names
    interface_list = interface_names.split(",")
    for interface_name in interface_list:
        if not interface_name.startswith("Vlan"):
            ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'" .format(interface_name, "Vlan", "vlan id"))
        #VRF should be configured after removing unique IP configuration
        intf_vrf = get_intf_vrf_bind_unique_ip(db, interface_name, "VLAN_INTERFACE")
        if intf_vrf:
            ctx.fail("%s is configured with Non default VRF, remove the VRF configuration and reconfigure after disabling unique IP configuration."%(str(interface_name)))
        #IP should be configured after removing unique IP configuration
        for k,v in db.get_table('VLAN_INTERFACE').items():
            if type(k) == tuple:
                (intf_name, ip) = k
                if intf_name == interface_name and ip != 0:
                    ctx.fail("%s is configured with IP %s, remove the IP configuration and reconfigure after disabling unique IP configuration."%(str(intf_name), str(ip)))
        try:
            db.set_entry('MCLAG_UNIQUE_IP', (interface_name), None )
        except (JsonPatchConflict, JsonPointerException) as e:
            ctx.fail("Failed to delete mclag unique IP from Vlan interface {}".format(interface_name))

#######

