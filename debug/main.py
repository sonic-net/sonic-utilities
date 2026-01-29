import re
import sys
import click
import subprocess
from shlex import join
from . import stp


def run_command(command, pager=False):
    command_str = join(command)
    click.echo(click.style("Command: ", fg='cyan') + click.style(command_str, fg='green'))
    p = subprocess.Popen(command, text=True, stdout=subprocess.PIPE)
    output = p.stdout.read()
    if pager:
        click.echo_via_pager(output)
    else:
        click.echo(output)


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])
#
# 'cli' group (root group) ###
#

@click.group(cls=click.Group, context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
def cli():
    """SONiC command line - 'debug' command"""
    pass


prefix_pattern = '^[A-Za-z0-9.:/]*$'
p = subprocess.check_output(['sudo', 'vtysh', '-c', 'show version'], text=True)
if 'FRRouting' in p:
    #
    # 'bgp' group for FRR ###
    #
    @cli.group()
    def bgp():
        """debug bgp group """
        pass

    @bgp.command('allow-martians')
    def allow_martians():
        """BGP allow martian next hops"""
        command = ['sudo', 'vtysh', '-c', "debug bgp allow-martians"]
        run_command(command)

    @bgp.command()
    @click.argument('additional', type=click.Choice(['segment']), required=False)
    def as4(additional):
        """BGP AS4 actions"""
        command = ['sudo', 'vtysh', '-c', "debug bgp as4"]
        if additional is not None:
            command[-1] += " segment"
        run_command(command)

    @bgp.command()
    @click.argument('prefix', required=True)
    def bestpath(prefix):
        """BGP bestpath"""
        if not re.match(prefix_pattern, prefix):
            sys.exit('Prefix contains only number, alphabet, period, colon, and forward slash')
        command = ['sudo', 'vtysh', '-c', "debug bgp bestpath %s" % prefix]
        run_command(command)

    @bgp.command()
    @click.argument('prefix_or_iface', required=False)
    def keepalives(prefix_or_iface):
        """BGP Neighbor Keepalives"""
        command = ['sudo', 'vtysh', '-c', "debug bgp keepalives"]
        if prefix_or_iface is not None:
            command[-1] += ' ' + prefix_or_iface
        run_command(command)

    @bgp.command('neighbor-events')
    @click.argument('prefix_or_iface', required=False)
    def neighbor_events(prefix_or_iface):
        """BGP Neighbor Events"""
        command = ['sudo', 'vtysh', '-c', "debug bgp neighbor-events"]
        if prefix_or_iface is not None:
            command[-1] += ' ' + prefix_or_iface
        run_command(command)

    @bgp.command()
    def nht():
        """BGP nexthop tracking events"""
        command = ['sudo', 'vtysh', '-c', "debug bgp nht"]
        run_command(command)

    @bgp.command()
    @click.argument('additional', type=click.Choice(['error']), required=False)
    def pbr(additional):
        """BGP policy based routing"""
        command = ['sudo', 'vtysh', '-c', "debug bgp pbr"]
        if additional is not None:
            command[-1] += " error"
        run_command(command)

    @bgp.command('update-groups')
    def update_groups():
        """BGP update-groups"""
        command = ['sudo', 'vtysh', '-c', "debug bgp update-groups"]
        run_command(command)

    @bgp.command()
    @click.argument('direction', type=click.Choice(['in', 'out', 'prefix']), required=False)
    @click.argument('prefix', required=False)
    def updates(direction, prefix):
        """BGP updates"""
        bgp_cmd = "debug bgp updates"
        if direction is not None:
            bgp_cmd += ' ' + direction
        if prefix is not None:
            if not re.match(prefix_pattern, prefix):
                sys.exit('Prefix contains only number, alphabet, period, colon, and forward slash')
            bgp_cmd += ' ' + prefix
        command = ['sudo', 'vtysh', '-c', bgp_cmd]
        run_command(command)

    @bgp.command()
    @click.argument('prefix', required=False)
    def zebra(prefix):
        """BGP Zebra messages"""
        command = ['sudo', 'vtysh', '-c', "debug bgp zebra"]
        if prefix is not None:
            if not re.match(prefix_pattern, prefix):
                sys.exit('Prefix contains only number, alphabet, period, colon, and forward slash')
            command[-1] += " prefix " + prefix
        run_command(command)

    #
    # 'zebra' group for FRR ###
    #
    @cli.group()
    def zebra():
        """debug zebra group"""
        pass

    @zebra.command()
    @click.argument('detailed', type=click.Choice(['detailed']), required=False)
    def dplane(detailed):
        """Debug zebra dataplane events"""
        command = ['sudo', 'vtysh', '-c', "debug zebra dplane"]
        if detailed is not None:
            command[-1] += " detailed"
        run_command(command)

    @zebra.command()
    def events():
        """Debug option set for zebra events"""
        command = ['sudo', 'vtysh', '-c', "debug zebra events"]
        run_command(command)

    @zebra.command()
    def fpm():
        """Debug zebra FPM events"""
        command = ['sudo', 'vtysh', '-c', "debug zebra fpm"]
        run_command(command)

    @zebra.command()
    def kernel():
        """Debug option set for zebra between kernel interface"""
        command = ['sudo', 'vtysh', '-c', "debug zebra kernel"]
        run_command(command)

    @zebra.command()
    def nht():
        """Debug option set for zebra next hop tracking"""
        command = ['sudo', 'vtysh', '-c', "debug zebra nht"]
        run_command(command)

    @zebra.command()
    def packet():
        """Debug option set for zebra packet"""
        command = ['sudo', 'vtysh', '-c', "debug zebra packet"]
        run_command(command)

    @zebra.command()
    @click.argument('detailed', type=click.Choice(['detailed']), required=False)
    def rib(detailed):
        """Debug RIB events"""
        command = ['sudo', 'vtysh', '-c', "debug zebra rib"]
        if detailed is not None:
            command[-1] += " detailed"
        run_command(command)

    @zebra.command()
    def vxlan():
        """Debug option set for zebra VxLAN (EVPN)"""
        command = ['sudo', 'vtysh', '-c', "debug zebra vxlan"]
        run_command(command)

else:
    #
    # 'bgp' group for quagga ###
    #
    @cli.group(invoke_without_command=True)
    @click.pass_context
    def bgp(ctx):
        """debug bgp on"""
        if ctx.invoked_subcommand is None:
            command = ['sudo', 'vtysh', '-c', "debug bgp"]
            run_command(command)

    @bgp.command()
    def events():
        """debug bgp events on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp events"]
        run_command(command)

    @bgp.command()
    def updates():
        """debug bgp updates on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp updates"]
        run_command(command)

    @bgp.command()
    def as4():
        """debug bgp as4 actions on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp as4"]
        run_command(command)

    @bgp.command()
    def filters():
        """debug bgp filters on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp filters"]
        run_command(command)

    @bgp.command()
    def fsm():
        """debug bgp finite state machine on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp fsm"]
        run_command(command)

    @bgp.command()
    def keepalives():
        """debug bgp keepalives on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp keepalives"]
        run_command(command)

    @bgp.command()
    def zebra():
        """debug bgp zebra messages on"""
        command = ['sudo', 'vtysh', '-c', "debug bgp zebra"]
        run_command(command)

    #
    # 'zebra' group for quagga ###
    #
    @cli.group()
    def zebra():
        """debug zebra group"""
        pass

    @zebra.command()
    def events():
        command = ['sudo', 'vtysh', '-c', "debug zebra events"]
        run_command(command)

    @zebra.command()
    def fpm():
        """debug zebra FPM events"""
        command = ['sudo', 'vtysh', '-c', "debug zebra fpm"]
        run_command(command)

    @zebra.command()
    def kernel():
        """debug option set for zebra between kernel interface"""
        command = ['sudo', 'vtysh', '-c', "debug zebra kernel"]
        run_command(command)

    @zebra.command()
    def packet():
        """debug option set for zebra packet"""
        command = ['sudo', 'vtysh', '-c', "debug zebra packet"]
        run_command(command)

    @zebra.command()
    def rib():
        """debug RIB events"""
        command = ['sudo', 'vtysh', '-c', "debug zebra rib"]
        run_command(command)

#
# 'STP' group
#
cli.add_command(stp.spanning_tree)

if __name__ == '__main__':
    cli()
