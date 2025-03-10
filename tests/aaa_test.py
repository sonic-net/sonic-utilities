import imp
import os
import sys

from click.testing import CliRunner
from utilities_common.db import Db
from jsonpatch import JsonPatchConflict
from unittest import mock
from mock import patch

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import mock_tables.dbconnector

show_aaa_default_output="""\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_failthrough_enable_output = """\
AAA authentication login local (default)
AAA authentication failthrough True
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_failthrough_disable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_fallback_enable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authentication fallback True
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_fallback_disable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authentication fallback False
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_debug_enable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authentication debug True
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_debug_disable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authentication debug False
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_trace_enable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authentication trace True
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_trace_disable_output = """\
AAA authentication login local (default)
AAA authentication failthrough False (default)
AAA authentication trace False
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_radius_output="""\
AAA authentication login radius
AAA authentication failthrough False (default)
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_radius_local_output="""\
AAA authentication login radius,local
AAA authentication failthrough False (default)
AAA authorization login local (default)
AAA accounting login disable (default)

"""

config_aaa_empty_output="""\
"""

config_aaa_not_a_valid_command_output="""\
Not a valid command
"""

show_aaa_tacacs_authentication_output="""\
AAA authentication login tacacs+
AAA authentication failthrough False (default)
AAA authorization login local (default)
AAA accounting login disable (default)

"""

show_aaa_tacacs_authorization_output="""\
AAA authentication login tacacs+
AAA authentication failthrough False (default)
AAA authorization login tacacs+
AAA accounting login disable (default)

"""

show_aaa_tacacs_local_authorization_output="""\
AAA authentication login tacacs+
AAA authentication failthrough False (default)
AAA authorization login tacacs+,local
AAA accounting login disable (default)

"""

show_aaa_tacacs_accounting_output="""\
AAA authentication login tacacs+
AAA authentication failthrough False (default)
AAA authorization login tacacs+,local
AAA accounting login tacacs+

"""

show_aaa_tacacs_local_accounting_output="""\
AAA authentication login tacacs+
AAA authentication failthrough False (default)
AAA authorization login tacacs+,local
AAA accounting login tacacs+,local

"""

show_aaa_disable_accounting_output="""\
AAA authentication login tacacs+
AAA authentication failthrough False (default)
AAA authorization login tacacs+,local
AAA accounting login disable (default)

"""

class TestAaa(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        imp.reload(config.main)
        import show.main
        imp.reload(show.main)

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

    def test_show_aaa_default(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["aaa"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_failthrough(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "failthrough", "enable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_failthrough_enable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "failthrough", "disable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_failthrough_disable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "failthrough", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_fallback(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "fallback", "enable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_fallback_enable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "fallback", "disable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_fallback_disable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "fallback", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_debug(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "debug", "enable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_debug_enable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "debug", "disable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_debug_disable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "debug", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_trace(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "trace", "enable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_trace_enable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "trace", "disable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_trace_disable_output

        result = runner.invoke(config.config.commands["aaa"],
                               ["authentication", "trace", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_radius(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "radius"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_radius_output

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_radius_local(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "radius", "local"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_radius_local_output

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_radius_invalid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "radius", "tacacs+"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_not_a_valid_command_output

    def test_config_aaa_tacacs(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        # test tacacs authentication
        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "tacacs+"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_tacacs_authentication_output

        # test tacacs authorization
        result = runner.invoke(config.config.commands["aaa"],\
                               ["authorization", "tacacs+"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_tacacs_authorization_output

        # test tacacs + local authorization
        result = runner.invoke(config.config.commands["aaa"],\
                               ["authorization", "tacacs+ local"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_tacacs_local_authorization_output

        # test tacacs accounting
        result = runner.invoke(config.config.commands["aaa"],\
                               ["accounting", "tacacs+"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_tacacs_accounting_output

        # test tacacs + local accounting
        result = runner.invoke(config.config.commands["aaa"],\
                               ["accounting", "tacacs+ local"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_tacacs_local_accounting_output

        # test disable accounting
        result = runner.invoke(config.config.commands["aaa"],\
                               ["accounting", "disable"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_disable_accounting_output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_config_aaa_tacacs_delete_yang_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["tacacs"].commands["delete"], ["10.10.10.10"], obj=obj)
        print(result.exit_code)
        assert result.exit_code != 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value={}))
    def test_config_aaa_tacacs_add_yang_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["tacacs"].commands["add"], ["10.10.10.10"], obj=obj)
        print(result.exit_code)
        assert result.exit_code != 0
