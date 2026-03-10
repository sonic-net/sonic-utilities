import click
from natsort import natsorted
from tabulate import tabulate

import utilities_common.cli as clicommon


@click.group(cls=clicommon.AliasedGroup)
def vlan():
    """Show VLAN information"""
    pass


def get_vlan_id(ctx, vlan):
    vlan_prefix, vid = vlan.split('Vlan')
    return vid


def get_vlan_ip_address(ctx, vlan):
    cfg, _ = ctx
    _, vlan_ip_data, _ = cfg
    ip_address = ""
    for key in vlan_ip_data:
        if not clicommon.is_ip_prefix_in_key(key):
            continue
        ifname, address = key
        if vlan == ifname:
            ip_address += "\n{}".format(address)

    return ip_address


def get_vlan_ports(ctx, vlan):
    cfg, db = ctx
    _, _, vlan_ports_data = cfg
    vlan_ports = []
    iface_alias_converter = clicommon.InterfaceAliasConverter(db)
    # Here natsorting is important in relation to another
    # column which prints port tagging mode.
    # If we sort both in the same way using same keys
    # we will result in right order in both columns.
    # This should be fixed by cli code autogeneration tool
    # and we won't need this specific approach with
    # VlanBrief.COLUMNS anymore.
    for key in natsorted(list(vlan_ports_data.keys())):
        ports_key, ports_value = key
        if vlan != ports_key:
            continue

        if clicommon.get_interface_naming_mode() == "alias":
            ports_value = iface_alias_converter.name_to_alias(ports_value)

        vlan_ports.append(ports_value)

    return '\n'.join(vlan_ports)


def get_vlan_ports_tagging(ctx, vlan):
    cfg, db = ctx
    _, _, vlan_ports_data = cfg
    vlan_ports_tagging = []
    # Here natsorting is important in relation to another
    # column which prints vlan ports.
    # If we sort both in the same way using same keys
    # we will result in right order in both columns.
    # This should be fixed by cli code autogeneration tool
    # and we won't need this specific approach with
    # VlanBrief.COLUMNS anymore.
    for key in natsorted(list(vlan_ports_data.keys())):
        ports_key, ports_value = key
        if vlan != ports_key:
            continue

        tagging_value = vlan_ports_data[key]["tagging_mode"]
        vlan_ports_tagging.append(tagging_value)

    return '\n'.join(vlan_ports_tagging)


def get_proxy_arp(ctx, vlan):
    cfg, _ = ctx
    _, vlan_ip_data, _ = cfg
    proxy_arp = "disabled"
    for key in vlan_ip_data:
        if clicommon.is_ip_prefix_in_key(key):
            continue
        if vlan == key:
            proxy_arp = vlan_ip_data[key].get("proxy_arp", "disabled")

    return proxy_arp


class VlanBrief:
    """ This class is used as a namespace to
    define columns for "show vlan brief" command.
    The usage of this class is for external plugin
    (in this case dhcp-relay) to append new columns
    to this list.
    """

    COLUMNS = [
        ("VLAN ID", get_vlan_id),
        ("IP Address", get_vlan_ip_address),
        ("Ports", get_vlan_ports),
        ("Port Tagging", get_vlan_ports_tagging),
        ("Proxy ARP", get_proxy_arp)
    ]

    @classmethod
    def register_column(cls, column_name, callback):
        """ Adds a new column to "vlan brief" output.
        Expected to be used from plugins code to extend
        this command with  additional VLAN fields. """

        cls.COLUMNS.append((column_name, callback))


@vlan.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def brief(db, verbose):
    """Show all bridge information"""
    header = [colname for colname, getter in VlanBrief.COLUMNS]
    body = []

    # Fetching data from config db for VLAN, VLAN_INTERFACE and VLAN_MEMBER
    vlan_data = db.cfgdb.get_table('VLAN')
    vlan_ip_data = db.cfgdb.get_table('VLAN_INTERFACE')
    vlan_ports_data = db.cfgdb.get_table('VLAN_MEMBER')
    vlan_cfg = (vlan_data, vlan_ip_data, vlan_ports_data)

    for vlan in natsorted(vlan_data):
        row = []
        for column in VlanBrief.COLUMNS:
            column_name, getter = column
            row.append(getter((vlan_cfg, db), vlan))
        body.append(row)

    click.echo(tabulate(body, header, tablefmt="grid"))


@vlan.command()
@clicommon.pass_db
def config(db):
    data = db.cfgdb.get_table('VLAN')
    keys = list(data.keys())
    member_data = db.cfgdb.get_table('VLAN_MEMBER')
    interface_naming_mode = clicommon.get_interface_naming_mode()
    iface_alias_converter = clicommon.InterfaceAliasConverter(db)
   
    def get_iface_name_for_display(member):
        name_for_display = member
        if interface_naming_mode == "alias" and member:
            name_for_display = iface_alias_converter.name_to_alias(member)
        return name_for_display
    
    def get_tagging_mode(vlan, member):
        if not member:
            return ''
        tagging_mode = db.cfgdb.get_entry('VLAN_MEMBER', (vlan, member)).get('tagging_mode')
        return '?' if tagging_mode is None else tagging_mode
        
    def tablelize(keys, data):
        table = []

        for k in natsorted(keys):
            members = set([(vlan, member) for vlan, member in member_data if vlan == k] + [(k, member) for member in set(data[k].get('members', []))])
            # vlan with no members
            if not members:
                members = [(k, '')]
            
            for vlan, member in natsorted(members):
                r = [vlan, data[vlan]['vlanid'], get_iface_name_for_display(member), get_tagging_mode(vlan, member)]
                table.append(r)

        return table

    header = ['Name', 'VID', 'Member', 'Mode']
    click.echo(tabulate(tablelize(keys, data), header))

