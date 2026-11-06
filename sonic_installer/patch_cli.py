"""Click command registration for SONiC Hotfix package management."""

import json
from pathlib import Path

import click

from .patch_manager import PatchError, PatchManager


def _invoke(action):
    try:
        return action()
    except PatchError as error:
        raise click.ClickException(str(error))


def register_patch_commands(
        group,
        abort_if_false,
        manager_factory=PatchManager):
    """Register Hotfix commands on the sonic-installer Click group."""

    @group.command("patch-install-precheck")
    @click.argument("patch_file", type=click.Path(exists=True,
                    dir_okay=False, path_type=Path))
    def patch_install_precheck(patch_file):
        """Validate a Hotfix package without installing it."""
        result = _invoke(lambda: manager_factory().precheck(patch_file))
        click.echo(json.dumps(result, indent=2))

    @group.command("patch-install")
    @click.option(
        "-y", "--yes", is_flag=True, callback=abort_if_false,
        expose_value=False, prompt="New patch will be installed, continue?",
    )
    @click.argument("patch_file", type=click.Path(exists=True,
                    dir_okay=False, path_type=Path))
    def patch_install(patch_file):
        """Install all sub-patches from a Hotfix package."""
        installed = _invoke(lambda: manager_factory().install(patch_file))
        if installed:
            click.echo("Installed patches: {}".format(", ".join(installed)))
        else:
            click.echo("All patches are already installed")

    @group.command("hotpatch-install-single")
    @click.option(
        "-y", "--yes", is_flag=True, callback=abort_if_false,
        expose_value=False, prompt="Hotpatch will be reapplied, continue?",
    )
    @click.argument("patch_file", type=click.Path(exists=True,
                    dir_okay=False, path_type=Path))
    def hotpatch_install_single(patch_file):
        """Reapply one persisted function hotpatch."""
        _invoke(lambda: manager_factory().reapply_hotpatch(patch_file))
        click.echo("Hotpatch reapplied: {}".format(patch_file.name))

    @group.command("patch-uninstall")
    @click.option(
        "-y", "--yes", is_flag=True, callback=abort_if_false,
        expose_value=False, prompt="Patch will be uninstalled, continue?",
    )
    @click.option("--single", is_flag=True,
                  help="Uninstall exactly one sub-patch")
    @click.argument("patch_name")
    def patch_uninstall(patch_name, single):
        """Uninstall a patch or all patches installed by one Hotfix."""
        removed = _invoke(lambda: manager_factory(
        ).uninstall(patch_name, single=single))
        click.echo("Uninstalled patches: {}".format(", ".join(removed)))

    @group.command("patch-list")
    @click.option("--json", "json_format", is_flag=True, help="Output JSON")
    @click.option("--name", help="Display one installed patch")
    def patch_list(json_format, name):
        """List installed Hotfix sub-patches."""
        patches = _invoke(lambda: manager_factory().list_patches())
        if name:
            patches = [patch for patch in patches if patch.get("name") == name]
            if not patches:
                raise click.ClickException(
                    "Patch is not installed: {}".format(name))
        if json_format:
            click.echo(json.dumps(patches, indent=2))
            return
        if not patches:
            click.echo("No patches installed")
            return
        for index, patch in enumerate(patches, 1):
            click.echo("{}. {} ({})".format(
                index,
                patch.get("name", ""),
                patch.get("desc", ""),
            ))
            if name and patch.get("metadata"):
                for key, value in patch["metadata"].items():
                    click.echo("   {}: {}".format(key, value))

    @group.command("patch-status")
    @click.option(
        "--section",
        type=click.Choice(["operation", "live", "pending"],
                          case_sensitive=False),
        help="Display one status section",
    )
    def patch_status(section):
        """Display Hotfix operation, live, and pending status."""
        status = _invoke(lambda: manager_factory().status(section))
        click.echo(json.dumps(status, indent=2))
