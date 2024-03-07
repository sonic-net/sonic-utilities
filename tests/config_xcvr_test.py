from unittest.mock import patch
import click
import config.main as config
import operator
import os
import pytest
import sys

from click.testing import CliRunner
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)


@pytest.fixture(scope='module')
def ctx(scope='module'):
    db = Db()
    obj = {'config_db':db.cfgdb, 'namespace': ''}
    yield obj


class TestConfigXcvr(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_config_laser_frequency(self, ctx):
        #self.basic_check("link-training", ["Ethernet0", "on"], ctx)
        result = self.basic_check("frequency", ["Ethernet0", "191300"], ctx)
        assert "Setting laser frequency" in result.output
        result = self.basic_check("frequency", ["Ethernet0", "--", "-1"], ctx, op=operator.ne)
        assert "Error: Frequency must be > 0" in result.output
        # Setting laser frequency on a port channel is not supported
        result = self.basic_check("frequency", ["PortChannel0001", "191300"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output
    
    def test_config_tx_power(self, ctx):
        result = self.basic_check("tx_power", ["Ethernet0", "11.3"], ctx)
        assert "Setting target Tx output power" in result.output
        result = self.basic_check("tx_power", ["Ethernet0", "11.34"], ctx, op=operator.ne)
        assert "Error: tx power must be with single decimal place" in result.output
        # Setting tx power on a port channel is not supported
        result = self.basic_check("tx_power", ["PortChannel0001", "11.3"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    @patch("config.main.ConfigDBConnector.get_entry")
    def test_dom(self, mock_get_entry, ctx):
        interface_name = 'Ethernet0'
        desired_config = 'enable'

        result = self.basic_check("dom", ["", desired_config], ctx, operator.ne)
        assert "Interface name is invalid. Please enter a valid interface name!!" in result.output

        mock_get_entry.return_value = None
        result = self.basic_check("dom", [interface_name, desired_config], ctx, operator.ne)
        assert "Interface {} does not exist".format(interface_name) in result.output

        mock_get_entry.return_value = {'subport': '2'}
        result = self.basic_check("dom", [interface_name, desired_config], ctx, operator.ne)
        assert "DOM monitoring config only supported for subports {}".format(config.DOM_CONFIG_SUPPORTED_SUBPORTS) in result.output

        mock_get_entry.return_value = {'subport': '1'}
        result = self.basic_check("dom", [interface_name, desired_config], ctx)

    def basic_check(self, command_name, para_list, ctx, op=operator.eq, expect_result=0):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["transceiver"].commands[command_name], para_list, obj = ctx)
        print(result.output)
        assert op(result.exit_code, expect_result)
        return result
