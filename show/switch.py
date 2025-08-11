import click

import utilities_common.cli as clicommon
from utilities_common import multi_asic


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
@multi_asic.multi_asic_click_options
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
@multi_asic.multi_asic_click_options
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
@multi_asic.multi_asic_click_options
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
@multi_asic.multi_asic_click_options
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
