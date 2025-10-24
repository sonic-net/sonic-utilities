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

import show.main as show
import clear.main as clear
import config.main as config

import mock_tables.dbconnector

from unittest import mock
from unittest.mock import patch
from utilities_common.db import Db

config_snmp_location_add_new_location ="""\
SNMP Location public has been added to configuration
Restarting SNMP service...
"""

config_snmp_contact_add_del_new_contact ="""\
SNMP Contact testuser testuser@contoso.com has been added to configuration
Restarting SNMP service...
""" 

tabular_data_show_run_snmp_contact_expected = """\
Contact\n-----------------------------\ntestuser testuser@contoso.com
"""

json_data_show_run_snmp_contact_expected = """\
{'Contact': 'testuser testuser@contoso.com'}
"""

tabular_data_show_run_snmp_community_expected = """\
Community String    Community Type
------------------  ----------------
Rainer              RW
msft                RO
"""

json_data_show_run_snmp_community_expected = """\
{'msft': {'TYPE': 'RO'}, 'Rainer': {'TYPE': 'RW'}}
"""

tabular_data_show_run_snmp_location_expected = """\
Location
----------
public
"""

json_data_show_run_snmp_location_expected = """\
{'Location': 'public'}
"""


tabular_data_show_run_snmp_user_expected = """\
User                Permission Type    Type          Auth Type    Auth Password                Encryption Type    Encryption Password
------------------  -----------------  ------------  -----------  ---------------------------  -----------------  --------------------------
test_authpriv_RO_1  RO                 AuthNoPriv    MD5          test_authpriv_RO_1_authpass
test_authpriv_RO_2  RO                 AuthNoPriv    SHA          test_authpriv_RO_2_authpass
test_authpriv_RO_3  RO                 AuthNoPriv    HMAC-SHA-2   test_authpriv_RO_3_authpass
test_authpriv_RW_1  RW                 AuthNoPriv    MD5          test_authpriv_RW_1_authpass
test_authpriv_RW_2  RW                 AuthNoPriv    SHA          test_authpriv_RW_2_authpass
test_authpriv_RW_3  RW                 AuthNoPriv    HMAC-SHA-2   test_authpriv_RW_3_authpass
test_nopriv_RO_1    RO                 noAuthNoPriv
test_nopriv_RW_1    RW                 noAuthNoPriv
test_priv_RO_1      RO                 Priv          MD5          test_priv_RO_1_authpass      DES                test_priv_RO_1_encrpytpass
test_priv_RO_2      RO                 Priv          MD5          test_priv_RO_2_authpass      AES                test_priv_RO_2_encrpytpass
test_priv_RO_3      RO                 Priv          SHA          test_priv_RO_3_authpass      DES                test_priv_RO_3_encrpytpass
test_priv_RO_4      RO                 Priv          SHA          test_priv_RO_4_authpass      AES                test_priv_RO_4_encrpytpass
test_priv_RO_5      RO                 Priv          HMAC-SHA-2   test_priv_RO_5_authpass      DES                test_priv_RO_5_encrpytpass
test_priv_RO_6      RO                 Priv          HMAC-SHA-2   test_priv_RO_6_authpass      AES                test_priv_RO_6_encrpytpass
test_priv_RW_1      RW                 Priv          MD5          test_priv_RO_1_authpass      DES                test_priv_RW_1_encrpytpass
test_priv_RW_2      RW                 Priv          MD5          test_priv_RO_2_authpass      AES                test_priv_RW_2_encrpytpass
test_priv_RW_3      RW                 Priv          SHA          test_priv_RW_3_authpass      DES                test_priv_RW_3_encrpytpass
test_priv_RW_4      RW                 Priv          SHA          test_priv_RW_4_authpass      AES                test_priv_RW_4_encrpytpass
test_priv_RW_5      RW                 Priv          HMAC-SHA-2   test_priv_RW_5_authpass      DES                test_priv_RW_5_encrpytpass
test_priv_RW_6      RW                 Priv          HMAC-SHA-2   test_priv_RW_6_authpass      AES                test_priv_RW_6_encrpytpass
"""




