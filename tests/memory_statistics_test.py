import unittest
from unittest.mock import patch
from click.testing import CliRunner
from config.memory_statistics import memory_statistics_enable
from config.memory_statistics import memory_statistics_disable
from config.memory_statistics import memory_statistics_retention_period
from config.memory_statistics import memory_statistics_sampling_interval
from show.memory_statistics import config, show_memory_statistics_logs


class TestMemoryStatisticsConfigCommands(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        # Mock Config DB connector to simulate the MEMORY_STATISTICS table
        self.config_db_mock = patch('config.memory_statistics.ConfigDBConnector')
        self.mock_db = self.config_db_mock.start()
        # Simulate MEMORY_STATISTICS table presence in Config DB
        self.mock_db.get_table.return_value = {
            "MEMORY_STATISTICS": {"status": "enabled", "retention_period": "30", "sampling_interval": "5"}
        }

    def tearDown(self):
        # Stop the Config DB mock
        self.config_db_mock.stop()

    def test_memory_statistics_enable(self):
        result = self.runner.invoke(memory_statistics_enable)
        self.assertIn("Memory Statistics feature enabled.", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_disable(self):
        result = self.runner.invoke(memory_statistics_disable)
        self.assertIn("Memory Statistics feature disabled.", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_retention_period(self):
        result = self.runner.invoke(memory_statistics_retention_period, ['30'])
        self.assertIn("Memory Statistics retention period set to 30 days.", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_memory_statistics_sampling_interval(self):
        result = self.runner.invoke(memory_statistics_sampling_interval, ['5'])
        self.assertIn("Memory Statistics sampling interval set to 5 minutes.", result.output)
        self.assertEqual(result.exit_code, 0)


class TestMemoryStatisticsShowCommands(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        # Mock Config DB connector to simulate MEMORY_STATISTICS table and logs
        self.config_db_mock = patch('show.memory_statistics.ConfigDBConnector')
        self.mock_db = self.config_db_mock.start()
        # Simulate logs and configuration
        self.mock_db.get_table.return_value = {
            "MEMORY_STATISTICS": {"status": "enabled", "retention_period": "30", "sampling_interval": "5"}
        }
        self.mock_db.get_log_entries.return_value = [
            {"date": "2023-10-01", "data": "Sample log entry 1"},
            {"date": "2023-10-02", "data": "Sample log entry 2"}
        ]

    def tearDown(self):
        # Stop the Config DB mock
        self.config_db_mock.stop()

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
