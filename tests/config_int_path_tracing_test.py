import os
import config.main as config
from click.testing import CliRunner
from utilities_common.db import Db


class TestConfigInterfacePathTracing(object):
    def test_interface_path_tracing_check(self):
        runner = CliRunner()
        db = Db()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["add"],
                               ["Ethernet0", "--interface-id", "129"], obj=obj)
        assert result.exit_code == 0

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["add"],
                               ["Ethernet0", "--interface-id", "129", "--ts-template", "template2"], obj=obj)
        assert result.exit_code == 0

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["del"],
                               ["Ethernet0"], obj=obj)
        assert result.exit_code == 0

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["add"],
                               ["Ethernet0", "--interface-id", "129"], obj=obj)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["add"],
                               ["Ethernet0", "--interface-id", "129", "--ts-template", "template2"], obj=obj)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["del"],
                               ["Ethernet0"], obj=obj)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0

    def test_interface_invalid_path_tracing_check(self):
        runner = CliRunner()
        db = Db()

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["add"],
                               ["Ethernet0", "--interface-id", "4096"], obj=obj)
        assert "Error: Invalid value" in result.output

        obj = {'config_db': db.cfgdb, 'namespace': ''}
        result = runner.invoke(config.config.commands["interface"].commands["path-tracing"].commands["add"],
                               ["Ethernet0", "--interface-id", "129", "--ts-template", "template5"], obj=obj)
        assert "Error: Invalid value" in result.output
