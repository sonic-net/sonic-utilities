#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with switches over serial via console device
#


try:
    import click
    import os
    import pwd
    import sys
    import utilities_common.cli as clicommon

    from tabulate import tabulate
    from .lib import *
    from .lib import initialize_console_runtime, console_connect, require_root, get_target_line, validate_mirror_timeout_duration, send_mirror_message
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))


@click.group()
@clicommon.pass_db
def consutil(db):
    """consutil - Command-line utility for interacting with switches via console device"""
    initialize_console_runtime(db)


# 'show' subcommand
@consutil.command()
@clicommon.pass_db
@click.option('--brief', '-b', is_flag=True)
def show(db, brief):
    """Show all ports and their info include available ttyUSB devices unless specified brief mode"""
    port_provider = ConsolePortProvider(db, brief, refresh=True)  # noqa: F405
    ports = list(port_provider.get_all())

    # sort ports for table rendering
    ports.sort(key=lambda p: int(p.line_num))

    # set table header style
    header = ["Line", "Baud", "Flow Control", "PID", "Start Time", "Device", "Oper State", "State Duration"]
    body = []
    for port in ports:
        # runtime information
        busy = "*" if port.busy else " "
        pid = port.session_pid if port.session_pid else "-"
        date = port.session_start_date if port.session_start_date else "-"
        baud = port.baud if port.baud else "-"
        flow_control = "Enabled" if port.flow_control else "Disabled"
        remote_device = port.remote_device if port.remote_device else "-"
        oper_state = port.oper_state if port.oper_state else "-"
        state_duration = port.state_duration if port.state_duration else "-"
        body.append([
            busy+port.line_num,
            baud if baud else "-",
            flow_control,
            pid if pid else "-",
            date if date else "-",
            remote_device,
            oper_state,
            state_duration,
        ])
    click.echo(tabulate(body, header, stralign='right'))


# 'show-escape' subcommand
@consutil.command('show-escape')
@clicommon.pass_db
@click.option('--brief', '-b', is_flag=True)
def show_escape(db, brief):
    """Show all default and line escape char info include available ttyUSB devices unless specified brief mode"""
    port_provider = ConsolePortProvider(db, brief, refresh=True)  # noqa: F405
    ports = list(port_provider.get_all())

    # sort ports for table rendering
    ports.sort(key=lambda p: int(p.line_num))

    # set table header style
    header = ["Line", "Default Escape Char", "Line Escape Char", "Final Escape Char"]
    body = []
    for port in ports:
        # runtime information
        busy = "*" if port.busy else " "
        body.append([
            busy+port.line_num,
            port.default_escape_char if port.default_escape_char else "-",
            port.line_escape_char if port.line_escape_char else "-",
            port.escape_char if port.escape_char else "-",
        ])
    click.echo(tabulate(body, header, stralign='right'))


# 'clear' subcommand
@consutil.command()
@clicommon.pass_db
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True,
              help="clear by name - if flag is set, interpret target as device name instead")
def clear(db, target, devicename):
    """Clear preexisting connection to line"""
    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERR_CMD)

    # identify the target line
    port_provider = ConsolePortProvider(db, configured_only=False)
    try:
        target_port = port_provider.get(target, use_device=devicename)
    except LineNotFoundError:
        click.echo("Target [{}] does not exist".format(target))
        sys.exit(ERR_DEV)

    if not target_port.clear_session():
        click.echo("No process is connected to line " + target_port.line_num)
    else:
        click.echo("Cleared line")

# 'connect' subcommand
@consutil.command()
@clicommon.pass_db
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True,
              help="connect by name - if flag is set, interpret target as device name instead")
def connect(db, target, devicename):
    """Connect to switch via console device - TARGET is line number or device name of switch"""
    console_connect(target, use_device=devicename, db=db)


# 'mirror' subcommand group
@consutil.group()
def mirror():
    """Manage console mirror recording sessions"""
    pass


# 'mirror start' subcommand
@mirror.command("start")
@clicommon.pass_db
@click.argument("target")
@click.option("--devicename", "-d", is_flag=True,
              help="interpret target as device name instead of line number")
@click.option("--direction", type=click.Choice(MIRROR_DIRECTIONS), default="both", show_default=True)
@click.option("--timeout", callback=validate_mirror_timeout_duration,
              help="auto-stop timeout, for example 30m, 2h, or 1d")
