import importlib
import json
import os
import sys

import click
import utilities_common.cli as clicommon
from natsort import natsorted
from sonic_py_common.multi_asic import get_external_ports
from tabulate import tabulate
from utilities_common import multi_asic as multi_asic_util
from utilities_common import constants
from utilities_common.general import load_db_config
from sonic_py_common import logger

SYSLOG_IDENTIFIER = "config"

log = logger.Logger(SYSLOG_IDENTIFIER)

# mock the redis for unit test purposes #
try:
    if os.environ["UTILITIES_UNIT_TESTING"] == "2":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        tests_path = os.path.join(modules_path, "tests")
        sys.path.insert(0, modules_path)
        sys.path.insert(0, tests_path)
        import mock_tables.dbconnector
    if os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] == "multi_asic":
        import mock_tables.mock_multi_asic
        importlib.reload(mock_tables.mock_multi_asic)
        mock_tables.dbconnector.load_namespace_config()

except KeyError:
    pass

# Default configuration
MAX_POLL_INTERVAL_TIME = 1000
DEFAULT_DETECTION_TIME = 200
DEFAULT_RESTORATION_TIME = 200
DEFAULT_POLL_INTERVAL = 200
DEFAULT_PORT_NUM = 32
DEFAULT_ACTION = 'drop'
DEFAULT_PFC_HISTORY_STATUS = "disable"

STATS_DESCRIPTION = [
    ('STORM DETECTED/RESTORED', 'PFC_WD_QUEUE_STATS_DEADLOCK_DETECTED', 'PFC_WD_QUEUE_STATS_DEADLOCK_RESTORED'),
    ('TX OK/DROP',              'PFC_WD_QUEUE_STATS_TX_PACKETS',        'PFC_WD_QUEUE_STATS_TX_DROPPED_PACKETS'),
    ('RX OK/DROP',              'PFC_WD_QUEUE_STATS_RX_PACKETS',        'PFC_WD_QUEUE_STATS_RX_DROPPED_PACKETS'),
    ('TX LAST OK/DROP',         'PFC_WD_QUEUE_STATS_TX_PACKETS_LAST',   'PFC_WD_QUEUE_STATS_TX_DROPPED_PACKETS_LAST'),
    ('RX LAST OK/DROP',         'PFC_WD_QUEUE_STATS_RX_PACKETS_LAST',   'PFC_WD_QUEUE_STATS_RX_DROPPED_PACKETS_LAST'),
]

CONFIG_DESCRIPTION = [
    ('ACTION',           'action',           'drop'),
    ('DETECTION TIME',   'detection_time',   'N/A'),
    ('RESTORATION TIME', 'restoration_time', 'infinite'),
    ('HISTORY',          'pfc_stat_history', 'disable')
]

STATS_HEADER = ('QUEUE', 'STATUS',) + list(zip(*STATS_DESCRIPTION))[0]
CONFIG_HEADER = ('PORT',) + list(zip(*CONFIG_DESCRIPTION))[0]

CONFIG_DB_PFC_WD_TABLE_NAME = 'PFC_WD'
STATE_DB_PFC_WD_STATE_TABLE = 'PFC_WD_STATE_TABLE'
STATE_DB_PFC_WD_HW_STATE_TABLE = 'PFC_WD_HW_STATE'
PORT_QOS_MAP =  "PORT_QOS_MAP"

# Main entrypoint
@click.group()
def cli():
    """ SONiC PFC Watchdog """
    load_db_config()

def get_all_queues(db, namespace=None, display=constants.DISPLAY_ALL):
    queue_names = db.get_all(db.COUNTERS_DB, 'COUNTERS_QUEUE_NAME_MAP')
    queues = list(queue_names.keys()) if queue_names else {}
    if display == constants.DISPLAY_ALL:
        return natsorted(queues)
    # filter the backend ports
    display_ports = [q.split(":")[0] for q in queues]
    display_ports = get_external_ports(display_ports, namespace)
    queues = [q for q in queues if q.split(":")[0] in display_ports]
    return natsorted(queues)


