#!/usr/bin/env python3

import click
from swsscommon.swsscommon import ConfigDBConnector
from tabulate import tabulate
from sonic_py_common import multi_asic
from utilities_common.general import load_db_config
from utilities_common import multi_asic as multi_asic_util

from sonic_py_common import device_info

from .dash_config import config_dash
from .dash_show import show_dash


platform_info = device_info.get_platform_info()


class Crm:

    thresholds = (
        "ipv4_route", "ipv6_route", "ipv4_nexthop", "ipv6_nexthop", "ipv4_neighbor", "ipv6_neighbor",
        "nexthop_group_member", "nexthop_group", "acl_table", "acl_group", "acl_entry",
        "acl_counter", "fdb_entry", "ipmc_entry", "snat_entry", "dnat_entry", "mpls_inseg",
        "mpls_nexthop", "srv6_nexthop", "srv6_my_sid_entry", "twamp_entry"
    )

    resources = (
        "ipv4_route", "ipv6_route", "ipv4_nexthop", "ipv6_nexthop", "ipv4_neighbor", "ipv6_neighbor",
        "nexthop_group_member", "nexthop_group", "fdb_entry", "ipmc_entry", "snat_entry", "dnat_entry",
        "mpls_inseg", "mpls_nexthop", "srv6_nexthop", "srv6_my_sid_entry", "twamp_entry"
    )

    acl_resources = (
        "acl_table", "acl_group", "acl_entry", "acl_counter"
    )

    def __init__(self, db=None):
        self.cli_mode = None
        self.addr_family = None
        self.res_type = None
        self.db = None
        self.cfgdb = db
        self.multi_asic = multi_asic_util.MultiAsic()

    def get_thresholds_list(self):
        return list(self.thresholds)

    def get_resources_list(self):
        return list(self.resources)

    @multi_asic_util.run_on_multi_asic
    def config(self, attr, val):
        """
        CRM handler for 'config' CLI commands.
        """
        if self.cfgdb:
            self.config_db = self.cfgdb
        self.config_db.mod_entry("CRM", 'Config', {attr: val})

    def show_summary(self):
        """
        CRM Handler to display general information.
        """

        configdb = self.cfgdb
        if configdb is None:
            # Get the namespace list
            namespaces = multi_asic.get_namespace_list()

            configdb = ConfigDBConnector(namespace=namespaces[0])
            configdb.connect()

        crm_info = configdb.get_entry('CRM', 'Config')

        if crm_info:
            try:
                click.echo('\nPolling Interval: ' + crm_info['polling_interval'] + ' second(s)\n')
            except KeyError:
                click.echo('\nError! Could not get CRM configuration.\n')
                click.echo('\nError! Please configure polling interval.\n')
        else:
            click.echo('\nError! Could not get CRM configuration.\n')

    def show_thresholds(self, resource):
        """
        CRM Handler to display thresholds information.
        """
        configdb = self.cfgdb
        if configdb is None:
            # Get the namespace list
            namespaces = multi_asic.get_namespace_list()

            configdb = ConfigDBConnector(namespace=namespaces[0])
            configdb.connect()

        crm_info = configdb.get_entry('CRM', 'Config')

        header = ("Resource Name", "Threshold Type", "Low Threshold", "High Threshold")
        data = []

        if crm_info:
            if resource == 'all':
                for res in self.get_thresholds_list():
                    try:
                        data.append([res, crm_info[res + "_threshold_type"], crm_info[res + "_low_threshold"], crm_info[res + "_high_threshold"]])
                    except KeyError:
                        pass
            else:
                try:
                    data.append([resource, crm_info[resource + "_threshold_type"], crm_info[resource + "_low_threshold"], crm_info[resource + "_high_threshold"]])
                except KeyError:
                    pass
        else:
            click.echo('\nError! Could not get CRM configuration.')

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    def get_resources(self, resource):
        """
        CRM Handler to get resources information.
        """
        crm_stats = self.db.get_all(self.db.COUNTERS_DB, 'CRM:STATS')
        data = []

        if crm_stats:
            if resource == 'all':
                for res in self.get_resources_list():
                    if 'crm_stats_' + res + "_used" in crm_stats.keys() and 'crm_stats_' + res + "_available" in crm_stats.keys():
                        data.append([res, crm_stats['crm_stats_' + res + "_used"], crm_stats['crm_stats_' + res + "_available"]])
            else:
                if 'crm_stats_' + resource + "_used" in crm_stats.keys() and 'crm_stats_' + resource + "_available" in crm_stats.keys():
                    data.append([resource, crm_stats['crm_stats_' + resource + "_used"], crm_stats['crm_stats_' + resource + "_available"]])

        return data

    def get_acl_resources(self):
        """
        CRM Handler to get ACL recources information.
        """
        data = []

        for stage in ["INGRESS", "EGRESS"]:
            for bind_point in ["PORT", "LAG", "VLAN", "RIF", "SWITCH"]:
                crm_stats = self.db.get_all(self.db.COUNTERS_DB, 'CRM:ACL_STATS:{0}:{1}'.format(stage, bind_point))

                if crm_stats:
                    for res in ["acl_group", "acl_table"]:
                        data.append([
                                        stage, bind_point, res,
                                        crm_stats['crm_stats_' + res + "_used"],
                                        crm_stats['crm_stats_' + res + "_available"]
                                    ])

        return data
    def get_acl_table_resources(self):
        """
        CRM Handler to display ACL table information.
        """
        # Retrieve all ACL table keys from CRM:ACL_TABLE_STATS
        crm_acl_keys = self.db.keys(self.db.COUNTERS_DB, 'CRM:ACL_TABLE_STATS*')
        data = []

        for key in crm_acl_keys or [None]:
            if key:
                id = key.replace('CRM:ACL_TABLE_STATS:', '')

                crm_stats = self.db.get_all(self.db.COUNTERS_DB, key)

                for res in ['acl_entry', 'acl_counter']:
                    if ('crm_stats_' + res + '_used' in crm_stats) and ('crm_stats_' + res + '_available' in crm_stats):
                        data.append([id, res, crm_stats['crm_stats_' + res + '_used'], crm_stats['crm_stats_' + res + '_available']])

        return data

    @multi_asic_util.run_on_multi_asic
    def show_resources(self, resource):
        """
        CRM Handler to display resources information.
        """
        if multi_asic.is_multi_asic():
            header = (self.multi_asic.current_namespace.upper() + "\n\nResource Name", "\n\nUsed Count", "\n\nAvailable Count")
            err_msg = '\nCRM counters are not ready for '+ self.multi_asic.current_namespace.upper() + '. They would be populated after the polling interval.'
        else:
            header = ("Resource Name", "Used Count", "Available Count")
            err_msg = '\nCRM counters are not ready. They would be populated after the polling interval.'

        data = []
        data = self.get_resources(resource)

        if data:
            click.echo()
            click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
            click.echo()
        else:
            click.echo(err_msg)

    @multi_asic_util.run_on_multi_asic
    def show_acl_resources(self):
        """
        CRM Handler to display ACL recources information.
        """

        if multi_asic.is_multi_asic():
            header = (self.multi_asic.current_namespace.upper() + "\n\nStage", "\n\nBind Point", "\n\nResource Name", "\n\nUsed Count", "\n\nAvailable Count")
        else:
            header = ("Stage", "Bind Point", "Resource Name", "Used Count", "Available Count")

        data = []
        data = self.get_acl_resources()

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    @multi_asic_util.run_on_multi_asic
    def show_acl_table_resources(self):
        """
        CRM Handler to display ACL table information.
        """
        if multi_asic.is_multi_asic():
            header = (self.multi_asic.current_namespace.upper() + "\n\nTable ID", "\n\nResource Name", "\n\nUsed Count", "\n\nAvailable Count")
        else:
            header = ("Table ID", "Resource Name", "Used Count", "Available Count")

        data = []
        data = self.get_acl_table_resources()

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    def show_all_thresholds(self):
        self.show_thresholds('all')

    def show_all_resources(self):
        self.show_resources('all')
        self.show_acl_resources()
        self.show_acl_table_resources()


