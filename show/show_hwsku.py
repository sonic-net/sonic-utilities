import click

import utilities_common.cli as clicommon
from utilities_common.hwsku import get_available_hwskus
from sonic_py_common import device_info

#
# 'hwsku' group ("show hwsku ...")
#


@click.group(cls=clicommon.AliasedGroup)
def hwsku():
    """Show hardware SKU information"""
    pass


# 'profiles' subcommand ("show hwsku profiles")
@hwsku.command()
def profiles():
    """Show available hardware SKU profiles"""
    platform = device_info.get_platform()
    if not platform:
        click.echo("Error: Unable to determine platform from /host/machine.conf")
        return

    available_hwskus = get_available_hwskus()
    if not available_hwskus:
        click.echo(f"No HWSKUs found for platform '{platform}'")
        return

    # Get current HWSKU
    current_hwsku = device_info.get_hwsku()

    click.echo(f"Platform: {platform}")
    click.echo("\nAvailable HWSKU Profiles:")
    for hwsku in sorted(available_hwskus):
        if hwsku == current_hwsku:
            click.echo(f"  * {hwsku} (current)")
        else:
            click.echo(f"  - {hwsku}")
