import click


@click.group()
def sed():
    """SED (Self-Encrypting Drive) password management commands"""
    pass


@sed.command('change-password')
@click.option('-p', '--password', required=True, help='New SED password')
def change_password(password):
    """Change SED password"""
    try:
        from sonic_platform import platform
        chassis = platform.Platform().get_chassis()
        if not hasattr(chassis, 'change_sed_password'):
            click.echo("Error: SED management not supported on this platform")
            return
        click.echo("Handling SED password change started...")
        success = chassis.change_sed_password(password)
        if success:
            click.echo("SED password change process completed successfully")
        else:
            click.echo("Error: SED password change failed")
    except NotImplementedError:
        click.echo("Error: SED management not implemented on this platform")
    except Exception as e:
        click.echo(f"Error changing SED password: {str(e)}")


@sed.command('reset-password')
def reset_password():
    """Reset SED password to default"""
    try:
        from sonic_platform import platform
        chassis = platform.Platform().get_chassis()
        if not hasattr(chassis, 'reset_sed_password'):
            click.echo("Error: SED management not supported on this platform")
            return
        click.echo("Handling SED password reset started...")
        success = chassis.reset_sed_password()
        if success:
            click.echo("SED password reset process completed successfully")
        else:
            click.echo("Error: SED password reset failed")
    except NotImplementedError:
        click.echo("Error: SED management not implemented on this platform")
    except Exception as e:
        click.echo(f"Error resetting SED password: {str(e)}")
