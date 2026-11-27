"""show platform security uefi ..."""

import click
from utilities_common import uefi as uefi_lib
from utilities_common import uefi_parser


@click.group()
def security():
    """Show platform security information"""
    pass


@security.group()
def uefi():
    """Show UEFI Secure Boot variables"""
    pass


def _fail(exc):
    click.echo(str(exc), err=True)
    raise SystemExit(exc.returncode)


@uefi.command()
def status():
    """Show SetupMode and SecureBoot"""
    try:
        setup, secure = uefi_lib.read_status()
    except uefi_lib.UefiError as exc:
        _fail(exc)
    click.echo(uefi_lib.format_status(setup, secure), nl=False)


@uefi.command()
@click.argument("var", required=True, type=click.Choice(
    ["all", "pk", "kek", "db", "dbx"], case_sensitive=False))
def variables(var):
    """Show UEFI PK, KEK, db, or dbx (efi-readvar)"""
    try:
        target = None if var.lower() == "all" else var
        out = uefi_lib.read_variables(target)
    except uefi_lib.UefiError as exc:
        _fail(exc)
    click.echo(out, nl=False)


@uefi.command()
@click.argument("path", required=True, type=click.Path(exists=True, dir_okay=False),
                metavar="<file.auth|file.esl>")
def inspect(path):
    """Dump AUTH2/ESL layout for debug (does not apply the file).

    Algorithm-agnostic: RSA-2048/SHA-256, RSA-4096/SHA-384, and PQC.
    Prints EFI_TIME, PKCS#7 size and digest/key OIDs, ESL type, and
    certificates or hashes. Cannot show append vs replace.
    """
    try:
        click.echo(uefi_parser.format_payload(path), nl=False)
    except uefi_lib.UefiError as exc:
        _fail(exc)


@uefi.command()
@click.argument("var", required=True, type=click.Choice(
    ["pk", "kek", "db", "dbx"], case_sensitive=False))
@click.argument("path", required=True, type=click.Path(exists=True, dir_okay=False),
                metavar="<file.auth|file.esl>")
def compare(var, path):
    """Compare current UEFI store to an AUTH2/ESL file (does not apply)."""
    try:
        click.echo(uefi_lib.format_compare(var, path), nl=False)
    except uefi_lib.UefiError as exc:
        _fail(exc)


@uefi.command()
def health():
    """Check enrolled certificate hygiene (expiry, db/dbx overlap).

    Warnings only. Firmware typically still trusts expired Secure Boot certs.
    """
    try:
        click.echo(uefi_lib.format_health(), nl=False)
    except uefi_lib.UefiError as exc:
        _fail(exc)


def attach(platform_group):
    platform_group.add_command(security)
