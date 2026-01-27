import os
import logging


import show.main as show
import config.main as config

from click.testing import CliRunner
from utilities_common.db import Db
from .mock_tables import dbconnector


logger = logging.getLogger(__name__)


SUCCESS = 0
ERROR2 = 2


test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "fast_linkup_input")
mock_state_path = os.path.join(input_path, "mock_state")
mock_config_path = os.path.join(input_path, "mock_config")


class TestFastLinkupCLI:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: %s", cls.__name__)
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: %s", cls.__name__)
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs.clear()

    def test_config_global_not_supported(self):
        # STATE_DB indicates not supported
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "not_supported", "state_db")
        db = Db()
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            ["--polling-time", "60"], obj=db
        )
        # Current CLI raises ClickException -> exit code 1
        assert result.exit_code != SUCCESS
        assert "not supported" in result.output.lower()

    def test_config_global_range_validation(self):
        # STATE_DB indicates supported with ranges polling:[5,120], guard:[1,20]
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        db = Db()
        runner = CliRunner()

        # Below min polling -> error
        res1 = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            ["--polling-time", "4"], obj=db
        )
        assert res1.exit_code != SUCCESS

        # Above max guard -> error
        res2 = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            ["--guard-time", "21"], obj=db
        )
        assert res2.exit_code != SUCCESS

        # In-range values -> success
        res3 = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            ["--polling-time", "60", "--guard-time", "10", "--ber", "12"], obj=db
        )
        assert res3.exit_code == SUCCESS

    # show command tests:
    # 1. Validate default global values match show output (feature supported)
    # 2. Validate configured global values via config CLI match show output
    def test_show_global_configured_values(self, monkeypatch):
        # Provide CONFIG_DB with a pre-set global entry and verify JSON output matches exactly
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "global", "config_db")
        db = Db()
        runner = CliRunner()
        # Ensure show command uses our injected Db
        monkeypatch.setattr(show, 'Db', lambda: db)
        result = runner.invoke(
            show.cli.commands["switch-fast-linkup"].commands["global"],
            ["--json"], obj=db
        )
        assert result.exit_code == SUCCESS
        import json
        data = json.loads(result.output)
        assert data == {"polling_time": "60", "guard_time": "10", "ber_threshold": "12"}

    def test_show_interfaces_mode(self, monkeypatch):
        # Provide CONFIG_DB with PORT table fast_linkup fields
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["fast-linkup"].commands["status"],
            [], obj=db
        )
        assert result.exit_code == SUCCESS
        self.assert_interface_fast_linkup_mode(result.output, "Ethernet0", "true")

    def test_enable_fast_linkup_supported(self, monkeypatch):
        # Use supported STATE_DB (FAST_LINKUP_CAPABLE == 'true')
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()

        # Patch command runner to simulate 'portconfig -fl' writing to CONFIG_DB
        import utilities_common.cli as clicommon

        def fake_run_command(
            cmd,
            display_cmd=False,
            ignore_error=False,
            return_cmd=False,
            interactive_mode=False,
            shell=False,
        ):
            # Expect: ['portconfig', '-p', <iface>, '-fl', <enabled|disabled>]
            assert cmd[0] == 'portconfig'
            iface = cmd[cmd.index('-p') + 1]
            mode = cmd[cmd.index('-fl') + 1]
            value = 'true' if mode == 'enabled' else 'false'
            db.cfgdb.mod_entry('PORT', iface, {'fast_linkup': value})
            return

        monkeypatch.setattr(clicommon, 'run_command', fake_run_command)
        # Enable fast-linkup on Ethernet0 via config CLI
        result = runner.invoke(
            config.config.commands["interface"].commands["fast-linkup"],
            ["Ethernet0", "enabled"],
            obj={'config_db': db.cfgdb, 'namespace': config.DEFAULT_NAMESPACE}
        )
        assert result.exit_code == SUCCESS

        # Show reflects change
        import show.interfaces as show_interfaces
        # Ensure 'show interfaces ...' reads from the same CONFIG_DB instance modified above
        monkeypatch.setattr(show_interfaces, 'ConfigDBConnector', lambda: db.cfgdb)
        show_result = runner.invoke(
            show.cli.commands["interfaces"].commands["fast-linkup"].commands["status"],
            [], obj=db
        )
        self.assert_interface_fast_linkup_mode(show_result.output, "Ethernet0", "true")

    def test_disable_fast_linkup_supported(self, monkeypatch):
        # Use supported STATE_DB (FAST_LINKUP_CAPABLE == 'true')
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()

        import utilities_common.cli as clicommon

        def fake_run_command(
            cmd,
            display_cmd=False,
            ignore_error=False,
            return_cmd=False,
            interactive_mode=False,
            shell=False,
        ):
            iface = cmd[cmd.index('-p') + 1]
            mode = cmd[cmd.index('-fl') + 1]
            value = 'true' if mode == 'enabled' else 'false'
            db.cfgdb.mod_entry('PORT', iface, {'fast_linkup': value})
            return

        monkeypatch.setattr(clicommon, 'run_command', fake_run_command)

        # Disable fast-linkup on Ethernet0 via config CLI
        result = runner.invoke(
            config.config.commands["interface"].commands["fast-linkup"],
            ["Ethernet0", "disabled"],
            obj={'config_db': db.cfgdb, 'namespace': config.DEFAULT_NAMESPACE}
        )
        assert result.exit_code == SUCCESS

        # Show reflects change
        import show.interfaces as show_interfaces
        # Ensure 'show interfaces ...' reads from the same CONFIG_DB instance modified above
        monkeypatch.setattr(show_interfaces, 'ConfigDBConnector', lambda: db.cfgdb)
        show_result = runner.invoke(
            show.cli.commands["interfaces"].commands["fast-linkup"].commands["status"],
            [], obj=db
        )
        self.assert_interface_fast_linkup_mode(show_result.output, "Ethernet0", "false")

    def test_enable_fast_linkup_not_supported(self, monkeypatch):
        # Use not_supported STATE_DB (FAST_LINKUP_CAPABLE == 'false')
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "not_supported", "state_db")
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()

        import utilities_common.cli as clicommon

        def fake_run_command(
            cmd,
            display_cmd=False,
            ignore_error=False,
            return_cmd=False,
            interactive_mode=False,
            shell=False,
        ):
            # In not-supported scenario, config command should fail before invoking portconfig,
            # but if invoked, simulate failure.
            raise SystemExit(1)

        monkeypatch.setattr(clicommon, 'run_command', fake_run_command)

        result = runner.invoke(
            config.config.commands["interface"].commands["fast-linkup"],
            ["Ethernet0", "enabled"],
            obj={'config_db': db.cfgdb, 'namespace': config.DEFAULT_NAMESPACE}
        )
        assert result.exit_code != SUCCESS

    # Helper: Assert that the specified interface has the expected fast-linkup mode in the CLI output.
    def assert_interface_fast_linkup_mode(self, output, intf_name, expected_mode):
        for line in output.splitlines():
            if intf_name in line and expected_mode.lower() in line.lower():
                return
        raise AssertionError(f"{intf_name} fast-linkup mode is not set to {expected_mode}")

    def test_config_global_no_options(self):
        # No options -> UsageError
        db = Db()
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            [],
            obj=db
        )
        assert result.exit_code != SUCCESS
        assert "no options are provided" in result.output.lower()

    def test_config_global_set_entry_failure(self, monkeypatch):
        # If set_entry raises, command should exit with code 1
        class FakeState:
            STATE_DB = "STATE_DB"

            def get_all(self, db, key):
                return {
                    "FAST_LINKUP_CAPABLE": "true",
                    "FAST_LINKUP_POLLING_TIMER_RANGE": "5,120",
                    "FAST_LINKUP_GUARD_TIMER_RANGE": "1,20"
                }

        class FakeCfg:
            def get_entry(self, *args, **kwargs):
                return {}

            def set_entry(self, *args, **kwargs):
                raise Exception()

        class FakeDb:
            def __init__(self):
                self.db = FakeState()
                self.cfgdb = FakeCfg()
        fake_db = FakeDb()

        runner = CliRunner()
        res = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            ["--polling-time", "60"],
            obj=fake_db
        )
        assert res.exit_code != SUCCESS

    def test_config_global_ber_out_of_range(self):
        # Use supported STATE_DB; out-of-range BER should error
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        db = Db()
        runner = CliRunner()
        res = runner.invoke(
            config.config.commands["switch-fast-linkup"].commands["global"],
            ["--ber", "0"],
            obj=db
        )
        assert res.exit_code != SUCCESS
        assert "ber_threshold" in res.output

    def test_config_interface_alias_none(self, monkeypatch):
        # Alias mode with alias not found -> ctx.fail("'interface_name' is None!")
        import utilities_common.cli as clicommon
        monkeypatch.setattr(clicommon, "get_interface_naming_mode", lambda: "alias")
        monkeypatch.setattr(config, "interface_alias_to_name", lambda cfgdb, name: None)
        # STATE_DB capability supported so we get to alias resolution
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["interface"].commands["fast-linkup"],
            ["EthAlias0", "enabled"],
            obj={'config_db': db.cfgdb, 'namespace': config.DEFAULT_NAMESPACE}
        )
        assert result.exit_code != SUCCESS
        assert "interface_name" in result.output

    def test_config_interface_invalid_name(self, monkeypatch):
        # Invalid interface name -> ctx.fail()
        import utilities_common.cli as clicommon
        monkeypatch.setattr(clicommon, "get_interface_naming_mode", lambda: "default")
        monkeypatch.setattr(config, "interface_name_is_valid", lambda cfgdb, name: False)
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["interface"].commands["fast-linkup"],
            ["Ethernet999", "enabled"],
            obj={'config_db': db.cfgdb, 'namespace': config.DEFAULT_NAMESPACE}
        )
        assert result.exit_code != SUCCESS
        assert "invalid" in result.output.lower()

    def test_config_interface_namespace_portconfig(self, monkeypatch):
        # Ensure namespace is passed to portconfig in multi-ASIC mode
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "supported", "state_db")
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ports", "config_db")
        db = Db()
        runner = CliRunner()

        import utilities_common.cli as clicommon

        def fake_run_command(
            cmd,
            display_cmd=False,
            ignore_error=False,
            return_cmd=False,
            interactive_mode=False,
            shell=False,
        ):
            assert '-n' in cmd
            ns_index = cmd.index('-n') + 1
            assert cmd[ns_index] == 'asic0'
            return

        monkeypatch.setattr(clicommon, 'run_command', fake_run_command)
        result = runner.invoke(
            config.config.commands["interface"].commands["fast-linkup"],
            ["Ethernet0", "enabled"],
            obj={'config_db': db.cfgdb, 'namespace': 'asic0'}
        )
        assert result.exit_code == SUCCESS

    def test_show_switch_fast_linkup_group_help(self):
        # Enter group to cover the 'pass' in group callback
        runner = CliRunner()
        res = runner.invoke(show.cli, ["switch-fast-linkup", "--help"])
        assert res.exit_code == SUCCESS
        assert "Show fast link-up feature configuration" in res.output

    def test_show_global_table_output(self, monkeypatch):
        # Non-JSON output should render table rows
        # Align with test_show_global_configured_values: set dedicated_dbs and monkeypatch show.Db
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "global", "config_db")
        db = Db()
        runner = CliRunner()
        monkeypatch.setattr(show, 'Db', lambda: db)
        res = runner.invoke(show.cli.commands["switch-fast-linkup"].commands["global"], [], obj=db)
        assert res.exit_code == SUCCESS
        assert "polling_time" in res.output and "60" in res.output

    def test_show_interfaces_fast_linkup_group_help(self):
        # Cover 'pass' in 'show interfaces fast-linkup' group
        runner = CliRunner()
        res = runner.invoke(show.cli, ["interfaces", "fast-linkup", "--help"])
        assert res.exit_code == SUCCESS
