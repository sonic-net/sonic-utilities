import click


# 'bmc' group ('config bmc ...')
@click.group('bmc')
def bmc():
    """BMC (Baseboard Management Controller) configuration tasks"""
    pass


# config bmc reset-root-password
@bmc.command('reset-root-password')
def reset_root_password():
    """Reset BMC root password to default"""
    try:
        import sonic_platform
        chassis = sonic_platform.platform.Platform().get_chassis()
        bmc = chassis.get_bmc()
        if bmc is None:
            click.echo("BMC is not available on this platform")
            return
        ret, msg = bmc.reset_root_password()
        if ret == 0:
            click.echo("BMC root password reset successful")
        else:
            click.echo(f"BMC root password reset failed: {msg}")
    except Exception as e:
        click.echo(f'Error: {str(e)}')


# config bmc open-session
@bmc.command('open-session')
def open_session():
    """Open a session with the BMC"""
    try:
        import sonic_platform
        chassis = sonic_platform.platform.Platform().get_chassis()
        bmc = chassis.get_bmc()
        if bmc is None:
            click.echo("BMC is not available on this platform")
            return
        ret, (msg, credentials) = bmc.open_session()
        if ret != 0 or not credentials:
            click.echo(f"Failed to open session: {msg}")
            return
        click.echo(f"Session ID: {credentials[0]}")
        click.echo(f"Token: {credentials[1]}")
    except Exception as e:
        click.echo(f'Error: {str(e)}')


# config bmc close-session --session-id <session-id>
@bmc.command('close-session')
@click.option('-s', '--session-id', required=True, help='Session ID to close')
def close_session(session_id):
    """Close a session with the BMC"""
    try:
        import sonic_platform
        chassis = sonic_platform.platform.Platform().get_chassis()
        bmc = chassis.get_bmc()
        if bmc is None:
            click.echo("BMC is not available on this platform")
            return
        ret, msg = bmc.close_session(session_id)
        if ret == 0:
            click.echo("Session closed successfully")
        else:
            click.echo(f"Failed to close session: {msg}")
    except Exception as e:
        click.echo(f'Error: {str(e)}')
