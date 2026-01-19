import datetime
import time
import re
from collections import OrderedDict, namedtuple
from natsort import natsorted
from tabulate import tabulate
from sonic_py_common import multi_asic
from sonic_py_common import device_info
from swsscommon.swsscommon import SonicV2Connector, CounterTable, PortCounter

from utilities_common import constants
import utilities_common.multi_asic as multi_asic_util
from utilities_common.netstat import ns_diff, table_as_json, format_brate, format_prate, \
                                     format_util, format_number_with_comma, format_util_directly, \
                                     format_fec_ber, format_fec_flr, format_fec_flr_predicted

"""
The order and count of statistics mentioned below needs to be in sync with the values in portstat script
So, any fields added/deleted in here should be reflected in portstat script also
"""
NStats = namedtuple("NStats", "rx_ok, rx_err, rx_drop, rx_ovr, tx_ok,\
                    tx_err, tx_drop, tx_ovr, rx_byt, tx_byt,\
                    rx_64, rx_65_127, rx_128_255, rx_256_511, rx_512_1023,\
                    rx_1024_1518, rx_1519_2047, rx_2048_4095, rx_4096_9216, rx_9217_16383,\
                    rx_uca, rx_mca, rx_bca, rx_all,\
                    tx_64, tx_65_127, tx_128_255, tx_256_511, tx_512_1023, tx_1024_1518,\
                    tx_1519_2047, tx_2048_4095, tx_4096_9216, tx_9217_16383,\
                    tx_uca, tx_mca, tx_bca, tx_all,\
                    rx_jbr, rx_frag, rx_usize, rx_ovrrun,\
                    fec_corr, fec_uncorr, fec_symbol_err,\
                    wred_grn_drp_pkt, wred_ylw_drp_pkt, wred_red_drp_pkt, wred_tot_drp_pkt,\
                    trim, trim_sent, trim_drop, fec_bin0, fec_bin1, fec_bin2, fec_bin3,\
                    fec_bin4, fec_bin5, fec_bin6, fec_bin7, fec_bin8, fec_bin9, fec_bin10,\
                    fec_bin11, fec_bin12, fec_bin13, fec_bin14, fec_bin15")
header_all = ['IFACE', 'STATE', 'RX_OK', 'RX_BPS', 'RX_PPS', 'RX_UTIL', 'RX_ERR', 'RX_DRP', 'RX_OVR',
              'TX_OK', 'TX_BPS', 'TX_PPS', 'TX_UTIL', 'TX_ERR', 'TX_DRP', 'TX_OVR', 'TRIM', 'TRIM_TX', 'TRIM_DRP']
header_std = ['IFACE', 'STATE', 'RX_OK', 'RX_BPS', 'RX_UTIL', 'RX_ERR', 'RX_DRP', 'RX_OVR',
              'TX_OK', 'TX_BPS', 'TX_UTIL', 'TX_ERR', 'TX_DRP', 'TX_OVR']
header_errors_only = ['IFACE', 'STATE', 'RX_ERR', 'RX_DRP', 'RX_OVR', 'TX_ERR', 'TX_DRP', 'TX_OVR']
header_fec_only = ['IFACE', 'STATE', 'FEC_CORR', 'FEC_UNCORR', 'FEC_SYMBOL_ERR', 'FEC_PRE_BER',
                   'FEC_POST_BER', 'FEC_PRE_BER_MAX', 'FLR(O)', 'FLR(P) (Accuracy)', 'FEC_MAX_T']
header_fec_hist_only = ['IFACE', 'BIN0', 'BIN1', 'BIN2', 'BIN3', 'BIN4', 'BIN5', 'BIN6', 'BIN7',
                        'BIN8', 'BIN9', 'BIN10', 'BIN11', 'BIN12', 'BIN13', 'BIN14', 'BIN15']
header_rates_only = ['IFACE', 'STATE', 'RX_OK', 'RX_BPS', 'RX_PPS', 'RX_UTIL', 'TX_OK', 'TX_BPS', 'TX_PPS', 'TX_UTIL']
header_trim_only = ['IFACE', 'STATE', 'TRIM_PKTS', 'TRIM_TX_PKTS', 'TRIM_DRP_PKTS']

rates_key_list = ['RX_BPS', 'RX_PPS', 'RX_UTIL', 'TX_BPS', 'TX_PPS', 'TX_UTIL', 'FEC_PRE_BER',
                  'FEC_POST_BER', 'FEC_PRE_BER_MAX', 'FEC_FLR', 'FEC_FLR_PREDICTED', 'FEC_FLR_R_SQUARED', 'FEC_MAX_T']
ratestat_fields = ("rx_bps",  "rx_pps", "rx_util", "tx_bps", "tx_pps", "tx_util", "fec_pre_ber", "fec_post_ber",
                   "fec_pre_ber_max", "fec_flr", "fec_flr_predicted", "fec_flr_r_squared", "fec_max_t")
RateStats = namedtuple("RateStats", ratestat_fields)

"""
The order and count of statistics mentioned below needs to be in sync with the values in portstat script
So, any fields added/deleted in here should be reflected in portstat script also
"""
wred_green_pkt_stat_capable = "false"
wred_yellow_pkt_stat_capable = "false"
wred_red_pkt_stat_capable = "false"
wred_total_pkt_stat_capable = "false"
is_wred_stats_reqd = True


