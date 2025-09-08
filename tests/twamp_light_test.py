import os
from click.testing import CliRunner
import pytest

from utilities_common.db import Db

import config.main as config
import show.main as show

from .utils import get_result_and_return_code
from unittest import mock
from mock import patch

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")


TL_SESSION_NAME = "session_name1"
TL_SRC_IP_PORT = "12.34.56.78:9876"
TL_SRC_IP_NO_PORT = "12.34.56.78"
TL_DST_IP_PORT = "98.76.54.32:6789"
TL_DST_IP_NO_PORT = "98.76.54.32"
TL_SRC_IP_DFT_PORT = "12.34.56.78:862"
TL_DST_IP_DFT_PORT = "98.76.54.32:863"
TL_SRC_IP_PORT_INVLD = "12.34.56.78:999"
TL_DST_IP_PORT_INVLD = "98.76.54.32:666"
TL_MONITOR_TIME = "139"
TL_TX_INTERVAL = "100"
TL_TIMEOUT = "5"
TL_STATS_INTERVAL = "34567"
TL_PKT_CNT = "7890"
TL_STATS_INTERVAL_DFT = str(int(TL_PKT_CNT) * int(TL_TX_INTERVAL) + int(TL_TIMEOUT) * 1000)
TL_STATS_INTERVAL_CNTINU_MODE_DFT = str(int(TL_MONITOR_TIME) * 1000)

TL_CFGDB_KEY_PREFIX = "TWAMP_SESSION"
TL_CFGDB_MODE_STRING = "mode"
TL_CFGDB_MODE_VALULE = "LIGHT"
TL_CFGDB_ROLE_STRING = "role"
TL_CFGDB_ROLE_RFLT_VALULE = "REFLECTOR"
TL_CFGDB_ROLE_SNDR_VALULE = "SENDER"
TL_CFGDB_SRCIP_STRING = "src_ip"
TL_CFGDB_SRCIP_VALULE = "12.34.56.78"
TL_CFGDB_SRCPT_STRING = "src_udp_port"
TL_CFGDB_SRCPT_VALULE = "9876"
TL_CFGDB_RFLT_DFT_PT = "862"
TL_CFGDB_SEND_DFT_PT = "863"
TL_CFGDB_DSTIP_STRING = "dst_ip"
TL_CFGDB_DSTIP_VALULE = "98.76.54.32"
TL_CFGDB_DSTPT_STRING = "dst_udp_port"
TL_CFGDB_DSTPT_VALULE = "6789"
TL_CFGDB_STATS_INTVL_STRING = "statistics_interval"

show_twamp_light_with_no_session_info = \
    """Time unit: Monitor Time/Timeout in second; Tx Interval/Stats Interval in millisecond
TWAMP-Light Sender Sessions
Name    Status    Sender IP:PORT    Reflector IP:PORT    Packet Count    Monitor Time    Tx Interval    \
Stats Interval    Timeout
------  --------  ----------------  -------------------  --------------  --------------  -------------  \
----------------  ---------

TWAMP-Light Reflector Sessions
Name    Status    Sender IP:PORT    Reflector IP:PORT
------  --------  ----------------  -------------------
"""

show_twamp_light_with_session_for_VM1 = \
    """Time unit: Monitor Time/Timeout in second; Tx Interval/Stats Interval in millisecond
TWAMP-Light Sender Sessions
Name              Status    Sender IP:PORT    Reflector IP:PORT      Packet Count  Monitor Time      \
Tx Interval    Stats Interval    Timeout
----------------  --------  ----------------  -------------------  --------------  --------------  \
-------------  ----------------  ---------
SESSION_SEND_VM1  active    10.20.100.1:862   10.10.100.2:863                 100  -                         \
100             15000          5

TWAMP-Light Reflector Sessions
Name    Status    Sender IP:PORT    Reflector IP:PORT
------  --------  ----------------  -------------------
"""

