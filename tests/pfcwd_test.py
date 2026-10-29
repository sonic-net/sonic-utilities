import importlib
import json
import os
import sys
from unittest.mock import patch, MagicMock

from click.testing import CliRunner
from swsscommon import swsscommon

from utilities_common.db import Db

from .pfcwd_input import pfcwd_test_vectors as test_vectors


_orig_sonic_get_all = swsscommon.SonicV2Connector.get_all


def _hw_get_all(self, db_id, key):
    """Hardware mode, with every configured port programmed at 200 ms."""
    if db_id == 'STATE_DB' and key == 'PFC_WD_STATE_TABLE|PFC_WD':
        return {
            'RECOVERY_MECHANISM': 'HARDWARE',
            'DETECTION_TIME_MIN': '100',
            'DETECTION_TIME_MAX': '5000',
            'RESTORATION_TIME_MIN': '100',
            'RESTORATION_TIME_MAX': '60000',
            'DLR_PACKET_ACTION': 'drop',
        }

    if db_id == 'STATE_DB' and key.startswith('PFC_WD_HW_STATE|'):
        return {
            'status': 'configured',
            'hw_detection_time': '200',
            'hw_restoration_time': '200',
        }

    return _orig_sonic_get_all(self, db_id, key)


def _hw_get_all_narrow(self, db_id, key):
    """Hardware mode with ranges narrower than the CLI's own limits."""
    if db_id == 'STATE_DB' and key == 'PFC_WD_STATE_TABLE|PFC_WD':
        return {
            'RECOVERY_MECHANISM': 'HARDWARE',
            'DETECTION_TIME_MIN': '100',
            'DETECTION_TIME_MAX': '1500',
            'RESTORATION_TIME_MIN': '100',
            'RESTORATION_TIME_MAX': '1000',
            'DLR_PACKET_ACTION': 'drop',
        }
    return _hw_get_all(self, db_id, key)


def _hw_get_all_zero_ranges(self, db_id, key):
    """Hardware mode where SAI reported 0-0 ranges."""
    if db_id == 'STATE_DB' and key == 'PFC_WD_STATE_TABLE|PFC_WD':
        return {
            'RECOVERY_MECHANISM': 'HARDWARE',
            'DETECTION_TIME_MIN': '0',
            'DETECTION_TIME_MAX': '0',
            'RESTORATION_TIME_MIN': '0',
            'RESTORATION_TIME_MAX': '0',
        }
    return _hw_get_all(self, db_id, key)


def _hw_get_all_forward(self, db_id, key):
    """Hardware mode with the switch-level action set to forward."""
    if db_id == 'STATE_DB' and key == 'PFC_WD_STATE_TABLE|PFC_WD':
        return {'RECOVERY_MECHANISM': 'HARDWARE', 'DLR_PACKET_ACTION': 'forward'}
    return _hw_get_all(self, db_id, key)


def _hw_get_all_rx_only(self, db_id, key):
    """Hardware mode where Ethernet4:3 has only RX counts."""
    oid = self.get('COUNTERS_DB', 'COUNTERS_QUEUE_NAME_MAP', 'Ethernet4:3')
    if db_id == 'COUNTERS_DB' and key == 'COUNTERS:' + oid:
        return {
            'PFC_WD_STATUS': 'operational',
            'PFC_WD_QUEUE_STATS_RX_PACKETS': '5',
            'PFC_WD_QUEUE_STATS_RX_DROPPED_PACKETS': '5',
        }
    return _hw_get_all(self, db_id, key)


