import sys
import click
from pfcwd.main import get_all_ports
# from utilities_common.cli import AbbreviationGroup, pass_db
# from .validated_config_db_connector import ValidatedConfigDBConnector
from tabulate import tabulate

import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
import utilities_common.constants as constants
import sonic_py_common.logger as logger

log = logger.Logger("config")
CONFIG_DB_PFC_STAT_HISTORY_TABLE_NAME = 'PFC_STAT_HISTORY'
CONFIG_DB_PFC_STAT_HISTORY_GROUP_NAME = 'PFC_STAT_HISTORY'
CONFIG_DB_FLEX_COUNTER_TABLE_NAME = "FLEX_COUNTER_TABLE"
PORT_QOS_MAP =  "PORT_QOS_MAP"
PFC_STAT_HISTORY_DEFAULT_POLLING_INTERVAL = 1000
PFC_STAT_HISTORY_DEFAULT_STATUS = "disable"

#
# 'pfc-stat-history' group ('config pfc-stat-history ...')
#
@click.group(cls=clicommon.AbbreviationGroup, name='pfc-stat-history')
@clicommon.pass_db
def config_pfc_stat_history(db):
    pass

@config_pfc_stat_history.command()
@click.argument('ports', nargs=-1)
@clicommon.pass_db
def start(db, ports):
    """ Start PFC Stat History on port(s) """
    PfcStatHistoryCli(db).start(ports)

@config_pfc_stat_history.command()
@click.argument('ports', nargs=-1)
@clicommon.pass_db
def stop(db, ports):
    """ Stop PFC Stat History on port(s) """
    PfcStatHistoryCli(db).stop(ports)

@config_pfc_stat_history.command('status')
@click.argument('status', type=click.Choice(['enable', 'disable']))
@clicommon.pass_db
def status(db, status):
    """ Enable/disable PFC Stat History counter polling """
    PfcStatHistoryCli(db).status(status)

@config_pfc_stat_history.command()
@click.argument('poll_interval', type=click.IntRange(100, 3000))
@clicommon.pass_db
def interval(db, poll_interval):
    """ PFC Stat History polling interval """
    PfcStatHistoryCli(db).interval(poll_interval)


#
# 'pfc-stat-history' group ('show pfc-stat-history ...')
#
@click.group(cls=clicommon.AbbreviationGroup, name='pfc-stat-history')
@clicommon.pass_db
def show_pfc_stat_history(db):
    pass

@show_pfc_stat_history.command()
@multi_asic_util.multi_asic_click_options
@clicommon.pass_db
def config(db, namespace, display):
    """ Show PFC Stat History configuration """
    PfcStatHistoryCli(db, namespace, display).show()

class PfcStatHistoryCli(object):
    '''
    Configuration of the PFC Stat History feature
    '''
    def __init__(
        self, db=None, namespace=None, display=constants.DISPLAY_ALL
    ):
        self.db = None
        self.config_db = None
        self.multi_asic = multi_asic_util.MultiAsic(
            display, namespace, db
        )
        self.all_ports = []
        self.all_started_ports = []

    def validate_ports(self, ports, allowed_ports):
        invalid_ports = ports - set(allowed_ports)

        if len(invalid_ports):
            click.echo("Failed to run command, invalid ports:")
            for opt in invalid_ports:
                click.echo(opt)
            sys.exit(1)

    @multi_asic_util.run_on_multi_asic
    def collect_all_ports(self):
        self.all_ports.extend(get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        ))

    @multi_asic_util.run_on_multi_asic
    def collect_all_started_ports(self):
        self.all_started_ports.extend(
            self.config_db.get_table(
                CONFIG_DB_PFC_STAT_HISTORY_TABLE_NAME
            ).keys()
        )

    def start(self, ports):
        self.collect_all_ports()
        self.validate_ports(set(ports), set(self.all_ports) | {"all"})
        self.start_cmd(ports)

    @multi_asic_util.run_on_multi_asic
    def start_cmd(self, ports):
        all_ports = get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )

        if len(ports) == 0 or ports[0] == "all":
            ports = all_ports

        for port in ports:
            # port does not belong to current namespace
            if port not in all_ports:
                continue
            pfc_status = self.config_db.get_entry(PORT_QOS_MAP, port).get('pfc_enable')
            if pfc_status is None:
                log.log_warning("SKIPPED: PFC is not enabled on port: {}".format(port), also_print_to_console=True)
                continue

            # the port simply needs to have an entry in config db, it is disabled by deletion
            self.config_db.mod_entry(
                CONFIG_DB_PFC_STAT_HISTORY_TABLE_NAME, port, {"status": "enabled"}
            )

    def stop(self, ports):
        self.collect_all_started_ports()
        self.validate_ports(set(ports), set(self.all_started_ports) | {"all"})
        self.stop_cmd(ports)
        
    @multi_asic_util.run_on_multi_asic
    def stop_cmd(self, ports):
        all_ports = get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )

        if len(ports) == 0 or ports[0] == "all":
            ports = all_ports

        for port in ports:
            # port does not belong to current namespace
            if port not in all_ports:
                continue
            self.config_db.mod_entry(CONFIG_DB_PFC_STAT_HISTORY_TABLE_NAME, port, None)

    @multi_asic_util.run_on_multi_asic
    def status(self, status):
        pfc_stat_history_group = {}
        pfc_stat_history_group['FLEX_COUNTER_STATUS'] = status
        self.config_db.mod_entry(CONFIG_DB_FLEX_COUNTER_TABLE_NAME,
                                 CONFIG_DB_PFC_STAT_HISTORY_GROUP_NAME,
                                 pfc_stat_history_group)

    @multi_asic_util.run_on_multi_asic
    def interval(self, poll_interval):
        pfc_stat_history_group = {}
        pfc_stat_history_group['POLL_INTERVAL'] = poll_interval
        self.config_db.mod_entry(CONFIG_DB_FLEX_COUNTER_TABLE_NAME,
                                 CONFIG_DB_PFC_STAT_HISTORY_GROUP_NAME,
                                 pfc_stat_history_group)

    @multi_asic_util.run_on_multi_asic
    def show(self):
        current_ns = self.multi_asic.current_namespace
        if current_ns:
            click.echo("Namespace: {}".format(current_ns))

        config = self.config_db.get_entry(
            CONFIG_DB_FLEX_COUNTER_TABLE_NAME, 
            CONFIG_DB_PFC_STAT_HISTORY_GROUP_NAME
        )

        all_ports = get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )

        click.echo(tabulate(config.items(), ["Setting", "Value"]))
        
        enabled_ports = []
        for port in all_ports:
            config_entry = self.config_db.get_entry(
                CONFIG_DB_PFC_STAT_HISTORY_TABLE_NAME, port
            )
            if config_entry is None or config_entry == {}:
                continue
            enabled_ports.append(port)

        if len(enabled_ports) > 0:
            click.echo("\nPFC Stat History enabled on:")
            click.echo('\n'.join(enabled_ports) + '\n')
        else:
            click.echo("\nPFC Stat History not enabled on any ports\n")