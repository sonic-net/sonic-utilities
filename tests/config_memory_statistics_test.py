# import subprocess
# import syslog
# from unittest.mock import Mock, patch

# import pytest
# from click.testing import CliRunner

# from config.memory_statistics import (
#     cli,
#     log_to_syslog,
#     MemoryStatisticsDB,
#     MEMORY_STATISTICS_KEY,
#     MEMORY_STATISTICS_TABLE,
#     RETENTION_PERIOD_MAX,
#     RETENTION_PERIOD_MIN,
#     SAMPLING_INTERVAL_MAX,
#     SAMPLING_INTERVAL_MIN,
#     update_memory_statistics_status,
# )


# @pytest.fixture
# def mock_db():
#     """Fixture to create a mock database connection."""
#     with patch('config.memory_statistics.ConfigDBConnector') as mock_db_class:
#         mock_db_instance = Mock()
#         mock_db_class.return_value = mock_db_instance
#         MemoryStatisticsDB._instance = None
#         MemoryStatisticsDB._db = None
#         yield mock_db_instance


# @pytest.fixture
# def cli_runner():
#     """Fixture to create a CLI runner."""
#     return CliRunner()


# class TestMemoryStatisticsDB:
#     """Tests for the MemoryStatisticsDB singleton class"""

#     def test_singleton_pattern(self, mock_db):
#         """Test that MemoryStatisticsDB implements singleton pattern correctly."""
#         MemoryStatisticsDB._instance = None
#         MemoryStatisticsDB._db = None

#         db1 = MemoryStatisticsDB()
#         db2 = MemoryStatisticsDB()
#         assert db1 is db2
#         assert MemoryStatisticsDB._instance is db1
#         mock_db.connect.assert_called_once()

#     def test_get_db_connection(self, mock_db):
#         """Test that get_db returns the same database connection."""
#         MemoryStatisticsDB._instance = None
#         MemoryStatisticsDB._db = None

#         db1 = MemoryStatisticsDB.get_db()
#         db2 = MemoryStatisticsDB.get_db()
#         assert db1 is db2
#         mock_db.connect.assert_called_once()


# class TestUpdateMemoryStatisticsStatus:
#     """Tests for update_memory_statistics_status function"""

#     def test_successful_enable(self, mock_db):
#         """Test successful status update to enable."""
#         success, error = update_memory_statistics_status("true")
#         assert success is True
#         assert error is None
#         mock_db.mod_entry.assert_called_once_with(
#             MEMORY_STATISTICS_TABLE,
#             MEMORY_STATISTICS_KEY,
#             {"enabled": "true"}
#         )

#     def test_successful_disable(self, mock_db):
#         """Test successful status update to disable."""
#         success, error = update_memory_statistics_status("false")
#         assert success is True
#         assert error is None
#         mock_db.mod_entry.assert_called_once_with(
#             MEMORY_STATISTICS_TABLE,
#             MEMORY_STATISTICS_KEY,
#             {"enabled": "false"}
#         )

#     def test_database_error(self, mock_db):
#         """Test handling of database errors."""
#         mock_db.mod_entry.side_effect = Exception("DB Error")
#         success, error = update_memory_statistics_status("true")
#         assert success is False
#         assert "Error updating memory statistics status" in error
#         assert "DB Error" in error


# class TestMemoryStatisticsEnable:
#     def test_enable_success(self, cli_runner, mock_db):
#         """Test successful enabling of memory statistics."""
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'enable'])
#         assert result.exit_code == 0
#         mock_db.mod_entry.assert_called_once_with(
#             MEMORY_STATISTICS_TABLE,
#             MEMORY_STATISTICS_KEY,
#             {"enabled": "true"}
#         )
#         assert "successfully" in result.output
#         assert "config save" in result.output

#     def test_enable_db_error(self, cli_runner, mock_db):
#         """Test handling of database error when enabling."""
#         mock_db.mod_entry.side_effect = Exception("DB Error")
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'enable'])
#         assert result.exit_code == 0
#         assert "Error" in result.output