def get_all_ports(db, namespace=None, display=constants.DISPLAY_ALL):
    all_port_names = db.get_all(db.COUNTERS_DB, 'COUNTERS_PORT_NAME_MAP')

    # Get list of physical ports
    port_names = {}
    for i in all_port_names:
        if i.startswith('Ethernet'):
            port_names[i] = all_port_names[i]
    display_ports = list(port_names.keys())
    if display == constants.DISPLAY_EXTERNAL:
        display_ports = get_external_ports(display_ports, namespace)
    return natsorted(display_ports)


def get_server_facing_ports(db):
    candidates = db.get_table('DEVICE_NEIGHBOR')
    server_facing_ports = []
    for port in candidates:
        neighbor = db.get_entry(
            'DEVICE_NEIGHBOR_METADATA', candidates[port]['name']
        )
        if neighbor and neighbor['type'].lower() == 'server':
            server_facing_ports.append(port)
    if not server_facing_ports:
        server_facing_ports = [p[1] for p in db.get_table('VLAN_MEMBER')]
    return server_facing_ports


def get_bp_ports(db):
    """    Get all the backplane ports.    """
    candidates = db.get_table('PORT')
    bp_ports = []
    for port in candidates:
        if candidates[port].get('admin_status') == 'up' \
           and candidates[port].get('role') == 'Int':
            bp_ports.append(port)
    return bp_ports


