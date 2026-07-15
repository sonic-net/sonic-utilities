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
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.change_sed_password.return_value = True
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            [],
            input='validpassword\nvalidpassword\n',
        )
        assert "Handling SED password change started..." in result.output
        assert "SED password change process completed successfully" in result.output
        mock_sed_mgmt.change_sed_password.assert_called_once_with("validpassword")

    @patch('sonic_platform.platform.Platform')
    def test_change_password_failure(self, mock_platform):
        """Test failed password change"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.change_sed_password.return_value = False
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            [],
            input='validpassword\nvalidpassword\n',
        )
        assert "Handling SED password change started..." in result.output
        assert "Error: SED password change failed" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_change_password_not_supported(self, mock_platform):
        """Test when SED management is not supported (get_sed_mgmt returns None)"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.get_sed_mgmt.return_value = None
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"], [])
        assert "Error: SED management not supported on this platform" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_change_password_exception(self, mock_platform):
        """Test general exception handling"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.change_sed_password.side_effect = Exception("Test error")
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["change-password"],
            [],
            input='validpassword\nvalidpassword\n',
        )
        assert "Error changing SED password: Test error" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_success(self, mock_platform):
        """Test successful password reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.reset_sed_password.return_value = True
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Handling SED password reset started..." in result.output
        assert "SED password reset process completed successfully" in result.output
        mock_sed_mgmt.reset_sed_password.assert_called_once()

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_failure(self, mock_platform):
        """Test failed password reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.reset_sed_password.return_value = False
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Handling SED password reset started..." in result.output
        assert "Error: SED password reset failed" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_not_supported(self, mock_platform):
        """Test when SED management is not supported (get_sed_mgmt returns None)"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.get_sed_mgmt.return_value = None
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Error: SED management not supported on this platform" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_reset_password_exception(self, mock_platform):
        """Test general exception handling for reset"""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.reset_sed_password.side_effect = Exception("Reset test error")
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["reset-password"],
            []
        )
        assert "Error resetting SED password: Reset test error" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_wipe_ssd_success_confirm_yes(self, mock_platform):
        """wipe-ssd success path with interactive 'y' confirmation."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.return_value = True
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["wipe-ssd"],
            [],
            input='y\n',
        )
        assert "SSD ERASE STARTED" in result.output
        assert "SSD wipe completed successfully" in result.output
        mock_sed_mgmt.wipe_ssd.assert_called_once()

    @patch('sonic_platform.platform.Platform')
    def test_wipe_ssd_confirm_abort(self, mock_platform):
        """wipe-ssd aborts and does NOT call wipe_ssd when user answers 'n'."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["wipe-ssd"],
            [],
            input='n\n',
        )
        mock_sed_mgmt.wipe_ssd.assert_not_called()
        # click.confirm(abort=True) exits non-zero on abort.
        assert result.exit_code != 0

    @patch('sonic_platform.platform.Platform')
    def test_wipe_ssd_yes_flag_skips_prompt(self, mock_platform):
        """wipe-ssd with -y skips the confirmation prompt."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.return_value = True
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["wipe-ssd"],
            ['--yes'],
        )
        assert "SSD wipe completed successfully" in result.output
        mock_sed_mgmt.wipe_ssd.assert_called_once()

    @patch('sonic_platform.platform.Platform')
    def test_wipe_ssd_failure(self, mock_platform):
        """wipe-ssd reports failure when SedMgmt.wipe_ssd returns False."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.return_value = False
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["wipe-ssd"],
            ['--yes'],
        )
        assert "Error: SSD wipe failed" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_wipe_ssd_not_supported(self, mock_platform):
        """wipe-ssd exits cleanly when get_sed_mgmt() returns None."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.get_sed_mgmt.return_value = None
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["wipe-ssd"],
            ['--yes'],
        )
        assert "Error: SED management not supported on this platform" in result.output

    @patch('sonic_platform.platform.Platform')
    def test_wipe_ssd_exception(self, mock_platform):
        """wipe-ssd surfaces unexpected exceptions."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.side_effect = Exception("boom")
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            config.config.commands["sed"].commands["wipe-ssd"],
            ['--yes'],
        )
        assert "Error wiping SSD: boom" in result.output
