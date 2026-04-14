"""
PRBS (Pseudo-Random Bit Sequence) show commands
"""

import json
import click
from datetime import datetime
from swsscommon.swsscommon import SonicV2Connector
from tabulate import tabulate
from natsort import natsorted
import utilities_common.cli as clicommon
from utilities_common.prbs_util import (
    format_ber,
    format_ber_scientific,
    average_ber,
    format_elapsed_time,
    calculate_duration,
    get_lock_status_from_rx_status,
    PRBS_RX_STATUS
)


def register(cli):
    """Register PRBS show commands"""
    cli.add_command(prbs_group)


@click.group(name='prbs')
@click.pass_context
def prbs_group(ctx):
    """Show PRBS information"""
    pass


def get_prbs_display_status(prbs_status, oper_status):
    """Derive display status from prbs_status and oper_status.

    prbs_status values in STATE_DB: running, errored, stopped, failed
    oper_status: TESTING when PRBS is active on the port

    Returns: Running, Interrupted, Errored, Failed, Completed, or None
    """
    if prbs_status == 'errored':
        return 'Errored'
    elif prbs_status == 'failed':
        return 'Failed'
    elif prbs_status == 'running':
        if oper_status and oper_status.lower() == 'testing':
            return 'Running'
        else:
            return 'Interrupted'
    elif prbs_status == 'stopped':
        return 'Completed'
    return None


def _compute_duration(display_status, start_time, stop_time):
    if display_status == 'Running':
        try:
            return format_elapsed_time(float(start_time))
        except Exception:
            return '--'
    elif display_status == 'Completed':
        return calculate_duration(start_time, stop_time)
    return '--'


def _parse_aggregate_results(results_data):
    """Extract (rx_status, error_count) from PORT_PRBS_RESULTS hash."""
    if not results_data:
        return None, None
    rx_status = results_data.get('rx_status')
    error_count_str = results_data.get('error_count')
    if error_count_str is not None:
        try:
            error_count = int(error_count_str)
        except (ValueError, TypeError):
            error_count = error_count_str
    else:
        error_count = None
    return rx_status, error_count


def _get_average_ber_from_lanes(db, interface):
    """Compute averaged BER across all lanes from PORT_PRBS_LANE_RESULT."""
    lane_keys = db.keys(db.STATE_DB, f'PORT_PRBS_LANE_RESULT|{interface}|*')
    if not lane_keys:
        return None, None

    ber_values = []
    for key in natsorted(lane_keys):
        lane_result = db.get_all(db.STATE_DB, key)
        try:
            mantissa = int(lane_result.get('ber_mantissa'))
        except (ValueError, TypeError):
            mantissa = None
        try:
            exponent = int(lane_result.get('ber_exponent'))
        except (ValueError, TypeError):
            exponent = None
        ber_values.append((mantissa, exponent))

    return average_ber(ber_values)


def show_all_prbs_status(db, output_json):
    """Show summary table of all PRBS tests across all ports."""
    test_keys = db.keys(db.STATE_DB, 'PORT_PRBS_TEST|*')

    if not test_keys:
        if output_json:
            click.echo(json.dumps({}))
        else:
            click.echo("No PRBS tests found")
        return

    table_data = []
    json_data = {}

    for key in natsorted(test_keys):
        interface = key.split('|')[1]
        test_data = db.get_all(db.STATE_DB, key)

        prbs_status = test_data.get('status', '')

        port_data = db.get_all(db.APPL_DB, f'PORT_TABLE:{interface}')
        oper_status = port_data.get('oper_status', '') if port_data else ''

        display_status = get_prbs_display_status(prbs_status, oper_status)
        if display_status is None:
            continue

        mode = test_data.get('mode', 'N/A')
        pattern = test_data.get('pattern', 'N/A')
        start_time = test_data.get('start_time', 'N/A')
        stop_time = test_data.get('stop_time', 'N/A')

        if start_time != 'N/A':
            try:
                start_time_str = datetime.fromtimestamp(float(start_time)).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                start_time_str = start_time
        else:
            start_time_str = '--'

        duration = _compute_duration(display_status, start_time, stop_time)

        rx_status_display = '--'
        error_count_display = '--'
        ber_display = '--'
        rx_status_val = None
        error_count_val = None
        ber_sci = None

        if display_status == 'Completed':
            results_data = db.get_all(db.STATE_DB, f'PORT_PRBS_RESULTS|{interface}')
            rx_status_val, error_count_val = _parse_aggregate_results(results_data)
            if rx_status_val is not None:
                rx_status_display = rx_status_val

            if rx_status_val in ('OK', 'LOCK_WITH_ERRORS'):
                if error_count_val is not None:
                    error_count_display = error_count_val
                avg_mantissa, avg_exponent = _get_average_ber_from_lanes(db, interface)
                if avg_mantissa is not None and avg_exponent is not None:
                    ber_display = format_ber(avg_mantissa, avg_exponent)
                    ber_sci = format_ber_scientific(avg_mantissa, avg_exponent)

        if output_json:
            json_data[interface] = {
                'mode': mode,
                'pattern': pattern,
                'status': display_status,
                'rx_status': rx_status_val,
                'error_count': error_count_val,
                'ber': ber_sci,
                'start_time': start_time_str,
                'duration': duration
            }
        else:
            table_data.append([interface, mode, pattern, display_status,
                               rx_status_display, error_count_display,
                               ber_display, start_time_str, duration])

    if output_json:
        click.echo(json.dumps(json_data, indent=2))
    else:
        if not table_data:
            click.echo("No active PRBS tests")
        else:
            headers = ['Interface', 'Mode', 'Pattern', 'Status', 'RX Status',
                        'Error Count', 'BER', 'Start Time', 'Duration']
            click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))


