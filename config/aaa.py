import click
import ipaddress
import re
from swsscommon.swsscommon import ConfigDBConnector
from .validated_config_db_connector import ValidatedConfigDBConnector
from jsonpatch import JsonPatchConflict
from jsonpointer import JsonPointerException
import utilities_common.cli as clicommon

ADHOC_VALIDATION = True
RADIUS_MAXSERVERS = 8
RADIUS_PASSKEY_MAX_LEN = 65
VALID_CHARS_MSG = "Valid chars are ASCII printable except SPACE, '#', and ','"

def is_secret(secret):
    return bool(re.match('^' + '[^ #,]*' + '$', secret))


def add_table_kv(table, entry, key, val):
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.mod_entry(table, entry, {key:val})
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


def del_table_key(table, entry, key):
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    data = config_db.get_entry(table, entry)
    if data:
        if key in data:
            del data[key]
        try:
            config_db.set_entry(table, entry, data)
        except (ValueError, JsonPatchConflict) as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@click.group()
def aaa():
    """AAA command line"""
    pass


# cmd: aaa authentication
@click.group()
def authentication():
    """User authentication"""
    pass
aaa.add_command(authentication)


# cmd: aaa authentication failthrough
@click.command()
@click.argument('option', type=click.Choice(["enable", "disable", "default"]))
def failthrough(option):
    """Allow AAA fail-through [enable | disable | default]"""
    if option == 'default':
        del_table_key('AAA', 'authentication', 'failthrough')
    else:
        if option == 'enable':
            add_table_kv('AAA', 'authentication', 'failthrough', True)
        elif option == 'disable':
            add_table_kv('AAA', 'authentication', 'failthrough', False)
authentication.add_command(failthrough)


# cmd: aaa authentication fallback
@click.command()
@click.argument('option', type=click.Choice(["enable", "disable", "default"]))
def fallback(option):
    """Allow AAA fallback [enable | disable | default]"""
    if option == 'default':
        del_table_key('AAA', 'authentication', 'fallback')
    else:
        if option == 'enable':
            add_table_kv('AAA', 'authentication', 'fallback', True)
        elif option == 'disable':
            add_table_kv('AAA', 'authentication', 'fallback', False)
authentication.add_command(fallback)


# cmd: aaa authentication debug
@click.command()
@click.argument('option', type=click.Choice(["enable", "disable", "default"]))
def debug(option):
    """AAA debug [enable | disable | default]"""
    if option == 'default':
        del_table_key('AAA', 'authentication', 'debug')
    else:
        if option == 'enable':
            add_table_kv('AAA', 'authentication', 'debug', True)
        elif option == 'disable':
            add_table_kv('AAA', 'authentication', 'debug', False)
authentication.add_command(debug)


# cmd: aaa authentication trace
@click.command()
@click.argument('option', type=click.Choice(["enable", "disable", "default"]))
def trace(option):
    """AAA packet trace [enable | disable | default]"""
    if option == 'default':
        del_table_key('AAA', 'authentication', 'trace')
    else:
        if option == 'enable':
            add_table_kv('AAA', 'authentication', 'trace', True)
        elif option == 'disable':
            add_table_kv('AAA', 'authentication', 'trace', False)
authentication.add_command(trace)


@click.command()
@click.argument('auth_protocol', nargs=-1, type=click.Choice(["ldap", "radius", "tacacs+", "local", "default"]))
def login(auth_protocol):
    """Switch login authentication [ {ldap, radius, tacacs+, local} | default ]"""
    if len(auth_protocol) is 0:
        click.echo('Argument "auth_protocol" is required')
        return
    elif len(auth_protocol) > 2:
        click.echo('Not a valid command.')
        return

    if 'default' in auth_protocol:
        if len(auth_protocol) !=1:
            click.echo('Not a valid command')
            return
        del_table_key('AAA', 'authentication', 'login')
    else:
        val = auth_protocol[0]
        if len(auth_protocol) == 2:
            val2 = auth_protocol[1]
            good_ap = False
            if val == 'local':
                if val2 == 'radius' or val2 == 'tacacs+' or val2 == 'ldap':
                    good_ap = True
            elif val == 'radius' or val == 'tacacs+' or val == 'ldap':
                if val2 == 'local':
                    good_ap = True
            if good_ap == True:
                val += ',' + val2
            else:
                click.echo('Not a valid command')
                return

        add_table_kv('AAA', 'authentication', 'login', val)
