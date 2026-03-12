import os
import pytest
import config.main as config
from unittest import mock

from click.testing import CliRunner
from utilities_common.db import Db
from config.main import EVPN_ES_TABLE


@pytest.fixture
def enable_click_ut_mode():
    os.environ['UTILITIES_UNIT_TESTING'] = "1"
    yield os.environ['UTILITIES_UNIT_TESTING']

    os.environ['UTILITIES_UNIT_TESTING'] = "0"


@pytest.fixture
def cli_db_connection(enable_click_ut_mode):
    config.run_vtysh_command = mock.MagicMock(return_value=None)
    return CliRunner(), {'config_db': Db().cfgdb}


def configure_manual_esi(runner, db, interface_name, esi_str):
    result = runner.invoke(config.config.commands["interface"].commands["evpn-esi"].commands['add'], [interface_name, esi_str], obj=db)
    assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"

    evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
    assert interface_name in evpn_es_table, f"'{interface_name}' not found in {EVPN_ES_TABLE}"
    assert evpn_es_table[interface_name]['esi'] == esi_str, f"Got ESI {evpn_es_table[interface_name]['esi']}, expected '{esi_str}'"
    assert evpn_es_table[interface_name]['type'] == 'TYPE_0_OPERATOR_CONFIGURED', f"Got ESI type {evpn_es_table[interface_name]['type']}, expected 'TYPE_0_OPERATOR_CONFIGURED'"
    assert evpn_es_table[interface_name]['df_pref'] == '32767', f"Found unexpected default df_pref {evpn_es_table[interface_name]['df_pref']}, expected '32767'"

    return result


def configure_mac_esi(runner, db, interface_name):
    result = runner.invoke(config.config.commands["interface"].commands["evpn-esi"].commands['add'], [interface_name, "auto-system-mac"], obj=db)
    assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"

    evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
    assert interface_name in evpn_es_table, f"'{interface_name}' not found in {EVPN_ES_TABLE}"
    assert evpn_es_table[interface_name]['esi'] == 'AUTO', f"Got ESI {evpn_es_table[interface_name]['esi']}, expected 'AUTO'"
    assert evpn_es_table[interface_name]['type'] == 'TYPE_3_MAC_BASED', f"Got ESI type {evpn_es_table[interface_name]['esi']}, expected 'TYPE_3_MAC_BASED'"
    assert evpn_es_table[interface_name]['df_pref'] == '32767', f"Found unexpected default df_pref {evpn_es_table[interface_name]['df_pref']}, expected '32767'"

    return result


def configure_esi_w_failure(runner, db, cli_args:list, error_to_find=None):
    result = runner.invoke(config.config.commands["interface"].commands["evpn-esi"].commands['add'], cli_args, obj=db)
    assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
    assert cli_args[0] not in db['config_db'].get_table(EVPN_ES_TABLE), f"'{cli_args[0]}' was unexpectedly added to {EVPN_ES_TABLE}"

    if error_to_find:
        assert error_to_find in result.output, f"Could not find error message '{error_to_find}' in the following output: {result.output}"

    return result


def delete_esi(runner, db, interface_name):
    result = runner.invoke(config.config.commands["interface"].commands["evpn-esi"].commands['del'], [interface_name], obj=db)
    assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"
    assert interface_name not in db['config_db'].get_table(EVPN_ES_TABLE), f"'{interface_name}' still remains in {EVPN_ES_TABLE}"


@pytest.fixture
def evpn_es_PortChannel01_mac(cli_db_connection):
    runner, db = cli_db_connection
    result = configure_mac_esi(runner, db, 'PortChannel01')
    yield result

    delete_esi(runner, db, 'PortChannel01')


@pytest.fixture
def evpn_es_PortChannel01_manual(cli_db_connection):
    runner, db = cli_db_connection
    result = configure_manual_esi(runner, db, 'PortChannel01', '00:01:02:03:04:05:06:07:08:FF')
    yield result

    delete_esi(runner, db, 'PortChannel01')


class TestEVPNEthernetSegmentManualConfigParsing():
    def test_invalid_manual_esi_wrong_number_of_bytes(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ['PortChannel01', '00:01'],
                                "Failed to parse manual ESI 00:01")


    def test_invalid_manual_esi_wrong_type_byte(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "01:01:02:03:04:05:06:07:08:09"],
                                "Manual ESI must start with type 0, got 01")


    def test_invalid_manual_esi_invalid_byte(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "00:01:02:03:04:ZZ:06:07:08:09"],
                                "Failed to parse ESI byte 'ZZ'")


    def test_invalid_manual_esi_byte_more_than_u8(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "00:01:02:03:04:05:06:AAAA:08:09"],
                                "'Byte' AAAA is > 255")

    def test_reserved_manual_esi_0_rejected(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "00:00:00:00:00:00:00:00:00:00"],
                                "Not allowed to configure a reserved ESI")

    def test_no_traceback_for_hex_byte(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "0f:01:02:03:04:05:06:07:08:09"],
                                "Manual ESI must start with type 0, got 0f")

    def test_reserved_manual_max_esi_rejected(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "ff:FF:ff:ff:ff:ff:ff:ff:ff:ff"],
                                "Not allowed to configure a reserved ESI")

