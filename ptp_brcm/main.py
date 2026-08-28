import click
from swsscommon.swsscommon import ConfigDBConnector

import utilities_common.cli as clicommon
from utilities_common.general import load_db_config

from .bcm_cint import run_bcm_cint, run_bcmcmd
from .portmap import interface_to_bcm_port


def _resolve_bcm_port(interface):
    load_db_config()
    config_db = ConfigDBConnector()
    config_db.connect()
    if not clicommon.is_valid_port(config_db, interface):
        raise click.ClickException('{} is not a valid Ethernet port'.format(interface))
    try:
        return interface_to_bcm_port(interface)
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc))


@click.command('ptp-1step')
@click.argument('interface')
def ptp_1step_cmd(interface):
    """Enable one-step PTP on a BCM port (e.g. Ethernet0)."""
    bcm_port = _resolve_bcm_port(interface)
    run_bcm_cint('set_ptp_state(0, {});'.format(bcm_port))


@click.command('ptp-get-state')
@click.argument('interface')
def ptp_get_state_cmd(interface):
    """Show BCM PTP state for a port (e.g. Ethernet0)."""
    bcm_port = _resolve_bcm_port(interface)
    run_bcm_cint('get_ptp_state(0, {});'.format(bcm_port))


@click.command('ptp-get-counter')
def ptp_get_counter_cmd():
    """Show BCM PTP timestamp counter."""
    run_bcm_cint('getCounter();')


@click.command('ptp-fw-status')
def ptp_fw_status_cmd():
    """Show BCM EDK firmware status (equivalent to bcmcmd edk -c info)."""
    run_bcmcmd('edk -c info')