show_twamp_light_with_session_info = \
    """Time unit: Monitor Time/Timeout in second; Tx Interval/Stats Interval in millisecond
TWAMP-Light Sender Sessions
Name              Status    Sender IP:PORT     Reflector IP:PORT      Packet Count  Monitor Time      \
Tx Interval    Stats Interval    Timeout
----------------  --------  -----------------  -------------------  --------------  --------------  \
-------------  ----------------  ---------
SESSION_SEND_VM1  active    10.20.100.1:862    10.10.100.2:863                 100  -                         \
100             15000          5
SESSION_SEND_VM2  active    192.168.50.3:1862  192.168.100.2:1863             2000  -                         \
200              1500          5

TWAMP-Light Reflector Sessions
Name              Status    Sender IP:PORT     Reflector IP:PORT
----------------  --------  -----------------  -------------------
SESSION_RECV_VM3  active    100.100.50.3:2862  100.100.100.2:2863
"""

twamp_light_null_output = ''''''

config_twamp_light_reflector_with_invalid_src_port = \
    """Usage: add [OPTIONS] <session_name> <sender_ip:port> <reflector_ip:port>

Error: Invalid value for "<sender_ip_port>": 999. Valid udp port range in 862|863|1025-65535
"""

config_twamp_light_reflector_with_invalid_dst_port = \
    """Usage: add [OPTIONS] <session_name> <sender_ip:port> <reflector_ip:port>

Error: Invalid value for "<reflector_ip_port>": 666. Valid udp port range in 862|863|1025-65535
"""

config_twamp_light_while_session_exist_error_info = \
    """Usage: add [OPTIONS] <session_name> <sender_ip:port> <reflector_ip:port>
           <packet_count> <tx_interval> <timeout> <statistics_interval>

Error: Invalid value for "<session_name>": """ + TL_SESSION_NAME + """. TWAMP-Light session already exists
"""

twamp_light_start_session_without_session_output = \
    """Usage: start [OPTIONS] <session_name|all>

Error: Invalid value for "<session_name>": """ + TL_SESSION_NAME + """. TWAMP-Light session does not exist
"""

twamp_light_add_continous_sender_with_invalid_monitor_time_output = \
    """Usage: add [OPTIONS] <session_name> <sender_ip:port> <reflector_ip:port>
           <monitor_time> <tx_interval> <timeout> <statistics_interval>
Try "add --help" for help.

Error: Statistics interval must be configured while monitor_time is 0(forever)
"""

twamp_light_add_continous_sender_with_invalid_stats_interval = \
    """Usage: add [OPTIONS] <session_name> <sender_ip:port> <reflector_ip:port>
           <monitor_time> <tx_interval> <timeout> <statistics_interval>
Try "add --help" for help.

Error: Statistics interval must be bigger than timeout*1000
"""

show_twamp_light_twoway_deley_stats_output = \
    """Latest two-way delay statistics(nsec):
Name                Index    Delay(AVG)    Jitter(AVG)
----------------  -------  ------------  -------------
SESSION_SEND_VM1        1             0              0
                        2             0              0
                        3             0              0
                        4             0              0
                        5             0              0
SESSION_SEND_VM2        1             0              0
                        2             0              0
                        3             0              0
                        4             0              0
                        5             0              0

Total two-way delay statistics(nsec):
Name                Delay(AVG)    Delay(MIN)    Delay(MAX)    Jitter(AVG)    Jitter(MIN)    Jitter(MAX)
----------------  ------------  ------------  ------------  -------------  -------------  -------------
SESSION_SEND_VM1             0             0             0              0              0              0
SESSION_SEND_VM2             0             0             0              0              0              0
"""

show_twamp_light_twoway_deley_stats_last3line_output = \
    """Latest two-way delay statistics(nsec):
Name                Index    Delay(AVG)    Jitter(AVG)
----------------  -------  ------------  -------------
SESSION_SEND_VM1        3             0              0
                        4             0              0
                        5             0              0
SESSION_SEND_VM2        3             0              0
                        4             0              0
                        5             0              0

Total two-way delay statistics(nsec):
Name                Delay(AVG)    Delay(MIN)    Delay(MAX)    Jitter(AVG)    Jitter(MIN)    Jitter(MAX)
----------------  ------------  ------------  ------------  -------------  -------------  -------------
SESSION_SEND_VM1             0             0             0              0              0              0
SESSION_SEND_VM2             0             0             0              0              0              0
"""

