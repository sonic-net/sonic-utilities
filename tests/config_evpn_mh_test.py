import os
import pytest

from click.testing import CliRunner
from utilities_common.db import Db
from config.main import config
from config.evpn_mh import EVPN_MH_TABLE


@pytest.fixture
def enable_click_ut_mode():
    os.environ['UTILITIES_UNIT_TESTING'] = "1"
    yield os.environ['UTILITIES_UNIT_TESTING']

    os.environ['UTILITIES_UNIT_TESTING'] = "0"

@pytest.fixture
def cli_db_connection(enable_click_ut_mode):
    return CliRunner(), {'config_db': Db().cfgdb}


#test startup_delay config
def configure_startup_delay(runner, db, startup_delay_value, startup_delay_expected_valid):
    evpn_mh_table = db['config_db'].get_table(EVPN_MH_TABLE)

    result = runner.invoke(config.commands["evpn-mh"].commands["startup-delay"], [str(startup_delay_value)], obj=db)
    evpn_mh_table = db['config_db'].get_table(EVPN_MH_TABLE)
    if startup_delay_expected_valid:
        assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"
        assert evpn_mh_table['default']['startup_delay'] == str(startup_delay_value), f"Found unexpected startup_delay {evpn_mh_table['default']['startup_delay']}, expected '{startup_delay_value}'"
    else:
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert not evpn_mh_table, f"Invalid startup delay config changed what is stored in config DB: {evpn_mh_table}, expected empty evpn_mh_table"

    return result

class TestEVPNMultiHomingStartupDelayConfig:
    @pytest.mark.parametrize("test_startup_delay_input,test_startup_delay_valid",
                             [
                                (0, True), (1, True), (300, True), (3600, True), (1800, True), (900, True), (2700, True),
                                (-1, False), (3601, False), (10000, False)
                             ])
    def test_startup_delay_config(self, cli_db_connection, test_startup_delay_input, test_startup_delay_valid):
        runner, db = cli_db_connection
        configure_startup_delay(runner, db, test_startup_delay_input, test_startup_delay_valid)

#test mac_holdtime config
def configure_mac_holdtime(runner, db, mac_holdtime_value, mac_holdtime_expected_valid):
    evpn_mh_table = db['config_db'].get_table(EVPN_MH_TABLE)
    previous_mac_holdtime_value = None
    if 'default' in evpn_mh_table.keys():
        previous_mac_holdtime_value = evpn_mh_table['default']['mac_holdtime']

    result = runner.invoke(config.commands["evpn-mh"].commands["mac-holdtime"], [str(mac_holdtime_value)], obj=db)
    evpn_mh_table = db['config_db'].get_table(EVPN_MH_TABLE)
    if mac_holdtime_expected_valid:
        assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"
        assert evpn_mh_table['default']['mac_holdtime'] == str(mac_holdtime_value), f"Found unexpected mac_holdtime {evpn_mh_table['default']['mac_holdtime']}, expected '{mac_holdtime_value}'"
    else:
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert not evpn_mh_table, f"Invalid mac holdtime config changed what is stored in config DB: {evpn_mh_table}, expected empty evpn_mh_table"

    return result

class TestEVPNMultiHomingMACHoldtimeConfig:
    @pytest.mark.parametrize("test_mac_holdtime_input,test_mac_holdtime_valid",
                             [
                                (0, True), (1, True), (1080, True), (86400, True), (43200, True), (21600, True), (64800, True),
                                (-1, False), (86401, False), (100000, False)
                             ])
    def test_mac_holdtime_config(self, cli_db_connection, test_mac_holdtime_input, test_mac_holdtime_valid):
        runner, db = cli_db_connection
        configure_mac_holdtime(runner, db, test_mac_holdtime_input, test_mac_holdtime_valid)


#test neigh_holdtime config
def configure_neigh_holdtime(runner, db, neigh_holdtime_value, neigh_holdtime_expected_valid):
    evpn_mh_table = db['config_db'].get_table(EVPN_MH_TABLE)
    previous_neigh_holdtime_value = None
    if 'default' in evpn_mh_table.keys():
        previous_neigh_holdtime_value = evpn_mh_table['default']['neigh_holdtime']

    result = runner.invoke(config.commands["evpn-mh"].commands["neigh-holdtime"], [str(neigh_holdtime_value)], obj=db)
    evpn_mh_table = db['config_db'].get_table(EVPN_MH_TABLE)
    if neigh_holdtime_expected_valid:
        assert result.exit_code == 0, f"Got exit code {result.exit_code} - {result.output}, expected 0"
        assert evpn_mh_table['default']['neigh_holdtime'] == str(neigh_holdtime_value), f"Found unexpected neigh_holdtime {evpn_mh_table['default']['neigh_holdtime']}, expected '{neigh_holdtime_value}'"
    else:
        assert result.exit_code != 0, f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        assert not evpn_mh_table, f"Invalid neigh holdtime config changed what is stored in config DB: {evpn_mh_table}, expected empty evpn_mh_table"

    return result

class TestEVPNMultiHomingNeighHoldtimeConfig:
    @pytest.mark.parametrize("test_neigh_holdtime_input,test_neigh_holdtime_valid",
                             [
                                (0, True), (1, True), (1080, True), (86400, True), (43200, True), (21600, True), (64800, True),
                                (-1, False), (86401, False), (100000, False)
                             ])
    def test_neigh_holdtime_config(self, cli_db_connection, test_neigh_holdtime_input, test_neigh_holdtime_valid):
        runner, db = cli_db_connection
        configure_neigh_holdtime(runner, db, test_neigh_holdtime_input, test_neigh_holdtime_valid)


