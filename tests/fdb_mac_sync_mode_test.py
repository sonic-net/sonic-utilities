import os
import pytest

import show.main as show

from click.testing import CliRunner
from config.main import config
from utilities_common.db import Db


FDB_SYNC_TABLE = 'FDB_SYNC'
EVPN_ES_TABLE = 'EVPN_ETHERNET_SEGMENT'
FDB_SYNC_KEY = 'global'
MAC_SYNC_MODE_FIELD = 'mac_sync_mode'
MAC_SYNC_MODE_DEFAULT = 'kernel'
DEVICE_METADATA_TABLE = 'DEVICE_METADATA'
DEVICE_METADATA_KEY = 'localhost'
L3_EVPN_MH_SUBTYPE = 'L3EvpnMH'


@pytest.fixture
def enable_click_ut_mode():
    os.environ['UTILITIES_UNIT_TESTING'] = "1"
    yield os.environ['UTILITIES_UNIT_TESTING']

    os.environ['UTILITIES_UNIT_TESTING'] = "0"


@pytest.fixture
def cli_db_connection(enable_click_ut_mode):
    db = Db()
    return CliRunner(), db


@pytest.fixture
def l3evpnmh_db_connection(cli_db_connection):
    runner, db = cli_db_connection
    metadata = db.cfgdb.get_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_KEY)
    db.cfgdb.set_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_KEY, dict(metadata, subtype=L3_EVPN_MH_SUBTYPE))
    yield runner, db

    db.cfgdb.set_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_KEY, metadata)


class TestFdbMacSyncModeConfig:
    @pytest.mark.parametrize("mac_sync_mode", ["kernel", "fpm"])
    def test_mac_sync_mode_config(self, cli_db_connection, mac_sync_mode):
        runner, db = cli_db_connection

        result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], [mac_sync_mode], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )

        fdb_sync_table = db.cfgdb.get_table(FDB_SYNC_TABLE)
        assert fdb_sync_table[FDB_SYNC_KEY][MAC_SYNC_MODE_FIELD] == mac_sync_mode, (
            f"Found unexpected {MAC_SYNC_MODE_FIELD} "
            f"{fdb_sync_table[FDB_SYNC_KEY][MAC_SYNC_MODE_FIELD]}, "
            f"expected '{mac_sync_mode}'"
        )

    def test_mac_sync_mode_config_invalid(self, cli_db_connection):
        runner, db = cli_db_connection

        result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], ["bridge"], obj=db)
        assert result.exit_code != 0, (
            f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        )
        assert "kernel" in result.output and "fpm" in result.output, (
            f"Error output does not name the supported modes: {result.output}"
        )

        fdb_sync_table = db.cfgdb.get_table(FDB_SYNC_TABLE)
        assert not fdb_sync_table, (
            f"Invalid mac sync mode changed what is stored in config DB: "
            f"{fdb_sync_table}, expected empty fdb_sync_table"
        )

    # Either mode is valid with an Ethernet Segment configured; guard against a
    # restriction being reintroduced.
    def test_mac_sync_mode_fpm_allowed_with_evpn_mh(self, cli_db_connection):
        runner, db = cli_db_connection
        db.cfgdb.set_entry(EVPN_ES_TABLE, "PortChannel0001", {"esi": "AUTO", "type": "TYPE_3_MAC_BASED"})

        result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], ["fpm"], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected success"
        )

        fdb_sync_table = db.cfgdb.get_table(FDB_SYNC_TABLE)
        written_mode = fdb_sync_table.get(FDB_SYNC_KEY, {}).get(MAC_SYNC_MODE_FIELD)
        assert written_mode == "fpm", (
            f"mac_sync_mode was not written to ConfigDB: {fdb_sync_table}"
        )

    def test_mac_sync_mode_kernel_allowed_with_evpn_mh(self, cli_db_connection):
        runner, db = cli_db_connection
        db.cfgdb.set_entry(EVPN_ES_TABLE, "PortChannel0001", {"esi": "AUTO", "type": "TYPE_3_MAC_BASED"})

        result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], ["kernel"], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert db.cfgdb.get_table(FDB_SYNC_TABLE)[FDB_SYNC_KEY][MAC_SYNC_MODE_FIELD] == "kernel"

    def test_mac_sync_mode_kernel_refused_on_l3evpnmh(self, l3evpnmh_db_connection):
        runner, db = l3evpnmh_db_connection

        result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], ["kernel"], obj=db)
        assert result.exit_code != 0, (
            f"Got zero exit code {result.exit_code} - {result.output}, expected non-zero"
        )
        assert L3_EVPN_MH_SUBTYPE in result.output, (
            f"Error output does not name the {L3_EVPN_MH_SUBTYPE} subtype: {result.output}"
        )
        assert not db.cfgdb.get_table(FDB_SYNC_TABLE), (
            f"Refused mac sync mode changed what is stored in config DB: "
            f"{db.cfgdb.get_table(FDB_SYNC_TABLE)}, expected empty fdb_sync_table"
        )

    def test_mac_sync_mode_fpm_allowed_on_l3evpnmh(self, l3evpnmh_db_connection):
        runner, db = l3evpnmh_db_connection

        result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], ["fpm"], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert db.cfgdb.get_table(FDB_SYNC_TABLE)[FDB_SYNC_KEY][MAC_SYNC_MODE_FIELD] == "fpm"


