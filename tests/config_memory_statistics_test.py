import pytest
import syslog
from unittest.mock import Mock, patch
from click.testing import CliRunner
from config.memory_statistics import (
    cli, update_memory_statistics_status, MEMORY_STATISTICS_TABLE,
    MEMORY_STATISTICS_KEY, SAMPLING_INTERVAL_MIN, SAMPLING_INTERVAL_MAX,
    RETENTION_PERIOD_MIN, RETENTION_PERIOD_MAX, log_to_syslog
)


@pytest.fixture
def mock_db():
    """Fixture to create a mock database connection."""
    with patch('config.memory_statistics.ConfigDBConnector') as mock_db_class:
        mock_db_instance = Mock()
        mock_db_class.return_value = mock_db_instance
        yield mock_db_instance


@pytest.fixture
def cli_runner():
    """Fixture to create a CLI runner."""
    return CliRunner()


class TestUpdateMemoryStatisticsStatus:
    """Direct tests for update_memory_statistics_status function"""

    def test_successful_enable(self, mock_db):
        """Test successful status update to enable."""
        success, error = update_memory_statistics_status("true", mock_db)
        assert success is True
        assert error is None
        mock_db.mod_entry.assert_called_once_with(
            MEMORY_STATISTICS_TABLE,
            MEMORY_STATISTICS_KEY,
            {"enabled": "true"}
        )

    def test_successful_disable(self, mock_db):
        """Test successful status update to disable."""
        success, error = update_memory_statistics_status("false", mock_db)
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
        success, error = update_memory_statistics_status("true", mock_db)
        assert success is False
        assert "Error updating memory statistics status" in error
        assert "DB Error" in error


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
        -1
    ])
    def test_invalid_sampling_intervals(self, interval, cli_runner, mock_db):
        """Test handling of invalid sampling intervals."""
        result = cli_runner.invoke(cli, ['config', 'memory-stats', 'sampling-interval', str(interval)])
        assert "Error" in result.output
        assert not mock_db.mod_entry.called


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
        -1
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


class TestSyslogLogging:
    @pytest.mark.parametrize("log_level,expected_level", [
        ("INFO", syslog.LOG_INFO),
        ("ERROR", syslog.LOG_ERR)
    ])
    def test_syslog_logging(self, log_level, expected_level):
        """Test syslog logging functionality."""
        with patch('syslog.syslog') as mock_syslog, \
             patch('syslog.openlog') as mock_openlog:

            log_to_syslog("Test message", expected_level)

            mock_openlog.assert_called_once_with(
                "memory_statistics",
                syslog.LOG_PID | syslog.LOG_CONS,
                syslog.LOG_USER
            )

            mock_syslog.assert_called_once_with(expected_level, "Test message")

    def test_syslog_logging_default_level(self):
        """Test syslog logging with default log level."""
        with patch('syslog.syslog') as mock_syslog, \
            patch('syslog.openlog') as _:
            log_to_syslog("Test message")
            mock_syslog.assert_called_once_with(syslog.LOG_INFO, "Test message")
