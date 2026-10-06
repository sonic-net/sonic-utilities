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


class TestDampingConfig(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_damping_algorithm(self, ctx):
        self.basic_check("algo", ["Ethernet0", "aied"], ctx)
        self.basic_check("algo", ["Ethernet0", "disabled"], ctx)

    def test_invalid_damping_algorithm(self, ctx):
        self.basic_check("algo", ["Ethernet0", "invalid"], ctx, operator.ne)
        result = self.basic_check("algo", ["Invalid", "aied"], ctx, op=operator.ne)
        assert "Error: Invalid port" in result.output

    def test_invalid_aied_config(self, ctx):
        result = self.basic_check("aied-param", ["Invalid"], ctx, op=operator.ne)
        assert "Error: Invalid port" in result.output
        result = self.basic_check("aied-param", ["Ethernet0"], ctx, op=operator.ne)
        assert "Error: Expected at least one valid AIED config parameter" in result.output
        result = self.basic_check("aied-param", ["Ethernet0", "--suppress-threshold", "10", "--max-suppress-time", "10", "--decay-half-life", "-1"], ctx, op=operator.ne)
        assert "Error: Invalid decay_half_life value -1. It should be >= 0" in result.output

    def test_max_suppress_time_config(self, ctx):
        result = self.basic_check("aied-param", ["Ethernet0", "--max-suppress-time", "-1"], ctx, op=operator.ne)
        assert "Error: Invalid max_suppress_time value" in result.output
        self.basic_check("aied-param", ["Ethernet0", "--max-suppress-time", "50"], ctx)

    def test_decay_half_life_config(self, ctx):
        result = self.basic_check("aied-param", ["Ethernet0", "--decay-half-life", "-1"], ctx, op=operator.ne)
        assert "Error: Invalid decay_half_life value" in result.output
        self.basic_check("aied-param", ["Ethernet0", "--decay-half-life", "50"], ctx)

    def test_suppress_threshold_config(self, ctx):
        result = self.basic_check("aied-param", ["Ethernet0", "--suppress-threshold", "-1"], ctx, op=operator.ne)
        assert "Error: Invalid suppress_threshold value" in result.output
        self.basic_check("aied-param", ["Ethernet0", "--suppress-threshold", "50"], ctx)

    def test_reuse_threshold_config(self, ctx):
        result = self.basic_check("aied-param", ["Ethernet0", "--reuse-threshold", "-1"], ctx, op=operator.ne)
        assert "Error: Invalid reuse_threshold value" in result.output
        self.basic_check("aied-param", ["Ethernet0", "--reuse-threshold", "50"], ctx)

    def test_flap_penalty_config(self, ctx):
        result = self.basic_check("aied-param", ["Ethernet0", "--flap-penalty", "-1"], ctx, op=operator.ne)
        assert "Error: Invalid flap_penalty value" in result.output
        self.basic_check("aied-param", ["Ethernet0", "--flap-penalty", "50"], ctx)

    def test_all_config(self, ctx):
        self.basic_check("aied-param", ["Ethernet0", "--decay-half-life", "1001", "--suppress-threshold", "190", "--max-suppress-time", "500",  "--flap-penalty", "1000", "--reuse-threshold", "170"], ctx)

    def basic_check(self, command_name, para_list, ctx, op=operator.eq, expect_result=0):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["damping"].commands[command_name], para_list, obj = ctx)
        print(result.exit_code, result.output)
        assert op(result.exit_code, expect_result)
        return result