class DashCrm(Crm):

    dash_resources = (
        "dash_vnet", "dash_eni", "dash_eni_ether_address_map", "dash_ipv4_inbound_routing", "dash_ipv6_inbound_routing",
        "dash_ipv4_outbound_routing", "dash_ipv6_outbound_routing", "dash_ipv4_pa_validation", "dash_ipv6_pa_validation",
        "dash_ipv4_outbound_ca_to_pa", "dash_ipv6_outbound_ca_to_pa", "dash_ipv4_acl_group","dash_ipv6_acl_group"
        )

    dash_acl_group_resources = (
        "dash_ipv4_acl_rule", "dash_ipv6_acl_rule"
        )

    dash_thresholds = dash_resources + dash_acl_group_resources

    def __init__(self, *args, **kwargs):
        self.direction = None

        super().__init__(*args, *kwargs)

    def get_thresholds_list(self):
        thresholds = super().get_thresholds_list()
        thresholds.extend(self.dash_thresholds)
        return list(thresholds)

    def get_resources_list(self):
        resources = super().get_resources_list()
        resources.extend(self.dash_resources)
        return list(resources)

    def show_all_resources(self):
        super().show_all_resources()
        self.show_acl_group_resources()

    def get_dash_acl_group_resources(self, resource=None):
        # Retrieve all ACL table keys from CRM:ACL_TABLE_STATS
        crm_acl_keys = self.db.keys(self.db.COUNTERS_DB, 'CRM:DASH_ACL_GROUP_STATS*')
        data = []

        for key in crm_acl_keys:
            id = key.replace('CRM:DASH_ACL_GROUP_STATS:', '')

            crm_stats = self.db.get_all(self.db.COUNTERS_DB, key)

            query = [resource] if resource else self.dash_acl_group_resources
            for res in query:
                used = f'crm_stats_{res}_used'
                available = f'crm_stats_{res}_available'
                if used in crm_stats and available in crm_stats:
                    data.append([id, res, crm_stats[used], crm_stats[available]])

        return data

    @multi_asic_util.run_on_multi_asic
    def show_acl_group_resources(self, resource=None):
        if self.multi_asic.is_multi_asic:
            click.echo('\nError! Could not get CRM configuration.\n')
            return

        header = ("DASH ACL Group ID", "Resource Name", "Used Count", "Available Count")

        data = []
        data = self.get_dash_acl_group_resources(resource)

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()


