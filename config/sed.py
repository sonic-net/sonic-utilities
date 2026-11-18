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
