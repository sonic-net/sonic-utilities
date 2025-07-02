import configparser
import os
import subprocess
import sys
import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic
from sonic_py_common.general import getstatusoutput_noshell_pipe
from flow_counter_util.route import exit_if_route_flow_counter_not_support
from utilities_common import util_base
from show.plugins.pbh import read_pbh_counters
from config.plugins.pbh import serialize_pbh_counters
from . import plugins
from . import stp
# This is from the aliases example:
# https://github.com/pallets/click/blob/57c6f09611fc47ca80db0bd010f05998b3c0aa95/examples/aliases/aliases.py
class Config(object):
    """Object to hold CLI config"""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


# Global Config object
_config = None



class AliasedGroup(click.Group):
    """This subclass of click.Group supports abbreviations and
       looking up aliases in a config file with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        global _config

        # If we haven't instantiated our global config, do it now and load current config
        if _config is None:
            _config = Config()

            # Load our config file
            cfg_file = os.path.join(os.path.dirname(__file__), 'aliases.ini')
            _config.read_config(cfg_file)

        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # No builtin found. Look up an explicit command alias in the config
        if cmd_name in _config.aliases:
            actual_cmd = _config.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


# To be enhanced. Routing-stack information should be collected from a global
# location (configdb?), so that we prevent the continous execution of this
# bash oneliner. To be revisited once routing-stack info is tracked somewhere.
def get_routing_stack():
    cmd0 = ["sudo", "docker", "ps"]
    cmd1 = ["grep", "bgp"]
    cmd2 = ["awk", '{print$2}']
    cmd3 = ["cut", "-d-", "-f3"]
    cmd4 = ["cut", "-d:", "-f1"]

    try:
        _, result = getstatusoutput_noshell_pipe(cmd0, cmd1, cmd2, cmd3, cmd4)

    except OSError as e:
        raise OSError("Cannot detect routing-stack")

    return (result)


# Global Routing-Stack variable
routing_stack = get_routing_stack()


def run_command(command, pager=False, return_output=False, return_exitstatus=False):
    # Provide option for caller function to Process the output.
    proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE)
    if return_output:
        output = proc.communicate()
        return output if not return_exitstatus else output + (proc.returncode,)
    elif pager:
        #click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        click.echo_via_pager(proc.stdout.read())
    else:
        #click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        click.echo(proc.stdout.read())


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])


#
# 'cli' group (root group) ###
#

# This is our entrypoint - the main "Clear" command
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """SONiC command line - 'Clear' command"""
    pass

#
# 'ip' group ###
#

# This allows us to add commands to both cli and ip groups, allowing for
# "Clear <command>" and "Clear ip <command>" to function the same
@cli.group()
def ip():
    """Clear IP """
    pass


# 'ipv6' group

@cli.group()
def ipv6():
    """Clear IPv6 information"""
    pass


# 'STP'
#
cli.add_command(stp.spanning_tree)

#
# Inserting BGP functionality into cli's clear parse-chain.
# BGP commands are determined by the routing-stack being elected.
#
if routing_stack == "quagga":
    from .bgp_quagga_v4 import bgp
    ip.add_command(bgp)
    from .bgp_quagga_v6 import bgp
    ipv6.add_command(bgp)
elif routing_stack == "frr":
    from .bgp_quagga_v4 import bgp
    ip.add_command(bgp)
    from .bgp_frr_v6 import bgp
    ipv6.add_command(bgp)

@cli.command()
def counters():
    """Clear counters"""
    command = ["portstat", "-c"]
    run_command(command)

@cli.command()
@click.argument('interface', metavar='<interface_name>', required=False, type=str)
def rifcounters(interface):
    """Clear RIF counters"""
    command = ["intfstat", "-c"]
    if interface is not None:
        command = ["intfstat", "-i", interface, "-c"]
    run_command(command)

@cli.command()
def queuecounters():
    """Clear queue counters"""
    command = ["queuestat", "-c"]
    run_command(command)

    command = ["queuestat", "-c", "--voq"]
    run_command(command)

@cli.command()
def fabriccountersqueue():
    """Clear fabric queue counters"""
    command = ["fabricstat", "-C", "-q"]
    run_command(command)

@cli.command()
def fabriccountersport():
   """Clear fabric port counters"""
   command = ["fabricstat", "-C"]
   run_command(command)

@cli.command()
def pfccounters():
    """Clear pfc counters"""
    command = ["pfcstat", "-c"]
    run_command(command)

@cli.command()
def dropcounters():
    """Clear drop counters"""
    command = ["dropstat", "-c", "clear"]
    run_command(command)

@cli.command()
def tunnelcounters():
    """Clear Tunnel counters"""
    command = ["tunnelstat", "-c"]
    run_command(command)


@cli.command()
def srv6counters():
    """Clear SRv6 counters"""
    command = ["srv6stat", "-c"]
    run_command(command)

#
# 'clear watermarks
#

@cli.group(name='priority-group')
def priority_group():
    """Clear priority_group WM"""
    pass

@priority_group.group()
def watermark():
    """Clear priority_group user WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")


