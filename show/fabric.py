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

@fabric.group(invoke_without_command=True)
@multi_asic_util.multi_asic_click_option_namespace
@click.option('-e', '--errors', is_flag=True)
def isolation(namespace, errors):
    """Show fabric isolation status"""
    cmd = ['fabricstat',  '-i']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if errors:
        cmd += ["-e"]
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
def port(namespace, errors):
    """Show fabric port stat"""
    cmd = ["fabricstat"]
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    if errors:
        cmd += ["-e"]
    clicommon.run_command(cmd)

@counters.command()
@multi_asic_util.multi_asic_click_option_namespace
def queue(namespace):
    """Show fabric queue stat"""
    cmd = ['fabricstat', '-q']
    if namespace is not None:
        cmd += ['-n', str(namespace)]
    clicommon.run_command(cmd)
