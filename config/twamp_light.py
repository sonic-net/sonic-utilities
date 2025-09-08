import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import ConfigDBConnector
import ipaddress

from .utils import log

TWAMP_MODE_FULL = "FULL"
TWAMP_MODE_LIGHT = "LIGHT"
TWAMP_ROLE_SENDER = "SENDER"
TWAMP_ROLE_REFLECTOR = "REFLECTOR"
CFG_TWAMP_SESSION_TABLE_NAME = "TWAMP_SESSION"
STATE_TWAMP_SESSION_TABLE_NAME = "TWAMP_SESSION_TABLE"
TWAMP_SESSION_DEFAULT_SENDER_UDP_PORT = 862
TWAMP_SESSION_DEFAULT_REFLECTOR_UDP_PORT = 863


def check_if_twamp_session_exist(config_db, name):
    """ Check if TWAMP-Light session exits in the config db """
    if len(config_db.get_entry(CFG_TWAMP_SESSION_TABLE_NAME, name)) != 0:
        return True
    return False


def check_twamp_udp_port(udp_port):
    """ Check if TWAMP-Light session udp_port """
    udp_port = int(udp_port)
    if udp_port == TWAMP_SESSION_DEFAULT_SENDER_UDP_PORT:
        return True
    if udp_port == TWAMP_SESSION_DEFAULT_REFLECTOR_UDP_PORT:
        return True
    if udp_port in range(1025, 65535+1):
        return True
    return False


# TWAMP CLI param callback check ##################
def validate_twamp_session_exist_cb(ctx, param, name):
    """ Helper function to validate session name """
    config_db = ConfigDBConnector()
    config_db.connect()
    if check_if_twamp_session_exist(config_db, name) is True:
        raise click.UsageError('Invalid value for "<{}>": {}. '
                               'TWAMP-Light session already exists'.format(param.name, name))
    return name


def validate_twamp_session_cb(ctx, param, name):
    """ Helper function to validate session name """
    config_db = ConfigDBConnector()
    config_db.connect()
    if name == 'all':
        session_keys = config_db.get_table(CFG_TWAMP_SESSION_TABLE_NAME).keys()
        if len(session_keys) == 0:
            raise click.UsageError('Invalid value for "<{}>": {}. '
                                   'TWAMP-Light session does not exist'.format(param.name, name))
        return session_keys
    else:
        session_keys = name.split(",")
        for key in session_keys:
            if check_if_twamp_session_exist(config_db, key) is False:
                raise click.UsageError('Invalid value for "<{}>": {}.'
                                       ' TWAMP-Light session does not exist'.format(param.name, key))
        return session_keys


def validate_twamp_ip_port_cb(ctx, param, ip_port):
    """ Helper function to validate ip address and udp port """
    if ip_port.count(':') == 1:
        ip_addr, udp_port = ip_port.split(':')
        if check_twamp_udp_port(udp_port) is False:
            raise click.UsageError('Invalid value for "<{}>": {}. Valid udp port range in '
                                   '862|863|1025-65535'.format(param.name, udp_port))
    else:
        ip_addr = ip_port
        if TWAMP_ROLE_SENDER in param.name.upper():
            udp_port = TWAMP_SESSION_DEFAULT_SENDER_UDP_PORT
        else:
            udp_port = TWAMP_SESSION_DEFAULT_REFLECTOR_UDP_PORT

    try:
        ipaddress.ip_interface(ip_addr)
    except ValueError:
        raise click.UsageError('Invalid value for "<{}>": {}. Valid format in IPv4_address or '
                               'IPv4_address:udp_port'.format(param.name, ip_addr))

    return ip_addr, udp_port


# TWAMP-Light Configuration ##################
#
# 'twamp-light' group ('config twamp-light ...')
#
@click.group(cls=clicommon.AbbreviationGroup, name='twamp-light')
def twamp_light():
    """ TWAMP-Light related configuration tasks """
    pass


