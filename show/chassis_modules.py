import click
from natsort import natsorted
from tabulate import tabulate
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.chassis import is_smartswitch, is_bmc
from utilities_common.module import ModuleHelper, NOT_AVAILABLE
from sonic_platform_base.module_base import ModuleBase

import utilities_common.cli as clicommon
from sonic_py_common import multi_asic

CHASSIS_MODULE_INFO_TABLE = 'CHASSIS_MODULE_TABLE'
CHASSIS_MODULE_INFO_KEY_TEMPLATE = 'CHASSIS_MODULE {}'
CHASSIS_MODULE_INFO_DESC_FIELD = 'desc'
CHASSIS_MODULE_INFO_SLOT_FIELD = 'slot'
CHASSIS_MODULE_INFO_OPERSTATUS_FIELD = 'oper_status'
CHASSIS_MODULE_INFO_ADMINSTATUS_FIELD = 'admin_status'
CHASSIS_MODULE_INFO_SERIAL_FIELD = 'serial'

CHASSIS_MIDPLANE_INFO_TABLE = 'CHASSIS_MIDPLANE_TABLE'
CHASSIS_MIDPLANE_INFO_IP_FIELD = 'ip_address'
CHASSIS_MIDPLANE_INFO_ACCESS_FIELD = 'access'

DPU_STATE_TABLE = 'DPU_STATE'
DPU_STATE_READY_STATUS_FIELD = 'ready_status'
DPU_STATE_RECOVERY_STATUS_FIELD = 'recovery_status'
DPU_STATE_RESET_COUNT_FIELD = 'reset_count'
DPU_STATE_LAST_DOWN_TIME_FIELD = 'last_down_time'
DPU_STATE_LAST_READY_TIME_FIELD = 'last_ready_time'

CHASSIS_SERVER = 'redis_chassis.server'
CHASSIS_SERVER_PORT = 6380

@click.group(cls=clicommon.AliasedGroup)
def chassis():
    """Chassis commands group"""
    pass

@chassis.group()
def modules():
    """Show chassis-modules information"""
    pass

