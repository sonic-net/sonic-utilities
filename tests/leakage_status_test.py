import sys
import os
from click.testing import CliRunner
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)


class TestFan(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_platform_leakage_status(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["leakage"].commands["status"])
        print(result.output)
        expected = """\
    Name    Leaking
--------  ---------
leakage1         No
leakage2         No
leakage3        Yes
"""

        assert result.output == expected

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
