import click
import utilities_common.cli as clicommon
import utilities_common.dhcp_relay_util as dhcp_relay_util
from swsscommon.swsscommon import SonicV2Connector

from jsonpatch import JsonPatchConflict
from time import sleep
from .utils import log
from .validated_config_db_connector import ValidatedConfigDBConnector

ADHOC_VALIDATION = True
DHCP_RELAY_TABLE = "DHCP_RELAY"
DHCPV6_SERVERS = "dhcpv6_servers"

#
# 'vlan' group ('config vlan ...')
#
@click.group(cls=clicommon.AbbreviationGroup, name='vlan')
def vlan():
    """VLAN-related configuration tasks"""
    pass


def set_dhcp_relay_table(table, config_db, vlan_name, value):
    config_db.set_entry(table, vlan_name, value)


def is_dhcp_relay_running():
    out, _ = clicommon.run_command(["systemctl", "show", "dhcp_relay.service", "--property", "ActiveState", "--value"],
                                   return_cmd=True)
    return out.strip() == "active"


@vlan.command('add')
@click.argument('vid', metavar='<vid>', required=True)
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@clicommon.pass_db
def add_vlan(db, vid, multiple):
    """Add VLAN"""

    ctx = click.get_current_context()

    config_db = ValidatedConfigDBConnector(db.cfgdb)

    vid_list = []
    # parser will parse the vid input if there are syntax errors it will throw error
    if multiple:
        vid_list = clicommon.multiple_vlan_parser(ctx, vid)
    else:
        if not vid.isdigit():
            ctx.fail("{} is not integer".format(vid))
        vid_list.append(int(vid))

    if ADHOC_VALIDATION:

        # loop will execute till an exception occurs
        for vid in vid_list:

            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))
            
            #Multiple VLANs need to be referenced
            vlan = 'Vlan{}'.format(vid)

            # default vlan checker
            if vid == 1:
                # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is default VLAN.".format(vlan))

            log.log_info("'vlan add {}' executing...".format(vid))

            # TODO: MISSING CONSTRAINT IN YANG MODEL
            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan):
                log.log_info("{} already exists".format(vlan))
                ctx.fail("{} already exists, Aborting!!!".format(vlan))
				
            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan, "DHCP_RELAY"):
                ctx.fail("DHCPv6 relay config for {} already exists".format(vlan))

            # set dhcpv4_relay table
            set_dhcp_relay_table('VLAN', config_db, vlan, {'vlanid': str(vid)})


def is_dhcpv6_relay_config_exist(db, vlan_name):
    keys = db.cfgdb.get_keys(DHCP_RELAY_TABLE)
    if len(keys) == 0 or vlan_name not in keys:
        return False

    table = db.cfgdb.get_entry("DHCP_RELAY", vlan_name)
    dhcpv6_servers = table.get(DHCPV6_SERVERS, [])
    if len(dhcpv6_servers) > 0:
        return True


def delete_db_entry(entry_name, db_connector, db_name):
    exists = db_connector.exists(db_name, entry_name)
    if exists:
        db_connector.delete(db_name, entry_name)


@vlan.command('del')
@click.argument('vid', metavar='<vid>', required=True)
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@click.option('--no_restart_dhcp_relay', is_flag=True, type=click.BOOL, required=False, default=False,
              help="If no_restart_dhcp_relay is True, do not restart dhcp_relay while del vlan and \
                  require dhcpv6 relay of this is empty")