@click.option("--max-file-size", type=click.IntRange(min=1, max=16777215),
              help="maximum size of each recording part in MB")
def mirror_start(db, target, devicename, direction, timeout, max_file_size):
    """Start mirroring a console line"""
    def _current_user():
        try:
            return pwd.getpwuid(os.getuid()).pw_name
        except KeyError:
            return str(os.getuid())

    require_root()
    line = get_target_line(db, target, use_device=devicename)
    request = {
        "op": "start",
        "line": line,
        "direction": direction,
        "owner_pid": os.getpid(),
        "started_by": _current_user(),
    }
    if timeout:
        request["timeout"] = timeout
    if max_file_size:
        request["max_file_size"] = max_file_size

    response = send_mirror_message(line, request)
    click.echo("Started mirror on line [{}]".format(line))
    click.echo("Recording file: {}".format(response.get("file_path", "-")))
    click.echo("Auto-stop timeout: {}".format(response.get("timeout", "-")))
    click.echo("Remaining: {}".format(response.get("remaining", "-")))


# 'mirror stop' subcommand
@mirror.command("stop")
@clicommon.pass_db
@click.argument("target")
@click.option("--devicename", "-d", is_flag=True,
              help="interpret target as device name instead of line number")
@click.option("--archive", "-a", is_flag=True,
              help="package all parts into a ZIP and remove source logs")
def mirror_stop(db, target, devicename, archive):
    """Stop mirroring a console line"""
    require_root()
    line = get_target_line(db, target, use_device=devicename)
    request = {"op": "stop", "line": line, "archive": archive}
    if archive:
        def show_progress(first_msg):
            click.echo(
                "Stopped mirror on line [{}]; packaging recording".format(line))
            click.echo("Expected archive: {}".format(
                first_msg.get("archive_path", "-")))
            click.echo("Waiting for packaging to complete...")
            click.echo("")
        first, final = send_mirror_message(
            line, request, wait_for_final=True, on_first_reply=show_progress)
        click.echo("Recording archive: {}".format(
            final.get("archive_path", "-")))
    else:
        response = send_mirror_message(line, request)
        click.echo("Stopped mirror on line [{}]".format(line))
        click.echo("Recording files retained with prefix:")
        click.echo(response.get("recording_prefix", "-"))


# 'mirror timeout' subcommand
@mirror.command("timeout")
@clicommon.pass_db
@click.argument("target")
@click.argument("duration", callback=validate_mirror_timeout_duration)
@click.option("--devicename", "-d", is_flag=True, help="interpret target as device name instead of line number")
def mirror_timeout(db, target, duration, devicename):
    """Update a console mirror timeout"""
    require_root()
    line = get_target_line(db, target, use_device=devicename)
    request = {"op": "timeout", "line": line, "timeout": duration}
    response = send_mirror_message(line, request)
    click.echo("Updated mirror timeout on line [{}]".format(line))
    click.echo("Timeout: {}".format(response.get("timeout", "-")))
    click.echo("Remaining: {}".format(response.get("remaining", "-")))


# 'mirror show' subcommand
@mirror.command("show")
@clicommon.pass_db
@click.argument("target", required=False)
@click.option("--devicename", "-d", is_flag=True,
              help="interpret target as device name instead of line number")
def mirror_show(db, target, devicename):
    """Show console mirror status"""
    require_root()
    if target:
        lines = [get_target_line(db, target, use_device=devicename)]
    else:
        port_provider = ConsolePortProvider(db, configured_only=True)
        lines = sorted(
            [port.line_num for port in port_provider.get_all()], key=lambda line: int(line))

    rows = []
    for line in lines:
        try:
            status = send_mirror_message(
                line, {"op": "status", "line": line}, quiet=True)
        except (OSError, RuntimeError):
            # TODO: 
            status = {"line": line, "state": "idle"}
        rows.append([
            line,
            status.get("state", "idle"),
            status.get("start_time") or "-",
            status.get("direction") or "-",
            status.get("timeout") or "-",
            status.get("remaining") or "-",
            status.get("file_path") or "-",
        ])

    click.echo(tabulate(rows, ["Line", "State", "Start Time",
               "Direction", "Timeout", "Remaining", "File"]))


if __name__ == '__main__':
    consutil()