@click.group()
@click.pass_context
def cli(ctx):
    """
    Utility entry point.
    """
    # Use the db object if given as input.
    db = None if ctx.obj is None else ctx.obj.cfgdb

    # Load database config files
    load_db_config()

    if device_info.get_platform_info().get('switch_type') == "dpu":
        crm = DashCrm(db)
    else:
        crm = Crm(db)

    context = {
        "crm": crm
    }

    ctx.obj = context

@cli.group()
@click.pass_context
def config(ctx):
    """CRM related configuration"""
    pass

@config.group()
@click.pass_context
def polling(ctx):
    """CRM polling configuration"""
    pass

@polling.command()
@click.pass_context
@click.argument('interval', type=click.IntRange(1, 9999))
def interval(ctx, interval):
    """CRM polling interval configuration in seconds (range: 1-9999)"""
    ctx.obj["crm"].config('polling_interval', interval)

@config.group()
@click.pass_context
def thresholds(ctx):
    """CRM thresholds configuration"""
    pass

@thresholds.group()
@click.pass_context
def ipv4(ctx):
    """CRM resource IPv4 address-family"""
    ctx.obj["crm"].addr_family = 'ipv4'

@thresholds.group()
@click.pass_context
def ipv6(ctx):
    """CRM resource IPv6 address-family"""
    ctx.obj["crm"].addr_family = 'ipv6'

@thresholds.group()
@click.pass_context
def mpls(ctx):
    """CRM resource MPLS address-family"""
    ctx.obj["crm"].addr_family = 'mpls'

@mpls.group()
@click.pass_context
def inseg(ctx):
    """CRM configuration for in-segment resource"""
    ctx.obj["crm"].res_type = 'inseg'

@ipv4.group()
@click.pass_context
def route(ctx):
    """CRM configuration for route resource"""
    ctx.obj["crm"].res_type = 'route'

@ipv4.group()
@click.pass_context
def neighbor(ctx):
    """CRM configuration for neigbor resource"""
    ctx.obj["crm"].res_type = 'neighbor'

@ipv4.group()
@click.pass_context
def nexthop(ctx):
    """CRM configuration for nexthop resource"""
    ctx.obj["crm"].res_type = 'nexthop'

@click.command()
@click.argument('value', type=click.Choice(['percentage', 'used', 'free']))
@click.pass_context
def type(ctx, value):
    """CRM threshold type configuration"""
    attr = ''

    if ctx.obj["crm"].addr_family != None:
        attr += ctx.obj["crm"].addr_family + '_'

    attr += ctx.obj["crm"].res_type + '_' + 'threshold_type'

    ctx.obj["crm"].config(attr, value)

@click.command()
@click.argument('value', type=click.INT)
@click.pass_context
def low(ctx, value):
    """CRM low threshold configuration"""
    attr = ''

    if ctx.obj["crm"].addr_family != None:
        attr += ctx.obj["crm"].addr_family + '_'

    attr += ctx.obj["crm"].res_type + '_' + 'low_threshold'

    ctx.obj["crm"].config(attr, value)

