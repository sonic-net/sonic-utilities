import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector

LLR_CAPABLE_KEY = "SWITCH_CAPABILITY|switch"
LLR_CAPABLE_FIELD = "LLR_CAPABLE"


def _check_llr_capability():
    """
    Check STATE_DB SWITCH_CAPABILITY|switch for LLR_CAPABLE == "true".
    Returns True if supported, False otherwise.
    """
    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)
    val = state_db.get(state_db.STATE_DB, LLR_CAPABLE_KEY, LLR_CAPABLE_FIELD)
    return val == "true"


def _validate_port_exists(db, interface_name):
    """
    Validate that the given interface exists in PORT table of CONFIG_DB.
    Returns True if the port exists, False otherwise.
    """
    entry = db.get_entry("PORT", interface_name)
    return len(entry) > 0


def _validate_llr_static_mode(cfgdb, interface_name, command_name):
    """
    Common validation for local/remote commands
    """
    if not _check_llr_capability():
        click.echo("Error: LLR is not supported on this platform.")
        raise SystemExit(1)

    if not _validate_port_exists(cfgdb, interface_name):
        click.echo("Error: Interface {} does not exist.".format(interface_name))
        raise SystemExit(1)

    entry = cfgdb.get_entry("LLR_PORT", interface_name)
    mode = entry.get("llr_mode", "static")
    if mode != "static":
        click.echo("Error: 'config llr interface {}' is only applicable "
                   "when llr_mode is 'static' (current mode: '{}').".format(
                       command_name, mode))
        raise SystemExit(1)


##############################################################################
# 'llr' group ("config llr ...")
##############################################################################

@click.group(cls=clicommon.AliasedGroup)
@click.pass_context
def llr(ctx):
    """Configure LLR (Link Layer Retry)"""
    pass


##############################################################################
# 'config llr interface ...'
##############################################################################

@llr.group(name='interface', cls=clicommon.AliasedGroup)
@click.pass_context
def llr_interface(ctx):
    """Configure LLR on a per-port basis"""
    pass


@llr_interface.command(name='mode')
@click.argument('interface_name', metavar='<interface-name>')
@click.argument('llr_mode', metavar='<static>', type=click.Choice(['static']))
@click.pass_context
def llr_interface_mode(ctx, interface_name, llr_mode):
    """Configure LLR mode on an interface"""
    if not _check_llr_capability():
        click.echo("Error: LLR is not supported on this platform.")
        raise SystemExit(1)

    cfgdb = ctx.obj.cfgdb
    if not _validate_port_exists(cfgdb, interface_name):
        click.echo("Error: Interface {} does not exist.".format(interface_name))
        raise SystemExit(1)

    cfgdb.mod_entry("LLR_PORT", interface_name, {"llr_mode": llr_mode})


@llr_interface.command(name='local')
@click.argument('interface_name', metavar='<interface-name>')
@click.argument('state', metavar='{enabled|disabled}',
                type=click.Choice(['enabled', 'disabled']))
@click.pass_context
def llr_interface_local(ctx, interface_name, state):
    """Enable/disable LLR local on an interface"""
    cfgdb = ctx.obj.cfgdb
    _validate_llr_static_mode(cfgdb, interface_name, "local")
    cfgdb.mod_entry("LLR_PORT", interface_name, {"llr_local": state})


@llr_interface.command(name='remote')
@click.argument('interface_name', metavar='<interface-name>')
@click.argument('state', metavar='{enabled|disabled}',
                type=click.Choice(['enabled', 'disabled']))
@click.pass_context
def llr_interface_remote(ctx, interface_name, state):
    """Enable/disable LLR remote on an interface"""
    cfgdb = ctx.obj.cfgdb
    _validate_llr_static_mode(cfgdb, interface_name, "remote")
    cfgdb.mod_entry("LLR_PORT", interface_name, {"llr_remote": state})