#
# 'twamp-light session-sender' group ('config twamp-light session-sender ...')
#
@twamp_light.group(cls=clicommon.AbbreviationGroup, name='session-sender')
def twamp_light_sender():
    """ TWAMP-Light session-sender related configutation tasks """
    pass


#
# 'twamp-light session-sender packet-count' group ('config twamp-light session-sender packet-count ...')
#
@twamp_light_sender.group('packet-count')
def twamp_light_sender_packet_count():
    """ TWAMP-Light session-sender packet-count mode """
    pass


#
# 'twamp-light session-sender packet-count add' command ('config twamp-light session-sender packet-count add ...')
#
@twamp_light_sender_packet_count.command('add')
@click.argument('session_name', metavar='<session_name>', required=True, callback=validate_twamp_session_exist_cb)
@click.argument('sender_ip_port', metavar='<sender_ip:port>', required=True, callback=validate_twamp_ip_port_cb)
@click.argument('reflector_ip_port', metavar='<reflector_ip:port>', required=True, callback=validate_twamp_ip_port_cb)
@click.argument('packet_count', metavar='<packet_count>',
                required=True, type=click.IntRange(min=100, max=30000), default=100)
@click.argument('tx_interval', metavar='<tx_interval>', required=True, type=click.Choice(['10', '100', '1000']),
                default='100')
@click.argument('timeout', metavar='<timeout>', required=True, type=click.IntRange(min=1, max=10), default=5)
@click.argument('statistics_interval', metavar='<statistics_interval>', required=False,
                type=click.IntRange(min=2000, max=3600000))
@click.option('--vrf', required=False, help='VRF Name')
@click.option('--dscp', required=False, type=click.IntRange(min=0, max=63), help='DSCP Value')
@click.option('--ttl', required=False, type=click.IntRange(min=1, max=255), help='TTL Value')
@click.option('--timestamp-format', required=False, type=click.Choice(['ntp', 'ptp']), help='Timestamp Format')
@clicommon.pass_db
def twamp_light_sender_packet_count_add(db, session_name, sender_ip_port, reflector_ip_port,
                                        packet_count, tx_interval, timeout, statistics_interval,
                                        vrf, dscp, ttl, timestamp_format):
    """ Add TWAMP-Light session-sender packet-count session """

    ctx = click.get_current_context()

    log.log_info("'twamp-light session-sender add packet-count {} {} {} {} {} {} {}' executing..."
                 .format(session_name, sender_ip_port, reflector_ip_port,
                         packet_count, tx_interval, timeout, statistics_interval))

    sender_ip, sender_udp_port = sender_ip_port
    reflector_ip, reflector_udp_port = reflector_ip_port

    if statistics_interval is None:
        statistics_interval = int(packet_count) * int(tx_interval) + int(timeout)*1000
    else:
        if int(statistics_interval) < int(tx_interval) + int(timeout)*1000:
            ctx.fail("Statistics interval must be bigger than tx_interval + timeout*1000")

    fvs = {
            'mode': TWAMP_MODE_LIGHT,
            'role': TWAMP_ROLE_SENDER,
            'src_ip': sender_ip,
            'dst_ip': reflector_ip,
            'src_udp_port': sender_udp_port,
            'dst_udp_port': reflector_udp_port,
            'packet_count': packet_count,
            'tx_interval': tx_interval,
            'timeout': timeout,
            'statistics_interval': statistics_interval
          }

    if vrf is not None:
        fvs['vrf_name'] = vrf
    if dscp is not None:
        fvs['dscp'] = dscp
    if ttl is not None:
        fvs['ttl'] = ttl
    if timestamp_format is not None:
        fvs['timestamp_format'] = timestamp_format

    db.cfgdb.set_entry(CFG_TWAMP_SESSION_TABLE_NAME, session_name, fvs)


#
# 'twamp-light session-sender continuous' group ('config twamp-light session-sender continuous ...')
#
@twamp_light_sender.group('continuous')
def twamp_light_sender_continuous():
    """ TWAMP-Light session-sender continuous mode """
    pass


