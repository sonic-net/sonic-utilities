import ipaddress

import click
from jsonpatch import JsonPatchConflict
from jsonpointer import JsonPointerException
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from .validated_config_db_connector import ValidatedConfigDBConnector

ADHOC_VALIDATION = True

def is_valid_ipv4_address(address):
    """Check if the given ipv4 address is valid"""
    invalid_list = ['0.0.0.0','255.255.255.255']
    try:
        ip = ipaddress.IPv4Address(address)
        if (ip.is_reserved) or (ip.is_multicast) or (ip.is_loopback) or (address in invalid_list):
            return False
    except ipaddress.AddressValueError:
        return False

    return True

def is_valid_port_address(address):
    """Check if the given port address is valid"""
    try:
        port_address = int(address)
    except ValueError:
        return False

    if port_address not in range(1, 65535):
        return False

    return True

def nat_interface_name_is_valid(interface_name):
    """Check if the given nat interface is valid"""

    config_db = ConfigDBConnector()
    config_db.connect()

    if interface_name.startswith("Ethernet"):
        interface_dict = config_db.get_table('PORT')
    elif interface_name.startswith("PortChannel"):
        interface_dict = config_db.get_table('PORTCHANNEL')
    elif interface_name.startswith("Vlan"):
        interface_dict = config_db.get_table('VLAN')
    elif interface_name.startswith("Loopback"):
        return True
    else:
        return False

    if interface_name is not None:
        if not interface_dict:
            return False
        return interface_name in interface_dict

    return False

def isIpOverlappingWithAnyStaticEntry(ipAddress, table):
    """Check if the given ipAddress is overlapping with any static entry"""

    config_db = ConfigDBConnector()
    config_db.connect()

    static_dict = config_db.get_table(table)

    if not static_dict:
        return False

    for key,values in static_dict.items():
        global_ip = "---"
        nat_type = "dnat"

        if table == 'STATIC_NAPT':
            if isinstance(key, tuple) is False:
                continue

            if (len(key) == 3):
                global_ip = key[0]
            else:
                continue
        elif table == 'STATIC_NAT':
            if isinstance(key, str) is True:
                global_ip = key
            else:
                continue

        local_ip = values["local_ip"]

        if "nat_type" in values:
            nat_type = values["nat_type"]

        if nat_type == "snat":
            global_ip = local_ip

        if global_ip == ipAddress:
            return True

    return False

def isOverlappingWithAnyDynamicEntry(ipAddress):
    """Check if the given ipAddress is overlapping with any dynamic pool entry"""

    config_db = ConfigDBConnector()
    config_db.connect()

    ip = int(ipaddress.IPv4Address(ipAddress))
    nat_pool_dict = config_db.get_table('NAT_POOL')

    if not nat_pool_dict:
        return False

    for values in nat_pool_dict.values():
        global_ip = values["nat_ip"]
        ipAddr = global_ip.split('-')
        if (len(ipAddr) == 1):
            startIp = int(ipaddress.IPv4Address(ipAddr[0]))
            endIp = int(ipaddress.IPv4Address(ipAddr[0]))
        else:
            startIp = int(ipaddress.IPv4Address(ipAddr[0]))
            endIp = int(ipaddress.IPv4Address(ipAddr[1]))

        if ((ip >= startIp) and (ip <= endIp)):
            return True

    return False

def getTwiceNatIdCountWithStaticEntries(twice_nat_id, table, count):
    """Get the twice nat id count with static entries"""

    config_db = ConfigDBConnector()
    config_db.connect()

    static_dict = config_db.get_table(table)
    twice_id_count =  count

    if not static_dict:
        return twice_id_count

    for key,values in static_dict.items():
        twice_id = 0

        if "twice_nat_id" in values:
            twice_id = int(values["twice_nat_id"])
        else:
            continue

        if twice_id == twice_nat_id:
            twice_id_count += 1

    return twice_id_count

def getTwiceNatIdCountWithDynamicBinding(twice_nat_id, count, dynamic_key):
    """Get the twice nat id count with dynamic binding"""

    config_db = ConfigDBConnector()
    config_db.connect()

    nat_binding_dict = config_db.get_table('NAT_BINDINGS')
    twice_id_count = count

    if not nat_binding_dict:
        return twice_id_count

    for key, values in nat_binding_dict.items():
        nat_pool_data = config_db.get_entry('NAT_POOL',values["nat_pool"])
        twice_id = 0

        if dynamic_key is not None:
            if dynamic_key == key:
                continue

        if not nat_pool_data:
            continue

        if "twice_nat_id" in values:
            if values["twice_nat_id"] == "NULL":
                continue
            else:
                twice_id = int(values["twice_nat_id"])
        else:
            continue

        if twice_id == twice_nat_id:
            twice_id_count += 1

    return twice_id_count
 