@modules.command()
@clicommon.pass_db
@click.argument('chassis_module_name', metavar='<module_name>', required=False)
def status(db, chassis_module_name):
    """Show chassis-modules status"""

    smartswitch = is_smartswitch()
    header = ['Name', 'Description', 'Physical-Slot', 'Oper-Status', 'Admin-Status', 'Serial']
    if smartswitch:
        header.append('Ready-Status')

    chassis_cfg_table = db.cfgdb.get_table('CHASSIS_MODULE')

    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)

    key_pattern = CHASSIS_MODULE_INFO_TABLE + '|*'
    if chassis_module_name:
        key_pattern = CHASSIS_MODULE_INFO_TABLE + '|' + chassis_module_name

    keys = state_db.keys(state_db.STATE_DB, key_pattern)
    if not keys:
        print('Key {} not found in {} table'.format(key_pattern, CHASSIS_MODULE_INFO_TABLE))
        return

    # On BMC, oper_status is read directly from the platform API.
    # ModuleHelper.__init__ does not raise on chassis load failure; it logs and keeps
    # platform_chassis=None. Treat that as unavailable so we don't emit per-module
    # errors in the loop — just fall back to STATE_DB silently.
    module_helper = None
    if is_bmc():
        try:
            helper = ModuleHelper()
            if helper.platform_chassis:
                module_helper = helper
        except Exception:
            pass

    # For SmartSwitch, connect to CHASSIS_STATE_DB to read DPU_STATE
    dpu_state_data = {}
    chassis_state_db = None
    if smartswitch:
        try:
            chassis_state_db = SonicV2Connector(host=CHASSIS_SERVER, port=CHASSIS_SERVER_PORT)
            chassis_state_db.connect(chassis_state_db.CHASSIS_STATE_DB)
            if chassis_module_name:
                dpu_key_pattern = DPU_STATE_TABLE + '|' + chassis_module_name
            else:
                dpu_key_pattern = DPU_STATE_TABLE + '|*'
            dpu_keys = chassis_state_db.keys(chassis_state_db.CHASSIS_STATE_DB, dpu_key_pattern)
            if dpu_keys:
                for dpu_key in dpu_keys:
                    dpu_name = dpu_key.split('|')[1]
                    dpu_state_data[dpu_name] = chassis_state_db.get_all(
                        chassis_state_db.CHASSIS_STATE_DB, dpu_key)
        except Exception:
            chassis_state_db = None
            dpu_state_data = {}

    table = []
    for key in natsorted(keys):
        key_list = key.split('|')
        if len(key_list) != 2:  # error data in DB, log it and ignore
            print('Warn: Invalid Key {} in {} table'.format(key, CHASSIS_MODULE_INFO_TABLE))
            continue

        data_dict = state_db.get_all(state_db.STATE_DB, key)

        # Use default values if any field is missing
        desc = data_dict.get(CHASSIS_MODULE_INFO_DESC_FIELD, 'N/A')
        slot = data_dict.get(CHASSIS_MODULE_INFO_SLOT_FIELD, 'N/A')
        oper_status = data_dict.get(CHASSIS_MODULE_INFO_OPERSTATUS_FIELD, ModuleBase.MODULE_STATUS_EMPTY)
        serial = data_dict.get(CHASSIS_MODULE_INFO_SERIAL_FIELD, 'N/A')

        # On BMC, prefer oper_status from platform API; fall back to STATE_DB if unavailable
        if module_helper is not None:
            platform_oper_status = module_helper.get_module_oper_status(key_list[1])
            if platform_oper_status != NOT_AVAILABLE:
                oper_status = platform_oper_status

        # Determine admin_status
        if smartswitch:
            admin_status = 'down'
        elif is_bmc():
            # On BMC, modules default to 'down' (kept powered off on boot)
            admin_status = 'down'
        else:
            admin_status = 'up'
        config_data = chassis_cfg_table.get(key_list[1])
        if config_data is not None:
            admin_status = config_data.get(CHASSIS_MODULE_INFO_ADMINSTATUS_FIELD, admin_status)

        row = [key_list[1], desc, slot, oper_status, admin_status, serial]

        if smartswitch:
            dpu_info = dpu_state_data.get(key_list[1], {})
            ready_status = dpu_info.get(DPU_STATE_READY_STATUS_FIELD, 'N/A')
            row.append(ready_status)

        table.append(tuple(row))

    if chassis_state_db:
        chassis_state_db.close(chassis_state_db.CHASSIS_STATE_DB)

    if table:
        click.echo(tabulate(table, header, tablefmt='simple', stralign='right'))
    else:
        click.echo('No data available in CHASSIS_MODULE_TABLE\n')


@modules.command()
@click.argument('chassis_module_name', metavar='<module_name>', required=False)
def recovery(chassis_module_name):
    """Show chassis-modules recovery information"""

    if not is_smartswitch():
        click.echo('This command is only supported on SmartSwitch platforms')
        return

    header = ['Name', 'Ready-Status', 'Recovery-Status', 'Reset-Count',
              'Last-Down-Time', 'Last-Ready-Time']

    try:
        chassis_state_db = SonicV2Connector(host=CHASSIS_SERVER, port=CHASSIS_SERVER_PORT)
        chassis_state_db.connect(chassis_state_db.CHASSIS_STATE_DB)
    except Exception:
        click.echo('Unable to connect to CHASSIS_STATE_DB')
        return

    key_pattern = DPU_STATE_TABLE + '|*'
    if chassis_module_name:
        key_pattern = DPU_STATE_TABLE + '|' + chassis_module_name

    keys = chassis_state_db.keys(chassis_state_db.CHASSIS_STATE_DB, key_pattern)
    if not keys:
        chassis_state_db.close(chassis_state_db.CHASSIS_STATE_DB)
        if chassis_module_name:
            click.echo('DPU recovery data not found for module {}'.format(chassis_module_name))
        else:
            click.echo('No DPU recovery data available')
        return

    table = []
    for key in natsorted(keys):
        key_list = key.split('|')
        if len(key_list) != 2:
            continue

        data_dict = chassis_state_db.get_all(chassis_state_db.CHASSIS_STATE_DB, key)

        ready_status = data_dict.get(DPU_STATE_READY_STATUS_FIELD, 'N/A')
        recovery_status = data_dict.get(DPU_STATE_RECOVERY_STATUS_FIELD, 'N/A')
        reset_count = data_dict.get(DPU_STATE_RESET_COUNT_FIELD, 'N/A')
        last_down_time = data_dict.get(DPU_STATE_LAST_DOWN_TIME_FIELD, 'N/A')
        last_ready_time = data_dict.get(DPU_STATE_LAST_READY_TIME_FIELD, 'N/A')

        table.append((key_list[1], ready_status, recovery_status, reset_count,
                      last_down_time, last_ready_time))

    chassis_state_db.close(chassis_state_db.CHASSIS_STATE_DB)

    if table:
        click.echo(tabulate(table, header, tablefmt='simple', stralign='right'))
    else:
        click.echo('No DPU recovery data available')