@clicommon.pass_db
def del_vlan(db, vid, multiple, no_restart_dhcp_relay):
    """Delete VLAN"""

    ctx = click.get_current_context()

    vid_list = []
    # parser will parse the vid input if there are syntax errors it will throw error
    if multiple:
        vid_list = clicommon.multiple_vlan_parser(ctx, vid)
    else:
        if not vid.isdigit():
            ctx.fail("{} is not integer".format(vid))
        vid_list.append(int(vid))
    
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    if ADHOC_VALIDATION:
        for vid in vid_list:
            log.log_info("'vlan del {}' executing...".format(vid))
            
            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))
            
            #Multiple VLANs needs to be referenced
            vlan = 'Vlan{}'.format(vid)

            #Multiple VLANs needs to be checked
            if no_restart_dhcp_relay:
                if is_dhcpv6_relay_config_exist(db, vlan):
                    ctx.fail("Can't delete {} because related DHCPv6 Relay config is exist".format(vlan))

            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) == False:
                log.log_info("{} does not exist".format(vlan))
                ctx.fail("{} does not exist, Aborting!!!".format(vlan))

            intf_table = db.cfgdb.get_table('VLAN_INTERFACE')
            for intf_key in intf_table:
                if ((type(intf_key) is str and intf_key == 'Vlan{}'.format(vid)) or  # TODO: MISSING CONSTRAINT IN YANG MODEL
                        (type(intf_key) is tuple and intf_key[0] == 'Vlan{}'.format(vid))):
                    ctx.fail("{} can not be removed. First remove IP addresses assigned to this VLAN".format(vlan))

            keys = [(k, v) for k, v in db.cfgdb.get_table('VLAN_MEMBER') if k == 'Vlan{}'.format(vid)]

            if keys:  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("VLAN ID {} can not be removed. First remove all members assigned to this VLAN.".format(vid))

            vxlan_table = db.cfgdb.get_table('VXLAN_TUNNEL_MAP')
            for vxmap_key, vxmap_data in vxlan_table.items():
                if vxmap_data['vlan'] == 'Vlan{}'.format(vid):
                    ctx.fail("vlan: {} can not be removed. First remove vxlan mapping '{}' assigned to VLAN".format(vid, '|'.join(vxmap_key))) 
        
            # set dhcpv4_relay table
            set_dhcp_relay_table('VLAN', config_db, vlan, None)

            if not no_restart_dhcp_relay and is_dhcpv6_relay_config_exist(db, vlan):
                # set dhcpv6_relay table
                set_dhcp_relay_table('DHCP_RELAY', config_db, vlan, None)
                # We need to restart dhcp_relay service after dhcpv6_relay config change
                if is_dhcp_relay_running():
                    dhcp_relay_util.handle_restart_dhcp_relay_service()

            delete_db_entry("DHCPv6_COUNTER_TABLE|{}".format(vlan), db.db, db.db.STATE_DB)
            delete_db_entry("DHCP_COUNTER_TABLE|{}".format(vlan), db.db, db.db.STATE_DB)

    vlans = db.cfgdb.get_keys('VLAN')
    if not vlans:
        docker_exec_cmd = ['docker', 'exec', '-i', 'swss']
        _, rc = clicommon.run_command(docker_exec_cmd + ['supervisorctl', 'status', 'ndppd'], ignore_error=True, return_cmd=True)
        if rc == 0:
            click.echo("No VLANs remaining, stopping ndppd service")
            clicommon.run_command(docker_exec_cmd + ['supervisorctl', 'stop', 'ndppd'], ignore_error=True, return_cmd=True)
            clicommon.run_command(docker_exec_cmd + ['rm', '-f', '/etc/supervisor/conf.d/ndppd.conf'], ignore_error=True, return_cmd=True)
            clicommon.run_command(docker_exec_cmd + ['supervisorctl', 'update'], return_cmd=True)

def restart_ndppd():
    verify_swss_running_cmd = ['docker', 'container', 'inspect', '-f', '{{.State.Status}}', 'swss']
    docker_exec_cmd = ['docker', 'exec', '-i', 'swss']
    ndppd_config_gen_cmd = ['sonic-cfggen', '-d', '-t', '/usr/share/sonic/templates/ndppd.conf.j2,/etc/ndppd.conf']
    ndppd_restart_cmd = ['supervisorctl', 'restart', 'ndppd']
    ndppd_status_cmd = ["supervisorctl", "status", "ndppd"]
    ndppd_conf_copy_cmd = ['cp', '/usr/share/sonic/templates/ndppd.conf', '/etc/supervisor/conf.d/']
    supervisor_update_cmd = ['supervisorctl', 'update']

    output, _ = clicommon.run_command(verify_swss_running_cmd, return_cmd=True)

    if output and output.strip() != "running":
        click.echo(click.style('SWSS container is not running, changes will take effect the next time the SWSS container starts', fg='red'),)
        return

    _, rc = clicommon.run_command(docker_exec_cmd + ndppd_status_cmd, ignore_error=True, return_cmd=True)

    if rc != 0:
        clicommon.run_command(docker_exec_cmd + ndppd_conf_copy_cmd)
        clicommon.run_command(docker_exec_cmd + supervisor_update_cmd, return_cmd=True)

    click.echo("Starting ndppd service")
    clicommon.run_command(docker_exec_cmd + ndppd_config_gen_cmd)
    sleep(3)
    clicommon.run_command(docker_exec_cmd + ndppd_restart_cmd, return_cmd=True)