@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
@watermark.command('headroom')
def clear_wm_pg_headroom(namespace):
    """Clear user headroom WM for pg"""
    command = ['watermarkstat', '-c', '-t', 'pg_headroom']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@watermark.command('shared')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_wm_pg_shared(namespace):
    """Clear user shared WM for pg"""
    command = ['watermarkstat', '-c', '-t', 'pg_shared']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)

@priority_group.group()
def drop():
    """Clear priority-group dropped packets stats"""
    pass

@drop.command('counters')
def clear_pg_counters():
    """Clear priority-group dropped packets counter """

    if os.geteuid() != 0 and os.environ.get("UTILITIES_UNIT_TESTING", "0") != "2":
        sys.exit("Root privileges are required for this operation")
    command = ['pg-drop', '-c', 'clear']
    run_command(command)

@priority_group.group(name='persistent-watermark')
def persistent_watermark():
    """Clear queue persistent WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")


@persistent_watermark.command('headroom')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_pwm_pg_headroom(namespace):
    """Clear persistent headroom WM for pg"""
    command = ['watermarkstat', '-c', '-p', '-t', 'pg_headroom']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@persistent_watermark.command('shared')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_pwm_pg_shared(namespace):
    """Clear persistent shared WM for pg"""
    command = ['watermarkstat', '-c', '-p', '-t', 'pg_shared']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@cli.group()
def queue():
    """Clear queue"""
    pass


@queue.command()
def wredcounters():
    """Clear queue wredcounters"""
    command = ['wredstat', '-c']
    run_command(command)


@queue.group()
def watermark():
    """Clear queue user WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")


@watermark.command('unicast')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_wm_q_uni(namespace):
    """Clear user WM for unicast queues"""
    command = ['watermarkstat', '-c', '-t', 'q_shared_uni']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@watermark.command('multicast')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_wm_q_multi(namespace):
    """Clear user WM for multicast queues"""
    command = ['watermarkstat', '-c', '-t', 'q_shared_multi']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@watermark.command('all')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_wm_q_all(namespace):
    """Clear user WM for all queues"""
    command = ['watermarkstat', '-c', '-t', 'q_shared_all']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@queue.group(name='persistent-watermark')
