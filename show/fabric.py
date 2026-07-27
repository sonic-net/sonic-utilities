import click

import utilities_common.multi_asic as multi_asic_util
import utilities_common.cli as clicommon

@click.group(cls=clicommon.AliasedGroup)
def fabric():
    """Show fabric information"""
    pass

@fabric.group(invoke_without_command=True)
def counters():
    """Show fabric port counters"""
    pass

@fabric.group(cls=clicommon.AliasedGroup)
def monitor():
    """Show fabric monitor"""
    pass

@monitor.group(invoke_without_command=True)
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-e', '--errors', is_flag=True)
def capacity(namespace, errors):
    """Show fabric capacity"""
    cmd = ['fabricstat', '-c']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if errors:
        cmd += ['-e']
    clicommon.run_command(cmd)

@fabric.group(invoke_without_command=True)
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-e', '--errors', is_flag=True)
@click.option('-nz', '--nonzero', is_flag=True,
              help='Show only fabric links with non-zero isolation counters')
def isolation(namespace, errors, nonzero):
    """Show fabric isolation status"""
    cmd = ['fabricstat',  '-i']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if errors:
        cmd += ["-e"]
    if nonzero:
        cmd += ['-nz']
    clicommon.run_command(cmd)

@fabric.group(invoke_without_command=True)
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-e', '--errors', is_flag=True)
def reachability(namespace, errors):
    """Show fabric reachability"""
    cmd = ['fabricstat', '-r']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if errors:
        cmd += ["-e"]
    clicommon.run_command(cmd)

@counters.command()
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-e', '--errors', is_flag=True)
@click.option('-nz', '--nonzero', is_flag=True,
              help='Show only fabric ports with a non-zero counter delta')
def port(namespace, errors, nonzero):
    """Show fabric port stat"""
    cmd = ["fabricstat"]
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if errors:
        cmd += ["-e"]
    if nonzero:
        cmd += ['-nz']
    clicommon.run_command(cmd)

@counters.command()
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-nz', '--nonzero', is_flag=True,
              help='Show only fabric queue rows with a non-zero counter delta')
def queue(namespace, nonzero):
    """Show fabric queue stat"""
    cmd = ['fabricstat', '-q']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if nonzero:
        cmd += ['-nz']
    clicommon.run_command(cmd)


@counters.command()
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-nz', '--nonzero', is_flag=True,
              help='Show only fabric links with non-zero Rx or Tx rate')
def rate(namespace, nonzero):
    """Show fabric counters rate"""
    cmd = ['fabricstat', '-s']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if nonzero:
        cmd += ['-nz']
    clicommon.run_command(cmd)
