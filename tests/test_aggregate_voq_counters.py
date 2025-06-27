from click.testing import CliRunner
import show.main as show
import os
import json

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_queue_counters_voq = """\
                     Port    Voq    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes    Credit-WD-Del/pkts
-------------------------  -----  --------------  ---------------  -----------  ------------  --------------------
sonic-lc1|asic0|Ethernet0   VOQ0             129              855           10          1220                     0

                     Port    Voq    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes    Credit-WD-Del/pkts
-------------------------  -----  --------------  ---------------  -----------  ------------  --------------------
sonic-lc2|asic0|Ethernet4   VOQ1              18             2196           16          1952                     0

"""

show_queue_counters_voq_sys_port = """\
                     Port    Voq    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes    Credit-WD-Del/pkts
-------------------------  -----  --------------  ---------------  -----------  ------------  --------------------
sonic-lc2|asic0|Ethernet4   VOQ1              18             2196           16          1952                     0

"""

show_queue_counters_voq_json = {
  "sonic-lc1|asic0|Ethernet0": {
    "VOQ0": {
      "creditWDPkts": "0",
      "dropbytes": "1220",
      "droppacket": "10",
      "totalbytes": "855",
      "totalpacket": "129"
    },
    "time": "2025-04-07T15:57:11.881430"
  },
  "sonic-lc2|asic0|Ethernet4": {
    "VOQ1": {
      "creditWDPkts": "0",
      "dropbytes": "1952",
      "droppacket": "16",
      "totalbytes": "2196",
      "totalpacket": "18"
    },
    "time": "2025-04-07T15:57:11.881496"
  }
}


class TestAggVoq(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "1"
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        print("SETUP")

    def test_queue_voq_counters_aggregate(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["counters"],
            ["--voq"]
        )
        assert result.exit_code == 0
        assert result.output == show_queue_counters_voq

    def test_queue_voq_counters_aggregate_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["counters"],
            ["--voq", "--json"]
        )
        res = result.output
        res.replace("\n", "")
        res = json.loads(res)
        assert result.exit_code == 0
        for lc in res:
            for voq in res[lc]:
                if voq != "time":
                    for counter in res[lc][voq]:
                        assert res[lc][voq][counter] == show_queue_counters_voq_json[lc][voq][counter]

    def test_queue_voq_counters_aggregate_sys_port(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["counters"],
            ["sonic-lc2|asic0|Ethernet4", "--voq"]
        )
        assert result.exit_code == 0
        assert result.output == show_queue_counters_voq_sys_port

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        print("TEARDOWN")
