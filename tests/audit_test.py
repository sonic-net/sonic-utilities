import show.main as show
import config.main as config
from mock import call, patch, Mock
from utilities_common.db import Db
from click.testing import CliRunner
import config.validated_config_db_connector as validated_config_db_connector # noqa F401

AUDIT_CONFIG_DIR = "/etc/audit/rules.d/"
is_yang_config_validation_enabled_patch = "validated_config_db_connector.device_info.is_yang_config_validation_enabled"
validated_mod_entry_patch = "config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry"


class TestConfigAudit(object):
    def setup_method(self):
        print('SETUP')

    @patch("click.echo")
    @patch(is_yang_config_validation_enabled_patch, Mock(return_value=True))
    @patch(validated_mod_entry_patch)
    def test_config_enable_audit_success(self, mock_mod_entry, mock_echo):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["audit"].commands["enable"], obj=obj)

        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert mock_mod_entry.call_args_list == [call("AUDIT", "config", {"enabled": "true"})]
        assert mock_echo.call_args_list == [call("Security auditing is enabled.")]

    @patch("click.echo")
    @patch(is_yang_config_validation_enabled_patch, Mock(return_value=True))
    @patch(validated_mod_entry_patch, Mock(side_effect=ValueError))
    def test_config_enable_audit_failed(self, mock_echo):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["audit"].commands["enable"], obj=obj)

        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 2
        assert "Invalid ConfigDB. Error" in result.output
        mock_echo.assert_not_called()

    @patch("click.echo")
    @patch(is_yang_config_validation_enabled_patch, Mock(return_value=True))
    @patch(validated_mod_entry_patch)
    def test_config_disable_audit_success(self, mock_mod_entry, mock_echo):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["audit"].commands["disable"], obj=obj)

        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert mock_mod_entry.call_args_list == [call("AUDIT", "config", {"enabled": "false"})]
        assert mock_echo.call_args_list == [call("Security auditing is disabled.")]

    @patch("click.echo")
    @patch(is_yang_config_validation_enabled_patch, Mock(return_value=True))
    @patch(validated_mod_entry_patch, Mock(side_effect=ValueError))
    def test_config_disable_audit_failed(self, mock_echo):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["audit"].commands["disable"], obj=obj)

        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 2
        assert "Invalid ConfigDB. Error" in result.output
        mock_echo.assert_not_called()

    def teardown_method(self):
        print('TEAR DOWN')


class TestShowAudit(object):
    def setup_method(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    @patch("click.echo")
    def test_show_audit(self, mock_echo, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['audit'])

        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert mock_echo.call_args_list == [
            call("List of current .rules files in {} directory".format(AUDIT_CONFIG_DIR)),
            call("\nList of all current active audit rules")
        ]
        assert mock_run_command.call_args_list == [
            call(['sudo', 'ls', AUDIT_CONFIG_DIR]),
            call(['sudo', 'auditctl', '-l'])
        ]

    def teardown_method(self):
        print('TEAR DOWN')