show_twamp_light_twoway_loss_stats_output = \
    """Latest two-way loss statistics:
Name                Index    Loss Count    Loss Ratio
----------------  -------  ------------  ------------
SESSION_SEND_VM1        1             0             0
                        2             0             0
                        3             0             0
                        4             0             0
                        5             0             0
SESSION_SEND_VM2        1             0             0
                        2             0             0
                        3             0             0
                        4             0             0
                        5             0             0

Total two-way loss statistics:
Name                Loss Count(AVG)    Loss Count(MIN)    Loss Count(MAX)    Loss Ratio(AVG)    \
Loss Ratio(MIN)    Loss Ratio(MAX)
----------------  -----------------  -----------------  -----------------  -----------------  \
-----------------  -----------------
SESSION_SEND_VM1                  0                  0                  0                  0                  \
0                  0
SESSION_SEND_VM2                  0                  0                  0                  0                  \
0                  0
"""

show_twamp_light_twoway_loss_stats_brief_output = \
    """Total two-way loss statistics:
Name                Loss Count(AVG)    Loss Count(MIN)    Loss Count(MAX)    Loss Ratio(AVG)    \
Loss Ratio(MIN)    Loss Ratio(MAX)
----------------  -----------------  -----------------  -----------------  -----------------  \
-----------------  -----------------
SESSION_SEND_VM1                  0                  0                  0                  0                  \
0                  0
"""


