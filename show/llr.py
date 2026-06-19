import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from natsort import natsorted
from sonic_py_common import multi_asic
from tabulate import tabulate

LLR_PROFILE_DISPLAY_FIELDS = [
    ("max_outstanding_frames", "Maximum Outstanding Frames"),
    ("max_outstanding_bytes",  "Maximum Outstanding Bytes"),
    ("max_replay_count",       "Maximum Replay Count"),
    ("max_replay_timer",       "Maximum Replay Timer(ns)"),
    ("pcs_lost_timeout",       "PCS Lost Status Timeout(ns)"),
    ("data_age_timeout",       "Data Age Timeout(ns)"),
    ("ctlos_spacing_bytes",    "CTLOS Spacing Bytes"),
    ("init_action",            "Init Action"),
    ("flush_action",           "Flush Action"),
]

STATUS_NA = "N/A"


def _get_valid_namespace_choices():
    """Namespace choices for the -n option (single-asic returns [''])."""
    return multi_asic_util.multi_asic_ns_choices()


def _resolve_namespaces(db, namespace):
    """
    Return the list of (namespace, SonicV2Connector) pairs to iterate.

    - When `namespace` is explicitly provided, only that namespace is
      returned.
    - When `namespace` is None on multi-asic, all per-asic namespaces in
      Db.db_clients are returned (excluding the host DEFAULT_NAMESPACE,
      since LLR_PORT/LLR_PROFILE tables live in per-asic APPL_DB).
    - When `namespace` is None on single-asic, the single DEFAULT_NAMESPACE
      entry is returned.
    """
    db_clients = getattr(db, "db_clients", None) or {
        multi_asic.DEFAULT_NAMESPACE: db.db
    }

    if namespace is not None and namespace != "":
        if namespace not in db_clients:
            return []
        return [(namespace, db_clients[namespace])]

    if multi_asic.is_multi_asic():
        return [
            (ns, conn) for ns, conn in db_clients.items()
            if ns != multi_asic.DEFAULT_NAMESPACE
        ]

    return [(multi_asic.DEFAULT_NAMESPACE, db_clients[multi_asic.DEFAULT_NAMESPACE])]


##############################################################################
# 'llr' group ("show llr ...")
##############################################################################

@click.group(cls=clicommon.AliasedGroup)
@click.pass_context
def llr(ctx):
    """Show LLR (Link Layer Retry) information"""
    pass


##############################################################################
# 'show llr interface [interface-name]'
##############################################################################

@llr.command(name='interface')
@click.argument('interface_name', metavar='<interface-name>', required=False, default=None)
@click.option('-n', '--namespace', help='Namespace name', required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=None)
@clicommon.pass_db
def llr_interface(db, interface_name, namespace):
    """Show LLR interface configuration"""
    ns_conns = _resolve_namespaces(db, namespace)
    is_multi = multi_asic.is_multi_asic()

    header = ["PORT"]
    if is_multi:
        header.append("Namespace")
    header += ["LLR Mode", "LLR Local", "LLR Remote", "LLR Profile"]
    rows = []

    for ns, conn in ns_conns:
        # APPL_DB entries (operational state)
        appl_ports = {}
        keys = conn.keys(conn.APPL_DB, "LLR_PORT_TABLE:*") or []
        for key in keys:
            port = key.split(":", 1)[1]
            entry = conn.get_all(conn.APPL_DB, key)
            if entry:
                appl_ports[port] = entry

        # CONFIG_DB entries not yet in APPL_DB (pending state)
        cfg_ports = {}
        cfg_keys = conn.keys(conn.CONFIG_DB, "LLR_PORT|*") or []
        for key in cfg_keys:
            port = key.split("|", 1)[1]
            if port not in appl_ports:
                entry = conn.get_all(conn.CONFIG_DB, key)
                if entry:
                    cfg_ports[port] = entry

        all_ports = set(appl_ports.keys()) | set(cfg_ports.keys())
        for port in natsorted(all_ports):
            if interface_name and port != interface_name:
                continue
            entry = appl_ports.get(port) or cfg_ports[port]
            profile = entry.get("llr_profile", STATUS_NA) if port in appl_ports else "-"
            row = [port]
            if is_multi:
                row.append(ns if ns else multi_asic.DEFAULT_NAMESPACE)
            row += [
                entry.get("llr_mode", STATUS_NA),
                entry.get("llr_local", "disabled"),
                entry.get("llr_remote", "disabled"),
                profile,
            ]
            rows.append(row)

    if not rows:
        if interface_name:
            click.echo("Interface {} not found in LLR configuration.".format(interface_name))
        else:
            click.echo("No LLR interface configuration found.")
        return

    click.echo()
    click.echo("LLR Interface Configuration")
    click.echo("----------------------------")
    click.echo()
    click.echo(tabulate(rows, headers=header, tablefmt="simple"))
    click.echo()


##############################################################################
# 'show llr profile [profile-name]'
##############################################################################

@llr.command(name='profile')
@click.argument('profile_name', metavar='<profile-name>', required=False, default=None)
@click.option('-n', '--namespace', help='Namespace name', required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=None)
@clicommon.pass_db
def llr_profile(db, profile_name, namespace):
    """Show LLR profile configuration"""
    ns_conns = _resolve_namespaces(db, namespace)
    is_multi = multi_asic.is_multi_asic()
    found = False

    for ns, conn in ns_conns:
        keys = conn.keys(conn.APPL_DB, "LLR_PROFILE_TABLE:*") or []
        for key in natsorted(keys):
            pname = key.split(":", 1)[1]
            if profile_name and pname != profile_name:
                continue
            entry = conn.get_all(conn.APPL_DB, key)
            if not entry:
                continue

            found = True
            heading = "LLR Profile: {}".format(pname)
            if is_multi:
                heading += " ({})".format(ns if ns else multi_asic.DEFAULT_NAMESPACE)
            rows = [[display, entry.get(field, STATUS_NA)]
                    for field, display in LLR_PROFILE_DISPLAY_FIELDS]
            click.echo(tabulate(rows, headers=[heading, ""], tablefmt="grid"))
            click.echo()

    if not found:
        if profile_name:
            click.echo("LLR profile {} not found.".format(profile_name))
        else:
            click.echo("No LLR profiles found.")


##############################################################################
# 'show llr counters [-i interface-name]'
# 'show llr counters detailed [interface-name]'
#
##############################################################################

@llr.group(name='counters', invoke_without_command=True, cls=clicommon.AliasedGroup)
@click.option('-i', '--interface', 'interface_name', metavar='<interface-name>',
              default=None, help='Filter counters for a specific interface')
@click.option('-n', '--namespace', help='Namespace name', required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=None)
@click.pass_context
def llr_counters(ctx, interface_name, namespace):
    """Show LLR counter statistics"""
    if ctx.invoked_subcommand is None:
        cmd = ['llrstat']
        if interface_name:
            cmd += ['-i', str(interface_name)]
        if namespace:
            cmd += ['-n', str(namespace)]
        clicommon.run_command(cmd)


@llr_counters.command(name='detailed')
@click.argument('interface_name', metavar='<interface-name>', required=False, default=None)
@click.option('-n', '--namespace', help='Namespace name', required=False,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              default=None)
@click.pass_context
def llr_counters_detailed(ctx, interface_name, namespace):
    """Show detailed LLR counter statistics per port"""
    cmd = ['llrstat', '-d']
    if interface_name:
        cmd += ['-i', str(interface_name)]
    if namespace:
        cmd += ['-n', str(namespace)]
    clicommon.run_command(cmd)
