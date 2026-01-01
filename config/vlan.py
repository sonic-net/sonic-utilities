import click
import utilities_common.cli as clicommon
import utilities_common.dhcp_relay_util as dhcp_relay_util
from sonic_py_common import multi_asic

from jsonpatch import JsonPatchConflict
from time import sleep
from .utils import log
from .validated_config_db_connector import ValidatedConfigDBConnector
from . import stp

ADHOC_VALIDATION = True
DHCP_RELAY_TABLE = "DHCP_RELAY"
DHCPV6_SERVERS = "dhcpv6_servers"

#
# 'vlan' group ('config vlan ...')
#


@click.group(cls=clicommon.AbbreviationGroup, name='vlan')
@click.option('-n', '--namespace', help='Namespace name', required=True if multi_asic.is_multi_asic() else False,
              type=click.Choice(multi_asic.get_namespace_list()))
@click.pass_context
def vlan(ctx, namespace):
    """VLAN-related configuration tasks"""
    if namespace is None:
        namespace = multi_asic.DEFAULT_NAMESPACE
    ctx.ensure_object(dict)
    ctx.obj['namespace'] = namespace


def set_dhcp_relay_table(table, config_db, vlan_name, value):
    config_db.set_entry(table, vlan_name, value)


def is_dhcp_relay_running():
    out, _ = clicommon.run_command(["systemctl", "show", "dhcp_relay.service", "--property", "ActiveState", "--value"],
                                   return_cmd=True)
    return out.strip() == "active"


def get_config_db_from_context(ctx):
    """
    Extract config_db from context object.
    Handles both dict-style context ({'config_db': ...}) and Db objects.
    Falls back to connecting to the database for the namespace.
    """
    namespace = ''
    if isinstance(ctx.obj, dict):
        namespace = ctx.obj.get('namespace', '')
        if 'config_db' in ctx.obj:
            return ctx.obj['config_db']
    elif hasattr(ctx.obj, 'cfgdb'):
        # ctx.obj is a Db object
        return ctx.obj.cfgdb

    # Fallback: connect to database for namespace
    return multi_asic.connect_config_db_for_ns(namespace)


def get_namespace_from_context(ctx):
    """Extract namespace from context object."""
    if isinstance(ctx.obj, dict):
        return ctx.obj.get('namespace', '')
    elif hasattr(ctx.obj, 'namespace'):
        return ctx.obj.namespace
    return ''


class ConfigDbWrapper:
    """Wrapper to provide both cfgdb and db (namespace db) attributes."""
    def __init__(self, cfgdb, ns_db):
        self.cfgdb = cfgdb
        self.db = ns_db


def get_db_with_namespace(ctx):
    """
    Get a database wrapper with both config_db and namespace db.
    Returns an object with both .cfgdb and .db attributes.
    """
    config_db = get_config_db_from_context(ctx)

    # Check if db object is available with both cfgdb and db
    if hasattr(ctx.obj, 'db'):
        ns_db = ctx.obj.db
    else:
        namespace = get_namespace_from_context(ctx)
        ns_db = multi_asic.connect_to_all_dbs_for_ns(namespace)

    return ConfigDbWrapper(config_db, ns_db)


@vlan.command('add')
@click.argument('vid', metavar='<vid>', required=True)
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@click.pass_context
def add_vlan(ctx, vid, multiple):
    """Add VLAN"""

    config_db = get_config_db_from_context(ctx)

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

            # Multiple VLANs need to be referenced
            vlan = 'Vlan{}'.format(vid)

            # Defualt VLAN checker
            if vid == 1:
                ctx.fail("{} is default VLAN".format(vlan))  # TODO: MISSING CONSTRAINT IN YANG MODEL

            log.log_info("'vlan add {}' executing...".format(vid))

            if clicommon.check_if_vlanid_exist(config_db, vlan):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} already exists.".format(vlan))

            if clicommon.check_if_vlanid_exist(config_db, vlan, "DHCP_RELAY"):
                ctx.fail("DHCPv6 relay config for {} already exists".format(vlan))

            # Enable STP on VLAN if PVST is enabled globally
            stp.vlan_enable_stp(config_db, vlan)

            # set dhcpv4_relay table
            set_dhcp_relay_table('VLAN', config_db, vlan, {'vlanid': str(vid)})


