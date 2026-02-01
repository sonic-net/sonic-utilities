from click.testing import CliRunner
from mock import patch, MagicMock
import config.main as config


class TestSed(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @patch('sonic_platform.platform.Platform')
    def test_change_password_success(self, mock_platform):
        """Test successful password change"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.change_sed_password.return_value = True
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            ["-p", "validpassword"]
        )
        assert "Handling SED password change started..." in result.output
        assert "SED password change process completed successfully" in result.output
        mock_chassis.change_sed_password.assert_called_once_with("validpassword")

    @patch('sonic_platform.platform.Platform')
    def test_change_password_failure(self, mock_platform):
        """Test failed password change"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.change_sed_password.return_value = False
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            ["-p", "validpassword"]
        )
        assert "Handling SED password change started..." in result.output
        assert "Error: SED password change failed" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_change_password_not_implemented(self, mock_platform):
        """Test NotImplementedError handling"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.change_sed_password.side_effect = NotImplementedError
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            ["-p", "validpassword"]
        )
        assert "Error: SED management not implemented on this platform" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_change_password_exception(self, mock_platform):
        """Test general exception handling"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.change_sed_password.side_effect = Exception("Test error")
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            ["-p", "validpassword"]
        )
        assert "Error changing SED password: Test error" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_success(self, mock_platform):
        """Test successful password reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.reset_sed_password.return_value = True
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Handling SED password reset started..." in result.output
        assert "SED password reset process completed successfully" in result.output
        mock_chassis.reset_sed_password.assert_called_once()

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_failure(self, mock_platform):
        """Test failed password reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.reset_sed_password.return_value = False
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Handling SED password reset started..." in result.output
        assert "Error: SED password reset failed" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_not_implemented(self, mock_platform):
        """Test NotImplementedError handling for reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.reset_sed_password.side_effect = NotImplementedError
        mock_platform.return_value.get_chassis.return_value = mock_chassis

        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Error: SED management not implemented on this platform" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_exception(self, mock_platform):
        """Test general exception handling for reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.reset_sed_password.side_effect = Exception("Reset test error")
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Error resetting SED password: Reset test error" in result.output