@click.command()
@click.argument('value', type=click.INT)
@click.pass_context
def high(ctx, value):
    """CRM high threshold configuration"""
    attr = ''

    if ctx.obj["crm"].addr_family != None:
        attr += ctx.obj["crm"].addr_family + '_'

    attr += ctx.obj["crm"].res_type + '_' + 'high_threshold'

    ctx.obj["crm"].config(attr, value)

route.add_command(type)
route.add_command(low)
route.add_command(high)
neighbor.add_command(type)
neighbor.add_command(low)
neighbor.add_command(high)
nexthop.add_command(type)
nexthop.add_command(low)
nexthop.add_command(high)
inseg.add_command(type)
inseg.add_command(low)
inseg.add_command(high)
ipv6.add_command(route)
ipv6.add_command(neighbor)
ipv6.add_command(nexthop)
mpls.add_command(nexthop)

@thresholds.group()
@click.pass_context
def nexthop(ctx):
    """CRM configuration for nexthop resource"""
    pass
@nexthop.group()
@click.pass_context
def group(ctx):
    """CRM configuration for nexthop group resource"""
    pass
@group.group()
@click.pass_context
def member(ctx):
    """CRM configuration for nexthop group member resource"""
    ctx.obj["crm"].res_type = 'nexthop_group_member'
@group.group()
@click.pass_context
def object(ctx):
    """CRM configuration for nexthop group resource"""
    ctx.obj["crm"].res_type = 'nexthop_group'

member.add_command(type)
member.add_command(low)
member.add_command(high)
object.add_command(type)
object.add_command(low)
object.add_command(high)

@thresholds.group()
@click.pass_context
def fdb(ctx):
    """CRM configuration for FDB resource"""
    ctx.obj["crm"].res_type = 'fdb_entry'

fdb.add_command(type)
fdb.add_command(low)
fdb.add_command(high)

@thresholds.group()
@click.pass_context
def ipmc(ctx):
    """CRM configuration for IPMC resource"""
    ctx.obj["crm"].res_type = 'ipmc_entry'

ipmc.add_command(type)
ipmc.add_command(low)
ipmc.add_command(high)

@thresholds.group()
@click.pass_context
def snat(ctx):
    """CRM configuration for Source NAT resource"""
    ctx.obj["crm"].res_type = 'snat_entry'

snat.add_command(type)
snat.add_command(low)
snat.add_command(high)

@thresholds.group()
@click.pass_context
def dnat(ctx):
    """CRM configuration for Destination NAT resource"""
    ctx.obj["crm"].res_type = 'dnat_entry'

dnat.add_command(type)
dnat.add_command(low)
dnat.add_command(high)

@thresholds.group()
@click.pass_context
def acl(ctx):
    """CRM configuration for ACL resource"""
    pass

@acl.group()
@click.pass_context
def table(ctx):
    """CRM configuration for ACL table resource"""
    ctx.obj["crm"].res_type = 'acl_table'

table.add_command(type)
table.add_command(low)
table.add_command(high)

@acl.group()
@click.pass_context
def group(ctx):
    """CRM configuration for ACL group resource"""
    ctx.obj["crm"].res_type = 'acl_group'

group.add_command(type)
group.add_command(low)
group.add_command(high)

@group.group()
@click.pass_context
def entry(ctx):
    """CRM configuration for ACL entry resource"""
    ctx.obj["crm"].res_type = 'acl_entry'

entry.add_command(type)
entry.add_command(low)
entry.add_command(high)

@group.group()
@click.pass_context
def counter(ctx):
    """CRM configuration for ACL counter resource"""
    ctx.obj["crm"].res_type = 'acl_counter'

counter.add_command(type)
counter.add_command(low)
counter.add_command(high)

@thresholds.group()
@click.pass_context
def srv6_nexthop(ctx):
    """CRM configuration for SRV6 Nexthop resource"""
    ctx.obj["crm"].res_type = 'srv6_nexthop'

srv6_nexthop.add_command(type)
srv6_nexthop.add_command(low)
srv6_nexthop.add_command(high)

@thresholds.group()
@click.pass_context
def srv6_my_sid_entry(ctx):
    """CRM configuration for SRV6 MY_SID resource"""
    ctx.obj["crm"].res_type = 'srv6_my_sid_entry'

srv6_my_sid_entry.add_command(type)
srv6_my_sid_entry.add_command(low)
srv6_my_sid_entry.add_command(high)

if device_info.get_platform_info().get('switch_type') == "dpu":
    thresholds.add_command(config_dash)

@cli.group()
@click.pass_context
def show(ctx):
    """Show CRM related information"""
    pass