class TestEVPNEthernetSegmentConfig():
    def test_add_del_mac_esi(self, cli_db_connection, evpn_es_PortChannel01_mac):
        # Implicitly tested via the fixtures
        pass

    def test_add_del_manual_esi(self, cli_db_connection, evpn_es_PortChannel01_manual):
        # Implicitly tested via the fixtures
        pass

    def test_add_same_es_twice(self, cli_db_connection, evpn_es_PortChannel01_mac):
        runner, db = cli_db_connection
        result = runner.invoke(config.config.commands["interface"].commands['evpn-esi'].commands["add"], ["PortChannel01", "auto-system-mac"], obj=db)
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"


    def test_del_non_existent_es(self, cli_db_connection):
        runner, db = cli_db_connection
        result = runner.invoke(config.config.commands["interface"].commands['evpn-esi'].commands["del"], ["PortChannel01"], obj=db)
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert "EVPN Ethernet Segment 'PortChannel01' does not exist" in result.output, f"Did not find the help string in {result.output}"


    def test_del_extra_arg(self, cli_db_connection):
        runner, db = cli_db_connection
        result = runner.invoke(config.config.commands["interface"].commands['evpn-esi'].commands["del"], ["PortChannel01", 'extra-arg'], obj=db)
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert "Got unexpected extra argument" in result.output, f'Did not find the extra argument help string in {result.output}'


    def test_add_unknown_esi_type(self, cli_db_connection):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel01", "unknown-esi-type"])


    def test_add_multiple_es(self, cli_db_connection):
        runner, db = cli_db_connection

        configure_mac_esi(runner, db, 'PortChannel01')
        configure_mac_esi(runner, db, 'PortChannel02')
        configure_mac_esi(runner, db, 'PortChannel03')
        configure_manual_esi(runner, db, 'PortChannel11', '00:11:02:03:04:05:06:07:08:09')
        configure_manual_esi(runner, db, 'PortChannel12', '00:12:02:03:04:05:06:07:08:09')
        configure_manual_esi(runner, db, 'PortChannel13', '00:13:02:03:04:05:06:07:08:09')

        configure_df_pref(runner, db, "PortChannel03", 22222, True)

        # Verify no other entries were overwritten
        evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
        for intf in ['PortChannel01', 'PortChannel02', 'PortChannel11', 'PortChannel12', 'PortChannel13']:
            assert evpn_es_table[intf]['df_pref'] == '32767', f"EVPN ES Entry {intf}'s df_pref was overwritten from 32768 to {evpn_es_table[intf]['df_pref']}"

        delete_esi(runner, db, 'PortChannel11')
        delete_esi(runner, db, 'PortChannel01')
        delete_esi(runner, db, 'PortChannel12')
        delete_esi(runner, db, 'PortChannel02')
        delete_esi(runner, db, 'PortChannel13')
        delete_esi(runner, db, 'PortChannel03')

    def test_add_same_manual_esi_twice(self, cli_db_connection, evpn_es_PortChannel01_manual):
        runner, db = cli_db_connection
        configure_esi_w_failure(runner, db, ["PortChannel02", "00:01:02:03:04:05:06:07:08:FF"],
                                "The ESI '00:01:02:03:04:05:06:07:08:FF' is already in use by 'PortChannel01'")


def configure_df_pref(runner, db, interface_name, df_pref_value, df_pref_expected_valid):
    evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
    previous_df_value = evpn_es_table[interface_name]['df_pref']

    result = runner.invoke(config.config.commands["interface"].commands["evpn-df-pref"], [interface_name, str(df_pref_value)], obj=db)

    evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
    if df_pref_expected_valid:
        assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"
        assert evpn_es_table[interface_name]['df_pref'] == str(df_pref_value), f"Found unexpected df_pref {evpn_es_table[interface_name]['df_pref']}, expected '{df_pref_value}'"
    else:
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert evpn_es_table[interface_name]['df_pref'] == previous_df_value, \
                f"Invalid DF pref config changed what is stored in config DB to {evpn_es_table[interface_name]['df_pref']}, expected {previous_df_value}"

    return result


class TestEVPNEthernetSegmentDFConfig():
    @pytest.mark.parametrize("test_df_pref_input,test_df_pref_valid",
                             [
                                (1, True), (65535, True), (32767, True), (16384, True), (48222, True),
                                (-1, False), (0, False), (65536, False), (1000000, False)
                             ])
    def test_df_pref_config(self, cli_db_connection, evpn_es_PortChannel01_mac, test_df_pref_input, test_df_pref_valid):
        runner, db = cli_db_connection
        evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
        prev_es_type = evpn_es_table['PortChannel01']['type']

        configure_df_pref(runner, db, 'PortChannel01', test_df_pref_input, test_df_pref_valid)

        evpn_es_table = db['config_db'].get_table(EVPN_ES_TABLE)
        es_type = evpn_es_table['PortChannel01']['type']
        assert prev_es_type == es_type, f"ES Type changed after applying DF configuration, was {prev_es_type}, changed to {es_type}"


    def test_df_pref_no_es_configured(self, cli_db_connection):
        runner, db = cli_db_connection
        result = runner.invoke(config.config.commands["interface"].commands["evpn-df-pref"], ["PortChannel01", str(33333)], obj=db)

        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert "does not exist" in result.output, f"Did not find the non-existent entry in help string {result.output}"
