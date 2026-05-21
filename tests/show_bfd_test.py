import os
import sys
from click.testing import CliRunner
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.db import Db

import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "bfd_input")

class TestShowBfd(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def set_db_values(self, db, key, kvs):
        for field, value in kvs.items():
            db.set(db.STATE_DB, key, field, value)

    def test_bfd_show(self):
        runner = CliRunner()
        db = Db()
        dbconnector = db.db

        self.set_db_values(dbconnector, "BFD_SESSION_TABLE|default|default|10.0.1.1",
                        {"state": "DOWN", "type": "async_active", "local_addr" : "10.0.0.1",
                        "tx_interval" :"300", "rx_interval" : "500", "multiplier" : "3", "multihop": "true"})
        self.set_db_values(dbconnector, "BFD_SESSION_TABLE|default|Ethernet12|10.0.2.1",
                        {"state": "UP", "type": "async_active", "local_addr" : "10.0.0.1",
                        "tx_interval" :"200", "rx_interval" : "600", "multiplier" : "3", "multihop": "false", "local_discriminator": "88"})
        self.set_db_values(dbconnector, "BFD_SESSION_TABLE|default|default|2000::10:1",
                        {"state": "UP", "type": "async_active", "local_addr" : "2000::1",
                        "tx_interval" :"100", "rx_interval" : "700", "multiplier" : "3", "multihop": "false"})
        self.set_db_values(dbconnector, "BFD_SESSION_TABLE|VrfRed|default|10.0.1.1",
                        {"state": "UP", "type": "async_active", "local_addr" : "10.0.0.1",
                        "tx_interval" :"400", "rx_interval" : "500", "multiplier" : "5", "multihop": "false"})

        expected_output = """\
Total number of BFD sessions: 6
Peer Addr              Interface    Vrf      State    Type          Local Addr               TX Interval    RX Interval    Multiplier  Multihop    Local Discriminator
---------------------  -----------  -------  -------  ------------  ---------------------  -------------  -------------  ------------  ----------  ---------------------
100.251.7.1            default      default  Up       async_active  10.0.0.1                         300            500             3  true        NA
fddd:a101:a251::a10:1  default      default  Down     async_active  fddd:c101:a251::a10:2            300            500             3  true        NA
10.0.1.1               default      default  DOWN     async_active  10.0.0.1                         300            500             3  true        NA
10.0.2.1               Ethernet12   default  UP       async_active  10.0.0.1                         200            600             3  false       88
2000::10:1             default      default  UP       async_active  2000::1                          100            700             3  false       NA
10.0.1.1               default      VrfRed   UP       async_active  10.0.0.1                         400            500             5  false       NA
"""

        result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)
        assert result.exit_code == 0
        assert result.output == expected_output

        expected_output = """\
Total number of BFD sessions for peer IP 10.0.1.1: 2
Peer Addr    Interface    Vrf      State    Type          Local Addr      TX Interval    RX Interval    Multiplier  Multihop    Local Discriminator
-----------  -----------  -------  -------  ------------  ------------  -------------  -------------  ------------  ----------  ---------------------
10.0.1.1     default      default  DOWN     async_active  10.0.0.1                300            500             3  true        NA
10.0.1.1     default      VrfRed   UP       async_active  10.0.0.1                400            500             5  false       NA
"""

        result = runner.invoke(show.cli.commands['bfd'].commands['peer'], ['10.0.1.1'], obj=db)
        assert result.exit_code == 0
        assert result.output == expected_output

        expected_output = """\
Total number of BFD sessions for peer IP 10.0.2.1: 1
Peer Addr    Interface    Vrf      State    Type          Local Addr      TX Interval    RX Interval    Multiplier  Multihop      Local Discriminator
-----------  -----------  -------  -------  ------------  ------------  -------------  -------------  ------------  ----------  ---------------------
10.0.2.1     Ethernet12   default  UP       async_active  10.0.0.1                200            600             3  false                          88
"""

        result = runner.invoke(show.cli.commands['bfd'].commands['peer'], ['10.0.2.1'], obj=db)
        assert result.exit_code == 0
        assert result.output == expected_output

        expected_output = """\
No BFD sessions found for peer IP 10.0.3.1
"""

        result = runner.invoke(show.cli.commands['bfd'].commands['peer'], ['10.0.3.1'], obj=db)
        assert result.exit_code == 0
        assert result.output == expected_output


    def test_bfd_show_no_session(self):
        runner = CliRunner()
        db = Db()

        expected_output = """\
Total number of BFD sessions: 2
Peer Addr              Interface    Vrf      State    Type          Local Addr               TX Interval    RX Interval    Multiplier  Multihop    Local Discriminator
---------------------  -----------  -------  -------  ------------  ---------------------  -------------  -------------  ------------  ----------  ---------------------
100.251.7.1            default      default  Up       async_active  10.0.0.1                         300            500             3  true        NA
fddd:a101:a251::a10:1  default      default  Down     async_active  fddd:c101:a251::a10:2            300            500             3  true        NA
"""

        result = runner.invoke(show.cli.commands['bfd'].commands['summary'], [], obj=db)
        assert result.exit_code == 0
        assert result.output == expected_output
