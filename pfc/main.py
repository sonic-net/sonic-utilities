#!/usr/bin/env python3
import os
import click
import json
from sonic_py_common import multi_asic
from tabulate import tabulate
from natsort import natsorted
from utilities_common import multi_asic as multi_asic_util

# Constants
ALL_PRIORITIES = [str(x) for x in range(8)]
PRIORITY_STATUS = ['on', 'off']
PORT_TABLE_NAME = "PORT"
PORT_QOS_MAP_TABLE_NAME = "PORT_QOS_MAP"


class Pfc(object):
    def __init__(self, namespace=None):
        self.multi_asic = multi_asic_util.MultiAsic(namespace_option=namespace)
        self.config_db = None

        # For unit testing
        self.updated_port_tables = {}
        self.test_filename = '/tmp/pfc_testdata.json'

    def dump_config_to_json(self, table_name, namespace):
        """
        This function dumps the current config in a JSON file for unit testing.
        """
        # Only dump files in unit testing mode
        if os.getenv("UTILITIES_UNIT_TESTING") != "2":
            return

        if namespace not in self.updated_port_tables.keys():
            self.updated_port_tables[namespace] = {}

        self.updated_port_tables[namespace][table_name] = self.config_db.get_table(table_name)
        with open(self.test_filename, "w") as fd:
            json.dump(self.updated_port_tables, fd)

    @multi_asic_util.run_on_multi_asic
    def configPfcAsym(self, interface, pfc_asym):
        """
        PFC handler to configure asymmetric PFC.
        """
        self.config_db.mod_entry(PORT_TABLE_NAME, interface, {'pfc_asym': pfc_asym})
        self.dump_config_to_json(PORT_TABLE_NAME, self.multi_asic.current_namespace)

    @multi_asic_util.run_on_multi_asic
    def showPfcAsym(self, interface):
        """
        PFC handler to display asymmetric PFC information.
        """
        namespace_str = f"Namespace {self.multi_asic.current_namespace}" if multi_asic.is_multi_asic() else ''
        header = ('Interface', 'Asymmetric')

        if interface:
            db_keys = self.config_db.keys(self.config_db.CONFIG_DB, 'PORT|{0}'.format(interface))
        else:
            db_keys = self.config_db.keys(self.config_db.CONFIG_DB, 'PORT|*')

        table = []

        for i in db_keys or [None]:
            key = None
            if i:
                key = i.split('|')[-1]

            if key and key.startswith('Ethernet'):
                entry = self.config_db.get_entry(PORT_TABLE_NAME, key)
                table.append([key, entry.get('pfc_asym', 'N/A')])

        sorted_table = natsorted(table)

        click.echo(namespace_str)
        click.echo(tabulate(sorted_table, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    @multi_asic_util.run_on_multi_asic
    def configPfcPrio(self, status, interface, priority):
        if interface not in self.config_db.get_keys(PORT_QOS_MAP_TABLE_NAME):
            click.echo('Cannot find interface {0}'.format(interface))
            return

        """Current lossless priorities on the interface"""
        entry = self.config_db.get_entry('PORT_QOS_MAP', interface)
        enable_prio = entry.get('pfc_enable').split(',')

        """Avoid '' in enable_prio"""
        enable_prio = [x.strip() for x in enable_prio if x.strip()]

        namespace_str = f" for namespace {self.multi_asic.current_namespace}" if multi_asic.is_multi_asic() else ''
        if status == 'on' and priority in enable_prio:
            click.echo('Priority {0} has already been enabled on {1}{2}'.format(priority, interface, namespace_str))
            return

        if status == 'off' and priority not in enable_prio:
            click.echo('Priority {0} is not enabled on {1}{2}'.format(priority, interface, namespace_str))
            return

        if status == 'on':
            enable_prio.append(priority)

        else:
            enable_prio.remove(priority)

        enable_prio.sort()
        self.config_db.mod_entry(PORT_QOS_MAP_TABLE_NAME, interface, {'pfc_enable': ','.join(enable_prio)})
        self.dump_config_to_json(PORT_QOS_MAP_TABLE_NAME, self.multi_asic.current_namespace)

    @multi_asic_util.run_on_multi_asic
    def showPfcPrio(self, interface):
        """
        PFC handler to display PFC enabled priority information.
        """
        header = ('Interface', 'Lossless priorities')
        table = []

        """Get all the interfaces with QoS map information"""
        intfs = self.config_db.get_keys('PORT_QOS_MAP')

        """The user specifies an interface but we cannot find it"""
        namespace_str = f"Namespace {self.multi_asic.current_namespace}" if multi_asic.is_multi_asic() else ''
        if interface and interface not in intfs:
            if multi_asic.is_multi_asic():
                click.echo('Cannot find interface {0} for {1}'.format(interface, namespace_str))
            else:
                click.echo('Cannot find interface {0}'.format(interface))
            return

        if interface:
            intfs = [interface]

        for intf in intfs:
            entry = self.config_db.get_entry('PORT_QOS_MAP', intf)
            table.append([intf, entry.get('pfc_enable', 'N/A')])

        sorted_table = natsorted(table)
        click.echo(namespace_str)
        click.echo(tabulate(sorted_table, headers=header, tablefmt="simple", missingval=""))
        click.echo()


@click.group()
def cli():
    """PFC Command Line"""


@cli.group()
def config():
    """Config PFC"""
    pass


@cli.group()
def show():
    """Show PFC information"""
    pass


@click.command()
@click.argument('status', type=click.Choice(PRIORITY_STATUS))
@click.argument('interface', type=click.STRING)
@multi_asic_util.multi_asic_click_option_namespace
def configAsym(status, interface, namespace):
    """Configure asymmetric PFC on a given port."""
    Pfc(namespace).configPfcAsym(interface, status)


@click.command()
@click.argument('status', type=click.Choice(PRIORITY_STATUS))
@click.argument('interface', type=click.STRING)
@click.argument('priority', type=click.Choice(ALL_PRIORITIES))
@multi_asic_util.multi_asic_click_option_namespace
def configPrio(status, interface, priority, namespace):
    """Configure PFC on a given priority."""
    Pfc(namespace).configPfcPrio(status, interface, priority)


@click.command()
@click.argument('interface', type=click.STRING, required=False)
@multi_asic_util.multi_asic_click_option_namespace
def showAsym(interface, namespace):
    """Show asymmetric PFC information"""
    Pfc(namespace).showPfcAsym(interface)


@click.command()
@click.argument('interface', type=click.STRING, required=False)
@multi_asic_util.multi_asic_click_option_namespace
def showPrio(interface, namespace):
    """Show PFC priority information"""
    Pfc(namespace).showPfcPrio(interface)


config.add_command(configAsym, "asymmetric")
config.add_command(configPrio, "priority")
show.add_command(showAsym, "asymmetric")
show.add_command(showPrio, "priority")
