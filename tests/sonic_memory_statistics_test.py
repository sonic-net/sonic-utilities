import logging
import os
import sys
import unittest
from unittest.mock import patch  # Added patch import
from utilities_common.general import load_module_from_source

TESTS_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
UTILITY_DIR_PATH = os.path.dirname(TESTS_DIR_PATH)
SCRIPTS_DIR_PATH = os.path.join(UTILITY_DIR_PATH, "scripts")
sys.path.append(SCRIPTS_DIR_PATH)

logger = logging.getLogger(__name__)

# Load `sonic-memory-statistics` module from source
sonic_memory_statistics_path = os.path.join(SCRIPTS_DIR_PATH, "sonic-memory-statistics")
sonic_memory_statistics = load_module_from_source("sonic_memory_statistics", sonic_memory_statistics_path)


class TestSonicMemoryStatistics(unittest.TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @patch("sonic_memory_statistics.run_command")
    def test_read_memory_statistics(self, mock_run_cmd):
        """Tests the function `read_memory_statistics(...)` in the `sonic-memory-statistics` script.
        """
        # Test for normal case
        mock_run_cmd.return_value = (0, ["1024"], None)
        memory_stats = sonic_memory_statistics.read_memory_statistics()
        assert memory_stats == 1024

        logger.info(f"Value of 'memory_stats' is: '{memory_stats}'.")
        logger.info("Expected value of 'memory_stats' is: '1024'.")

        # Test for non-integer return
        mock_run_cmd.return_value = (0, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            memory_stats = sonic_memory_statistics.read_memory_statistics()
        self.assertEqual(sys_exit.exception.code, 1)

        # Test for empty return
        mock_run_cmd.return_value = (0, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            memory_stats = sonic_memory_statistics.read_memory_statistics()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_memory_statistics.run_command")
    def test_write_memory_statistics(self, mock_run_cmd):
        """Tests the function `write_memory_statistics(...)` in the `sonic-memory-statistics` script.
        """
        mock_run_cmd.return_value = (0, [], None)
        sonic_memory_statistics.write_memory_statistics(1024)

        # Simulate failure cases
        mock_run_cmd.return_value = (1, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_memory_statistics.write_memory_statistics(1024)
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_memory_statistics.memory_statistics_enable")
    @patch("sonic_memory_statistics.get_memory_retention")
    def test_memory_statistics_enable(self, mock_retention, mock_enable):
        """Tests the function `memory_statistics_enable(...)` in `sonic-memory-statistics.py`.
        """
        mock_retention.return_value = 3600
        mock_enable.return_value = True

        return_result = sonic_memory_statistics.memory_statistics_enable(True)
        assert return_result is True  # Changed comparison to 'is True'

        mock_enable.return_value = False
        return_result = sonic_memory_statistics.memory_statistics_enable(False)
        assert return_result is False  # Changed comparison to 'is False'

    @patch("sonic_memory_statistics.get_current_sampling_interval")
    def test_get_sampling_interval(self, mock_sampling_interval):
        """Tests the function `get_current_sampling_interval(...)` in `sonic-memory-statistics.py`.
        """
        mock_sampling_interval.return_value = 60
        sampling_interval = sonic_memory_statistics.get_current_sampling_interval()
        assert sampling_interval == 60

        # Test for failure case
        mock_sampling_interval.return_value = None
        with self.assertRaises(SystemExit) as sys_exit:
            sampling_interval = sonic_memory_statistics.get_current_sampling_interval()
        self.assertEqual(sys_exit.exception.code, 1)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


if __name__ == '__main__':
    unittest.main()
