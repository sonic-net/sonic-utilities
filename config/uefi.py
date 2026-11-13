"""config platform security uefi ...

Apply-only. AUTH2/ESL files are built on the owner host. This CLI never
takes a private key and never retries a firmware reject.
"""

import sys

import click
from utilities_common import uefi as uefi_lib


@click.group()
def security():
    """Platform security configuration"""
    pass


@security.group()
def uefi():
    """UEFI Secure Boot key enrollment and updates"""
    pass


def _fail(exc):
    uefi_lib.audit_error(str(exc))
    click.echo(str(exc), err=True)
    raise SystemExit(exc.returncode)


def _confirm(yes, message):
    if not yes:
        click.confirm(message, abort=True)


def _argv():
    return " ".join(["config"] + sys.argv[1:])


@uefi.command()
@click.option("-y", "--yes", is_flag=True, help="Do not prompt")
@click.argument("var", required=True, type=click.Choice(
    ["pk", "kek", "db", "dbx"], case_sensitive=False))
@click.argument("path", required=True, metavar="<file.esl|file.auth>")
def enroll(var, path, yes):
    """Enroll a key in Setup Mode.

    kek/db/dbx take an unsigned ESL (efi-updatevar -e).
    pk takes a self-signed AUTH2 (efi-updatevar -f).
    """
    if var.lower() == "pk":
        _confirm(yes, "Enroll PK (claim). This leaves Setup Mode. Continue?")
    else:
        _confirm(yes, "Enroll {} from {}. Continue?".format(var, path))
    try:
        uefi_lib.audit_notice(
            "'platform security uefi enroll' executing with command: {}".format(_argv()))
        uefi_lib.enroll(var, path)
        uefi_lib.audit_notice(
            "'platform security uefi enroll' applied {} from {}".format(var, path))
    except uefi_lib.UefiError as exc:
        _fail(exc)


@uefi.command()
@click.option("-y", "--yes", is_flag=True, help="Do not prompt")
@click.argument("var", required=True, type=click.Choice(
    ["pk", "kek", "db", "dbx"], case_sensitive=False))
@click.argument("path", required=True, metavar="<file.auth>")
def append(var, path, yes):
    """Append certificates in User Mode (AUTH2 with efi-updatevar -a).

    The AUTH2 must be built with sign-efi-sig-list -a. Revoke is this
    command on dbx. The CLI cannot read APPEND_WRITE from the file.
    """
    _confirm(yes, "Append AUTH2 to {} from {}. Continue?".format(var, path))
    try:
        uefi_lib.audit_notice(
            "'platform security uefi append' executing with command: {}".format(_argv()))
        uefi_lib.append(var, path)
        uefi_lib.audit_notice(
            "'platform security uefi append' applied {} from {}".format(var, path))
    except uefi_lib.UefiError as exc:
        _fail(exc)


@uefi.command("update")
@click.option("-y", "--yes", is_flag=True, help="Do not prompt")
@click.argument("var", required=True, type=click.Choice(
    ["pk", "kek", "db", "dbx"], case_sensitive=False))
@click.argument("path", required=True, metavar="<file.auth>")
def update_cmd(var, path, yes):
    """Replace a variable in User Mode (AUTH2, efi-updatevar -f).

    Remove is this command with an AUTH2 whose ESL is the remaining certs.
    """
    _confirm(
        yes,
        "Replace {}. Certificates not in this AUTH2 are removed. Continue?".format(var))
    try:
        uefi_lib.audit_notice(
            "'platform security uefi update' executing with command: {}".format(_argv()))
        uefi_lib.update(var, path)
        uefi_lib.audit_notice(
            "'platform security uefi update' applied {} from {}".format(var, path))
    except uefi_lib.UefiError as exc:
        _fail(exc)


@uefi.command()
@click.option("-y", "--yes", is_flag=True, help="Do not prompt")
@click.argument("path", required=True, metavar="PK.empty.auth")
def unclaim(path, yes):
    """Return to Setup Mode with a PK-signed empty AUTH2.

    This is not 'update pk' with a new certificate.
    """
    _confirm(yes, "Unclaim: return to Setup Mode. Continue?")
    try:
        uefi_lib.audit_notice(
            "'platform security uefi unclaim' executing with command: {}".format(_argv()))
        uefi_lib.unclaim(path)
        uefi_lib.audit_notice(
            "'platform security uefi unclaim' applied from {}".format(path))
    except uefi_lib.UefiError as exc:
        _fail(exc)


def attach(platform_group):
    platform_group.add_command(security)
