import click

import json
import ipaddress
import subprocess

import utilities_common.cli as clicommon
from sonic_py_common import logger
from syslog_util import common as syslog_common


SYSLOG_TABLE_CDB = "SYSLOG_SERVER"

SYSLOG_SOURCE = "source"
SYSLOG_PORT = "port"
SYSLOG_VRF = "vrf"

VRF_TABLE_CDB = "VRF"
MGMT_VRF_TABLE_CDB = "MGMT_VRF_CONFIG"

MGMT_VRF_GLOBAL = "vrf_global"
MGMT_VRF_GLOBAL_ENABLED = "mgmtVrfEnabled"


log = logger.Logger()
log.set_min_log_priority_info()

#
# Syslog helpers ------------------------------------------------------------------------------------------------------
#

def exec_cmd(cmd):
    """ Execute shell command """
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT)


def get_vrf_list():
    """ Get Linux VRF device list """
    vrf_list = []
    vrf_data = json.loads(exec_cmd(['ip', '--json', 'vrf', 'show']))
    for vrf_entry in vrf_data:
        vrf_name = vrf_entry.get('name', None)
        if vrf_name is not None:
            vrf_list.append(vrf_name)
    return vrf_list


def get_vrf_member_dict():
    """ Get Linux VRF device to member dict """
    vrf_member_dict = {}
    vrf_list = get_vrf_list()
    for vrf_name in vrf_list:
        vrf_member_dict[vrf_name] = []
        vrf_member_data = json.loads(exec_cmd(['ip', '--json', 'link', 'show', 'vrf', vrf_name]))
        for vrf_member_entry in vrf_member_data:
            vrf_member_name = vrf_member_entry.get('ifname', None)
            if vrf_member_name is not None:
                vrf_member_dict[vrf_name].append(vrf_member_name)
    return vrf_member_dict


def get_ip_addr_dict():
    """ Get Linux interface to IPv4/IPv6 address list dict """
    ip_addr_dict = {}
    ip_addr_data = json.loads(exec_cmd(['ip', '--json', 'address', 'show']))
    for ip_addr_entry in ip_addr_data:
        link_name = ip_addr_entry.get('ifname', None)
        if link_name is not None:
            ip_addr_dict[link_name] = []
            ip_data = ip_addr_entry.get('addr_info', None)
            if ip_data is not None:
                for ip_entry in ip_data:
                    ip_addr = ip_entry.get('local', None)
                    if ip_addr is not None:
                        ip_addr_dict[link_name].append(ip_addr)
    return ip_addr_dict


def get_param(ctx, name):
    """ Get click parameter """
    for param in ctx.command.params:
        if param.name == name:
            return param
    return None


def get_param_hint(ctx, name):
    """ Get click parameter description """
    return get_param(ctx, name).get_error_hint(ctx)

#
# Syslog DB interface -------------------------------------------------------------------------------------------------
#

def add_entry(db, table, key, data):
    """ Add new entry in table """
    cfg = db.get_config()
    cfg.setdefault(table, {})

    if key in cfg[table]:
        raise click.ClickException("{}{}{} already exists in Config DB".format(
                table, db.TABLE_NAME_SEPARATOR, db.serialize_key(key)
            )
        )

    db.set_entry(table, key, data)


def del_entry(db, table, key):
    """ Delete entry in table """
    cfg = db.get_config()
    cfg.setdefault(table, {})

    if key not in cfg[table]:
        raise click.ClickException("{}{}{} doesn't exist in Config DB".format(
                table, db.TABLE_NAME_SEPARATOR, db.serialize_key(key)
            )
        )

    db.set_entry(table, key, None)


def is_exist_in_db(db, table, key):
    """
    Check if provided hash already exists in Config DB

    Args:
        db: reference to Config DB
        table: table to search in Config DB
        key: key to search in Config DB

    Returns:
        bool: The return value. True for success, False otherwise
    """
    if (not table) or (not key):
        return False

    if key not in db.get_keys(table):
        return False

    return True


def is_mgmt_vrf_enabled(db):
    """
    Check if management VRF is enabled in Config DB

    Args:
        db: reference to Config DB

    Returns:
        bool: The return value. True for success, False otherwise
    """
    entry = db.get_entry(MGMT_VRF_TABLE_CDB, MGMT_VRF_GLOBAL)
    if not entry:
        return False

    value = entry.get(MGMT_VRF_GLOBAL_ENABLED, None)
    if not value:
        return False

    return value.title() == 'True'

#
# Syslog validators ---------------------------------------------------------------------------------------------------
#

