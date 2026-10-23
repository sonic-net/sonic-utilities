import os
from importlib import reload

import mock

from click.testing import CliRunner

import config.main
import show.main
import utilities_common.multi_asic
from utilities_common.db import Db


FDB_SYNC_TABLE = 'FDB_SYNC'
FDB_SYNC_KEY = 'global'
MAC_SYNC_MODE_FIELD = 'mac_sync_mode'
DEVICE_METADATA_TABLE = 'DEVICE_METADATA'
DEVICE_METADATA_KEY = 'localhost'
SHOW_COMMANDS = (("mac", "sync-mode"), ("fdb", "mac-sync-mode"))


class TestMultiAsicFdbMacSyncMode:
    """Each ASIC's fpmsyncd and fdbsyncd read the CONFIG_DB of their namespace, not the host's."""

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        from mock_tables import dbconnector
        dbconnector.load_namespace_config()

        reload(utilities_common.multi_asic)
        reload(show.main)
        reload(config.main)

    def test_config_requires_namespace(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.main.config.commands["fdb"], ["mac-sync-mode", "fpm"], obj=db)

        assert result.exit_code != 0, result.output
        assert "Missing option" in result.output

    def test_config_sets_only_the_selected_namespace(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.main.config.commands["fdb"], ["-n", "asic0", "mac-sync-mode", "fpm"], obj=db)

        assert result.exit_code == 0, result.output
        assert db.cfgdb_clients["asic0"].get_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY) == {MAC_SYNC_MODE_FIELD: "fpm"}
        assert db.cfgdb_clients["asic1"].get_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY) == {}
        assert db.cfgdb.get_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY) == {}

    def test_config_kernel_refused_only_on_an_l3evpnmh_namespace(self):
        runner = CliRunner()
        db = Db()
        asic1 = db.cfgdb_clients["asic1"]
        metadata = asic1.get_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_KEY)
        asic1.set_entry(DEVICE_METADATA_TABLE, DEVICE_METADATA_KEY, dict(metadata, subtype='L3EvpnMH'))

        result = runner.invoke(config.main.config.commands["fdb"], ["-n", "asic1", "mac-sync-mode", "kernel"], obj=db)
        assert result.exit_code != 0, result.output
        assert "L3EvpnMH" in result.output

        result = runner.invoke(config.main.config.commands["fdb"], ["-n", "asic0", "mac-sync-mode", "kernel"], obj=db)
        assert result.exit_code == 0, result.output

    def test_config_validated_write_targets_the_selected_namespace(self):
        # With YANG validation on, the write goes through GenericUpdater, which must run in asic0.
        runner = CliRunner()
        db = Db()

        with mock.patch('config.validated_config_db_connector.device_info.is_yang_config_validation_enabled',
                        return_value=True), \
                mock.patch('config.validated_config_db_connector.GenericUpdater') as mock_generic_updater:
            result = runner.invoke(config.main.config.commands["fdb"], ["-n", "asic0", "mac-sync-mode", "fpm"], obj=db)

        assert result.exit_code == 0, result.output
        mock_generic_updater.assert_called_once_with(scope="asic0")
        patch = mock_generic_updater.return_value.apply_patch.call_args[1]["patch"]
        assert {"op": "add", "path": "/FDB_SYNC/global/mac_sync_mode", "value": "fpm"} in patch.patch

    def test_show_reads_the_selected_namespace(self):
        # asic0 runs fpm mode and the host has no FDB_SYNC entry.
        runner = CliRunner()
        db = Db()
        db.cfgdb_clients["asic0"].set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: "fpm"})

        for group, command in SHOW_COMMANDS:
            result = runner.invoke(show.main.cli.commands[group], ["-n", "asic0", command], obj=db)
            assert result.exit_code == 0, result.output
            assert result.output == "fpm\n", f"show {group} -n asic0 {command}"

            result = runner.invoke(show.main.cli.commands[group], ["-n", "asic1", command], obj=db)
            assert result.exit_code == 0, result.output
            assert result.output == "kernel\n", f"show {group} -n asic1 {command}"

    def test_show_names_each_namespace_without_a_selection(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb_clients["asic0"].set_entry(FDB_SYNC_TABLE, FDB_SYNC_KEY, {MAC_SYNC_MODE_FIELD: "fpm"})

        for group, command in SHOW_COMMANDS:
            result = runner.invoke(show.main.cli.commands[group], [command], obj=db)
            assert result.exit_code == 0, result.output
            assert result.output == "asic0: fpm\nasic1: kernel\n", f"show {group} {command}"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from mock_tables import mock_single_asic
        reload(mock_single_asic)
        from mock_tables import dbconnector
        dbconnector.load_database_config()

        reload(utilities_common.multi_asic)
        reload(show.main)
        reload(config.main)
