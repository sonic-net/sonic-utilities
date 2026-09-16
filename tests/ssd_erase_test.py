from click.testing import CliRunner
from mock import patch, MagicMock
from ssd_erase.main import ssd_erase


class TestSsdErase(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @patch('sonic_platform.platform.Platform')
    def test_ssd_erase_success_confirm_yes(self, mock_platform):
        """ssd-erase success path with interactive 'y' confirmation."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.return_value = True
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            ssd_erase,
            [],
            input='y\n',
        )
        assert "SSD ERASE STARTED" in result.output
        assert "SSD erase completed successfully" in result.output
        assert result.exit_code == 0
        mock_sed_mgmt.wipe_ssd.assert_called_once()

    @patch('sonic_platform.platform.Platform')
    def test_ssd_erase_confirm_abort(self, mock_platform):
        """ssd-erase aborts and does NOT call wipe_ssd when user answers 'n'."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            ssd_erase,
            [],
            input='n\n',
        )
        mock_sed_mgmt.wipe_ssd.assert_not_called()
        # click.confirm(abort=True) exits non-zero on abort.
        assert result.exit_code != 0

    @patch('sonic_platform.platform.Platform')
    def test_ssd_erase_yes_flag_skips_prompt(self, mock_platform):
        """ssd-erase with -y skips the confirmation prompt."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.return_value = True
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            ssd_erase,
            ['--yes'],
        )
        assert "SSD erase completed successfully" in result.output
        mock_sed_mgmt.wipe_ssd.assert_called_once()

    @patch('sonic_platform.platform.Platform')
    def test_ssd_erase_failure(self, mock_platform):
        """ssd-erase reports failure when SedMgmt.wipe_ssd returns False."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.return_value = False
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            ssd_erase,
            ['--yes'],
        )
        assert "Error: SSD erase failed" in result.output
        assert result.exit_code == 1

    @patch('sonic_platform.platform.Platform')
    def test_ssd_erase_not_supported(self, mock_platform):
        """ssd-erase exits cleanly when get_sed_mgmt() returns None."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_chassis.get_sed_mgmt.return_value = None
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            ssd_erase,
            ['--yes'],
        )
        assert "Error: SED management not supported on this platform" in result.output
        assert result.exit_code == 1

    @patch('sonic_platform.platform.Platform')
    def test_ssd_erase_exception(self, mock_platform):
        """ssd-erase surfaces unexpected exceptions."""
        runner = CliRunner()
        mock_chassis = MagicMock()
        mock_sed_mgmt = MagicMock()
        mock_sed_mgmt.wipe_ssd.side_effect = Exception("boom")
        mock_chassis.get_sed_mgmt.return_value = mock_sed_mgmt
        mock_platform.return_value.get_chassis.return_value = mock_chassis
        result = runner.invoke(
            ssd_erase,
            ['--yes'],
        )
        assert "Error erasing SSD: boom" in result.output
        assert result.exit_code == 1