class TestFdbMacSyncModeShow:
    def test_mac_sync_mode_show_default(self, cli_db_connection):
        runner, db = cli_db_connection

        assert not db.cfgdb.get_table(FDB_SYNC_TABLE), (
            "FDB_SYNC is expected to be absent from the mock CONFIG_DB"
        )

        result = runner.invoke(show.cli.commands["fdb"].commands["mac-sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output.strip() == MAC_SYNC_MODE_DEFAULT, (
            f"Found unexpected {MAC_SYNC_MODE_FIELD} {result.output.strip()}, "
            f"expected the '{MAC_SYNC_MODE_DEFAULT}' default"
        )

    def test_mac_sync_mode_show_entry_without_mode(self, cli_db_connection):
        runner, db = cli_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {})
        assert FDB_SYNC_KEY in db.cfgdb.get_keys(FDB_SYNC_TABLE)

        result = runner.invoke(show.cli.commands["fdb"].commands["mac-sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output.strip() == MAC_SYNC_MODE_DEFAULT, (
            f"Found unexpected {MAC_SYNC_MODE_FIELD} {result.output.strip()}, "
            f"expected the '{MAC_SYNC_MODE_DEFAULT}' default"
        )

    @pytest.mark.parametrize("mac_sync_mode", ["kernel", "fpm"])
    def test_mac_sync_mode_show_configured(self, cli_db_connection, mac_sync_mode):
        runner, db = cli_db_connection

        config_result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], [mac_sync_mode], obj=db)
        assert config_result.exit_code == 0, (
            f"Got exit code {config_result.exit_code} - {config_result.output}, expected 0"
        )

        result = runner.invoke(show.cli.commands["fdb"].commands["mac-sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output.strip() == mac_sync_mode, (
            f"Found unexpected {MAC_SYNC_MODE_FIELD} {result.output.strip()}, "
            f"expected '{mac_sync_mode}'"
        )

    @pytest.mark.parametrize("mac_sync_mode", [None, "kernel", "fpm"])
    def test_show_mac_sync_mode_matches_show_fdb(self, cli_db_connection, mac_sync_mode):
        runner, db = cli_db_connection

        if mac_sync_mode:
            config_result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], [mac_sync_mode], obj=db)
            assert config_result.exit_code == 0, (
                f"Got exit code {config_result.exit_code} - {config_result.output}, expected 0"
            )

        fdb_result = runner.invoke(show.cli.commands["fdb"].commands["mac-sync-mode"], [], obj=db)
        mac_result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert mac_result.exit_code == 0, (
            f"Got exit code {mac_result.exit_code} - {mac_result.output}, expected 0"
        )
        assert mac_result.output == fdb_result.output == (mac_sync_mode or MAC_SYNC_MODE_DEFAULT) + "\n", (
            f"show mac sync-mode printed {mac_result.output!r}, show fdb mac-sync-mode {fdb_result.output!r}"
        )

    @pytest.mark.parametrize("group,command", [("fdb", "mac-sync-mode"), ("mac", "sync-mode")])
    def test_mac_sync_mode_show_l3evpnmh_is_fpm(self, l3evpnmh_db_connection, group, command):
        runner, db = l3evpnmh_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: "kernel"})

        result = runner.invoke(show.cli.commands[group].commands[command], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output.strip() == "fpm", (
            f"Found unexpected {MAC_SYNC_MODE_FIELD} {result.output.strip()} on an "
            f"{L3_EVPN_MH_SUBTYPE} device, expected 'fpm'"
        )
