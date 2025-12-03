import sys
import os
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

import show.main as show

class TestFan(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_platform_fan(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["fan"])
        print(result.output)
        expected = """\
  Drawer    LED    FAN    Speed    Direction    Presence    Status          Timestamp
--------  -----  -----  -------  -----------  ----------  --------  -----------------
 drawer1    red   fan1      30%       intake     Present        OK  20200813 01:32:30
 drawer2  green   fan2      50%       intake     Present    Not OK  20200813 01:32:30
 drawer3  green   fan3      50%       intake     Present  Updating  20200813 01:32:30
"""

        assert result.output == expected

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

