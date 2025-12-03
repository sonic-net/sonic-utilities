import sys
import os
import click
from click.testing import CliRunner

import show.main as show
import clear.main as clear
import config.main as config
import config.validated_config_db_connector as validated_config_db_connector

import pytest

from unittest import mock
from unittest.mock import patch
from utilities_common.db import Db

tabular_data_show_run_snmp_contact_expected = """\
Contact    Contact Email\n---------  --------------------\ntestuser   testuser@contoso.com
"""

json_data_show_run_snmp_contact_expected = """\
{'testuser': 'testuser@contoso.com'}
"""

config_snmp_contact_add_del_new_contact ="""\
Contact name testuser and contact email testuser@contoso.com have been added to configuration
Restarting SNMP service...
""" 

config_snmp_location_add_new_location ="""\
SNMP Location public has been added to configuration
Restarting SNMP service...
"""


expected_snmp_community_add_new_community_ro_output = {"TYPE": "RO"}
expected_snmp_community_add_new_community_rw_output = {"TYPE": "RW"}
expected_snmp_community_replace_existing_community_with_new_community_output = {'TYPE': 'RW'}

expected_snmp_user_priv_ro_md5_des_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass',
                                                       'SNMP_USER_AUTH_TYPE': 'MD5',
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass',
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'DES',
                                                       'SNMP_USER_PERMISSION': 'RO',
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_ro_md5_aes_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass',
                                                       'SNMP_USER_AUTH_TYPE': 'MD5',
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass',
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'AES',
                                                       'SNMP_USER_PERMISSION': 'RO',
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_ro_sha_des_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                       'SNMP_USER_AUTH_TYPE': 'SHA', 
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'DES', 
                                                       'SNMP_USER_PERMISSION': 'RO', 
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_ro_sha_aes_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                       'SNMP_USER_AUTH_TYPE': 'SHA', 
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'AES', 
                                                       'SNMP_USER_PERMISSION': 'RO', 
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_ro_hmac_sha_2_des_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                              'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 
                                                              'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                              'SNMP_USER_ENCRYPTION_TYPE': 'DES', 
                                                              'SNMP_USER_PERMISSION': 'RO', 
                                                              'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_ro_hmac_sha_2_aes_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                              'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 
                                                              'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                              'SNMP_USER_ENCRYPTION_TYPE': 'AES', 
                                                              'SNMP_USER_PERMISSION': 'RO', 
                                                              'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_rw_md5_des_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                       'SNMP_USER_AUTH_TYPE': 'MD5', 
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'DES', 
                                                       'SNMP_USER_PERMISSION': 'RW', 
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_rw_md5_aes_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                       'SNMP_USER_AUTH_TYPE': 'MD5', 
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'AES', 
                                                       'SNMP_USER_PERMISSION': 'RW', 
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_rw_sha_des_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                       'SNMP_USER_AUTH_TYPE': 'SHA', 
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'DES', 
                                                       'SNMP_USER_PERMISSION': 'RW', 
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_rw_sha_aes_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                       'SNMP_USER_AUTH_TYPE': 'SHA', 
                                                       'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                       'SNMP_USER_ENCRYPTION_TYPE': 'AES', 
                                                       'SNMP_USER_PERMISSION': 'RW', 
                                                       'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_rw_hmac_sha_2_des_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                              'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 
                                                              'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                              'SNMP_USER_ENCRYPTION_TYPE': 'DES', 
                                                              'SNMP_USER_PERMISSION': 'RW', 
                                                              'SNMP_USER_TYPE': 'Priv'}
expected_snmp_user_priv_rw_hmac_sha_2_aes_config_db_output = {'SNMP_USER_AUTH_PASSWORD': 'user_auth_pass', 
                                                              'SNMP_USER_AUTH_TYPE': 'HMAC-SHA-2', 
                                                              'SNMP_USER_ENCRYPTION_PASSWORD': 'user_encrypt_pass', 
                                                              'SNMP_USER_ENCRYPTION_TYPE': 'AES', 
                                                              'SNMP_USER_PERMISSION': 'RW', 
                                                              'SNMP_USER_TYPE': 'Priv'}

class TestSNMPConfigCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    # Add snmp community tests
    def test_config_snmp_community_add_new_community_ro(self):
        config.ADHOC_VALIDATION = True
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"],
                                                         ["Everest", "ro"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP community Everest added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_COMMUNITY", "Everest") == expected_snmp_community_add_new_community_ro_output

    def test_config_snmp_community_add_new_community_rw(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"],
                                                         ["Shasta", "rw"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP community Shasta added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_COMMUNITY", "Shasta") == expected_snmp_community_add_new_community_rw_output

    def test_config_snmp_community_add_new_community_with_invalid_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"], ["Everest", "RT"])
        print(result.exit_code)
        assert result.exit_code == 1
        assert 'Invalid community type.  Must be either RO or RW' in result.output

    def test_config_snmp_community_add_invalid_community_over_32_characters(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"],
                                                     ["over_32_character_community_string", "ro"])
        print(result.exit_code)
        assert result.exit_code == 2
        assert 'FAILED: SNMP community string length should be not be greater than 32' in result.output

    def test_config_snmp_community_add_invalid_community_with_excluded_special_characters(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"],
                                                     ["Test@snmp", "ro"])
        print(result.exit_code)
        assert result.exit_code == 2
        assert 'FAILED: SNMP community string should not have any of these special symbols' in result.output

    def test_config_snmp_community_add_existing_community(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"], ["Rainer", "rw"])
        print(result.exit_code)
        assert result.exit_code == 3
        assert 'SNMP community Rainer is already configured' in result.output

    # Del snmp community tests
    def test_config_snmp_community_del_existing_community(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["del"],
                                                         ["Rainer"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP community Rainer removed from configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_COMMUNITY", "Everest") == {}

    def test_config_snmp_community_del_non_existing_community(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["del"], ["Everest"])
        print(result.exit_code)
        assert result.exit_code == 1
        assert 'SNMP community Everest is not configured' in result.output

    # Replace snmp community tests
    def test_config_snmp_community_replace_existing_community_with_new_community(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["replace"],
                                                         ["Rainer", "Everest"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP community Everest added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_COMMUNITY", "Everest") == \
                expected_snmp_community_replace_existing_community_with_new_community_output

    def test_config_snmp_community_replace_existing_community_non_existing_community(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["replace"],
                                                     ["Denali", "Everest"])
        print(result.exit_code)
        assert result.exit_code == 1
        assert 'Current SNMP community Denali is not configured' in result.output

    def test_config_snmp_community_replace_new_community_already_exists(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["replace"],
                                                     ["Rainer", "msft"])
        print(result.exit_code)
        assert result.exit_code == 3
        assert 'New SNMP community msft to replace current SNMP community Rainer already configured' in result.output

    def test_config_snmp_community_replace_with_invalid_new_community_bad_symbol(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["replace"],
                                                     ["Rainer", "msft@"])
        print(result.exit_code)
        assert result.exit_code == 2
        assert 'FAILED: SNMP community string should not have any of these special symbols' in result.output

    def test_config_snmp_community_replace_with_invalid_new_community_over_32_chars(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["replace"],
                                                     ["Rainer", "over_32_characters_community_string"])
        print(result.exit_code)
        assert result.exit_code == 2
        assert 'FAILED: SNMP community string length should be not be greater than 32' in result.output


    # Del snmp contact when CONTACT not setup in REDIS
    def test_config_snmp_contact_del_without_contact_redis(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["del"], ["blah"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 2
        assert 'Contact name blah is not configured' in result.output
        assert db.cfgdb.get_entry("SNMP", "CONTACT") == {}

    def test_config_snmp_contact_modify_without_contact_redis(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["modify"], 
                                                     ["blah", "blah@contoso.com"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 3
        assert 'Contact name blah is not configured' in result.output
        assert db.cfgdb.get_entry("SNMP", "CONTACT") == {}

    def test_config_snmp_contact_add_del_new_contact(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["del"],
                                    ["testuser"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert 'SNMP contact testuser removed from configuration' in result.output
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {} 

    # Add snmp contact tests
    def test_config_snmp_contact_add_with_existing_contact(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                                     ["blah", "blah@contoso.com"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'Contact already exists.  Use sudo config snmp contact modify instead' in result.output

    def test_config_snmp_contact_add_invalid_email(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                              ["testuser", "testusercontoso.com"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 2
            assert "Contact email testusercontoso.com is not valid" in result.output


    # Delete snmp contact tests
    def test_config_snmp_contact_del_new_contact_when_contact_exists(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["del"], ["blah"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'SNMP contact blah is not configured' in result.output

    def test_config_snmp_contact_del_with_existing_contact(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["del"], 
                                   ["testuser"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP contact testuser removed from configuration' in result.output
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {}

    # Modify snmp contact tests
    def test_config_snmp_contact_modify_email_with_existing_contact(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["modify"],
                                                         ["testuser", "testuser@test.com"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP contact testuser email updated to testuser@test.com' in result.output
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@test.com"}

    def test_config_snmp_contact_modify_contact_and_email_with_existing_entry(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["modify"],
                                                     ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'SNMP contact testuser testuser@contoso.com already exists' in result.output

    def test_config_snmp_contact_modify_existing_contact_with_invalid_email(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["modify"],
                                                     ["testuser", "testuser@contosocom"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 2
            assert 'Contact email testuser@contosocom is not valid' in result.output


    def test_config_snmp_contact_modify_new_contact_with_invalid_email(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["add"],
                                    ["testuser", "testuser@contoso.com"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_snmp_contact_add_del_new_contact
            assert db.cfgdb.get_entry("SNMP", "CONTACT") == {"testuser": "testuser@contoso.com"}

            result = runner.invoke(config.config.commands["snmp"].commands["contact"].commands["modify"],
                                                     ["blah", "blah@contoso@com"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 2
            assert 'Contact email blah@contoso@com is not valid' in result.output

    # Add snmp location tests
    def test_config_snmp_location_add_exiting_location_with_same_location_already_existing(self):
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

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["add"], 
                                                         ["public"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'Location already exists' in result.output

    def test_config_snmp_location_add_new_location_with_location_already_existing(self):
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

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["add"], 
                                                         ["Mile High"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'Location already exists' in result.output

    # Del snmp location tests
    def test_config_snmp_location_del_with_existing_location(self):
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

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["del"],
                                                         ["public"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert 'SNMP Location public removed from configuration' in result.output
            assert db.cfgdb.get_entry("SNMP", "LOCATION") == {}

    def test_config_snmp_location_del_new_location_with_location_already_existing(self):
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

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["del"], 
                                                         ["Mile High"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'SNMP Location Mile High does not exist.  The location is public' in result.output

    # Modify snmp location tests
    def test_config_snmp_location_modify_with_same_location(self):
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

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["modify"], 
                                                         ["public"], obj=db)
            print(result.exit_code)
            assert result.exit_code == 1
            assert 'SNMP location public already exists' in result.output

    def test_config_snmp_location_modify_without_redis(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["modify"],
                                                         ["Rainer"],obj=db)
        print(result.exit_code)
        assert result.exit_code == 2
        assert "Cannot modify SNMP Location.  You must use 'config snmp location add " \
                "command <snmp_location>'" in result.output
        assert db.cfgdb.get_entry("SNMP", "LOCATION") == {}

    def test_config_snmp_location_modify_without_existing_location(self):
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

            result = runner.invoke(config.config.commands["snmp"].commands["location"].commands["modify"],
                                                         ["Rainer"],obj=db)
            print(result.exit_code)
            assert result.exit_code == 0
            assert "SNMP location Rainer modified in configuration" in result.output
            assert db.cfgdb.get_entry("SNMP", "LOCATION") == {"Location": "Rainer"}

    # Add snmp user tests
    def test_config_snmp_user_add_invalid_user_name_over_32_characters(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["over_32_characters_community_user", "noAUthNoPRiv", "ro"])
        print(result.exit_code)
        assert result.exit_code == 1
        assert 'FAILED: SNMP user over_32_characters_community_user length should not be greater than 32 characters' \
               in result.output

    def test_config_snmp_user_add_excluded_special_characters_in_username(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["Test@user", "noAUthNoPRiv", "ro"])
        print(result.exit_code)
        assert result.exit_code == 1
        assert 'FAILED: SNMP user Test@user should not have any of these special symbols' in result.output

    def test_config_snmp_user_add_existing_user(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_1", "noAUthNoPRiv", "ro"])
        print(result.exit_code)
        assert result.exit_code == 14
        assert 'SNMP user test_nopriv_RO_1 is already configured' in result.output

    def test_config_snmp_user_add_invalid_user_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "nopriv", "ro"])
        print(result.exit_code)
        print(result)
        print(result.output)
        assert result.exit_code == 2
        assert "Invalid user type.  Must be one of these one of these three 'noauthnopriv' or 'authnopriv' or 'priv'" in result.output

    def test_config_snmp_user_add_invalid_permission_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "noauthnopriv", "ab"])
        print(result.exit_code)
        assert result.exit_code == 3
        assert "Invalid community type.  Must be either RO or RW" in result.output

    def test_config_snmp_user_add_user_type_noauthnopriv_with_unnecessary_auth_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "noauthnopriv", "ro", "sha"])
        print(result.exit_code)
        assert result.exit_code == 4
        assert "User auth type not used with 'noAuthNoPriv'.  Please use 'AuthNoPriv' or 'Priv' instead" in result.output

    def test_config_snmp_user_add_user_type_authnopriv_missing_auth_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "authnopriv", "ro"])
        print(result.exit_code)
        assert result.exit_code == 5
        assert "User auth type is missing.  Must be MD5, SHA, or HMAC-SHA-2" in result.output

    def test_config_snmp_user_add_user_type_authnopriv_missing_auth_password(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "authnopriv", "ro", "sha"])
        print(result.exit_code)
        assert result.exit_code == 7
        assert "User auth password is missing" in result.output

    def test_config_snmp_user_add_user_type_authnopriv_with_unnecessary_encrypt_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                            ["test_nopriv_RO_3", "authnopriv", "ro", "sha", "testauthpass", "DES"])
        print(result.exit_code)
        assert result.exit_code == 9
        assert "User encrypt type not used with 'AuthNoPriv'.  Please use 'Priv' instead" in result.output

    def test_config_snmp_user_add_user_type_priv_missing_auth_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "priv", "ro"])
        print(result.exit_code)
        assert result.exit_code == 5
        assert "User auth type is missing.  Must be MD5, SHA, or HMAC-SHA-2" in result.output

    def test_config_snmp_user_add_user_type_priv_missing_auth_password(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "priv", "ro", "md5"])
        print(result.exit_code)
        assert result.exit_code == 7
        assert "User auth password is missing" in result.output

    def test_config_snmp_user_add_user_type_priv_missing_encrypt_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                                                     ["test_nopriv_RO_3", "priv", "ro", "md5", "testauthpass"])
        print(result.exit_code)
        assert result.exit_code == 10
        assert "User encrypt type is missing.  Must be DES or AES" in result.output

    def test_config_snmp_user_add_user_type_priv_invalid_encrypt_password_over_64_characters(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                ["test_nopriv_RO_3", "priv", "ro", "md5", "testauthpass", "DES", 
                 "superlongencryptionpasswordtotestbeingoverthesixtyfourcharacterlimit"])
        print(result.exit_code)
        assert result.exit_code == 13
        assert "FAILED: SNMP user password length should be not be greater than 64" in result.output

    def test_config_snmp_user_add_user_type_priv_invalid_encrypt_password_excluded_special_characters(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                 ["test_nopriv_RO_3", "priv", "ro", "md5", "testauthpass", "DES", "testencrypt@pass"])
        print(result.exit_code)
        assert result.exit_code == 13
        assert "FAILED: SNMP user password should not have any of these special symbols" in result.output

    def test_config_snmp_user_add_user_type_priv_invalid_encrypt_password_not_long_enough(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                              ["test_nopriv_RO_3", "priv", "ro", "md5", "testauthpass", "DES", "test1"])
        print(result.exit_code)
        assert result.exit_code == 13
        assert "FAILED: SNMP user password length should be at least 8 characters" in result.output

    def test_config_snmp_user_add_invalid_auth_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                              ["test_nopriv_RO_3", "authnopriv", "ro", "DM5", "user_auth_pass"])
        print(result.exit_code)
        assert result.exit_code == 6
        assert "Invalid user authentication type. Must be one of these 'MD5', 'SHA', or 'HMAC-SHA-2'" in result.output

    def test_config_snmp_user_add_missing_auth_password(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                              ["test_nopriv_RO_3", "authnopriv", "ro", "SHA", ""])
        print(result.exit_code)
        assert result.exit_code == 7
        assert 'User auth password is missing' in result.output

    def test_config_snmp_user_add_invalid_encrypt_type(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                              ["test_nopriv_RO_3", "priv", "ro", "SHA", "user_auth_pass", "EAS", "user_encrypt_pass"])
        print(result.exit_code)
        assert result.exit_code == 11
        assert "Invalid user encryption type.  Must be one of these two 'DES' or 'AES'" in result.output

    def test_config_snmp_user_add_missing_encrypt_password(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                              ["test_nopriv_RO_3", "priv", "ro", "SHA", "user_auth_pass", "AES"])
        print(result.exit_code)
        assert result.exit_code == 12
        assert 'User encrypt password is missing' in result.output

    def test_config_snmp_user_add_user_already_existing(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                              ["test_nopriv_RO_1", "noauthnopriv", "ro"])
        print(result.exit_code)
        assert result.exit_code == 14
        assert 'SNMP user test_nopriv_RO_1 is already configured' in result.output

    def test_config_snmp_user_add_valid_user_priv_ro_md5_des(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RO_7", "priv", "ro", "MD5", "user_auth_pass", "DES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RO_7 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RO_7") == expected_snmp_user_priv_ro_md5_des_config_db_output

    def test_config_snmp_user_add_valid_user_priv_ro_md5_aes(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RO_8", "priv", "ro", "MD5", "user_auth_pass", "AES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RO_8 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RO_8") == expected_snmp_user_priv_ro_md5_aes_config_db_output

    def test_config_snmp_user_add_valid_user_priv_ro_sha_des(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RO_9", "priv", "ro", "SHA", "user_auth_pass", "DES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RO_9 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RO_9") == expected_snmp_user_priv_ro_sha_des_config_db_output

    def test_config_snmp_user_add_valid_user_priv_ro_sha_aes(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RO_10", "priv", "ro", "SHA", "user_auth_pass", "AES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RO_10 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RO_10") == expected_snmp_user_priv_ro_sha_aes_config_db_output

    def test_config_snmp_user_add_valid_user_priv_ro_hmac_sha_2_des(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                ["test_priv_RO_11", "priv", "ro", "HMAC-SHA-2", "user_auth_pass", "DES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RO_11 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RO_11") == \
               expected_snmp_user_priv_ro_hmac_sha_2_des_config_db_output

    def test_config_snmp_user_add_valid_user_priv_ro_hmac_sha_2_aes(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                ["test_priv_RO_12", "priv", "ro", "HMAC-SHA-2", "user_auth_pass", "AES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RO_12 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RO_12") == \
               expected_snmp_user_priv_ro_hmac_sha_2_aes_config_db_output

    def test_config_snmp_user_add_valid_user_priv_rw_md5_des(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RW_7", "priv", "rw", "MD5", "user_auth_pass", "DES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RW_7 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RW_7") == expected_snmp_user_priv_rw_md5_des_config_db_output

    def test_config_snmp_user_add_valid_user_priv_rw_md5_aes(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RW_8", "priv", "rw", "MD5", "user_auth_pass", "AES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RW_8 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RW_8") == expected_snmp_user_priv_rw_md5_aes_config_db_output

    def test_config_snmp_user_add_valid_user_priv_rw_sha_des(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RW_9", "priv", "rw", "SHA", "user_auth_pass", "DES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RW_9 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RW_9") == expected_snmp_user_priv_rw_sha_des_config_db_output

    def test_config_snmp_user_add_valid_user_priv_rw_sha_aes(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                    ["test_priv_RW_10", "priv", "rw", "SHA", "user_auth_pass", "AES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RW_10 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RW_10") == expected_snmp_user_priv_rw_sha_aes_config_db_output

    def test_config_snmp_user_add_valid_user_priv_rw_hmac_sha_2_des(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                ["test_priv_RW_11", "priv", "rw", "HMAC-SHA-2", "user_auth_pass", "DES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RW_11 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RW_11") == \
               expected_snmp_user_priv_rw_hmac_sha_2_des_config_db_output

    def test_config_snmp_user_add_valid_user_priv_rw_hmac_sha_2_aes(self):
        db = Db()
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["add"],
                ["test_priv_RW_12", "priv", "rw", "HMAC-SHA-2", "user_auth_pass", "AES", "user_encrypt_pass"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_priv_RW_12 added to configuration' in result.output
        assert db.cfgdb.get_entry("SNMP_USER", "test_priv_RW_12") == \
               expected_snmp_user_priv_rw_hmac_sha_2_aes_config_db_output

    # Del snmp user tests
    def test_config_snmp_user_del_valid_user(self):
        runner = CliRunner()
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                    ["test_nopriv_RO_1"])
        print(result.exit_code)
        assert result.exit_code == 0
        assert 'SNMP user test_nopriv_RO_1 removed from configuration' in result.output

    def test_config_snmp_user_del_invalid_user(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["user"].commands["del"],
                ["test_nopriv_RO_2"])
        print(result.exit_code)
        assert result.exit_code == 1
        assert 'SNMP user test_nopriv_RO_2 is not configured' in result.output

    @pytest.mark.parametrize("invalid_email", ['test@contoso', 'test.contoso.com', 'testcontoso@com', 
                                               '123_%contoso.com', 'mytest@contoso.comm'])
    def test_is_valid_email(self, invalid_email):
        output = config.is_valid_email(invalid_email)
        assert output == False

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_config_snmp_community_add_new_community_with_invalid_type_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        result = runner.invoke(config.config.commands["snmp"].commands["community"].commands["add"], ["Everest", "RT"])
        print(result.exit_code)
        assert result.exit_code != 0
        assert 'SNMP community configuration failed' in result.output

    @patch('netifaces.interfaces', mock.Mock(return_value=['eth0']))
    @patch('netifaces.ifaddresses', mock.Mock(return_value={2:
                                              [{'addr': '10.1.0.32', 'netmask': '255.255.255.0',
                                                'broadcast': '10.1.0.255'}],
                                                10: [{'addr': 'fe80::1%eth0', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]}))
    @patch('os.system', mock.Mock(return_value=0))
    def test_config_snmpagentaddress_add_linklocal(self):
        db = Db()
        obj = {'db': db.cfgdb}
        runner = CliRunner()
        runner.invoke(config.config.commands["snmpagentaddress"].commands["add"], ["fe80::1%eth0"], obj=obj)
        assert ('fe80::1%eth0', '', '') in db.cfgdb.get_keys('SNMP_AGENT_ADDRESS_CONFIG')
        assert db.cfgdb.get_entry("SNMP_AGENT_ADDRESS_CONFIG", "fe80::1%eth0||") == {}

    @patch('netifaces.interfaces', mock.Mock(return_value=['eth0']))
    @patch('netifaces.ifaddresses', mock.Mock(return_value={2:
                                              [{'addr': '10.1.0.32', 'netmask': '255.255.255.0',
                                                'broadcast': '10.1.0.255'}],
                                                10: [{'addr': 'fe80::1', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]}))
    @patch('os.system', mock.Mock(return_value=0))
    def test_config_snmpagentaddress_add_ipv4(self):
        db = Db()
        obj = {'db': db.cfgdb}
        runner = CliRunner()
        runner.invoke(config.config.commands["snmpagentaddress"].commands["add"], ["10.1.0.32"], obj=obj)
        assert ('10.1.0.32', '', '') in db.cfgdb.get_keys('SNMP_AGENT_ADDRESS_CONFIG')
        assert db.cfgdb.get_entry("SNMP_AGENT_ADDRESS_CONFIG", "10.1.0.32||") == {}

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