############### NAT Configuration ##################

#
# 'nat' group ('config nat ...')
#
@click.group('nat')
def nat():
    """NAT-related configuration tasks"""
    pass

#
# 'nat add' group ('config nat add ...')
#
@nat.group('add')
def add():
    """Add NAT-related configuration tasks"""
    pass

#
# 'nat remove' group ('config nat remove ...')
#
@nat.group('remove')
def remove():
    """Remove NAT-related configuration tasks"""
    pass

#
# 'nat set' group ('config nat set ...')
#
@nat.group('set')
def set():
    """Set NAT-related timeout configuration tasks"""
    pass

#
# 'nat reset' group ('config nat reset ...')
#
@nat.group('reset')
def reset():
    """Reset NAT-related timeout configuration tasks"""
    pass

#
# 'nat add static' group ('config nat add static ...')
#
@add.group('static')
def static():
    """Add Static related configuration"""
    pass

#
# 'nat add static basic' command ('config nat add static basic <global-ip> <local-ip>')
#
@static.command('basic')
@click.pass_context
@click.argument('global_ip', metavar='<global_ip>', required=True)
@click.argument('local_ip', metavar='<local_ip>', required=True)
@click.option('-nat_type', metavar='<nat_type>', required=False, type=click.Choice(["snat", "dnat"]), help="Set nat type")
@click.option('-twice_nat_id', metavar='<twice_nat_id>', required=False, type=click.IntRange(1, 9999), help="Set the twice nat id")
def add_basic(ctx, global_ip, local_ip, nat_type, twice_nat_id):
    """Add Static NAT-related configuration"""
    if ADHOC_VALIDATION:
        # Verify the ip address format 
        if is_valid_ipv4_address(local_ip) is False:
            ctx.fail("Given local ip address {} is invalid. Please enter a valid local ip address !!".format(local_ip)) 

        if is_valid_ipv4_address(global_ip) is False:
            ctx.fail("Given global ip address {} is invalid. Please enter a valid global ip address !!".format(global_ip))
   
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    table = "STATIC_NAT"
    key = global_ip
    dataKey1 = 'local_ip'
    dataKey2 = 'nat_type'
    dataKey3 = 'twice_nat_id'

    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey1] == local_ip:
            click.echo("Trying to add static nat entry, which is already present.")
            entryFound = True

    if nat_type == 'snat':
        ipAddress = local_ip
    else:
        ipAddress = global_ip

    if isIpOverlappingWithAnyStaticEntry(ipAddress, 'STATIC_NAPT') is True:
        ctx.fail("Given entry is overlapping with existing NAPT entry !!")

    if isOverlappingWithAnyDynamicEntry(ipAddress) is True:
        ctx.fail("Given entry is overlapping with existing Dynamic entry !!")

    if entryFound is False:
        counters_db = SonicV2Connector()
        counters_db.connect(counters_db.COUNTERS_DB)
        snat_entries = 0
        max_entries = 0
        exists = counters_db.exists(counters_db.COUNTERS_DB, 'COUNTERS_GLOBAL_NAT:Values')
        if exists:
            counter_entry = counters_db.get_all(counters_db.COUNTERS_DB, 'COUNTERS_GLOBAL_NAT:Values')
            if 'SNAT_ENTRIES' in counter_entry:
                snat_entries = counter_entry['SNAT_ENTRIES']
            if 'MAX_NAT_ENTRIES' in counter_entry:
                max_entries = counter_entry['MAX_NAT_ENTRIES']

        if int(snat_entries) >= int(max_entries):
            click.echo("Max limit is reached for NAT entries, skipping adding the entry.")
            entryFound = True

    if entryFound is False:
        count = 0
        if twice_nat_id is not None:
            count = getTwiceNatIdCountWithStaticEntries(twice_nat_id, table, count)
            count = getTwiceNatIdCountWithDynamicBinding(twice_nat_id, count, None)
            if count > 1:
                ctx.fail("Same Twice nat id is not allowed for more than 2 entries!!")

        if nat_type is not None and twice_nat_id is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: nat_type, dataKey3: twice_nat_id})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif nat_type is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: nat_type})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif twice_nat_id is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey3: twice_nat_id})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        else:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat add static tcp' command ('config nat add static tcp <global-ip> <global-port> <local-ip> <local-port>')
