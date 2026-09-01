"""show secure-boot commands."""

import json
import subprocess

import click
from tabulate import tabulate

try:
    import utilities_common.cli as clicommon
    GROUP_CLS = clicommon.AliasedGroup
except Exception:  # pragma: no cover
    GROUP_CLS = click.Group

BACKEND = "/usr/sbin/tam-uefi-tool"
TIMEOUT = 180

class BackendError(RuntimeError):
    pass

def run_backend(*args):
    try:
        cp = subprocess.run([BACKEND] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=TIMEOUT, check=False)
    except FileNotFoundError:
        raise BackendError(f"{BACKEND} is not installed")
    except subprocess.TimeoutExpired:
        raise BackendError("secure boot backend timed out")
    try:
        data = json.loads(cp.stdout or "{}")
    except json.JSONDecodeError:
        raise BackendError("invalid backend response: {}".format((cp.stdout or "").strip()))
    if cp.returncode != 0 or "error" in data:
        raise BackendError(data.get("error", "secure boot backend failed"))
    return data

@click.group(name="secure-boot", cls=GROUP_CLS)
def secure_boot():
    """Show Secure Boot certificate backend state."""
    pass

@secure_boot.command()
def status():
    """Show Secure Boot backend mode and key state."""
    try:
        data = run_backend("status")
    except BackendError as exc:
        raise click.ClickException(str(exc))
    m = data["mode"]
    click.echo("Secure Boot Backend: platform")
    click.echo("UEFI Mode: {} ({}, {})".format(m["raw"], m["hex"], m["name"]))
    click.echo("")
    rows=[]; keys=data["keys"]
    for var in ("PK", "KEK", "db", "dbx"):
        vendor=keys.get(f"{var}Vendor", {})
        customer=keys.get(f"{var}Customer", {})
        rows.append([var, vendor.get("state","unknown"), vendor.get("certificate_count","-"), customer.get("state","unknown"), customer.get("certificate_count","-")])
    click.echo(tabulate(rows, headers=["Variable","Vendor State","Vendor Certs","Customer State","Customer Certs"], tablefmt="simple"))

@secure_boot.command()
def mode():
    """Show Secure Boot backend mode."""
    try:
        data = run_backend("mode")
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
        data = run_backend("keys")
    except BackendError as exc:
        raise click.ClickException(str(exc))
    rows=[]
    for var in ("PK","KEK","db","dbx"):
        for store,suffix in (("vendor","Vendor"),("customer","Customer")):
            item=data.get(f"{var}{suffix}", {})
            rows.append([var,store,item.get("state","unknown"),item.get("certificate_count","-")])
    click.echo(tabulate(rows, headers=["Variable","Store","State","Certificates"], tablefmt="simple"))

@secure_boot.command(name="key")
@click.argument("variable", type=click.Choice(["PK","KEK","db","dbx"], case_sensitive=False))
@click.option("--store", type=click.Choice(["vendor","customer"]), default="customer", show_default=True)
def key_cmd(variable, store):
    """Show one Secure Boot variable state."""
    try:
        data = run_backend("key", variable, "--store", store)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    item = next(iter(data.values()))
    rows = [["Variable", variable], ["Store", store], ["State", item.get("state","unknown")], ["Certificates", item.get("certificate_count","-")]]
    click.echo(tabulate(rows, tablefmt="plain"))
