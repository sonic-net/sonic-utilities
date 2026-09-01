"""config secure-boot commands."""

import json
import subprocess
import click

try:
    import utilities_common.cli as clicommon
    GROUP_CLS = clicommon.AliasedGroup
except Exception:  # pragma: no cover
    GROUP_CLS = click.Group

BACKEND = "/usr/sbin/tam-uefi-tool"
TIMEOUT = 300

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
    """Configure Secure Boot certificate backend."""
    pass

@secure_boot.group(cls=GROUP_CLS)
def certificate():
    """Configure Secure Boot certificates."""
    pass

@certificate.command(name="update")
@click.argument("variable", type=click.Choice(["PK","KEK","db","dbx"], case_sensitive=False))
@click.argument("auth_var_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--operation", type=click.Choice(["append","update","remove"]), default="update", show_default=True)
def certificate_update(variable, auth_var_file, operation):
    """Submit an authenticated variable update file."""
    try:
        result = run_backend("update", variable, "--file", auth_var_file, "--operation", operation)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    click.echo("Secure Boot certificate update submitted successfully")
    click.echo("Variable: {}".format(result.get("variable", variable)))
    click.echo("Operation: {}".format(result.get("operation", operation)))

@certificate.command(name="install")
@click.argument("variable", type=click.Choice(["PK","KEK","db","dbx"], case_sensitive=False))
@click.argument("auth_var_file", type=click.Path(exists=True, dir_okay=False, readable=True))
def certificate_install(variable, auth_var_file):
    """Install/append an authenticated certificate update."""
    try:
        run_backend("update", variable, "--file", auth_var_file, "--operation", "append")
    except BackendError as exc:
        raise click.ClickException(str(exc))
    click.echo("Secure Boot certificate install submitted successfully")

@certificate.command(name="revoke")
@click.argument("variable", type=click.Choice(["db","dbx"], case_sensitive=False))
@click.argument("auth_var_file", type=click.Path(exists=True, dir_okay=False, readable=True))
def certificate_revoke(variable, auth_var_file):
    """Submit an authenticated revocation update."""
    try:
        run_backend("update", variable, "--file", auth_var_file, "--operation", "append")
    except BackendError as exc:
        raise click.ClickException(str(exc))
    click.echo("Secure Boot revocation update submitted successfully")

@secure_boot.group(cls=GROUP_CLS)
def mode():
    """Configure platform Secure Boot mode."""
    pass

@mode.command(name="set")
@click.argument("ownership_voucher_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--yes", is_flag=True, help="Confirm platform ownership/mode update.")
def mode_set(ownership_voucher_file, yes):
    """Submit a platform ownership voucher."""
    if not yes:
        raise click.ClickException("mode set requires --yes confirmation")
    try:
        run_backend("set-mode", "--file", ownership_voucher_file)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    click.echo("Secure Boot mode update submitted successfully")