@prbs_group.command()
@click.option('-i', '--interface', 'interface_name', metavar='<interface_name>', default=None, help='Display detailed PRBS test results for interface <interface_name>')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def status(ctx, interface_name, output_json):
    """Show PRBS test status

    Without arguments, shows a summary of all active PRBS tests.
    With an interface name, shows detailed per-lane results.
    """
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.STATE_DB)
    db.connect(db.APPL_DB)

    if interface_name is None:
        show_all_prbs_status(db, output_json)
        return

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = clicommon.iface_alias_converter.alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("Invalid interface name")

    test_data = db.get_all(db.STATE_DB, f'PORT_PRBS_TEST|{interface_name}')

    if not test_data:
        if output_json:
            click.echo(json.dumps({'error': f'No PRBS test data available for {interface_name}'}))
        else:
            click.echo(f"No PRBS test data available for {interface_name}")
        return

    prbs_status = test_data.get('status', '')
    port_data = db.get_all(db.APPL_DB, f'PORT_TABLE:{interface_name}')
    oper_status = port_data.get('oper_status', '') if port_data else ''
    display_status = get_prbs_display_status(prbs_status, oper_status) or 'Unknown'

    if prbs_status == 'failed':
        message = f'Failed to start prbs test on {interface_name}'
        if output_json:
            click.echo(json.dumps({'interface': interface_name, 'status': 'Failed', 'message': message}, indent=2))
        else:
            click.echo(message)
        return

    mode = test_data.get('mode', 'N/A')
    pattern = test_data.get('pattern', 'N/A')
    start_time = test_data.get('start_time', 'N/A')
    stop_time = test_data.get('stop_time', 'N/A')
    duration = _compute_duration(display_status, start_time, stop_time)

    header = {
        'interface': interface_name,
        'mode': mode,
        'pattern': pattern,
        'status': display_status,
        'duration': duration,
    }
    header_line = f"Interface: {interface_name} | Mode: {mode} | Pattern: {pattern} | Status: {display_status} | Duration: {duration}"

    if mode == 'tx':
        message = 'TX mode does not capture PRBS results'
        if output_json:
            click.echo(json.dumps({**header, 'message': message}, indent=2))
        else:
            click.echo(f"Interface:       {interface_name}")
            click.echo(f"Mode:            {mode}")
            click.echo(f"Pattern:         {pattern}")
            click.echo(f"Status:          {display_status}")
            click.echo(f"Duration:        {duration}")
            click.echo(f"Note:            {message}")
        return

    lane_keys = db.keys(db.STATE_DB, f'PORT_PRBS_LANE_RESULT|{interface_name}|*')

    if not lane_keys:
        message = 'No PRBS result data available'
        if output_json:
            click.echo(json.dumps({**header, 'message': message}, indent=2))
        else:
            click.echo(f"{header_line}\n")
            click.echo(f"Note: {message}")
        return

    sorted_keys = natsorted(lane_keys)
    lane_data = []
    lane_json = []

    for key in sorted_keys:
        lane_num = int(key.split('|')[2])
        lane_result = db.get_all(db.STATE_DB, key)

        rx_status = lane_result.get('rx_status', 'N/A')
        lock_status = get_lock_status_from_rx_status(rx_status)
        error_count_str = lane_result.get('error_count')
        try:
            error_count = int(error_count_str)
            has_error_count = True
        except (ValueError, TypeError):
            error_count = 0
            has_error_count = False

        ber_mantissa_str = lane_result.get('ber_mantissa')
        ber_exponent_str = lane_result.get('ber_exponent')
        try:
            ber_mantissa = int(ber_mantissa_str)
        except (ValueError, TypeError):
            ber_mantissa = None
        try:
            ber_exponent = int(ber_exponent_str)
        except (ValueError, TypeError):
            ber_exponent = None

        if ber_mantissa is not None and ber_exponent is not None:
            ber_display = format_ber(ber_mantissa, ber_exponent)
            ber_sci = format_ber_scientific(ber_mantissa, ber_exponent)
        else:
            ber_display = 'N/A'
            ber_sci = None

        if output_json:
            lane_json.append({
                'lane': lane_num,
                'lock_status': lock_status,
                'rx_status': rx_status,
                'error_count': error_count if has_error_count else None,
                'ber': ber_sci,
                'ber_mantissa': ber_mantissa,
                'ber_exponent': ber_exponent,
            })
        else:
            lane_data.append([
                lane_num,
                lock_status,
                rx_status,
                error_count if has_error_count else 'N/A',
                ber_display,
            ])

    if output_json:
        click.echo(json.dumps({**header, 'lanes': lane_json}, indent=2))
    else:
        click.echo(f"{header_line}\n")

        headers = ['Lane', 'Lock', 'RX Status', 'Errors', 'BER']
        click.echo(tabulate(lane_data, headers=headers, tablefmt='simple'))
