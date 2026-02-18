import os
import sys
from importlib import reload

from click.testing import CliRunner

import show.main as show
from tests.bfd_input.bfd_masic_test_vectors import test_data

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestShowBfdMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

        # Set the database to mock multi-asic state
        from mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        from mock_tables import dbconnector
        dbconnector.load_namespace_config()

    def test_show_bfd_summary_masic_asic0(self):
        self.command_executor(test_data["show_bfd_summary_masic_asic0"])

    def test_show_bfd_summary_masic_all(self):
        self.command_executor(test_data["show_bfd_summary_masic_all"])

    def test_show_bfd_peer_masic_asic0(self):
        self.command_executor(test_data["show_bfd_peer_masic_asic0"])

    @classmethod
    def teardown_class(cls):
        # Reset the database to mock single-asic state
        from mock_tables import mock_single_asic
        reload(mock_single_asic)
        from mock_tables import dbconnector
        dbconnector.load_database_config()

        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

        print("TEARDOWN")

    @staticmethod
    def command_executor(test_case_data):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["bfd"].commands[test_case_data["cmd"]], args=test_case_data["args"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == test_case_data["expected_output"]
