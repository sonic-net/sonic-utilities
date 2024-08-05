import show.main as show
import config.main as config
from mock import patch, Mock
from utilities_common.db import Db
from click.testing import CliRunner
import config.validated_config_db_connector as validated_config_db_connector # noqa F401

is_yang_config_validation_enabled_patch = "validated_config_db_connector.device_info.is_yang_config_validation_enabled"
validated_mod_entry_patch = "config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry"


class TestConfigAudit(object):
    def setup(self):
        print('SETUP')

    @patch(is_yang_config_validation_enabled_patch, Mock(return_value=True))
    @patch(validated_mod_entry_patch, Mock(side_effect=ValueError))
    def test_enable_audit(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(config.config.commands["audit"].commands["enable"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    @patch(is_yang_config_validation_enabled_patch, Mock(return_value=True))
    @patch(validated_mod_entry_patch, Mock(side_effect=ValueError))
    def test_disable_audit(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(config.config.commands["audit"].commands["disable"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    def teardown(self):
        print('TEAR DOWN')


class TestShowAudit(object):
    def setup(self):
        print('SETUP')

    @patch('utilities_common.cli.run_command')
    def test_show_audit(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands['audit'])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        mock_run_command.assert_called_once_with(['sudo', 'auditctl', '-l'])

    def teardown(self):
        print('TEAR DOWN')