#
@static.command('tcp')
@click.pass_context
@click.argument('global_ip', metavar='<global_ip>', required=True)
@click.argument('global_port', metavar='<global_port>', type=click.IntRange(1, 65535), required=True)
@click.argument('local_ip', metavar='<local_ip>', required=True)
@click.argument('local_port', metavar='<local_port>', type=click.IntRange(1, 65535), required=True)
@click.option('-nat_type', metavar='<nat_type>', required=False, type=click.Choice(["snat", "dnat"]), help="Set nat type")
@click.option('-twice_nat_id', metavar='<twice_nat_id>', required=False, type=click.IntRange(1, 9999), help="Set the twice nat id")
def add_tcp(ctx, global_ip, global_port, local_ip, local_port, nat_type, twice_nat_id):
    """Add Static TCP Protocol NAPT-related configuration"""
    if ADHOC_VALIDATION: 
        # Verify the ip address format 
        if is_valid_ipv4_address(local_ip) is False:
            ctx.fail("Given local ip address {} is invalid. Please enter a valid local ip address !!".format(local_ip))

        if is_valid_ipv4_address(global_ip) is False:
            ctx.fail("Given global ip address {} is invalid. Please enter a valid global ip address !!".format(global_ip))

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    
    entryFound = False
    table = "STATIC_NAPT"
    key = "{}|TCP|{}".format(global_ip, global_port)
    dataKey1 = 'local_ip'
    dataKey2 = 'local_port'
    dataKey3 = 'nat_type'
    dataKey4 = 'twice_nat_id'

    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey1] == local_ip and data[dataKey2] == str(local_port):
            click.echo("Trying to add static napt entry, which is already present.")
            entryFound = True

    if nat_type == 'snat':
        ipAddress = local_ip
    else: 
        ipAddress = global_ip

    if isIpOverlappingWithAnyStaticEntry(ipAddress, 'STATIC_NAT') is True:
        ctx.fail("Given entry is overlapping with existing NAT entry !!")

    if entryFound is False:
        counters_db = SonicV2Connector()
        counters_db.connect(counters_db.COUNTERS_DB)
        snat_entries = 0
        max_entries = 0
        exists = counters_db.exists(counters_db.COUNTERS_DB, 'COUNTERS_GLOBAL_NAT:Values')
        if exists:
            counter_entry = counters_db.get_all(counters_db.COUNTERS_DB, 'COUNTERS_GLOBAL_NAT:Values')
            if 'SNAT_ENTRIES' in counter_entry:
                snat_entries = counter_entry['SNAT_ENTRIES']
            if 'MAX_NAT_ENTRIES' in counter_entry:
                max_entries = counter_entry['MAX_NAT_ENTRIES']

        if int(snat_entries) >= int(max_entries):
            click.echo("Max limit is reached for NAT entries, skipping adding the entry.")
            entryFound = True

    if entryFound is False:
        count = 0
        if twice_nat_id is not None:
            count = getTwiceNatIdCountWithStaticEntries(twice_nat_id, table, count)
            count = getTwiceNatIdCountWithDynamicBinding(twice_nat_id, count, None)
            if count > 1:
                ctx.fail("Same Twice nat id is not allowed for more than 2 entries!!")

        if nat_type is not None and twice_nat_id is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port, dataKey3: nat_type, dataKey4: twice_nat_id})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif nat_type is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port, dataKey3: nat_type})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif twice_nat_id is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port, dataKey4: twice_nat_id})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        else:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat add static udp' command ('config nat add static udp <global-ip> <global-port> <local-ip> <local-port>')
