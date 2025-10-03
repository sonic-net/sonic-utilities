import os
import importlib
import sys
import traceback
from unittest import mock

from click.testing import CliRunner

from .mock_tables import dbconnector

import config.main as config
import show.main as show
from utilities_common.db import Db

show_interfaces_mpls_output_frontend="""\
Interface    MPLS State
-----------  ------------
Ethernet0    enable
Ethernet4    enable
Ethernet8    disable
Ethernet12   disable
Ethernet16   disable
Ethernet20   enable
"""

show_interfaces_mpls_masic_output_frontend="""\
Interface    MPLS State
-----------  ------------
Ethernet0    enable
Ethernet4    disable
"""

show_interfaces_mpls_masic_output_all="""\
Interface       MPLS State
--------------  ------------
Ethernet0       enable
Ethernet4       disable
Ethernet64      enable
Ethernet-BP0    enable
Ethernet-BP4    disable
Ethernet-BP256  disable
Ethernet-BP260  enable
"""
show_interfaces_mpls_masic_output_asic_all="""\
Interface     MPLS State
------------  ------------
Ethernet0     enable
Ethernet4     disable
Ethernet-BP0  enable
Ethernet-BP4  disable
"""

show_interfaces_mpls_output_interface="""\
Interface    MPLS State
-----------  ------------
Ethernet4    enable
"""

show_interfaces_mpls_masic_output_interface="""\
Interface    MPLS State
-----------  ------------
Ethernet4    disable
"""

invalid_interface_remove_output = """\
Usage: remove [OPTIONS] <interface_name>
Try "remove --help" for help.

Error: interface Ethernet8 doesn`t exist
"""

invalid_interface_add_output = """\
Usage: add [OPTIONS] <interface_name>
Try "add --help" for help.

Error: interface Ethernet8 doesn`t exist
""" 
 
invalid_interface_show_output = """\
Usage: mpls [OPTIONS] [INTERFACENAME]
Try 'mpls --help' for help.

Error: interface Ethernet100 doesn`t exist
"""
 
modules_path = os.path.join(os.path.dirname(__file__), "..")
test_path = os.path.join(modules_path, "tests")
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)
mock_db_path = os.path.join(test_path, "mpls_input")

class TestMpls(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        jsonfile = os.path.join(mock_db_path, 'appl_db')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile

    def test_config_mpls_add(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["add"],
                 ["Ethernet0"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("INTERFACE", "Ethernet0") == {"mpls": "enable"}

    def test_config_mpls_invalid_interface_add(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["add"],
                 ["Ethernet8"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0


    def test_show_interfaces_mpls_frontend(self):

        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["-dfrontend"]
                 )
        print(result.exit_code)
        print(result.output) 
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_output_frontend

    def test_show_interfaces_mpls(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"], []
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_output_frontend

    def test_show_interfaces_mpls_dall(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["-dall"]
                 )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_output_frontend

    def test_show_interfaces_mpls_asic_interface(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["Ethernet4"]
                 )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_output_interface
    
    def test_show_interfaces_mpls_asic_invalid_interface(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["Ethernet100"]
                 )
        print(result.output)
        assert result.exit_code == 2
        assert result.output == invalid_interface_show_output 
    
    def test_config_mpls_remove(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["remove"],
                 ["Ethernet0"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("INTERFACE", "Ethernet0") == {"mpls": "disable"}

    def test_config_mpls_invalid_interface_remove(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["remove"],
                 ["Ethernet8"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0


    @classmethod 
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config()
        dbconnector.dedicated_dbs['APPL_DB'] = {}

class TestMplsMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config() 
        

    def test_config_mpls_masic_add(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb, 'namespace':'asic0'}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["add"],
                 ["Ethernet0"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("INTERFACE", "Ethernet0") == {"mpls": "enable"}


    def test_config_mpls_masic_invalid_interface_add(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb, 'namespace':'asic0'}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["add"],
                 ["Ethernet8"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0


    def test_show_interfaces_mpls_masic_frontend(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["-dfrontend"]
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_masic_output_frontend

    def test_show_interfaces_mpls_masic_all(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["-dall"]
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_masic_output_all

    def test_show_interfaces_mpls_masic_asic(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["-nasic0"]
                 )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_masic_output_frontend

    def test_show_interfaces_mpls_masic_asic_all(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["-nasic0", "-dall"]
                 )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_masic_output_asic_all
    
    def test_show_interfaces_mpls_masic_asic_interface(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["Ethernet4"]
                 )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_masic_output_interface
    
    def test_show_interfaces_mpls_masic_asic_invalid_interface(self):
        runner = CliRunner()
        result = runner.invoke(
                 show.cli.commands["interfaces"].commands["mpls"],
                 ["Ethernet100"]
                 )
        print(result.output)
        assert result.exit_code == 2
        assert result.output == invalid_interface_show_output 
    
    def test_config_mpls_masic_remove(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb, 'namespace':'asic0'}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["remove"],
                 ["Ethernet0"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("INTERFACE", "Ethernet0") == {"mpls": "disable"}

    def test_config_mpls_masic_invalid_interface_remove(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb, 'namespace':'asic0'}

        result = runner.invoke(
                 config.config.commands["interface"].commands["mpls"].commands["remove"],
                 ["Ethernet8"], obj=obj
                 )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config()
