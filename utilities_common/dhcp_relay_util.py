import click
import utilities_common.cli as clicommon


def restart_dhcp_relay_service():
    """
    Restart dhcp_relay service
    """
    click.echo("Restarting DHCP relay service...")
    clicommon.run_command(["systemctl", "stop", "dhcp_relay"], display_cmd=False)
    clicommon.run_command(["systemctl", "reset-failed", "dhcp_relay"], display_cmd=False)
    clicommon.run_command(["systemctl", "start", "dhcp_relay"], display_cmd=False)


def handle_restart_dhcp_relay_service():
    try:
        restart_dhcp_relay_service()
    except SystemExit as e:
        ctx = click.get_current_context()
        ctx.fail("Restart service dhcp_relay failed with error {}".format(e))