#
@static.command('udp')
@click.pass_context
@click.argument('global_ip', metavar='<global_ip>', required=True)
@click.argument('global_port', metavar='<global_port>', type=click.IntRange(1, 65535), required=True)
@click.argument('local_ip', metavar='<local_ip>', required=True)
@click.argument('local_port', metavar='<local_port>', type=click.IntRange(1, 65535), required=True)
@click.option('-nat_type', metavar='<nat_type>', required=False, type=click.Choice(["snat", "dnat"]), help="Set nat type")
@click.option('-twice_nat_id', metavar='<twice_nat_id>', required=False, type=click.IntRange(1, 9999), help="Set the twice nat id")
def add_udp(ctx, global_ip, global_port, local_ip, local_port, nat_type, twice_nat_id):
    """Add Static UDP Protocol NAPT-related configuration"""
    
    if ADHOC_VALIDATION:
        # Verify the ip address format 
        if is_valid_ipv4_address(local_ip) is False:
            ctx.fail("Given local ip address {} is invalid. Please enter a valid local ip address !!".format(local_ip))

        if is_valid_ipv4_address(global_ip) is False:
            ctx.fail("Given global ip address {} is invalid. Please enter a valid global ip address !!".format(global_ip))

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    table = "STATIC_NAPT"
    key = "{}|UDP|{}".format(global_ip, global_port)
    dataKey1 = 'local_ip'
    dataKey2 = 'local_port'
    dataKey3 = 'nat_type'
    dataKey4 = 'twice_nat_id'

    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey1] == local_ip and data[dataKey2] == str(local_port):
            click.echo("Trying to add static napt entry, which is already present.")
            entryFound = True

    if nat_type == 'snat':
        ipAddress = local_ip
    else:
        ipAddress = global_ip

    if isIpOverlappingWithAnyStaticEntry(ipAddress, 'STATIC_NAT') is True:
        ctx.fail("Given entry is overlapping with existing NAT entry !!")

    if entryFound is False:
        counters_db = SonicV2Connector()
        counters_db.connect(counters_db.COUNTERS_DB)
        snat_entries = 0
        max_entries = 0
        exists = counters_db.exists(counters_db.COUNTERS_DB, 'COUNTERS_GLOBAL_NAT:Values')
        if exists:
            counter_entry = counters_db.get_all(counters_db.COUNTERS_DB, 'COUNTERS_GLOBAL_NAT:Values')
            if 'SNAT_ENTRIES' in counter_entry:
                snat_entries = counter_entry['SNAT_ENTRIES']
            if 'MAX_NAT_ENTRIES' in counter_entry:
                max_entries = counter_entry['MAX_NAT_ENTRIES']
 
        if int(snat_entries) >= int(max_entries):
            click.echo("Max limit is reached for NAT entries, skipping adding the entry.")
            entryFound = True

    if entryFound is False:
        count = 0
        if twice_nat_id is not None:
            count = getTwiceNatIdCountWithStaticEntries(twice_nat_id, table, count)
            count = getTwiceNatIdCountWithDynamicBinding(twice_nat_id, count, None)
            if count > 1:
                ctx.fail("Same Twice nat id is not allowed for more than 2 entries!!")

        if nat_type is not None and twice_nat_id is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port, dataKey3: nat_type, dataKey4: twice_nat_id})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif nat_type is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port, dataKey3: nat_type})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif twice_nat_id is not None:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port, dataKey4: twice_nat_id})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        else:
            try:
                config_db.set_entry(table, key, {dataKey1: local_ip, dataKey2: local_port})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove static' group ('config nat remove static ...')
#
@remove.group('static')
def static():
    """Remove Static related configuration"""
    pass

#
# 'nat remove static basic' command ('config nat remove static basic <global-ip> <local-ip>')
#
@static.command('basic')
@click.pass_context
@click.argument('global_ip', metavar='<global_ip>', required=True)
@click.argument('local_ip', metavar='<local_ip>', required=True)
def remove_basic(ctx, global_ip, local_ip):
    """Remove Static NAT-related configuration"""
    
    if ADHOC_VALIDATION:
        # Verify the ip address format 
        if is_valid_ipv4_address(local_ip) is False:
            ctx.fail("Given local ip address {} is invalid. Please enter a valid local ip address !!".format(local_ip))

        if is_valid_ipv4_address(global_ip) is False:
            ctx.fail("Given global ip address {} is invalid. Please enter a valid global ip address !!".format(global_ip))

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    table = 'STATIC_NAT'
    key = global_ip
    dataKey = 'local_ip'
    
    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey] == local_ip:
            try:
                config_db.set_entry(table, key, None)
                entryFound = True
            except (JsonPatchConflict, JsonPointerException) as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    if entryFound is False:
        click.echo("Trying to delete static nat entry, which is not present.")


#
# 'nat remove static tcp' command ('config nat remove static tcp <global-ip> <global-port> <local-ip> <local-port>')
#
@static.command('tcp')
@click.pass_context
@click.argument('global_ip', metavar='<global_ip>', required=True)
@click.argument('global_port', metavar='<global_port>', type=click.IntRange(1, 65535), required=True)
@click.argument('local_ip', metavar='<local_ip>', required=True)
@click.argument('local_port', metavar='<local_port>', type=click.IntRange(1, 65535), required=True)
def remove_tcp(ctx, global_ip, global_port, local_ip, local_port):
    """Remove Static TCP Protocol NAPT-related configuration"""
    
    if ADHOC_VALIDATION:
        # Verify the ip address format 
        if is_valid_ipv4_address(local_ip) is False:
            ctx.fail("Given local ip address {} is invalid. Please enter a valid local ip address !!".format(local_ip))

        if is_valid_ipv4_address(global_ip) is False:
            ctx.fail("Given global ip address {} is invalid. Please enter a valid global ip address !!".format(global_ip))

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    table = "STATIC_NAPT"
    key = "{}|TCP|{}".format(global_ip, global_port)

    data = config_db.get_entry(table, key)
    if data:
        if data['local_ip'] == local_ip and data['local_port'] == str(local_port):
            try:
                config_db.set_entry(table, key, None)
                entryFound = True
            except (JsonPatchConflict, JsonPointerException) as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    if entryFound is False:
        click.echo("Trying to delete static napt entry, which is not present.")

