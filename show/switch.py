import json

import click
import tabulate

import utilities_common.cli as clicommon
from utilities_common import constants
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic
from utilities_common.switch_hash import (
    STATE_SWITCH_CAPABILITY,
    SW_CAP_KEY,
)


#
# Switch CLI ----------------------------------------------------------------------------------------------------------
#


@click.group(
    name="switch",
    cls=clicommon.AliasedGroup
)
def switch():
    """ Show switch configuration """
    pass


def _switch_capability_db_key():
    return "{}|{}".format(STATE_SWITCH_CAPABILITY, SW_CAP_KEY)


def _format_switch_capabilities_body(entry):
    body = []
    for key in sorted(entry.keys()):
        body.append([key, entry[key]])
    return body


def _print_switch_capabilities_namespace(ctx, state_db, ns, namespace_option, json_fmt, idx):
    entry = state_db.get_all(state_db.STATE_DB, _switch_capability_db_key())

    if not entry:
        if not multi_asic.is_multi_asic() or namespace_option:
            ctx.fail("No data is present in STATE DB")
        return False

    if multi_asic.is_multi_asic() and not namespace_option:
        if idx > 0:
            click.echo()
        if ns != constants.DEFAULT_NAMESPACE:
            click.echo("Namespace {}:".format(ns))

    if json_fmt:
        click.echo(json.dumps(entry, indent=4))
    else:
        header = ["Capability", "Value"]
        body = _format_switch_capabilities_body(entry)
        click.echo(tabulate.tabulate(body, header, tablefmt="grid"))

    return True


@switch.command(
    name="capabilities"
)
@multi_asic_util.multi_asic_click_option_namespace
@click.option(
    "-j", "--json", "json_fmt",
    help="Display in JSON format",
    is_flag=True,
    default=False
)
@clicommon.pass_db
@click.pass_context
def capabilities(ctx, db, namespace, json_fmt):
    """ Show switch capabilities """

    ns_list = multi_asic.get_namespace_list(namespace)
    json_output = {}
    found = False

    for idx, ns in enumerate(ns_list):
        state_db = db.db_clients.get(ns, db.db)

        if json_fmt and len(ns_list) > 1:
            entry = state_db.get_all(state_db.STATE_DB, _switch_capability_db_key())
            if not entry:
                continue
            found = True
            json_output[ns if ns else "host"] = entry
            continue

        if _print_switch_capabilities_namespace(ctx, state_db, ns, namespace, json_fmt, idx):
            found = True

    if not found:
        ctx.fail("No data is present in STATE DB")
    if json_fmt and len(ns_list) > 1:
        click.echo(json.dumps(json_output, indent=4))


@switch.group(
    name="counters",
    cls=clicommon.AliasedGroup,
    invoke_without_command=True
)
@click.option(
    "-p", "--period",
    help="Display stats over a specified period (in seconds)",
    type=click.INT,
    default=0,
    show_default=True
)
@multi_asic_util.multi_asic_click_options
@click.option(
    "-j", "--json", "json_fmt",
    help="Display in JSON format",
    is_flag=True,
    default=False
)
@click.option(
    "-v", "--verbose",
    help="Enable verbose output",
    is_flag=True,
    default=False
)
@click.pass_context
def counters(ctx, period, display, namespace, json_fmt, verbose):
    """ Show switch counters """

    if ctx.invoked_subcommand is not None:
        return

    cmd = ["switchstat"]

    if period is not None:
        cmd += ["-p", str(period)]
    if display is not None:
        cmd += ['-d', str(display)]
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if json_fmt:
        cmd += ['-j']

    clicommon.run_command(cmd, display_cmd=verbose)


@counters.command(
    name="all"
)
@click.option(
    "-p", "--period",
    help="Display stats over a specified period (in seconds)",
    type=click.INT,
    default=0,
    show_default=True
)
@multi_asic_util.multi_asic_click_options
@click.option(
    "-j", "--json", "json_fmt",
    help="Display in JSON format",
    is_flag=True,
    default=False
)
@click.option(
    "-v", "--verbose",
    help="Enable verbose output",
    is_flag=True,
    default=False
)
def all_stats(period, display, namespace, json_fmt, verbose):
    """ Show switch all stats """

    cmd = ["switchstat", "--all"]

    if period is not None:
        cmd += ["-p", str(period)]
    if display is not None:
        cmd += ['-d', str(display)]
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if json_fmt:
        cmd += ['-j']

    clicommon.run_command(cmd, display_cmd=verbose)


@counters.command(
    name="trim"
)
@click.option(
    "-p", "--period",
    help="Display stats over a specified period (in seconds)",
    type=click.INT,
    default=0,
    show_default=True
)
@multi_asic_util.multi_asic_click_options
@click.option(
    "-j", "--json", "json_fmt",
    help="Display in JSON format",
    is_flag=True,
    default=False
)
@click.option(
    "-v", "--verbose",
    help="Enable verbose output",
    is_flag=True,
    default=False
)
def trim_stats(period, display, namespace, json_fmt, verbose):
    """ Show switch trimming stats """

    cmd = ["switchstat", "--trim"]

    if period is not None:
        cmd += ["-p", str(period)]
    if display is not None:
        cmd += ['-d', str(display)]
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if json_fmt:
        cmd += ['-j']

    clicommon.run_command(cmd, display_cmd=verbose)


@counters.command(
    name="detailed"
)
@click.option(
    "-p", "--period",
    help="Display stats over a specified period (in seconds)",
    type=click.INT,
    default=0,
    show_default=True
)
@multi_asic_util.multi_asic_click_options
@click.option(
    "-v", "--verbose",
    help="Enable verbose output",
    is_flag=True,
    default=False
)
def detailed_stats(period, display, namespace, verbose):
    """ Show switch detailed stats """

    cmd = ["switchstat", "--detail"]

    if period is not None:
        cmd += ["-p", str(period)]
    if display is not None:
        cmd += ['-d', str(display)]
    if namespace is not None:
        cmd += ['-n', str(namespace)]

    clicommon.run_command(cmd, display_cmd=verbose)
