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


class TestConfigInterface(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_config_link_training(self, ctx):
        self.basic_check("link-training", ["Ethernet0", "on"], ctx)
        self.basic_check("link-training", ["Ethernet0", "off"], ctx)
        self.basic_check("link-training", ["Invalid", "on"], ctx, operator.ne)
        self.basic_check("link-training", ["Invalid", "off"], ctx, operator.ne)
        self.basic_check("link-training", ["Ethernet0", "invalid"], ctx, operator.ne)
        # Setting link training on a port channel is not supported
        result = self.basic_check("link-training", ["PortChannel0001", "on"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def basic_check(self, command_name, para_list, ctx, op=operator.eq, expect_result=0):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands[command_name], para_list, obj = ctx)
        print(result.output)
        assert op(result.exit_code, expect_result)
        return result
