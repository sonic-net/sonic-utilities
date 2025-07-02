from click.testing import CliRunner
from utilities_common.db import Db
from unittest import mock
from mock import patch
from .mock_tables import dbconnector
import config.main as config
import config.validated_config_db_connector as validated_config_db_connector 

class TestSynchronousMode(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        dbconnector.load_namespace_config()

    def __check_result(self, result_msg, mode):
        if mode == "enable" or mode == "disable":
            expected_msg = """Wrote %s synchronous mode into CONFIG_DB, swss restart required to apply the configuration: \n
    Option 1. config save -y \n
              config reload -y \n
    Option 2. systemctl restart swss"""  % mode
        else:
            expected_msg = "Error: Invalid argument %s, expect either enable or disable" % mode

        return expected_msg in result_msg


    def test_synchronous_mode(self):
        runner = CliRunner()

        result = runner.invoke(config.config.commands["synchronous_mode"], ["enable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "enable")

        result = runner.invoke(config.config.commands["synchronous_mode"], ["disable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "disable")

        result = runner.invoke(config.config.commands["synchronous_mode"], ["invalid-input"])
        print(result.output)
        assert result.exit_code != 0
        assert self.__check_result(result.output, "invalid-input")

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_synchronous_mode_invalid_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["synchronous_mode"], ["invalid-input"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert self.__check_result(result.output, "invalid-input")
