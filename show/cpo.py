"""Click entry points for the CPO display framework."""

import click


def run_cposhow(args, namespace=None, json_output=False, verbose=False):
    """Reserve forwarding to cposhow without implementing execution yet.

    Future implementation converts interface aliases, appends common options
    and relays stdout/stderr/exit status unchanged. This wrapper must not read
    STATE_DB or duplicate the script's query/formatting logic.
    """
    raise click.ClickException("CPO command forwarding is not implemented yet (framework draft).")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cpo():
    """Show CPO information (framework draft; queries are not implemented)."""
    pass


@cpo.command('map')
@click.argument('port', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def map(port, namespace, json_output, verbose):
    """Show port-to-OE/ELS/bank/laser associations."""
    args = ["map"]
    if port is not None:
        args.append(port)
    run_cposhow(args, namespace, json_output, verbose)


@cpo.group()
def oe():
    """Show OE resource views."""
    pass


@oe.command('list')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_list(namespace, json_output, verbose):
    """List resources and their associated ports."""
    args = ["oe", "list"]
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('info')
@click.argument('oe_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_info(oe_index, namespace, json_output, verbose):
    """Show static identification fields."""
    args = ["oe", "info"]
    if oe_index is not None:
        args.append(oe_index)
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('status')
@click.argument('oe_index', required=False)
@click.option('-b', '--bank', type=click.IntRange(min=0), help='Select one bank.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_status(oe_index, bank, namespace, json_output, verbose):
    """Show published module and channel status."""
    args = ["oe", "status"]
    if oe_index is not None:
        args.append(oe_index)
    if bank is not None:
        args.extend(["--bank", str(bank)])
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('lpmode')
@click.argument('oe_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_lpmode(oe_index, namespace, json_output, verbose):
    """Show low-power mode derived from published status."""
    args = ["oe", "lpmode"]
    if oe_index is not None:
        args.append(oe_index)
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('flag')
@click.argument('oe_index', required=False)
@click.option('-b', '--bank', type=click.IntRange(min=0), help='Select one bank.')
@click.option('--history', is_flag=True, help='Include count/set/clear metadata.')
@click.option('--show-suppressed', is_flag=True, help='List unmapped fields for diagnosis.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_flag(oe_index, bank, history, show_suppressed, namespace, json_output, verbose):
    """Show published flags and optional change history."""
    args = ["oe", "flag"]
    if oe_index is not None:
        args.append(oe_index)
    if bank is not None:
        args.extend(["--bank", str(bank)])
    if history:
        args.append("--history")
    if show_suppressed:
        args.append("--show-suppressed")
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('dom')
@click.argument('oe_index', required=False)
@click.option('-b', '--bank', type=click.IntRange(min=0), help='Select one bank.')
@click.option('--show-suppressed', is_flag=True, help='List unmapped fields for diagnosis.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_dom(oe_index, bank, show_suppressed, namespace, json_output, verbose):
    """Show published monitoring values and thresholds."""
    args = ["oe", "dom"]
    if oe_index is not None:
        args.append(oe_index)
    if bank is not None:
        args.extend(["--bank", str(bank)])
    if show_suppressed:
        args.append("--show-suppressed")
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('temperature')
@click.argument('oe_index', required=False)
@click.option('--show-suppressed', is_flag=True, help='List unmapped fields for diagnosis.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_temperature(oe_index, show_suppressed, namespace, json_output, verbose):
    """Show module temperature, with the sensor-table fallback."""
    args = ["oe", "temperature"]
    if oe_index is not None:
        args.append(oe_index)
    if show_suppressed:
        args.append("--show-suppressed")
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('voltage')
@click.argument('oe_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_voltage(oe_index, namespace, json_output, verbose):
    """Show module voltage and thresholds."""
    args = ["oe", "voltage"]
    if oe_index is not None:
        args.append(oe_index)
    run_cposhow(args, namespace, json_output, verbose)


@oe.command('firmware-info')
@click.argument('oe_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def oe_firmware_info(oe_index, namespace, json_output, verbose):
    """Show published firmware versions; do not access hardware."""
    args = ["oe", "firmware-info"]
    if oe_index is not None:
        args.append(oe_index)
    run_cposhow(args, namespace, json_output, verbose)


@cpo.group()
def els():
    """Show ELS resource views."""
    pass


@els.command('list')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_list(namespace, json_output, verbose):
    """List resources and their associated ports."""
    args = ["els", "list"]
    run_cposhow(args, namespace, json_output, verbose)


@els.command('presence')
@click.argument('els_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_presence(els_index, namespace, json_output, verbose):
    """Show presence from published information rows."""
    args = ["els", "presence"]
    if els_index is not None:
        args.append(els_index)
    run_cposhow(args, namespace, json_output, verbose)


@els.command('info')
@click.argument('els_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_info(els_index, namespace, json_output, verbose):
    """Show static identification fields."""
    args = ["els", "info"]
    if els_index is not None:
        args.append(els_index)
    run_cposhow(args, namespace, json_output, verbose)


@els.command('status')
@click.argument('els_index', required=False)
@click.option('-b', '--bank', type=click.IntRange(min=0), help='Select one bank.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_status(els_index, bank, namespace, json_output, verbose):
    """Show published module and channel status."""
    args = ["els", "status"]
    if els_index is not None:
        args.append(els_index)
    if bank is not None:
        args.extend(["--bank", str(bank)])
    run_cposhow(args, namespace, json_output, verbose)


@els.command('lpmode')
@click.argument('els_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_lpmode(els_index, namespace, json_output, verbose):
    """Show low-power mode derived from published status."""
    args = ["els", "lpmode"]
    if els_index is not None:
        args.append(els_index)
    run_cposhow(args, namespace, json_output, verbose)


@els.command('flag')
@click.argument('els_index', required=False)
@click.option('-b', '--bank', type=click.IntRange(min=0), help='Select one bank.')
@click.option('--history', is_flag=True, help='Include count/set/clear metadata.')
@click.option('--show-suppressed', is_flag=True, help='List unmapped fields for diagnosis.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_flag(els_index, bank, history, show_suppressed, namespace, json_output, verbose):
    """Show published flags and optional change history."""
    args = ["els", "flag"]
    if els_index is not None:
        args.append(els_index)
    if bank is not None:
        args.extend(["--bank", str(bank)])
    if history:
        args.append("--history")
    if show_suppressed:
        args.append("--show-suppressed")
    run_cposhow(args, namespace, json_output, verbose)


@els.command('dom')
@click.argument('els_index', required=False)
@click.option('-b', '--bank', type=click.IntRange(min=0), help='Select one bank.')
@click.option('--show-suppressed', is_flag=True, help='List unmapped fields for diagnosis.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_dom(els_index, bank, show_suppressed, namespace, json_output, verbose):
    """Show published monitoring values and thresholds."""
    args = ["els", "dom"]
    if els_index is not None:
        args.append(els_index)
    if bank is not None:
        args.extend(["--bank", str(bank)])
    if show_suppressed:
        args.append("--show-suppressed")
    run_cposhow(args, namespace, json_output, verbose)


@els.command('temperature')
@click.argument('els_index', required=False)
@click.option('--show-suppressed', is_flag=True, help='List unmapped fields for diagnosis.')
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_temperature(els_index, show_suppressed, namespace, json_output, verbose):
    """Show module temperature, with the sensor-table fallback."""
    args = ["els", "temperature"]
    if els_index is not None:
        args.append(els_index)
    if show_suppressed:
        args.append("--show-suppressed")
    run_cposhow(args, namespace, json_output, verbose)


@els.command('voltage')
@click.argument('els_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_voltage(els_index, namespace, json_output, verbose):
    """Show module voltage and thresholds."""
    args = ["els", "voltage"]
    if els_index is not None:
        args.append(els_index)
    run_cposhow(args, namespace, json_output, verbose)


@els.command('firmware-info')
@click.argument('els_index', required=False)
@click.option('-n', '--namespace', default=None, help='ASIC namespace name or all.')
@click.option('-j', '--json', 'json_output', is_flag=True, help='Preserve raw DB keys and values.')
@click.option('--verbose', is_flag=True, help='Show the forwarded command on stderr.')
def els_firmware_info(els_index, namespace, json_output, verbose):
    """Show published firmware versions; do not access hardware."""
    args = ["els", "firmware-info"]
    if els_index is not None:
        args.append(els_index)
    run_cposhow(args, namespace, json_output, verbose)
