import click


@click.group()
def sed():
    """SED (Self-Encrypting Drive) password management commands"""
    pass


@sed.command('change-password')
def change_password():
    """Change SED password"""
    try:
        from sonic_platform import platform
        chassis = platform.Platform().get_chassis()
        sed_mgmt = chassis.get_sed_mgmt()
        if sed_mgmt is None:
            click.echo("Error: SED management not supported on this platform")
            return
        password = click.prompt(
            'New SED password',
            hide_input=True,
            confirmation_prompt=True
        )
        click.echo("Handling SED password change started...")
        success = sed_mgmt.change_sed_password(password)
        if success:
            click.echo("SED password change process completed successfully")
        else:
            click.echo("Error: SED password change failed")
    except Exception as e:
        click.echo(f"Error changing SED password: {str(e)}")


@sed.command('reset-password')
def reset_password():
    """Reset SED password to default"""
    try:
        from sonic_platform import platform
        chassis = platform.Platform().get_chassis()
        sed_mgmt = chassis.get_sed_mgmt()
        if sed_mgmt is None:
            click.echo("Error: SED management not supported on this platform")
            return
        click.echo("Handling SED password reset started...")
        success = sed_mgmt.reset_sed_password()
        if success:
            click.echo("SED password reset process completed successfully")
        else:
            click.echo("Error: SED password reset failed")
    except Exception as e:
        click.echo(f"Error resetting SED password: {str(e)}")


WIPE_SSD_START_BANNER = (
    "=========================================================================\n"
    " SSD ERASE STARTED\n"
    "   * Do NOT power off the switch or interrupt this session.\n"
    "   * The wipe runs from a RAM-disk and will keep going even if SSH drops.\n"
    "   * Follow progress in syslog: journalctl -f -t ssd_erase.sh\n"
    "   * When it finishes, reboot with: sudo /sbin/reboot\n"
    "========================================================================="
)


@sed.command('wipe-ssd')
@click.option('-y', '--yes', is_flag=True, default=False,
              help='Skip the interactive confirmation prompt.')
def wipe_ssd(yes):
    """Securely wipe the boot SSD (SED PSID revert + NVMe sanitize).

    IRREVERSIBLE: after wipe the switch cannot boot until re-imaged.
    """
    try:
        from sonic_platform import platform
        chassis = platform.Platform().get_chassis()
        sed_mgmt = chassis.get_sed_mgmt()
        if sed_mgmt is None:
            click.echo("Error: SED management not supported on this platform")
            return
        if not yes:
            click.confirm(
                'This will PERMANENTLY erase the SSD. Continue?',
                default=False,
                abort=True,
            )
        click.echo(WIPE_SSD_START_BANNER)
        success = sed_mgmt.wipe_ssd()
        if success:
            click.echo("SSD wipe completed successfully. Reboot now with `sudo /sbin/reboot`.")
        else:
            click.echo("Error: SSD wipe failed")
    except click.exceptions.Abort:
        raise
    except Exception as e:
        click.echo(f"Error wiping SSD: {str(e)}")
