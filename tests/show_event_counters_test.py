import os
import sys
from click.testing import CliRunner
from utilities_common.db import Db
import show.main as show

class TestShowEventCounters(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_event_counters_show(self):
        from .mock_tables import dbconnector
        test_path = os.path.dirname(os.path.abspath(__file__))
        mock_db_path = os.path.join(test_path, "event_counters_input")
        jsonfile_counters = os.path.join(mock_db_path, "counters_db")
        dbconnector.dedicated_dbs['COUNTERS_DB'] = jsonfile_counters
        runner = CliRunner()
        db = Db()
        expected_output = """\
                   name    count
-----------------------  -------
          latency_in_ms        2
missed_by_slow_receiver        0
        missed_internal        0
        missed_to_cache        0
              published    40147
"""

        result = runner.invoke(show.cli.commands['event-counters'], [], obj=db)
        print(result.exit_code)
        print(result.output)
        dbconnector.dedicated_dbs['COUNTERS_DB'] = None
        assert result.exit_code == 0
        assert result.output == expected_output

