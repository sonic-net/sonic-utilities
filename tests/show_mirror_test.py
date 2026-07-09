# flake8: noqa: E501
import os
import sys
from swsscommon.swsscommon import SonicV2Connector
from click.testing import CliRunner
from utilities_common.db import Db

import acl_loader.main as acl_loader_show
from acl_loader import *
from acl_loader.main import *  # noqa: F403, F401

class TestShowMirror(object):
    def test_mirror_show(self):
        runner = CliRunner()
        aclloader = AclLoader()
        aclloader.configdb.set_entry("MIRROR_SESSION", "session1", {"direction": "BOTH", "dst_port": "Ethernet30", "src_port": "Ethernet40", "type": "SPAN"})
        aclloader.configdb.set_entry("MIRROR_SESSION", "session2", {"direction": "BOTH", "dst_port": "Ethernet7", "src_port": "Ethernet8", "type": "SPAN"})
        aclloader.configdb.set_entry("MIRROR_SESSION", "session11", {"direction": "RX", "dst_port": "Ethernet9", "src_port": "Ethernet10", "type": "SPAN"})
        aclloader.configdb.set_entry("MIRROR_SESSION", "session15", {"direction": "TX", "dst_port": "Ethernet2", "src_port": "Ethernet3", "type": "SPAN"})
        aclloader.read_sessions_info()
        context = {
            "acl_loader": aclloader
        }
        expected_output = """\
ERSPAN Sessions
Name                  Status    SRC IP    DST IP    GRE     DSCP    TTL    Queue    Policer    Monitor Port    SRC Port               Direction    Sample Rate    Truncate Size
--------------------  --------  --------  --------  ------  ------  -----  -------  ---------  --------------  ---------------------  -----------  -------------  ---------------
test_session_db1      active                                                                                    Ethernet40,Ethernet48  rx
test_session_sampled  active     10.0.0.1  10.0.0.2  0x8949  8       64                                         Ethernet0              rx           50000          128

SPAN Sessions
Name       Status    DST Port    SRC Port    Direction    Queue    Policer
---------  --------  ----------  ----------  -----------  -------  ---------
session1   active     Ethernet30  Ethernet40  both
session2   active     Ethernet7   Ethernet8   both
session11  active     Ethernet9   Ethernet10  rx
session15  active     Ethernet2   Ethernet3   tx
"""
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['session'], [], obj=context)
        assert result.exit_code == 0
        print (result.output)
        #The state of mirror_session depends on the state_db table entry. This case does not care about the state and is uniformly set to active.
        result_output = result.output.replace('error', 'active')
        result_output = result_output.replace('inactive', 'active')
        assert result_output == expected_output

