import os
import sys

from click.testing import CliRunner

from tests.fdbshow_input.fdbshow_masic_test_vectors import show_mac_masic_asic0_output, test_data
from tests.utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestFdbshowMultiAsic(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        print("SETUP")

    def test_show_mac_masic_asic0(self):
        return_code, result = get_result_and_return_code([
            'fdbshow', '-n', 'asic0'
        ])
        print("return_code: {}".format(return_code))
        print("result: {}".format(result))
        assert return_code == 0
        assert result == show_mac_masic_asic0_output

        self.command_executor(test_data["show_mac_masic_asic0"])

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        print("TEARDOWN")

    @staticmethod
    def command_executor(test_case_data):
        import show.main as show
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["mac"], test_case_data["args"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == test_case_data["expected_output"]