authentication.add_command(login)

# cmd: aaa authorization
@click.command()
@click.argument('protocol', nargs=-1, type=click.Choice([ "tacacs+", "local", "tacacs+ local"]))
def authorization(protocol):
    """Switch AAA authorization [tacacs+ | local | '\"tacacs+ local\"']"""
    if len(protocol) == 0:
        click.echo('Argument "protocol" is required')
        return

    if len(protocol) == 1 and (protocol[0] == 'tacacs+' or protocol[0] == 'local'):
        add_table_kv('AAA', 'authorization', 'login', protocol[0])
    elif len(protocol) == 1 and protocol[0] == 'tacacs+ local':
        add_table_kv('AAA', 'authorization', 'login', 'tacacs+,local')
    else:
        click.echo('Not a valid command')
aaa.add_command(authorization)

# cmd: aaa accounting
@click.command()
@click.argument('protocol', nargs=-1, type=click.Choice(["disable", "tacacs+", "local", "tacacs+ local"]))
def accounting(protocol):
    """Switch AAA accounting [disable | tacacs+ | local | '\"tacacs+ local\"']"""
    if len(protocol) == 0:
        click.echo('Argument "protocol" is required')
        return

    if len(protocol) == 1:
        if protocol[0] == 'tacacs+' or protocol[0] == 'local':
            add_table_kv('AAA', 'accounting', 'login', protocol[0])
        elif protocol[0] == 'tacacs+ local':
            add_table_kv('AAA', 'accounting', 'login', 'tacacs+,local')
        elif protocol[0] == 'disable':
            del_table_key('AAA', 'accounting', 'login')
        else:
            click.echo('Not a valid command')
    else:
        click.echo('Not a valid command')
aaa.add_command(accounting)

@click.group()
def tacacs():
    """TACACS+ server configuration"""
    pass


@click.group()
@click.pass_context
def default(ctx):
    """set its default configuration"""
    ctx.obj = 'default'
tacacs.add_command(default)


@click.command()
@click.argument('second', metavar='<time_second>', type=click.IntRange(0, 60), required=False)
@click.pass_context
def timeout(ctx, second):
    """Specify TACACS+ server global timeout <0 - 60>"""
    if ctx.obj == 'default':
        del_table_key('TACPLUS', 'global', 'timeout')
    elif second:
        add_table_kv('TACPLUS', 'global', 'timeout', second)
    else:
        click.echo('Argument "second" is required')
tacacs.add_command(timeout)
default.add_command(timeout)


@click.command()
@click.argument('type', metavar='<type>', type=click.Choice(["chap", "pap", "mschap", "login"]), required=False)
@click.pass_context
def authtype(ctx, type):
    """Specify TACACS+ server global auth_type [chap | pap | mschap | login]"""
    if ctx.obj == 'default':
        del_table_key('TACPLUS', 'global', 'auth_type')
    elif type:
        add_table_kv('TACPLUS', 'global', 'auth_type', type)
    else:
        click.echo('Argument "type" is required')
tacacs.add_command(authtype)
default.add_command(authtype)


@click.command()
@click.argument('secret', metavar='<secret_string>', required=False)
@click.pass_context
def passkey(ctx, secret):
    """Specify TACACS+ server global passkey <STRING>"""
    if ctx.obj == 'default':
        del_table_key('TACPLUS', 'global', 'passkey')
    elif secret:
        add_table_kv('TACPLUS', 'global', 'passkey', secret)
    else:
        click.echo('Argument "secret" is required')
