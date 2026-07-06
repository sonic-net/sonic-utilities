import click
import re
import utilities_common.cli as clicommon
from sonic_py_common import logger

# Table names
CFG_ISIS_GLOBALS = "ISIS_GLOBALS"
CFG_ISIS_GLOBALS_TIMERS = "ISIS_GLOBALS_TIMERS"
CFG_ISIS_INTERFACE = "ISIS_INTERFACE"

# Logger
log = logger.Logger("isis_cli")
log.set_min_log_priority_info()


def _alias_to_name(db_conn, interface_alias):
    """Resolve interface alias to native name if alias mode is active"""
    port_dict = db_conn.get_table('PORT')
    if not port_dict:
        return interface_alias
    for port_name, info in port_dict.items():
        if interface_alias == info.get('alias'):
            return port_name
    return interface_alias


def _validate_interface(db_conn, interface_name):
    """Validate that the interface exists in ConfigDB"""
    port_dict = db_conn.get_table('PORT')
    port_channel_dict = db_conn.get_table('PORTCHANNEL')
    vlan_dict = db_conn.get_table('VLAN')
    loopback_dict = db_conn.get_table('LOOPBACK_INTERFACE')
    vlan_sub_dict = db_conn.get_table('VLAN_SUB_INTERFACE')

    if port_dict and interface_name in port_dict:
        return True
    if port_channel_dict and interface_name in port_channel_dict:
        return True
    if vlan_dict and interface_name in vlan_dict:
        return True
    if loopback_dict and interface_name in loopback_dict:
        return True
    if vlan_sub_dict and interface_name in vlan_sub_dict:
        return True

    return False


#
# IS-IS Global Configuration --------------------------------------------------
#

@click.group(
    name="isis",
    cls=clicommon.AliasedGroup
)
def ISIS():
    """Configure IS-IS routing protocol"""
    pass