def server_validator(ctx, db, ip_addr, is_exist=True):
    """
    Check if server IP address exists in Config DB

    Args:
        ctx: click context
        db: reference to Config DB
        ip_addr: server IP address
        is_exist: entry existence flag. True for presence assert, False otherwise
    """
    if is_exist:
        if not is_exist_in_db(db, str(SYSLOG_TABLE_CDB), str(ip_addr)):
            raise click.UsageError("Invalid value for {}: {} is not a valid syslog server".format(
                get_param_hint(ctx, "server_ip_address"), ip_addr), ctx
            )
    else:
        if is_exist_in_db(db, str(SYSLOG_TABLE_CDB), str(ip_addr)):
            raise click.UsageError("Invalid value for {}: {} is a valid syslog server".format(
                get_param_hint(ctx, "server_ip_address"), ip_addr), ctx
            )


def ip_addr_validator(ctx, param, value):
    """
    Check if IP address option is valid

    Args:
        ctx: click context
        param: click parameter context
        value: value of parameter

    Returns:
        str: validated parameter
    """
    if value is None:
        return None

    try:
        ip = ipaddress.ip_address(value)
    except Exception as e:
        raise click.UsageError("Invalid value for {}: {}".format(
            param.get_error_hint(ctx), e), ctx
        )

    return str(ip)


def source_validator(ctx, server, source):
    """
    Check if source option is valid

    Args:
        ctx: click context
        server: server IP address
        source: source IP address
    """
    source_ip = ipaddress.ip_address(source)
    if source_ip.is_loopback or source_ip.is_multicast or source_ip.is_link_local:
        raise click.UsageError("Invalid value for {}: {} is a loopback/multicast/link-local IP address".format(
            get_param_hint(ctx, "source"), source), ctx
        )

    server_ip = ipaddress.ip_address(server)
    if server_ip.version != source_ip.version:
        raise click.UsageError("Invalid value for {} / {}: {} / {} IP address family mismatch".format(
            get_param_hint(ctx, "server_ip_address"), get_param_hint(ctx, "source"), server, source), ctx
        )


def vrf_validator(ctx, db, value):
    """
    Check if VRF device option is valid

    Args:
        ctx: click context
        db: reference to Config DB
        value: value of parameter

    Returns:
        str: validated parameter
    """
    if value is None:
        return None

    vrf_list = ["default"]
    if is_mgmt_vrf_enabled(db):
        vrf_list.append("mgmt")
    vrf_list.extend(db.get_keys(VRF_TABLE_CDB))

    return click.Choice(vrf_list).convert(value, get_param(ctx, "vrf"), ctx)


def source_to_vrf_validator(ctx, source, vrf):
    """
    Check if source IP address and VRF device are compliant to Linux configuration

    I. VRF/Source: unset/unset

    Linux kernel decides which source IP to use within the default VRF

    II. VRF/Source: unset/set

    Check if source IP is configured on any default VRF member:
    yes - set source IP, no - generate error

    III. VRF/Source: set/unset

    Check VRF type:
    1. Default
    2. MGMT
    3. DATA

    Default VRF:
    1. Skip VRF configuration

    MGMT VRF:
    1. Check if MGMT VRF is enabled:
    yes - set VRF, no - generate error

    DATA VRF:
    1. Check if VRF is a member of SONiC VRF table:
    yes - set VRF, no - generate error

    IV. VRF/Source: set/set

    Check VRF type:
    1. Default
    2. MGMT
    3. DATA

    Default VRF:
    1. Check if source IP is configured on any DEFAULT VRF member:
    yes - set source IP, no - generate error
    2. Skip VRF configuration

    MGMT VRF:
    1. Check if MGMT VRF is enabled:
    yes - set VRF, no - generate error
    2. Check if source IP is configured on any MGMT VRF member:
    yes - set source IP, no - generate error

    DATA VRF:
    1. Check if VRF is a member of SONiC VRF table:
    yes - set VRF, no - generate error
    2. Check if source IP is configured on any DATA VRF member:
    yes - set source IP, no - generate error

    Args:
        ctx: click context
        source: source IP address
        vrf: VRF device
    """
    def to_ip_addr_list(ip_addr_dict):
        return list(set([ip_addr for _, ip_addr_list in ip_addr_dict.items() for ip_addr in ip_addr_list]))

    if (source is None) and (vrf is None):
        return

    try:
        vrf_list = get_vrf_list()
        vm_dict = get_vrf_member_dict()
        ip_dict = get_ip_addr_dict()
    except Exception as e:
        raise click.ClickException(str(e))

    if vrf is not None and vrf != "default": # Non default VRF device
        if vrf not in vrf_list:
            raise click.UsageError("Invalid value for {}: {} VRF doesn't exist in Linux".format(
                get_param_hint(ctx, "vrf"), vrf), ctx
            )
        if source is not None:
            filter_out = vm_dict[vrf]
            ip_vrf_dict = dict(filter(lambda value: value[0] in filter_out, ip_dict.items()))
            if source not in to_ip_addr_list(ip_vrf_dict):
                raise click.UsageError("Invalid value for {}: {} IP doesn't exist in Linux {} VRF".format(
                    get_param_hint(ctx, "source"), source, vrf), ctx
                )
    else: # Default VRF device
        if source is not None:
            filter_out = vrf_list
            filter_out.extend([vm for _, vm_list in vm_dict.items() for vm in vm_list])
            ip_vrf_dict = dict(filter(lambda value: value[0] not in filter_out, ip_dict.items()))
            if source not in to_ip_addr_list(ip_vrf_dict):
                raise click.UsageError("Invalid value for {}: {} IP doesn't exist in Linux default VRF".format(
                    get_param_hint(ctx, "source"), source), ctx
                )