tacacs.add_command(passkey)
default.add_command(passkey)


# cmd: tacacs add <ip_address> --timeout SECOND --key SECRET --type TYPE --port PORT --pri PRIORITY
@click.command()
@click.argument('address', metavar='<ip_address>')
@click.option('-t', '--timeout', help='Transmission timeout interval, default 5', type=int)
@click.option('-k', '--key', help='Shared secret')
@click.option('-a', '--auth_type', help='Authentication type, default pap', type=click.Choice(["chap", "pap", "mschap", "login"]))
@click.option('-o', '--port', help='TCP port range is 1 to 65535, default 49', type=click.IntRange(1, 65535), default=49)
@click.option('-p', '--pri', help="Priority, default 1", type=click.IntRange(1, 64), default=1)
@click.option('-m', '--use-mgmt-vrf', help="Management vrf, default is no vrf", is_flag=True)
def add(address, timeout, key, auth_type, port, pri, use_mgmt_vrf):
    """Specify a TACACS+ server"""
    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(address):
            click.echo('Invalid ip address') # TODO: MISSING CONSTRAINT IN YANG MODEL
            return

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    old_data = config_db.get_entry('TACPLUS_SERVER', address)
    if old_data != {}:
        click.echo('server %s already exists' % address)
    else:
        data = {
            'tcp_port': str(port),
            'priority': pri
        }
        if auth_type is not None:
            data['auth_type'] = auth_type
        if timeout is not None:
            data['timeout'] = str(timeout)
        if key is not None:
            data['passkey'] = key
        if use_mgmt_vrf :
            data['vrf'] = "mgmt"
        try:
            config_db.set_entry('TACPLUS_SERVER', address, data)
        except ValueError as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ip address. Error: {}".format(e))
tacacs.add_command(add)


# cmd: tacacs delete <ip_address>
# 'del' is keyword, replace with 'delete'
@click.command()
@click.argument('address', metavar='<ip_address>')
def delete(address):
    """Delete a TACACS+ server"""
    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(address):
            click.echo('Invalid ip address')
            return

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.set_entry('TACPLUS_SERVER', address, None)
    except JsonPatchConflict as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ip address. Error: {}".format(e))
tacacs.add_command(delete)


@click.group()
def radius():
    """RADIUS server configuration"""
    pass


@click.group()
@click.pass_context
def default(ctx):
    """set its default configuration"""
    ctx.obj = 'default'
radius.add_command(default)


@click.command()
@click.argument('second', metavar='<time_second>', type=click.IntRange(1, 60), required=False)
@click.pass_context
def timeout(ctx, second):
    """Specify RADIUS server global timeout <1 - 60>"""
    if ctx.obj == 'default':
        del_table_key('RADIUS', 'global', 'timeout')
    elif second:
        add_table_kv('RADIUS', 'global', 'timeout', second)
    else:
        click.echo('Not support empty argument')
radius.add_command(timeout)
default.add_command(timeout)


@click.command()
@click.argument('retries', metavar='<retry_attempts>', type=click.IntRange(0, 10), required=False)
@click.pass_context
def retransmit(ctx, retries):
    """Specify RADIUS server global retry attempts <0 - 10>"""
    if ctx.obj == 'default':
        del_table_key('RADIUS', 'global', 'retransmit')
    elif retries != None:
        add_table_kv('RADIUS', 'global', 'retransmit', retries)
    else:
        click.echo('Not support empty argument')
radius.add_command(retransmit)
default.add_command(retransmit)


@click.command()
@click.argument('type', metavar='<type>', type=click.Choice(["chap", "pap", "mschapv2"]), required=False)
@click.pass_context
def authtype(ctx, type):
    """Specify RADIUS server global auth_type [chap | pap | mschapv2]"""
    if ctx.obj == 'default':
        del_table_key('RADIUS', 'global', 'auth_type')
    elif type:
        add_table_kv('RADIUS', 'global', 'auth_type', type)
    else:
        click.echo('Not support empty argument')
