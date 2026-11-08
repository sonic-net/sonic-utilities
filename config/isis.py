import click
import re
import utilities_common.cli as clicommon
from sonic_py_common import logger, multi_asic
from swsscommon.swsscommon import ConfigDBConnector

# Table names
CFG_ISIS_GLOBALS = "ISIS_GLOBALS"
CFG_ISIS_GLOBALS_TIMERS = "ISIS_GLOBALS_TIMERS"
CFG_ISIS_INTERFACE = "ISIS_INTERFACE"

# Logger
log = logger.Logger("isis_cli")
log.set_min_log_priority_info()


def _interface_vrf(db, name):
    for table in ('INTERFACE', 'PORTCHANNEL_INTERFACE', 'VLAN_INTERFACE',
                  'LOOPBACK_INTERFACE', 'VLAN_SUB_INTERFACE'):
        entry = db.get_entry(table, name)
        if entry.get('vrf_name'):
            return entry['vrf_name']
    return 'default'


def _resolve_interface(ctx, db, name):
    # Import lazily: main registers this module's command groups.
    from config.main import (interface_alias_to_name, interface_name_is_valid,
                             interface_is_in_portchannel, interface_is_in_vlan)
    if clicommon.get_interface_naming_mode() == 'alias':
        name = interface_alias_to_name(db, name)
    if not db.get_entry("VLAN_INTERFACE", name) and not interface_name_is_valid(db, name):
        ctx.fail("Interface '{}' does not exist".format(name))
    if (interface_is_in_portchannel(db.get_table('PORTCHANNEL_MEMBER'), name) or
            interface_is_in_vlan(db.get_table('VLAN_MEMBER'), name)):
        ctx.fail("Interface '{}' is a PortChannel or VLAN member".format(name))
    return name


def _require_process(ctx, db, vrf):
    if db.get_entry(CFG_ISIS_GLOBALS, vrf).get('enabled') != 'true':
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first.".format(vrf))


#
# IS-IS Global Configuration --------------------------------------------------
#

@click.group(
    name="isis",
    cls=clicommon.AliasedGroup
)
@click.option('-n', '--namespace',
              required=multi_asic.is_multi_asic(),
              type=click.Choice(multi_asic.get_namespace_list()))
@clicommon.pass_db
@click.pass_context
def ISIS(ctx, db, namespace):
    """Configure IS-IS routing protocol"""
    if namespace is not None:
        db.cfgdb = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        db.cfgdb.connect()
    if db.cfgdb.get_entry('DEVICE_METADATA', 'localhost').get('frr_mgmt_framework_config') != 'true':
        click.echo('Warning: IS-IS requires frr_mgmt_framework_config=true and a bgp container restart.', err=True)