# class TestMemoryStatisticsDisable:
#     def test_disable_success(self, cli_runner, mock_db):
#         """Test successful disabling of memory statistics."""
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'disable'])
#         assert result.exit_code == 0
#         mock_db.mod_entry.assert_called_once_with(
#             MEMORY_STATISTICS_TABLE,
#             MEMORY_STATISTICS_KEY,
#             {"enabled": "false"}
#         )
#         assert "successfully" in result.output
#         assert "config save" in result.output

#     def test_disable_db_error(self, cli_runner, mock_db):
#         """Test handling of database error when disabling."""
#         mock_db.mod_entry.side_effect = Exception("DB Error")
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'disable'])
#         assert result.exit_code == 0
#         assert "Error" in result.output


# class TestSamplingInterval:
#     @pytest.mark.parametrize("interval", [
#         SAMPLING_INTERVAL_MIN,
#         SAMPLING_INTERVAL_MAX,
#         (SAMPLING_INTERVAL_MIN + SAMPLING_INTERVAL_MAX) // 2
#     ])
#     def test_valid_sampling_intervals(self, interval, cli_runner, mock_db):
#         """Test setting valid sampling intervals."""
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', str(interval)])
#         assert result.exit_code == 0
#         mock_db.mod_entry.assert_called_once_with(
#             MEMORY_STATISTICS_TABLE,
#             MEMORY_STATISTICS_KEY,
#             {"sampling_interval": str(interval)}
#         )
#         assert f"set to {interval}" in result.output

#     @pytest.mark.parametrize("interval", [
#         SAMPLING_INTERVAL_MIN - 1,
#         SAMPLING_INTERVAL_MAX + 1,
#         0,
#         -1
#     ])
#     def test_invalid_sampling_intervals(self, interval, cli_runner, mock_db):
#         """Test handling of invalid sampling intervals."""
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', str(interval)])
#         assert "Error" in result.output
#         assert not mock_db.mod_entry.called

#     def test_sampling_interval_db_error(self, cli_runner, mock_db):
#         """Test database error case when setting sampling interval."""
#         mock_db.mod_entry.side_effect = Exception("DB Error")
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', '5'])
#         assert "Error" in result.output


# class TestRetentionPeriod:
#     @pytest.mark.parametrize("period", [
#         RETENTION_PERIOD_MIN,
#         RETENTION_PERIOD_MAX,
#         (RETENTION_PERIOD_MIN + RETENTION_PERIOD_MAX) // 2
#     ])
#     def test_valid_retention_periods(self, period, cli_runner, mock_db):
#         """Test setting valid retention periods."""
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', str(period)])
#         assert result.exit_code == 0
#         mock_db.mod_entry.assert_called_once_with(
#             MEMORY_STATISTICS_TABLE,
#             MEMORY_STATISTICS_KEY,
#             {"retention_period": str(period)}
#         )
#         assert f"set to {period}" in result.output

#     @pytest.mark.parametrize("period", [
#         RETENTION_PERIOD_MIN - 1,
#         RETENTION_PERIOD_MAX + 1,
#         0,
#         -1
#     ])
#     def test_invalid_retention_periods(self, period, cli_runner, mock_db):
#         """Test handling of invalid retention periods."""
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', str(period)])
#         assert "Error" in result.output
#         assert not mock_db.mod_entry.called

#     def test_db_error(self, cli_runner, mock_db):
#         """Test handling of database errors."""
#         mock_db.mod_entry.side_effect = Exception("DB Error")
#         result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', '15'])
#         assert "Error" in result.output


# class TestSyslogLogging:
#     @pytest.mark.parametrize("log_level,expected_level", [
#         ("INFO", syslog.LOG_INFO),
#         ("ERROR", syslog.LOG_ERR)
#     ])
#     def test_syslog_logging(self, log_level, expected_level):
#         """Test syslog logging functionality."""
#         with patch('syslog.syslog') as mock_syslog, \
#              patch('syslog.openlog') as mock_openlog:

#             log_to_syslog("Test message", expected_level)

#             mock_openlog.assert_called_once_with(
#                 "memory_statistics",
#                 syslog.LOG_PID | syslog.LOG_CONS,
#                 syslog.LOG_USER
#             )