counter_bucket_dict = {
        0: ['SAI_PORT_STAT_IF_IN_UCAST_PKTS', 'SAI_PORT_STAT_IF_IN_NON_UCAST_PKTS'],
        1: ['SAI_PORT_STAT_IF_IN_ERRORS'],
        2: ['SAI_PORT_STAT_IF_IN_DISCARDS'],
        3: ['SAI_PORT_STAT_ETHER_RX_OVERSIZE_PKTS'],
        4: ['SAI_PORT_STAT_IF_OUT_UCAST_PKTS', 'SAI_PORT_STAT_IF_OUT_NON_UCAST_PKTS'],
        5: ['SAI_PORT_STAT_IF_OUT_ERRORS'],
        6: ['SAI_PORT_STAT_IF_OUT_DISCARDS'],
        7: ['SAI_PORT_STAT_ETHER_TX_OVERSIZE_PKTS'],
        8: ['SAI_PORT_STAT_IF_IN_OCTETS'],
        9: ['SAI_PORT_STAT_IF_OUT_OCTETS'],
        10: ['SAI_PORT_STAT_ETHER_IN_PKTS_64_OCTETS'],
        11: ['SAI_PORT_STAT_ETHER_IN_PKTS_65_TO_127_OCTETS'],
        12: ['SAI_PORT_STAT_ETHER_IN_PKTS_128_TO_255_OCTETS'],
        13: ['SAI_PORT_STAT_ETHER_IN_PKTS_256_TO_511_OCTETS'],
        14: ['SAI_PORT_STAT_ETHER_IN_PKTS_512_TO_1023_OCTETS'],
        15: ['SAI_PORT_STAT_ETHER_IN_PKTS_1024_TO_1518_OCTETS'],
        16: ['SAI_PORT_STAT_ETHER_IN_PKTS_1519_TO_2047_OCTETS'],
        17: ['SAI_PORT_STAT_ETHER_IN_PKTS_2048_TO_4095_OCTETS'],
        18: ['SAI_PORT_STAT_ETHER_IN_PKTS_4096_TO_9216_OCTETS'],
        19: ['SAI_PORT_STAT_ETHER_IN_PKTS_9217_TO_16383_OCTETS'],
        20: ['SAI_PORT_STAT_IF_IN_UCAST_PKTS'],
        21: ['SAI_PORT_STAT_IF_IN_MULTICAST_PKTS'],
        22: ['SAI_PORT_STAT_IF_IN_BROADCAST_PKTS'],
        23: ['SAI_PORT_STAT_IF_IN_UCAST_PKTS', 'SAI_PORT_STAT_IF_IN_MULTICAST_PKTS',
             'SAI_PORT_STAT_IF_IN_BROADCAST_PKTS'],
        24: ['SAI_PORT_STAT_ETHER_OUT_PKTS_64_OCTETS'],
        25: ['SAI_PORT_STAT_ETHER_OUT_PKTS_65_TO_127_OCTETS'],
        26: ['SAI_PORT_STAT_ETHER_OUT_PKTS_128_TO_255_OCTETS'],
        27: ['SAI_PORT_STAT_ETHER_OUT_PKTS_256_TO_511_OCTETS'],
        28: ['SAI_PORT_STAT_ETHER_OUT_PKTS_512_TO_1023_OCTETS'],
        29: ['SAI_PORT_STAT_ETHER_OUT_PKTS_1024_TO_1518_OCTETS'],
        30: ['SAI_PORT_STAT_ETHER_OUT_PKTS_1519_TO_2047_OCTETS'],
        31: ['SAI_PORT_STAT_ETHER_OUT_PKTS_2048_TO_4095_OCTETS'],
        32: ['SAI_PORT_STAT_ETHER_OUT_PKTS_4096_TO_9216_OCTETS'],
        33: ['SAI_PORT_STAT_ETHER_OUT_PKTS_9217_TO_16383_OCTETS'],
        34: ['SAI_PORT_STAT_IF_OUT_UCAST_PKTS'],
        35: ['SAI_PORT_STAT_IF_OUT_MULTICAST_PKTS'],
        36: ['SAI_PORT_STAT_IF_OUT_BROADCAST_PKTS'],
        37: ['SAI_PORT_STAT_IF_OUT_UCAST_PKTS', 'SAI_PORT_STAT_IF_OUT_MULTICAST_PKTS',
             'SAI_PORT_STAT_IF_OUT_BROADCAST_PKTS'],
        38: ['SAI_PORT_STAT_ETHER_STATS_JABBERS'],
        39: ['SAI_PORT_STAT_ETHER_STATS_FRAGMENTS'],
        40: ['SAI_PORT_STAT_ETHER_STATS_UNDERSIZE_PKTS'],
        41: ['SAI_PORT_STAT_IP_IN_RECEIVES'],
        42: ['SAI_PORT_STAT_IF_IN_FEC_CORRECTABLE_FRAMES'],
        43: ['SAI_PORT_STAT_IF_IN_FEC_NOT_CORRECTABLE_FRAMES'],
        44: ['SAI_PORT_STAT_IF_IN_FEC_SYMBOL_ERRORS'],
        45: ['SAI_PORT_STAT_GREEN_WRED_DROPPED_PACKETS'],
        46: ['SAI_PORT_STAT_YELLOW_WRED_DROPPED_PACKETS'],
        47: ['SAI_PORT_STAT_RED_WRED_DROPPED_PACKETS'],
        48: ['SAI_PORT_STAT_WRED_DROPPED_PACKETS'],
        49: ['SAI_PORT_STAT_TRIM_PACKETS'],
        50: ['SAI_PORT_STAT_TX_TRIM_PACKETS'],
        51: ['SAI_PORT_STAT_DROPPED_TRIM_PACKETS'],
        52: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S0'],
        53: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S1'],
        54: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S2'],
        55: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S3'],
        56: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S4'],
        57: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S5'],
        58: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S6'],
        59: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S7'],
        60: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S8'],
        61: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S9'],
        62: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S10'],
        63: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S11'],
        64: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S12'],
        65: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S13'],
        66: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S14'],
        67: ['SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S15'],
}

