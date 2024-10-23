import unittest
from click.testing import CliRunner
from config.memory_statistics import (
    memory_statistics_enable,
    memory_statistics_disable,
    memory_statistics_retention_period,
    memory_statistics_sampling_interval
)
from show.memory_statistics import config, show_memory_statistics_logs
from swsscommon.swsscommon import ConfigDBConnector


class TestMemoryStatisticsConfigCommands(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.db = ConfigDBConnector()
        self.db.connect()
        # Ensure a clean state in the MEMORY_STATISTICS table before each test
        self.db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {
            "enabled": "false",
            "retention_period": "15",  # Default retention period
            "sampling_interval": "5"    # Default sampling interval
        })

    def tearDown(self):
        # Clean up after each test to avoid side effects
        self.db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {
            "enabled": "false",
            "retention_period": "15",
            "sampling_interval": "5"
        })

    def test_memory_statistics_enable(self):
        result = self.runner.invoke(memory_statistics_enable)
        self.assertIn("Memory Statistics feature enabled.", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_disable(self):
        result = self.runner.invoke(memory_statistics_disable)
        self.assertIn("Memory Statistics feature disabled.", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_retention_period(self):
        result = self.runner.invoke(memory_statistics_retention_period, ['15'])  # Test with default
        self.assertIn("Memory Statistics retention period set to 15 days.", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_sampling_interval(self):
        result = self.runner.invoke(memory_statistics_sampling_interval, ['5'])  # Test with default
        self.assertIn("Memory Statistics sampling interval set to 5 minutes.", result.output)
        self.assertEqual(result.exit_code, 0)


class TestMemoryStatisticsShowCommands(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.db = ConfigDBConnector()
        self.db.connect()
        # Ensure a clean state in the MEMORY_STATISTICS table before each test
        self.db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {
            "enabled": "true",
            "retention_period": "15",  # Default retention period
            "sampling_interval": "5"    # Default sampling interval
        })

    def tearDown(self):
        # Clean up after each test to avoid side effects
        self.db.mod_entry("MEMORY_STATISTICS", "memory_statistics", {
            "enabled": "true",
            "retention_period": "15",
            "sampling_interval": "5"
        })

    def test_memory_statistics_config(self):
        result = self.runner.invoke(config)
        self.assertIn("Memory Statistics administrative mode:", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_logs(self):
        result = self.runner.invoke(show_memory_statistics_logs, ['2023-10-01', '2023-10-02'])
        self.assertIn("Memory Statistics logs", result.output)
        self.assertEqual(result.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