class TestTwampLightshow():
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        yield
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    @pytest.fixture(scope="function", autouse=True)
    def setUp(self):
        self.runner = CliRunner()
        yield
        del os.environ["TWAMPLIGHT_SHOW_MOCK"]

    def set_mock_variant(self, variant: str):
        os.environ["TWAMPLIGHT_SHOW_MOCK"] = variant

    def test_show_twamp_light_with_no_session_info(self):
        self.set_mock_variant("2")

        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["session"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_with_no_session_info

        return_code, result = get_result_and_return_code('twamp-light')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        # twamp-light script will not remove last blank line; show command can remove last blank line automaticaly
        assert result.rstrip() == show_twamp_light_with_no_session_info.rstrip()

    def test_show_twamp_light_with_normal_session_info(self):
        self.set_mock_variant("1")
        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["session"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_with_session_info

        # Specifiy the session
        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["session"], ["SESSION_SEND_VM1"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_with_session_for_VM1

    def test_show_twamp_light_stats_twoway_delay(self):
        self.set_mock_variant("1")
        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["statistics"], ["twoway-delay"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_twoway_deley_stats_output

        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["statistics"],
                                    ["twoway-delay", "--lastest_number", "3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_twoway_deley_stats_last3line_output

    def test_show_twamp_light_stats_twoway_loss(self):
        self.set_mock_variant("1")
        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["statistics"], ["twoway-loss"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_twoway_loss_stats_output

        result = self.runner.invoke(show.cli.commands["twamp-light"].commands["statistics"],
                                    ["twoway-loss", "SESSION_SEND_VM1", "-b", ])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_twamp_light_twoway_loss_stats_brief_output

    def test_config_add_reflector_normal(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light reflector sender port
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-reflector"].
                                    commands["add"], [TL_SESSION_NAME, TL_SRC_IP_NO_PORT, TL_DST_IP_PORT], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config reflector normal config test case with code {}:{} "\
                                      "Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
        # Check role string
        role_string = twamp_session.get(TL_CFGDB_ROLE_STRING)
        assert role_string is not None, "Role string not found"
        assert role_string == TL_CFGDB_ROLE_RFLT_VALULE, "Role string value not set"

        # Check source ip string
        srcip_string = twamp_session.get(TL_CFGDB_SRCIP_STRING)
        assert srcip_string is not None, "Src IP string not found"
        assert srcip_string == TL_CFGDB_SRCIP_VALULE, "Src IP string value not set"

        # Check source port string
        srcport_string = twamp_session.get(TL_CFGDB_SRCPT_STRING)
        assert srcport_string is not None, "SRC Port string not found"
        assert srcport_string == TL_CFGDB_RFLT_DFT_PT, "SRC Port string value not set"

        # Check dest port string
        dstport_string = twamp_session.get(TL_CFGDB_DSTPT_STRING)
        assert dstport_string is not None, "Dest Port string not found"
        assert dstport_string == TL_CFGDB_DSTPT_VALULE, "Dest Port string value not set"

    def test_config_remove_reflector_normal(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light reflector sender port
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-reflector"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_NO_PORT, TL_DST_IP_PORT, "--vrf", "VRF_TEST",
                                     "--dscp", "10", "--ttl", "20", "--timestamp-format", "ntp"], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config reflector normal config test case with code {}:{} "\
                                      "Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
        assert 0 != len(twamp_session), "twamp_session not found"

        # Check role string
        role_string = twamp_session.get(TL_CFGDB_ROLE_STRING)
        assert role_string is not None, "Role string not found"
        assert role_string == TL_CFGDB_ROLE_RFLT_VALULE, "Role string value not set"

        # Check source ip string
        srcip_string = twamp_session.get(TL_CFGDB_SRCIP_STRING)
        assert srcip_string is not None, "Src IP string not found"
        assert srcip_string == TL_CFGDB_SRCIP_VALULE, "Src IP string value not set"

        # Check source port string
        srcport_string = twamp_session.get(TL_CFGDB_SRCPT_STRING)
        assert srcport_string is not None, "SRC Port string not found"
        assert srcport_string == TL_CFGDB_RFLT_DFT_PT, "SRC Port string value not set"

        # Check dest port string
        dstport_string = twamp_session.get(TL_CFGDB_DSTPT_STRING)
        assert dstport_string is not None, "Dest Port string not found"
        assert dstport_string == TL_CFGDB_DSTPT_VALULE, "Dest Port string value not set"

        # Remove Session
        with patch("config.twamp_light.check_if_twamp_session_exist") as mock_function:
            mock_function.return_value = True
            result = self.runner.invoke(config.config.commands["twamp-light"].commands["remove"],
                                        [TL_SESSION_NAME], obj=db)
            assert result.output == twamp_light_null_output
            assert result.exit_code == 0, "twamp ligith config reflector normal config test case with code {}:{} "\
                                          "Output:{}".format(type(result.exit_code), result.exit_code,
                                                             result.output)
            twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
            assert 0 == len(twamp_session), "twamp_session isn't removed"

    def test_add_reflector_with_invalid_send_port(self):
        self.set_mock_variant("1")
        db = Db()

        # config invalid twamp light reflector sender port
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-reflector"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT_INVLD, TL_DST_IP_PORT], obj=db)
        print(result.output)
        assert result.output == config_twamp_light_reflector_with_invalid_src_port
        assert result.exit_code != 0, "reflector invalid src port test case with code {}:{} Output:{}".\
                                      format(type(result.exit_code), result.exit_code, result.output)

        # config invalid twamp light reflector sender port
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-reflector"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_PORT_INVLD], obj=db)
        print(result.output)
        assert result.output == config_twamp_light_reflector_with_invalid_dst_port
        assert result.exit_code != 0, "reflector invalid src port test case with code {}:{} Output:{}".\
                                      format(type(result.exit_code), result.exit_code, result.output)

    def test_config_add_sender_continuous_normal(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light sender with continuous mode
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["continuous"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_PORT, TL_MONITOR_TIME,
                                     TL_TX_INTERVAL, TL_TIMEOUT, TL_STATS_INTERVAL,  "--vrf",  "VRF_TEST",
                                     "--dscp", "15", "--ttl", "56", "--timestamp-format", "ptp"], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config reflector normal config test case with code {}:{} "\
                                      "Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
#        print(twamp_session)

        # Check role string
        role_string = twamp_session.get(TL_CFGDB_ROLE_STRING)
        assert role_string is not None, "Role string not found"
        assert role_string == TL_CFGDB_ROLE_SNDR_VALULE, "Role string value not set"

        # Check dst ip string
        srcip_string = twamp_session.get(TL_CFGDB_DSTIP_STRING)
        assert srcip_string is not None, "Src IP string not found"
        assert srcip_string == TL_CFGDB_DSTIP_VALULE, "Src IP string value not set"

        # Check dest port string
        dstport_string = twamp_session.get(TL_CFGDB_SRCPT_STRING)
        assert dstport_string is not None, "Dest Port string not found"
        assert dstport_string == TL_CFGDB_SRCPT_VALULE, "Dest Port string value not set"

        # Check src port string
        stats_intvl_string = twamp_session.get(TL_CFGDB_STATS_INTVL_STRING)
        assert stats_intvl_string is not None, "Stats interval string not found"
        assert stats_intvl_string == TL_STATS_INTERVAL, "Stats interval string value not set"

    def test_config_add_sender_continuous_with_invalid_stats_interval_monitor_time_none_zero(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light sender with continuous mode， without config stats internval
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["continuous"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_PORT, TL_MONITOR_TIME,
                                     TL_TX_INTERVAL, TL_TIMEOUT], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config reflector normal config test case with code "\
                                      "{}:{} Output:{}".\
                                      format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
#        print(twamp_session)

        # Check stats interval string
        stats_intvl_string = twamp_session.get(TL_CFGDB_STATS_INTVL_STRING)
        assert stats_intvl_string is not None, "Stats interval string not found"
        assert stats_intvl_string == TL_STATS_INTERVAL_CNTINU_MODE_DFT, "Stats interval string value not set"

    def test_config_add_sender_continuous_with_invalid_stats_interval_monitor_time_zero(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light sender with continuous mode， without config stats internval
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["continuous"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_PORT, "0", TL_TX_INTERVAL,
                                     TL_TIMEOUT], obj=db)
        assert result.output == twamp_light_add_continous_sender_with_invalid_monitor_time_output
        assert result.exit_code != 0, "twamp ligith config continuous sender with invalid monitor time. "\
                                      "Test case with code {}:{} Output:{}".\
                                      format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
#        print(twamp_session)

        # Check stats interval string
        stats_intvl_string = twamp_session.get(TL_CFGDB_STATS_INTVL_STRING)
        assert stats_intvl_string is None, "Stats interval string should not found"

    def test_config_add_sender_continuous_with_invalid_stats_interval_too_small(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light sender with continuous mode， without config stats internval
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["continuous"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_PORT, TL_MONITOR_TIME,
                                     TL_TX_INTERVAL, TL_TIMEOUT, "2000"], obj=db)
        assert result.output == twamp_light_add_continous_sender_with_invalid_stats_interval
        assert result.exit_code != 0, "twamp ligith config continuous sender with invalid stats interval. "\
                                      "Test case with code {}:{} Output:{}".\
                                      format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
#        print(twamp_session)

        # Check stats interval string
        stats_intvl_string = twamp_session.get(TL_CFGDB_STATS_INTVL_STRING)
        assert stats_intvl_string is None, "Stats interval string should not found"

    def test_config_add_sender_pkt_count_normal(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light sender
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["packet-count"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_NO_PORT, TL_PKT_CNT,
                                     TL_TX_INTERVAL, TL_TIMEOUT, TL_STATS_INTERVAL, "--vrf",  "VRF_TEST",
                                     "--dscp", "15", "--ttl", "56", "--timestamp-format", "ptp"], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config sender normal config test case with code {}:{} Output:"\
                                      "{}".format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
#        print(twamp_session)

        # Check role string
        role_string = twamp_session.get(TL_CFGDB_ROLE_STRING)
        assert role_string is not None, "Role string not found"
        assert role_string == TL_CFGDB_ROLE_SNDR_VALULE, "Role string value not set"

        # Check src ip string
        srcip_string = twamp_session.get(TL_CFGDB_SRCIP_STRING)
        assert srcip_string is not None, "Src IP string not found"
        assert srcip_string == TL_CFGDB_SRCIP_VALULE, "Src IP string value not set"

        # Check dst port string
        dstport_string = twamp_session.get(TL_CFGDB_DSTPT_STRING)
        assert dstport_string is not None, "Dest Port string not found"
        assert dstport_string == TL_CFGDB_SEND_DFT_PT, "Dest Port string value not set"

        # Check stats interval string
        stats_intvl_string = twamp_session.get(TL_CFGDB_STATS_INTVL_STRING)
        assert stats_intvl_string is not None, "Stats interval string not found"
        assert stats_intvl_string == TL_STATS_INTERVAL, "Stats interval string value not set"

    def test_config_add_sender_pkt_count_with_invalid_stats_interval(self):
        self.set_mock_variant("1")
        db = Db()

        # config valid twamp light sender without stats interval
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["packet-count"].commands["add"],
                                    [TL_SESSION_NAME, TL_SRC_IP_PORT, TL_DST_IP_NO_PORT, TL_PKT_CNT,
                                     TL_TX_INTERVAL, TL_TIMEOUT], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config sender normal config test case with code {}:{} "\
                                      "Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        twamp_session = db.cfgdb.get_entry(TL_CFGDB_KEY_PREFIX, TL_SESSION_NAME)
#        print(twamp_session)

        # Check stats interval string
        stats_intvl_string = twamp_session.get(TL_CFGDB_STATS_INTVL_STRING)
        assert stats_intvl_string is not None, "Stats interval string not found"
        assert stats_intvl_string == TL_STATS_INTERVAL_DFT, "Stats interval string value not set"

    def test_config_add_sender_while_session_exist(self):
        self.set_mock_variant("1")
        db = Db()

        with patch("config.twamp_light.check_if_twamp_session_exist") as mock_function:
            mock_function.return_value = True
            # config valid twamp light sender with default port
            result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                        commands["packet-count"].commands["add"],
                                        [TL_SESSION_NAME, TL_SRC_IP_DFT_PORT, TL_DST_IP_DFT_PORT, TL_PKT_CNT,
                                         TL_TX_INTERVAL, TL_TIMEOUT, TL_STATS_INTERVAL], obj=db)
            assert result.output == config_twamp_light_while_session_exist_error_info
            print(result.output)
            assert result.exit_code != 0, "twamp ligith config sender while session is exist, should report error"\
                                          " info. test case with code {}:{} Output:{}".\
                                          format(type(result.exit_code), result.exit_code, result.output)

    def test_config_add_sender_start_with_no_session(self):
        self.set_mock_variant("1")
        db = Db()

        # Start session before create session
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["start"], [TL_SESSION_NAME], obj=db)
        assert result.output == twamp_light_start_session_without_session_output
        assert result.exit_code != 0, "twamp ligith config sender start session test case with code {}:{} Output:"\
                                      "{}".format(type(result.exit_code), result.exit_code, result.output)

#    @patch("config.twamp_light.ConfigDBConnector.get_table",
#           mock.Mock(return_value={"TWAMP_SESSION_TABLE|session_name1"}))
#    @patch("config.twamp_light.ConfigDBConnector.get_entry", mock.Mock(???))
    def test_config_add_sender_start_single_session(self):
        self.set_mock_variant("1")
        db = Db()

        with patch("config.twamp_light.check_if_twamp_session_exist") as mock_function:
            mock_function.return_value = False
            # config valid twamp light sender with default port
            result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                        commands["packet-count"].commands["add"],
                                        [TL_SESSION_NAME, TL_SRC_IP_DFT_PORT, TL_DST_IP_DFT_PORT, TL_PKT_CNT,
                                         TL_TX_INTERVAL, TL_TIMEOUT, TL_STATS_INTERVAL], obj=db)
            assert result.output == twamp_light_null_output
            assert result.exit_code == 0, "twamp ligith config sender with default port config test case with code"\
                                          " {}:{} Output:{}".format(type(result.exit_code),
                                                                    result.exit_code, result.output)

        with patch("config.twamp_light.check_if_twamp_session_exist") as mock_function:
            mock_function.return_value = True
            # Start session
            result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                        commands["start"], [TL_SESSION_NAME], obj=db)
            assert result.output == twamp_light_null_output
            assert result.exit_code == 0, "twamp ligith config sender start session test case with code {}:{} "\
                                          "Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    @patch("config.twamp_light.ConfigDBConnector.get_table", mock.Mock(return_value={TL_SESSION_NAME: ""}))
    def test_config_add_sender_start_all_session(self):
        self.set_mock_variant("1")
        db = Db()

        with patch("config.twamp_light.check_if_twamp_session_exist") as mock_function:
            mock_function.return_value = False
            # config valid twamp light sender with default port
            result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                        commands["packet-count"].commands["add"],
                                        [TL_SESSION_NAME, TL_SRC_IP_DFT_PORT, TL_DST_IP_DFT_PORT,
                                         TL_PKT_CNT, TL_TX_INTERVAL, TL_TIMEOUT, TL_STATS_INTERVAL], obj=db)
            assert result.output == twamp_light_null_output
            assert result.exit_code == 0, "twamp ligith config sender with default port config test case with "\
                   "code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # Start session
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["start"], ["all"], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config sender start session test case with code {}:{} "\
                                      "Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # Stop session
        result = self.runner.invoke(config.config.commands["twamp-light"].commands["session-sender"].
                                    commands["stop"], ["all"], obj=db)
        assert result.output == twamp_light_null_output
        assert result.exit_code == 0, "twamp ligith config sender start session test case with code {}:{} "\
                                      "Output:{}".format(type(result.exit_code), result.exit_code, result.output)
