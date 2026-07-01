import importlib
import os
import sys
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from utilities_common.db import Db

from .pfcwd_input import pfcwd_test_vectors as test_vectors

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
    def test_pfcwd_start_default_32_ports(self, mock_os):
        """Test start_default on 32-port system: multiply=1, detection/restoration=200, poll=200ms"""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # Patch PORT table to have exactly 32 ports so multiply = (32-1)//32+1 = 1
        original_get_table = db.cfgdb.get_table

        def mock_get_table_32_ports(table):
            if table == 'PORT':
                return {'Ethernet%d' % i: {} for i in range(0, 32 * 4, 4)}  # 32 ports
            return original_get_table(table)

        mock_os.geteuid.return_value = 0
        with patch.object(db.cfgdb, 'get_table', side_effect=mock_get_table_32_ports):
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
        assert result.output == test_vectors.pfcwd_show_start_default_32_ports

    @patch('pfcwd.main.os')
    def test_pfcwd_start_default_512_ports(self, mock_os):
        """Test start_default on 512-port system: multiply=16, detection/restoration=3200, poll=1000ms"""
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        # Patch PORT table to have 512 ports so multiply = (512-1)//32+1 = 16
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
        assert result.output == test_vectors.pfcwd_show_start_default_512_ports

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

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        import mock_tables.mock_single_asic
        importlib.reload(mock_tables.mock_single_asic)
        import pfcwd.main
        importlib.reload(pfcwd.main)


class TestPfcwdstatClear(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        scripts_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts'
        )
        import importlib.util
        from importlib.machinery import SourceFileLoader
        script_path = os.path.join(scripts_path, "pfcwdstat")
        loader = SourceFileLoader("pfcwdstat", script_path)
        spec = importlib.util.spec_from_loader("pfcwdstat", loader, origin=script_path)
        cls.pfcwdstat = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.pfcwdstat)
        sys.modules['pfcwdstat'] = cls.pfcwdstat

    def _make_mock_db(self, queue_name_map=None, counters=None):
        mock_db = MagicMock()
        mock_db.COUNTERS_DB = 'COUNTERS_DB'

        def get_all(db_id, key):
            if key == 'COUNTERS_QUEUE_NAME_MAP':
                return queue_name_map
            return (counters or {}).get(key)

        mock_db.get_all.side_effect = get_all
        return mock_db

    def _pfc_wd_counters(self, value='100', status='operational'):
        """Return a COUNTERS hash with all PFC_WD stats fields set to value."""
        fields = {f: value for f in self.pfcwdstat.PFC_WD_STATS_FIELDS}
        fields['PFC_WD_STATUS'] = status
        return fields

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_single_queue(self, mock_connector):
        oid = 'oid:0x100'
        mock_db = self._make_mock_db(
            queue_name_map={'Ethernet0:3': oid},
            counters={'COUNTERS:' + oid: self._pfc_wd_counters()},
        )
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        assert mock_db.set.call_count == len(self.pfcwdstat.PFC_WD_STATS_FIELDS)
        assert all(c[0][1] == 'COUNTERS:' + oid for c in mock_db.set.call_args_list)
        assert all(c[0][3] == '0' for c in mock_db.set.call_args_list)

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_multiple_queues(self, mock_connector):
        oid_map = {
            'Ethernet0:3': 'oid:0x100',
            'Ethernet0:4': 'oid:0x200',
            'Ethernet4:3': 'oid:0x300',
        }
        counters = {
            'COUNTERS:' + oid: self._pfc_wd_counters()
            for oid in oid_map.values()
        }
        mock_db = self._make_mock_db(queue_name_map=oid_map, counters=counters)
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        num_fields = len(self.pfcwdstat.PFC_WD_STATS_FIELDS)
        assert mock_db.set.call_count == num_fields * 3
        counter_keys = {c[0][1] for c in mock_db.set.call_args_list}
        assert counter_keys == {
            'COUNTERS:oid:0x100',
            'COUNTERS:oid:0x200',
            'COUNTERS:oid:0x300',
        }

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_no_entries(self, mock_connector):
        mock_db = self._make_mock_db(queue_name_map=None)
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        mock_db.set.assert_not_called()

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_skips_queue_without_pfc_wd_stats(self, mock_connector):
        """Queues that have no PFC_WD_QUEUE_STATS_* fields are not touched."""
        oid = 'oid:0x100'
        mock_db = self._make_mock_db(
            queue_name_map={'Ethernet0:3': oid},
            counters={'COUNTERS:' + oid: {'SAI_QUEUE_STAT_PACKETS': '500'}},
        )
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        mock_db.set.assert_not_called()

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_stale_stats_no_pfc_wd_table(self, mock_connector):
        """Stats from inactive queues (PFC_WD_TABLE gone, STATUS=N/A) are cleared.

        An implementation that enumerates queues via PFC_WD_TABLE|* would bail
        with 'No PFC Watchdog stats found.' when pfcwd is no longer active,
        leaving residual stats that 'show pfcwd stats' continues to render.
        """
        oid = 'oid:0x15000000000032'
        # No PFC_WD_STATUS field — mirrors the inactive/stale state
        stale_counters = {f: '100' for f in self.pfcwdstat.PFC_WD_STATS_FIELDS}
        mock_db = self._make_mock_db(
            queue_name_map={'Ethernet32:4': oid},
            counters={'COUNTERS:' + oid: stale_counters},
        )
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        assert mock_db.set.call_count == len(self.pfcwdstat.PFC_WD_STATS_FIELDS)
        assert all(c[0][1] == 'COUNTERS:' + oid for c in mock_db.set.call_args_list)
        assert all(c[0][3] == '0' for c in mock_db.set.call_args_list)

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_skips_active_storm_queue(self, mock_connector):
        """A queue with an active storm (PFC_WD_STATUS == 'stormed') is not
        cleared, so the in-flight DEADLOCK_DETECTED/RESTORED pair is not split
        (which would otherwise leave RESTORED > DETECTED once the storm ends)."""
        oid = 'oid:0x100'
        mock_db = self._make_mock_db(
            queue_name_map={'Ethernet384:3': oid},
            counters={'COUNTERS:' + oid: self._pfc_wd_counters(status='stormed')},
        )
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        mock_db.set.assert_not_called()

    @patch('pfcwdstat.SonicV2Connector')
    def test_clear_mixed_storm_and_idle(self, mock_connector):
        """Stormed queues are skipped while non-stormed queues are still cleared
        in the same invocation."""
        stormed_oid = 'oid:0x100'
        idle_oid = 'oid:0x200'
        mock_db = self._make_mock_db(
            queue_name_map={'Ethernet0:3': stormed_oid, 'Ethernet4:3': idle_oid},
            counters={
                'COUNTERS:' + stormed_oid: self._pfc_wd_counters(status='stormed'),
                'COUNTERS:' + idle_oid: self._pfc_wd_counters(status='operational'),
            },
        )
        mock_connector.return_value = mock_db

        self.pfcwdstat.clear_stats()

        # Only the non-stormed (idle) queue is zeroed.
        assert mock_db.set.call_count == len(self.pfcwdstat.PFC_WD_STATS_FIELDS)
        assert all(c[0][1] == 'COUNTERS:' + idle_oid for c in mock_db.set.call_args_list)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