#
# 'twamp-light session-sender continuous add' command ('config twamp-light session-sender continuous add ...')
#
@twamp_light_sender_continuous.command('add')
@click.argument('session_name', metavar='<session_name>', required=True, callback=validate_twamp_session_exist_cb)
@click.argument('sender_ip_port', metavar='<sender_ip:port>', required=True, callback=validate_twamp_ip_port_cb)
@click.argument('reflector_ip_port', metavar='<reflector_ip:port>', required=True, callback=validate_twamp_ip_port_cb)
@click.argument('monitor_time', metavar='<monitor_time>', required=True, type=click.INT, default=0)
@click.argument('tx_interval', metavar='<tx_interval>', required=True, type=click.Choice(['10', '100', '1000']),
                default='100')
@click.argument('timeout', metavar='<timeout>', required=True, type=click.IntRange(min=1, max=10), default=5)
@click.argument('statistics_interval', metavar='<statistics_interval>', required=False,
                type=click.IntRange(min=2000, max=3600000))
@click.option('--vrf', required=False, help='VRF Name')
@click.option('--dscp', required=False, type=click.IntRange(min=0, max=63), help='DSCP Value')
@click.option('--ttl', required=False, type=click.IntRange(min=1, max=255), help='TTL Value')
@click.option('--timestamp-format', required=False, type=click.Choice(['ntp', 'ptp']), help='Timestamp Format')
@clicommon.pass_db
def twamp_light_sender_continuous_add(db, session_name, sender_ip_port, reflector_ip_port,
                                      monitor_time, tx_interval, timeout, statistics_interval,
                                      vrf, dscp, ttl, timestamp_format):
    """ Add TWAMP-Light Session-Sender continuous session """

    ctx = click.get_current_context()

    log.log_info("'twamp-light session-sender add continuous {} {} {} {} {} {} {}' executing..."
                 .format(session_name, sender_ip_port, reflector_ip_port,
                         monitor_time, tx_interval, timeout, statistics_interval))

    sender_ip, sender_udp_port = sender_ip_port
    reflector_ip, reflector_udp_port = reflector_ip_port

    if statistics_interval is None:
        if int(monitor_time) == 0:
            ctx.fail("Statistics interval must be configured while monitor_time is 0(forever)")
        else:
            statistics_interval = int(monitor_time)*1000

    if int(statistics_interval) <= int(timeout)*1000:
        ctx.fail("Statistics interval must be bigger than timeout*1000")

    fvs = {
            'mode': TWAMP_MODE_LIGHT,
            'role': TWAMP_ROLE_SENDER,
            'src_ip': sender_ip,
            'dst_ip': reflector_ip,
            'src_udp_port': sender_udp_port,
            'dst_udp_port': reflector_udp_port,
            'monitor_time': monitor_time,
            'tx_interval': tx_interval,
            'timeout': timeout,
            'statistics_interval': statistics_interval
          }

    if vrf is not None:
        fvs['vrf_name'] = vrf
    if dscp is not None:
        fvs['dscp'] = dscp
    if ttl is not None:
        fvs['ttl'] = ttl
    if timestamp_format is not None:
        fvs['timestamp_format'] = timestamp_format

    db.cfgdb.set_entry(CFG_TWAMP_SESSION_TABLE_NAME, session_name, fvs)


#
# 'twamp-light session-sender start' command ('config twamp-light session-sender start ...')
#
@twamp_light_sender.command('start')
@click.argument('session_name', metavar='<session_name|all>', required=True, callback=validate_twamp_session_cb)
@clicommon.pass_db
def twamp_light_sender_start(db, session_name):
    """ Start TWAMP-Light session-sender session """

    log.log_info("'twamp-light session-sender start {}' executing...".format(session_name))

    session_keys = session_name

    for key in session_keys:
        fvs = {}
        fvs = db.cfgdb.get_entry(CFG_TWAMP_SESSION_TABLE_NAME, key)
        fvs['admin_state'] = 'enabled'

        db.cfgdb.set_entry(CFG_TWAMP_SESSION_TABLE_NAME, key, fvs)