def persistent_watermark():
    """Clear queue persistent WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")


@persistent_watermark.command('unicast')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_pwm_q_uni(namespace):
    """Clear persistent WM for persistent queues"""
    command = ['watermarkstat', '-c', '-p', '-t', 'q_shared_uni']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@persistent_watermark.command('multicast')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_pwm_q_multi(namespace):
    """Clear persistent WM for multicast queues"""
    command = ['watermarkstat', '-c', '-p', '-t', 'q_shared_multi']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@persistent_watermark.command('all')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def clear_pwm_q_all(namespace):
    """Clear persistent WM for all queues"""
    command = ['watermarkstat', '-c', '-p', '-t', 'q_shared_all']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@cli.group(name='headroom-pool')
def headroom_pool():
    """Clear headroom pool WM"""
    pass


@headroom_pool.command('watermark')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def watermark(namespace):
    """Clear headroom pool user WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")

    command = ['watermarkstat', '-c', '-t', 'headroom_pool']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)


@headroom_pool.command('persistent-watermark')
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
def persistent_watermark(namespace):
    """Clear headroom pool persistent WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")

    command = ['watermarkstat', '-c', '-p', '-t', 'headroom_pool']
    if namespace:
        command += ['-n', str(namespace)]
    run_command(command)

#
# 'arp' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def arp(ipaddress):
    """Clear IP ARP table"""
    if ipaddress is not None:
        command = ['sudo', 'ip', '-4', 'neigh', 'show', ipaddress]
        (out, err) = run_command(command, return_output=True)
        if not err and 'dev' in out:
            outputList = out.split()
            dev = outputList[outputList.index('dev') + 1]
            command = ['sudo', 'ip', '-4', 'neigh', 'del', ipaddress, 'dev', dev]
        else:
            click.echo("Neighbor {} not found".format(ipaddress))
            return
    else:
        command = ['sudo', 'ip', '-4', '-s', '-s', 'neigh', 'flush', 'all']

    run_command(command)

#
# 'ndp' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def ndp(ipaddress):
    """Clear IPv6 NDP table"""
    if ipaddress is not None:
        command = ['sudo', 'ip', '-6', 'neigh', 'show', ipaddress]
        (out, err) = run_command(command, return_output=True)
        if not err and 'dev' in out:
            outputList = out.split()
            dev = outputList[outputList.index('dev') + 1]
            command = ['sudo', 'ip', '-6', 'neigh', 'del', ipaddress, 'dev', dev]
        else:
            click.echo("Neighbor {} not found".format(ipaddress))
            return
    else:
        command = ['sudo', 'ip', '-6', '-s', '-s', 'neigh', 'flush', 'all']

    run_command(command)

# Add 'arp' command to both the root 'cli' group and the 'ip' subgroup
cli.add_command(arp)
cli.add_command(ndp)
ip.add_command(arp)
ip.add_command(ndp)

#
# 'fdb' command ####
#
@cli.group()
def fdb():
    """Clear FDB table"""
    pass

@fdb.command('all')
def clear_all_fdb():
    """Clear All FDB entries"""
    command = ['fdbclear']
    run_command(command)

# 'sonic-clear fdb port' and 'sonic-clear fdb vlan' will be added later
'''
@fdb.command('port')
@click.argument('portid', required=True)
def clear_port_fdb(portid):
    """Clear FDB entries learned from one port"""
    command = 'fdbclear' + ' -p ' + portid
    run_command(command)

@fdb.command('vlan')
@click.argument('vlanid', required=True)
def clear_vlan_fdb(vlanid):
    """Clear FDB entries learned in one VLAN"""
    command = 'fdbclear' + ' -v ' + vlanid
    run_command(command)
'''

#
# 'line' command
#
@cli.command('line')
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True, help="clear by name - if flag is set, interpret target as device name instead")
def line(target, devicename):
    """Clear preexisting connection to line"""
    cmd = ["consutil", "clear", "--devicename", str(target)] if devicename else ["consutil", "clear", str(target)]
    (output, _, exitstatus) = run_command(cmd, return_output=True, return_exitstatus=True)
    click.echo(output)
    sys.exit(exitstatus)

#
# 'nat' group ("clear nat ...")
#

@cli.group(cls=AliasedGroup)
def nat():
    """Clear the nat info"""
    pass

# 'statistics' subcommand ("clear nat statistics")
@nat.command()
def statistics():
    """ Clear all NAT statistics """

    cmd = ["natclear", "-s"]
    run_command(cmd)

# 'translations' subcommand ("clear nat translations")
@nat.command()
def translations():
    """ Clear all NAT translations """

    cmd = ["natclear", "-t"]
    run_command(cmd)

# 'pbh' group ("clear pbh ...")
@cli.group(cls=AliasedGroup)
def pbh():
    """ Clear the PBH info """
    pass

# 'statistics' subcommand ("clear pbh statistics")
@pbh.command()
@clicommon.pass_db
def statistics(db):
    """ Clear PBH counters
        clear counters -- write current counters to file in /tmp
    """

    pbh_rules = db.cfgdb.get_table("PBH_RULE")
    pbh_counters = read_pbh_counters(pbh_rules)

    serialize_pbh_counters(pbh_counters)


# ("sonic-clear flowcnt-trap")
@cli.command()
def flowcnt_trap():
    """ Clear trap flow counters """
    command = ["flow_counters_stat", "-c", '-t', "trap"]
    run_command(command)


# ("sonic-clear flowcnt-route")
@cli.group(invoke_without_command=True)
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
@click.pass_context
def flowcnt_route(ctx, namespace):
    """Clear all route flow counters"""
    exit_if_route_flow_counter_not_support()
    if ctx.invoked_subcommand is None:
        command = ['flow_counters_stat', '-c', '-t', 'route']
        # None namespace means default namespace
        if namespace is not None:
            command += ['-n', str(namespace)]
        clicommon.run_command(command)


# ("sonic-clear flowcnt-route pattern")
@flowcnt_route.command()
@click.option('--vrf', help='VRF/VNET name or default VRF')
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
@click.argument('prefix-pattern', required=True)
def pattern(prefix_pattern, vrf, namespace):
    """Clear route flow counters by pattern"""
    command = ['flow_counters_stat', '-c', '-t', 'route', '--prefix_pattern', str(prefix_pattern)]
    if vrf:
        command += ['--vrf', str(vrf)]
    # None namespace means default namespace
    if namespace is not None:
        command += ['-n', str(namespace)]
    clicommon.run_command(command)


# ("sonic-clear flowcnt-route route")
@flowcnt_route.command()
@click.option('--vrf', help='VRF/VNET name or default VRF')
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
@click.argument('prefix', required=True)
def route(prefix, vrf, namespace):
    """Clear route flow counters by prefix"""
    command = ['flow_counters_stat', '-c', '-t', 'route', '--prefix', str(prefix)]
    if vrf:
        command += ['--vrf', str(vrf)]
    # None namespace means default namespace
    if namespace is not None:
        command += ['-n', str(namespace)]
    clicommon.run_command(command)


# Load plugins and register them
helper = util_base.UtilHelper()
helper.load_and_register_plugins(plugins, cli)

# ("sonic-clear asic-sdk-health-event")
@cli.command()
@click.option('--namespace', '-n', 'namespace', required=False, default=None, show_default=False,
              help='Option needed for multi-asic only: provide namespace name',
              type=click.Choice(multi_asic_util.multi_asic_ns_choices()))
@clicommon.pass_db
def asic_sdk_health_event(db, namespace):
    """Clear received ASIC/SDK health events"""
    if multi_asic.get_num_asics() > 1:
        namespace_list = multi_asic.get_namespaces_from_linux()
    else:
        namespace_list = [multi_asic.DEFAULT_NAMESPACE]

    for ns in namespace_list:
        if namespace and namespace != ns:
            continue

        state_db = db.db_clients[ns]
        keys = state_db.keys(db.db.STATE_DB, "ASIC_SDK_HEALTH_EVENT_TABLE*")
        for key in keys:
            state_db.delete(state_db.STATE_DB, key);


if __name__ == '__main__':
    cli()
