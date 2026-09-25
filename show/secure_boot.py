"""show secure-boot commands."""

import click
from tabulate import tabulate

from utilities_common.secure_boot import BackendError, run_backend

try:
    import utilities_common.cli as clicommon
    GROUP_CLS = clicommon.AliasedGroup
except Exception:  # pragma: no cover
    GROUP_CLS = click.Group

TIMEOUT = 180


@click.group(name="secure-boot", cls=GROUP_CLS)
def secure_boot():
    """Show Secure Boot certificate backend state."""
    pass


@secure_boot.command()
def status():
    """Show Secure Boot backend mode and key state."""
    try:
        data = run_backend(("status",), TIMEOUT)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    m = data["mode"]
    click.echo("UEFI Mode: {} ({}, {})".format(m["raw"], m["hex"], m["name"]))
    click.echo("")
    keys = data["keys"]
    has_unified = any(f"{var}Unified" in keys for var in ("PK", "KEK", "db", "dbx"))
    if has_unified:
        rows = []
        for var in ("PK", "KEK", "db", "dbx"):
            item = keys.get(f"{var}Unified", {})
            rows.append([var, item.get("state", "unknown"), item.get("entry_count", "-")])
        click.echo(tabulate(
            rows,
            headers=["Variable", "State", "Entries"],
            tablefmt="simple",
        ))
        return
    rows = []
    for var in ("PK", "KEK", "db", "dbx"):
        vendor = keys.get(f"{var}Vendor", {})
        customer = keys.get(f"{var}Customer", {})
        rows.append([
            var,
            vendor.get("state", "unknown"),
            vendor.get("entry_count", "-"),
            customer.get("state", "unknown"),
            customer.get("entry_count", "-"),
        ])
    click.echo(tabulate(
        rows,
        headers=["Variable", "Vendor State", "Vendor Entries", "Customer State", "Customer Entries"],
        tablefmt="simple",
    ))


@secure_boot.command()
def mode():
    """Show Secure Boot backend mode."""
    try:
        data = run_backend(("mode",), TIMEOUT)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    rows = [
        ["Mode", "{} ({})".format(data["raw"], data["name"])],
        ["Mode Hex", data["hex"]],
        ["Vendor store write", "yes" if data["policy"].get("vendor_store_write") else "no"],
        ["Vendor store lock", "yes" if data["policy"].get("vendor_store_lock") else "no"],
        ["Customer store write", "yes" if data["policy"].get("customer_store_write") else "no"],
        ["Customer store lock", "yes" if data["policy"].get("customer_store_lock") else "no"],
    ]
    click.echo(tabulate(rows, tablefmt="plain"))


@secure_boot.command(name="keys")
def keys_cmd():
    """Show PK/KEK/db/dbx state."""
    try:
        data = run_backend(("keys",), TIMEOUT)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    rows = []
    for var in ("PK", "KEK", "db", "dbx"):
        unified = data.get(f"{var}Unified")
        if unified is not None:
            rows.append([var, "unified", unified.get("state", "unknown"), unified.get("entry_count", "-")])
            continue
        for store, suffix in (("vendor", "Vendor"), ("customer", "Customer")):
            item = data.get(f"{var}{suffix}", {})
            rows.append([var, store, item.get("state", "unknown"), item.get("entry_count", "-")])
    click.echo(tabulate(rows, headers=["Variable", "Store", "State", "Entries"], tablefmt="simple"))


@secure_boot.command(name="key")
@click.argument("variable", type=click.Choice(["PK", "KEK", "db", "dbx"], case_sensitive=False))
@click.option("--store", type=click.Choice(["vendor", "customer", "unified"]), default=None)
def key_cmd(variable, store):
    """Show one Secure Boot variable state."""
    # Omitting --store lets the selected backend pick its natural default
    # (unified for generic UEFI, customer for platform backends).
    args = ["key", variable]
    if store is not None:
        args.extend(["--store", store])
    try:
        data = run_backend(tuple(args), TIMEOUT)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    if not data:
        raise click.ClickException("invalid empty backend response")
    key_name, item = next(iter(data.items()))
    if store is not None:
        display_store = store
    elif key_name.endswith("Unified"):
        display_store = "unified"
    elif key_name.endswith("Vendor"):
        display_store = "vendor"
    elif key_name.endswith("Customer"):
        display_store = "customer"
    else:
        display_store = "unknown"
    rows = [
        ["Variable", variable],
        ["Store", display_store],
        ["State", item.get("state", "unknown")],
        ["Entries", item.get("entry_count", "-")],
    ]
    click.echo(tabulate(rows, tablefmt="plain"))
