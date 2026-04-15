import os
import sys
from swsscommon.swsscommon import SonicV2Connector
from click.testing import CliRunner
from utilities_common.db import Db

import acl_loader.main as acl_loader_show
from acl_loader import *
from acl_loader.main import *  # noqa: F403
from acl_loader.main import AclLoader  # noqa: F405

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
Name              Status    SRC IP    DST IP    GRE    DSCP    TTL    Queue    Policer    Monitor Port    SRC Port               Direction      Sample Rate    Truncate Size
----------------  --------  --------  --------  -----  ------  -----  -------  ---------  --------------  ---------------------  -----------  -------------  ---------------
test_session_db1  active                                                                                   Ethernet40,Ethernet48  rx

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

    def test_mirror_show_with_sample_rate(self):
        runner = CliRunner()
        aclloader = AclLoader()
        aclloader.configdb.set_entry("MIRROR_SESSION", "erspan_sampled", {
            "type": "ERSPAN",
            "src_ip": "10.0.1.192",
            "dst_ip": "10.0.1.193",
            "gre_type": "0x8949",
            "dscp": "8",
            "ttl": "64",
            "src_port": "Ethernet0",
            "direction": "RX",
            "sample_rate": "50000",
            "truncate_size": "128"
        })
        aclloader.read_sessions_info()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['session'], [], obj=context)
        assert result.exit_code == 0
        assert "50000" in result.output
        assert "128" in result.output
        assert "Sample Rate" in result.output
        assert "Truncate Size" in result.output