def is_dhcpv6_relay_config_exist(config_db, vlan_name):
    keys = config_db.get_keys(DHCP_RELAY_TABLE)
    if len(keys) == 0 or vlan_name not in keys:
        return False

    table = config_db.get_entry("DHCP_RELAY", vlan_name)
    dhcpv6_servers = table.get(DHCPV6_SERVERS, [])
    if len(dhcpv6_servers) > 0:
        return True


def delete_db_entry(entry_name, db_connector, db_name):
    exists = db_connector.exists(db_name, entry_name)
    if exists:
        db_connector.delete(db_name, entry_name)


def enable_stp_on_port(db, port):
    if stp.is_global_stp_enabled(db) is True:
        vlan_list_for_intf = stp.get_vlan_list_for_interface(db, port)
        if len(vlan_list_for_intf) == 0:
            stp.interface_enable_stp(db, port)


def disable_stp_on_vlan_port(db, vlan, port):
    if stp.is_global_stp_enabled(db) is True:
        vlan_interface = str(vlan) + "|" + port
        db.set_entry('STP_VLAN_PORT', vlan_interface, None)
        vlan_list_for_intf = stp.get_vlan_list_for_interface(db, port)
        if len(vlan_list_for_intf) == 0:
            db.set_entry('STP_PORT', port, None)


def disable_stp_on_vlan(db, vlan_interface):
    db.set_entry('STP_VLAN', vlan_interface, None)
    stp_intf_list = stp.get_intf_list_from_stp_vlan_intf_table(db, vlan_interface)
    for intf_name in stp_intf_list:
        key = vlan_interface + "|" + intf_name
        db.set_entry('STP_VLAN_PORT', key, None)

@vlan.command('del')
@click.argument('vid', metavar='<vid>', required=True)
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@click.option('--no_restart_dhcp_relay', is_flag=True, type=click.BOOL, required=False, default=False,
              help="If no_restart_dhcp_relay is True, do not restart dhcp_relay while del vlan and \
                  require dhcpv6 relay of this is empty")
