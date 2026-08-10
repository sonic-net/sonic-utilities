import json
import os
import shutil
import subprocess
import sys

import click
from natsort import natsorted
from tabulate import tabulate
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.chassis import is_smartswitch, is_bmc
from utilities_common.module import ModuleHelper, NOT_AVAILABLE
from sonic_platform_base.module_base import ModuleBase

import utilities_common.cli as clicommon
from sonic_py_common import multi_asic

STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_NOT_APPLICABLE = "not_applicable"

_CONSISTENCY_CHECKER_SCRIPT = "chassis_db_consistency_checker.py"
_CONSISTENCY_CHECKER_TIMEOUT_SEC = 120


def _consistency_checker_script_path():
    script = shutil.which(_CONSISTENCY_CHECKER_SCRIPT)
    if script is not None:
        return script
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", _CONSISTENCY_CHECKER_SCRIPT)
    )


def _run_system_lag_consistency_checker(lag_id_only=False):
    """Run chassis_db_consistency_checker --json and return parsed result."""
    script = _consistency_checker_script_path()
    cmd = [sys.executable, script, "--json"]
    if lag_id_only:
        cmd.append("--lag-id-only")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_CONSISTENCY_CHECKER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        raise click.ClickException(
            f"{_CONSISTENCY_CHECKER_SCRIPT} timed out after "
            f"{_CONSISTENCY_CHECKER_TIMEOUT_SEC}s"
        )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "no output"
        raise click.ClickException(
            f"{_CONSISTENCY_CHECKER_SCRIPT} failed (rc={proc.returncode}): {detail}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"{_CONSISTENCY_CHECKER_SCRIPT} returned invalid JSON: {exc}"
        )


def _echo_indented_lines(lines, indent="    "):
    for line in lines:
        click.echo(f"{indent}{line}")


def _echo_indented_block(title, lines):
    if not lines:
        return
    click.echo(f"  {title}:")
    _echo_indented_lines(lines)


def _format_lag_member_key(member_key):
    if ":" in member_key:
        lag_alias, port_alias = member_key.rsplit(":", 1)
        return f"{lag_alias} : {port_alias}"
    return member_key


def _format_unresolved_lag_member(item):
    aggregate_id = item.get("system_port_aggregate_id")
    aggregate_label = aggregate_id if aggregate_id is not None else "unknown"
    return (
        f"lag_oid={item['lag_oid']}, "
        f"SAI_LAG_ATTR_SYSTEM_PORT_AGGREGATE_ID={aggregate_label}, "
        f"port_oid={item['port_oid']}"
    )


def _lag_member_issue_count(lag_members):
    return (
        len(lag_members["missing_in_asic_db"])
        + len(lag_members["extra_in_asic_db"])
        + len(lag_members["status_mismatch"])
        + len(lag_members["invalid_port_id"])
        + len(lag_members["unresolved"])
        + len(lag_members["incomplete_attrs"])
    )


