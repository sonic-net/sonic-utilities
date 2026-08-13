from click.testing import CliRunner
import show.main as show


show_lacp_info_output = (
    "Trunk                   Member Port         Mode     Priority   Actor System id (key)    "
    "Partner System id (key)     Speed (Mbps)\n"
    "----------------------  ------------------  ------  ----------  -----------------------  "
    "-------------------------  --------------\n"
    "PortChannel0001 (down)  Ethernet112 (down)  Active    10000     52:54:00:f2:e1:23 (5)    "
    "00:00:00:00:00:00 (5)          10000\n"
    "PortChannel0002 (down)  Ethernet116 (up)    Active    20000     52:54:00:f2:e1:23 (1)    "
    "1e:af:77:fc:79:ee (1)          40000\n"
    "PortChannel0003 (up)    Ethernet120 (up)    Active    30000     52:54:00:f2:e1:23 (4)    "
    "16:0e:58:6f:3c:dd (4)          400000\n"
)

show_lacp_status_output = """\
     Trunk        Member Port    Role     Exp    Def    Dist    Col      Sync       Aggr    Timeout    Mode
---------------  -------------  -------  -----  -----  ------  -----  -----------  ------  ---------  -------
PortChannel0001   Ethernet112    Actor    No     No      No     No    Out-of-Sync   Yes       3s      Active
                                Partner   No     No      No     No    Out-of-Sync    No       3s      Passive
PortChannel0002   Ethernet116    Actor    No     No     Yes     Yes     In-Sync     Yes       3s      Active
                                Partner   No     No     Yes     Yes     In-Sync     Yes       3s      Active
PortChannel0003   Ethernet120    Actor    No     No     Yes     Yes     In-Sync     Yes       3s      Active
                                Partner   No     No     Yes     Yes     In-Sync     Yes       3s      Active

Values: expired/defaulted/distributing/collecting/sync/aggregating/timeout/mode
"""

show_lacp_counters_output = """\
Trunk            Member Port      LACP Tx    LACP Rx    Rx Errors
---------------  -------------  ---------  ---------  -----------
PortChannel0001  Ethernet112        23829      23808           20
PortChannel0002  Ethernet116        28112      28103            0
PortChannel0003  Ethernet120        41539      41533            0
"""


class TestLacp(object):

    def test_show_lacp(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["lacp"], [])
        print(result.output)
        assert result.exit_code == 0

    def test_show_lacp_info(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["lacp"].commands["info"], [])
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_lacp_info_output

    def test_show_lacp_status(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["lacp"].commands["status"], [])
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_lacp_status_output

    def test_show_lacp_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["lacp"].commands["counters"], [])
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_lacp_counters_output
