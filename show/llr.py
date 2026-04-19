import click
import utilities_common.cli as clicommon
from natsort import natsorted
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
@clicommon.pass_db
def llr_interface(db, interface_name):
    """Show LLR interface configuration"""
    conn = db.db

    # Collect APPL_DB entries (operational state)
    appl_ports = {}
    keys = conn.keys(conn.APPL_DB, "LLR_PORT_TABLE:*")
    if keys:
        for key in keys:
            port = key.split(":", 1)[1]
            entry = conn.get_all(conn.APPL_DB, key)
            if entry:
                appl_ports[port] = entry

    # Collect CONFIG_DB entries not yet in APPL_DB (pending state)
    cfg_ports = {}
    cfg_keys = conn.keys(conn.CONFIG_DB, "LLR_PORT|*")
    if cfg_keys:
        for key in cfg_keys:
            port = key.split("|", 1)[1]
            if port not in appl_ports:
                entry = conn.get_all(conn.CONFIG_DB, key)
                if entry:
                    cfg_ports[port] = entry

    if not appl_ports and not cfg_ports:
        click.echo("No LLR interface configuration found.")
        return

    header = ["PORT", "LLR Mode", "LLR Local", "LLR Remote", "LLR Profile"]
    rows = []

    all_ports = set(appl_ports.keys()) | set(cfg_ports.keys())
    for port in natsorted(all_ports):
        if interface_name and port != interface_name:
            continue

        if port in appl_ports:
            entry = appl_ports[port]
            rows.append([
                port,
                entry.get("llr_mode", STATUS_NA),
                entry.get("llr_local", "disabled"),
                entry.get("llr_remote", "disabled"),
                entry.get("llr_profile", STATUS_NA),
            ])
        else:
            entry = cfg_ports[port]
            rows.append([
                port,
                entry.get("llr_mode", STATUS_NA),
                entry.get("llr_local", "disabled"),
                entry.get("llr_remote", "disabled"),
                "-",
            ])

    if interface_name and not rows:
        click.echo("Interface {} not found in LLR configuration.".format(interface_name))
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
@clicommon.pass_db
def llr_profile(db, profile_name):
    """Show LLR profile configuration"""
    conn = db.db

    keys = conn.keys(conn.APPL_DB, "LLR_PROFILE_TABLE:*")
    if not keys:
        click.echo("No LLR profiles found.")
        return

    found = False
    for key in natsorted(keys):
        pname = key.split(":", 1)[1]
        if profile_name and pname != profile_name:
            continue

        entry = conn.get_all(conn.APPL_DB, key)
        if not entry:
            continue

        found = True
        rows = [[display, entry.get(field, STATUS_NA)]
                for field, display in LLR_PROFILE_DISPLAY_FIELDS]
        click.echo(tabulate(rows,
                            headers=["LLR Profile: {}".format(pname), ""],
                            tablefmt="grid"))
        click.echo()

    if profile_name and not found:
        click.echo("LLR profile {} not found.".format(profile_name))


##############################################################################
# 'show llr counters [-i interface-name]'
# 'show llr counters detailed [interface-name]'
#
##############################################################################

@llr.group(name='counters', invoke_without_command=True, cls=clicommon.AliasedGroup)
@click.option('-i', '--interface', 'interface_name', metavar='<interface-name>',
              default=None, help='Filter counters for a specific interface')
@click.pass_context
def llr_counters(ctx, interface_name):
    """Show LLR counter statistics"""
    if ctx.invoked_subcommand is None:
        cmd = ['llrstat']
        if interface_name:
            cmd += ['-i', str(interface_name)]
        clicommon.run_command(cmd)


@llr_counters.command(name='detailed')
@click.argument('interface_name', metavar='<interface-name>', required=False, default=None)
@click.pass_context
def llr_counters_detailed(ctx, interface_name):
    """Show detailed LLR counter statistics per port"""
    cmd = ['llrstat', '-d']
    if interface_name:
        cmd += ['-i', str(interface_name)]
    clicommon.run_command(cmd)
