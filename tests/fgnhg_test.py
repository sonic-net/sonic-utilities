import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


show_fgnhg_hash_view_output="""\
FG NHG Prefix    Next Hop            Hash buckets
---------------  ------------------  ------------------------------
100.50.25.12/32  200.200.200.4       0   1   2   3   4   5   6   7
100.50.25.12/32  200.200.200.5       8   9   10  11  12  13  14  15
fc:5::/128       200:200:200:200::4  0   1   2   3   4   5   6   7
fc:5::/128       200:200:200:200::5  8   9   10  11  12  13  14  15
"""

show_fgnhgv4_hash_view_output="""\
FG NHG Prefix    Next Hop       Hash buckets
---------------  -------------  ------------------------------
100.50.25.12/32  200.200.200.4  0   1   2   3   4   5   6   7
100.50.25.12/32  200.200.200.5  8   9   10  11  12  13  14  15
"""

show_fgnhgv6_hash_view_output="""\
FG NHG Prefix    Next Hop            Hash buckets
---------------  ------------------  ------------------------------
fc:5::/128       200:200:200:200::4  0   1   2   3   4   5   6   7
fc:5::/128       200:200:200:200::5  8   9   10  11  12  13  14  15
"""

show_fgnhg_active_hops_output="""\
FG NHG Prefix    Active Next Hops
---------------  ------------------
100.50.25.12/32  200.200.200.4
                 200.200.200.5
fc:5::/128       200:200:200:200::4
                 200:200:200:200::5
"""

show_fgnhgv4_active_hops_output="""\
FG NHG Prefix    Active Next Hops
---------------  ------------------
100.50.25.12/32  200.200.200.4
                 200.200.200.5
"""

show_fgnhgv6_active_hops_output="""\
FG NHG Prefix    Active Next Hops
---------------  ------------------
fc:5::/128       200:200:200:200::4
                 200:200:200:200::5
"""



class TestFineGrainedNexthopGroup(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_show_fgnhg_hash_view(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["hash-view"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhg_hash_view_output

    def test_show_fgnhgv4_hash_view(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["hash-view"], ["fgnhg_v4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhgv4_hash_view_output

    def test_show_fgnhgv6_hash_view(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["hash-view"], ["fgnhg_v6"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhgv6_hash_view_output

    def test_show_fgnhg_active_hops(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["active-hops"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhg_active_hops_output

    def test_show_fgnhgv4_active_hops(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["active-hops"], ["fgnhg_v4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhgv4_active_hops_output

    def test_show_fgnhgv6_active_hops(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["active-hops"], ["fgnhg_v6"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhgv6_active_hops_output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