#
# Syslog CLI ----------------------------------------------------------------------------------------------------------
#

@click.group(
    name="syslog",
    cls=clicommon.AliasedGroup
)
def syslog():
    """ Configure syslog server """
    pass


@syslog.command("add")
@click.argument(
    "server_ip_address",
    nargs=1,
    required=True,
    callback=ip_addr_validator
)
@click.option(
    "-s", "--source",
    help="Configures syslog source IP address",
    callback=ip_addr_validator
)
@click.option(
    "-p", "--port",
    help="Configures syslog server UDP port",
    type=click.IntRange(min=0, max=65535, clamp=False)
)
@click.option(
    "-r", "--vrf",
    help="Configures syslog VRF device"
)
@clicommon.pass_db
def add(db, server_ip_address, source, port, vrf):
    """ Add object to SYSLOG_SERVER table """
    ctx = click.get_current_context()

    server_validator(ctx, db.cfgdb, server_ip_address, False)

    table = str(SYSLOG_TABLE_CDB)
    key = str(server_ip_address)
    data = {}

    if source is not None:
        source_validator(ctx, server_ip_address, source)
        data[SYSLOG_SOURCE] = source
    if port is not None:
        data[SYSLOG_PORT] = port
    if vrf is not None:
        vrf_validator(ctx, db.cfgdb, vrf)
        data[SYSLOG_VRF] = vrf

    source_to_vrf_validator(ctx, source, vrf)

    try:
        add_entry(db.cfgdb, table, key, data)
        clicommon.run_command(['systemctl', 'reset-failed', 'rsyslog-config', 'rsyslog'], display_cmd=True)
        clicommon.run_command(['systemctl', 'restart', 'rsyslog-config'], display_cmd=True)
        log.log_notice("Added remote syslog logging: server={},source={},port={},vrf={}".format(
            server_ip_address,
            data.get(SYSLOG_SOURCE, "N/A"),
            data.get(SYSLOG_PORT, "N/A"),
            data.get(SYSLOG_VRF, "N/A")
        ))
    except Exception as e:
        log.log_error("Failed to add remote syslog logging: {}".format(str(e)))
        ctx.fail(str(e))


@syslog.command("del")
@click.argument(
    "server_ip_address",
    nargs=1,
    required=True,
    callback=ip_addr_validator
)
@clicommon.pass_db
def delete(db, server_ip_address):
    """ Delete object from SYSLOG_SERVER table """
    ctx = click.get_current_context()

    server_validator(ctx, db.cfgdb, server_ip_address)

    table = str(SYSLOG_TABLE_CDB)
    key = str(server_ip_address)

    try:
        del_entry(db.cfgdb, table, key)
        clicommon.run_command(['systemctl', 'reset-failed', 'rsyslog-config', 'rsyslog'], display_cmd=True)
        clicommon.run_command(['systemctl', 'restart', 'rsyslog-config'], display_cmd=True)
        log.log_notice("Removed remote syslog logging: server={}".format(server_ip_address))
    except Exception as e:
        log.log_error("Failed to remove remote syslog logging: {}".format(str(e)))
        ctx.fail(str(e))


@syslog.command("rate-limit-host")
@click.option("-i", "--interval", help="Configures syslog rate limit interval in seconds for host", type=click.IntRange(0, 2147483647))
@click.option("-b", "--burst", help="Configures syslog rate limit burst in number of messages for host", type=click.IntRange(0, 2147483647))
@clicommon.pass_db
def rate_limit_host(db, interval, burst):
    """ Configure syslog rate limit for host """
    syslog_common.rate_limit_validator(interval, burst)
    syslog_common.save_rate_limit_to_db(db, None, interval, burst, log)