#             mock_syslog.assert_called_once_with(expected_level, "Test message")

#     def test_syslog_logging_default_level(self):
#         """Test syslog logging with default log level."""
#         with patch('syslog.syslog') as mock_syslog, \
#              patch('syslog.openlog') as _:
#             log_to_syslog("Test message")
#             mock_syslog.assert_called_once_with(syslog.LOG_INFO, "Test message")


# def test_main_execution():
#     """Test the main execution block of the script."""
#     with patch('config.memory_statistics.cli') as mock_cli:
#         module_code = compile(
#             'if __name__ == "__main__": cli()',
#             'memory_statistics.py',
#             'exec'
#         )

#         namespace = {'__name__': '__main__', 'cli': mock_cli}
#         exec(module_code, namespace)

#         mock_cli.assert_called_once()


# def test_main_cli_integration():
#     """Test the main CLI integration with actual command."""
#     runner = CliRunner()

#     with patch('config.memory_statistics.MemoryStatisticsDB.get_db') as mock_get_db:
#         mock_db = Mock()
#         mock_get_db.return_value = mock_db

#         result = runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', '5'])
#         assert result.exit_code == 0
#         mock_get_db.assert_called_once()


# def test_script_execution():
#     """Test that the script runs successfully."""
#     result = subprocess.run(["python3",
#                              "config/memory_statistics.py"], capture_output=True)
#     assert result.returncode == 0


import subprocess
import syslog
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from config.memory_statistics import (
    cli,
    log_to_syslog,
    MemoryStatisticsDB,
    MEMORY_STATISTICS_KEY,
    MEMORY_STATISTICS_TABLE,
    RETENTION_PERIOD_MAX,
    RETENTION_PERIOD_MIN,
    SAMPLING_INTERVAL_MAX,
    SAMPLING_INTERVAL_MIN,
    update_memory_statistics_status,
)


@pytest.fixture
def mock_db():
    """Fixture to create a mock database connection."""
    with patch('config.memory_statistics.ConfigDBConnector') as mock_db_class:
        mock_db_instance = Mock()
        mock_db_class.return_value = mock_db_instance
        MemoryStatisticsDB._instance = None
        MemoryStatisticsDB._db = None
        yield mock_db_instance


@pytest.fixture
def cli_runner():
    """Fixture to create a CLI runner."""
    return CliRunner()


class TestMemoryStatisticsDB:
    """Tests for the MemoryStatisticsDB singleton class"""

    def test_singleton_pattern(self, mock_db):
        """Test that MemoryStatisticsDB implements singleton pattern correctly."""
        # Reset the singleton instance before test
        MemoryStatisticsDB._instance = None
        MemoryStatisticsDB._db = None

        db1 = MemoryStatisticsDB()
        db2 = MemoryStatisticsDB()
        assert db1 is db2
        assert MemoryStatisticsDB._instance is db1
        mock_db.connect.assert_called_once()

    def test_get_db_connection(self, mock_db):
        """Test that get_db returns the same database connection."""
        # Reset the singleton instance before test
        MemoryStatisticsDB._instance = None
        MemoryStatisticsDB._db = None
        
        db1 = MemoryStatisticsDB.get_db()
        db2 = MemoryStatisticsDB.get_db()
        
        assert db1 is db2
        # Check that ConfigDBConnector.connect() was called
        mock_db.connect.assert_called_once()

    def test_connect_db_failure(self, mock_db):
        """Test handling of database connection failure."""
        mock_db.connect.side_effect = RuntimeError("Connection failed")
        MemoryStatisticsDB._instance = None
        MemoryStatisticsDB._db = None

        with pytest.raises(RuntimeError, match="Database connection unavailable"):
            MemoryStatisticsDB.get_db()


