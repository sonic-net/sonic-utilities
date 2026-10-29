"""Display the HLD protection state and reconciliation diagnostics."""

import click
from natsort import natsorted
from sonic_py_common import multi_asic
from tabulate import tabulate

import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util


TABLE = "BRIDGE_PORT_PROTECTION_STATE"


@click.command(name="bridge-port-protection")
@click.argument("interface", required=False)
@click.option("--verbose", is_flag=True, help="Show HLD reconciliation timing, arbitration source and cache diagnostics.")
@click.option("-n", "--namespace", default=None,
              type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
              help="ASIC namespace; default shows all front-end ASICs.")
@clicommon.pass_db
def bridge_port_protection(db, interface, verbose, namespace):
    """Show operator intent, observed SAI path and HLD reconciliation diagnostics."""
    is_multi = multi_asic.is_multi_asic()
    if namespace is not None:
        clients = {namespace: db.db_clients[namespace]}
    elif is_multi:
        clients = {ns: conn for ns, conn in db.db_clients.items()
                   if ns in multi_asic.get_front_end_namespaces()}
    else:
        clients = {"": db.db_clients[""]}

    rows = []
    for ns, conn in natsorted(clients.items()):
        keys = conn.keys(conn.STATE_DB, TABLE + "|*") or []
        for key in natsorted(keys):
            name = key.split("|", 1)[1]
            if interface is not None and name.lower() != interface.lower():
                continue
            state = conn.get_all(conn.STATE_DB, key) or {}
            if not state:
                continue
            software = state.get("protection_type") == "sw_protection"
            path = state.get("protection_state")
            health = state.get("reconciliation_state")
            if health not in ("STEADY", "CONVERGING", "INCONSISTENT") or (software and health == "CONVERGING"):
                health = "INCONSISTENT"
            convergence = "n/a" if software else state.get("convergence_mode", "—")
            outcome = state.get("last_arbitration_outcome", "none")
            if software or convergence == "disabled":
                arbitration = "n/a"
            elif outcome == "none":
                arbitration = "none"
            else:
                arbitration = "{} ({}) @ {}".format(
                    outcome, state.get("last_arbitration_source", "—"),
                    state.get("last_arbitration_ts") or "—")
            row = [name]
            if is_multi:
                row.append(ns or "host")
            row.extend([path if path in ("PRIMARY", "PROTECTION") else "—",
                        state.get("protection_type") or "—", convergence,
                        health,
                        state.get("admin_mode") or "—", arbitration,
                        state.get("last_resync_ts") or "—"])
            if verbose:
                row.extend(["n/a" if software or convergence == "disabled" else
                            state.get("t_reconcile_armed_at") or "—",
                            "n/a" if software or convergence == "disabled" else
                            state.get("last_arbitration_source") or "—",
                            "n/a" if software else state.get("last_cache_update_ts") or "—"])
            rows.append(row)

    if not rows:
        click.echo("No bridge-port protection state available." if interface is None else
                   "No bridge-port protection state available for {}.".format(interface))
        return
    headers = ["INTERFACE"]
    if is_multi:
        headers.append("NAMESPACE")
    headers.extend(["STATE", "TYPE", "CONVERGENCE", "RECONCILIATION",
                    "ADMIN_MODE", "LAST_ARBITRATION", "LAST_RESYNC"])
    if verbose:
        headers.extend(["T_RECONCILE_ARMED_AT", "LAST_ARBITRATION_SOURCE", "LAST_CACHE_UPDATE"])
    click.echo(tabulate(rows, headers, tablefmt="simple"))
