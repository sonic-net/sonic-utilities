import os
import sys
import config.bmc as bmc

from unittest import mock
from click.testing import CliRunner
from mock import MagicMock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)


class TestBmcResetControl(object):
    """Tests for the direct switch-host BMC reset command."""

    @staticmethod
    def _platform_with_bmc(bmc_device):
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value.get_bmc.return_value = bmc_device
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        return mock_sonic_platform

    def test_reset(self):
        runner = CliRunner()
        bmc_device = MagicMock()
        bmc_device.reset.return_value = True
        with mock.patch.dict('sys.modules', {
                'sonic_platform': self._platform_with_bmc(bmc_device)}):
            result = runner.invoke(bmc.bmc, ['reset'])
        assert result.exit_code == 0
        assert 'BMC reset completed' in result.output
        bmc_device.reset.assert_called_once_with()

    def test_reset_control_is_unsupported_without_bmc(self):
        runner = CliRunner()
        with mock.patch.dict('sys.modules', {
                'sonic_platform': self._platform_with_bmc(None)}):
            result = runner.invoke(bmc.bmc, ['reset'])
        assert result.exit_code != 0
        assert 'not supported' in result.output

    def test_reset_control_is_unsupported_when_not_implemented(self):
        runner = CliRunner()
        bmc_device = MagicMock()
        bmc_device.reset.side_effect = NotImplementedError
        with mock.patch.dict('sys.modules', {
                'sonic_platform': self._platform_with_bmc(bmc_device)}):
            result = runner.invoke(bmc.bmc, ['reset'])
        assert result.exit_code == 1
        assert 'BMC reset control is not supported on this platform' in result.output
        assert 'BMC reset failed' not in result.output
        assert 'BMC reset completed' not in result.output
        bmc_device.reset.assert_called_once_with()

    def test_reset_control_fails_when_platform_rejects_request(self):
        runner = CliRunner()
        bmc_device = MagicMock()
        bmc_device.reset.return_value = False
        with mock.patch.dict('sys.modules', {
                'sonic_platform': self._platform_with_bmc(bmc_device)}):
            result = runner.invoke(bmc.bmc, ['reset'])
        assert result.exit_code != 0
        assert 'BMC reset failed' in result.output
        assert 'BMC reset completed' not in result.output
        bmc_device.reset.assert_called_once_with()

    def test_reset_reports_hardware_exception(self):
        runner = CliRunner()
        bmc_device = MagicMock()
        bmc_device.reset.side_effect = RuntimeError('hardware failure')
        with mock.patch.dict('sys.modules', {
                'sonic_platform': self._platform_with_bmc(bmc_device)}):
            result = runner.invoke(bmc.bmc, ['reset'])
        assert result.exit_code != 0
        assert 'BMC reset failed: hardware failure' in result.output
        assert 'BMC reset completed' not in result.output
        bmc_device.reset.assert_called_once_with()

class TestBmcResetRootPassword(object):
    """Test class for 'config bmc reset-root-password' command"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_reset_root_password_success(self):
        """Test successful root password reset"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.reset_root_password.return_value = (0, "Password reset successful")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.reset_root_password, [])
            assert result.exit_code == 0
            assert "BMC root password reset successful" in result.output
            mock_bmc.reset_root_password.assert_called_once()

    def test_reset_root_password_failure(self):
        """Test failed root password reset"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.reset_root_password.return_value = (1, "Password reset failed")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.reset_root_password, [])
            assert result.exit_code == 0
            assert "BMC root password reset failed: Password reset failed" in result.output
            mock_bmc.reset_root_password.assert_called_once()

    def test_reset_root_password_bmc_not_available(self):
        """Test when BMC is not available"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = None
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.reset_root_password, [])
            assert result.exit_code == 0
            assert "BMC is not available on this platform" in result.output

    def test_reset_root_password_exception(self):
        """Test when an exception occurs"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.side_effect = Exception("Test exception")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.reset_root_password, [])
            assert result.exit_code == 0
            assert "Error: Test exception" in result.output


class TestBmcOpenSession(object):
    """Test class for 'config bmc open-session' command"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_open_session_success(self):
        """Test successful session opening"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.open_session.return_value = (0, ("Login successful", ("session_123", "token_abc")))
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.open_session, [])
            assert result.exit_code == 0
            assert "Session ID: session_123" in result.output
            assert "Token: token_abc" in result.output
            mock_bmc.open_session.assert_called_once()

    def test_open_session_failure_no_credentials(self):
        """Test failed session opening with no credentials"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.open_session.return_value = (1, ("Login failed", None))
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.open_session, [])
            assert result.exit_code == 0
            assert "Failed to open session: Login failed" in result.output
            mock_bmc.open_session.assert_called_once()

    def test_open_session_failure_empty_credentials(self):
        """Test failed session opening with empty credentials"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.open_session.return_value = (0, ("Login successful", ()))
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.open_session, [])
            assert result.exit_code == 0
            assert "Failed to open session: Login successful" in result.output
            mock_bmc.open_session.assert_called_once()

    def test_open_session_bmc_not_available(self):
        """Test when BMC is not available"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = None
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.open_session, [])
            assert result.exit_code == 0
            assert "BMC is not available on this platform" in result.output

    def test_open_session_exception(self):
        """Test when an exception occurs"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.side_effect = Exception("Test exception")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.open_session, [])
            assert result.exit_code == 0
            assert "Error: Test exception" in result.output


class TestBmcCloseSession(object):
    """Test class for 'config bmc close-session' command"""

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_close_session_success(self):
        """Test successful session closing"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.close_session.return_value = (0, "Session closed successfully")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.close_session, ['--session-id', 'session_123'])
            assert result.exit_code == 0
            assert "Session closed successfully" in result.output
            mock_bmc.close_session.assert_called_once_with('session_123')

    def test_close_session_failure(self):
        """Test failed session closing"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_bmc = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = mock_bmc
        mock_bmc.close_session.return_value = (1, "Session not found")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.close_session, ['--session-id', 'invalid_session'])
            assert result.exit_code == 0
            assert "Failed to close session: Session not found" in result.output
            mock_bmc.close_session.assert_called_once_with('invalid_session')

    def test_close_session_bmc_not_available(self):
        """Test when BMC is not available"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.return_value = None
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.close_session, ['--session-id', 'session_123'])
            assert result.exit_code == 0
            assert "BMC is not available on this platform" in result.output

    def test_close_session_exception(self):
        """Test when an exception occurs"""
        runner = CliRunner()
        mock_sonic_platform = MagicMock()
        mock_platform = MagicMock()
        mock_chassis = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_chassis.get_bmc.side_effect = Exception("Test exception")
        mock_sonic_platform.platform.Platform.return_value = mock_platform
        with mock.patch.dict('sys.modules', {
            'sonic_platform': mock_sonic_platform,
            'sonic_platform.platform': mock_sonic_platform.platform
        }):
            result = runner.invoke(bmc.close_session, ['--session-id', 'session_123'])
            assert result.exit_code == 0
            assert "Error: Test exception" in result.output

    def test_close_session_missing_session_id(self):
        """Test when session-id parameter is missing"""
        runner = CliRunner()
        result = runner.invoke(bmc.close_session, [])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output