@syslog.command("rate-limit-container")
@click.argument("service_name", required=True)
@click.option("-i", "--interval", help="Configures syslog rate limit interval in seconds for specified containers", type=click.IntRange(0, 2147483647))
@click.option("-b", "--burst", help="Configures syslog rate limit burst in number of messages for specified containers", type=click.IntRange(0, 2147483647))
@clicommon.pass_db
def rate_limit_container(db, service_name, interval, burst):
    """ Configure syslog rate limit for containers """
    syslog_common.rate_limit_validator(interval, burst)
    feature_data = db.cfgdb.get_table(syslog_common.FEATURE_TABLE)
    syslog_common.service_validator(feature_data, service_name)
    syslog_common.save_rate_limit_to_db(db, service_name, interval, burst, log)


@syslog.group(
    name="rate-limit-feature",
    cls=clicommon.AliasedGroup
)
def rate_limit_feature():
    """ Configure syslog rate limit feature """
    pass


@rate_limit_feature.command("enable")
@clicommon.pass_db
def enable_rate_limit_feature(db):
    """ Enable syslog rate limit feature """
    feature_data = db.cfgdb.get_table(syslog_common.FEATURE_TABLE)
    for feature_name in feature_data.keys():
        click.echo(f'Enabling syslog rate limit feature for {feature_name}')
        output, _ = clicommon.run_command(['docker', 'ps', '-q', '-f', 'status=running', '-f', f'name={feature_name}'], return_cmd=True)
        if not output:
            click.echo(f'{feature_name} is not running, ignoring...')
            continue
        
        output, _ = clicommon.run_command(['docker', 'exec', '-i', feature_name, 'supervisorctl', 'status', 'containercfgd'], 
                                          ignore_error=True, return_cmd=True)
        if 'no such process' not in output:
            click.echo(f'Syslog rate limit feature is already enabled in {feature_name}, ignoring...')
            continue
        
        commands = [
            ['docker', 'cp', '/usr/share/sonic/templates/containercfgd.conf', f'{feature_name}:/etc/supervisor/conf.d/'],
            ['docker', 'exec', '-i', feature_name, 'supervisorctl', 'reread'],
            ['docker', 'exec', '-i', feature_name, 'supervisorctl', 'update'],
            ['docker', 'exec', '-i', feature_name, 'supervisorctl', 'start', 'containercfgd']
        ]
        
        failed = False
        for command in commands:
            output, ret = clicommon.run_command(command, return_cmd=True)
            if ret != 0:
                failed = True
                click.echo(f'Enable syslog rate limit feature for {feature_name} failed - {output}')
                break
        
        if not failed:
            click.echo(f'Enabled syslog rate limit feature for {feature_name}')
        
            
@rate_limit_feature.command("disable")
@clicommon.pass_db
def disable_rate_limit_feature(db):
    """ Disable syslog rate limit feature """
    feature_data = db.cfgdb.get_table(syslog_common.FEATURE_TABLE)
    for feature_name in feature_data.keys():
        click.echo(f'Disabling syslog rate limit feature for {feature_name}')
        output, _ = clicommon.run_command(['docker', 'ps', '-q', '-f', 'status=running', '-f', f'name={feature_name}'], return_cmd=True)
        if not output:
            click.echo(f'{feature_name} is not running, ignoring...')
            continue
        
        output, _ = clicommon.run_command(['docker', 'exec', '-i', feature_name, 'supervisorctl', 'status', 'containercfgd'], 
                                          ignore_error=True, return_cmd=True)
        if 'no such process' in output:
            click.echo(f'Syslog rate limit feature is already disabled in {feature_name}, ignoring...')
            continue
        
        commands = [
            ['docker', 'exec', '-i', feature_name, 'supervisorctl', 'stop', 'containercfgd'],
            ['docker', 'exec', '-i', feature_name, 'rm', '-f', '/etc/supervisor/conf.d/containercfgd.conf'],
            ['docker', 'exec', '-i', feature_name, 'supervisorctl', 'reread'],
            ['docker', 'exec', '-i', feature_name, 'supervisorctl', 'update']
        ]
        failed = False
        for command in commands:
            output, ret = clicommon.run_command(command, return_cmd=True)
            if ret != 0:
                failed = True
                click.echo(f'Disable syslog rate limit feature for {feature_name} failed - {output}')
                break
        
        if not failed:
            click.echo(f'Disabled syslog rate limit feature for {feature_name}')

