import dualtor_neighbor_check
import json
import pytest
import shlex
import sys
import subprocess
import tabulate

from unittest.mock import call
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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results)

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
        res = dualtor_neighbor_check.parse_check_results(check_results, bouncing_ips={"10.0.0.2"})
        assert res is True
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
        res = dualtor_neighbor_check.parse_check_results(check_results)
        assert res is False
        assert check_results[0]["HWSTATUS"] == "inconsistent"

    def test_recheck_bouncing_neighbors_disabled_when_delay_zero(self, mock_log_functions):
        """delay_ms=0 must short-circuit: no sleep, no re-read, empty set."""
        check_results = [{
            "NEIGHBOR": "10.0.0.1", "MAC": "aa:bb:cc:dd:ee:01", "PORT": "Ethernet4",
            "IN_MUX_TOGGLE": False, "HWSTATUS": False,
        }]
        with patch("dualtor_neighbor_check.time.sleep") as mock_sleep, \
                patch("dualtor_neighbor_check.read_tables_from_db") as mock_read:
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, {}, {}, MagicMock(), {}, delay_ms=0)
        assert bouncing == set()
        mock_sleep.assert_not_called()
        mock_read.assert_not_called()

    def test_recheck_bouncing_neighbors_no_suspects_skips_reread(self, mock_log_functions):
        """No failing rows -> no sleep, no re-read."""
        check_results = [{
            "NEIGHBOR": "10.0.0.1", "MAC": "aa:bb:cc:dd:ee:01", "PORT": "Ethernet4",
            "IN_MUX_TOGGLE": False, "HWSTATUS": True,
        }]
        with patch("dualtor_neighbor_check.time.sleep") as mock_sleep, \
                patch("dualtor_neighbor_check.read_tables_from_db") as mock_read:
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, {}, {}, MagicMock(), {}, delay_ms=300)
        assert bouncing == set()
        mock_sleep.assert_not_called()
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
        second_asic_fdb = {"aa:bb:cc:dd:ee:02": "oid:0xbridgeport_eth36"}
        if_oid_to_port_name_map = {"oid:0xbridgeport_eth36": "Ethernet36"}

        with patch("dualtor_neighbor_check.time.sleep"), \
                patch("dualtor_neighbor_check.read_tables_from_db",
                      return_value=(second_neighbors, {}, {}, {}, second_asic_fdb, [], [], {})):
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, first_neighbors, first_mac_to_port,
                MagicMock(), if_oid_to_port_name_map, delay_ms=300)
        assert bouncing == {"10.0.0.2"}

    def test_recheck_bouncing_neighbors_stable_returns_empty(self, mock_log_functions):
        """A failing row whose bindings are stable across reads is NOT bouncing
        (this is the RC2-persistent path we still want to fail loudly)."""
        check_results = [{
            "NEIGHBOR": "10.0.0.2", "MAC": "aa:bb:cc:dd:ee:02", "PORT": "Ethernet8",
            "IN_MUX_TOGGLE": False, "HWSTATUS": False,
        }]
        first_neighbors = {"10.0.0.2": "aa:bb:cc:dd:ee:02"}
        first_mac_to_port = {"aa:bb:cc:dd:ee:02": "Ethernet8"}
        second_asic_fdb = {"aa:bb:cc:dd:ee:02": "oid:0xbridgeport_eth8"}
        if_oid_to_port_name_map = {"oid:0xbridgeport_eth8": "Ethernet8"}

        with patch("dualtor_neighbor_check.time.sleep"), \
                patch("dualtor_neighbor_check.read_tables_from_db",
                      return_value=(dict(first_neighbors), {}, {}, {}, second_asic_fdb, [], [], {})):
            bouncing = dualtor_neighbor_check.recheck_bouncing_neighbors(
                check_results, first_neighbors, first_mac_to_port,
                MagicMock(), if_oid_to_port_name_map, delay_ms=300)
        assert bouncing == set()