@show.command()
@click.pass_context
def summary(ctx):
    """Show CRM general information"""
    ctx.obj["crm"].show_summary()

@show.group()
@click.pass_context
def resources(ctx):
    """Show CRM resources information"""
    ctx.obj["crm"].cli_mode = 'resources'

@show.group()
@click.pass_context
def thresholds(ctx):
    """Show CRM thresholds information"""
    ctx.obj["crm"].cli_mode = 'thresholds'

@resources.command()
@click.pass_context
def all(ctx):
    """Show CRM information for all resources"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_all_thresholds()
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_all_resources()

@resources.group()
@click.pass_context
def ipv4(ctx):
    """CRM resource IPv4 address family"""
    ctx.obj["crm"].addr_family = 'ipv4'

@resources.group()
@click.pass_context
def ipv6(ctx):
    """CRM resource IPv6 address family"""
    ctx.obj["crm"].addr_family = 'ipv6'

@resources.group()
@click.pass_context
def mpls(ctx):
    """CRM resource MPLS address family"""
    ctx.obj["crm"].addr_family = 'mpls'

@mpls.command()
@click.pass_context
def inseg(ctx):
    """Show CRM information for in-segment resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_inseg'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_inseg'.format(ctx.obj["crm"].addr_family))

@ipv4.command()
@click.pass_context
def route(ctx):
    """Show CRM information for route resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_route'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_route'.format(ctx.obj["crm"].addr_family))

@ipv4.command()
@click.pass_context
def neighbor(ctx):
    """Show CRM information for neighbor resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_neighbor'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_neighbor'.format(ctx.obj["crm"].addr_family))

@ipv4.command()
@click.pass_context
def nexthop(ctx):
    """Show CRM information for nexthop resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_nexthop'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_nexthop'.format(ctx.obj["crm"].addr_family))

ipv6.add_command(route)
ipv6.add_command(neighbor)
ipv6.add_command(nexthop)
mpls.add_command(nexthop)

@resources.group()
@click.pass_context
def nexthop(ctx):
    """Show CRM information for nexthop resource"""
    pass

@nexthop.group()
@click.pass_context
def group(ctx):
    """Show CRM information for nexthop group resource"""
    pass

@group.command()
@click.pass_context
def member(ctx):
    """Show CRM information for nexthop group member resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('nexthop_group_member')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('nexthop_group_member')

@group.command()
@click.pass_context
def object(ctx):
    """Show CRM information for nexthop group resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('nexthop_group')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('nexthop_group')

@resources.group()
@click.pass_context
def acl(ctx):
    """Show CRM information for acl resource"""
    pass

@acl.command()
@click.pass_context
def table(ctx):
    """Show CRM information for acl table resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('acl_table')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_acl_table_resources()

@acl.command()
@click.pass_context
def group(ctx):
    """Show CRM information for acl group resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('acl_group')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_acl_resources()

@resources.command()
@click.pass_context
def fdb(ctx):
    """Show CRM information for fdb resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('fdb_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('fdb_entry')

@resources.command()
@click.pass_context
def ipmc(ctx):
    """Show CRM information for IPMC resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('ipmc_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('ipmc_entry')

@resources.command()
@click.pass_context
def snat(ctx):
    """Show CRM information for SNAT resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('snat_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('snat_entry')

@resources.command()
@click.pass_context
def dnat(ctx):
    """Show CRM information for DNAT resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('dnat_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('dnat_entry')

@resources.command()
@click.pass_context
def srv6_nexthop(ctx):
    """Show CRM information for SRV6 Nexthop"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('srv6_nexthop')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('srv6_nexthop')

@resources.command()
@click.pass_context
def srv6_my_sid_entry(ctx):
    """Show CRM information for SRV6 MY_SID entry"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('srv6_my_sid_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('srv6_my_sid_entry')


@resources.command()
@click.pass_context
def twamp_entry(ctx):
    """Show CRM information for TWAMP entry"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('twamp_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('twamp_entry')

thresholds.add_command(acl)
thresholds.add_command(all)
thresholds.add_command(fdb)
thresholds.add_command(ipv4)
thresholds.add_command(ipv6)
thresholds.add_command(mpls)
thresholds.add_command(nexthop)
thresholds.add_command(ipmc)
thresholds.add_command(snat)
thresholds.add_command(dnat)
thresholds.add_command(srv6_nexthop)
thresholds.add_command(srv6_my_sid_entry)
thresholds.add_command(twamp_entry)

if device_info.get_platform_info().get('switch_type') == "dpu":
    resources.add_command(show_dash)
    thresholds.add_command(show_dash)

if __name__ == '__main__':
    cli()