#
# 'nat remove static udp' command ('config nat remove static udp <local-ip> <local-port> <global-ip> <global-port>')
#
@static.command('udp')
@click.pass_context
@click.argument('global_ip', metavar='<global_ip>', required=True)
@click.argument('global_port', metavar='<global_port>', type=click.IntRange(1, 65535), required=True)
@click.argument('local_ip', metavar='<local_ip>', required=True)
@click.argument('local_port', metavar='<local_port>', type=click.IntRange(1, 65535), required=True)
def remove_udp(ctx, global_ip, global_port, local_ip, local_port):
    """Remove Static UDP Protocol NAPT-related configuration"""
    
    if ADHOC_VALIDATION:
        # Verify the ip address format 
        if is_valid_ipv4_address(local_ip) is False:
            ctx.fail("Given local ip address {} is invalid. Please enter a valid local ip address !!".format(local_ip))

        if is_valid_ipv4_address(global_ip) is False:
            ctx.fail("Given global ip address {} is invalid. Please enter a valid global ip address !!".format(global_ip))

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    table = "STATIC_NAPT"
    key = "{}|UDP|{}".format(global_ip, global_port)
    dataKey1 = 'local_ip'
    dataKey2 = 'local_port'

    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey1] == local_ip and data[dataKey2] == str(local_port):
            try:
                config_db.set_entry(table, key, None)
                entryFound = True
            except (JsonPatchConflict, JsonPointerException) as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    if entryFound is False:
        click.echo("Trying to delete static napt entry, which is not present.")

#
# 'nat remove static all' command ('config nat remove static all')
#
@static.command('all')
@click.pass_context
def remove_static_all(ctx):
    """Remove all Static related configuration"""

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    tables = ['STATIC_NAT', 'STATIC_NAPT']

    for table_name in tables:
        table_dict = config_db.get_table(table_name)
        if table_dict:
            for table_key_name in table_dict:
                try:
                    config_db.set_entry(table_name, table_key_name, None)
                except (JsonPatchConflict, JsonPointerException) as e:
                    ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat add pool' command ('config nat add pool <pool_name> <global_ip> <global_port_range>')