@click.pass_context
def del_vlan(ctx, vid, multiple, no_restart_dhcp_relay):
    """Delete VLAN"""

    db = get_db_with_namespace(ctx)

    vid_list = []
    # parser will parse the vid input if there are syntax errors it will throw error
    if multiple:
        vid_list = clicommon.multiple_vlan_parser(ctx, vid)
    else:
        if not vid.isdigit():
            ctx.fail("{} is not integer".format(vid))
        vid_list.append(int(vid))

    if ADHOC_VALIDATION:
        for vid in vid_list:
            log.log_info("'vlan del {}' executing...".format(vid))

            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))

            # Multiple VLANs needs to be referenced
            vlan = 'Vlan{}'.format(vid)

            # Multiple VLANs needs to be checked
            if no_restart_dhcp_relay:
                if is_dhcpv6_relay_config_exist(db.cfgdb, vlan):
                    ctx.fail("Can't delete {} because related DHCPv6 Relay config is exist".format(vlan))

            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) is False:
                ctx.fail("{} does not exist".format(vlan))

            intf_table = db.cfgdb.get_table('VLAN_INTERFACE')
            for intf_key in intf_table:
                if ((type(
                    intf_key) is str and intf_key == 'Vlan{}'.format(vid)) or  # TODO: MISSING CONSTRAINT IN YANG MODEL
                        (type(intf_key) is tuple and intf_key[0] == 'Vlan{}'.format(vid))):
                    ctx.fail("{} can not be removed. First remove IP addresses assigned to this VLAN".format(vlan))

            keys = [(k, v) for k, v in db.cfgdb.get_table('VLAN_MEMBER') if k == 'Vlan{}'.format(vid)]

            if keys:  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("VLAN ID {} can not be removed. First remove all members assigned to this VLAN.".format(vid))

            vxlan_table = db.cfgdb.get_table('VXLAN_TUNNEL_MAP')
            for vxmap_key, vxmap_data in vxlan_table.items():
                if vxmap_data['vlan'] == 'Vlan{}'.format(vid):
                    ctx.fail("vlan: {} can not be removed. "
                             "First remove vxlan mapping '{}' assigned to VLAN".format(
                              vid, '|'.join(vxmap_key)))

            if vlan in db.cfgdb.get_table('DHCPV4_RELAY'):
                ctx.fail(f"{vlan} cannot be removed as it is being used in DHCPV4_RELAY table.")
            # set dhcpv4_relay table
            set_dhcp_relay_table('VLAN', db.cfgdb, vlan, None)

            if not no_restart_dhcp_relay and is_dhcpv6_relay_config_exist(db.cfgdb, vlan):
                # set dhcpv6_relay table
                set_dhcp_relay_table('DHCP_RELAY', db.cfgdb, vlan, None)
                # We need to restart dhcp_relay service after dhcpv6_relay config change
                if is_dhcp_relay_running():
                    dhcp_relay_util.handle_restart_dhcp_relay_service()

            delete_db_entry("DHCPv6_COUNTER_TABLE|{}".format(vlan), db.db, db.db.STATE_DB)
            delete_db_entry("DHCP_COUNTER_TABLE|{}".format(vlan), db.db, db.db.STATE_DB)

            # Delete STP_VLAN & STP_VLAN_PORT entries when VLAN is deleted.
            disable_stp_on_vlan(db.cfgdb, 'Vlan{}'.format(vid))

    vlans = db.cfgdb.get_keys('VLAN')
    if not vlans:
        docker_exec_cmd = ['docker', 'exec', '-i', 'swss']
        _, rc = clicommon.run_command(
            docker_exec_cmd + ['supervisorctl', 'status', 'ndppd'], ignore_error=True, return_cmd=True)
        if rc == 0:
            click.echo("No VLANs remaining, stopping ndppd service")
            clicommon.run_command(
                docker_exec_cmd + ['supervisorctl', 'stop', 'ndppd'], ignore_error=True, return_cmd=True)
            clicommon.run_command(
                docker_exec_cmd + ['rm', '-f', '/etc/supervisor/conf.d/ndppd.conf'], ignore_error=True, return_cmd=True)
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
        click.echo(click.style('SWSS container is not running, '
                               'changes will take effect the next time the SWSS container starts', fg='red'),)
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
@click.pass_context
@clicommon.pass_db
def config_proxy_arp(db, ctx, vid, mode):
    """Configure proxy ARP for a VLAN"""

    log.log_info("'setting proxy ARP to {} for Vlan{}".format(mode, vid))

    config_db = get_config_db_from_context(ctx)
    vlan = 'Vlan{}'.format(vid)

    if not clicommon.is_valid_vlan_interface(config_db, vlan):
        ctx.fail("Interface {} does not exist".format(vlan))

    config_db.mod_entry('VLAN_INTERFACE', vlan, {"proxy_arp": mode})
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
@click.pass_context
def add_vlan_member(ctx, vid, port, untagged, multiple, except_flag):
    """Add VLAN member"""

    db = get_db_with_namespace(ctx)

    # parser will parse the vid input if there are syntax errors it will throw error
    vid_list = clicommon.vlan_member_input_parser(ctx, "add", db, except_flag, multiple, vid, port)
    # multiple vlan command cannot be used to add multiple untagged vlan members
    if untagged and (multiple or except_flag or vid == "all"):
        ctx.fail("{} cannot have more than one untagged Vlan.".format(port))
    if ADHOC_VALIDATION:
        for vid in vid_list:
            vlan = 'Vlan{}'.format(vid)
            # default vlan checker
            if vid == 1:
                ctx.fail("{} is default VLAN".format(vlan))
            log.log_info("'vlan member add {} {}' executing...".format(vid, port))
            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))
            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) is False:
                ctx.fail("{} does not exist".format(vlan))
            if clicommon.get_interface_naming_mode() == "alias":  # TODO: MISSING CONSTRAINT IN YANG MODEL
                alias = port
                iface_alias_converter = clicommon.InterfaceAliasConverter(db)
                port = iface_alias_converter.alias_to_name(alias)
                if port is None:
                    ctx.fail("cannot find port name for alias {}".format(alias))
            if clicommon.is_port_mirror_dst_port(db.cfgdb, port):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is configured as mirror destination port".format(port))
            if clicommon.is_port_vlan_member(db.cfgdb, port, vlan):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is already a member of {}".format(port, vlan))
            if clicommon.is_valid_port(db.cfgdb, port):
                is_port = True
            elif clicommon.is_valid_portchannel(db.cfgdb, port):
                is_port = False
            else:
                ctx.fail("{} does not exist".format(port))
            if (is_port and clicommon.is_port_router_interface(db.cfgdb, port)) or \
                (not is_port and clicommon.is_pc_router_interface(
                    db.cfgdb, port)):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is a router interface!".format(port))
            portchannel_member_table = db.cfgdb.get_table('PORTCHANNEL_MEMBER')
            if (is_port and clicommon.interface_is_in_portchannel(
                 portchannel_member_table, port)):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is part of portchannel!".format(port))
            if (clicommon.interface_is_untagged_member(
                    db.cfgdb, port) and untagged):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is already untagged member!".format(port))
            # checking mode status of port if its access, trunk or routed
            if is_port:
                port_data = db.cfgdb.get_entry('PORT', port)
            # if not port then is a port channel
            elif not is_port:
                port_data = db.cfgdb.get_entry('PORTCHANNEL', port)
            existing_mode = None
            if "mode" in port_data:
                existing_mode = port_data["mode"]
            if existing_mode == "routed":
                ctx.fail("{} is in routed mode!\nUse switchport mode command to change port mode".format(port))
            mode_type = "access" if untagged else "trunk"
            if existing_mode == "access" and mode_type == "trunk":  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is in access mode! Tagged Members cannot be added".format(port))
            elif existing_mode == mode_type or (existing_mode == "trunk" and mode_type == "access"):
                pass

            # If port is being made L2 port, enable STP
            enable_stp_on_port(db.cfgdb, port)

            try:
                db.cfgdb.set_entry('VLAN_MEMBER', (vlan, port), {'tagging_mode': "untagged" if untagged else "tagged"})
            except ValueError:
                ctx.fail("{} invalid or does not exist, or {} invalid or does not exist".format(vlan, port))


