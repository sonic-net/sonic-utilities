import os

from click.testing import CliRunner
import show.main as show
import clear.main as clear
from .utils import get_result_and_return_code
from utilities_common.cli import UserCache

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_policer_counters_output = """\
  Policer    Total Packets    Total Bytes    Green Packets    Green Bytes\
    Yellow Packets    Yellow Bytes    Red Packets    Red Bytes
---------  ---------------  -------------  ---------------  -------------\
  ----------------  --------------  -------------  -----------
 policer0             4000           1000             3000           2000\
              8000            7000           6000         5000

"""

show_policer_counters_output_diff = """\
  Policer    Total Packets    Total Bytes    Green Packets    Green Bytes\
    Yellow Packets    Yellow Bytes    Red Packets    Red Bytes
---------  ---------------  -------------  ---------------  -------------\
  ----------------  --------------  -------------  -----------
 policer0                0              0                0              0\
                 0               0              0            0

"""


def del_cached_stats():
    cache = UserCache("policerstat")
    cache.remove_all()


def policer_clear(expected_output):
    del_cached_stats()

    return_code, result = get_result_and_return_code(
        ['policerstat', '-c']
    )

    assert return_code == 0

    return_code, result = get_result_and_return_code(
        ['policerstat']
    )

    result_stat = [s for s in result.split("\n") if "Last cached" not in s]
    expected = expected_output.split("\n")
    assert result_stat == expected
    del_cached_stats()


class TestPolicerstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        del_cached_stats()

    def test_policer_counters(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['policer'], ['policer0', '--counter'])
        assert result.exit_code == 0
        assert result.output == show_policer_counters_output

    def test_policerstat(self):
        return_code, result = get_result_and_return_code(['policerstat'])
        assert return_code == 0
        assert result == show_policer_counters_output

    def test_policer_counters_with_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['policercounters'], [])
        assert result.exit_code == 0
        assert result.output == "Cleared counters\n\n"
        result = runner.invoke(
            show.cli.commands["policer"],
            ["--counter"]
        )
        assert result.output == show_policer_counters_output_diff

    def test_policer_clear(self):
        policer_clear(show_policer_counters_output_diff)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        del_cached_stats()