@ISIS.command(name="enable")
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_enable(ctx, db, vrf):
    """Enable IS-IS routing process for a VRF"""
    table = CFG_ISIS_GLOBALS
    key = vrf

    from config.main import is_vrf_exists
    if vrf != 'default' and not is_vrf_exists(db.cfgdb, vrf):
        ctx.fail("VRF '{}' does not exist".format(vrf))
    if db.cfgdb.get_entry(table, key).get('enabled') == 'true':
        click.echo("IS-IS is already enabled for VRF '{}'".format(vrf))
        return

    data = {"enabled": "true"}
    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Enabled IS-IS routing process for VRF '{}'".format(vrf))
        log.log_notice("Enabled IS-IS routing process for VRF '{}'".format(vrf))
    except Exception as e:
        log.log_error("Failed to enable IS-IS for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS.command(name="disable")
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_disable(ctx, db, vrf):
    """Disable IS-IS routing process for a VRF"""
    table = CFG_ISIS_GLOBALS
    key = vrf

    if not db.cfgdb.get_entry(table, key):
        click.echo("IS-IS routing process for VRF '{}' is not configured".format(vrf))
        return

    try:
        for name in db.cfgdb.get_table(CFG_ISIS_INTERFACE):
            if _interface_vrf(db.cfgdb, name) == vrf:
                ctx.fail("Disable IS-IS on interface '{}' first".format(name))
        # Clean up timers table if exists
        timers_table = CFG_ISIS_GLOBALS_TIMERS
        if db.cfgdb.get_entry(timers_table, key):
            db.cfgdb.set_entry(timers_table, key, None)
        db.cfgdb.set_entry(table, key, None)

        click.echo("Disabled IS-IS routing process for VRF '{}'".format(vrf))
        log.log_notice("Disabled IS-IS routing process for VRF '{}'".format(vrf))
    except Exception as e:
        log.log_error("Failed to disable IS-IS for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS.command(name="net")
@click.argument("net_title")
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_net(ctx, db, net_title, vrf):
    """Configure Network Entity Title (NET) for IS-IS"""
    # Strict validation of NET (e.g. 49.0001.1921.6800.0001.00)
    net_pattern = re.compile(r'^[a-fA-F0-9]{2}(\.[a-fA-F0-9]{4}){3,9}\.00$')
    if not net_pattern.match(net_title):
        ctx.fail("Invalid NET format '{}'. Example format: 49.0001.1921.6800.0001.00".format(net_title))

    table = CFG_ISIS_GLOBALS
    key = vrf

    if db.cfgdb.get_entry(table, key).get("enabled") != "true":
        ctx.fail(
            "IS-IS routing process for VRF '{}' is not enabled. Please enable it first using "
            "'config isis enable {}'".format(vrf, vrf)
        )

    data = {}
    data["net_title"] = net_title

    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Configured IS-IS NET to '{}' for VRF '{}'".format(net_title, vrf))
        log.log_notice("Configured IS-IS NET to '{}' for VRF '{}'".format(net_title, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS NET for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS.command(name="level")
@click.argument("level", type=click.Choice(['level-1', 'level-2', 'level-1-2']))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_level(ctx, db, level, vrf):
    """Configure IS-IS routing level"""
    table = CFG_ISIS_GLOBALS
    key = vrf

    if db.cfgdb.get_entry(table, key).get("enabled") != "true":
        ctx.fail(
            "IS-IS routing process for VRF '{}' is not enabled. Please enable it first using "
            "'config isis enable {}'".format(vrf, vrf)
        )

    data = {}
    data["level"] = level

    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Configured IS-IS level to '{}' for VRF '{}'".format(level, vrf))
        log.log_notice("Configured IS-IS level to '{}' for VRF '{}'".format(level, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS level for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS.command(name="hostname")
@click.argument("state", type=click.Choice(['enable', 'disable']))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_hostname(ctx, db, state, vrf):
    """Configure dynamic hostname support for IS-IS"""
    table = CFG_ISIS_GLOBALS
    key = vrf

    if db.cfgdb.get_entry(table, key).get("enabled") != "true":
        ctx.fail(
            "IS-IS routing process for VRF '{}' is not enabled. Please enable it first using "
            "'config isis enable {}'".format(vrf, vrf)
        )

    data = {}
    data["dynamic_hostname"] = "true" if state == "enable" else "false"

    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Configured IS-IS dynamic hostname to '{}' for VRF '{}'".format(state, vrf))
        log.log_notice("Configured IS-IS dynamic hostname to '{}' for VRF '{}'".format(state, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS dynamic hostname for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS.group(name="timer")
def ISIS_TIMER():
    """Configure IS-IS global timers"""
    pass


@ISIS_TIMER.command(name="lsp-mtu")
@click.argument("mtu", type=click.IntRange(128, 4352))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_timer_lsp_mtu(ctx, db, mtu, vrf):
    """Configure IS-IS LSP MTU size"""
    _require_process(ctx, db.cfgdb, vrf)

    table = CFG_ISIS_GLOBALS_TIMERS
    key = vrf
    data = {}
    data["lsp_mtu"] = str(mtu)

    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Configured IS-IS LSP MTU to {} for VRF '{}'".format(mtu, vrf))
        log.log_notice("Configured IS-IS LSP MTU to {} for VRF '{}'".format(mtu, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS LSP MTU for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS_TIMER.command(name="lsp-refresh")
@click.argument("interval", type=click.IntRange(1, 65235))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_timer_lsp_refresh(ctx, db, interval, vrf):
    """Configure IS-IS LSP refresh interval (seconds)"""
    _require_process(ctx, db.cfgdb, vrf)

    table = CFG_ISIS_GLOBALS_TIMERS
    key = vrf
    data = {}
    if interval + 300 > int(db.cfgdb.get_entry(table, key).get("lsp_lifetime", 1200)):
        ctx.fail("LSP lifetime must be at least refresh interval + 300 seconds")
    data["lsp_refresh_interval"] = str(interval)

    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Configured IS-IS LSP refresh interval to {}s for VRF '{}'".format(interval, vrf))
        log.log_notice("Configured IS-IS LSP refresh interval to {}s for VRF '{}'".format(interval, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS LSP refresh interval for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS_TIMER.command(name="lsp-lifetime")
@click.argument("lifetime", type=click.IntRange(350, 65535))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_timer_lsp_lifetime(ctx, db, lifetime, vrf):
    """Configure IS-IS max LSP lifetime (seconds)"""
    _require_process(ctx, db.cfgdb, vrf)

    table = CFG_ISIS_GLOBALS_TIMERS
    key = vrf
    data = {}
    if lifetime < int(db.cfgdb.get_entry(table, key).get("lsp_refresh_interval", 900)) + 300:
        ctx.fail("LSP lifetime must be at least refresh interval + 300 seconds")
    data["lsp_lifetime"] = str(lifetime)

    try:
        db.cfgdb.mod_entry(table, key, data)
        click.echo("Configured IS-IS LSP max lifetime to {}s for VRF '{}'".format(lifetime, vrf))
        log.log_notice("Configured IS-IS LSP max lifetime to {}s for VRF '{}'".format(lifetime, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS LSP max lifetime for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


#
# IS-IS Interface Configuration -----------------------------------------------
#

@click.group(
    name="isis",
    cls=clicommon.AliasedGroup
)
@click.pass_context
def INTERFACE_ISIS(ctx):
    """Configure IS-IS interface settings"""
    if not ctx.obj or 'config_db' not in ctx.obj:
        ctx.fail("config_db is not initialized")


@INTERFACE_ISIS.command(name="enable")
@click.argument("interface_name")
@click.pass_context
def interface_isis_enable(ctx, interface_name):
    """Enable IS-IS routing on an interface"""
    db = ctx.obj['config_db']

    interface_name = _resolve_interface(ctx, db, interface_name)

    _require_process(ctx, db, _interface_vrf(db, interface_name))

    table = CFG_ISIS_INTERFACE
    key = interface_name

    if db.get_entry(table, key).get("enabled") == "true":
        click.echo("IS-IS is already enabled on interface {}".format(interface_name))
        return

    # Explicit administrative state is shared with YANG and frrcfgd.
    data = {"enabled": "true"}

    try:
        db.mod_entry(table, key, data)
        click.echo("Enabled IS-IS on interface {}".format(interface_name))
        log.log_notice("Enabled IS-IS on interface {}".format(interface_name))
    except Exception as e:
        log.log_error("Failed to enable IS-IS on interface {}: {}".format(interface_name, str(e)))
        ctx.fail(str(e))


@INTERFACE_ISIS.command(name="disable")
@click.argument("interface_name")
@click.pass_context
def interface_isis_disable(ctx, interface_name):
    """Disable IS-IS routing on an interface"""
    db = ctx.obj['config_db']

    # Cleanup must also work after the interface is removed or becomes a member.
    if not db.get_entry(CFG_ISIS_INTERFACE, interface_name):
        from config.main import interface_alias_to_name
        if clicommon.get_interface_naming_mode() == 'alias':
            interface_name = interface_alias_to_name(db, interface_name)

    table = CFG_ISIS_INTERFACE
    key = interface_name

    if not db.get_entry(table, key):
        click.echo("IS-IS routing is not enabled on interface {}".format(interface_name))
        return

    try:
        db.set_entry(table, key, None)
        click.echo("Disabled IS-IS on interface {}".format(interface_name))
        log.log_notice("Disabled IS-IS on interface {}".format(interface_name))
    except Exception as e:
        log.log_error("Failed to disable IS-IS on interface {}: {}".format(interface_name, str(e)))
        ctx.fail(str(e))


@INTERFACE_ISIS.command(name="metric")
@click.argument("interface_name")
@click.argument("metric_val", type=click.IntRange(1, 16777215))
@click.pass_context
def interface_isis_metric(ctx, interface_name, metric_val):
    """Configure IS-IS metric for an interface"""
    db = ctx.obj['config_db']

    interface_name = _resolve_interface(ctx, db, interface_name)

    table = CFG_ISIS_INTERFACE
    key = interface_name

    if db.get_entry(table, key).get("enabled") != "true":
        ctx.fail(
            "IS-IS routing is not enabled on interface {}. Please enable it first using "
            "'config interface isis enable {}'".format(interface_name, interface_name)
        )

    data = {}
    data["metric"] = str(metric_val)

    try:
        db.mod_entry(table, key, data)
        click.echo("Configured IS-IS metric to {} on interface {}".format(metric_val, interface_name))
        log.log_notice("Configured IS-IS metric to {} on interface {}".format(metric_val, interface_name))
    except Exception as e:
        log.log_error("Failed to configure IS-IS metric on interface {}: {}".format(interface_name, str(e)))
        ctx.fail(str(e))


@INTERFACE_ISIS.command(name="circuit-type")
@click.argument("interface_name")
@click.argument("circuit_type", type=click.Choice(['p2p', 'lan']))
@click.pass_context
def interface_isis_circuit_type(ctx, interface_name, circuit_type):
    """Configure IS-IS circuit type for an interface"""
    db = ctx.obj['config_db']

    interface_name = _resolve_interface(ctx, db, interface_name)

    table = CFG_ISIS_INTERFACE
    key = interface_name

    if db.get_entry(table, key).get("enabled") != "true":
        ctx.fail(
            "IS-IS routing is not enabled on interface {}. Please enable it first using "
            "'config interface isis enable {}'".format(interface_name, interface_name)
        )

    data = {}
    data["circuit_type"] = circuit_type

    try:
        db.mod_entry(table, key, data)
        click.echo("Configured IS-IS circuit type to '{}' on interface {}".format(circuit_type, interface_name))
        log.log_notice("Configured IS-IS circuit type to '{}' on interface {}".format(circuit_type, interface_name))
    except Exception as e:
        log.log_error("Failed to configure IS-IS circuit type on interface {}: {}".format(interface_name, str(e)))
        ctx.fail(str(e))


@INTERFACE_ISIS.command(name="passive")
@click.argument("interface_name")
@click.argument("mode", type=click.Choice(['enable', 'disable']))
@click.pass_context
def interface_isis_passive(ctx, interface_name, mode):
    """Configure IS-IS passive mode for an interface"""
    db = ctx.obj['config_db']

    interface_name = _resolve_interface(ctx, db, interface_name)

    table = CFG_ISIS_INTERFACE
    key = interface_name

    if db.get_entry(table, key).get("enabled") != "true":
        ctx.fail(
            "IS-IS routing is not enabled on interface {}. Please enable it first using "
            "'config interface isis enable {}'".format(interface_name, interface_name)
        )

    data = {}
    data["passive"] = "true" if mode == "enable" else "false"

    try:
        db.mod_entry(table, key, data)
        click.echo("Configured IS-IS passive mode to '{}' on interface {}".format(mode, interface_name))
        log.log_notice("Configured IS-IS passive mode to '{}' on interface {}".format(mode, interface_name))
    except Exception as e:
        log.log_error("Failed to configure IS-IS passive mode on interface {}: {}".format(interface_name, str(e)))
        ctx.fail(str(e))


def _set_interface_af(ctx, interface_name, family, state):
    db = ctx.obj['config_db']
    name = _resolve_interface(ctx, db, interface_name)
    if db.get_entry(CFG_ISIS_INTERFACE, name).get('enabled') != 'true':
        ctx.fail("IS-IS routing is not enabled on interface {}".format(name))
    _require_process(ctx, db, _interface_vrf(db, name))
    try:
        db.mod_entry(CFG_ISIS_INTERFACE, name,
                     {family.lower() + '_enabled': 'true' if state == 'enable' else 'false'})
        click.echo("Configured IS-IS {} to '{}' on interface {}".format(family, state, name))
        log.log_notice("Configured IS-IS {} to '{}' on interface {}".format(family, state, name))
    except Exception as e:
        log.log_error("Failed to configure IS-IS {} on interface {}: {}".format(family, name, str(e)))
        ctx.fail(str(e))


@INTERFACE_ISIS.command(name='ipv4')
@click.argument('interface_name')
@click.argument('state', type=click.Choice(['enable', 'disable']))
@click.pass_context
def interface_isis_ipv4(ctx, interface_name, state):
    """Enable or disable IS-IS IPv4 routing on an interface."""
    _set_interface_af(ctx, interface_name, 'IPv4', state)


@INTERFACE_ISIS.command(name='ipv6')
@click.argument('interface_name')
@click.argument('state', type=click.Choice(['enable', 'disable']))
@click.pass_context
def interface_isis_ipv6(ctx, interface_name, state):
    """Enable or disable IS-IS IPv6 routing on an interface."""
    _set_interface_af(ctx, interface_name, 'IPv6', state)


@ISIS.command(name='reset')
@click.argument('field', type=click.Choice(['net', 'level', 'hostname', 'lsp-mtu', 'lsp-refresh', 'lsp-lifetime']))
@click.argument('vrf', required=False, default='default')
@clicommon.pass_db
@click.pass_context
def isis_reset(ctx, db, field, vrf):
    """Reset a global setting to its default (remove NET when selected)."""
    _require_process(ctx, db.cfgdb, vrf)
    fields = {'net': 'net_title', 'level': 'level', 'hostname': 'dynamic_hostname',
              'lsp-mtu': 'lsp_mtu', 'lsp-refresh': 'lsp_refresh_interval', 'lsp-lifetime': 'lsp_lifetime'}
    table = CFG_ISIS_GLOBALS_TIMERS if field.startswith('lsp-') else CFG_ISIS_GLOBALS
    timers = db.cfgdb.get_entry(CFG_ISIS_GLOBALS_TIMERS, vrf)
    refresh = 900 if field == 'lsp-refresh' else int(timers.get('lsp_refresh_interval', 900))
    lifetime = 1200 if field == 'lsp-lifetime' else int(timers.get('lsp_lifetime', 1200))
    if field in ('lsp-refresh', 'lsp-lifetime') and lifetime < refresh + 300:
        ctx.fail('LSP lifetime must be at least refresh interval + 300 seconds')
    entry = db.cfgdb.get_entry(table, vrf)
    if fields[field] in entry:
        entry.pop(fields[field])
        db.cfgdb.set_entry(table, vrf, entry or None)


@INTERFACE_ISIS.command(name='reset')
@click.argument('interface_name')
@click.argument('field', type=click.Choice(['metric', 'circuit-type', 'passive', 'ipv4', 'ipv6']))
@click.pass_context
def interface_isis_reset(ctx, interface_name, field):
    """Reset an interface setting to its default."""
    db = ctx.obj['config_db']
    name = _resolve_interface(ctx, db, interface_name)
    if db.get_entry(CFG_ISIS_INTERFACE, name).get('enabled') != 'true':
        ctx.fail("IS-IS routing is not enabled on interface {}".format(name))
    if field in ('ipv4', 'ipv6'):
        _require_process(ctx, db, _interface_vrf(db, name))
    fields = {'metric': 'metric', 'circuit-type': 'circuit_type', 'passive': 'passive',
              'ipv4': 'ipv4_enabled', 'ipv6': 'ipv6_enabled'}
    entry = db.get_entry(CFG_ISIS_INTERFACE, name)
    entry.pop(fields[field], None)
    db.set_entry(CFG_ISIS_INTERFACE, name, entry)
