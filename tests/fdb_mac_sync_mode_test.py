import json
import os
import pytest

import show.main as show

from click.testing import CliRunner
from config.main import config, config_file_yang_validation
from utilities_common.db import Db


FDB_SYNC_TABLE = 'FDB_SYNC'
EVPN_ES_TABLE = 'EVPN_ETHERNET_SEGMENT'
FDB_SYNC_KEY = 'global'
MAC_SYNC_MODE_FIELD = 'mac_sync_mode'
MAC_SYNC_MODE_DEFAULT = 'kernel'
STATE_FDB_SYNC_KEY = 'FDB_SYNC|global'
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


def show_output(configured, running="unknown", note=False):
    out = f"Configured: {configured}\nRunning: {running}\n"
    if note:
        out += "The configured mode takes effect when the bgp container restarts.\n"
    return out


@pytest.fixture
def running_mode(cli_db_connection):
    """Publish the running mode the way fpmsyncd does, and remove it afterwards."""
    _, db = cli_db_connection

    def publish(mode):
        db.db.set("STATE_DB", STATE_FDB_SYNC_KEY, MAC_SYNC_MODE_FIELD, mode)

    yield publish
    db.db.delete("STATE_DB", STATE_FDB_SYNC_KEY)


class TestFdbMacSyncModeShow:
    def test_mac_sync_mode_show_default(self, cli_db_connection):
        runner, db = cli_db_connection

        assert not db.cfgdb.get_table(FDB_SYNC_TABLE), (
            "FDB_SYNC is expected to be absent from the mock CONFIG_DB"
        )

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output(MAC_SYNC_MODE_DEFAULT), (
            f"Found unexpected output {result.output!r}, "
            f"expected the '{MAC_SYNC_MODE_DEFAULT}' default and an unknown running mode"
        )

    def test_mac_sync_mode_show_entry_without_mode(self, cli_db_connection):
        runner, db = cli_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {})
        assert FDB_SYNC_KEY in db.cfgdb.get_keys(FDB_SYNC_TABLE)

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output(MAC_SYNC_MODE_DEFAULT), (
            f"Found unexpected output {result.output!r}, expected the '{MAC_SYNC_MODE_DEFAULT}' default"
        )

    @pytest.mark.parametrize("mac_sync_mode", ["kernel", "fpm"])
    def test_mac_sync_mode_show_configured(self, cli_db_connection, mac_sync_mode):
        runner, db = cli_db_connection

        config_result = runner.invoke(config.commands["fdb"].commands["mac-sync-mode"], [mac_sync_mode], obj=db)
        assert config_result.exit_code == 0, (
            f"Got exit code {config_result.exit_code} - {config_result.output}, expected 0"
        )

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output(mac_sync_mode), (
            f"Found unexpected output {result.output!r}, expected configured '{mac_sync_mode}'"
        )

    @pytest.mark.parametrize("configured,running,note", [
        ("fpm", "fpm", False),
        ("kernel", "kernel", False),
        # Configured but the bgp container has not restarted yet.
        ("fpm", "kernel", True),
        ("kernel", "fpm", True),
        # Anything but an exact 'fpm' runs as kernel, so a hand-edited value changes nothing on restart.
        ("FPM", "kernel", False),
        ("bogus", "kernel", False),
        ("bogus", "fpm", True),
    ])
    def test_mac_sync_mode_show_running(self, cli_db_connection, running_mode, configured, running, note):
        runner, db = cli_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: configured})
        running_mode(running)

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output(configured, running, note), (
            f"show mac sync-mode printed {result.output!r}"
        )

    def test_mac_sync_mode_show_running_empty(self, cli_db_connection, running_mode):
        runner, db = cli_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: "fpm"})
        running_mode("")

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output("fpm"), (
            f"Found unexpected output {result.output!r}, expected an unknown running mode and no note"
        )

    def test_mac_sync_mode_show_l3evpnmh_running_kernel(self, l3evpnmh_db_connection, running_mode):
        runner, db = l3evpnmh_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: "kernel"})
        running_mode("kernel")

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output("fpm", "kernel", True), (
            f"Found unexpected output {result.output!r} on an {L3_EVPN_MH_SUBTYPE} device running kernel"
        )

    def test_mac_sync_mode_show_l3evpnmh_is_fpm(self, l3evpnmh_db_connection):
        runner, db = l3evpnmh_db_connection
        db.cfgdb.set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: "kernel"})

        result = runner.invoke(show.cli.commands["mac"].commands["sync-mode"], [], obj=db)
        assert result.exit_code == 0, (
            f"Got exit code {result.exit_code} - {result.output}, expected 0"
        )
        assert result.output == show_output("fpm"), (
            f"Found unexpected output {result.output!r} on an {L3_EVPN_MH_SUBTYPE} device, "
            f"expected configured 'fpm'"
        )


# config reload validates the saved config against the installed YANG models and aborts on a table that has none,
# so this fails until the FDB_SYNC model of sonic-net/sonic-buildimage#30365 is installed.
class TestFdbSyncYangModel:
    @pytest.mark.parametrize("mac_sync_mode", ["kernel", "fpm"])
    def test_saved_mac_sync_mode_passes_config_reload_validation(self, tmp_path, mac_sync_mode):
        config_file = tmp_path / "config_db.json"
        config_file.write_text(json.dumps({FDB_SYNC_TABLE: {FDB_SYNC_KEY: {MAC_SYNC_MODE_FIELD: mac_sync_mode}}}))

        assert config_file_yang_validation(str(config_file))
