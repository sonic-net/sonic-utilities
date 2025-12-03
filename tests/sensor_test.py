import sys
import os
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

import show.main as show

class TestVoltage(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_platform_voltage(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["voltage"])
        print(result.output)
        expected = """\
  Sensor    Voltage    High TH    Low TH    Crit High TH    Crit Low TH    Warning          Timestamp
--------  ---------  ---------  --------  --------------  -------------  ---------  -----------------
VSENSOR0     760 mV        852       684             872            664      False  20230704 17:38:04
VSENSOR1     759 mV        852       684             872            664      False  20230704 17:38:04
"""

        assert result.output == expected

    def test_show_platform_current(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["current"])
        print(result.output)
        expected = """\
  Sensor    Current    High TH    Low TH    Crit High TH    Crit Low TH    Warning          Timestamp
--------  ---------  ---------  --------  --------------  -------------  ---------  -----------------
ISENSOR0     410 mA        440       320             460            300      False  20230704 17:38:04
ISENSOR1     360 mA        440       320             460            300      False  20230704 17:38:04
"""

        assert result.output == expected

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

