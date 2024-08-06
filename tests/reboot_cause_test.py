import os
import sys
import textwrap
from unittest import mock

from click.testing import CliRunner

from .mock_tables import dbconnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)


import show.main as show

"""
    Note: The following 'show reboot-cause' commands simply call other SONiC
    CLI utilities, so the unit tests for the other utilities are expected
    to cover testing their functionality:

        show reboot-cause
        show reboot-cause history
"""

class TestShowRebootCause(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    # Test 'show reboot-cause' without previous-reboot-cause.json 
    def test_reboot_cause_no_history_file(self):
        expected_output = "Unknown\n"
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["reboot-cause"], [])
        assert result.output == expected_output

    # Test 'show reboot-cause' with user issued reboot
    def test_reboot_cause_user(self):
        expected_output = "User issued 'reboot' command [User: admin, Time: Thu Oct 22 03:11:08 UTC 2020]\n"

        with mock.patch("show.reboot_cause.read_reboot_cause_file", return_value={"comment": "", "gen_time": "2020_10_22_03_14_07", "cause": "reboot", "user": "admin", "time": "Thu Oct 22 03:11:08 UTC 2020"}):
            runner = CliRunner()
            result = runner.invoke(show.cli.commands["reboot-cause"], [])
            assert result.output == expected_output


    # Test 'show reboot-cause' with non-user issue reboot (hardware reboot-cause or unknown reboot-cause)
    def test_reboot_cause_non_user(self):
        expected_output = "Watchdog\n"

        with mock.patch("show.reboot_cause.read_reboot_cause_file", return_value={"comment": "N/A", "gen_time": "2020_10_22_03_15_08", "cause": "Watchdog", "user": "N/A", "time": "N/A"}):
            runner = CliRunner()
            result = runner.invoke(show.cli.commands["reboot-cause"], [])
            assert result.output == expected_output


    # Test 'show reboot-cause history'
    def test_reboot_cause_history(self):
        expected_output = """\
Name                 Cause        Time                          User    Comment
-------------------  -----------  ----------------------------  ------  ---------
2020_10_09_04_53_58  warm-reboot  Fri Oct  9 04:51:47 UTC 2020  admin   N/A
2020_10_09_02_33_06  reboot       Fri Oct  9 02:29:44 UTC 2020  admin   N/A
"""
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["reboot-cause"].commands["history"], [])
        print(result.output)
        assert result.output == expected_output

    # Test 'show reboot-cause history all'
    def test_reboot_cause_history_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["reboot-cause"].commands["history"], ["all"])
        print(result.output)

    # Test 'show reboot-cause history SWITCH'
    def test_reboot_cause_history_switch(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["reboot-cause"].commands["history"], ["SWITCH"])
        print(result.output)

    # Test 'show reboot-cause history DPU0'
    def test_reboot_cause_history_dpu(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["reboot-cause"].commands["history"], ["DPU0"])
        print(result.output)

    # Test 'show reboot-cause all'
    def test_reboot_cause_all(self):
        with mock.patch("show.reboot_cause.fetch_data_from_db",
                        return_value={
                            "comment": "",
                            "gen_time": "2020_10_22_03_14_07",
                            "device": "DPU0",
                            "cause": "reboot",
                            "user": "admin",
                            "time": "Thu Oct 22 03:11:08 UTC 2020"
                        }):
            runner = CliRunner()
            result = runner.invoke(show.cli.commands["reboot-cause"].commands["all"], [])
            print(result.output)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
