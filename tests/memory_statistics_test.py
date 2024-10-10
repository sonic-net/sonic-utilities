from click.testing import CliRunner
from utilities_common.db import Db


class TestMemoryStatistics(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_config_memory_statistics_enable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["memory-statistics"].commands["enable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'MEMORY_STATISTICS' table.
        db.cfgdb.delete_table("MEMORY_STATISTICS")

        result = runner.invoke(config.config.commands["memory-statistics"].commands["enable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    def test_config_memory_statistics_disable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["memory-statistics"].commands["disable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'MEMORY_STATISTICS' table.
        db.cfgdb.delete_table("MEMORY_STATISTICS")

        result = runner.invoke(config.config.commands["memory-statistics"].commands["disable"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    def test_config_memory_statistics_retention_period(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["memory-statistics"].commands["retention-period"], ["30"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'MEMORY_STATISTICS' table.
        db.cfgdb.delete_table("MEMORY_STATISTICS")

        result = runner.invoke(config.config.commands["memory-statistics"].commands["retention-period"], ["30"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    def test_config_memory_statistics_sampling_interval(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["memory-statistics"].commands["sampling-interval"], ["5"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

        # Delete the 'MEMORY_STATISTICS' table.
        db.cfgdb.delete_table("MEMORY_STATISTICS")

        result = runner.invoke(config.config.commands["memory-statistics"].commands["sampling-interval"], ["5"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 1

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
