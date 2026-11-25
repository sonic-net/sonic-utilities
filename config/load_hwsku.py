import click
import os
import shutil
import subprocess
from datetime import datetime

import utilities_common.cli as clicommon
from utilities_common.hwsku import get_available_hwskus
from sonic_py_common import logger
from sonic_py_common import device_info

log = logger.Logger()
log.set_min_log_priority_info()

# Constants
CONFIG_DB_PATH = "/etc/sonic/config_db.json"
SONIC_CFGGEN_PATH = "/usr/local/bin/sonic-cfggen"

#
# HWSKU helpers ------------------------------------------------------------------------------------------------------
#


def is_valid_hwsku(hwsku_name):
    """
    Validate if the given HWSKU name is valid for the current platform

    Args:
        hwsku_name: The HWSKU name to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: Boolean indicating if the HWSKU is valid
        - error_message: String with error details if invalid, None if valid
    """
    platform = device_info.get_platform()
    if not platform:
        return False, "Unable to determine platform from /host/machine.conf"

    available_hwskus = get_available_hwskus()
    if not available_hwskus:
        return False, f"No HWSKUs found for platform '{platform}'"

    if hwsku_name not in available_hwskus:
        return False, f"Invalid HWSKU '{hwsku_name}'. Available HWSKUs: {', '.join(sorted(available_hwskus))}"

    return True, None


def complete_hwsku_names(ctx, args, incomplete):
    """
    Autocomplete function for HWSKU names

    Args:
        ctx: Click context
        args: Current arguments
        incomplete: The incomplete string being typed

    Returns:
        List of HWSKU names that match the incomplete string
    """
    available_hwskus = get_available_hwskus()
    return [hwsku for hwsku in available_hwskus if hwsku.startswith(incomplete)]

#
# HWSKU CLI ----------------------------------------------------------------------------------------------------------
#


@click.group(
    name="hwsku",
    cls=clicommon.AliasedGroup
)
def hwsku():
    """ Configure hardware SKU """
    pass


@hwsku.command("load")
@click.argument(
    "hwsku_name",
    nargs=1,
    required=True,
    shell_complete=complete_hwsku_names
)
@click.option(
    '-y', '--yes',
    is_flag=True,
    help='Automatically answer yes to prompts'
)
@click.option(
    '-r', '--reload',
    is_flag=True,
    help='Reload configuration after generating new config'
)
def load(hwsku_name, yes, reload):
    """ Load hardware SKU configuration """
    ctx = click.get_current_context()

    try:
        # Validate the HWSKU name
        is_valid, error_msg = is_valid_hwsku(hwsku_name)
        if not is_valid:
            log.log_error(f"HWSKU validation failed: {error_msg}")
            ctx.fail(error_msg)

        # Get current HWSKU for backup naming
        current_hwsku = device_info.get_hwsku()
        if not current_hwsku:
            current_hwsku = "unknown"

        # Create backup directory if it doesn't exist
        backup_dir = "/etc/sonic/backup_config"
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir, mode=0o755)
            except Exception as e:
                error_msg = f"Failed to create backup directory: {str(e)}"
                log.log_error(error_msg)
                ctx.fail(error_msg)

        # Create backup path with timestamp: /etc/sonic/backup_config/<hwsku>_<timestamp>.json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/{current_hwsku}_{timestamp}.json"

        # Confirm with user before proceeding (unless -y flag is used)
        if not yes:
            click.echo("\nThis will:")
            click.echo(f"  1. Backup current config to {backup_path}")
            click.echo(f"  2. Generate new config for HWSKU '{hwsku_name}'")
            if reload:
                click.echo("  3. Reload the configuration (services will restart)")
            else:
                click.echo("  3. Skip reload (you will need to manually reload)")
            click.echo("")
            if not click.confirm("Do you want to continue?"):
                click.echo("Operation cancelled.")
                return

        click.echo(f"\nLoading hardware SKU: {hwsku_name}")
        log.log_notice(f"Loading hardware SKU: {hwsku_name} (current: {current_hwsku})")

        # Step 1: Backup current config_db.json
        if os.path.exists(CONFIG_DB_PATH):
            try:
                shutil.copy2(CONFIG_DB_PATH, backup_path)
                log.log_notice(f"Backed up config to {backup_path}")
            except Exception as e:
                error_msg = f"Failed to backup config: {str(e)}"
                log.log_error(error_msg)
                ctx.fail(error_msg)
        else:
            click.echo(f"Warning: {CONFIG_DB_PATH} does not exist, skipping backup")

        # Step 2: Generate new config using sonic-cfggen
        try:
            # Run: sonic-cfggen -H -k <hwsku_name> --print-data > /etc/sonic/config_db.json
            command = [SONIC_CFGGEN_PATH, '-H', '-k', hwsku_name, '--print-data']
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )

            # Write the output to config_db.json
            with open(CONFIG_DB_PATH, 'w') as f:
                f.write(result.stdout)

            log.log_notice(f"Generated new config for HWSKU '{hwsku_name}'")
            click.echo("Config generated successfully")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to generate config: {e.stderr if e.stderr else str(e)}"
            log.log_error(error_msg)
            # Restore backup if generation failed
            if os.path.exists(backup_path):
                click.echo(f"Restoring backup from {backup_path}...")
                shutil.copy2(backup_path, CONFIG_DB_PATH)
                os.remove(backup_path)
                log.log_notice(f"Backup restored and removed: {backup_path}")
            ctx.fail(error_msg)
        except Exception as e:
            error_msg = f"Failed to generate config: {str(e)}"
            log.log_error(error_msg)
            # Restore backup if generation failed
            if os.path.exists(backup_path):
                click.echo(f"Restoring backup from {backup_path}...")
                shutil.copy2(backup_path, CONFIG_DB_PATH)
                os.remove(backup_path)
                log.log_notice(f"Backup restored and removed: {backup_path}")
            ctx.fail(error_msg)

        # Step 3: Reload configuration (optional)
        if reload:
            click.echo("Reloading configuration...")
            try:
                # Run: config reload -y
                reload_command = ['config', 'reload', '-y', '-f']
                subprocess.run(reload_command, check=True)

                log.log_notice(f"Successfully loaded HWSKU '{hwsku_name}' and reloaded config")
                click.echo(f"\nHardware SKU '{hwsku_name}' loaded successfully!")
                click.echo("Configuration reloaded.")
                click.echo(f"Backup saved to: {backup_path}")

            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to reload config: {str(e)}"
                log.log_error(error_msg)
                click.echo("\nWarning: Config was generated but reload failed.")
                click.echo("You can manually reload using: config reload -y")
                restore_cmd = f"cp {backup_path} {CONFIG_DB_PATH} && config reload -y"
                click.echo(f"Or restore backup using: {restore_cmd}")
                ctx.fail(error_msg)
        else:
            log.log_notice(f"Successfully generated config for HWSKU '{hwsku_name}' (reload skipped)")
            click.echo(f"\nHardware SKU '{hwsku_name}' config generated successfully!")
            click.echo(f"Backup saved to: {backup_path}")
            click.echo("\nTo apply the new configuration, run: config reload -y")

    except Exception as e:
        log.log_error(f"Failed to load hardware SKU: {str(e)}")
        ctx.fail(str(e))