class TestUpdateMemoryStatisticsStatus:
    """Tests for update_memory_statistics_status function"""

    def test_successful_enable(self, mock_db):
        """Test successful status update to enable."""
        success, error = update_memory_statistics_status(True)
        assert success is True
        assert error is None
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"enabled": "true"}
        )

    def test_successful_disable(self, mock_db):
        """Test successful status update to disable."""
        success, error = update_memory_statistics_status(False)
        assert success is True
        assert error is None
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"enabled": "false"}
        )

    def test_database_error(self, mock_db):
        """Test handling of database errors."""
        mock_db.mod_entry.side_effect = Exception("DB Error")
        success, error = update_memory_statistics_status(True)
        assert success is False
        assert "Unexpected error updating memory statistics status" in error
        assert "DB Error" in error

    def test_specific_exceptions(self, mock_db):
        """Test handling of specific exceptions."""
        for exception in [KeyError, ConnectionError, RuntimeError]:
            mock_db.mod_entry.side_effect = exception("Specific error")
            success, error = update_memory_statistics_status(True)
            assert success is False
            assert "Specific error" in error


class TestMemoryStatisticsEnable:
    def test_enable_success(self, cli_runner, mock_db):
        """Test successful enabling of memory statistics."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'enable'])
        assert result.exit_code == 0
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"enabled": "true"}
        )
        assert "successfully" in result.output
        assert "config save" in result.output

    def test_enable_db_error(self, cli_runner, mock_db):
        """Test handling of database error when enabling."""
        mock_db.mod_entry.side_effect = Exception("DB Error")
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'enable'])
        assert result.exit_code == 0
        assert "Error" in result.output


class TestMemoryStatisticsDisable:
    def test_disable_success(self, cli_runner, mock_db):
        """Test successful disabling of memory statistics."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'disable'])
        assert result.exit_code == 0
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"enabled": "false"}
        )
        assert "successfully" in result.output
        assert "config save" in result.output

    def test_disable_db_error(self, cli_runner, mock_db):
        """Test handling of database error when disabling."""
        mock_db.mod_entry.side_effect = Exception("DB Error")
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'disable'])
        assert result.exit_code == 0
        assert "Error" in result.output


class TestSamplingInterval:
    @pytest.mark.parametrize("interval", [
        SAMPLING_INTERVAL_MIN,
        SAMPLING_INTERVAL_MAX,
        (SAMPLING_INTERVAL_MIN + SAMPLING_INTERVAL_MAX) // 2
    ])
    def test_valid_sampling_intervals(self, interval, cli_runner, mock_db):
        """Test setting valid sampling intervals."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', str(interval)])
        assert result.exit_code == 0
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"sampling_interval": str(interval)}
        )
        assert f"set to {interval}" in result.output

    @pytest.mark.parametrize("interval", [
        SAMPLING_INTERVAL_MIN - 1,
        SAMPLING_INTERVAL_MAX + 1,
        0,
        -1,
        256  # Outside uint8 range
    ])
    def test_invalid_sampling_intervals(self, interval, cli_runner, mock_db):
        """Test handling of invalid sampling intervals."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', str(interval)])
        assert "Error" in result.output
        assert not mock_db.mod_entry.called

    def test_sampling_interval_db_error(self, cli_runner, mock_db):
        """Test database error case when setting sampling interval."""
        mock_db.mod_entry.side_effect = Exception("DB Error")
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', '5'])
        assert "Error" in result.output

    @pytest.mark.parametrize("exception", [
        KeyError("Key not found"),
        ConnectionError("Connection failed"),
        ValueError("Invalid value"),
        RuntimeError("Runtime error")
    ])
    def test_sampling_interval_specific_errors(self, exception, cli_runner, mock_db):
        """Test handling of specific errors when setting sampling interval."""
        mock_db.mod_entry.side_effect = exception
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', '5'])
        assert result.exit_code == 0
        assert "Error" in result.output
        assert str(exception) in result.output


