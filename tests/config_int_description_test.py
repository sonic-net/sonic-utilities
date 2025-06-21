import config.main as config
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
    obj = {'config_db': db.cfgdb, 'namespace': ''}
    yield obj


class TestConfigInterfaceDescription(object):
    def test_interface_description(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["interface"].commands["description"],
                               ["Ethernet0", "To_server_0"], obj=db)
        assert result.exit_code != 0

    def test_interface_description_invalid_interface_name(self, ctx):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["description"],
                               ["", "test"], obj=ctx)
        assert "Interface name is invalid" in result.output

    def test_interface_description_valid_config(self, ctx):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["description"],
                               ["Ethernet0", "test"], obj=ctx)
        assert result.exit_code == 0