@ISIS.command(name="enable")
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_enable(ctx, db, vrf):
    """Enable IS-IS routing process for a VRF"""
    table = CFG_ISIS_GLOBALS
    key = vrf

    cfg = db.cfgdb.get_config()
    cfg.setdefault(table, {})

    if key in cfg[table]:
        data = cfg[table][key]
        if data.get("enabled") == "true":
            click.echo("IS-IS is already enabled for VRF '{}'".format(vrf))
            return

    data = {"enabled": "true"}
    try:
        db.cfgdb.set_entry(table, key, data)
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

    cfg = db.cfgdb.get_config()
    if table not in cfg or key not in cfg[table]:
        click.echo("IS-IS routing process for VRF '{}' is not configured".format(vrf))
        return

    try:
        db.cfgdb.set_entry(table, key, None)
        # Clean up timers table if exists
        timers_table = CFG_ISIS_GLOBALS_TIMERS
        if timers_table in cfg and key in cfg[timers_table]:
            db.cfgdb.set_entry(timers_table, key, None)

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
    net_pattern = re.compile(r'^[a-fA-F0-9]{2}(\.[a-fA-F0-9]{4}){1,9}\.[a-fA-F0-9]{2}$')
    if not net_pattern.match(net_title):
        ctx.fail("Invalid NET format '{}'. Example format: 49.0001.1921.6800.0001.00".format(net_title))

    table = CFG_ISIS_GLOBALS
    key = vrf

    cfg = db.cfgdb.get_config()
    if table not in cfg or key not in cfg[table]:
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first using 'config isis enable {}'".format(vrf, vrf))

    data = cfg[table][key]
    data["net_title"] = net_title

    try:
        db.cfgdb.set_entry(table, key, data)
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

    cfg = db.cfgdb.get_config()
    if table not in cfg or key not in cfg[table]:
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first using 'config isis enable {}'".format(vrf, vrf))

    data = cfg[table][key]
    data["level"] = level

    try:
        db.cfgdb.set_entry(table, key, data)
        click.echo("Configured IS-IS level to '{}' for VRF '{}'".format(level, vrf))
        log.log_notice("Configured IS-IS level to '{}' for VRF '{}'".format(level, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS level for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS.command(name="hostname")
@click.argument("state", type=click.Choice(['enabled', 'disabled']))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_hostname(ctx, db, state, vrf):
    """Configure dynamic hostname support for IS-IS"""
    table = CFG_ISIS_GLOBALS
    key = vrf

    cfg = db.cfgdb.get_config()
    if table not in cfg or key not in cfg[table]:
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first using 'config isis enable {}'".format(vrf, vrf))

    data = cfg[table][key]
    data["dynamic_hostname"] = "true" if state == "enabled" else "false"

    try:
        db.cfgdb.set_entry(table, key, data)
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
    cfg = db.cfgdb.get_config()
    if CFG_ISIS_GLOBALS not in cfg or vrf not in cfg[CFG_ISIS_GLOBALS]:
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first.".format(vrf))

    table = CFG_ISIS_GLOBALS_TIMERS
    key = vrf
    cfg.setdefault(table, {})
    data = cfg[table].setdefault(key, {})
    data["lsp_mtu"] = str(mtu)

    try:
        db.cfgdb.set_entry(table, key, data)
        click.echo("Configured IS-IS LSP MTU to {} for VRF '{}'".format(mtu, vrf))
        log.log_notice("Configured IS-IS LSP MTU to {} for VRF '{}'".format(mtu, vrf))
    except Exception as e:
        log.log_error("Failed to configure IS-IS LSP MTU for VRF '{}': {}".format(vrf, str(e)))
        ctx.fail(str(e))


@ISIS_TIMER.command(name="lsp-refresh")
@click.argument("interval", type=click.IntRange(1, 65535))
@click.argument("vrf", required=False, default="default")
@clicommon.pass_db
@click.pass_context
def isis_timer_lsp_refresh(ctx, db, interval, vrf):
    """Configure IS-IS LSP refresh interval (seconds)"""
    cfg = db.cfgdb.get_config()
    if CFG_ISIS_GLOBALS not in cfg or vrf not in cfg[CFG_ISIS_GLOBALS]:
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first.".format(vrf))

    table = CFG_ISIS_GLOBALS_TIMERS
    key = vrf
    cfg.setdefault(table, {})
    data = cfg[table].setdefault(key, {})
    data["lsp_refresh_interval"] = str(interval)

    try:
        db.cfgdb.set_entry(table, key, data)
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
    cfg = db.cfgdb.get_config()
    if CFG_ISIS_GLOBALS not in cfg or vrf not in cfg[CFG_ISIS_GLOBALS]:
        ctx.fail("IS-IS routing process for VRF '{}' is not enabled. Please enable it first.".format(vrf))

    table = CFG_ISIS_GLOBALS_TIMERS
    key = vrf
    cfg.setdefault(table, {})
    data = cfg[table].setdefault(key, {})
    data["lsp_lifetime"] = str(lifetime)

    try:
        db.cfgdb.set_entry(table, key, data)
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

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = _alias_to_name(db, interface_name)
        if not interface_name:
            ctx.fail("Invalid interface alias")

    if not _validate_interface(db, interface_name):
        ctx.fail("Interface '{}' does not exist".format(interface_name))

    table = CFG_ISIS_INTERFACE
    key = interface_name

    cfg = db.get_config()
    cfg.setdefault(table, {})

    if key in cfg[table]:
        click.echo("IS-IS is already enabled on interface {}".format(interface_name))
        return

    # Use a dummy dict containing just enabled: true to trigger creation
    data = {"enabled": "true"}

    try:
        db.set_entry(table, key, data)
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

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = _alias_to_name(db, interface_name)
        if not interface_name:
            ctx.fail("Invalid interface alias")

    table = CFG_ISIS_INTERFACE
    key = interface_name

    cfg = db.get_config()
    if table not in cfg or key not in cfg[table]:
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

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = _alias_to_name(db, interface_name)
        if not interface_name:
            ctx.fail("Invalid interface alias")

    table = CFG_ISIS_INTERFACE
    key = interface_name

    cfg = db.get_config()
    if table not in cfg or key not in cfg[table]:
        ctx.fail("IS-IS routing is not enabled on interface {}. Please enable it first using 'config interface isis enable {}'".format(interface_name, interface_name))

    data = cfg[table][key]
    data["metric"] = str(metric_val)

    try:
        db.set_entry(table, key, data)
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

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = _alias_to_name(db, interface_name)
        if not interface_name:
            ctx.fail("Invalid interface alias")

    table = CFG_ISIS_INTERFACE
    key = interface_name

    cfg = db.get_config()
    if table not in cfg or key not in cfg[table]:
        ctx.fail("IS-IS routing is not enabled on interface {}. Please enable it first using 'config interface isis enable {}'".format(interface_name, interface_name))

    data = cfg[table][key]
    data["circuit_type"] = circuit_type

    try:
        db.set_entry(table, key, data)
        click.echo("Configured IS-IS circuit type to '{}' on interface {}".format(circuit_type, interface_name))
        log.log_notice("Configured IS-IS circuit type to '{}' on interface {}".format(circuit_type, interface_name))
    except Exception as e:
        log.log_error("Failed to configure IS-IS circuit type on interface {}: {}".format(interface_name, str(e)))
        ctx.fail(str(e))