STATUS_NA = 'N/A'

RATES_TABLE_PREFIX = "RATES:"

COUNTER_TABLE_PREFIX = "COUNTERS:"
COUNTERS_PORT_NAME_MAP = "COUNTERS_PORT_NAME_MAP"

PORT_STATUS_TABLE_PREFIX = "PORT_TABLE:"
PORT_STATE_TABLE_PREFIX = "PORT_TABLE|"
PORT_OPER_STATUS_FIELD = "oper_status"
PORT_ADMIN_STATUS_FIELD = "admin_status"
PORT_STATUS_VALUE_UP = 'UP'
PORT_STATUS_VALUE_DOWN = 'DOWN'
PORT_SPEED_FIELD = "speed"

PORT_STATE_UP = 'U'
PORT_STATE_DOWN = 'D'
PORT_STATE_DISABLED = 'X'

LINECARD_PORT_STAT_TABLE = 'LINECARD_PORT_STAT_TABLE'
LINECARD_PORT_STAT_MARK_TABLE = 'LINECARD_PORT_STAT_MARK_TABLE'
CHASSIS_MIDPLANE_INFO_TABLE = 'CHASSIS_MIDPLANE_TABLE'


def intfsorted(intf_list):
    """
        Sort the interfaces list purely based on digital indexes
    """
    def sort_key(intf):
        return [int(i) for i in re.findall(r'\d+', intf)]

    return sorted(intf_list, key=sort_key)


def is_non_zero(value):
    """
        Check if the value is non-zero.
    """
    if value == STATUS_NA:
        return False
    if type(value) is str and ',' in value:
        value = value.replace(',', '')

    return int(value) != 0