def _hw_get_all_no_ranges(self, db_id, key):
    """Hardware mode without reported ranges."""
    if db_id == 'STATE_DB' and key == 'PFC_WD_STATE_TABLE|PFC_WD':
        return {'RECOVERY_MECHANISM': 'HARDWARE'}
    return _hw_get_all(self, db_id, key)

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "pfcwd")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestPfcwd(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        print("SETUP")

    def test_pfcwd_show_config(self):
        self.executor(test_vectors.testData['pfcwd_show_config'])

    def test_pfcwd_show_config_single_port(self):
        self.executor(test_vectors.testData['pfcwd_show_config_single_port'])

    def test_pfcwd_show_config_multi_port(self):
        self.executor(test_vectors.testData['pfcwd_show_config_multi_port'])

    def test_pfcwd_show_config_invalid_port(self):
        self.executor(test_vectors.testData['pfcwd_show_config_invalid_port'])

    def test_pfcwd_show_stats(self):
        self.executor(test_vectors.testData['pfcwd_show_stats'])

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    def test_pfcwd_show_stats_hw_mode(self):
        import pfcwd.main as pfcwd
        result = CliRunner().invoke(pfcwd.cli.commands["show"].commands["stats"], [], obj=Db())
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_stats_hw_mode_output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_rx_only)
    def test_pfcwd_show_stats_hw_mode_rx_only_queue_is_empty(self):
        import pfcwd.main as pfcwd
        result = CliRunner().invoke(pfcwd.cli.commands["show"].commands["stats"], [], obj=Db())
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_stats_hw_mode_rx_only_output

    def test_pfcwd_show_stats_single_queue(self):
        self.executor(test_vectors.testData['pfcwd_show_stats_single_queue'])

    def test_pfcwd_show_stats_multi_queue(self):
        self.executor(test_vectors.testData['pfcwd_show_stats_multi_queue'])

    def test_pfcwd_show_stats_invalid_queue(self):
        self.executor(test_vectors.testData['pfcwd_show_stats_invalid_queue'])

    def executor(self, testcase):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        for input in testcase:
            exec_cmd = ""
            if len(input['cmd']) == 1:
                exec_cmd = pfcwd.cli.commands[input['cmd'][0]]
            else:
                exec_cmd = pfcwd.cli.commands[input['cmd'][0]].commands[input['cmd'][1]]

            if 'db' in input and input['db']:
                result = runner.invoke(
                    exec_cmd, input['args'], obj=db
                )
            else:
                result = runner.invoke(exec_cmd, input['args'])

            print(result.exit_code)
            print(result.output)

            if input['rc'] == 0:
                assert result.exit_code == 0
            else:
                assert result.exit_code != 0

            if 'rc_msg' in input:
                assert input['rc_msg'] in result.output

            if 'rc_output' in input:
                assert result.output == input['rc_output']

    @patch('pfcwd.main.os')
    def test_pfcwd_start_ports_valid(self, mock_os):
        # pfcwd start --action drop --restoration-time 200 Ethernet0 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "101",
                "Ethernet0", "102"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_config_output_pass

    @patch('pfcwd.main.os')
    def test_pfcwd_enable_history_ports_valid(self, mock_os):
        # pfcwd pfc_stat_history enable Ethernet0
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # initially history is disabled
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["pfc_stat_history"],
            [
                "enable",
                "Ethernet0"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # now valid port is enabled
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_enable_history_config_output_pass

    @patch('pfcwd.main.os')
    def test_pfcwd_start_actions(self, mock_os):
        # pfcwd start --action forward --restoration-time 200 Ethernet0 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        # always skip Ethernet8 because 'pfc_enable' not configured for this port
        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "301",
                "all", "302"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_action_forward_output

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "alert", "--restoration-time", "501",
                "all", "502"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_action_alert_output

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "601",
                "all", "602"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_action_drop_output

        result = runner.invoke(
        pfcwd.cli.commands["start_default"],
            [],
            obj=db
        )

        assert result.exit_code == 0

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )

        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_default

    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_multiply_boundary(self, mock_os):
        """32 PFC-enabled ports stay on multiply=1; 33 cross to multiply=2."""
        mock_os.geteuid.return_value = 0

        db = Db()
        ports = ['Ethernet%d' % (i * 4) for i in range(32)]
        result = self._run_start_default_with_ports(db, ports)
        assert result.exit_code == 0
        # (32-1)//32+1 = 1
        assert db.cfgdb.get_entry("PFC_WD", "Ethernet0").get("detection_time") == '200'
        assert db.cfgdb.get_entry("PFC_WD", "GLOBAL").get("POLL_INTERVAL") == '200'

        db = Db()
        ports = ['Ethernet%d' % (i * 4) for i in range(33)]
        result = self._run_start_default_with_ports(db, ports)
        assert result.exit_code == 0
        # (33-1)//32+1 = 2
        assert db.cfgdb.get_entry("PFC_WD", "Ethernet0").get("detection_time") == '400'
        assert db.cfgdb.get_entry("PFC_WD", "GLOBAL").get("POLL_INTERVAL") == '400'

    @staticmethod
    def _run_start_default_with_ports(db, pfc_ports, non_pfc_ports=(), extra_ports=()):
        """Run start_default with a synthetic port layout.

        start_default scales its timers off the ports it actually configures, which are the
        DEVICE_NEIGHBOR ports carrying a PORT_QOS_MAP 'pfc_enable'.

        Args:
            db (obj): Db instance to run against.
            pfc_ports (list): Ports in DEVICE_NEIGHBOR with pfc_enable set.
            non_pfc_ports (list): Ports in DEVICE_NEIGHBOR without pfc_enable, i.e. ports that
                are candidates for configuration but get skipped.
            extra_ports (list): Ports present only in PORT, without pfc_enable.
        """
        import pfcwd.main as pfcwd

        original_get_table = db.cfgdb.get_table
        original_get_entry = db.cfgdb.get_entry
        no_pfc = list(non_pfc_ports) + list(extra_ports)

        def mock_get_table(table):
            if table == 'PORT':
                return {port: {} for port in list(pfc_ports) + no_pfc}
            if table == 'DEVICE_NEIGHBOR':
                return {port: {} for port in list(pfc_ports) + list(non_pfc_ports)}
            if table == 'PORT_QOS_MAP':
                return {port: {'pfc_enable': '3,4'} for port in pfc_ports}
            return original_get_table(table)

        def mock_get_entry(table, key):
            if table == 'PORT_QOS_MAP':
                if key in pfc_ports:
                    return {'pfc_enable': '3,4'}
                if key in no_pfc:
                    return {}
            return original_get_entry(table, key)

        with patch.object(db.cfgdb, 'get_table', side_effect=mock_get_table), \
                patch.object(db.cfgdb, 'get_entry', side_effect=mock_get_entry):
            return CliRunner().invoke(pfcwd.cli.commands["start_default"], [], obj=db)

    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_512_ports(self, mock_os):
        """Test start_default on 512-port system: multiply=16, detection/restoration=3200, poll=1000ms"""
        db = Db()
        mock_os.geteuid.return_value = 0

        # 512 PFC-enabled ports so multiply = (512-1)//32+1 = 16. Asserted on CONFIG_DB rather
        # than rendered output, which would be 512 rows.
        ports = ['Ethernet%d' % i for i in range(512)]
        result = self._run_start_default_with_ports(db, ports)
        assert result.exit_code == 0

        entry = db.cfgdb.get_entry("PFC_WD", "Ethernet0")
        assert entry.get("detection_time") == '3200'
        assert entry.get("restoration_time") == '3200'
        # 200 * 16 = 3200 exceeds MAX_POLL_INTERVAL_TIME, so poll interval clamps to 1000.
        assert db.cfgdb.get_entry("PFC_WD", "GLOBAL").get("POLL_INTERVAL") == '1000'

    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_ignores_pfc_ineligible_ports(self, mock_os):
        """Ports without pfc_enable must not inflate the timer scaling.

        They are skipped by verify_pfc_enable_status_per_port, so counting them makes the
        timers larger on behalf of ports that never receive a watchdog: 64 PFC-enabled ports
        alongside 3 ineligible ones scaled off all 67 PORT entries, giving multiply=3 (600ms)
        instead of the correct multiply=2 (400ms).
        """
        db = Db()
        mock_os.geteuid.return_value = 0

        pfc_ports = ['Ethernet%d' % (i * 4) for i in range(64)]
        ineligible = ['Ethernet256', 'Ethernet260', 'Ethernet-Rec0']
        result = self._run_start_default_with_ports(db, pfc_ports, extra_ports=ineligible)
        assert result.exit_code == 0

        # (64-1)//32+1 = 2 -> 400ms. Counting all 67 PORT entries would give 3 -> 600ms.
        entry = db.cfgdb.get_entry("PFC_WD", "Ethernet0")
        assert entry.get("detection_time") == '400'
        assert entry.get("restoration_time") == '400'
        assert db.cfgdb.get_entry("PFC_WD", "GLOBAL").get("POLL_INTERVAL") == '400'

        # The ineligible ports get no watchdog at all.
        for port in ineligible:
            assert db.cfgdb.get_entry("PFC_WD", port) == {}

    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_skips_neighbor_without_pfc_enable(self, mock_os):
        """A configuration candidate that lacks pfc_enable must not be counted.

        Unlike the ports in the test above, this port *is* in DEVICE_NEIGHBOR, so it reaches
        the count as a candidate and is excluded only by the pfc_enable check itself. Sitting
        on the 32/33 boundary makes that exclusion observable: counting it would give
        multiply=2 (400ms) instead of multiply=1 (200ms).
        """
        db = Db()
        mock_os.geteuid.return_value = 0

        pfc_ports = ['Ethernet%d' % (i * 4) for i in range(32)]
        no_pfc = 'Ethernet900'
        result = self._run_start_default_with_ports(db, pfc_ports, non_pfc_ports=[no_pfc])
        assert result.exit_code == 0

        # 32 counted, not 33: (32-1)//32+1 = 1 -> 200ms.
        entry = db.cfgdb.get_entry("PFC_WD", "Ethernet0")
        assert entry.get("detection_time") == '200'
        assert entry.get("restoration_time") == '200'
        assert db.cfgdb.get_entry("PFC_WD", "GLOBAL").get("POLL_INTERVAL") == '200'

        # It is still walked by the configuration loop, so it warns and gets no watchdog.
        assert "PFC is not enabled on port: {}".format(no_pfc) in result.output
        assert db.cfgdb.get_entry("PFC_WD", no_pfc) == {}

    @patch('pfcwd.main.os')
    def test_pfcwd_start_history(self, mock_os):
        # pfcwd start all 600 --restoration-time 601 --pfc-stat-history
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # initially history disabled on all ports
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        mock_os.geteuid.return_value = 0
        # start wd with history flag
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "all", "600", "--restoration-time", "601",
                "--pfc-stat-history"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_history_output

    @patch('pfcwd.main.os')
    def test_pfcwd_pfc_not_enabled(self, mock_os):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        mock_os.geteuid.return_value = 0

        result = runner.invoke(
        pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "601", "--pfc-stat-history",
                "Ethernet8", "602"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert test_vectors.pfc_is_not_enabled == result.output

    @patch('pfcwd.main.os')
    def test_pfcwd_enable_history_pfc_not_enabled(self, mock_os):
        # pfcwd pfc_stat_history enable Ethernet8
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        # attempt to enable history on Ethernet without pfc
        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["pfc_stat_history"],
            [
                "enable",
                "Ethernet8"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert test_vectors.pfc_is_not_enabled == result.output

        # verify no change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )

        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == test_vectors.pfcwd_show_config_output

    def test_pfcwd_start_ports_invalid(self):
        # pfcwd start --action drop --restoration-time 200 Ethernet0 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "101", "--pfc-stat-history",
                "Ethernet1000", "102"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == test_vectors.show_pfc_config_invalid_options_fail

    def test_pfcwd_enable_history_ports_invalid(self):
        # pfcwd pfc_stat_history enable Ethernet1000
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.pfcwd_show_config_output

        # attempt to enable history on invalid port
        result = runner.invoke(
            pfcwd.cli.commands["pfc_stat_history"],
            [
                "enable",
                "Ethernet1000"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == test_vectors.show_pfc_config_invalid_options_fail

        # config unchanged
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == test_vectors.pfcwd_show_config_output

    def test_pfcwd_show_stats_check_storm_no_storms(self):
        """ Test --check-storm flag when no storms are present """
        import pfcwd.main as pfcwd
        from unittest.mock import patch
        runner = CliRunner()
        db = Db()

        # Mock the collect_stats method to simulate no storms
        def mock_collect_stats_no_storm(self, empty, queues, storm_only=False):
            # Create fake table data with only operational queues
            self.table = [
                ['Ethernet0:3', 'operational', '2/2', '100/100', '100/100', '0/0', '0/0'],
                ['Ethernet4:3', 'operational', '3/3', '150/150', '150/150', '0/0', '0/0'],
                ['Ethernet8:4', 'operational', '1/1', '50/50', '50/50', '0/0', '0/0']
            ]

        with patch.object(pfcwd.PfcwdCli, 'collect_stats', mock_collect_stats_no_storm):
            # Test with no storms - should exit 0
            result = runner.invoke(
                pfcwd.cli.commands["show"].commands["stats"],
                ["--check-storm"],
                obj=db
            )
            print("No storms test - exit code:", result.exit_code)
            print("No storms test - output:", result.output)
            assert result.exit_code == 0
            assert result.output == ""  # Should be silent when checking storms

    def test_pfcwd_show_stats_check_storm_with_storms(self):
        """ Test --check-storm flag when storms are present """
        import pfcwd.main as pfcwd
        from unittest.mock import patch
        runner = CliRunner()
        db = Db()

        # Mock the collect_stats method to simulate storm detection
        def mock_collect_stats_with_storm(self, empty, queues, storm_only=False):
            # Create fake table data with a stormed queue
            self.table = [
                ['Ethernet0:3', 'stormed', '1/0', '100/300', '100/300', '0/200', '0/200']
            ]

        with patch.object(pfcwd.PfcwdCli, 'collect_stats', mock_collect_stats_with_storm):
            result = runner.invoke(
                pfcwd.cli.commands["show"].commands["stats"],
                ["--check-storm"],
                obj=db
            )
            print("With storms test - exit code:", result.exit_code)
            print("With storms test - output:", result.output)
            assert result.exit_code == 1
            assert result.output == ""  # Should be silent when checking storms

    def test_pfcwd_show_stats_check_storm_mixed_status(self):
        """ Test --check-storm flag with mixed operational and stormed queues """
        import pfcwd.main as pfcwd
        from unittest.mock import patch
        runner = CliRunner()
        db = Db()

        # Mock the collect_stats method to simulate mixed queue states
        def mock_collect_stats_mixed(self, empty, queues, storm_only=False):
            # Create fake table data with mixed states - should still exit 1 if ANY storm detected
            self.table = [
                ['Ethernet0:3', 'operational', '2/2', '100/100', '100/100', '0/0', '0/0'],
                ['Ethernet4:3', 'stormed', '1/0', '100/300', '100/300', '0/200', '0/200'],
                ['Ethernet8:4', 'operational', '0/0', '50/50', '50/50', '0/0', '0/0']
            ]

        with patch.object(pfcwd.PfcwdCli, 'collect_stats', mock_collect_stats_mixed):
            result = runner.invoke(
                pfcwd.cli.commands["show"].commands["stats"],
                ["--check-storm"],
                obj=db
            )
            print("Mixed states test - exit code:", result.exit_code)
            print("Mixed states test - output:", result.output)
            assert result.exit_code == 1  # Should exit 1 if ANY storms detected
            assert result.output == ""

    def test_pfcwd_show_stats_normal_output_unchanged(self):
        """ Test that normal stats output is unchanged when not using --check-storm """
        import pfcwd.main as pfcwd
        from unittest.mock import patch
        runner = CliRunner()
        db = Db()

        # Mock the collect_stats method to ensure consistent test output
        def mock_collect_stats_normal(self, empty, queues, storm_only=False):
            # Create fake table data with mixed states (like normal operation)
            self.table = [
                ['Ethernet0:3', 'operational', '2/2', '100/100', '100/100', '0/0', '0/0'],
                ['Ethernet4:3', 'operational', '3/3', '150/150', '150/150', '0/0', '0/0']
            ]

        with patch.object(pfcwd.PfcwdCli, 'collect_stats', mock_collect_stats_normal):
            # Test normal stats command (without --check-storm) - should work as before
            result = runner.invoke(
                pfcwd.cli.commands["show"].commands["stats"],
                obj=db
            )
            print("Normal output test - exit code:", result.exit_code)
            print("Normal output test - output length:", len(result.output))
            assert result.exit_code == 0
            # Should have normal tabulated output (not empty)
            assert len(result.output) > 0
            assert "QUEUE" in result.output  # Should contain table headers

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=0))
    def test_pfcwd_stop_hardware_mode_stormed_blocked(self):
        """HW mode: stop is refused while Ethernet0:3 and Ethernet8:4 are stormed."""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["stop"],
            [],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert "Cannot stop PFC watchdog while queues are in stormed state" in result.output
        assert "Ethernet0:3" in result.output
        assert "Ethernet8:4" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=0))
    def test_pfcwd_stop_hardware_mode_no_storm(self):
        """HW mode: stop succeeds for Ethernet4, which has no stormed queue."""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["stop"],
            ["Ethernet4"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_hardware_mode(self, mock_os):
        """HW mode: unscaled 200 ms defaults on 512 ports and no PFC_WD|GLOBAL write."""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        original_get_table = db.cfgdb.get_table

        def mock_get_table_512_ports(table):
            if table == 'PORT':
                return {'Ethernet%d' % i: {} for i in range(512)}
            return original_get_table(table)

        mock_os.geteuid.return_value = 0
        with patch.object(db.cfgdb, 'get_table', side_effect=mock_get_table_512_ports):
            result = runner.invoke(
                pfcwd.cli.commands["start_default"],
                [],
                obj=db
            )
        assert result.exit_code == 0

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_default_hw_mode
        # the software watchdog's POLL_INTERVAL is removed
        assert 'POLL_INTERVAL' not in db.cfgdb.get_entry("PFC_WD", "GLOBAL")

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_forward)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_hardware_mode_action_mismatch(self, mock_os):
        # start_default writes drop; the hardware is on forward with ports configured
        import pfcwd.main as pfcwd
        mock_os.geteuid.return_value = 0
        db = Db()
        before = db.cfgdb.get_table("PFC_WD")
        result = CliRunner().invoke(pfcwd.cli.commands["start_default"], [], obj=db)
        assert result.exit_code == 1
        assert "Error: Action mismatch" in result.output
        assert db.cfgdb.get_table("PFC_WD") == before

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_hardware_mode_keeps_big_red_switch(self, mock_os):
        import pfcwd.main as pfcwd
        mock_os.geteuid.return_value = 0
        db = Db()
        db.cfgdb.set_entry("PFC_WD", "GLOBAL", {'POLL_INTERVAL': '600', 'BIG_RED_SWITCH': 'enable'})
        result = CliRunner().invoke(pfcwd.cli.commands["start_default"], [], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("PFC_WD", "GLOBAL") == {'BIG_RED_SWITCH': 'enable'}

    def test_pfcwd_show_config_json_single_asic(self):
        import pfcwd.main as pfcwd
        result = CliRunner().invoke(pfcwd.cli.commands["show"].commands["config"], ["--json"], obj=Db())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mode"] == "software"
        assert data["poll_interval"] == "600"
        assert data["big_red_switch"] is None

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")


class TestMultiAsicPfcwdShow(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()
        import pfcwd.main
        importlib.reload(pfcwd.main)

    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=8))
    def test_pfcwd_start_nonroot(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "601",
                "all", "602"
            ],
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == 'Root privileges are required for this operation\n'

    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=8))
    def test_pfcwd_stop_nonroot(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands['stop'],
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == 'Root privileges are required for this operation\n'

    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=8))
    def test_pfcwd_start_default_nonroot(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands['start_default'],
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == 'Root privileges are required for this operation\n'

    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=8))
    def test_pfcwd_counter_poll_nonroot(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands['counter_poll'], ['enable'],
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == 'Root privileges are required for this operation\n'

    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=8))
    def test_pfcwd_big_red_switch_nonroot(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands['big_red_switch'], ['enable'],
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == 'Root privileges are required for this operation\n'

    @patch('pfcwd.main.os.geteuid', MagicMock(return_value=8))
    def test_pfcwd_pfc_stat_history_nonroot(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands['pfc_stat_history'], ['enable', 'all'],
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == 'Root privileges are required for this operation\n'

    def test_pfcwd_stats_all(self):
        import pfcwd.main as pfcwd
        print(pfcwd.__file__)
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["stats"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfcwd_stats_all

    def test_pfcwd_stats_with_queues(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["stats"],
            [
                "Ethernet0:3", "Ethernet4:15", "Ethernet-BP0:13",
                "Ethernet-BP260:10", "InvalidQueue"
            ]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfcwd_stats_with_queues

    def test_pfcwd_config_all(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfc_config_all

    def test_pfcwd_config_with_ports(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            ["Ethernet0", "Ethernet-BP0", "Ethernet-BP256", "InvalidPort"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfcwd_config_with_ports

    @patch('pfcwd.main.os')
    def test_pfcwd_start_ports_masic_valid(self, mock_os):
        # pfcwd start --action forward --restoration-time 200 Ethernet0 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()
        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.show_pfc_config_all

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "101",
                "Ethernet0", "Ethernet-BP4", "102"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfc_config_start_pass

    @patch('pfcwd.main.os')
    def test_pfcwd_enable_history_ports_masic_valid(self, mock_os):
        # pfcwd pfc_stat_history enable Ethernet0, Ethernet-BP4
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()
        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.show_pfc_config_all

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["pfc_stat_history"],
            [
                "enable",
                "Ethernet0", "Ethernet-BP4"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfc_config_enable_history_pass

    @patch('pfcwd.main.os')
    def test_pfcwd_start_actions_masic(self, mock_os):
        # pfcwd start --action drop --restoration-time 200 Ethernet0 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()
        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.show_pfc_config_all

        # always skip Ethernet-BP260 because 'pfc_enable' not configured for this port
        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "301",
                "all", "302"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfc_config_start_action_drop_masic

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "alert", "--restoration-time", "401",
                "all", "402"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfc_config_start_action_alert_masic

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "701",
                "all", "702"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.show_pfc_config_start_action_forward_masic

    @patch('pfcwd.main.os')
    def test_pfcwd_start_history_masic(self, mock_os):
        # pfcwd start all 600 --restoration-time 601 --pfc-stat-history
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # initially history disabled on all ports
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.show_pfc_config_all

        mock_os.geteuid.return_value = 0
        # start wd with history flag
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "all", "600", "--restoration-time", "601",
                "--pfc-stat-history"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        # get config after the change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_start_history_output_masic

    def test_pfcwd_start_ports_masic_invalid(self):
        # --action drop --restoration-time 200 Ethernet0 Ethernet500 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "101", "--pfc-stat-history",
                "Ethernet0", "Ethernet-500", "102"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == test_vectors.show_pfc_config_invalid_options_fail_masic

        # get config after the command, config shouldn't change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == test_vectors.show_pfc_config_all

    def test_pfcwd_enable_history_ports_masic_invalid(self):
        # pfcwd pfc_stat_history enable Ethernet0 Ethernet-500
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["pfc_stat_history"],
            [
                "enable",
                "Ethernet0", "Ethernet-500",
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == test_vectors.show_pfc_config_invalid_options_fail_masic

        # get config after the command, config shouldn't change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == test_vectors.show_pfc_config_all

    @patch('pfcwd.main.os')
    def test_pfcwd_pfc_not_enabled_masic(self, mock_os):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
        pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "601", "--pfc-stat-history",
                "Ethernet-BP260", "602"
            ],
            obj=db
        )

        assert result.exit_code == 0
        assert test_vectors.pfc_is_not_enabled_masic == result.output

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )

        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == test_vectors.show_pfc_config_all

    @patch('pfcwd.main.os')
    def test_pfcwd_enable_history_pfc_not_enabled_masic(self, mock_os):
        # pfcwd pfc_stat_history enable Ethernet-BP260
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # get initial config
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.output == test_vectors.show_pfc_config_all

        # attempt to enable history on Ethernet without pfc
        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["pfc_stat_history"],
            [
                "enable",
                "Ethernet-BP260"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert test_vectors.pfc_is_not_enabled_masic == result.output

        # verify no change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )

        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == test_vectors.show_pfc_config_all

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    def test_pfcwd_show_config_hardware_mode(self):
        """HW mode: the software-mode table under a recovery mode line."""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_vectors.pfcwd_show_config_hw_mode

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    def test_pfcwd_show_config_hardware_mode_json(self):
        """HW mode --json: mode, numeric ranges and per-port hw_* fields."""
        import pfcwd.main as pfcwd
        import json
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            ["--json"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mode"] == "hardware"
        assert data["hw_detection_time_ms"] == {"min": 100, "max": 5000}
        assert data["hw_restoration_time_ms"] == {"min": 100, "max": 60000}
        # PFC_WD|GLOBAL is per ASIC
        assert data["poll_interval"] == {"asic0": "199", "asic1": "199"}
        assert data["big_red_switch"] == {"asic0": "enable", "asic1": "enable"}
        port = data["ports"]["Ethernet0"]
        assert port["action"] == "drop"
        assert port["detection_time"] == "200"
        assert port["restoration_time"] == "200"
        assert port["hw_detection_time"] == "200"
        assert port["hw_restoration_time"] == "200"
        assert port["hw_status"] == "configured"

    def test_pfcwd_show_config_software_mode_json(self):
        """SW mode --json: mode=software and no hw_* keys anywhere."""
        import pfcwd.main as pfcwd
        import json
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            ["--json"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mode"] == "software"
        assert "hw_detection_time_ms" not in data
        assert "hw_restoration_time_ms" not in data
        assert data["poll_interval"] == {"asic0": "199", "asic1": "199"}
        for port_cfg in data["ports"].values():
            assert "hw_status" not in port_cfg
            assert "hw_detection_time" not in port_cfg

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_hint_points_to_config(self, mock_os):
        """In HW mode the start hint references show pfcwd config."""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
            pfcwd.cli.commands["start"],
            ["--action", "drop", "--restoration-time", "600", "Ethernet0", "600"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert "Run 'show pfcwd config' to verify hardware programming" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_action_override_multiple_ports_blocked(self, mock_os):
        """HW mode: a different action is refused while other ports are configured."""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        mock_os.geteuid.return_value = 0

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            ["--action", "drop", "--restoration-time", "600", "Ethernet0", "600"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            ["--action", "drop", "--restoration-time", "600", "Ethernet4", "600"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            ["--action", "forward", "--restoration-time", "600", "Ethernet-BP0", "600"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert "Error: Action mismatch" in result.output
        assert "Current global action: drop" in result.output
        assert "Requested action: forward" in result.output

    def _start(self, args):
        import pfcwd.main as pfcwd
        result = CliRunner().invoke(pfcwd.cli.commands["start"], args, obj=Db())
        print(result.output)
        return result

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_default_restoration(self, mock_os):
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "drop", "Ethernet0", "600"])
        assert result.exit_code == 0
        assert "default to 2 times detection time: 1200 ms" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_narrow)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_default_restoration_out_of_range(self, mock_os):
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "drop", "Ethernet0", "600"])
        assert result.exit_code == 1
        assert "restoration_time 1200ms is outside hardware supported range [100-1000]ms" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_narrow)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_detection_out_of_range(self, mock_os):
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "drop", "--restoration-time", "600", "Ethernet0", "1600"])
        assert result.exit_code == 1
        assert "detection_time 1600ms is outside hardware supported range [100-1500]ms" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_narrow)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_restoration_out_of_range(self, mock_os):
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "drop", "--restoration-time", "1200", "Ethernet0", "600"])
        assert result.exit_code == 1
        assert "restoration_time 1200ms is outside hardware supported range [100-1000]ms" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_no_ranges)
    def test_pfcwd_show_config_hw_mode_json_without_ranges(self):
        import pfcwd.main as pfcwd
        result = CliRunner().invoke(pfcwd.cli.commands["show"].commands["config"], ["--json"], obj=Db())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mode"] == "hardware"
        assert data["hw_detection_time_ms"] == {"min": None, "max": None}
        assert data["hw_restoration_time_ms"] == {"min": None, "max": None}

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_zero_ranges)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_zero_ranges(self, mock_os):
        # a zero-bound range is not checked
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "drop", "--restoration-time", "600", "Ethernet0", "600"])
        assert result.exit_code == 0

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_no_ranges)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_without_ranges(self, mock_os):
        # orchagent skips the range check when SAI did not report the ranges
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "drop", "--restoration-time", "1200", "Ethernet0", "1600"])
        assert result.exit_code == 0

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_action_change_on_all_ports(self, mock_os):
        # orchagent refuses each port while others keep the old action
        mock_os.geteuid.return_value = 0
        result = self._start(["--action", "forward", "--restoration-time", "600", "all", "600"])
        assert result.exit_code == 1
        assert "Error: Action mismatch" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all_forward)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_without_action_is_drop(self, mock_os):
        mock_os.geteuid.return_value = 0
        result = self._start(["--restoration-time", "600", "Ethernet-BP0", "600"])
        assert result.exit_code == 1
        assert "Current global action: forward" in result.output
        assert "Requested action: drop" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_start_hw_mode_action_change_on_only_port(self, mock_os):
        import pfcwd.main as pfcwd
        mock_os.geteuid.return_value = 0
        db = Db()
        for config_db in db.cfgdb_clients.values():
            for key in config_db.get_table('PFC_WD'):
                if key not in ('GLOBAL', 'Ethernet0'):
                    config_db.set_entry('PFC_WD', key, None)
        result = CliRunner().invoke(
            pfcwd.cli.commands["start"],
            ["--action", "forward", "--restoration-time", "600", "Ethernet0", "600"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert "Action mismatch" not in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_interval_hw_mode_refused(self, mock_os):
        import pfcwd.main as pfcwd
        mock_os.geteuid.return_value = 0
        result = CliRunner().invoke(pfcwd.cli.commands["interval"], ["200"], obj=Db())
        assert result.exit_code == 1
        assert "not supported with hardware based PFC watchdog" in result.output

    @patch.object(swsscommon.SonicV2Connector, 'get_all', new=_hw_get_all)
    @patch('pfcwd.main.os')
    def test_pfcwd_big_red_switch_hw_mode_refused(self, mock_os):
        import pfcwd.main as pfcwd
        mock_os.geteuid.return_value = 0
        db = Db()
        result = CliRunner().invoke(pfcwd.cli.commands["big_red_switch"], ["enable"], obj=db)
        assert result.exit_code == 1
        assert "not supported with hardware based PFC watchdog" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        import mock_tables.mock_single_asic
        importlib.reload(mock_tables.mock_single_asic)
        import pfcwd.main
        importlib.reload(pfcwd.main)