@modules.command()
@click.argument('chassis_module_name', metavar='<module_name>', required=False)
def midplane_status(chassis_module_name):
    """Show chassis-modules midplane-status"""

    header = ['Name', 'IP-Address', 'Reachability']

    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)

    key_pattern = '*'
    if chassis_module_name:
        key_pattern = '|' + chassis_module_name

    keys = state_db.keys(state_db.STATE_DB, CHASSIS_MIDPLANE_INFO_TABLE + key_pattern)
    if not keys:
        print('Key {} not found in {} table'.format(key_pattern, CHASSIS_MIDPLANE_INFO_TABLE))
        return

    table = []
    for key in natsorted(keys):
        key_list = key.split('|')
        if len(key_list) != 2:
            print('Warn: Invalid Key {} in {} table'.format(key, CHASSIS_MIDPLANE_INFO_TABLE))
            continue

        data_dict = state_db.get_all(state_db.STATE_DB, key)

        # Defensive access with fallback defaults
        ip = data_dict.get(CHASSIS_MIDPLANE_INFO_IP_FIELD, 'N/A')
        access = data_dict.get(CHASSIS_MIDPLANE_INFO_ACCESS_FIELD, 'Unknown')

        table.append((key_list[1], ip, access))

    if table:
        click.echo(tabulate(table, header, tablefmt='simple', stralign='right'))
    else:
        click.echo('No data available in CHASSIS_MIDPLANE_TABLE\n')

@chassis.command()
@click.argument('systemportname', required=False)
@click.option('--namespace', '-n', 'namespace', required=True if multi_asic.is_multi_asic() else False,
                default=None, type=str, show_default=False, help='Namespace name or all')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def system_ports(systemportname, namespace, verbose):
    """Show VOQ system ports information"""

    cmd = ['voqutil', '-c', 'system_ports']

    if systemportname is not None:
        cmd += ['-i', str(systemportname)]

    if namespace is not None:
        cmd += ['-n', str(namespace)]

    clicommon.run_command(cmd, display_cmd=verbose)

@chassis.command()
@click.argument('ipaddress', required=False)
@click.option('--asicname', '-n', 'asicname', default=None, type=str, show_default=False, help='Asic name')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def system_neighbors(asicname, ipaddress, verbose):
    """Show VOQ system neighbors information"""

    cmd = ['voqutil', '-c', 'system_neighbors']

    if ipaddress is not None:
        cmd += ['-a', str(ipaddress)]

    if asicname is not None:
        cmd += ['-n', str(asicname)]

    clicommon.run_command(cmd, display_cmd=verbose)

@chassis.command()
@click.argument('systemlagname', required=False)
@click.option('--asicname', '-n', 'asicname', default=None, type=str, show_default=False, help='Asic name')
@click.option('--linecardname', '-l', 'linecardname', default=None, type=str, show_default=False, help='Linecard or Host name')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def system_lags(systemlagname, asicname, linecardname, verbose):
    """Show VOQ system lags information"""

    cmd = ['voqutil', '-c', 'system_lags']

    if systemlagname is not None:
        cmd += ['-s', str(systemlagname)]

    if asicname is not None:
        cmd += ['-n', str(asicname)]

    if linecardname is not None:
        cmd += ['-l', str(linecardname)]

    clicommon.run_command(cmd, display_cmd=verbose)
