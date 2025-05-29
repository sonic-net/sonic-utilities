import imp
import os
import sys
import mock
import jsonpatch

from click.testing import CliRunner
from utilities_common.db import Db
from mock import patch
from jsonpointer import JsonPointerException

import config.main as config
import config.aaa as aaa
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import mock_tables.dbconnector

show_radius_default_output="""\
RADIUS global auth_type pap (default)
RADIUS global retransmit 3 (default)
RADIUS global timeout 5 (default)
RADIUS global passkey <EMPTY_STRING> (default)

"""

show_radius_server_output="""\
RADIUS global auth_type pap (default)
RADIUS global retransmit 3 (default)
RADIUS global timeout 5 (default)
RADIUS global passkey <EMPTY_STRING> (default)

RADIUS_SERVER address 10.10.10.10
               auth_port 1812
               priority 1
               retransmit 1
               timeout 3
               passkey testing123
               src_intf eth0

"""

show_radius_global_output="""\
RADIUS global auth_type chap
RADIUS global retransmit 3 (default)
RADIUS global timeout 5 (default)
RADIUS global passkey <EMPTY_STRING> (default)

"""

show_radius_global_nasip_source_ip_output="""\
RADIUS global auth_type pap (default)
RADIUS global retransmit 3 (default)
RADIUS global timeout 5 (default)
RADIUS global passkey <EMPTY_STRING> (default)
RADIUS global nas_ip 1.1.1.1
RADIUS global src_ip 2000::1

"""

config_radius_empty_output="""\
"""

show_radius_global_timeout_output = """\
RADIUS global auth_type pap (default)
RADIUS global retransmit 3 (default)
RADIUS global timeout 60
RADIUS global passkey <EMPTY_STRING> (default)

"""

show_radius_global_retransmit_output = """\
RADIUS global auth_type pap (default)
RADIUS global retransmit 10
RADIUS global timeout 5 (default)
RADIUS global passkey <EMPTY_STRING> (default)

"""

config_radius_server_invalidkey_output="""\
--key: Valid chars are ASCII printable except SPACE, '#', and ','
"""

config_radius_invalidipaddress_output="""\
Invalid ip address
"""

class TestRadius(object):
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

    def test_show_radius_default(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_default_output

    def test_config_radius_server(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["radius"],\
                               ["add", "10.10.10.10", "-r", "1", "-t", "3",\
                                "-k", "testing123", "-s", "eth0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_server_output

        result = runner.invoke(config.config.commands["radius"],\
                               ["delete", "10.10.10.10"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_default_output

    def test_config_radius_server_invalidkey(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["radius"],\
                               ["add", "10.10.10.10", "-r", "1", "-t", "3",\
                                "-k", "comma,invalid", "-s", "eth0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_server_invalidkey_output

    def test_config_radius_nasip_invalid(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["radius"],\
                               ["nasip", "invalid"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_invalidipaddress_output

    def test_config_radius_sourceip_invalid(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["radius"],\
                               ["sourceip", "invalid"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_invalidipaddress_output

    def test_config_radius_authtype(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["radius"],\
                               ["authtype", "chap"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_global_output

        result = runner.invoke(config.config.commands["radius"],\
                               ["default", "authtype"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_default_output

    def test_config_radius_timeout(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["radius"],
                               ["timeout", "60"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_global_timeout_output

        result = runner.invoke(config.config.commands["radius"],
                               ["default", "timeout"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_default_output

    def test_config_radius_retransmit(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["radius"],
                               ["retransmit", "10"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_global_retransmit_output

        result = runner.invoke(config.config.commands["radius"],
                               ["default", "retransmit"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_radius_empty_output

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_default_output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_config_radius_server_invalidkey_yang_validation(self):
        aaa.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["radius"],\
                               ["add", "10.10.10.10", "-r", "1", "-t", "3",\
                                "-k", "comma,invalid", "-s", "eth0"], obj=db)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPointerException))
    def test_config_radius_server_invalid_delete_yang_validation(self):
        aaa.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["radius"],\
                               ["delete", "10.10.10.x"], obj=db)
        print(result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_config_radius_nasip_sourceip(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()
        
        result = runner.invoke(config.config.commands["radius"],\
                               ["nasip", "1.1.1.1"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["radius"],\
                               ["sourceip", "2000::1"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_global_nasip_source_ip_output

        # Test delete nasip/sourceip
        result = runner.invoke(config.config.commands["radius"],
                               ["default", "nasip"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["radius"],
                               ["default", "sourceip"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands["radius"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_radius_default_output