#
# 'twamp-light session-sender stop' command ('config twamp-light session-sender stop ...')
#
@twamp_light_sender.command('stop')
@click.argument('session_name', metavar='<session_name|all>', required=True, callback=validate_twamp_session_cb)
@clicommon.pass_db
def twamp_light_sender_stop(db, session_name):
    """ Stop TWAMP-Light session-sender session """

    log.log_info("'twamp-light session-sender stop {}' executing...".format(session_name))

    session_keys = session_name

    for key in session_keys:
        fvs = {}
        fvs = db.cfgdb.get_entry(CFG_TWAMP_SESSION_TABLE_NAME, key)
        fvs['admin_state'] = 'disabled'

        db.cfgdb.set_entry(CFG_TWAMP_SESSION_TABLE_NAME, key, fvs)


#
# 'twamp-light session-reflector' group ('config twamp-light session-reflector ...')
#
@twamp_light.group(cls=clicommon.AbbreviationGroup, name='session-reflector')
def twamp_light_reflector():
    """ TWAMP-Light session-reflector related configutation tasks """
    pass


#
# 'twamp-light session-reflector add' command ('config twamp-light session-reflector add ...')
#
@twamp_light_reflector.command('add')
@click.argument('session_name', metavar='<session_name>', required=True, callback=validate_twamp_session_exist_cb)
@click.argument('sender_ip_port', metavar='<sender_ip:port>', required=True, callback=validate_twamp_ip_port_cb)
@click.argument('reflector_ip_port', metavar='<reflector_ip:port>', required=True, callback=validate_twamp_ip_port_cb)
@click.option('--vrf', required=False, help='VRF Name')
@click.option('--dscp', required=False, type=click.IntRange(min=0, max=63), help='DSCP Value')
@click.option('--ttl', required=False, type=click.IntRange(min=1, max=255), help='TTL Value')
@click.option('--timestamp-format', required=False, type=click.Choice(['ntp', 'ptp']), help="Timestamp Format")
@clicommon.pass_db
def twamp_light_reflector_add(db, session_name, sender_ip_port, reflector_ip_port,
                              vrf, dscp, ttl, timestamp_format):
    """ Add TWAMP-Light session-reflector session """

    log.log_info("'twamp-light add reflector {} {} {}' executing..."
                 .format(session_name, sender_ip_port, reflector_ip_port))

    sender_ip, sender_udp_port = sender_ip_port
    reflector_ip, reflector_udp_port = reflector_ip_port

    fvs = {
            'mode': TWAMP_MODE_LIGHT,
            'role': TWAMP_ROLE_REFLECTOR,
            'src_ip': sender_ip,
            'dst_ip': reflector_ip,
            'src_udp_port': sender_udp_port,
            'dst_udp_port': reflector_udp_port
            }

    if vrf is not None:
        fvs['vrf_name'] = vrf
    if dscp is not None:
        fvs['dscp'] = dscp
    if ttl is not None:
        fvs['ttl'] = ttl
    if timestamp_format is not None:
        fvs['timestamp_format'] = timestamp_format

    db.cfgdb.set_entry(CFG_TWAMP_SESSION_TABLE_NAME, session_name, fvs)


#
# 'twamp-light remove' command ('config twamp-light remove ...')
#
@twamp_light.command('remove')
@click.argument('session_name', metavar='<session_name|all>', required=True, callback=validate_twamp_session_cb)
@clicommon.pass_db
def twamp_light_remove(db, session_name):
    """ Remove TWAMP-Light session """

    log.log_info("'twamp-light remove {}' executing...".format(session_name))

    session_keys = session_name

    for key in session_keys:
        db.cfgdb.set_entry(CFG_TWAMP_SESSION_TABLE_NAME, key, None)