radius.add_command(authtype)
default.add_command(authtype)


@click.command()
@click.argument('secret', metavar='<secret_string>', required=False)
@click.pass_context
def passkey(ctx, secret):
    """Specify RADIUS server global passkey <STRING>"""
    if ctx.obj == 'default':
        del_table_key('RADIUS', 'global', 'passkey')
    elif secret:
        if len(secret) > RADIUS_PASSKEY_MAX_LEN:
            click.echo('Maximum of %d chars can be configured' % RADIUS_PASSKEY_MAX_LEN)
            return
        elif not is_secret(secret):
            click.echo(VALID_CHARS_MSG)
            return
        add_table_kv('RADIUS', 'global', 'passkey', secret)
    else:
        click.echo('Not support empty argument')
radius.add_command(passkey)
default.add_command(passkey)

@click.command()
@click.argument('src_ip', metavar='<source_ip>', required=False)
@click.pass_context
def sourceip(ctx, src_ip):
    """Specify RADIUS server global source ip <IPAddress>"""
    if ctx.obj == 'default':
        del_table_key('RADIUS', 'global', 'src_ip')
        return
    elif not src_ip:
        click.echo('Not support empty argument')
        return

    if not clicommon.is_ipaddress(src_ip):
        click.echo('Invalid ip address')
        return

    v6_invalid_list = [ipaddress.IPv6Address('0::0'), ipaddress.IPv6Address('0::1')]
    net = ipaddress.ip_network(src_ip, strict=False)
    if (net.version == 4):
        if src_ip == "0.0.0.0":
            click.echo('enter non-zero ip address')
            return
        ip = ipaddress.IPv4Address(src_ip)
        if ip.is_reserved:
            click.echo('Reserved ip is not valid')
            return
        if ip.is_multicast:
            click.echo('Multicast ip is not valid')
            return
    elif (net.version == 6):
        ip = ipaddress.IPv6Address(src_ip)
        if (ip.is_multicast):
            click.echo('Multicast ip is not valid')
            return
        if (ip in v6_invalid_list):
            click.echo('Invalid ip address')
            return
    add_table_kv('RADIUS', 'global', 'src_ip', src_ip)
radius.add_command(sourceip)
default.add_command(sourceip)

@click.command()
@click.argument('nas_ip', metavar='<nas_ip>', required=False)
@click.pass_context
def nasip(ctx, nas_ip):
    """Specify RADIUS server global NAS-IP|IPV6-Address <IPAddress>"""
    if ctx.obj == 'default':
        del_table_key('RADIUS', 'global', 'nas_ip')
        return
    elif not nas_ip:
        click.echo('Not support empty argument')
        return

    if not clicommon.is_ipaddress(nas_ip):
        click.echo('Invalid ip address')
        return

    v6_invalid_list = [ipaddress.IPv6Address('0::0'), ipaddress.IPv6Address('0::1')]
    net = ipaddress.ip_network(nas_ip, strict=False)
    if (net.version == 4):
        if nas_ip == "0.0.0.0":
            click.echo('enter non-zero ip address')
            return
        ip = ipaddress.IPv4Address(nas_ip)
        if ip.is_reserved:
            click.echo('Reserved ip is not valid')
            return
        if ip.is_multicast:
            click.echo('Multicast ip is not valid')
            return
    elif (net.version == 6):
        ip = ipaddress.IPv6Address(nas_ip)
        if (ip.is_multicast):
            click.echo('Multicast ip is not valid')
            return
        if (ip in v6_invalid_list):
            click.echo('Invalid ip address')
            return
    add_table_kv('RADIUS', 'global', 'nas_ip', nas_ip)
radius.add_command(nasip)
default.add_command(nasip)