#
@add.command('pool')
@click.pass_context
@click.argument('pool_name', metavar='<pool_name>', required=True)
@click.argument('global_ip_range', metavar='<global_ip_range>', required=True)
@click.argument('global_port_range', metavar='<global_port_range>', required=False)
def add_pool(ctx, pool_name, global_ip_range, global_port_range):
    """Add Pool for Dynamic NAT-related configuration"""

    if len(pool_name) > 32:
        ctx.fail("Invalid pool name. Maximum allowed pool name is 32 characters !!")

    # Verify the ip address range and format
    ip_address = global_ip_range.split("-")
    if len(ip_address) > 2:
        ctx.fail("Given ip address range {} is invalid. Please enter a valid ip address range !!".format(global_ip_range))
    elif len(ip_address) == 2:
        if is_valid_ipv4_address(ip_address[0]) is False:
            ctx.fail("Given ip address {} is not valid global address. Please enter a valid ip address !!".format(ip_address[0]))

        if is_valid_ipv4_address(ip_address[1]) is False:
            ctx.fail("Given ip address {} is not valid global address. Please enter a valid ip address !!".format(ip_address[1]))

        ipLowLimit = int(ipaddress.IPv4Address(ip_address[0]))
        ipHighLimit = int(ipaddress.IPv4Address(ip_address[1]))
        if ipLowLimit >= ipHighLimit:
            ctx.fail("Given ip address range {} is invalid. Please enter a valid ip address range !!".format(global_ip_range))
    else:
        if is_valid_ipv4_address(ip_address[0]) is False:
            ctx.fail("Given ip address {} is not valid global address. Please enter a valid ip address !!".format(ip_address[0]))
        ipLowLimit = int(ipaddress.IPv4Address(ip_address[0]))
        ipHighLimit = int(ipaddress.IPv4Address(ip_address[0]))

    # Verify the port address range and format
    if global_port_range is not None:   
        port_address = global_port_range.split("-")

        if len(port_address) > 2:
            ctx.fail("Given port address range {} is invalid. Please enter a valid port address range !!".format(global_port_range))
        elif len(port_address) == 2:
            if is_valid_port_address(port_address[0]) is False:
                ctx.fail("Given port value {} is invalid. Please enter a valid port value !!".format(port_address[0]))

            if is_valid_port_address(port_address[1]) is False:
                ctx.fail("Given port value {} is invalid. Please enter a valid port value !!".format(port_address[1]))

            portLowLimit = int(port_address[0])
            portHighLimit = int(port_address[1])
            if portLowLimit >= portHighLimit:
                ctx.fail("Given port address range {} is invalid. Please enter a valid port address range !!".format(global_port_range))
        else:
            if is_valid_port_address(port_address[0]) is False:
                ctx.fail("Given port value {} is invalid. Please enter a valid port value !!".format(port_address[0]))
    else:
        global_port_range = "NULL"

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    table = "NAT_POOL"
    key = pool_name
    dataKey1 = 'nat_ip'
    dataKey2 = 'nat_port'

    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey1] == global_ip_range and data[dataKey2] == global_port_range:
            click.echo("Trying to add pool, which is already present.")
            entryFound = True

    pool_dict = config_db.get_table(table)    
    if len(pool_dict) == 16:
        click.echo("Failed to add pool, as already reached maximum pool limit 16.")
        entryFound = True

    # Verify the Ip address is overlapping with any Static NAT entry
    if entryFound == False:
        static_dict = config_db.get_table('STATIC_NAT')
        if static_dict:
            for staticKey, staticValues in static_dict.items():
                global_ip = "---"
                local_ip = "---"
                nat_type = "dnat"

                if isinstance(staticKey, str) is True:
                    global_ip = staticKey
                else:
                    continue

                local_ip = staticValues["local_ip"]

                if "nat_type" in staticValues:
                    nat_type = staticValues["nat_type"]

                if nat_type == "snat":
                    global_ip = local_ip

                ipAddress = int(ipaddress.IPv4Address(global_ip))
                if (ipAddress >= ipLowLimit and ipAddress <= ipHighLimit):
                    ctx.fail("Given Ip address entry is overlapping with existing Static NAT entry !!")

    if entryFound == False:
        try:
            config_db.set_entry(table, key, {dataKey1: global_ip_range, dataKey2 : global_port_range})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat add binding' command ('config nat add binding <binding_name> <pool_name> <acl_name>')
#
@add.command('binding')
@click.pass_context
@click.argument('binding_name', metavar='<binding_name>', required=True)
@click.argument('pool_name', metavar='<pool_name>', required=True)
@click.argument('acl_name', metavar='<acl_name>', required=False)
@click.option('-nat_type', metavar='<nat_type>', required=False, type=click.Choice(["snat", "dnat"]), help="Set nat type")
@click.option('-twice_nat_id', metavar='<twice_nat_id>', required=False, type=click.IntRange(1, 9999), help="Set the twice nat id")
def add_binding(ctx, binding_name, pool_name, acl_name, nat_type, twice_nat_id):
    """Add Binding for Dynamic NAT-related configuration"""

    entryFound = False
    table = 'NAT_BINDINGS'
    key = binding_name
    dataKey1 = 'access_list'
    dataKey2 = 'nat_pool'
    dataKey3 = 'nat_type'
    dataKey4 = 'twice_nat_id'

    if acl_name is None:
        acl_name = ""

    if len(binding_name) > 32:
        ctx.fail("Invalid binding name. Maximum allowed binding name is 32 characters !!")

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    data = config_db.get_entry(table, key)
    if data:
        if data[dataKey1] == acl_name and data[dataKey2] == pool_name:
            click.echo("Trying to add binding, which is already present.")
            entryFound = True

    binding_dict = config_db.get_table(table)
    if len(binding_dict) == 16:
        click.echo("Failed to add binding, as already reached maximum binding limit 16.")
        entryFound = True

    if nat_type is not None:
        if nat_type == "dnat":
            click.echo("Ignored, DNAT is not yet supported for Binding ")
            entryFound = True
    else:
        nat_type = "snat"

    if twice_nat_id is None:
        twice_nat_id = "NULL"

    if entryFound is False:
        count = 0
        if twice_nat_id is not None:
            count = getTwiceNatIdCountWithStaticEntries(twice_nat_id, 'STATIC_NAT', count)
            count = getTwiceNatIdCountWithStaticEntries(twice_nat_id, 'STATIC_NAPT', count)
            count = getTwiceNatIdCountWithDynamicBinding(twice_nat_id, count, key)
            if count > 1:
                ctx.fail("Same Twice nat id is not allowed for more than 2 entries!!")

        try:
            config_db.set_entry(table, key, {dataKey1: acl_name, dataKey2: pool_name, dataKey3: nat_type, dataKey4: twice_nat_id})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove pool' command ('config nat remove pool <pool_name>')
