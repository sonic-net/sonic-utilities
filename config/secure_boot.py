"""config secure-boot commands."""

import click

from utilities_common.secure_boot import BackendError, run_backend

try:
    import utilities_common.cli as clicommon
    GROUP_CLS = clicommon.AliasedGroup
except Exception:  # pragma: no cover
    GROUP_CLS = click.Group

TIMEOUT = 300


@click.group(name="secure-boot", cls=GROUP_CLS)
def secure_boot():
    """Configure Secure Boot certificate backend."""
    pass


@secure_boot.group(cls=GROUP_CLS)
def certificate():
    """Configure Secure Boot certificates."""
    pass


@certificate.command(name="update")
@click.argument("variable", type=click.Choice(["PK", "KEK", "db", "dbx"], case_sensitive=False))
@click.argument("auth_var_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--operation", type=click.Choice(["append", "update", "remove"]), default="update", show_default=True)
def certificate_update(variable, auth_var_file, operation):
    """Submit an authenticated variable update file."""
    try:
        result = run_backend(("update", variable, "--file", auth_var_file, "--operation", operation), TIMEOUT)
    except BackendError as exc:
        raise click.ClickException(str(exc))
    click.echo("Secure Boot certificate update submitted successfully")
    click.echo("Variable: {}".format(result.get("variable", variable)))
    click.echo("Operation: {}".format(result.get("operation", operation)))
