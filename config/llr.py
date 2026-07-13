import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic
from utilities_common.llr import is_llr_capable


def _get_valid_namespace_choices():
    """Namespace choices for the -n option.
    On single-asic this returns [''] (DEFAULT_NAMESPACE) so the option
    remains valid but effectively unused.
    """
    return multi_asic_util.multi_asic_ns_choices()


def _get_cfgdb(ctx, namespace):
    """
    Return the ConfigDBConnector for the given namespace from
    Db.cfgdb_clients.  Falls back to ctx.obj.cfgdb / ctx.obj when the
    caller injected a plain ConfigDBConnector (some unit-test paths).
    """
    db = ctx.obj
    cfgdb_clients = getattr(db, "cfgdb_clients", None)
    if cfgdb_clients:
        ns = namespace if namespace is not None else multi_asic.DEFAULT_NAMESPACE
        if ns in cfgdb_clients:
            return cfgdb_clients[ns]
    return getattr(db, "cfgdb", db)


def _validate_port_exists(db, interface_name):
    """
    Validate that the given interface exists in PORT table of CONFIG_DB.
    Returns True if the port exists, False otherwise.
    """
    entry = db.get_entry("PORT", interface_name)
    return len(entry) > 0


def _validate_llr_static_mode(cfgdb, interface_name, command_name, namespace):
    """
    Common validation for local/remote commands
    """
    if not is_llr_capable(namespace):
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
@click.option('-n', '--namespace', help='Namespace name',
              required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=multi_asic.get_current_namespace())
@click.pass_context
def llr_interface_mode(ctx, interface_name, llr_mode, namespace):
    """Configure LLR mode on an interface"""
    if not is_llr_capable(namespace):
        click.echo("Error: LLR is not supported on this platform.")
        raise SystemExit(1)

    cfgdb = _get_cfgdb(ctx, namespace)
    if not _validate_port_exists(cfgdb, interface_name):
        click.echo("Error: Interface {} does not exist.".format(interface_name))
        raise SystemExit(1)

    cfgdb.mod_entry("LLR_PORT", interface_name, {"llr_mode": llr_mode})


@llr_interface.command(name='local')
@click.argument('interface_name', metavar='<interface-name>')
@click.argument('state', metavar='{enabled|disabled}',
                type=click.Choice(['enabled', 'disabled']))
@click.option('-n', '--namespace', help='Namespace name',
              required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=multi_asic.get_current_namespace())
@click.pass_context
def llr_interface_local(ctx, interface_name, state, namespace):
    """Enable/disable LLR local on an interface"""
    cfgdb = _get_cfgdb(ctx, namespace)
    _validate_llr_static_mode(cfgdb, interface_name, "local", namespace)
    cfgdb.mod_entry("LLR_PORT", interface_name, {"llr_local": state})


@llr_interface.command(name='remote')
@click.argument('interface_name', metavar='<interface-name>')
@click.argument('state', metavar='{enabled|disabled}',
                type=click.Choice(['enabled', 'disabled']))
@click.option('-n', '--namespace', help='Namespace name',
              required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=multi_asic.get_current_namespace())
@click.pass_context
def llr_interface_remote(ctx, interface_name, state, namespace):
    """Enable/disable LLR remote on an interface"""
    cfgdb = _get_cfgdb(ctx, namespace)
    _validate_llr_static_mode(cfgdb, interface_name, "remote", namespace)
    cfgdb.mod_entry("LLR_PORT", interface_name, {"llr_remote": state})