class Portstat(object):
    def __init__(self, namespace, display_option):
        self.db = None
        self.namespace = namespace
        self.display_option = display_option
        self.multi_asic = multi_asic_util.MultiAsic(display_option, namespace)
        if device_info.is_supervisor():
            self.db = SonicV2Connector(use_unix_socket_path=False)
            self.db.connect(self.db.CHASSIS_STATE_DB, False)
        self.db_clients = {}
        self.sorted = natsorted

    def get_cnstat_dict(self):
        self.cnstat_dict = OrderedDict()
        self.cnstat_dict['time'] = datetime.datetime.now()
        self.ratestat_dict = OrderedDict()
        if device_info.is_supervisor():
            if device_info.is_voq_chassis() or (self.namespace is None and self.display_option != 'all'):
                self.collect_stat_from_lc()
                self.sorted = intfsorted
            else:
                self.collect_stat()
                self.sorted = natsorted
        else:
            self.collect_stat()
        return self.cnstat_dict, self.ratestat_dict

    def collect_stat_from_lc(self):
        # Retrieve the current counter values from all LCs

        # Clear stale records
        self.db.delete_all_by_pattern(self.db.CHASSIS_STATE_DB, LINECARD_PORT_STAT_TABLE + "*")
        self.db.delete_all_by_pattern(self.db.CHASSIS_STATE_DB, LINECARD_PORT_STAT_MARK_TABLE + "*")

        # Check how many linecards are connected
        tempdb = SonicV2Connector(use_unix_socket_path=False)
        tempdb.connect(tempdb.STATE_DB, False)
        linecard_midplane_keys = tempdb.keys(tempdb.STATE_DB, CHASSIS_MIDPLANE_INFO_TABLE + "*")
        lc_count = 0
        if not linecard_midplane_keys:
            # LC has not published it's Counter which could be due to chassis_port_counter_monitor.service not running
            print("No linecards are connected!")
            return
        else:
            for key in linecard_midplane_keys:
                linecard_status = tempdb.get(tempdb.STATE_DB, key, "access")
                if linecard_status == "True":
                    lc_count += 1

        # Notify the Linecards to publish their counter values instantly
        self.db.set(self.db.CHASSIS_STATE_DB, "GET_LINECARD_COUNTER|pull", "enable", "true")
        time.sleep(2)

        # Check if all LCs have published counters
        linecard_names = self.db.keys(self.db.CHASSIS_STATE_DB, LINECARD_PORT_STAT_MARK_TABLE + "*")
        linecard_port_aliases = self.db.keys(self.db.CHASSIS_STATE_DB, LINECARD_PORT_STAT_TABLE + "*")
        if not linecard_port_aliases:
            # LC has not published it's Counter which could be due to chassis_port_counter_monitor.service not running
            print("Linecard Counter Table is not available.")
            return
        if len(linecard_names) != lc_count:
            print("Not all linecards have published their counter values.")
            return

        # Create the dictornaries to store the counter values
        cnstat_dict = OrderedDict()
        cnstat_dict['time'] = datetime.datetime.now()
        ratestat_dict = OrderedDict()

        # Get the counter values from CHASSIS_STATE_DB
        for key in linecard_port_aliases:
            rx_ok = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_ok")
            rx_bps = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_bps")
            rx_pps = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_pps")
            rx_util = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_util")
            rx_err = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_err")
            rx_drop = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_drop")
            rx_ovr = self.db.get(self.db.CHASSIS_STATE_DB, key, "rx_ovr")
            tx_ok = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_ok")
            tx_bps = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_bps")
            tx_pps = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_pps")
            tx_util = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_util")
            tx_err = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_err")
            tx_drop = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_drop")
            tx_ovr = self.db.get(self.db.CHASSIS_STATE_DB, key, "tx_ovr")
            fec_pre_ber = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_pre_ber")
            fec_post_ber = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_post_ber")
            fec_pre_ber_max = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_pre_ber_max")
            fec_flr = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_flr")
            fec_flr_predicted = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_flr_predicted")
            fec_flr_r_squared = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_flr_r_squared")
            fec_max_t = self.db.get(self.db.CHASSIS_STATE_DB, key, "fec_max_t")
            port_alias = key.split("|")[-1]
            cnstat_dict[port_alias] = NStats._make([rx_ok, rx_err, rx_drop, rx_ovr, tx_ok, tx_err, tx_drop, tx_ovr] +
                                                   [STATUS_NA] * (len(NStats._fields) - 8))._asdict()
            ratestat_dict[port_alias] = RateStats._make([rx_bps, rx_pps, rx_util, tx_bps,
                                                        tx_pps, tx_util, fec_pre_ber, fec_post_ber, fec_pre_ber_max,
                                                        fec_flr, fec_flr_predicted, fec_flr_r_squared, fec_max_t])
        self.cnstat_dict.update(cnstat_dict)
        self.ratestat_dict.update(ratestat_dict)

    @multi_asic_util.run_on_multi_asic
    def collect_stat(self):
        """
        Collect the statisitics from all the asics present on the
        device and store in a dict
        """

        global wred_green_pkt_stat_capable
        global wred_yellow_pkt_stat_capable
        global wred_red_pkt_stat_capable
        global wred_total_pkt_stat_capable
        global is_wred_stats_reqd

        wred_green_pkt_stat_capable = self.db.get(
            self.db.STATE_DB,
            "PORT_COUNTER_CAPABILITIES|WRED_ECN_PORT_WRED_GREEN_DROP_COUNTER",
            "isSupported")
        wred_yellow_pkt_stat_capable = self.db.get(
            self.db.STATE_DB,
            "PORT_COUNTER_CAPABILITIES|WRED_ECN_PORT_WRED_YELLOW_DROP_COUNTER",
            "isSupported")
        wred_red_pkt_stat_capable = self.db.get(
            self.db.STATE_DB,
            "PORT_COUNTER_CAPABILITIES|WRED_ECN_PORT_WRED_RED_DROP_COUNTER",
            "isSupported")
        wred_total_pkt_stat_capable = self.db.get(
            self.db.STATE_DB,
            "PORT_COUNTER_CAPABILITIES|WRED_ECN_PORT_WRED_TOTAL_DROP_COUNTER",
            "isSupported")

        # Remove the unsupported stats from the counter dict
        if (is_wred_stats_reqd is False) or (wred_green_pkt_stat_capable != "true"):
            if ('SAI_PORT_STAT_GREEN_WRED_DROPPED_PACKETS' in counter_bucket_dict.keys()):
                del counter_bucket_dict['SAI_PORT_STAT_GREEN_WRED_DROPPED_PACKETS']

        if (is_wred_stats_reqd is False) or (wred_yellow_pkt_stat_capable != "true"):
            if ('SAI_PORT_STAT_YELLOW_WRED_DROPPED_PACKETS' in counter_bucket_dict.keys()):
                del counter_bucket_dict['SAI_PORT_STAT_YELLOW_WRED_DROPPED_PACKETS']

        if (is_wred_stats_reqd is False) or (wred_red_pkt_stat_capable != "true"):
            if ('SAI_PORT_STAT_RED_WRED_DROPPED_PACKETS' in counter_bucket_dict.keys()):
                del counter_bucket_dict['SAI_PORT_STAT_RED_WRED_DROPPED_PACKETS']

        if (is_wred_stats_reqd is False) or (wred_total_pkt_stat_capable != "true"):
            if ('SAI_PORT_STAT_WRED_DROPPED_PACKETS' in counter_bucket_dict.keys()):
                del counter_bucket_dict['SAI_PORT_STAT_WRED_DROPPED_PACKETS']

        cnstat_dict, ratestat_dict = self.get_cnstat()
        self.cnstat_dict.update(cnstat_dict)
        self.ratestat_dict.update(ratestat_dict)

    def get_cnstat(self):
        """
            Get the counters info from database.
        """
        def get_counters(port):
            """
                Get the counters from specific table.
            """
            fields = ["0"] * len(counter_bucket_dict)

            _, fvs = counter_table.get(PortCounter(), port)
            fvs = dict(fvs)
            for pos, cntr_list in counter_bucket_dict.items():
                for counter_name in cntr_list:
                    if counter_name not in fvs:
                        fields[pos] = STATUS_NA
                    elif fields[pos] != STATUS_NA:
                        fields[pos] = str(int(fields[pos]) + int(float(fvs[counter_name])))

            cntr = NStats._make(fields)._asdict()
            return cntr

        def get_rates(table_id):
            """
                Get the rates from specific table.
            """
            fields = ["0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]
            for pos, name in enumerate(rates_key_list):
                full_table_id = RATES_TABLE_PREFIX + table_id
                counter_data = self.db.get(self.db.COUNTERS_DB, full_table_id, name)
                if counter_data is None:
                    fields[pos] = STATUS_NA
                elif fields[pos] != STATUS_NA:
                    fields[pos] = float(counter_data)
            cntr = RateStats._make(fields)
            return cntr

        # Get the info from database
        counter_port_name_map = self.db.get_all(self.db.COUNTERS_DB, COUNTERS_PORT_NAME_MAP)
        # Build a dictionary of the stats
        cnstat_dict = OrderedDict()
        cnstat_dict['time'] = datetime.datetime.now()
        ratestat_dict = OrderedDict()
        counter_table = CounterTable(self.db.get_redis_client(self.db.COUNTERS_DB))
        if counter_port_name_map is None:
            return cnstat_dict, ratestat_dict
        for port in self.sorted(counter_port_name_map):
            port_name = port.split(":")[0]
            if self.multi_asic.skip_display(constants.PORT_OBJ, port_name):
                continue
            cnstat_dict[port] = get_counters(port)
            ratestat_dict[port] = get_rates(counter_port_name_map[port])
        return cnstat_dict, ratestat_dict

    def get_port_speed(self, port_name):
        """
            Get the port speed
        """
        # Get speed from APPL_DB
        state_db_table_id = PORT_STATE_TABLE_PREFIX + port_name
        app_db_table_id = PORT_STATUS_TABLE_PREFIX + port_name
        for ns in self.multi_asic.get_ns_list_based_on_options():
            self.db = self.get_db_client(ns)
            speed = self.db.get(self.db.STATE_DB, state_db_table_id, PORT_SPEED_FIELD)
            oper_status = self.db.get(self.db.APPL_DB, app_db_table_id, PORT_OPER_STATUS_FIELD)
            if speed is None or speed == STATUS_NA or oper_status != "up":
                speed = self.db.get(self.db.APPL_DB, app_db_table_id, PORT_SPEED_FIELD)
            if speed is not None:
                return int(speed)
        return STATUS_NA

    def get_db_client(self, ns):
        if not self.db_clients.get(ns):
            self.db_clients[ns] = multi_asic.connect_to_all_dbs_for_ns(ns)
        return self.db_clients[ns]

    def get_port_state(self, port_name):
        """
            Get the port state
        """
        if device_info.is_supervisor():
            if device_info.is_voq_chassis() or (self.namespace is None and self.display_option != 'all'):
                self.db.connect(self.db.CHASSIS_STATE_DB, False)
                return self.db.get(self.db.CHASSIS_STATE_DB, LINECARD_PORT_STAT_TABLE + "|" + port_name, "state")
            else:
                pass

        full_table_id = PORT_STATUS_TABLE_PREFIX + port_name
        for ns in self.multi_asic.get_ns_list_based_on_options():
            self.db = self.get_db_client(ns)
            admin_state = self.db.get(self.db.APPL_DB, full_table_id, PORT_ADMIN_STATUS_FIELD)
            oper_state = self.db.get(self.db.APPL_DB, full_table_id, PORT_OPER_STATUS_FIELD)

            if admin_state is None or oper_state is None:
                continue
            if admin_state.upper() == PORT_STATUS_VALUE_DOWN:
                return PORT_STATE_DISABLED
            elif admin_state.upper() == PORT_STATUS_VALUE_UP and oper_state.upper() == PORT_STATUS_VALUE_UP:
                return PORT_STATE_UP
            elif admin_state.upper() == PORT_STATUS_VALUE_UP and oper_state.upper() == PORT_STATUS_VALUE_DOWN:
                return PORT_STATE_DOWN
            else:
                return STATUS_NA
        return STATUS_NA

    def cnstat_intf_diff_print(self, cnstat_new_dict, cnstat_old_dict, intf_list):
        """
            Print the difference between two cnstat results for interface.
        """

        for key in self.sorted(cnstat_new_dict.keys()):
            cntr = cnstat_new_dict.get(key)
            if key == 'time':
                continue

            if key in cnstat_old_dict:
                old_cntr = cnstat_old_dict.get(key)
            else:
                old_cntr = NStats._make([0] * len(counter_bucket_dict))._asdict()

            if intf_list and key not in intf_list:
                continue

            print("Packets Received 64 Octets..................... {}".format(ns_diff(cntr['rx_64'],
                                                                                      old_cntr['rx_64'])))
            print("Packets Received 65-127 Octets................. {}".format(ns_diff(cntr['rx_65_127'],
                                                                                      old_cntr['rx_65_127'])))
            print("Packets Received 128-255 Octets................ {}".format(ns_diff(cntr['rx_128_255'],
                                                                                      old_cntr['rx_128_255'])))
            print("Packets Received 256-511 Octets................ {}".format(ns_diff(cntr['rx_256_511'],
                                                                                      old_cntr['rx_256_511'])))
            print("Packets Received 512-1023 Octets............... {}".format(ns_diff(cntr['rx_512_1023'],
                                                                                      old_cntr['rx_512_1023'])))
            print("Packets Received 1024-1518 Octets.............. {}".format(ns_diff(cntr['rx_1024_1518'],
                                                                                      old_cntr['rx_1024_1518'])))
            print("Packets Received 1519-2047 Octets.............. {}".format(ns_diff(cntr['rx_1519_2047'],
                                                                                      old_cntr['rx_1519_2047'])))
            print("Packets Received 2048-4095 Octets.............. {}".format(ns_diff(cntr['rx_2048_4095'],
                                                                                      old_cntr['rx_2048_4095'])))
            print("Packets Received 4096-9216 Octets.............. {}".format(ns_diff(cntr['rx_4096_9216'],
                                                                                      old_cntr['rx_4096_9216'])))
            print("Packets Received 9217-16383 Octets............. {}".format(ns_diff(cntr['rx_9217_16383'],
                                                                                      old_cntr['rx_9217_16383'])))

            print("")
            print("Total Packets Received Without Errors.......... {}".format(ns_diff(cntr['rx_all'],
                                                                                      old_cntr['rx_all'])))
            print("Unicast Packets Received....................... {}".format(ns_diff(cntr['rx_uca'],
                                                                                      old_cntr['rx_uca'])))
            print("Multicast Packets Received..................... {}".format(ns_diff(cntr['rx_mca'],
                                                                                      old_cntr['rx_mca'])))
            print("Broadcast Packets Received..................... {}".format(ns_diff(cntr['rx_bca'],
                                                                                      old_cntr['rx_bca'])))

            print("")
            print("Jabbers Received............................... {}".format(ns_diff(cntr['rx_jbr'],
                                                                                      old_cntr['rx_jbr'])))
            print("Fragments Received............................. {}".format(ns_diff(cntr['rx_frag'],
                                                                                      old_cntr['rx_frag'])))
            print("Undersize Received............................. {}".format(ns_diff(cntr['rx_usize'],
                                                                                      old_cntr['rx_usize'])))
            print("Overruns Received.............................. {}".format(ns_diff(cntr["rx_ovrrun"],
                                                                                      old_cntr["rx_ovrrun"])))

            print("")
            print("Packets Transmitted 64 Octets.................. {}".format(ns_diff(cntr['tx_64'],
                                                                                      old_cntr['tx_64'])))
            print("Packets Transmitted 65-127 Octets.............. {}".format(ns_diff(cntr['tx_65_127'],
                                                                                      old_cntr['tx_65_127'])))
            print("Packets Transmitted 128-255 Octets............. {}".format(ns_diff(cntr['tx_128_255'],
                                                                                      old_cntr['tx_128_255'])))
            print("Packets Transmitted 256-511 Octets............. {}".format(ns_diff(cntr['tx_256_511'],
                                                                                      old_cntr['tx_256_511'])))
            print("Packets Transmitted 512-1023 Octets............ {}".format(ns_diff(cntr['tx_512_1023'],
                                                                                      old_cntr['tx_512_1023'])))
            print("Packets Transmitted 1024-1518 Octets........... {}".format(ns_diff(cntr['tx_1024_1518'],
                                                                                      old_cntr['tx_1024_1518'])))
            print("Packets Transmitted 1519-2047 Octets........... {}".format(ns_diff(cntr['tx_1519_2047'],
                                                                                      old_cntr['tx_1519_2047'])))
            print("Packets Transmitted 2048-4095 Octets........... {}".format(ns_diff(cntr['tx_2048_4095'],
                                                                                      old_cntr['tx_2048_4095'])))
            print("Packets Transmitted 4096-9216 Octets........... {}".format(ns_diff(cntr['tx_4096_9216'],
                                                                                      old_cntr['tx_4096_9216'])))
            print("Packets Transmitted 9217-16383 Octets.......... {}".format(ns_diff(cntr['tx_9217_16383'],
                                                                                      old_cntr['tx_9217_16383'])))

            print("")
            print("Total Packets Transmitted Successfully......... {}".format(ns_diff(cntr['tx_all'],
                                                                                      old_cntr['tx_all'])))
            print("Unicast Packets Transmitted.................... {}".format(ns_diff(cntr['tx_uca'],
                                                                                      old_cntr['tx_uca'])))
            print("Multicast Packets Transmitted.................. {}".format(ns_diff(cntr['tx_mca'],
                                                                                      old_cntr['tx_mca'])))
            print("Broadcast Packets Transmitted.................. {}".format(ns_diff(cntr['tx_bca'],
                                                                                      old_cntr['tx_bca'])))

            if (
                wred_green_pkt_stat_capable == "true"
                or wred_yellow_pkt_stat_capable == "true"
                or wred_red_pkt_stat_capable == "true"
                or wred_total_pkt_stat_capable == "true"
            ):
                print("")
                if wred_green_pkt_stat_capable == "true":
                    print(
                        "WRED Green Dropped Packets..................... {}".format(
                            ns_diff(cntr['wred_grn_drp_pkt'], old_cntr['wred_grn_drp_pkt'])
                        )
                    )

                if wred_yellow_pkt_stat_capable == "true":
                    print(
                        "WRED Yellow Dropped Packets.................... {}".format(
                            ns_diff(cntr['wred_ylw_drp_pkt'], old_cntr['wred_ylw_drp_pkt'])
                        )
                    )

                if wred_red_pkt_stat_capable == "true":
                    print(
                        "WRED Red Dropped Packets....................... {}".format(
                            ns_diff(cntr['wred_red_drp_pkt'], old_cntr['wred_red_drp_pkt'])
                        )
                    )

                if wred_total_pkt_stat_capable == "true":
                    print(
                        "WRED Total Dropped Packets..................... {}".format(
                            ns_diff(cntr['wred_tot_drp_pkt'], old_cntr['wred_tot_drp_pkt'])
                        )
                    )
                print("")

            print("Trimmed Packets................................ {}".format(
                ns_diff(cntr['trim'], old_cntr['trim'])
            ))
            print("Trimmed Sent Packets........................... {}".format(
                ns_diff(cntr['trim_sent'], old_cntr['trim_sent'])
            ))
            print("Trimmed Dropped Packets........................ {}".format(
                ns_diff(cntr['trim_drop'], old_cntr['trim_drop'], raw=True)
            ))
            print("")

            print("Time Since Counters Last Cleared............... " + str(cnstat_old_dict.get('time')))

    def cnstat_diff_print(self, cnstat_new_dict, cnstat_old_dict,
                          ratestat_dict, intf_list, use_json,
                          print_all, errors_only, fec_stats_only,
                          rates_only, trim_stats_only, fec_hist_only, detail=False, nonzero=False):
        """
            Print the difference between two cnstat results.
        """

        if intf_list and detail:
            self.cnstat_intf_diff_print(cnstat_new_dict, cnstat_old_dict, intf_list)
            return None

        table = []
        header = None

        for key in self.sorted(cnstat_new_dict.keys()):
            cntr = cnstat_new_dict.get(key)
            if key == 'time':
                continue
            old_cntr = None
            if key in cnstat_old_dict:
                old_cntr = cnstat_old_dict.get(key)
            else:
                old_cntr = NStats._make([0] * len(counter_bucket_dict))._asdict()

            rates = ratestat_dict.get(key, RateStats._make([STATUS_NA] * len(ratestat_fields)))

            if intf_list and key not in intf_list:
                continue
            port_speed = self.get_port_speed(key)

            if print_all:
                header = header_all

                if not nonzero or is_non_zero(ns_diff(cntr["rx_ok"], old_cntr["rx_ok"])) or \
                   is_non_zero(ns_diff(cntr["tx_ok"], old_cntr["tx_ok"])) or \
                   is_non_zero(ns_diff(cntr["rx_err"], old_cntr["rx_err"])) or \
                   is_non_zero(ns_diff(cntr["tx_err"], old_cntr["tx_err"])) or \
                   is_non_zero(ns_diff(cntr["rx_drop"], old_cntr["rx_drop"])) or \
                   is_non_zero(ns_diff(cntr["tx_drop"], old_cntr["tx_drop"])) or \
                   is_non_zero(ns_diff(cntr["rx_ovr"], old_cntr["rx_ovr"])) or \
                   is_non_zero(ns_diff(cntr["tx_ovr"], old_cntr["tx_ovr"])):
                    table.append((key, self.get_port_state(key),
                                  ns_diff(cntr["rx_ok"], old_cntr["rx_ok"]),
                                  format_brate(rates.rx_bps),
                                  format_prate(rates.rx_pps),
                                  format_util(rates.rx_bps, port_speed)
                                  if rates.rx_util == STATUS_NA else format_util_directly(rates.rx_util),
                                  ns_diff(cntr["rx_err"], old_cntr["rx_err"]),
                                  ns_diff(cntr["rx_drop"], old_cntr["rx_drop"]),
                                  ns_diff(cntr["rx_ovr"], old_cntr["rx_ovr"]),
                                  ns_diff(cntr["tx_ok"], old_cntr["tx_ok"]),
                                  format_brate(rates.tx_bps),
                                  format_prate(rates.tx_pps),
                                  format_util(rates.tx_bps, port_speed)
                                  if rates.tx_util == STATUS_NA else format_util_directly(rates.tx_util),
                                  ns_diff(cntr["tx_err"], old_cntr["tx_err"]),
                                  ns_diff(cntr["tx_drop"], old_cntr["tx_drop"]),
                                  ns_diff(cntr["tx_ovr"], old_cntr["tx_ovr"]),
                                  ns_diff(cntr["trim"], old_cntr["trim"]),
                                  ns_diff(cntr["trim_sent"], old_cntr["trim_sent"]),
                                  ns_diff(cntr["trim_drop"], old_cntr["trim_drop"], raw=True)))
            elif errors_only:
                header = header_errors_only

                if not nonzero or is_non_zero(ns_diff(cntr["rx_err"], old_cntr["rx_err"])) or \
                   is_non_zero(ns_diff(cntr["tx_err"], old_cntr["tx_err"])) or \
                   is_non_zero(ns_diff(cntr["rx_drop"], old_cntr["rx_drop"])) or \
                   is_non_zero(ns_diff(cntr["tx_drop"], old_cntr["tx_drop"])) or \
                   is_non_zero(ns_diff(cntr["rx_ovr"], old_cntr["rx_ovr"])) or \
                   is_non_zero(ns_diff(cntr["tx_ovr"], old_cntr["tx_ovr"])):
                    table.append((key, self.get_port_state(key),
                                  ns_diff(cntr["rx_err"], old_cntr["rx_err"]),
                                  ns_diff(cntr["rx_drop"], old_cntr["rx_drop"]),
                                  ns_diff(cntr["rx_ovr"], old_cntr["rx_ovr"]),
                                  ns_diff(cntr["tx_err"], old_cntr["tx_err"]),
                                  ns_diff(cntr["tx_drop"], old_cntr["tx_drop"]),
                                  ns_diff(cntr["tx_ovr"], old_cntr["tx_ovr"])))
            elif fec_stats_only:
                header = header_fec_only

                if not nonzero or is_non_zero(ns_diff(cntr['fec_corr'], old_cntr['fec_corr'])) or \
                   is_non_zero(ns_diff(cntr['fec_uncorr'], old_cntr['fec_uncorr'])) or \
                   is_non_zero(ns_diff(cntr['fec_symbol_err'], old_cntr['fec_symbol_err'])):
                    table.append((key, self.get_port_state(key),
                                  ns_diff(cntr['fec_corr'], old_cntr['fec_corr']),
                                  ns_diff(cntr['fec_uncorr'], old_cntr['fec_uncorr']),
                                  ns_diff(cntr['fec_symbol_err'], old_cntr['fec_symbol_err']),
                                  format_fec_ber(rates.fec_pre_ber),
                                  format_fec_ber(rates.fec_post_ber),
                                  format_fec_ber(rates.fec_pre_ber_max),
                                  format_fec_flr(rates.fec_flr),
                                  format_fec_flr_predicted(rates.fec_flr_predicted,
                                                           rates.fec_flr_r_squared),
                                  rates.fec_max_t))
            elif fec_hist_only:
                header = header_fec_hist_only

                table.append((key, ns_diff(cntr['fec_bin0'], old_cntr['fec_bin0']),
                              ns_diff(cntr['fec_bin1'], old_cntr['fec_bin1']),
                              ns_diff(cntr['fec_bin2'], old_cntr['fec_bin2']),
                              ns_diff(cntr['fec_bin3'], old_cntr['fec_bin3']),
                              ns_diff(cntr['fec_bin4'], old_cntr['fec_bin4']),
                              ns_diff(cntr['fec_bin5'], old_cntr['fec_bin5']),
                              ns_diff(cntr['fec_bin6'], old_cntr['fec_bin6']),
                              ns_diff(cntr['fec_bin7'], old_cntr['fec_bin7']),
                              ns_diff(cntr['fec_bin8'], old_cntr['fec_bin8']),
                              ns_diff(cntr['fec_bin9'], old_cntr['fec_bin9']),
                              ns_diff(cntr['fec_bin10'], old_cntr['fec_bin10']),
                              ns_diff(cntr['fec_bin11'], old_cntr['fec_bin11']),
                              ns_diff(cntr['fec_bin12'], old_cntr['fec_bin12']),
                              ns_diff(cntr['fec_bin13'], old_cntr['fec_bin13']),
                              ns_diff(cntr['fec_bin14'], old_cntr['fec_bin14']),
                              ns_diff(cntr['fec_bin15'], old_cntr['fec_bin15'])))

            elif rates_only:
                header = header_rates_only

                if not nonzero or is_non_zero(ns_diff(cntr["rx_ok"], old_cntr["rx_ok"])) or \
                   is_non_zero(ns_diff(cntr["tx_ok"], old_cntr["tx_ok"])):
                    table.append((key,
                                  self.get_port_state(key),
                                  ns_diff(cntr["rx_ok"], old_cntr["rx_ok"]),
                                  format_brate(rates.rx_bps),
                                  format_prate(rates.rx_pps),
                                  format_util(rates.rx_bps, port_speed)
                                  if rates.rx_util == STATUS_NA else format_util_directly(rates.rx_util),
                                  ns_diff(cntr["tx_ok"], old_cntr["tx_ok"]),
                                  format_brate(rates.tx_bps),
                                  format_prate(rates.tx_pps),
                                  format_util(rates.tx_bps, port_speed)
                                  if rates.tx_util == STATUS_NA else format_util_directly(rates.tx_util)))
            elif trim_stats_only:  # Packet Trimming related statistics
                header = header_trim_only

                if not nonzero or is_non_zero(ns_diff(cntr['trim'], old_cntr['trim'])):
                    table.append((key, self.get_port_state(key),
                                  ns_diff(cntr["trim"], old_cntr["trim"]),
                                  ns_diff(cntr["trim_sent"], old_cntr["trim_sent"]),
                                  ns_diff(cntr["trim_drop"], old_cntr["trim_drop"], raw=True)))
            else:
                header = header_std

                if not nonzero or is_non_zero(ns_diff(cntr["rx_ok"], old_cntr["rx_ok"])) or \
                   is_non_zero(ns_diff(cntr["tx_ok"], old_cntr["tx_ok"])) or \
                   is_non_zero(ns_diff(cntr["rx_err"], old_cntr["rx_err"])) or \
                   is_non_zero(ns_diff(cntr["tx_err"], old_cntr["tx_err"])) or \
                   is_non_zero(ns_diff(cntr["rx_drop"], old_cntr["rx_drop"])) or \
                   is_non_zero(ns_diff(cntr["tx_drop"], old_cntr["tx_drop"])) or \
                   is_non_zero(ns_diff(cntr["rx_ovr"], old_cntr["rx_ovr"])) or \
                   is_non_zero(ns_diff(cntr["tx_ovr"], old_cntr["tx_ovr"])):
                    table.append((key,
                                  self.get_port_state(key),
                                  ns_diff(cntr["rx_ok"], old_cntr["rx_ok"]),
                                  format_brate(rates.rx_bps),
                                  format_util(rates.rx_bps, port_speed)
                                  if rates.rx_util == STATUS_NA else format_util_directly(rates.rx_util),
                                  ns_diff(cntr["rx_err"], old_cntr["rx_err"]),
                                  ns_diff(cntr["rx_drop"], old_cntr["rx_drop"]),
                                  ns_diff(cntr["rx_ovr"], old_cntr["rx_ovr"]),
                                  ns_diff(cntr["tx_ok"], old_cntr["tx_ok"]),
                                  format_brate(rates.tx_bps),
                                  format_util(rates.tx_bps, port_speed)
                                  if rates.tx_util == STATUS_NA else format_util_directly(rates.tx_util),
                                  ns_diff(cntr["tx_err"], old_cntr["tx_err"]),
                                  ns_diff(cntr["tx_drop"], old_cntr["tx_drop"]),
                                  ns_diff(cntr["tx_ovr"], old_cntr["tx_ovr"])))

        if table:
            if use_json:
                print(table_as_json(table, header))
            else:
                print(tabulate(table, header, tablefmt='simple', stralign='right'))
        elif nonzero:
            print("No non-zero statistics found for the specified interfaces.")

        if device_info.is_voq_chassis():
            return
        elif (multi_asic.is_multi_asic() or device_info.is_packet_chassis()) and not use_json:
            print("\nReminder: Please execute 'show interface counters -d all' to include internal links\n")