#
@remove.command('pool')
@click.pass_context
@click.argument('pool_name', metavar='<pool_name>', required=True)
def remove_pool(ctx, pool_name):
    """Remove Pool for Dynamic NAT-related configuration"""
 
    entryFound = False
    table = "NAT_POOL"
    key = pool_name

    if len(pool_name) > 32:
        ctx.fail("Invalid pool name. Maximum allowed pool name is 32 characters !!")

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    data = config_db.get_entry(table, key)
    if not data:
        click.echo("Trying to delete pool, which is not present.")
        entryFound = True

    binding_dict = config_db.get_table('NAT_BINDINGS')
    if binding_dict and entryFound == False:    
        for binding_name, binding_values in binding_dict.items():
            if binding_values['nat_pool'] == pool_name:
                click.echo("Pool is not removed, as it is mapped to Binding {}, remove the pool binding first !!".format(binding_name))
                entryFound = True
                break

    if entryFound == False:
        try:
            config_db.set_entry(table, key, None)
        except (JsonPatchConflict, JsonPointerException) as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove pools' command ('config nat remove pools')
#
@remove.command('pools')
@click.pass_context
def remove_pools(ctx):
    """Remove all Pools for Dynamic configuration"""

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    entryFound = False
    pool_table_name = 'NAT_POOL'
    binding_table_name = 'NAT_BINDINGS'
    binding_dict = config_db.get_table(binding_table_name)
    pool_dict = config_db.get_table(pool_table_name)
    if pool_dict:
        for pool_key_name in pool_dict:
            entryFound = False
            for binding_name, binding_values in binding_dict.items():
                if binding_values['nat_pool'] == pool_key_name:
                    click.echo("Pool {} is not removed, as it is mapped to Binding {}, remove the pool binding first !!".format(pool_key_name,binding_name))
                    entryFound = True
                    break

            if entryFound == False:
                try:
                    config_db.set_entry(pool_table_name, pool_key_name, None)
                except (JsonPatchConflict, JsonPointerException) as e:
                    ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove binding' command ('config nat remove binding <binding_name>')
#
@remove.command('binding')
@click.pass_context
@click.argument('binding_name', metavar='<binding_name>', required=True)
def remove_binding(ctx, binding_name):
    """Remove Binding for Dynamic NAT-related configuration"""

    entryFound = False
    table = 'NAT_BINDINGS'
    key = binding_name

    if len(binding_name) > 32:
        ctx.fail("Invalid binding name. Maximum allowed binding name is 32 characters !!")

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    data = config_db.get_entry(table, key)
    if not data:
        click.echo("Trying to delete binding, which is not present.")
        entryFound = True

    if entryFound == False:
        try:
            config_db.set_entry(table, key, None)
        except (JsonPatchConflict, JsonPointerException) as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove bindings' command ('config nat remove bindings')
#
@remove.command('bindings')
@click.pass_context
def remove_bindings(ctx):
    """Remove all Bindings for Dynamic configuration"""

    config_db = ValidatedConfigBConnector(ConfigDBConnector())
    config_db.connect()

    binding_table_name = 'NAT_BINDINGS'
    binding_dict = config_db.get_table(binding_table_name)
    if binding_dict:
        for binding_key_name in binding_dict:
            try:
                config_db.set_entry(binding_table_name, binding_key_name, None)
            except (JsonPatchConflict, JsonPointerException) as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat add interface' command ('config nat add interface <interface_name> -nat_zone <zone-value>')
