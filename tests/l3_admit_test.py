from click.testing import CliRunner
import show.main as show

show_l3_admit_output = """\
Dest Mac           Mask               Ingress Port
-----------------  -----------------  --------------
02:1a:0a:05:17:01  ff:ff:ff:ff:ff:ff  <any>
02:1a:0a:05:17:03  ff:ff:ff:ff:ff:ff  Ethernet1/4/5
02:1b:00:00:00:00  ff:ff:00:00:00:00  Ethernet1/3/1
"""


class TestL3Admit(object):

    def test_show_l3_admit(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["l3-admit"], [])
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_l3_admit_output