@vlan.command('proxy_arp')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('mode', metavar='<mode>', required=True, type=click.Choice(["enabled", "disabled"]))
@clicommon.pass_db
def config_proxy_arp(db, vid, mode):
    """Configure proxy ARP for a VLAN"""

    log.log_info("'setting proxy ARP to {} for Vlan{}".format(mode, vid))

    ctx = click.get_current_context()

    vlan = 'Vlan{}'.format(vid)

    if not clicommon.is_valid_vlan_interface(db.cfgdb, vlan):
        ctx.fail("Interface {} does not exist".format(vlan))

    db.cfgdb.mod_entry('VLAN_INTERFACE', vlan, {"proxy_arp": mode})
    click.echo('Proxy ARP setting saved to ConfigDB')
    restart_ndppd()
#
# 'member' group ('config vlan member ...')
#
@vlan.group(cls=clicommon.AbbreviationGroup, name='member')
def vlan_member():
    pass

@vlan_member.command('add')
@click.argument('vid', metavar='<vid>', required=True)
@click.argument('port', metavar='port', required=True)
@click.option('-u', '--untagged', is_flag=True, help="Untagged status")
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@click.option('-e', '--except_flag', is_flag=True, help="Skips the given vlans and adds all other existing vlans")
@clicommon.pass_db
def add_vlan_member(db, vid, port, untagged, multiple, except_flag):
    """Add VLAN member"""

    ctx = click.get_current_context()

    # parser will parse the vid input if there are syntax errors it will throw error

    vid_list = clicommon.vlan_member_input_parser(ctx, "add", db, except_flag, multiple, vid, port)

    # multiple vlan command cannot be used to add multiple untagged vlan members
    if untagged and (multiple or except_flag or vid == "all"):
        ctx.fail("{} cannot have more than one untagged Vlan.".format(port))
    
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        for vid in vid_list:

            vlan = 'Vlan{}'.format(vid)

            # default vlan checker
            if vid == 1:
                ctx.fail("{} is default VLAN".format(vlan))

            log.log_info("'vlan member add {} {}' executing...".format(vid, port))

            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))

            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) == False:
                log.log_info("{} does not exist".format(vlan))
                ctx.fail("{} does not exist".format(vlan))

            if clicommon.get_interface_naming_mode() == "alias":  # TODO: MISSING CONSTRAINT IN YANG MODEL
                alias = port
                iface_alias_converter = clicommon.InterfaceAliasConverter(db)
                port = iface_alias_converter.alias_to_name(alias)
                if port is None:
                    ctx.fail("cannot find port name for alias {}".format(alias))

            # TODO: MISSING CONSTRAINT IN YANG MODEL
            if clicommon.is_port_mirror_dst_port(db.cfgdb, port):
                ctx.fail("{} is configured as mirror destination port".format(port))

            # TODO: MISSING CONSTRAINT IN YANG MODEL
            if clicommon.is_port_vlan_member(db.cfgdb, port, vlan):
                log.log_info("{} is already a member of {}, Aborting!!!".format(port, vlan))
                ctx.fail("{} is already a member of {}, Aborting!!!".format(port, vlan))
                

            if clicommon.is_valid_port(db.cfgdb, port):
                is_port = True
            elif clicommon.is_valid_portchannel(db.cfgdb, port):
                is_port = False
            else:
                ctx.fail("{} does not exist".format(port))
            
            if (is_port and clicommon.is_port_router_interface(db.cfgdb, port)) or \
                (not is_port and clicommon.is_pc_router_interface(db.cfgdb, port)): # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is in routed mode!\nUse switchport mode command to change port mode".format(port))

            portchannel_member_table = db.cfgdb.get_table('PORTCHANNEL_MEMBER')

            # TODO: MISSING CONSTRAINT IN YANG MODEL
            if (is_port and clicommon.interface_is_in_portchannel(portchannel_member_table, port)):
                ctx.fail("{} is part of portchannel!".format(port))

            # TODO: MISSING CONSTRAINT IN YANG MODEL
            if (clicommon.interface_is_untagged_member(db.cfgdb, port) and untagged):
                ctx.fail("{} is already untagged member!".format(port))
            
            # checking mode status of port if its access, trunk or routed
            if is_port:
                port_data = config_db.get_entry('PORT',port)
            
            # if not port then is a port channel
            elif not is_port:
                port_data = config_db.get_entry('PORTCHANNEL',port)

            if "mode" not in port_data: 
                ctx.fail("{} is in routed mode!\nUse switchport mode command to change port mode".format(port))
            else:
                existing_mode = port_data["mode"]
            
            if existing_mode == "routed":
                ctx.fail("{} is in routed mode!\nUse switchport mode command to change port mode".format(port))

            mode_type = "access" if untagged else "trunk"
            if existing_mode == "access" and mode_type == "trunk":  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is in access mode! Tagged Members cannot be added".format(port))
            
            elif existing_mode == mode_type or (existing_mode == "trunk" and mode_type == "access"):
                pass
            
            # in case of exception in list last added member will be shown to user
        
            try:
                config_db.set_entry('VLAN_MEMBER', (vlan, port), {'tagging_mode': "untagged" if untagged else "tagged" })
            except ValueError:
                ctx.fail("{} invalid or does not exist, or {} invalid or does not exist".format(vlan, port))

