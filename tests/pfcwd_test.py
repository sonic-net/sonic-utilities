import importlib
import os
import sys
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from utilities_common.db import Db

from .pfcwd_input.pfcwd_test_vectors import *

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "pfcwd")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestPfcwd(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_pfcwd_show_config(self):
        self.executor(testData['pfcwd_show_config'])

    def test_pfcwd_show_config_single_port(self):
        self.executor(testData['pfcwd_show_config_single_port'])

    def test_pfcwd_show_config_multi_port(self):
        self.executor(testData['pfcwd_show_config_multi_port'])

    def test_pfcwd_show_config_invalid_port(self):
        self.executor(testData['pfcwd_show_config_invalid_port'])

    def test_pfcwd_show_stats(self):
        self.executor(testData['pfcwd_show_stats'])

    def test_pfcwd_show_stats_single_queue(self):
        self.executor(testData['pfcwd_show_stats_single_queue'])

    def test_pfcwd_show_stats_multi_queue(self):
        self.executor(testData['pfcwd_show_stats_multi_queue'])

    def test_pfcwd_show_stats_invalid_queue(self):
        self.executor(testData['pfcwd_show_stats_invalid_queue'])

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
        assert result.output == pfcwd_show_config_output

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
        assert result.output == pfcwd_show_start_config_output_pass

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
        assert result.output == pfcwd_show_config_output

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
        assert result.output == pfcwd_show_start_action_forward_output

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
        assert result.output == pfcwd_show_start_action_alert_output

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
        assert result.output == pfcwd_show_start_action_drop_output

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
        assert result.output == pfcwd_show_start_default


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
        assert result.output == pfcwd_show_config_output

        mock_os.geteuid.return_value = 0

        result = runner.invoke(
        pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "601",
                "Ethernet8", "602"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        assert pfc_is_not_enabled == result.output


    def test_pfcwd_start_ports_invalid(self):
        # pfcwd start --action drop --restoration-time 200 Ethernet0 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "101",
                "Ethernet1000", "102"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == pfcwd_show_start_config_output_fail

    def test_pfcwd_show_stats_check_storm_no_storms(self):
        """ Test --check-storm flag when no storms are present """
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()
        
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
        runner = CliRunner()
        db = Db()
        
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

    def test_pfcwd_stats_all(self):
        import pfcwd.main as pfcwd
        print(pfcwd.__file__)
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["stats"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfcwd_stats_all

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
        assert result.output == show_pfcwd_stats_with_queues

    def test_pfcwd_config_all(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_config_all

    def test_pfcwd_config_with_ports(self):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            ["Ethernet0", "Ethernet-BP0", "Ethernet-BP256", "InvalidPort"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfcwd_config_with_ports

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
        assert result.output == show_pfc_config_all

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
        assert result.output == show_pfc_config_start_pass

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
        assert result.output == show_pfc_config_all

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
        assert result.output == show_pfc_config_start_action_drop_masic

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
        assert result.output == show_pfc_config_start_action_alert_masic

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
        assert result.output == show_pfc_config_start_action_forward_masic

    def test_pfcwd_start_ports_masic_invalid(self):
        # --action drop --restoration-time 200 Ethernet0 Ethernet500 200
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            pfcwd.cli.commands["start"],
            [
                "--action", "forward", "--restoration-time", "101",
                "Ethernet0", "Ethernet-500", "102"
            ],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_pfc_config_start_fail

        # get config after the command, config shouldn't change
        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )
        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == show_pfc_config_all

    @patch('pfcwd.main.os')
    def test_pfcwd_pfc_not_enabled_masic(self, mock_os):
        import pfcwd.main as pfcwd
        runner = CliRunner()
        db = Db()

        mock_os.geteuid.return_value = 0
        result = runner.invoke(
        pfcwd.cli.commands["start"],
            [
                "--action", "drop", "--restoration-time", "601",
                "Ethernet-BP260", "602"
            ],
            obj=db
        )

        assert result.exit_code == 0
        assert pfc_is_not_enabled_masic == result.output

        result = runner.invoke(
            pfcwd.cli.commands["show"].commands["config"],
            obj=db
        )

        print(result.output)
        assert result.exit_code == 0
        # same as original config
        assert result.output == show_pfc_config_all

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        import mock_tables.mock_single_asic
        importlib.reload(mock_tables.mock_single_asic)
        import pfcwd.main
        importlib.reload(pfcwd.main)