def _print_system_lag_consistency_text(result, lag_id_only_mode):
    status = result["status"]
    status_label = "OK" if status == STATUS_OK else "FAILED"
    click.echo(f"System LAG consistency: {status_label}")
    click.echo("")
    if lag_id_only_mode:
        click.echo("Mode: LAG ID only (lag members not checked)")
        click.echo("")
    click.echo("Chassis summary:")
    click.echo(f"  SYSTEM_LAG_ID_TABLE:      {result['chassis_lag_id_count']} lag IDs")
    if not lag_id_only_mode:
        click.echo(
            f"  SYSTEM_LAG_MEMBER_TABLE:  {result['chassis_lag_member_count']} lag members"
        )
    click.echo("")

    asic_names = sorted(result["asics"].keys())
    for index, asic_name in enumerate(asic_names):
        asic_info = result["asics"][asic_name]
        lag_ids = asic_info["lag_ids"]
        lag_members = asic_info.get("lag_members", {})
        lag_id_mismatch_count = (
            len(lag_ids["missing_in_asic_db"]) + len(lag_ids["extra_in_asic_db"])
        )
        lag_id_mismatch_label = "mismatch" if lag_id_mismatch_count == 1 else "mismatches"

        click.echo(f"ASIC namespace: {asic_name}")
        click.echo(
            f"  Lag IDs in ASIC_DB:      {lag_ids['lag_id_count']} "
            f"({lag_id_mismatch_count} {lag_id_mismatch_label})"
        )
        if not lag_id_only_mode:
            member_issue_count = _lag_member_issue_count(lag_members)
            issue_label = "issue" if member_issue_count == 1 else "issues"
            click.echo(
                f"  Lag members in ASIC_DB:  {lag_members['member_count']} "
                f"({member_issue_count} {issue_label})"
            )

        # LAG IDs configured in chassis_db but missing from this ASIC_DB's SAI LAG objects
        _echo_indented_block(
            "Lag IDs missing in ASIC_DB (in CHASSIS_DB - SYSTEM_LAG_ID_TABLE)",
            lag_ids["missing_in_asic_db"],
        )
        # LAG IDs present on ASIC_DB but not listed in chassis_db SYSTEM_LAG_ID_TABLE
        _echo_indented_block(
            "Lag IDs extra in ASIC_DB (not in CHASSIS_DB - SYSTEM_LAG_ID_TABLE)",
            lag_ids["extra_in_asic_db"],
        )

        if not lag_id_only_mode:
            # Chassis SYSTEM_LAG_MEMBER_TABLE entries with no matching ASIC_DB LAG member
            _echo_indented_block(
                "Lag members missing in ASIC_DB (in CHASSIS_DB - SYSTEM_LAG_MEMBER_TABLE)",
                [_format_lag_member_key(m) for m in lag_members["missing_in_asic_db"]],
            )
            # ASIC_DB LAG members not defined in chassis_db SYSTEM_LAG_MEMBER_TABLE
            _echo_indented_block(
                "Lag members extra in ASIC_DB (not in CHASSIS_DB - SYSTEM_LAG_MEMBER_TABLE)",
                [_format_lag_member_key(m) for m in lag_members["extra_in_asic_db"]],
            )
            # Member exists on both sides but chassis status vs ingress/egress_disable disagree
            _echo_indented_block(
                "Lag member status mismatch",
                [
                    f"{item['member']} (chassis={item['chassis_status']}, "
                    f"ingress_disable={item['ingress_disable']}, "
                    f"egress_disable={item['egress_disable']})"
                    for item in lag_members["status_mismatch"]
                ],
            )
            # Member key resolved but PORT_ID OID is not a valid PORT/SYSTEM_PORT object
            _echo_indented_block(
                "Lag member invalid PORT_ID",
                [
                    f"{item['member']} (port_id={item['port_id']})"
                    for item in lag_members["invalid_port_id"]
                ],
            )
            # LAG member has LAG_ID and PORT_ID but OID-to-alias mapping failed
            _echo_indented_block(
                "Lag member unresolved OID mapping",
                [_format_unresolved_lag_member(item) for item in lag_members["unresolved"]],
            )
            # SAI LAG member object missing SAI_LAG_MEMBER_ATTR_LAG_ID or PORT_ID
            _echo_indented_block(
                "Lag member incomplete attributes",
                [
                    f"lag_member_oid={item['lag_member_oid']}, lag_oid={item['lag_oid']}, "
                    f"port_oid={item['port_oid']}"
                    for item in lag_members["incomplete_attrs"]
                ],
            )

        if index < len(asic_names) - 1:
            click.echo("")

    if status == STATUS_OK:
        click.echo("")
        click.echo("All ASIC namespaces are in sync with chassis_db.")
    else:
        click.echo("")
        click.echo("One or more ASIC namespaces are out of sync with chassis_db.")


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
    bmc = is_bmc()
    header = ['Name', 'Description', 'Physical-Slot', 'Oper-Status', 'Admin-Status', 'Serial']
    if smartswitch:
        header.append('Ready-Status')
    if bmc:
        # Physical-Slot is not meaningful on BMC; drop it and add the
        # BMC-only timing fields configured via 'config chassis modules
        # power-on-delay' / 'shutdown-timeout' for SWITCH-HOST modules.
        header.remove('Physical-Slot')
        header.extend(['Power-On-Delay (sec)', 'Shutdown-Timeout (sec)'])

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
        elif is_bmc() and key_list[1].startswith("SWITCH-HOST"):
            # On BMC, SWITCH-HOST default is 'down' (kept powered off on boot)
            admin_status = 'down'
        else:
            admin_status = 'up'
        config_data = chassis_cfg_table.get(key_list[1])
        if config_data is not None:
            admin_status = config_data.get(CHASSIS_MODULE_INFO_ADMINSTATUS_FIELD, admin_status)

        row = [key_list[1], desc, slot, oper_status, admin_status, serial]
        if bmc:
            # Physical-Slot column omitted from header on BMC; drop matching value
            row.pop(2)

        if smartswitch:
            dpu_info = dpu_state_data.get(key_list[1], {})
            ready_status = dpu_info.get(DPU_STATE_READY_STATUS_FIELD, 'N/A')
            row.append(ready_status)

        if bmc:
            # Only meaningful for SWITCH-HOST modules; other module types show N/A.
            if key_list[1].startswith("SWITCH-HOST"):
                cfg = config_data or {}
                power_on_delay = cfg.get('power_on_delay', '0')
                shutdown_timeout = cfg.get('graceful_shutdown_timeout', '120')
            else:
                power_on_delay = 'N/A'
                shutdown_timeout = 'N/A'
            row.extend([power_on_delay, shutdown_timeout])

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


@chassis.command(name="system-lag-consistency")
@click.option(
    "--lag-id-only",
    is_flag=True,
    help="Check SYSTEM_LAG_ID_TABLE only; skip lag member checks",
)
@click.option("-j", "--json", "json_output", is_flag=True, help="Output in JSON format")
def system_lag_consistency(json_output, lag_id_only):
    """Verify system LAG consistency between CHASSIS_APP_DB and ASIC_DB.

    Default: SYSTEM_LAG_ID_TABLE and SYSTEM_LAG_MEMBER_TABLE. With --lag-id-only,
    SYSTEM_LAG_ID_TABLE only (VOQ chassis linecards).
    """

    result = _run_system_lag_consistency_checker(lag_id_only=lag_id_only)

    if json_output:
        click.echo(clicommon.json_dump(result))
        return

    lag_id_only_mode = result.get("lag_id_only", lag_id_only)
    status = result["status"]
    if status == STATUS_NOT_APPLICABLE:
        click.echo("System LAG consistency: not applicable")
        click.echo(f"Reason: {result['reason']}")
        return

    if status == STATUS_ERROR:
        click.echo("System LAG consistency: error")
        click.echo(f"Reason: {result['reason']}")
        return

    _print_system_lag_consistency_text(result, lag_id_only_mode)