@vlan_member.command('del')
@click.argument('vid', metavar='<vid>', required=True)
@click.argument('port', metavar='<port>', required=True)
@click.option('-m', '--multiple', is_flag=True, help="Add Multiple Vlan(s) in Range or in Comma separated list")
@click.option('-e', '--except_flag', is_flag=True, help="Skips the given vlans and adds all other existing vlans")
@click.pass_context
def del_vlan_member(ctx, vid, port, multiple, except_flag):
    """Delete VLAN member"""

    db = get_db_with_namespace(ctx)

    # parser will parse the vid input if there are syntax errors it will throw error
    vid_list = clicommon.vlan_member_input_parser(ctx, "del", db, except_flag, multiple, vid, port)
    if ADHOC_VALIDATION:
        for vid in vid_list:
            log.log_info("'vlan member del {} {}' executing...".format(vid, port))

            if not clicommon.is_vlanid_in_range(vid):
                ctx.fail("Invalid VLAN ID {} (2-4094)".format(vid))

            vlan = 'Vlan{}'.format(vid)

            if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) is False:
                ctx.fail("{} does not exist".format(vlan))

            if clicommon.get_interface_naming_mode() == "alias":  # TODO: MISSING CONSTRAINT IN YANG MODEL
                alias = port
                iface_alias_converter = clicommon.InterfaceAliasConverter(db)
                port = iface_alias_converter.alias_to_name(alias)
                if port is None:
                    ctx.fail("cannot find port name for alias {}".format(alias))

            if not clicommon.is_port_vlan_member(db.cfgdb, port, vlan):  # TODO: MISSING CONSTRAINT IN YANG MODEL
                ctx.fail("{} is not a member of {}".format(port, vlan))

            # If port is being made non-L2 port, disable STP
            disable_stp_on_vlan_port(db.cfgdb, vlan, port)

            try:
                db.cfgdb.set_entry('VLAN_MEMBER', (vlan, port), None)
                delete_db_entry("DHCPv6_COUNTER_TABLE|{}".format(port), db.db, db.db.STATE_DB)
                delete_db_entry("DHCP_COUNTER_TABLE|{}".format(port), db.db, db.db.STATE_DB)
            except JsonPatchConflict:
                ctx.fail("{} invalid or does not exist, or {} is not a member of {}".format(vlan, port, vlan))
