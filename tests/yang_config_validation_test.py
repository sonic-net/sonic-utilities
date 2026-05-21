from click.testing import CliRunner
from utilities_common.db import Db
from unittest import mock
from mock import patch
import config.main as config
import config.validated_config_db_connector as validated_config_db_connector

class TestYangConfigValidation(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def __check_result(self, result_msg, mode):
        if mode == "enable" or mode == "disable":
            expected_msg = """Wrote %s yang config validation into CONFIG_DB""" % mode
        else:
            expected_msg = "Error: Invalid argument %s, expect either enable or disable" % mode

        return expected_msg in result_msg

    def test_yang_config_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()

        result = runner.invoke(config.config.commands["yang_config_validation"], ["enable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "enable")

        result = runner.invoke(config.config.commands["yang_config_validation"], ["disable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "disable")

        result = runner.invoke(config.config.commands["yang_config_validation"], ["invalid-input"])
        print(result.output)
        assert result.exit_code != 0
        assert self.__check_result(result.output, "invalid-input")

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_invalid_yang_config_validation_using_yang(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["yang_config_validation"], ["invalid-input"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert self.__check_result(result.output, "invalid-input")