#
@add.command('interface')
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('-nat_zone', metavar='<nat_zone>', required=True, type=click.IntRange(0, 3), help="Set nat zone")
def add_interface(ctx, interface_name, nat_zone):
    """Add interface related nat configuration"""

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    if nat_interface_name_is_valid(interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a  valid interface name!!")

    if interface_name.startswith("Ethernet"):
        interface_table_type = "INTERFACE"
    elif interface_name.startswith("PortChannel"):
        interface_table_type = "PORTCHANNEL_INTERFACE"
    elif interface_name.startswith("Vlan"):
        interface_table_type = "VLAN_INTERFACE"
    elif interface_name.startswith("Loopback"):
        interface_table_type = "LOOPBACK_INTERFACE"

    interface_table_dict = config_db.get_table(interface_table_type)

    if not interface_table_dict or interface_name not in interface_table_dict:
        ctx.fail("Interface table is not present. Please configure ip-address on {} and apply the nat zone !!".format(interface_name))

    try:
        config_db.mod_entry(interface_table_type, interface_name, {"nat_zone": nat_zone})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove interface' command ('config nat remove interface <interface_name>')
#
@remove.command('interface')
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
def remove_interface(ctx, interface_name):
    """Remove interface related NAT configuration"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    if nat_interface_name_is_valid(interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a  valid interface name!!")

    if interface_name.startswith("Ethernet"):
        interface_table_type = "INTERFACE"
    elif interface_name.startswith("PortChannel"):
        interface_table_type = "PORTCHANNEL_INTERFACE"
    elif interface_name.startswith("Vlan"):
        interface_table_type = "VLAN_INTERFACE"
    elif interface_name.startswith("Loopback"):
        interface_table_type = "LOOPBACK_INTERFACE"

    interface_table_dict = config_db.get_table(interface_table_type)

    if not interface_table_dict or interface_name not in interface_table_dict:
        ctx.fail("Interface table is not present. Ignoring the nat zone configuration")

    try:
        config_db.mod_entry(interface_table_type, interface_name, {"nat_zone": "0"})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat remove interfaces' command ('config nat remove interfaces')
#
@remove.command('interfaces')
@click.pass_context
def remove_interfaces(ctx):
    """Remove all interface related NAT configuration"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    tables = ['INTERFACE', 'PORTCHANNEL_INTERFACE', 'VLAN_INTERFACE', 'LOOPBACK_INTERFACE']
    nat_config = {"nat_zone": "0"}

    for table_name in tables:
        table_dict = config_db.get_table(table_name)
        if table_dict:
            for table_key_name in table_dict:
                if isinstance(table_key_name, str) is False:
                    continue

                try:
                    config_db.set_entry(table_name, table_key_name, nat_config)
                except ValueError as e:
                    ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat feature' group ('config nat feature ')
#
@nat.group('feature')
def feature():
    """Enable or Disable the NAT feature"""
    pass

#
# 'nat feature enable' command ('config nat feature enable>')
#
@feature.command('enable')
@click.pass_context
def enable(ctx):
    """Enable the NAT feature """

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"admin_mode": "enabled"})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat feature disable' command ('config nat feature disable>')
#
@feature.command('disable')
@click.pass_context
def disable(ctx):
    """Disable the NAT feature """
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"admin_mode": "disabled"})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat set timeout' command ('config nat set timeout <seconds>')
#
@set.command('timeout')
@click.pass_context
@click.argument('seconds', metavar='<timeout in range of 300 to 432000 seconds>', type=click.IntRange(300, 432000), required=True)
def timeout(ctx, seconds):
    """Set NAT timeout configuration"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"nat_timeout": seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat set tcp-timeout' command ('config nat set tcp-timeout <seconds>')
#
@set.command('tcp-timeout')
@click.pass_context
@click.argument('seconds', metavar='<timeout in range of 300 to 432000 seconds>', type=click.IntRange(300, 432000), required=True)
def tcp_timeout(ctx, seconds):
    """Set NAT TCP timeout configuration"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"nat_tcp_timeout": seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat set udp-timeout' command ('config nat set udp-timeout <seconds>')
#
@set.command('udp-timeout')
@click.pass_context
@click.argument('seconds', metavar='<timeout in range of 120 to 600 seconds>', type=click.IntRange(120, 600), required=True)
def udp_timeout(ctx, seconds):
    """Set NAT UDP timeout configuration"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()

    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"nat_udp_timeout": seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat reset timeout' command ('config nat reset timeout')
#
@reset.command('timeout')
@click.pass_context
def timeout(ctx):
    """Reset NAT timeout configuration to default value (600 seconds)"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    seconds = 600
    
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"nat_timeout": seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat reset tcp-timeout' command ('config nat reset tcp-timeout')
#
@reset.command('tcp-timeout')
@click.pass_context
def tcp_timeout(ctx):
    """Reset NAT TCP timeout configuration to default value (86400 seconds)"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    seconds = 86400
    
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"nat_tcp_timeout": seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'nat reset udp-timeout' command ('config nat reset udp-timeout')
#
@reset.command('udp-timeout')
@click.pass_context
def udp_timeout(ctx):
    """Reset NAT UDP timeout configuration to default value (300 seconds)"""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    seconds = 300
    
    try:
        config_db.mod_entry("NAT_GLOBAL", "Values", {"nat_udp_timeout": seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))