@click.command()
@click.argument('option', type=click.Choice(["enable", "disable", "default"]))
def statistics(option):
    """Specify RADIUS server global statistics [enable | disable | default]"""
    if option == 'default':
        del_table_key('RADIUS', 'global', 'statistics')
    else:
        if option == 'enable':
            add_table_kv('RADIUS', 'global', 'statistics', 'true')
        elif option == 'disable':
            add_table_kv('RADIUS', 'global', 'statistics', 'false')
radius.add_command(statistics)


# cmd: radius add <ip_address_or_domain_name> --retransmit COUNT --timeout SECOND --key SECRET --type TYPE --auth-port PORT --pri PRIORITY
@click.command()
@click.argument('address', metavar='<ip_address_or_domain_name>')
@click.option('-r', '--retransmit', help='Retransmit attempts, default 3', type=click.IntRange(1, 10))
@click.option('-t', '--timeout', help='Transmission timeout interval, default 5', type=click.IntRange(1, 60))
@click.option('-k', '--key', help='Shared secret')
@click.option('-a', '--auth_type', help='Authentication type, default pap', type=click.Choice(["chap", "pap", "mschapv2"]))
@click.option('-o', '--auth-port', help='UDP port range is 1 to 65535, default 1812', type=click.IntRange(1, 65535), default=1812)
@click.option('-p', '--pri', help="Priority, default 1", type=click.IntRange(1, 64), default=1)
@click.option('-m', '--use-mgmt-vrf', help="Management vrf, default is no vrf", is_flag=True)
@click.option('-s', '--source-interface', help='Source Interface')
def add(address, retransmit, timeout, key, auth_type, auth_port, pri, use_mgmt_vrf, source_interface):
    """Specify a RADIUS server"""

    if ADHOC_VALIDATION:
        if key:
            if len(key) > RADIUS_PASSKEY_MAX_LEN:
                click.echo('--key: Maximum of %d chars can be configured' % RADIUS_PASSKEY_MAX_LEN)
                return
            elif not is_secret(key):
                click.echo('--key: ' + VALID_CHARS_MSG)
                return

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    old_data = config_db.get_table('RADIUS_SERVER')
    if address in old_data :
        click.echo('server %s already exists' % address)
        return
    if len(old_data) == RADIUS_MAXSERVERS:
        click.echo('Maximum of %d can be configured' % RADIUS_MAXSERVERS)
    else:
        data = {
            'auth_port': str(auth_port),
            'priority': pri
        }
        if auth_type is not None:
            data['auth_type'] = auth_type
        if retransmit is not None:
            data['retransmit'] = str(retransmit)
        if timeout is not None:
            data['timeout'] = str(timeout)
        if key is not None:
            data['passkey'] = key
        if use_mgmt_vrf :
            data['vrf'] = "mgmt"
        if ADHOC_VALIDATION:
            if source_interface :
                if (source_interface.startswith("Ethernet") or \
                    source_interface.startswith("PortChannel") or \
                    source_interface.startswith("Vlan") or \
                    source_interface.startswith("Loopback") or \
                    source_interface == "eth0"):
                    data['src_intf'] = source_interface
                else:
                    click.echo('Not supported interface name (valid interface name: Etherent<id>/PortChannel<id>/Vlan<id>/Loopback<id>/eth0)')
        else:
            if source_interface:
                data['src_intf'] = source_interface
        try:
            config_db.set_entry('RADIUS_SERVER', address, data)
        except ValueError as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
radius.add_command(add)


# cmd: radius delete <ip_address_or_domain_name>
# 'del' is keyword, replace with 'delete'
@click.command()
@click.argument('address', metavar='<ip_address_or_domain_name>')
def delete(address):
    """Delete a RADIUS server"""

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.set_entry('RADIUS_SERVER', address, None)
    except (JsonPointerException, JsonPatchConflict) as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))
radius.add_command(delete)
