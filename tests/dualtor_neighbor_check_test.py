import dualtor_neighbor_check
import json
import pytest
import shlex
import sys
import subprocess
import tabulate

from unittest.mock import call
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

sys.path.append("scripts")


class TestDualtorNeighborCheck(object):
    """Test class to test dualtor_neighbor_check.py"""

    @pytest.fixture
    def mock_log_functions(self):
        with patch("dualtor_neighbor_check.WRITE_LOG_ERROR") as mock_log_err, \
                patch("dualtor_neighbor_check.WRITE_LOG_WARN") as mock_log_warn, \
                patch("dualtor_neighbor_check.WRITE_LOG_INFO") as mock_log_info, \
                patch("dualtor_neighbor_check.WRITE_LOG_DEBUG") as mock_log_debug:
            yield mock_log_err, mock_log_warn, mock_log_info, mock_log_debug

    @pytest.fixture
    def mock_py_log_functions(self):
        with patch("dualtor_neighbor_check.logging.error") as mock_log_err, \
                patch("dualtor_neighbor_check.logging.warning") as mock_log_warn, \
                patch("dualtor_neighbor_check.logging.info") as mock_log_info, \
                patch("dualtor_neighbor_check.logging.debug") as mock_log_debug:
            yield mock_log_err, mock_log_warn, mock_log_info, mock_log_debug

    @pytest.fixture
    def mock_syslog_log_function(self):
        with patch("dualtor_neighbor_check.syslog.syslog") as mock_syslog_log:
            yield mock_syslog_log

    def test_run_command(self, mock_log_functions):
        with patch("dualtor_neighbor_check.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_proc.communicate.return_value = (b"admin", None)
            mock_proc.returncode = 0

            out = dualtor_neighbor_check.run_command("whoami")

            mock_popen.assert_called_once_with(shlex.split("whoami"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            mock_proc.communicate.assert_called_once()
            assert out == "admin"

    def test_run_command_nonzero_return(self, mock_log_functions):
        with patch("dualtor_neighbor_check.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_proc.communicate.return_value = (b"ls: cannot access '/tmp/not-existed': No such file or directory", None)
            mock_proc.returncode = 2

            with pytest.raises(RuntimeError):
                dualtor_neighbor_check.run_command("ls /tmp/not-existed")

            mock_popen.assert_called_once_with(shlex.split("ls /tmp/not-existed"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            mock_proc.communicate.assert_called_once()

    def test_flush_neighbor_ipv4(self, mock_log_functions):
        with patch("dualtor_neighbor_check.run_command") as mock_run_command:
            dualtor_neighbor_check.flush_neighbor("192.168.0.2")

            mock_run_command.assert_called_once_with("sudo ip -4 neigh flush to 192.168.0.2")

    def test_flush_neighbor_ipv6(self, mock_log_functions):
        with patch("dualtor_neighbor_check.run_command") as mock_run_command:
            dualtor_neighbor_check.flush_neighbor("fc02:1000::1")

            mock_run_command.assert_called_once_with("sudo ip -6 neigh flush to fc02:1000::1")

    def test_flush_inconsistent_neighbors_flushes_all_failed_neighbors(self, mock_log_functions):
        _, mock_log_warn, _, _ = mock_log_functions
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"},
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"},
            {"NEIGHBOR": "192.168.0.3", "PORT": "Ethernet8", "_NEIGHBOR_MODE": "prefix-route"},
            {"NEIGHBOR": "192.168.0.4", "PORT": "Ethernet12", "_NEIGHBOR_MODE": "host-route"},
            {"NEIGHBOR": "192.168.0.5", "PORT": dualtor_neighbor_check.NOT_AVAILABLE,
             "_NEIGHBOR_MODE": "prefix-route"}
        ]

        with patch("dualtor_neighbor_check.flush_neighbor") as mock_flush_neighbor:
            flush_count = dualtor_neighbor_check.flush_inconsistent_neighbors(failed_neighbors)

            assert flush_count == 4
            mock_flush_neighbor.assert_has_calls([
                call("192.168.0.2"),
                call("192.168.0.3"),
                call("192.168.0.4"),
                call("192.168.0.5")
            ])
            mock_log_warn.assert_has_calls([
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.2"),
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.3"),
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.4"),
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.5")
            ])

    def test_flush_inconsistent_neighbors_continues_after_flush_failure(self, mock_log_functions):
        mock_log_err, mock_log_warn, _, _ = mock_log_functions
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"},
            {"NEIGHBOR": "192.168.0.3", "PORT": "Ethernet8", "_NEIGHBOR_MODE": "prefix-route"},
            {"NEIGHBOR": "192.168.0.4", "PORT": "Ethernet12", "_NEIGHBOR_MODE": "host-route"},
        ]

        with patch("dualtor_neighbor_check.flush_neighbor",
                   side_effect=[None, RuntimeError("flush failed"), None]) as mock_flush_neighbor:
            flush_count = dualtor_neighbor_check.flush_inconsistent_neighbors(failed_neighbors)

            assert flush_count == 2
            mock_flush_neighbor.assert_has_calls([
                call("192.168.0.2"),
                call("192.168.0.3"),
                call("192.168.0.4")
            ])
            mock_log_warn.assert_has_calls([
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.2"),
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.3"),
                call("Flushing inconsistent neighbor entry: %s", "192.168.0.4")
            ])
            mock_log_err.assert_called_once_with(
                "Failed to flush inconsistent neighbor entry %s: %s",
                "192.168.0.3",
                ANY
            )

    def test_flush_inconsistent_neighbors_continues_after_invalid_ip(self, mock_log_functions):
        mock_log_err, _, _, _ = mock_log_functions
        failed_neighbors = [
            {"NEIGHBOR": "not-an-ip", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"},
            {"NEIGHBOR": "192.168.0.3", "PORT": "Ethernet8", "_NEIGHBOR_MODE": "prefix-route"},
        ]

        with patch("dualtor_neighbor_check.flush_neighbor",
                   side_effect=[ValueError("invalid IP"), None]) as mock_flush_neighbor:
            flush_count = dualtor_neighbor_check.flush_inconsistent_neighbors(failed_neighbors)

            assert flush_count == 1
            mock_flush_neighbor.assert_has_calls([
                call("not-an-ip"),
                call("192.168.0.3")
            ])
            mock_log_err.assert_called_once_with(
                "Failed to flush inconsistent neighbor entry %s: %s",
                "not-an-ip",
                ANY
            )

    def test_parse_check_results_returns_failed_neighbors_consistent(self, mock_log_functions):
        check_results = [{
            "NEIGHBOR": "192.168.0.2",
            "MAC": "ee:86:d8:46:7d:01",
            "PORT": "Ethernet4",
            "MUX_STATE": "active",
            "IN_MUX_TOGGLE": False,
            "NEIGHBOR_IN_ASIC": True,
            "TUNNEL_IN_ASIC": False,
            "HWSTATUS": True,
            "_NEIGHBOR_MODE": "host-route"
        }]

        res, failed_neighbors = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        assert failed_neighbors == []

    def test_parse_check_results_empty_matches_original_no_output(self, mock_log_functions):
        _, mock_log_warn, _, _ = mock_log_functions

        res, failed_neighbors = dualtor_neighbor_check.parse_check_results([])

        assert res is True
        assert failed_neighbors == []
        mock_log_warn.assert_not_called()

    def test_run_neighbor_check(self, mock_log_functions):
        appl_db = MagicMock()
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        if_oid_to_port_name_map = {"1001": "Ethernet4"}
        tables = (
            {"192.168.0.2": "ee:86:d8:46:7d:01"},
            {"Ethernet4": "active"},
            {"Ethernet4": "active"},
            {"Ethernet4": "prefix-route"},
            {"ee:86:d8:46:7d:01": "1001"},
            [],
            [],
            {}
        )
        expected_check_results = [{"NEIGHBOR": "192.168.0.2"}]

        with patch("dualtor_neighbor_check.read_tables_from_db", return_value=tables) as mock_read_tables, \
                patch("dualtor_neighbor_check.get_mac_to_port_name_map",
                      return_value={"ee:86:d8:46:7d:01": "Ethernet4"}) as mock_get_mac_map, \
                patch("dualtor_neighbor_check.check_neighbor_consistency",
                      return_value=expected_check_results) as mock_check:
            result = dualtor_neighbor_check.run_neighbor_check(
                appl_db, mux_server_to_port_map, if_oid_to_port_name_map)

            assert result == expected_check_results
            mock_read_tables.assert_called_once_with(appl_db)
            mock_get_mac_map.assert_called_once_with(tables[4], if_oid_to_port_name_map)
            mock_check.assert_called_once_with(
                tables[0],
                tables[1],
                tables[2],
                {"ee:86:d8:46:7d:01": "Ethernet4"},
                tables[5],
                tables[6],
                tables[7],
                mux_server_to_port_map,
                tables[3]
            )

    def test_main_skips_non_dualtor(self, mock_log_functions):
        args = MagicMock()
        config_db = MagicMock()

        with patch("dualtor_neighbor_check.parse_args", return_value=args), \
                patch("dualtor_neighbor_check.config_logging") as mock_config_logging, \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector",
                      return_value=config_db) as mock_config_db_connector, \
                patch("dualtor_neighbor_check.daemon_base.db_connect") as mock_db_connect, \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={}), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=False), \
                patch("dualtor_neighbor_check.run_neighbor_check") as mock_run_neighbor_check:
            result = dualtor_neighbor_check.main()

            assert result == 0
            mock_config_logging.assert_called_once_with(args)
            mock_config_db_connector.assert_called_once_with(use_unix_socket_path=False)
            config_db.connect.assert_called_once()
            mock_db_connect.assert_called_once_with("APPL_DB")
            mock_run_neighbor_check.assert_not_called()

    def test_main_flushes_and_reruns_inconsistent_neighbors(self, mock_log_functions):
        args = MagicMock()
        config_db = MagicMock()
        appl_db = MagicMock()
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"}
        ]

        with patch("dualtor_neighbor_check.parse_args", return_value=args), \
                patch("dualtor_neighbor_check.config_logging"), \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector", return_value=config_db), \
                patch("dualtor_neighbor_check.daemon_base.db_connect", return_value=appl_db), \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={"Ethernet4": {}}), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=True), \
                patch("dualtor_neighbor_check.get_mux_server_to_port_map",
                      return_value={"192.168.0.2": "Ethernet4"}) as mock_mux_server_map, \
                patch("dualtor_neighbor_check.get_if_br_oid_to_port_name_map",
                      return_value={"1001": "Ethernet4"}) as mock_oid_map, \
                patch("dualtor_neighbor_check.run_neighbor_check",
                      side_effect=[[{"first": "result"}], [{"second": "result"}]]) as mock_run_neighbor_check, \
                patch("dualtor_neighbor_check.parse_check_results",
                      side_effect=[(False, failed_neighbors), (True, [])]) as mock_parse_results, \
                patch("dualtor_neighbor_check.flush_inconsistent_neighbors", return_value=1) as mock_flush, \
                patch("dualtor_neighbor_check.time.sleep") as mock_sleep:
            result = dualtor_neighbor_check.main()

            assert result == 0
            mock_mux_server_map.assert_called_once_with({"Ethernet4": {}})
            mock_oid_map.assert_called_once_with()
            mock_run_neighbor_check.assert_has_calls([
                call(appl_db, {"192.168.0.2": "Ethernet4"}, {"1001": "Ethernet4"}, args.recheck_delay_ms),
                call(appl_db, {"192.168.0.2": "Ethernet4"}, {"1001": "Ethernet4"}, args.recheck_delay_ms)
            ])
            mock_parse_results.assert_has_calls([
                call([{"first": "result"}]),
                call([{"second": "result"}])
            ])
            mock_flush.assert_called_once_with(failed_neighbors)
            mock_sleep.assert_called_once_with(dualtor_neighbor_check.POST_FLUSH_CHECK_DELAY_SEC)

    def test_main_waits_once_before_post_flush_check(self, mock_log_functions):
        args = MagicMock()
        config_db = MagicMock()
        appl_db = MagicMock()
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "host-route"}
        ]

        with patch("dualtor_neighbor_check.parse_args", return_value=args), \
                patch("dualtor_neighbor_check.config_logging"), \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector", return_value=config_db), \
                patch("dualtor_neighbor_check.daemon_base.db_connect", return_value=appl_db), \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={"Ethernet4": {}}), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=True), \
                patch("dualtor_neighbor_check.get_mux_server_to_port_map",
                      return_value={"192.168.0.2": "Ethernet4"}), \
                patch("dualtor_neighbor_check.get_if_br_oid_to_port_name_map",
                      return_value={"1001": "Ethernet4"}), \
                patch("dualtor_neighbor_check.run_neighbor_check",
                      side_effect=[[{"first": "result"}], [{"second": "result"}]]) as mock_run_neighbor_check, \
                patch("dualtor_neighbor_check.parse_check_results",
                      side_effect=[(False, failed_neighbors), (True, [])]) as mock_parse_results, \
                patch("dualtor_neighbor_check.flush_inconsistent_neighbors", return_value=1), \
                patch("dualtor_neighbor_check.time.sleep") as mock_sleep:
            result = dualtor_neighbor_check.main()

            assert result == 0
            assert mock_run_neighbor_check.call_count == 2
            assert mock_parse_results.call_count == 2
            mock_sleep.assert_called_once_with(dualtor_neighbor_check.POST_FLUSH_CHECK_DELAY_SEC)

    def test_main_returns_failure_when_post_flush_check_remains_inconsistent(self, mock_log_functions):
        args = MagicMock()
        config_db = MagicMock()
        appl_db = MagicMock()
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"}
        ]

        with patch("dualtor_neighbor_check.parse_args", return_value=args), \
                patch("dualtor_neighbor_check.config_logging"), \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector", return_value=config_db), \
                patch("dualtor_neighbor_check.daemon_base.db_connect", return_value=appl_db), \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={"Ethernet4": {}}), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=True), \
                patch("dualtor_neighbor_check.get_mux_server_to_port_map",
                      return_value={"192.168.0.2": "Ethernet4"}), \
                patch("dualtor_neighbor_check.get_if_br_oid_to_port_name_map",
                      return_value={"1001": "Ethernet4"}), \
                patch("dualtor_neighbor_check.run_neighbor_check",
                      side_effect=[[{"first": "result"}], [{"second": "result"}]]) as mock_run_neighbor_check, \
                patch("dualtor_neighbor_check.parse_check_results",
                      side_effect=[(False, failed_neighbors), (False, failed_neighbors)]) as mock_parse_results, \
                patch("dualtor_neighbor_check.flush_inconsistent_neighbors", return_value=1), \
                patch("dualtor_neighbor_check.time.sleep") as mock_sleep:
            result = dualtor_neighbor_check.main()

            assert result == 1
            assert mock_run_neighbor_check.call_count == 2
            assert mock_parse_results.call_count == 2
            mock_sleep.assert_called_once_with(dualtor_neighbor_check.POST_FLUSH_CHECK_DELAY_SEC)

    def test_main_skips_rerun_when_no_neighbors_are_flushed(self, mock_log_functions):
        args = MagicMock()
        config_db = MagicMock()
        appl_db = MagicMock()
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"}
        ]

        with patch("dualtor_neighbor_check.parse_args", return_value=args), \
                patch("dualtor_neighbor_check.config_logging"), \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector", return_value=config_db), \
                patch("dualtor_neighbor_check.daemon_base.db_connect", return_value=appl_db), \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={"Ethernet4": {}}), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=True), \
                patch("dualtor_neighbor_check.get_mux_server_to_port_map",
                      return_value={"192.168.0.2": "Ethernet4"}), \
                patch("dualtor_neighbor_check.get_if_br_oid_to_port_name_map",
                      return_value={"1001": "Ethernet4"}), \
                patch("dualtor_neighbor_check.run_neighbor_check",
                      return_value=[{"first": "result"}]) as mock_run_neighbor_check, \
                patch("dualtor_neighbor_check.parse_check_results",
                      return_value=(False, failed_neighbors)) as mock_parse_results, \
                patch("dualtor_neighbor_check.flush_inconsistent_neighbors", return_value=0), \
                patch("dualtor_neighbor_check.time.sleep") as mock_sleep:
            result = dualtor_neighbor_check.main()

            assert result == 1
            mock_run_neighbor_check.assert_called_once()
            mock_parse_results.assert_called_once_with([{"first": "result"}])
            mock_sleep.assert_not_called()

    def test_main_logs_alert_when_post_flush_check_remains_inconsistent(self, mock_log_functions):
        mock_log_err, _, _, _ = mock_log_functions
        args = MagicMock()
        config_db = MagicMock()
        appl_db = MagicMock()
        failed_neighbors = [
            {"NEIGHBOR": "192.168.0.2", "PORT": "Ethernet4", "_NEIGHBOR_MODE": "prefix-route"}
        ]

        with patch("dualtor_neighbor_check.parse_args", return_value=args), \
                patch("dualtor_neighbor_check.config_logging"), \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector", return_value=config_db), \
                patch("dualtor_neighbor_check.daemon_base.db_connect", return_value=appl_db), \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={"Ethernet4": {}}), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=True), \
                patch("dualtor_neighbor_check.get_mux_server_to_port_map",
                      return_value={"192.168.0.2": "Ethernet4"}), \
                patch("dualtor_neighbor_check.get_if_br_oid_to_port_name_map",
                      return_value={"1001": "Ethernet4"}), \
                patch("dualtor_neighbor_check.run_neighbor_check",
                      side_effect=[[{"first": "result"}], [{"second": "result"}]]), \
                patch("dualtor_neighbor_check.parse_check_results",
                      side_effect=[(False, failed_neighbors), (False, failed_neighbors)]), \
                patch("dualtor_neighbor_check.flush_inconsistent_neighbors", return_value=1), \
                patch("dualtor_neighbor_check.time.sleep"):
            result = dualtor_neighbor_check.main()

            assert result == 1
            mock_log_err.assert_called_with(
                "ALERT: post-flush dualtor neighbor check still found inconsistent neighbors."
            )

    def test_redis_cli(self, mock_log_functions):
        with patch("dualtor_neighbor_check.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_proc.communicate.return_value = (b"6cde21a0d21ab29e08dd72e13b77214dbb01902f", None)
            mock_proc.returncode = 0

            redis_cmd = "script load \"return helloworld\""
            out = dualtor_neighbor_check.redis_cli(redis_cmd)

            mock_popen.assert_called_once_with(shlex.split("sudo redis-cli %s" % redis_cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            mock_proc.communicate.assert_called_once()
            assert out == "6cde21a0d21ab29e08dd72e13b77214dbb01902f"

    def test_redis_cli_error_stdout(self, mock_log_functions):
        with patch("dualtor_neighbor_check.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_proc.communicate.return_value = (b"(error) NOSCRIPT No matching script. Please use EVAL.", None)
            mock_proc.returncode = 0

            redis_cmd = "evalsha 0 0"
            with pytest.raises(RuntimeError):
                dualtor_neighbor_check.redis_cli(redis_cmd)

            mock_popen.assert_called_once_with(shlex.split("sudo redis-cli %s" % redis_cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            mock_proc.communicate.assert_called_once()

    def test_log_config_default(self, mock_py_log_functions):
        mock_log_err, mock_log_warn, mock_log_info, mock_log_debug = mock_py_log_functions
        with patch("dualtor_neighbor_check.sys.argv", ["dualtor_neighbor_check.py"]) as mock_argv:
            args = dualtor_neighbor_check.parse_args()
            dualtor_neighbor_check.config_logging(args)
            dualtor_neighbor_check.WRITE_LOG_ERROR("test_error")
            dualtor_neighbor_check.WRITE_LOG_WARN("test_warn")
            dualtor_neighbor_check.WRITE_LOG_INFO("test_info")
            dualtor_neighbor_check.WRITE_LOG_DEBUG("test_debug")

            assert args.log_output == dualtor_neighbor_check.LogOutput.STDOUT
            assert args.log_level == dualtor_neighbor_check.logging.WARNING
            assert args.syslog_level is None
            mock_log_err.assert_called_once_with("test_error")
            mock_log_warn.assert_called_once_with("test_warn")
            mock_log_info.assert_called_once_with("test_info")
            mock_log_debug.assert_called_once_with("test_debug")

    def test_log_config_syslog_default_level(self, mock_syslog_log_function):
        expected_syslog_calls = [
            call(dualtor_neighbor_check.syslog.LOG_ERR, "test_error"),
            call(dualtor_neighbor_check.syslog.LOG_NOTICE, "test_warn")
        ]
        with patch("dualtor_neighbor_check.sys.argv", ["dualtor_neighbor_check.py", "-o", "SYSLOG"]) as mock_argv:
            args = dualtor_neighbor_check.parse_args()
            dualtor_neighbor_check.config_logging(args)
            dualtor_neighbor_check.WRITE_LOG_ERROR("test_error")
            dualtor_neighbor_check.WRITE_LOG_WARN("test_warn")
            dualtor_neighbor_check.WRITE_LOG_INFO("test_info")
            dualtor_neighbor_check.WRITE_LOG_DEBUG("test_debug")

            assert args.log_output == dualtor_neighbor_check.LogOutput.SYSLOG
            assert args.syslog_level == dualtor_neighbor_check.SyslogLevel.NOTICE
            assert args.log_level is None
            mock_syslog_log_function.assert_has_calls(expected_syslog_calls)

    def test_log_config_syslog_debug_level(self, mock_syslog_log_function):
        expected_syslog_calls = [
            call(dualtor_neighbor_check.syslog.LOG_ERR, "test_error"),
            call(dualtor_neighbor_check.syslog.LOG_NOTICE, "test_warn"),
            call(dualtor_neighbor_check.syslog.LOG_INFO, "test_info"),
            call(dualtor_neighbor_check.syslog.LOG_DEBUG, "test_debug")
        ]
        with patch("dualtor_neighbor_check.sys.argv", ["dualtor_neighbor_check.py", "-o", "SYSLOG", "-s", "DEBUG"]) as mock_argv:
            args = dualtor_neighbor_check.parse_args()
            dualtor_neighbor_check.config_logging(args)
            dualtor_neighbor_check.WRITE_LOG_ERROR("test_error")
            dualtor_neighbor_check.WRITE_LOG_WARN("test_warn")
            dualtor_neighbor_check.WRITE_LOG_INFO("test_info")
            dualtor_neighbor_check.WRITE_LOG_DEBUG("test_debug")

            assert args.log_output == dualtor_neighbor_check.LogOutput.SYSLOG
            assert args.syslog_level == dualtor_neighbor_check.SyslogLevel.DEBUG
            assert args.log_level is None
            mock_syslog_log_function.assert_has_calls(expected_syslog_calls)

    def test_is_dualtor_true(self, mock_log_functions):
        mock_config_db = MagicMock()
        mock_config_db.get_table = MagicMock(
            return_value={
                "localhost": {
                    "bgp_asn": "65100",
                    "hostname": "lab-dev-01-t0",
                    "peer_switch": "lab-dev-01-lt0",
                    "subtype": "DualToR",
                    "type": "ToRRouter",
                }
            }
        )

        is_dualtor = dualtor_neighbor_check.is_dualtor(mock_config_db)
        mock_config_db.get_table.assert_has_calls(
            [call("DEVICE_METADATA")]
        )
        assert is_dualtor

    def test_is_dualtor_false(self, mock_log_functions):
        mock_config_db = MagicMock()
        mock_config_db.get_table = MagicMock(
            return_value={
                "localhost": {
                    "bgp_asn": "65100",
                    "hostname": "lab-dev-01-t0",
                    "type": "ToRRouter",
                }
            }
        )

        is_dualtor = dualtor_neighbor_check.is_dualtor(mock_config_db)
        mock_config_db.get_table.assert_has_calls(
            [call("DEVICE_METADATA")]
        )
        assert not is_dualtor

    def test_is_dualtor_false_empty_metadata(self, mock_log_functions):
        mock_config_db = MagicMock()
        mock_config_db.get_table = MagicMock(return_value={})

        is_dualtor = dualtor_neighbor_check.is_dualtor(mock_config_db)
        mock_config_db.get_table.assert_has_calls(
            [call("DEVICE_METADATA")]
        )
        assert not is_dualtor

    def test_read_from_db(self, mock_log_functions):
        with patch("dualtor_neighbor_check.run_command") as mock_run_command:
            neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
            mux_states = {"Ethernet4": "active"}
            hw_mux_states = {"Ethernet4": "active"}
            port_neighbor_modes = {"Ethernet4": "host-route"}
            asic_fdb = {"ee:86:d8:46:7d:01": "oid:0x3a00000000064b"}
            asic_route_table = []
            asic_neigh_table = \
                ["{\"ip\":\"192.168.0.23\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}"]
            asic_nexthop_table = \
                {'oid:0x40000000005c0': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_IP', 'nexthop_id': 'oid:0x40000000005c0'}}
            mock_run_command.side_effect = [
                "c53fd5eaad68be1e66a2fe80cd20a9cb18c91259",
                json.dumps(
                    {
                        "neighbors": neighbors,
                        "mux_states": mux_states,
                        "hw_mux_states": hw_mux_states,
                        "port_neighbor_modes": port_neighbor_modes,
                        "asic_fdb": asic_fdb,
                        "asic_route_table": asic_route_table,
                        "asic_neigh_table": asic_neigh_table,
                        "asic_nexthop_table": asic_nexthop_table
                    }
                )
            ]
            mock_appl_db = MagicMock()
            mock_appl_db.get = MagicMock(return_value=None)

            result = dualtor_neighbor_check.read_tables_from_db(mock_appl_db)

            mock_appl_db.get.assert_called_once_with("_DUALTOR_NEIGHBOR_CHECK_SCRIPT_SHA1")
            mock_run_command.assert_has_calls(
                [
                    call("sudo redis-cli SCRIPT LOAD \"%s\"" % dualtor_neighbor_check.DB_READ_SCRIPT),
                    call("sudo redis-cli EVALSHA c53fd5eaad68be1e66a2fe80cd20a9cb18c91259 0")
                ]
            )
            assert neighbors == result[0]
            assert mux_states == result[1]
            assert hw_mux_states == result[2]
            assert port_neighbor_modes == result[3]
            assert {k: v.lstrip("oid:0x") for k, v in asic_fdb.items()} == result[4]
            assert asic_route_table == result[5]
            assert asic_neigh_table == result[6]
            assert asic_nexthop_table == result[7]

    def test_read_from_db_script_not_existed(self, mock_log_functions):
        with patch("dualtor_neighbor_check.run_command") as mock_run_command:
            neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
            mux_states = {"Ethernet4": "active"}
            hw_mux_states = {"Ethernet4": "active"}
            port_neighbor_modes = {"Ethernet4": "prefix-route"}
            asic_fdb = {"ee:86:d8:46:7d:01": "oid:0x3a00000000064b"}
            asic_route_table = []
            asic_neigh_table = \
                ["{\"ip\":\"192.168.0.23\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}"]
            asic_nexthop_table = \
                {'oid:0x40000000005c0': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_IP', 'nexthop_id': 'oid:0x40000000005c0'}}
            mock_run_command.side_effect = [
                "(integer) 0",
                "c53fd5eaad68be1e66a2fe80cd20a9cb18c91259",
                json.dumps(
                    {
                        "neighbors": neighbors,
                        "mux_states": mux_states,
                        "hw_mux_states": hw_mux_states,
                        "port_neighbor_modes": port_neighbor_modes,
                        "asic_fdb": asic_fdb,
                        "asic_route_table": asic_route_table,
                        "asic_neigh_table": asic_neigh_table,
                        "asic_nexthop_table": asic_nexthop_table
                    }
                )
            ]
            mock_appl_db = MagicMock()
            mock_appl_db.get = MagicMock(return_value="c53fd5eaad68be1e66a2fe80cd20a9cb18c91259")

            result = dualtor_neighbor_check.read_tables_from_db(mock_appl_db)

            mock_appl_db.get.assert_called_once_with("_DUALTOR_NEIGHBOR_CHECK_SCRIPT_SHA1")
            mock_run_command.assert_has_calls(
                [
                    call("sudo redis-cli SCRIPT EXISTS c53fd5eaad68be1e66a2fe80cd20a9cb18c91259"),
                    call("sudo redis-cli SCRIPT LOAD \"%s\"" % dualtor_neighbor_check.DB_READ_SCRIPT),
                    call("sudo redis-cli EVALSHA c53fd5eaad68be1e66a2fe80cd20a9cb18c91259 0")
                ]
            )
            assert neighbors == result[0]
            assert mux_states == result[1]
            assert hw_mux_states == result[2]
            assert port_neighbor_modes == result[3]
            assert {k: v.lstrip("oid:0x") for k, v in asic_fdb.items()} == result[4]
            assert asic_route_table == result[5]
            assert asic_neigh_table == result[6]
            assert asic_nexthop_table == result[7]

    def test_read_from_db_with_lua_cache(self, mock_log_functions):
        with patch("dualtor_neighbor_check.run_command") as mock_run_command:
            neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
            mux_states = {"Ethernet4": "active"}
            hw_mux_states = {"Ethernet4": "active"}
            port_neighbor_modes = {"Ethernet4": "host-route"}
            asic_fdb = {"ee:86:d8:46:7d:01": "oid:0x3a00000000064b"}
            asic_route_table = []
            asic_neigh_table = \
                ["{\"ip\":\"192.168.0.23\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}"]
            asic_nexthop_table = \
                {'oid:0x40000000005c0': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_IP', 'nexthop_id': 'oid:0x40000000005c0'}}
            mock_run_command.side_effect = [
                "(integer) 1",
                json.dumps(
                    {
                        "neighbors": neighbors,
                        "mux_states": mux_states,
                        "hw_mux_states": hw_mux_states,
                        "port_neighbor_modes": port_neighbor_modes,
                        "asic_fdb": asic_fdb,
                        "asic_route_table": asic_route_table,
                        "asic_neigh_table": asic_neigh_table,
                        "asic_nexthop_table": asic_nexthop_table
                    }
                )
            ]
            mock_appl_db = MagicMock()
            mock_appl_db.get = MagicMock(return_value="c53fd5eaad68be1e66a2fe80cd20a9cb18c91259")

            result = dualtor_neighbor_check.read_tables_from_db(mock_appl_db)

            mock_appl_db.get.assert_called_once_with("_DUALTOR_NEIGHBOR_CHECK_SCRIPT_SHA1")
            mock_run_command.assert_has_calls(
                [
                    call("sudo redis-cli SCRIPT EXISTS c53fd5eaad68be1e66a2fe80cd20a9cb18c91259"),
                    call("sudo redis-cli EVALSHA c53fd5eaad68be1e66a2fe80cd20a9cb18c91259 0")
                ]
            )
            assert neighbors == result[0]
            assert mux_states == result[1]
            assert hw_mux_states == result[2]
            assert port_neighbor_modes == result[3]
            assert {k: v.lstrip("oid:0x") for k, v in asic_fdb.items()} == result[4]
            assert asic_route_table == result[5]
            assert asic_neigh_table == result[6]
            assert asic_nexthop_table == result[7]

    def test_get_mux_server_to_port_map(self, mock_log_functions):
        mux_cables = {
            "Ethernet4": {
                "server_ipv4": "192.168.0.2/32",
                "server_ipv6": "fc02:1000::2/128",
                "state": "active"
            }
        }
        mux_server_to_port_map = {
            "192.168.0.2": "Ethernet4",
            "fc02:1000::2": "Ethernet4"
        }

        result = dualtor_neighbor_check.get_mux_server_to_port_map(mux_cables)

        assert mux_server_to_port_map == result

    def test_check_neighbor_consistency_soc_ip_neighbor(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.1": "aa:bb:cc:dd:ee:ff"}  # SOC IP neighbor
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {"Ethernet4": "prefix-route"}
        mac_to_port_name_map = {"aa:bb:cc:dd:ee:ff": "Ethernet4"}
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.1/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005c0"
            }
        ]
        asic_neigh_table = \
            ["{\"ip\":\"192.168.0.1\",\"rif\":\"oid:0x6000000000671\"," +
             "\"switch_id\":\"oid:0x21000000000000\"}"]
        asic_nexthop_table = \
            {'oid:0x40000000005c0': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_IP', 'nexthop_id': 'oid:0x40000000005c0'}}
        mux_server_to_port_map = {}
        expected_output = \
            ["192.168.0.1", "aa:bb:cc:dd:ee:ff", "Ethernet4", "active", "no", "yes", "yes", "NEIGHBOR", "consistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_multiple_neighbors_with_soc_ips(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {
            "192.168.0.2": "ee:86:d8:46:7d:01",  # Server IP
            "192.168.0.1": "aa:bb:cc:dd:ee:ff",  # SOC IP
            "192.168.0.5": "11:22:33:44:55:66"   # Regular neighbor
        }
        mux_states = {"Ethernet4": "active", "Ethernet8": "standby"}
        hw_mux_states = {"Ethernet4": "active", "Ethernet8": "standby"}
        port_neighbor_modes = {"Ethernet4": "prefix-route", "Ethernet8": "prefix-route"}
        mac_to_port_name_map = {
            "ee:86:d8:46:7d:01": "Ethernet4",
            "aa:bb:cc:dd:ee:ff": "Ethernet4",
            "11:22:33:44:55:66": "Ethernet8"
        }
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.2/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005c0"
            },
            {
                "route_details": "{\"dest\":\"192.168.0.1/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005c0"
            },
            {
                "route_details": "{\"dest\":\"192.168.0.5/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005ae"
            }
        ]
        asic_neigh_table = [
            "{\"ip\":\"192.168.0.2\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}",
            "{\"ip\":\"192.168.0.1\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}",
            "{\"ip\":\"192.168.0.5\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}"
        ]
        asic_nexthop_table = {
            'oid:0x40000000005c0': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_IP',
                                    'nexthop_id': 'oid:0x40000000005c0'},
            'oid:0x40000000005ae': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_TUNNEL_ENCAP',
                                    'nexthop_id': 'oid:0x40000000005ae'}
        }
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_outputs = [
            ["192.168.0.1", "aa:bb:cc:dd:ee:ff", "Ethernet4", "active", "no", "yes", "yes", "NEIGHBOR", "consistent"],
            ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "active", "no", "yes", "yes", "NEIGHBOR", "consistent"],
            ["192.168.0.5", "11:22:33:44:55:66", "Ethernet8", "standby", "no", "yes", "yes", "TUNNEL", "consistent"]
        ]
        expected_log_output = tabulate.tabulate(
            expected_outputs,
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_no_fdb_entry(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:02": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_consistent_neighbor_mux_active(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {"Ethernet4": "prefix-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.2/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005c0"
            }
        ]
        asic_neigh_table = [
                            "{\"ip\":\"192.168.0.2\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":" +
                            "\"oid:0x21000000000000\" }"
                           ]
        asic_nexthop_table = \
            {'oid:0x40000000005c0': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_IP', 'nexthop_id': 'oid:0x40000000005c0'}}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "active", "no", "yes", "yes", "NEIGHBOR",
                           "consistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_inconsistent_neighbor_mux_active_no_asic_neighbor(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {"Ethernet4": "prefix-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.2/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005ae"
            }
        ]
        asic_neigh_table = []
        asic_nexthop_table = \
            {'oid:0x40000000005ae': {'nexthop_type': 'SAI_NEXT_HOP_TYPE_TUNNEL_ENCAP',
                                     'nexthop_id': 'oid:0x40000000005ae'}}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "active", "no", "no", "yes", "TUNNEL",
                           "inconsistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_PREFIX_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]
        expected_log_error_calls = [call("Found neighbors that are inconsistent with mux states: %s", ["192.168.0.2"])]
        expected_log_error_calls.extend([call("Failed PREFIX-ROUTE neighbors:")])
        expected_log_error_calls.extend([call(line) for line in expected_log_output])

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is False
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_has_calls(expected_log_error_calls)

    def test_check_neighbor_consistency_inconsistent_neighbor_mux_active_asic_tunnel_route(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.2/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005ae"
            }
        ]
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "active", "no", "no", "yes", "inconsistent"]
        expected_log_output = tabulate.tabulate([expected_output],
                                                headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
                                                tablefmt="simple").split("\n")
        expected_log_warn_calls = \
            [call("================================================================================")]
        expected_log_warn_calls.extend([call("Neighbors in HOST-ROUTE mode:")])
        expected_log_warn_calls.extend([call("=====================================================================" +
                                             "===========")])
        expected_log_warn_calls.extend([call(line) for line in expected_log_output])
        expected_log_error_calls = [call("Found neighbors that are inconsistent with mux states: %s", ["192.168.0.2"])]
        expected_log_error_calls.extend([call("Failed HOST-ROUTE neighbors:")])
        expected_log_error_calls.extend([call(line) for line in expected_log_output])

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is False
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_has_calls(expected_log_error_calls)

    def test_check_neighbor_consistency_inconsistent_neighbor_mux_active_in_toggle(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "standby"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "active", "yes", "no", "no", "inconsistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_consistent_neighbor_mux_standby(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "standby"}
        hw_mux_states = {"Ethernet4": "standby"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.2/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005ae"
            }
        ]
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "standby", "no", "no", "yes", "consistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_inconsistent_neighbor_mux_standby_no_asic_tunnel_route(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "standby"}
        hw_mux_states = {"Ethernet4": "standby"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "standby", "no", "no", "no", "inconsistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]
        expected_log_error_calls = [call("Found neighbors that are inconsistent with mux states: %s", ["192.168.0.2"])]
        expected_log_error_calls.extend([call("Failed HOST-ROUTE neighbors:")])
        expected_log_error_calls.extend([call(line) for line in expected_log_output])

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is False
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_has_calls(expected_log_error_calls)

    def test_check_neighbor_consistency_inconsistent_neighbor_mux_standby_asic_neighbor(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "standby"}
        hw_mux_states = {"Ethernet4": "standby"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = ["{\"ip\":\"192.168.0.2\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":" +
                            "\"oid:0x21000000000000\"}"]
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "standby", "no", "yes", "no",
                           "inconsistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call("===========================================================================" +
                                        "=====")]
        expected_log_warn_calls.extend([call("Neighbors in HOST-ROUTE mode:")])
        expected_log_warn_calls.extend([call("=======================================================================" +
                                             "=========")])
        expected_log_warn_calls.extend([call(line) for line in expected_log_output])
        expected_log_error_calls = [call("Found neighbors that are inconsistent with mux states: %s", ["192.168.0.2"])]
        expected_log_error_calls.extend([call("Failed HOST-ROUTE neighbors:")])
        expected_log_error_calls.extend([call(line) for line in expected_log_output])

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is False
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_has_calls(expected_log_error_calls)

    def test_check_neighbor_consistency_inconsistent_neighbor_mux_standby_in_toggle(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01"}
        mux_states = {"Ethernet4": "standby"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {"Ethernet4": "host-route"}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.2", "ee:86:d8:46:7d:01", "Ethernet4", "standby", "yes", "no", "no", "inconsistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_zero_mac_neighbor(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.102": "00:00:00:00:00:00"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = [
            {
                "route_details": "{\"dest\":\"192.168.0.102/32\",\"switch_id\":\"oid:0x21000000000000\"," +
                                 "\"vr\":\"oid:0x3000000000024\"}",
                "nexthop_id": "oid:0x40000000005ae"
            }
        ]
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.102", "00:00:00:00:00:00", "N/A", "N/A", "N/A", "no", "yes", "consistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_zero_mac_expired_neighbor(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.102": "00:00:00:00:00:00"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = ["{\"ip\":\"192.168.0.102\",\"rif\":\"oid:0x6000000000671\",\"switch_id\":\"oid:0x21000000000000\"}"]
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.102", "00:00:00:00:00:00", "N/A", "N/A", "N/A", "yes", "no", "consistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is True
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_not_called()

    def test_check_neighbor_consistency_inconsistent_zero_mac_neighbor(self, mock_log_functions):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"192.168.0.102": "00:00:00:00:00:00"}
        mux_states = {"Ethernet4": "active"}
        hw_mux_states = {"Ethernet4": "active"}
        port_neighbor_modes = {}
        mac_to_port_name_map = {"ee:86:d8:46:7d:01": "Ethernet4"}
        asic_route_table = []
        asic_neigh_table = []
        asic_nexthop_table = {}
        mux_server_to_port_map = {"192.168.0.2": "Ethernet4"}
        expected_output = ["192.168.0.102", "00:00:00:00:00:00", "N/A", "N/A", "N/A", "no", "no", "inconsistent"]
        expected_log_output = tabulate.tabulate(
            [expected_output],
            headers=dualtor_neighbor_check.NEIGHBOR_ATTRIBUTES_HOST_ROUTE,
            tablefmt="simple"
        ).split("\n")
        expected_log_warn_calls = [call(line) for line in expected_log_output]
        expected_log_error_calls = [call("Found neighbors that are inconsistent with mux states: %s", ["192.168.0.102"])]
        expected_log_error_calls.extend([call("Failed HOST-ROUTE neighbors:")])
        expected_log_error_calls.extend([call(line) for line in expected_log_output])

        check_results = dualtor_neighbor_check.check_neighbor_consistency(
            neighbors,
            mux_states,
            hw_mux_states,
            mac_to_port_name_map,
            asic_route_table,
            asic_neigh_table,
            asic_nexthop_table,
            mux_server_to_port_map,
            port_neighbor_modes
        )
        res, _ = dualtor_neighbor_check.parse_check_results(check_results)

        assert res is False
        mock_log_warn.assert_has_calls(expected_log_warn_calls)
        mock_log_error.assert_has_calls(expected_log_error_calls)

    def test_identify_suspect_neighbors_filters_correctly(self, mock_log_functions):
        """Only non-zero-MAC, non-in-toggle, failing rows with a resolved port should be suspects."""
        zero = dualtor_neighbor_check.ZERO_MAC
        na = dualtor_neighbor_check.NOT_AVAILABLE
        check_results = [
            {"NEIGHBOR": "10.0.0.1", "MAC": "aa:bb:cc:dd:ee:01", "PORT": "Ethernet4",
             "IN_MUX_TOGGLE": False, "HWSTATUS": False},
            {"NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
             "IN_MUX_TOGGLE": False, "HWSTATUS": True},
            {"NEIGHBOR": "10.0.0.3", "MAC": "aa:bb:cc:dd:ee:03", "PORT": "Ethernet12",
             "IN_MUX_TOGGLE": True,  "HWSTATUS": False},
            {"NEIGHBOR": "10.0.0.4", "MAC": zero,                "PORT": "Ethernet16",
             "IN_MUX_TOGGLE": False, "HWSTATUS": False},
            {"NEIGHBOR": "10.0.0.5", "MAC": "aa:bb:cc:dd:ee:05", "PORT": na,
             "IN_MUX_TOGGLE": False, "HWSTATUS": False},
        ]
        suspects = dualtor_neighbor_check.identify_suspect_neighbors(check_results)
        assert suspects == [("10.0.0.1", "aa:bb:cc:dd:ee:01", "Ethernet4")]

    def test_detect_bouncing_detects_mac_move_and_neigh_change(self, mock_log_functions):
        """detect_bouncing should flag IPs whose IP->MAC or MAC->port mapping changed."""
        suspects = [
            ("10.0.0.1", "aa:bb:cc:dd:ee:01", "Ethernet4"),
            ("10.0.0.2", "aa:bb:cc:dd:ee:02", "Ethernet8"),
            ("10.0.0.3", "aa:bb:cc:dd:ee:03", "Ethernet12"),
            ("10.0.0.4", "aa:bb:cc:dd:ee:04", "Ethernet16"),
            ("10.0.0.5", "aa:bb:cc:dd:ee:05", "Ethernet20"),
        ]
        first_neighbors = {
            "10.0.0.1": "aa:bb:cc:dd:ee:01", "10.0.0.2": "aa:bb:cc:dd:ee:02",
            "10.0.0.3": "aa:bb:cc:dd:ee:03", "10.0.0.4": "aa:bb:cc:dd:ee:04",
            "10.0.0.5": "aa:bb:cc:dd:ee:05",
        }
        first_mac_to_port = {
            "aa:bb:cc:dd:ee:01": "Ethernet4",  "aa:bb:cc:dd:ee:02": "Ethernet8",
            "aa:bb:cc:dd:ee:03": "Ethernet12", "aa:bb:cc:dd:ee:04": "Ethernet16",
            "aa:bb:cc:dd:ee:05": "Ethernet20",
        }
        second_neighbors = {
            "10.0.0.1": "aa:bb:cc:dd:ee:01",
            "10.0.0.2": "aa:bb:cc:dd:ee:02",
            "10.0.0.3": "aa:bb:cc:dd:ee:99",
            "10.0.0.5": "aa:bb:cc:dd:ee:05",
        }
        second_mac_to_port = {
            "aa:bb:cc:dd:ee:01": "Ethernet4",
            "aa:bb:cc:dd:ee:02": "Ethernet36",
            "aa:bb:cc:dd:ee:03": "Ethernet12",
            "aa:bb:cc:dd:ee:99": "Ethernet12",
        }
        bouncing = dualtor_neighbor_check.detect_bouncing(
            suspects, first_neighbors, first_mac_to_port, second_neighbors, second_mac_to_port)
        assert bouncing == {"10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5"}

    def test_detect_bouncing_no_change_returns_empty(self, mock_log_functions):
        suspects = [("10.0.0.1", "aa:bb:cc:dd:ee:01", "Ethernet4")]
        first_neighbors = {"10.0.0.1": "aa:bb:cc:dd:ee:01"}
        first_mac_to_port = {"aa:bb:cc:dd:ee:01": "Ethernet4"}
        bouncing = dualtor_neighbor_check.detect_bouncing(
            suspects, first_neighbors, first_mac_to_port,
            dict(first_neighbors), dict(first_mac_to_port))
        assert bouncing == set()

    def test_parse_check_results_bouncing_demoted_to_non_failure(self, mock_log_functions):
        """A row whose IP is in bouncing_ips must not be reported as a failure;
        its HWSTATUS column is rendered as 'bouncing' for operator visibility."""
        mock_log_error, _, _, _ = mock_log_functions
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
            "MUX_STATE": "standby", "IN_MUX_TOGGLE": False,
            "NEIGHBOR_IN_ASIC": True, "TUNNEL_IN_ASIC": False, "HWSTATUS": False,
            "_NEIGHBOR_MODE": "host-route",
        }]
        res, failed_neighbors = dualtor_neighbor_check.parse_check_results(check_results, bouncing_ips={"10.0.0.2"})
        assert res is True
        assert failed_neighbors == []
        assert check_results[0]["HWSTATUS"] == dualtor_neighbor_check.BOUNCING
        mock_log_error.assert_not_called()

    def test_parse_check_results_without_bouncing_still_fails(self, mock_log_functions):
        """Sanity: same inconsistent row, no bouncing_ips -> still a failure."""
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
            "MUX_STATE": "standby", "IN_MUX_TOGGLE": False,
            "NEIGHBOR_IN_ASIC": True, "TUNNEL_IN_ASIC": False, "HWSTATUS": False,
            "_NEIGHBOR_MODE": "host-route",
        }]
        res, failed_neighbors = dualtor_neighbor_check.parse_check_results(check_results)
        assert res is False
        assert failed_neighbors == check_results
        assert check_results[0]["HWSTATUS"] == "inconsistent"

    def test_recheck_bouncing_neighbors_disabled_when_delay_zero(self, mock_log_functions):
        """delay_ms=0 must short-circuit: no sleep, no re-read, empty set."""
        check_results = [{
            "NEIGHBOR": "10.0.0.1", "MAC": "aa:bb:cc:dd:ee:01", "PORT": "Ethernet4",
            "IN_MUX_TOGGLE": False, "HWSTATUS": False,
        }]
        with patch("dualtor_neighbor_check.time.sleep") as mock_sleep, \
                patch("dualtor_neighbor_check.read_tables_from_db") as mock_full_read, \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db") as mock_read:
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, {}, {}, MagicMock(), {}, delay_ms=0)
        assert bouncing == set()
        mock_sleep.assert_not_called()
        mock_full_read.assert_not_called()
        mock_read.assert_not_called()

    def test_recheck_bouncing_neighbors_no_suspects_skips_reread(self, mock_log_functions):
        """No failing rows -> no sleep, no re-read."""
        check_results = [{
            "NEIGHBOR": "10.0.0.1", "MAC": "aa:bb:cc:dd:ee:01", "PORT": "Ethernet4",
            "IN_MUX_TOGGLE": False, "HWSTATUS": True,
        }]
        with patch("dualtor_neighbor_check.time.sleep") as mock_sleep, \
                patch("dualtor_neighbor_check.read_tables_from_db") as mock_full_read, \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db") as mock_read:
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, {}, {}, MagicMock(), {}, delay_ms=300)
        assert bouncing == set()
        mock_sleep.assert_not_called()
        mock_full_read.assert_not_called()
        mock_read.assert_not_called()

    def test_recheck_bouncing_neighbors_detects_mac_move(self, mock_log_functions):
        """A failing row whose MAC moves ports between the two reads is bouncing."""
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
            "IN_MUX_TOGGLE": False, "HWSTATUS": False,
        }]
        first_neighbors = {"10.0.0.2": "aa:bb:cc:dd:ee:02"}
        first_mac_to_port = {"aa:bb:cc:dd:ee:02": "Ethernet8"}

        second_neighbors = {"10.0.0.2": "aa:bb:cc:dd:ee:02"}
        second_asic_fdb = {"aa:bb:cc:dd:ee:02": "3a00000000064c"}
        if_oid_to_port_name_map = {"3a00000000064c": "Ethernet36"}
        appl_db = MagicMock()

        with patch("dualtor_neighbor_check.time.sleep") as mock_sleep, \
                patch("dualtor_neighbor_check.read_tables_from_db") as mock_full_read, \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db",
                      return_value=(second_neighbors, second_asic_fdb)) as mock_read:
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, first_neighbors, first_mac_to_port,
                appl_db, if_oid_to_port_name_map, delay_ms=300)
        assert bouncing == {"10.0.0.2"}
        mock_sleep.assert_called_once_with(0.3)
        mock_full_read.assert_not_called()
        mock_read.assert_called_once_with(appl_db, ["10.0.0.2"], ["aa:bb:cc:dd:ee:02"])

    def test_recheck_bouncing_neighbors_stable_returns_empty(self, mock_log_functions):
        """A failing row whose bindings are stable across reads is NOT bouncing
        (this is the RC2-persistent path we still want to fail loudly)."""
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
            "IN_MUX_TOGGLE": False, "HWSTATUS": False,
        }]
        first_neighbors = {"10.0.0.2": "aa:bb:cc:dd:ee:02"}
        first_mac_to_port = {"aa:bb:cc:dd:ee:02": "Ethernet8"}
        second_asic_fdb = {"aa:bb:cc:dd:ee:02": "3a00000000064b"}
        if_oid_to_port_name_map = {"3a00000000064b": "Ethernet8"}

        with patch("dualtor_neighbor_check.time.sleep"), \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db",
                      return_value=(dict(first_neighbors), second_asic_fdb)):
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, first_neighbors, first_mac_to_port,
                MagicMock(), if_oid_to_port_name_map, delay_ms=300)
        assert bouncing == set()

    @pytest.mark.parametrize("cached, script_exists", [(False, False), (True, False), (True, True)])
    def test_read_recheck_tables_normalizes_bridge_ports(self, mock_log_functions, cached, script_exists):
        script_sha1 = "c53fd5eaad68be1e66a2fe80cd20a9cb18c91259"
        appl_db = MagicMock()
        appl_db.get.return_value = script_sha1 if cached else None
        neighbors = {"192.168.0.2": "ee:86:d8:46:7d:01", "fc02:1000::2": "ee:86:d8:46:7d:01"}
        asic_fdb = {"ee:86:d8:46:7d:01": "oid:0x3a00000000064b"}
        replies = []
        expected_calls = []
        if cached:
            replies.append("1" if script_exists else "0")
            expected_calls.append(call("sudo redis-cli SCRIPT EXISTS %s" % script_sha1))
        if not cached or not script_exists:
            replies.append(script_sha1)
            expected_calls.append(call("sudo redis-cli SCRIPT LOAD \"%s\"" % dualtor_neighbor_check.RECHECK_READ_SCRIPT))
        replies.append(json.dumps({"neighbors": neighbors, "asic_fdb": asic_fdb}))
        expected_calls.append(call(
            "sudo redis-cli EVALSHA %s 0 2 192.168.0.2 fc02:1000::2 ee:86:d8:46:7d:01" % script_sha1
        ))

        with patch("dualtor_neighbor_check.run_command", side_effect=replies) as mock_run:
            result = dualtor_neighbor_check.read_recheck_tables_from_db(
                appl_db, list(neighbors), list(asic_fdb)
            )

        assert result == (neighbors, {"ee:86:d8:46:7d:01": "3a00000000064b"})
        assert mock_run.call_args_list == expected_calls
        appl_db.get.assert_called_once_with(dualtor_neighbor_check.RECHECK_READ_SCRIPT_CONFIG_DB_KEY)
        if not cached or not script_exists:
            appl_db.set.assert_called_once_with(dualtor_neighbor_check.RECHECK_READ_SCRIPT_CONFIG_DB_KEY, script_sha1)
        else:
            appl_db.set.assert_not_called()

    @pytest.mark.parametrize("empty_table", [{}, []])
    def test_read_recheck_tables_empty_bindings(self, mock_log_functions, empty_table):
        with patch("dualtor_neighbor_check.load_db_read_script", return_value="cached"), \
                patch("dualtor_neighbor_check.redis_cli", return_value=json.dumps(
                    {"neighbors": empty_table, "asic_fdb": empty_table}
                )):
            assert dualtor_neighbor_check.read_recheck_tables_from_db(
                MagicMock(), ["192.168.0.2"], ["ee:86:d8:46:7d:01"]
            ) == ({}, {})

    @pytest.mark.parametrize("table_name", ["neighbors", "asic_fdb"])
    @pytest.mark.parametrize("invalid_table", [None, False, [1]])
    def test_read_recheck_tables_rejects_invalid_tables(self, mock_log_functions, table_name, invalid_table):
        tables = {"neighbors": {}, "asic_fdb": {}}
        tables[table_name] = invalid_table
        with patch("dualtor_neighbor_check.load_db_read_script", return_value="cached"), \
                patch("dualtor_neighbor_check.redis_cli", return_value=json.dumps(tables)), \
                pytest.raises(TypeError, match="Invalid %s table" % table_name):
            dualtor_neighbor_check.read_recheck_tables_from_db(MagicMock(), ["192.168.0.2"], [])

    @pytest.mark.parametrize("response, error", [("not json", json.JSONDecodeError), ("{}", KeyError)])
    def test_read_recheck_tables_propagates_bad_response(self, mock_log_functions, response, error):
        with patch("dualtor_neighbor_check.load_db_read_script", return_value="cached"), \
                patch("dualtor_neighbor_check.redis_cli", return_value=response), \
                pytest.raises(error):
            dualtor_neighbor_check.read_recheck_tables_from_db(MagicMock(), ["192.168.0.2"], [])

    def test_db_read_scripts_survive_command_splitting(self):
        for script in (dualtor_neighbor_check.DB_READ_SCRIPT, dualtor_neighbor_check.RECHECK_READ_SCRIPT):
            command = "sudo redis-cli SCRIPT LOAD \"%s\"" % script
            assert shlex.split(command) == ["sudo", "redis-cli", "SCRIPT", "LOAD", script]

    def test_recheck_reads_only_suspects_with_unique_macs(self, mock_log_functions):
        appl_db = MagicMock()
        mac = "aa:bb:cc:dd:ee:02"
        check_results = [
            {"NEIGHBOR": "10.0.0.2", "MAC": mac, "PORT": "Ethernet8",
             "IN_MUX_TOGGLE": False, "HWSTATUS": False},
            {"NEIGHBOR": "fc02:1000::2", "MAC": mac, "PORT": "Ethernet8",
             "IN_MUX_TOGGLE": False, "HWSTATUS": False},
            {"NEIGHBOR": "10.0.0.3", "MAC": "aa:bb:cc:dd:ee:03", "PORT": "Ethernet12",
             "IN_MUX_TOGGLE": False, "HWSTATUS": True},
        ]
        neighbors = {"10.0.0.2": mac, "fc02:1000::2": mac}
        with patch("dualtor_neighbor_check.time.sleep"), \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db",
                      return_value=(neighbors, {mac: "3a00000000064b"})) as mock_read:
            result = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, neighbors, {mac: "Ethernet8"},
                appl_db, {"3a00000000064b": "Ethernet8"}, 300
            )
        assert result == set()
        mock_read.assert_called_once_with(appl_db, ["10.0.0.2", "fc02:1000::2"], [mac])

    def test_recheck_propagates_redis_failure(self, mock_log_functions):
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
            "IN_MUX_TOGGLE": False, "HWSTATUS": False,
        }]
        with patch("dualtor_neighbor_check.time.sleep"), \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db",
                      side_effect=RuntimeError("Redis reread failed")), \
                pytest.raises(RuntimeError, match="Redis reread failed"):
            dualtor_neighbor_check.recheck_bouncing_neighbors(check_results, {}, {}, MagicMock(), {}, 300)

    @pytest.mark.parametrize("arguments, delay", [
        ([], 300), (["--recheck-delay-ms", "0"], 0), (["--recheck-delay-ms", "25"], 25)
    ])
    def test_parse_args_recheck_delay(self, arguments, delay):
        with patch("dualtor_neighbor_check.sys.argv", ["dualtor_neighbor_check.py"] + arguments):
            assert dualtor_neighbor_check.parse_args().recheck_delay_ms == delay

    def test_parse_args_rejects_negative_recheck_delay(self, capsys):
        with patch("dualtor_neighbor_check.sys.argv", ["dualtor_neighbor_check.py", "--recheck-delay-ms", "-1"]), \
                pytest.raises(SystemExit) as exc:
            dualtor_neighbor_check.parse_args()
        assert exc.value.code == 2
        assert "--recheck-delay-ms must be non-negative." in capsys.readouterr().err

    def test_parse_check_results_never_demotes_zero_mac(self, mock_log_functions):
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": dualtor_neighbor_check.ZERO_MAC, "PORT": "N/A",
            "MUX_STATE": "N/A", "IN_MUX_TOGGLE": "N/A", "NEIGHBOR_IN_ASIC": False,
            "TUNNEL_IN_ASIC": False, "HWSTATUS": False, "_NEIGHBOR_MODE": "host-route",
        }]
        result, failed = dualtor_neighbor_check.parse_check_results(check_results, bouncing_ips={"10.0.0.2"})
        assert result is False
        assert failed == check_results
        assert failed[0]["HWSTATUS"] == "inconsistent"

    @pytest.mark.parametrize("neighbor_mode", ["host-route", "prefix-route"])
    @pytest.mark.parametrize("include_stable, delay_ms", [(False, 300), (True, 300), (False, 0)])
    def test_main_rechecks_before_flushing(self, mock_log_functions, neighbor_mode, include_stable, delay_ms):
        mock_log_error, mock_log_warn, _, _ = mock_log_functions
        neighbors = {"10.0.0.2": "aa:bb:cc:dd:ee:02"}
        first_fdb = {"aa:bb:cc:dd:ee:02": "3a00000000064b"}
        second_fdb = {"aa:bb:cc:dd:ee:02": "3a00000000064c"}
        if_oid_to_port_name_map = {
            "3a00000000064b": "Ethernet8", "3a00000000064c": "Ethernet36", "3a00000000064d": "Ethernet4"
        }
        if include_stable:
            neighbors["10.0.0.3"] = "aa:bb:cc:dd:ee:03"
            first_fdb["aa:bb:cc:dd:ee:03"] = "3a00000000064d"
            second_fdb["aa:bb:cc:dd:ee:03"] = "3a00000000064d"
        mux_states = {"Ethernet8": "active", "Ethernet4": "active"}
        tables = (
            neighbors, mux_states, dict(mux_states),
            {port: neighbor_mode for port in mux_states}, first_fdb, [], [], {}
        )
        expected_failed = ["10.0.0.3"] if include_stable else (["10.0.0.2"] if delay_ms == 0 else [])

        with patch("dualtor_neighbor_check.sys.argv",
                   ["dualtor_neighbor_check.py", "--recheck-delay-ms", str(delay_ms)]), \
                patch("dualtor_neighbor_check.config_logging"), \
                patch("dualtor_neighbor_check.swsscommon.ConfigDBConnector"), \
                patch("dualtor_neighbor_check.daemon_base.db_connect"), \
                patch("dualtor_neighbor_check.is_dualtor", return_value=True), \
                patch("dualtor_neighbor_check.get_mux_cable_config", return_value={"Ethernet8": {}}), \
                patch("dualtor_neighbor_check.get_if_br_oid_to_port_name_map", return_value=if_oid_to_port_name_map), \
                patch("dualtor_neighbor_check.read_tables_from_db", return_value=tables) as mock_full_read, \
                patch("dualtor_neighbor_check.read_recheck_tables_from_db",
                      return_value=(neighbors, second_fdb)) as mock_recheck, \
                patch("dualtor_neighbor_check.flush_neighbor") as mock_flush, \
                patch("dualtor_neighbor_check.time.sleep") as mock_sleep:
            result = dualtor_neighbor_check.main()

        assert result == (1 if expected_failed else 0)
        assert mock_flush.call_args_list == [call(ip) for ip in expected_failed]
        assert mock_full_read.call_count == (2 if expected_failed else 1)
        assert mock_recheck.call_count == (mock_full_read.call_count if delay_ms else 0)
        expected_sleeps = [call(delay_ms / 1000.0)] if delay_ms else []
        if expected_failed:
            expected_sleeps += [call(dualtor_neighbor_check.POST_FLUSH_CHECK_DELAY_SEC)] + expected_sleeps
            mock_log_error.assert_any_call("Found neighbors that are inconsistent with mux states: %s", expected_failed)
            mock_log_error.assert_called_with("ALERT: post-flush dualtor neighbor check still found inconsistent neighbors.")
        else:
            mock_log_error.assert_not_called()
        assert mock_sleep.call_args_list == expected_sleeps
        if delay_ms:
            assert any("bouncing" in str(log_call) for log_call in mock_log_warn.call_args_list)
