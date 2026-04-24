import sys
import os
import click
from click.testing import CliRunner
import pytest
import traceback

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

mock_db_path = os.path.join(test_path, "mock_tables")

import show.main as show
import clear.main as clear
import config.main as config

import mock_tables.dbconnector

from unittest import mock
from unittest.mock import patch
from utilities_common.db import Db


add_lag_member_with_non_deft_tpid_configured="""\
Usage: add [OPTIONS] <portchannel_name> <port_name>
Try 'add --help' for help.

Error: Port TPID of Ethernet20: 0x9200 is not at default 0x8100
"""

bad_tpid_configured="""\
TPID 0x2000 is not allowed. Allowed: 0x8100, 9100, 9200, or 88A8.
"""

bad_lag_tpid_configured="""\
TPID 0x2100 is not allowed. Allowed: 0x8100, 9100, 9200, or 88A8.
"""

tpid_set_on_lag_mbr_attempted_not_allowed="""\
Ethernet32 is already member of PortChannel1001. Set TPID NOT allowed.
"""

show_interface_tpid_output="""\
      Interface      Alias    Oper    Admin    TPID
---------------  ---------  ------  -------  ------
      Ethernet0  Ethernet0    down       up  0x9200
     Ethernet16       etp5      up       up     N/A
     Ethernet24       etp6      up       up  0x8100
     Ethernet28       etp8      up       up     N/A
     Ethernet32       etp9      up       up  0x8100
     Ethernet36      etp10      up       up  0x8100
    Ethernet112      etp29      up       up  0x8100
    Ethernet116      etp30      up       up  0x8100
    Ethernet120      etp31      up       up  0x8100
    Ethernet124      etp32      up       up  0x8100
PortChannel0001        N/A    down       up  0x8100
PortChannel0002        N/A      up       up  0x8100
PortChannel0003        N/A      up       up  0x8100
PortChannel0004        N/A      up       up  0x8100
PortChannel1001        N/A     N/A      N/A  0x8100
"""

show_interface_tpid_ethernet0_output="""\
  Interface      Alias    Oper    Admin    TPID
-----------  ---------  ------  -------  ------
  Ethernet0  Ethernet0    down       up  0x9200
"""


class TestTpid(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        import mock_tables.dbconnector

    def test_tpid_config_bad_tpid(self):
        db = Db()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet0", "0x2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        #traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 1
        assert result.output == bad_tpid_configured

    def test_tpid_config_lag_mbr(self):
        db = Db()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet32", "0x9100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == tpid_set_on_lag_mbr_attempted_not_allowed
        
    def test_tpid_add_lag_mbr_with_non_default_tpid(self):
        db = Db()
        obj = {'db': db.cfgdb}
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0001","Ethernet20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert result.output == add_lag_member_with_non_deft_tpid_configured

    def test_tpid_config_port_interface(self):
        db = Db()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet0", "0x9200"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet0", "0x9100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet0", "0x88a8"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet0", "0x8100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["Ethernet0", "0x2000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == bad_tpid_configured

    def test_tpid_config_portchannel_interface(self):
        db = Db()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["PortChannel1001", "0x9200"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["PortChannel1001", "0x9100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["PortChannel1001", "0x88A8"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["PortChannel1001", "0x8100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["interface"].commands["tpid"], ["PortChannel1001", "0x2100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == bad_lag_tpid_configured

    def test_show_tpid(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["tpid"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interface_tpid_output

    def test_show_tpid_ethernet0(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["tpid"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interface_tpid_ethernet0_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