class PfcwdCli(object):
    def __init__(
        self, db=None, namespace=None, display=constants.DISPLAY_ALL
    ):
        self.db = None
        self.config_db = None
        self.multi_asic = multi_asic_util.MultiAsic(
            display, namespace, db
        )
        self.table = []
        self.all_ports = []
        self.is_hardware_mode = False
        self.json_ports = {}
        self.json_globals = {}
        self.json_output_mode = False

    @multi_asic_util.run_on_multi_asic
    def collect_stats(self, empty, queues):
        table = []

        if len(queues) == 0:
            queues = get_all_queues(
                self.db,
                self.multi_asic.current_namespace,
                self.multi_asic.display_option
            )
        hw_mode = self.is_hw_mode()

        for queue in queues:
            stats_list = []
            queue_oid = self.db.get(
                self.db.COUNTERS_DB, 'COUNTERS_QUEUE_NAME_MAP', queue
            )
            if queue_oid is None:
                continue
            stats = self.db.get_all(
                self.db.COUNTERS_DB, 'COUNTERS:' + queue_oid
            )
            if stats is None:
                continue
            for stat in STATS_DESCRIPTION:
                # The hardware watchdog does not count RX
                if hw_mode and stat[0].startswith('RX'):
                    stats_list.append('N/A')
                    continue
                line = stats.get(stat[1], '0') + '/' + stats.get(stat[2], '0')
                stats_list.append(line)
            if any(line not in ('0/0', 'N/A') for line in stats_list) or empty:
                table.append(
                    [queue, stats.get('PFC_WD_STATUS', 'N/A')] + stats_list
                )

        self.table += table

    def show_stats(self, empty, queues, check_storm=False):
        del self.table[:]
        self.collect_stats(empty, queues)

        if check_storm:
            # Check for storms and exit accordingly - no output needed
            storms_detected = any(row[1] == 'stormed' for row in self.table if len(row) > 1)
            sys.exit(1 if storms_detected else 0)

        click.echo(tabulate(
            self.table, STATS_HEADER, stralign='right', numalign='right',
            tablefmt='simple'
        ))

    @multi_asic_util.run_on_multi_asic
    def get_all_namespace_ports(self):
        ports = get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )
        self.all_ports.extend(ports)

    def get_invalid_ports(self, ports=[]):
        if len(ports) == 0:
            return []
        self.get_all_namespace_ports()
        port_set = set(ports)
        # "all" is a valid option, remove before performing set diff
        port_set.discard("all")
        return port_set - set(self.all_ports)

    @multi_asic_util.run_on_multi_asic
    def collect_config(self, ports):
        table = []

        if len(ports) == 0:
            ports = get_all_ports(
                self.db, self.multi_asic.current_namespace,
                self.multi_asic.display_option
            )

        hw_limits = self.get_hw_recovery_limits()
        hw_mode = hw_limits is not None
        if hw_mode:
            self.is_hardware_mode = True

        glob_entry = self.config_db.get_entry(
            CONFIG_DB_PFC_WD_TABLE_NAME, 'GLOBAL'
        )
        for key, field in (('poll_interval', 'POLL_INTERVAL'),
                           ('big_red_switch', 'BIG_RED_SWITCH')):
            if self.multi_asic.is_multi_asic:
                # PFC_WD|GLOBAL is per ASIC
                self.json_globals.setdefault(key, {})[
                    self.multi_asic.current_namespace] = glob_entry.get(field)
            else:
                self.json_globals[key] = glob_entry.get(field)
        if hw_mode and 'hw_detection_time_ms' not in self.json_globals:
            for name in ('detection', 'restoration'):
                self.json_globals['hw_{}_time_ms'.format(name)] = {
                    'min': hw_limits[name + '_min'],
                    'max': hw_limits[name + '_max'],
                }

        ports_found = False
        for port in ports:
            config_entry = self.config_db.get_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, port
            )
            if config_entry is None or config_entry == {}:
                continue
            ports_found = True
            if hw_mode:
                hw_state = self.db.get_all(
                    self.db.STATE_DB,
                    STATE_DB_PFC_WD_HW_STATE_TABLE + '|' + port
                ) or {}
            config_list = []
            for config in CONFIG_DESCRIPTION:
                line = config_entry.get(config[1], config[2])
                config_list.append(line)
            table.append([port] + config_list)

            port_json = {
                'action': config_entry.get('action'),
                'detection_time': config_entry.get('detection_time'),
                'restoration_time': config_entry.get('restoration_time'),
                'pfc_stat_history': config_entry.get('pfc_stat_history'),
            }
            if hw_mode:
                port_json['hw_detection_time'] = hw_state.get('hw_detection_time')
                port_json['hw_restoration_time'] = hw_state.get('hw_restoration_time')
                port_json['hw_status'] = hw_state.get('status')
            self.json_ports[port] = port_json

        if not ports_found:
            return

        poll_interval = glob_entry.get('POLL_INTERVAL')

        current_ns = self.multi_asic.current_namespace
        asic_namesapce = \
            "" if current_ns is None or current_ns == "" else " on {}".format(
                current_ns
            )
        # The hardware watchdog ignores PFC_WD|GLOBAL
        show_global = not self.json_output_mode and not hw_mode
        if poll_interval is not None and show_global:
            click.echo(
                "Changed polling interval to {}ms{}".format(
                    poll_interval, asic_namesapce
                )
            )

        big_red_switch = glob_entry.get('BIG_RED_SWITCH')

        if big_red_switch is not None and show_global:
            click.echo("BIG_RED_SWITCH status is {}{}".format(
                big_red_switch, asic_namesapce
            ))

        self.table += table

    def config(self, ports, json_output=False):
        del self.table[:]
        self.is_hardware_mode = False
        self.json_ports = {}
        self.json_globals = {}
        self.json_output_mode = json_output
        self.collect_config(ports)
        if json_output:
            result = {
                'mode': 'hardware' if self.is_hardware_mode else 'software',
                'ports': self.json_ports,
            }
            result.update(self.json_globals)
            click.echo(json.dumps(result, indent=4, sort_keys=True))
            return
        if self.is_hardware_mode:
            # Hardware values are shown by --json only
            click.echo("Recovery mode: hardware")
        click.echo(tabulate(
            self.table, CONFIG_HEADER, stralign='right', numalign='right',
            tablefmt='simple'
        ))

    def start(self, action, restoration_time, ports, detection_time, pfc_stat_history):
        invalid_ports = self.get_invalid_ports(ports)
        if len(invalid_ports):
            click.echo("Failed to run command, invalid options:")
            for opt in invalid_ports:
                click.echo(opt)
            sys.exit(1)
        self.start_cmd(action, restoration_time, ports, detection_time, pfc_stat_history)

    def pfc_stat_history(self, pfc_stat_history, ports):
        invalid_ports = self.get_invalid_ports(ports)
        if len(invalid_ports):
            click.echo("Failed to run command, invalid options:")
            for opt in invalid_ports:
                click.echo(opt)
            sys.exit(1)
        self.pfc_stat_history_cmd(pfc_stat_history, ports)

    def verify_pfc_enable_status_per_port(self, port, pfcwd_info, overwrite=True):
        pfc_status = self.config_db.get_entry(PORT_QOS_MAP, port).get('pfc_enable')
        if pfc_status is None:
            log.log_warning("SKIPPED: PFC is not enabled on port: {}".format(port), also_print_to_console=True)
            return

        if overwrite:
            # don't clear existing pfc history setting unless set explicitly
            cur_pfc_history = self.config_db.get_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, port
            ).get("pfc_stat_history", DEFAULT_PFC_HISTORY_STATUS)

            pfcwd_info.setdefault("pfc_stat_history", cur_pfc_history)

            self.config_db.mod_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, port, None
            )
            self.config_db.set_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, port, pfcwd_info
            )
        else:
            self.config_db.mod_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, port, pfcwd_info
            )

    def configure_ports(self, ports, pfcwd_info, overwrite=True):
        all_ports = get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )

        if len(ports) == 0:
            ports = all_ports

        for port in ports:
            if port == "all":
                for p in all_ports:
                    self.verify_pfc_enable_status_per_port(p, pfcwd_info, overwrite)
            else:
                if port not in all_ports:
                    continue
                self.verify_pfc_enable_status_per_port(port, pfcwd_info, overwrite)

    @multi_asic_util.run_on_multi_asic
    def start_cmd(self, action, restoration_time, ports, detection_time, pfc_stat_history):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")

        pfcwd_info = {
            'detection_time': detection_time,
        }
        if action is not None:
            pfcwd_info['action'] = action
        if restoration_time is not None:
            pfcwd_info['restoration_time'] = restoration_time
        else:
            pfcwd_info['restoration_time'] = 2 * detection_time
            click.echo(
                "restoration time not defined; default to 2 times "
                "detection time: {} ms".format(2 * detection_time)
            )
        if pfc_stat_history:
            pfcwd_info["pfc_stat_history"] = "enable"

        hw_limits = self.get_hw_recovery_limits()
        if hw_limits is not None:
            for name, value in (('detection', detection_time),
                                ('restoration', pfcwd_info['restoration_time'])):
                low = hw_limits[name + '_min']
                high = hw_limits[name + '_max']
                # Skip a range that was not reported or has a zero bound
                if not low or not high:
                    continue
                if not low <= value <= high:
                    click.echo(
                        "Error: {}_time {}ms is outside hardware supported "
                        "range [{}-{}]ms".format(name, value, low, high),
                        err=True
                    )
                    sys.exit(1)

            # orchagent programs a port without an action as drop
            self.check_hw_action(action or DEFAULT_ACTION, ports)

        self.configure_ports(ports, pfcwd_info, overwrite=True)

        if hw_limits is not None:
            click.echo("Configuration submitted. Run 'show pfcwd config' to verify hardware programming.")

    def check_hw_action(self, action, ports):
        """Exit unless the hardware can take `action` for `ports`."""
        current_action = self.get_hw_global_action()
        if not current_action or current_action == action:
            return

        # One action for all ports; orchagent changes it only on the sole configured port
        if len(ports) == 0 or "all" in ports:
            ports = get_all_ports(
                self.db, self.multi_asic.current_namespace,
                self.multi_asic.display_option
            )
        configured_ports = set(self.config_db.get_table(CONFIG_DB_PFC_WD_TABLE_NAME)) - {'GLOBAL'}
        ports_with_old_action = configured_ports - set(ports) if len(ports) == 1 else configured_ports
        if ports_with_old_action:
            click.echo(
                "Error: Action mismatch. Hardware PFC watchdog requires all ports "
                "to use the same action.\n"
                "Current global action: {}\n"
                "Requested action: {}\n"
                "Ports with current action: {}\n"
                "Please use action '{}' or remove all existing ports first.".format(
                    current_action,
                    action,
                    ', '.join(sorted(ports_with_old_action)),
                    current_action
                ),
                err=True
            )
            sys.exit(1)

    def is_hw_mode(self):
        return self.get_hw_state() is not None

    def refuse_in_hw_mode(self):
        if self.is_hw_mode():
            click.echo(
                "Error: This command is not supported with hardware based PFC watchdog",
                err=True
            )
            sys.exit(1)

    def get_hw_state(self):
        """Return the STATE_DB PFC_WD_STATE_TABLE|PFC_WD entry in hardware mode, else None."""
        entry = self.db.get_all(
            self.db.STATE_DB, STATE_DB_PFC_WD_STATE_TABLE + '|PFC_WD'
        ) or {}
        if entry.get('RECOVERY_MECHANISM', '').upper() != 'HARDWARE':
            return None
        return entry

    def get_hw_recovery_limits(self):
        """Return the hardware timer limits (None if unreported), or None outside hardware mode."""
        entry = self.get_hw_state()
        if entry is None:
            return None

        def limit(field):
            try:
                return int(entry[field])
            except (KeyError, TypeError, ValueError):
                return None

        return {
            'detection_min': limit('DETECTION_TIME_MIN'),
            'detection_max': limit('DETECTION_TIME_MAX'),
            'restoration_min': limit('RESTORATION_TIME_MIN'),
            'restoration_max': limit('RESTORATION_TIME_MAX'),
        }

    def get_hw_global_action(self):
        """Return the hardware action, or None if unknown or not in hardware mode."""
        entry = self.get_hw_state()
        if entry is None:
            return None
        action = entry.get('DLR_PACKET_ACTION', '')
        if action.upper() in ['UNKNOWN', '']:
            return None
        return action.lower()

    @multi_asic_util.run_on_multi_asic
    def interval(self, poll_interval):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")

        self.refuse_in_hw_mode()

        pfcwd_info = {}
        if poll_interval is not None:
            pfcwd_table = self.config_db.get_table(CONFIG_DB_PFC_WD_TABLE_NAME)
            entry_min = MAX_POLL_INTERVAL_TIME
            for entry in pfcwd_table:
                if("Ethernet" not in entry):
                    continue
                detection_time_entry_value = int(self.config_db.get_entry(
                    CONFIG_DB_PFC_WD_TABLE_NAME, entry
                ).get('detection_time'))
                restoration_time_entry_value = int(self.config_db.get_entry(
                    CONFIG_DB_PFC_WD_TABLE_NAME, entry
                ).get('restoration_time'))
                if ((detection_time_entry_value is not None) and
                    (detection_time_entry_value < entry_min)
                ):
                    entry_min = detection_time_entry_value
                    entry_min_str = "detection time"
                if ((restoration_time_entry_value is not None) and
                    (restoration_time_entry_value < entry_min)
                ):
                    entry_min = restoration_time_entry_value
                    entry_min_str = "restoration time"
            if entry_min < poll_interval:
                click.echo(
                   "unable to use polling interval = {}ms, value is "
                   "bigger than one of the configured {} values, "
                   "please choose a smaller polling_interval".format(
                        poll_interval, entry_min_str
                    ), err=True
                )
                sys.exit(1)

            pfcwd_info['POLL_INTERVAL'] = poll_interval
            self.config_db.mod_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL", pfcwd_info
            )

    def get_stormed_queues(self, ports):
        """Return the queues (port:index) of the given ports that are stormed."""
        stormed_queues = []

        all_queues = get_all_queues(
            self.db,
            self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )

        for queue in all_queues:
            port_name = queue.split(':')[0]
            if port_name not in ports:
                continue

            queue_oid = self.db.get(
                self.db.COUNTERS_DB, 'COUNTERS_QUEUE_NAME_MAP', queue
            )
            if queue_oid is None:
                continue

            stats = self.db.get_all(
                self.db.COUNTERS_DB, 'COUNTERS:' + queue_oid
            )
            if stats is None:
                continue

            status = stats.get('PFC_WD_STATUS', '')
            if status == 'stormed':
                stormed_queues.append(queue)

        return stormed_queues

    @multi_asic_util.run_on_multi_asic
    def stop(self, ports):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")

        all_ports = get_all_ports(
            self.db, self.multi_asic.current_namespace,
            self.multi_asic.display_option
        )

        if len(ports) == 0:
            ports = all_ports

        if self.is_hw_mode():
            stormed_queues = self.get_stormed_queues(ports)
            if stormed_queues:
                click.echo(
                    "Error: Cannot stop PFC watchdog while queues are in stormed state.\n"
                    "Stormed queues: {}".format(', '.join(stormed_queues)),
                    err=True
                )
                sys.exit(1)

        for port in ports:
            if port not in all_ports:
                continue
            self.config_db.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, port, None)

    def count_pfc_enabled_ports(self, ports):
        """Count the ports that PFC watchdog will actually be configured on.

        verify_pfc_enable_status_per_port() skips any port that has no 'pfc_enable' in
        PORT_QOS_MAP, so these are the ports that receive a PFC_WD entry and contribute
        watchdog polling load. Counting every PORT entry instead would inflate the timers
        on behalf of ports that never get a watchdog.

        Args:
            ports (list): Candidate ports, i.e. the external and backplane ports.

        Returns:
            int: Number of the given ports that have PFC enabled.
        """
        port_qos_map = self.config_db.get_table(PORT_QOS_MAP)
        return sum(
            1 for port in ports
            if port_qos_map.get(port, {}).get('pfc_enable') is not None
        )

    @multi_asic_util.run_on_multi_asic
    def start_default(self):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")
        enable = self.config_db.get_entry('DEVICE_METADATA', 'localhost').get(
            'default_pfcwd_status'
        )

        # Get active ports from Config DB
        external_ports = list(self.config_db.get_table('DEVICE_NEIGHBOR').keys())
        bp_ports = get_bp_ports(self.config_db)

        active_ports = natsorted(set(external_ports + bp_ports))

        if not enable or enable.lower() != "enable":
            return

        port_num = self.count_pfc_enabled_ports(active_ports)

        hw_mode = self.is_hw_mode()

        # Hardware timers are per port, so they are not scaled by port count
        if hw_mode:
            self.check_hw_action(DEFAULT_ACTION, active_ports)
            detection_time = DEFAULT_DETECTION_TIME
            restoration_time = DEFAULT_RESTORATION_TIME
        else:
            # Parameter values positively correlate to the number of ports.
            multiply = max(1, (port_num-1)//DEFAULT_PORT_NUM+1)
            detection_time = DEFAULT_DETECTION_TIME * multiply
            restoration_time = DEFAULT_RESTORATION_TIME * multiply
            poll_interval = DEFAULT_POLL_INTERVAL * multiply
            if poll_interval > MAX_POLL_INTERVAL_TIME:
                poll_interval = MAX_POLL_INTERVAL_TIME

        pfcwd_info = {
            'detection_time': detection_time,
            'restoration_time': restoration_time,
            'action': DEFAULT_ACTION,
            'pfc_stat_history': DEFAULT_PFC_HISTORY_STATUS
        }

        for port in active_ports:
            self.verify_pfc_enable_status_per_port(port, pfcwd_info, overwrite=True)

        # The hardware watchdog ignores PFC_WD|GLOBAL
        if not hw_mode:
            pfcwd_info = {}
            pfcwd_info['POLL_INTERVAL'] = poll_interval
            self.config_db.mod_entry(
                CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL", pfcwd_info
            )
        else:
            # Drop a polling interval left by the software watchdog
            global_entry = self.config_db.get_entry(CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL")
            if global_entry.pop('POLL_INTERVAL', None) is not None:
                self.config_db.set_entry(
                    CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL", global_entry or None
                )

    @multi_asic_util.run_on_multi_asic
    def counter_poll(self, counter_poll):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")
        pfcwd_info = {}
        pfcwd_info['FLEX_COUNTER_STATUS'] = counter_poll
        self.config_db.mod_entry("FLEX_COUNTER_TABLE", "PFCWD", pfcwd_info)

    @multi_asic_util.run_on_multi_asic
    def big_red_switch(self, big_red_switch):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")

        self.refuse_in_hw_mode()

        pfcwd_info = {}
        if big_red_switch is not None:
            pfcwd_info['BIG_RED_SWITCH'] = big_red_switch
        self.config_db.mod_entry(
            CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL",
            pfcwd_info
        )

    @multi_asic_util.run_on_multi_asic
    def pfc_stat_history_cmd(self, pfc_stat_history, ports):
        if os.geteuid() != 0:
            sys.exit("Root privileges are required for this operation")

        pfcwd_info = {
            'pfc_stat_history': pfc_stat_history
        }
        self.configure_ports(ports, pfcwd_info, overwrite=False)

# Show stats
class Show(object):
    # Show commands
    @cli.group()
    def show():
        """ Show PFC Watchdog information"""

    @show.command()
    @multi_asic_util.multi_asic_click_options
    @click.option('-e', '--empty', is_flag=True)
    @click.option('--check-storm', is_flag=True, help='Exit 1 if any storms detected, 0 otherwise')
    @click.argument('queues', nargs=-1)
    @clicommon.pass_db
    def stats(db, namespace, display, empty, check_storm, queues):
        """ Show PFC Watchdog stats per queue """
        if (len(queues)):
            display = constants.DISPLAY_ALL
        PfcwdCli(db, namespace, display).show_stats(empty, queues, check_storm)

    # Show config
    @show.command()
    @multi_asic_util.multi_asic_click_options
    @click.option('--json', 'json_output', is_flag=True, help="Display output in JSON format")
    @click.argument('ports', nargs=-1)
    @clicommon.pass_db
    def config(db, namespace, display, ports, json_output):
        """ Show PFC Watchdog configuration """
        PfcwdCli(db, namespace, display).config(ports, json_output)


# Start WD
class Start(object):
    @cli.command()
    @click.option(
        '--action', '-a', type=click.Choice(['drop', 'forward', 'alert'])
    )
    @click.option('--restoration-time', '-r', type=click.IntRange(100, 60000))
    @click.option('--pfc-stat-history', is_flag=True)
    @click.argument('ports', nargs=-1)
    @click.argument('detection-time', type=click.IntRange(100, 5000))
    @clicommon.pass_db
    def start(db, action, restoration_time, ports, detection_time, pfc_stat_history):
        """
        Start PFC watchdog on port(s). To config all ports, use all as input.

        Example:

        sudo pfcwd start --action drop all 400 --restoration-time 400 --pfc-stat-history enable

        """
        PfcwdCli(db).start(
            action, restoration_time, ports, detection_time, pfc_stat_history
        )


# Set WD poll interval
class Interval(object):
    @cli.command()
    @click.argument('poll_interval', type=click.IntRange(100, MAX_POLL_INTERVAL_TIME))
    @clicommon.pass_db
    def interval(db, poll_interval):
        """ Set PFC watchdog counter polling interval """
        PfcwdCli(db).interval(poll_interval)


# Stop WD
class Stop(object):
    @cli.command()
    @click.argument('ports', nargs=-1)
    @clicommon.pass_db
    def stop(db, ports):
        """ Stop PFC watchdog on port(s) """
        PfcwdCli(db).stop(ports)


# Set WD default configuration on server facing ports when enable flag is on
class StartDefault(object):
    @cli.command("start_default")
    @clicommon.pass_db
    def start_default(db):
        """ Start PFC WD by default configurations  """
        PfcwdCli(db).start_default()


# Enable/disable PFC WD counter polling
class CounterPoll(object):
    @cli.command('counter_poll')
    @click.argument('counter_poll', type=click.Choice(['enable', 'disable']))
    @clicommon.pass_db
    def counter_poll(db, counter_poll):
        """ Enable/disable counter polling """
        PfcwdCli(db).counter_poll(counter_poll)


# Enable/disable PFC WD BIG_RED_SWITCH mode
class BigRedSwitch(object):
    @cli.command('big_red_switch')
    @click.argument('big_red_switch', type=click.Choice(['enable', 'disable']))
    @clicommon.pass_db
    def big_red_switch(db, big_red_switch):
        """ Enable/disable BIG_RED_SWITCH mode """
        PfcwdCli(db).big_red_switch(big_red_switch)


# Enable/disable PFC WD PFC_STAT_HISTORY mode
class PfcStatHistory(object):
    @cli.command('pfc_stat_history')
    @click.argument('pfc_stat_history', type=click.Choice(['enable', 'disable']))
    @click.argument('ports', nargs=-1)
    @clicommon.pass_db
    def pfc_stat_history(db, pfc_stat_history, ports):
        """ Enable/disable PFC Historical Statistics mode on ports"""
        PfcwdCli(db).pfc_stat_history(pfc_stat_history, ports)


def get_pfcwd_clis():
    cli.add_command(PfcStatHistory().pfc_stat_history)
    cli.add_command(BigRedSwitch().big_red_switch)
    cli.add_command(CounterPoll().counter_poll)
    cli.add_command(StartDefault().start_default)
    cli.add_command(Stop().stop)
    cli.add_command(Interval().interval)
    cli.add_command(Start().start)
    cli.add_command(Show().show)
    return cli


if __name__ == '__main__':
    cli = get_pfcwd_clis()
    cli()
