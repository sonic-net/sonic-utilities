import click


ERASE_START_BANNER = (
    "=========================================================================\n"
    " SSD ERASE STARTED\n"
    "   * Do NOT power off the switch or interrupt this session.\n"
    "   * The erase runs from a RAM-disk and will keep going even if SSH drops.\n"
    "   * Follow progress in syslog: journalctl -f -t ssd_erase.sh\n"
    "   * When it finishes, reboot with: sudo /sbin/reboot\n"
    "========================================================================="
)


# ==================== Entry point ====================
@click.command()
@click.option('-y', '--yes', is_flag=True, default=False, help='Skip the interactive confirmation prompt.')
def ssd_erase(yes):
    """Securely erase the boot SSD (SED PSID revert + NVMe sanitize).

    IRREVERSIBLE: after erase the switch cannot boot until re-imaged.
    """
    try:
        from sonic_platform import platform
        chassis = platform.Platform().get_chassis()
        sed_mgmt = chassis.get_sed_mgmt()
        if sed_mgmt is None:
            click.echo("Error: SED management not supported on this platform")
            raise click.exceptions.Exit(1)
        if not yes:
            click.confirm(
                'This will PERMANENTLY erase the SSD. Continue?',
                default=False,
                abort=True,
            )
        click.echo(ERASE_START_BANNER)
        success = sed_mgmt.wipe_ssd()
        if success:
            click.echo("SSD erase completed successfully. Reboot now with `sudo /sbin/reboot`.")
        else:
            click.echo("Error: SSD erase failed")
            raise click.exceptions.Exit(1)
    except (click.exceptions.Abort, click.exceptions.Exit):
        raise
    except Exception as e:
        click.echo(f"Error erasing SSD: {str(e)}")
        raise click.exceptions.Exit(1)


if __name__ == '__main__':
    ssd_erase()
