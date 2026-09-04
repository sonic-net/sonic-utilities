import click
import utilities_common.cli as clicommon
from sonic_py_common import device_info


def _reject_non_switch_host():
    if not device_info.is_switch_host():
        raise click.ClickException('Operation only supported on Switch-Host')


def _reject_unless_switch_host_openbmc():
    _reject_non_switch_host()
    if device_info.get_bmc_os() == device_info.BMC_OS_SONIC:
        raise click.ClickException('Operation not supported when BMC OS is sonic')


# 'bmc' group ('config bmc ...')
@click.group('bmc')
def bmc():
    """BMC (Baseboard Management Controller) configuration tasks"""
    pass


# config bmc os <openbmc|sonic>
@bmc.command('os')
@click.argument('os_type', metavar='<os>',
                type=click.Choice([device_info.BMC_OS_OPENBMC, device_info.BMC_OS_SONIC],
                                  case_sensitive=False))
@clicommon.pass_db
def config_bmc_os(db, os_type):
    """Configure BMC operating system (openbmc: Redfish, sonic: Redis)"""
    _reject_non_switch_host()
    db.cfgdb.mod_entry('DEVICE_METADATA', 'bmc', {'os': os_type.lower()})
    click.echo(f"BMC OS set to {os_type.lower()}")


# config bmc reset-root-password
@bmc.command('reset-root-password')
def reset_root_password():
    """Reset BMC root password to default"""
    _reject_unless_switch_host_openbmc()
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
    _reject_unless_switch_host_openbmc()
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
    _reject_unless_switch_host_openbmc()
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