class TestRetentionPeriod:
    @pytest.mark.parametrize("period", [
        RETENTION_PERIOD_MIN,
        RETENTION_PERIOD_MAX,
        (RETENTION_PERIOD_MIN + RETENTION_PERIOD_MAX) // 2
    ])
    def test_valid_retention_periods(self, period, cli_runner, mock_db):
        """Test setting valid retention periods."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', str(period)])
        assert result.exit_code == 0
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"retention_period": str(period)}
        )
        assert f"set to {period}" in result.output

    @pytest.mark.parametrize("period", [
        RETENTION_PERIOD_MIN - 1,
        RETENTION_PERIOD_MAX + 1,
        0,
        -1,
        256  # Outside uint8 range
    ])
    def test_invalid_retention_periods(self, period, cli_runner, mock_db):
        """Test handling of invalid retention periods."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', str(period)])
        assert "Error" in result.output
        assert not mock_db.mod_entry.called

    def test_db_error(self, cli_runner, mock_db):
        """Test handling of database errors."""
        mock_db.mod_entry.side_effect = Exception("DB Error")
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', '15'])
        assert "Error" in result.output

    @pytest.mark.parametrize("exception", [
        KeyError("Key not found"),
        ConnectionError("Connection failed"),
        ValueError("Invalid value"),
        RuntimeError("Runtime error")
    ])
    def test_retention_period_specific_errors(self, exception, cli_runner, mock_db):
        """Test handling of specific errors when setting retention period."""
        mock_db.mod_entry.side_effect = exception
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'retention-period', '15'])
        assert result.exit_code == 0
        assert "Error" in result.output
        assert str(exception) in result.output


class TestSyslogLogging:
    @pytest.mark.parametrize("log_level,expected_level", [
        ("INFO", syslog.LOG_INFO),
        ("ERROR", syslog.LOG_ERR)
    ])
    def test_syslog_logging(self, log_level, expected_level):
        """Test syslog logging functionality."""
        with patch('syslog.syslog') as mock_syslog:
            log_to_syslog("Test message", expected_level)
            mock_syslog.assert_called_once_with(expected_level, "Test message")

    def test_syslog_logging_default_level(self):
        """Test syslog logging with default log level."""
        with patch('syslog.syslog') as mock_syslog:
            log_to_syslog("Test message")
            mock_syslog.assert_called_once_with(syslog.LOG_INFO, "Test message")

    def test_syslog_logging_error(self):
        """Test syslog logging error handling."""
        with patch('syslog.syslog', side_effect=Exception("Syslog error")), \
             patch('click.echo') as mock_echo:
            log_to_syslog("Test message")
            mock_echo.assert_called_once_with("Failed to log to syslog: Syslog error", err=True)


def test_main_execution():
    """Test the main execution block of the script."""
    with patch('config.memory_statistics.cli') as mock_cli:
        module_code = compile(
            'if __name__ == "__main__": cli()',
            'memory_statistics.py',
            'exec'
        )

        namespace = {'__name__': '__main__', 'cli': mock_cli}
        exec(module_code, namespace)

        mock_cli.assert_called_once()

def test_main_cli_integration():
    """Test the main CLI integration with actual command."""
    runner = CliRunner()

    with patch('config.memory_statistics.MemoryStatisticsDB.get_db') as mock_get_db:
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        result = runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', '5'])
        assert result.exit_code == 0
        mock_get_db.assert_called_once()

def test_script_execution():
    """Test that the script runs successfully."""
    result = subprocess.run(["python3",
                             "config/memory_statistics.py"], capture_output=True)
    assert result.returncode == 0

# def test_syslog_closelog():
#     """Test that syslog.closelog is called when the script exits."""
#     with patch('syslog.closelog') as mock_closelog:
#         # Simulate running the script
#         module_code = compile(
#             'if __name__ == "__main__": cli()',
#             'memory_statistics.py',
#             'exec'
#         )
#         namespace = {'__name__': '__main__', 'cli': Mock()}
#         exec(module_code, namespace)
        
#         # Verify that syslog.closelog was called
#         mock_closelog.assert_called_once()

def test_syslog_closelog():
    """Test that syslog.closelog is called when the script exits."""
    with patch('syslog.closelog') as mock_closelog, \
         patch('config.memory_statistics.cli') as mock_cli:
        # Simulate running the script
        module_code = compile(
            'if __name__ == "__main__": cli()',
            'memory_statistics.py',
            'exec'
        )
        namespace = {'__name__': '__main__', 'cli': mock_cli}
        exec(module_code, namespace)
        
        # Verify that syslog.closelog was called
        mock_closelog.assert_called_once()