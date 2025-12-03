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

    def test_config_autoneg(self, ctx):
        self.basic_check("autoneg", ["Ethernet0", "enabled"], ctx)
        self.basic_check("autoneg", ["Ethernet0", "disabled"], ctx)
        self.basic_check("autoneg", ["Invalid", "enabled"], ctx, operator.ne)
        self.basic_check("autoneg", ["Ethernet0", "invalid"], ctx, operator.ne)
        # Setting auto negotiation on a port channel is not supported
        result = self.basic_check("autoneg", ["PortChannel0001", "enabled"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def test_config_speed(self, ctx):
        self.basic_check("speed", ["Ethernet0", "40000"], ctx)
        self.basic_check("speed", ["Invalid", "40000"], ctx, operator.ne)
        # 50000 is not a supported speed
        result = self.basic_check("speed", ["Ethernet0", "50000"], ctx, operator.ne)
        assert 'Invalid speed' in result.output
        assert 'Valid speeds:' in result.output
        self.basic_check("speed", ["Ethernet0", "invalid"], ctx, operator.ne)
        # Setting speed on a port channel is not supported
        result = self.basic_check("speed", ["PortChannel0001", "100000"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def test_config_adv_speeds(self, ctx):
        self.basic_check("advertised-speeds", ["Ethernet0", "40000,100000"], ctx)
        self.basic_check("advertised-speeds", ["Ethernet0", "all"], ctx)
        self.basic_check("advertised-speeds", ["Invalid", "40000,100000"], ctx, operator.ne)
        result = self.basic_check("advertised-speeds", ["Ethernet0", "50000,100000"], ctx, operator.ne)
        assert 'Invalid speed' in result.output
        assert 'Valid speeds:' in result.output
        result = self.basic_check("advertised-speeds", ["Ethernet0", "50000,50000"], ctx, operator.ne)
        assert 'Invalid speed' in result.output
        assert 'duplicate' in result.output
        # Setting advertised speeds on a port channel is not supported
        result = self.basic_check("advertised-speeds", ["PortChannel0001", "40000,100000"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def test_config_type(self, ctx):
        self.basic_check("type", ["Ethernet0", "CR4"], ctx)
        self.basic_check("type", ["Ethernet0", "none"], ctx)
        self.basic_check("type", ["Invalid", "CR4"], ctx, operator.ne)
        self.basic_check("type", ["Ethernet0", ""], ctx, operator.ne)
        result = self.basic_check("type", ["Ethernet0", "Invalid"], ctx, operator.ne)
        assert 'Invalid interface type specified' in result.output
        assert 'Valid interface types:' in result.output
        result = self.basic_check("type", ["Ethernet16", "Invalid"], ctx, operator.ne)
        assert "Setting RJ45 ports' type is not supported" in result.output
        # Setting type on a port channel is not supported
        result = self.basic_check("type", ["PortChannel0001", "CR4"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def test_config_adv_types(self, ctx):
        self.basic_check("advertised-types", ["Ethernet0", "CR4,KR4"], ctx)
        self.basic_check("advertised-types", ["Ethernet0", "all"], ctx)
        self.basic_check("advertised-types", ["Invalid", "CR4,KR4"], ctx, operator.ne)
        result = self.basic_check("advertised-types", ["Ethernet0", "CR4,Invalid"], ctx, operator.ne)
        assert 'Invalid interface type specified' in result.output
        assert 'Valid interface types:' in result.output
        result = self.basic_check("advertised-types", ["Ethernet0", "CR4,CR4"], ctx, operator.ne)
        assert 'Invalid interface type specified' in result.output
        assert 'duplicate' in result.output
        self.basic_check("advertised-types", ["Ethernet0", ""], ctx, operator.ne)
        result = self.basic_check("advertised-types", ["Ethernet16", "Invalid"], ctx, operator.ne)
        assert "Setting RJ45 ports' advertised types is not supported" in result.output
        # Setting advertised types on a port channel is not supported
        result = self.basic_check("advertised-types", ["PortChannel0001", "CR4,KR4"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def test_config_mtu(self, ctx):
        self.basic_check("mtu", ["Ethernet0", "1514"], ctx)
        result = self.basic_check("mtu", ["PortChannel0001", "1514"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output

    def test_config_fec(self, ctx):
        # Set a fec mode which is in supported_fec list but not default
        # on an interface with supported_fec
        self.basic_check("fec", ["Ethernet0", "test"], ctx)
        # Set a fec mode which is one of default values on an interface without supported_fecs
        self.basic_check("fec", ["Ethernet4", "rs"], ctx)
        # Negative case: Set a fec mode which is default but not in port's supported_fecs
        result = self.basic_check("fec", ["Ethernet0", "fc"], ctx, operator.ne)
        assert "fec fc is not in ['rs', 'none', 'test']" in result.output
        # Negative case: set a fec mode which is not default on an interface without supported_fecs
        result = self.basic_check("fec", ["Ethernet4", "test"], ctx, operator.ne)
        assert "fec test is not in ['rs', 'fc', 'none', 'auto']" in result.output
        # Negative case: set a fec mode on a port where setting fec is not supported
        result = self.basic_check("fec", ["Ethernet112", "test"], ctx, operator.ne)
        assert "Setting fec is not supported" in result.output
        # Negative case: set a fec mode on a port channel is not supported
        result = self.basic_check("fec", ["PortChannel0001", "none"], ctx, operator.ne)
        assert 'Invalid port PortChannel0001' in result.output        

    def basic_check(self, command_name, para_list, ctx, op=operator.eq, expect_result=0):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands[command_name], para_list, obj = ctx)
        print(result.output)
        assert op(result.exit_code, expect_result)
        return result