json_data_show_run_snmp_user_expected = """{'test_authpriv_RO_2': {'SNMP_USER_TYPE': 'AuthNoPriv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'SHA', 'SNMP_USER_AUTH_PASSWORD': 'test_authpriv_RO_2_authpass', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_authpriv_RO_3': {'SNMP_USER_TYPE': 'AuthNoPriv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 'SNMP_USER_AUTH_PASSWORD': 'test_authpriv_RO_3_authpass', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_priv_RW_4': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'SHA', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RW_4_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'AES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RW_4_encrpytpass'}, 'test_priv_RW_3': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'SHA', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RW_3_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'DES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RW_3_encrpytpass'}, 'test_priv_RO_2': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'MD5', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_2_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'AES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RO_2_encrpytpass'}, 'test_nopriv_RO_1': {'SNMP_USER_TYPE': 'noAuthNoPriv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': '', 'SNMP_USER_AUTH_PASSWORD': '', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_priv_RW_1': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'MD5', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_1_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'DES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RW_1_encrpytpass'}, 'test_authpriv_RW_1': {'SNMP_USER_TYPE': 'AuthNoPriv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'MD5', 'SNMP_USER_AUTH_PASSWORD': 'test_authpriv_RW_1_authpass', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_priv_RO_6': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_6_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'AES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RO_6_encrpytpass'}, 'test_priv_RO_1': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'MD5', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_1_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'DES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RO_1_encrpytpass'}, 'test_priv_RO_5': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_5_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'DES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RO_5_encrpytpass'}, 'test_nopriv_RW_1': {'SNMP_USER_TYPE': 'noAuthNoPriv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': '', 'SNMP_USER_AUTH_PASSWORD': '', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_priv_RO_3': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'SHA', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_3_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'DES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RO_3_encrpytpass'}, 'test_priv_RW_2': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'MD5', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_2_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'AES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RW_2_encrpytpass'}, 'test_authpriv_RW_3': {'SNMP_USER_TYPE': 'AuthNoPriv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 'SNMP_USER_AUTH_PASSWORD': 'test_authpriv_RW_3_authpass', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_priv_RW_5': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RW_5_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'DES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RW_5_encrpytpass'}, 'test_priv_RW_6': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RW_6_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'AES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RW_6_encrpytpass'}, 'test_authpriv_RW_2': {'SNMP_USER_TYPE': 'AuthNoPriv', 'SNMP_USER_PERMISSION': 'RW', 'SNMP_USER_AUTH_TYPE': 'SHA', 'SNMP_USER_AUTH_PASSWORD': 'test_authpriv_RW_2_authpass', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}, 'test_priv_RO_4': {'SNMP_USER_TYPE': 'Priv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'SHA', 'SNMP_USER_AUTH_PASSWORD': 'test_priv_RO_4_authpass', 'SNMP_USER_ENCRYPTION_TYPE': 'AES', 'SNMP_USER_ENCRYPTION_PASSWORD': 'test_priv_RO_4_encrpytpass'}, 'test_authpriv_RO_1': {'SNMP_USER_TYPE': 'AuthNoPriv', 'SNMP_USER_PERMISSION': 'RO', 'SNMP_USER_AUTH_TYPE': 'MD5', 'SNMP_USER_AUTH_PASSWORD': 'test_authpriv_RO_1_authpass', 'SNMP_USER_ENCRYPTION_TYPE': '', 'SNMP_USER_ENCRYPTION_PASSWORD': ''}}
"""

tabular_data_show_run_snmp_expected = """\
Location
----------
public


Contact
-----------------------------
testuser testuser@contoso.com


Community String    Community Type
------------------  ----------------
Rainer              RW
msft                RO


User                Permission Type    Type          Auth Type    Auth Password                Encryption Type    Encryption Password
------------------  -----------------  ------------  -----------  ---------------------------  -----------------  --------------------------
test_authpriv_RO_1  RO                 AuthNoPriv    MD5          test_authpriv_RO_1_authpass
test_authpriv_RO_2  RO                 AuthNoPriv    SHA          test_authpriv_RO_2_authpass
test_authpriv_RO_3  RO                 AuthNoPriv    HMAC-SHA-2   test_authpriv_RO_3_authpass
test_authpriv_RW_1  RW                 AuthNoPriv    MD5          test_authpriv_RW_1_authpass
test_authpriv_RW_2  RW                 AuthNoPriv    SHA          test_authpriv_RW_2_authpass
test_authpriv_RW_3  RW                 AuthNoPriv    HMAC-SHA-2   test_authpriv_RW_3_authpass
test_nopriv_RO_1    RO                 noAuthNoPriv
test_nopriv_RW_1    RW                 noAuthNoPriv
test_priv_RO_1      RO                 Priv          MD5          test_priv_RO_1_authpass      DES                test_priv_RO_1_encrpytpass
test_priv_RO_2      RO                 Priv          MD5          test_priv_RO_2_authpass      AES                test_priv_RO_2_encrpytpass
test_priv_RO_3      RO                 Priv          SHA          test_priv_RO_3_authpass      DES                test_priv_RO_3_encrpytpass
test_priv_RO_4      RO                 Priv          SHA          test_priv_RO_4_authpass      AES                test_priv_RO_4_encrpytpass
test_priv_RO_5      RO                 Priv          HMAC-SHA-2   test_priv_RO_5_authpass      DES                test_priv_RO_5_encrpytpass
test_priv_RO_6      RO                 Priv          HMAC-SHA-2   test_priv_RO_6_authpass      AES                test_priv_RO_6_encrpytpass
test_priv_RW_1      RW                 Priv          MD5          test_priv_RO_1_authpass      DES                test_priv_RW_1_encrpytpass
test_priv_RW_2      RW                 Priv          MD5          test_priv_RO_2_authpass      AES                test_priv_RW_2_encrpytpass
test_priv_RW_3      RW                 Priv          SHA          test_priv_RW_3_authpass      DES                test_priv_RW_3_encrpytpass
test_priv_RW_4      RW                 Priv          SHA          test_priv_RW_4_authpass      AES                test_priv_RW_4_encrpytpass
test_priv_RW_5      RW                 Priv          HMAC-SHA-2   test_priv_RW_5_authpass      DES                test_priv_RW_5_encrpytpass
test_priv_RW_6      RW                 Priv          HMAC-SHA-2   test_priv_RW_6_authpass      AES                test_priv_RW_6_encrpytpass
"""


class TestSNMPShowCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    # mock the redis for unit test purposes #
    try:
        if os.environ["UTILITIES_UNIT_TESTING"] == "1":
            modules_path = os.path.join(os.path.dirname(__file__), "..")
            test_path = os.path.join(modules_path, "sonic-utilities-tests")
            sys.path.insert(0, modules_path)
            sys.path.insert(0, test_path)
            import mock_tables.dbconnector
    except KeyError:
        pass

    def test_show_run_snmp_location_tabular(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["add"],
                                    ["public"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_location_add_new_location
            assert db.cfgdb.get_entry("SNMP", "LOCATION") == {"Location": "public"}

            result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["location"], 
                                   [], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == tabular_data_show_run_snmp_location_expected

    def test_show_run_snmp_location_json(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["add"],
                                    ["public"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_location_add_new_location
            assert db.cfgdb.get_entry("SNMP", "LOCATION") == {"Location": "public"}

            result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["location"], 
                                   ["--json"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == json_data_show_run_snmp_location_expected

    def test_show_run_snmp_location_json_bad_key(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["location"], ["--json"])            
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert "{}" in result.output


    def test_show_run_snmp_location_bad_key(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["location"], [])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert "" in result.output

    def test_show_run_snmp_contact_tabular(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                   ["testuser testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"Contact": "testuser testuser@contoso.com"}

            result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["contact"], 
                                   [], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == tabular_data_show_run_snmp_contact_expected

    def test_show_run_snmp_contact_json(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                   ["testuser testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"Contact": "testuser testuser@contoso.com"}

            result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["contact"], 
                                   ["--json"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == json_data_show_run_snmp_contact_expected 

    def test_show_run_snmp_contact_json_bad_key(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["contact"], ["--json"])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert '{}' in result.output

    def test_show_run_snmp_contact_tabular_bad_key(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["contact"])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert '' in result.output


    def test_show_run_snmp_community_tabular(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["community"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == tabular_data_show_run_snmp_community_expected

    def test_show_run_snmp_community_json(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["community"], 
                               ["--json"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == json_data_show_run_snmp_community_expected 

    def test_show_run_snmp_user_tabular(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["user"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == tabular_data_show_run_snmp_user_expected

    def test_show_run_snmp_user_json(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["user"], ["--json"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == json_data_show_run_snmp_user_expected

    def test_show_run_snmp_user_json_bad_key(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_authpriv_RO_1"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_authpriv_RO_1 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_authpriv_RO_2"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_authpriv_RO_2 removed from configuration' in result.output 

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_authpriv_RO_3"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_authpriv_RO_3 removed from configuration' in result.output 

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_authpriv_RW_1"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_authpriv_RW_1 removed from configuration' in result.output
 
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_authpriv_RW_2"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_authpriv_RW_2 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_authpriv_RW_3"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_authpriv_RW_3 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_nopriv_RO_1"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_nopriv_RO_1 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_nopriv_RW_1"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_nopriv_RW_1 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RO_1"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RO_1 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RO_2"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RO_2 removed from configuration' in result.output            
            
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RO_3"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RO_3 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RO_4"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RO_4 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RO_5"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RO_5 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RO_6"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RO_6 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RW_1"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RW_1 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RW_2"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RW_2 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RW_3"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RW_3 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RW_4"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RW_4 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RW_5"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RW_5 removed from configuration' in result.output

            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_priv_RW_6"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP user test_priv_RW_6 removed from configuration' in result.output

            result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"].commands["user"], ["--json"], obj=db)
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "{}" in result.output


    def test_show_run_snmp_tabular(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                   ["testuser testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"Contact": "testuser testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["add"],
                                    ["public"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_location_add_new_location
            assert db.cfgdb.get_entry("SNMP", "LOCATION") == {"Location": "public"}

            result = runner.invoke(show.cli.commands["runningconfiguration"].commands["snmp"], [], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == tabular_data_show_run_snmp_expected


    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