@vlan_member.command('del')
@click.argument('vid', metavar='<vid>', required=True)
@click.argument('port', metavar='<port>', required=True)
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@click.option('-e', '--except_flag', is_flag=True, help="Skips the given vlans and adds all other existing vlans")
@clicommon.pass_db
def del_vlan_member(db, vid, port, multiple, except_flag):
    """Delete VLAN member"""

    ctx = click.get_current_context()
    
    # parser will parse the vid input if there are syntax errors it will throw error

    vid_list = clicommon.vlan_member_input_parser(ctx,"del", db, except_flag, multiple, vid, port)

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    if ADHOC_VALIDATION:
        for vid in vid_list:

            log.log_info("'vlan member del {} {}' executing...".format(vid, port))

            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))

            vlan = 'Vlan{}'.format(vid)

            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) == False:
                log.log_info("{} does not exist".format(vlan))
                ctx.fail("{} does not exist, Aborting!!!".format(vlan))

            if clicommon.get_interface_naming_mode() == "alias":  # TODO: MISSING CONSTRAINT IN YANG MODEL
                alias = port
                iface_alias_converter = clicommon.InterfaceAliasConverter(db)
                port = iface_alias_converter.alias_to_name(alias)
                if port is None:
                    ctx.fail("cannot find port name for alias {}".format(alias))

            # TODO: MISSING CONSTRAINT IN YANG MODEL
            if not clicommon.is_port_vlan_member(db.cfgdb, port, vlan):
                ctx.fail("{} is not a member of {}".format(port, vlan))

        
            try:
                config_db.set_entry('VLAN_MEMBER', (vlan, port), None)
                delete_db_entry("DHCPv6_COUNTER_TABLE|{}".format(port), db.db, db.db.STATE_DB)
                delete_db_entry("DHCP_COUNTER_TABLE|{}".format(port), db.db, db.db.STATE_DB)
            except JsonPatchConflict:
                ctx.fail("{} invalid or does not exist, or {} is not a member of {}".format(vlan, port, vlan))

