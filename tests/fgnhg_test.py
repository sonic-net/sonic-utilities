import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


show_fgnhg_hash_view_output="""\
VNET/VRF    FG NHG Prefix    Next Hop            Hash buckets
----------  ---------------  ------------------  ------------------------------
default     100.50.25.12/32  200.200.200.4       0   1   2   3   4   5   6   7
default     100.50.25.12/32  200.200.200.5       8   9   10  11  12  13  14  15
Vnet1       10.0.0.1/32      100.100.100.4       0   1   2   3
Vnet1       10.0.0.1/32      100.100.100.5       4   5   6   7
default     fc:5::/128       200:200:200:200::4  0   1   2   3   4   5   6   7
default     fc:5::/128       200:200:200:200::5  8   9   10  11  12  13  14  15
"""

show_fgnhgv4_hash_view_output="""\
VNET/VRF    FG NHG Prefix    Next Hop       Hash buckets
----------  ---------------  -------------  ------------------------------
default     100.50.25.12/32  200.200.200.4  0   1   2   3   4   5   6   7
default     100.50.25.12/32  200.200.200.5  8   9   10  11  12  13  14  15
"""

show_fgnhgv6_hash_view_output="""\
VNET/VRF    FG NHG Prefix    Next Hop            Hash buckets
----------  ---------------  ------------------  ------------------------------
default     fc:5::/128       200:200:200:200::4  0   1   2   3   4   5   6   7
default     fc:5::/128       200:200:200:200::5  8   9   10  11  12  13  14  15
"""

show_fgnhg_active_hops_output="""\
VNET/VRF    FG NHG Prefix    Active Next Hops
----------  ---------------  ------------------
default     100.50.25.12/32  200.200.200.4
                             200.200.200.5
Vnet1       10.0.0.1/32      100.100.100.4
                             100.100.100.5
default     fc:5::/128       200:200:200:200::4
                             200:200:200:200::5
"""

show_fgnhgv4_active_hops_output="""\
VNET/VRF    FG NHG Prefix    Active Next Hops
----------  ---------------  ------------------
default     100.50.25.12/32  200.200.200.4
                             200.200.200.5
"""

show_fgnhgv6_active_hops_output="""\
VNET/VRF    FG NHG Prefix    Active Next Hops
----------  ---------------  ------------------
default     fc:5::/128       200:200:200:200::4
                             200:200:200:200::5
"""

show_fgnhg_hash_view_vrf_output = """\
VNET/VRF    FG NHG Prefix    Next Hop       Hash buckets
----------  ---------------  -------------  --------------
Vnet1       10.0.0.1/32      100.100.100.4  0   1   2   3
Vnet1       10.0.0.1/32      100.100.100.5  4   5   6   7
"""

show_fgnhg_active_hops_vrf_output = """\
VNET/VRF    FG NHG Prefix    Active Next Hops
----------  ---------------  ------------------
Vnet1       10.0.0.1/32      100.100.100.4
                             100.100.100.5
"""

show_fgnhg_hash_view_default_vrf_output = """\
VNET/VRF    FG NHG Prefix    Next Hop       Hash buckets
----------  ---------------  -------------  ------------------------------
default     100.50.25.12/32  200.200.200.4  0   1   2   3   4   5   6   7
default     100.50.25.12/32  200.200.200.5  8   9   10  11  12  13  14  15
"""

show_fgnhg_active_hops_default_vrf_output = """\
VNET/VRF    FG NHG Prefix    Active Next Hops
----------  ---------------  ------------------
default     100.50.25.12/32  200.200.200.4
                             200.200.200.5
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

    def test_show_fgnhg_hash_view_vrf_prefix(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["hash-view"], ["Vnet1", "10.0.0.1/32"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhg_hash_view_vrf_output

    def test_show_fgnhg_active_hops_vrf_prefix(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["active-hops"], ["Vnet1", "10.0.0.1/32"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_fgnhg_active_hops_vrf_output

    def test_show_fgnhg_hash_view_default_vrf_prefix(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["hash-view"], ["default", "100.50.25.12/32"])
        assert result.exit_code == 0
        assert result.output == show_fgnhg_hash_view_default_vrf_output

    def test_show_fgnhg_active_hops_default_vrf_prefix(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["active-hops"], ["default", "100.50.25.12/32"])
        assert result.exit_code == 0
        assert result.output == show_fgnhg_active_hops_default_vrf_output

    def test_show_fgnhg_hash_view_invalid_vrf(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["hash-view"], ["InvalidVrf", "10.0.0.1/32"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "No FG_ROUTE_TABLE entry found" in result.output

    def test_show_fgnhg_active_hops_invalid_vrf(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["fgnhg"].commands["active-hops"], ["InvalidVrf", "10.0.0.1/32"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "No FG_ROUTE_TABLE entry found" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
