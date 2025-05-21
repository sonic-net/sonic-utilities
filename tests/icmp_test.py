import os
import traceback

import traceback

from click.testing import CliRunner
from utilities_common.db import Db

import show.main as show


tabular_session_status_output_expected = """\
Key                                    Dst IP          Tx Interval    Rx Interval  HW lookup    Cookie      State
-------------------------------------  ------------  -------------  -------------  -----------  ----------  -------
default|Ethernet0|0x4eb39592|RX        192.168.0.3               0            300  false        0x58767e7a  Up
default|Ethernet128|0x23ffb930|NORMAL  192.168.0.31            100            300  false        0x58767e7a  Down
default|Ethernet152|0x39e05375|NORMAL  192.168.0.37            100            300  false        0x58767e7a  Up
default|Ethernet8|0x69f578f5|NORMAL    192.168.0.5             100            300  false        0x58767e7a  Up
"""

session_summary_output_expected = """\
Total Sessions: 4
Up sessions: 3
RX sessions: 1
"""

tabular_session_key_status_output_expected = """\
Key                              Dst IP         Tx Interval    Rx Interval  HW lookup    Cookie      State
-------------------------------  -----------  -------------  -------------  -----------  ----------  -------
default|Ethernet0|0x4eb39592|RX  192.168.0.3              0            300  false        0x58767e7a  Up
"""

class TestIcmpSession(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_icmpecho_summary(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["icmp"].commands["summary"], obj=db)

        assert result.exit_code == 0
        assert result.output == session_summary_output_expected

    def test_icmpecho_sessions(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["icmp"].commands["sessions"], obj=db)
        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert result.output == tabular_session_status_output_expected

    def test_icmpecho_key_sessions(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["icmp"].commands["sessions"], "default|Ethernet0|0x4eb39592|RX", obj=db)
        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert result.output == tabular_session_key_status_output_expected

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
