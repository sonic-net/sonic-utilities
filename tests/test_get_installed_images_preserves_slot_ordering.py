from unittest.mock import MagicMock, patch, call
from click.testing import CliRunner
from sonic_installer.main import cleanup, sonic_installer
from sonic_installer.bootloader.uboot import UbootBootloader


@patch("subprocess.Popen")
def test_get_installed_images_preserves_slot_ordering(mock_popen):
    """
    Regression test for Issue-4968.

    Empty U-Boot slots must be represented as "" so that the
    returned image index continues to map to the underlying slot.
    """

    # Case 1 First_slot_valid sonic image and second_slot no image
    proc1 = MagicMock()
    proc1.communicate.return_value = ("SONiC-OS-1\n", None)

    proc2 = MagicMock()
    proc2.communicate.return_value = ("NONE", None)

    mock_popen.side_effect = [proc1, proc2]

    bootloader = UbootBootloader()

    assert bootloader.get_installed_images() == ["SONiC-OS-1", ""]

    # Case 2 First_slot no image and second_slot valid sonic image
    proc1 = MagicMock()
    proc1.communicate.return_value = ("NONE", None)

    proc2 = MagicMock()
    proc2.communicate.return_value = ("SONiC-OS-2\n", None)

    mock_popen.side_effect = [proc1, proc2]

    bootloader = UbootBootloader()

    assert bootloader.get_installed_images() == ["", "SONiC-OS-2"]


@patch.object(UbootBootloader, "get_installed_images")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_set_next_image_preserves_slot_mapping(mock_run_command, mock_get_images):

    mock_get_images.return_value = ["", "SONiC-OS-2"]

    bootloader = UbootBootloader()

    bootloader.set_next_image("SONiC-OS-2")

    mock_run_command.assert_called_once_with(
        ['/usr/bin/fw_setenv', 'boot_once', 'run sonic_image_2']
    )


@patch("sonic_installer.main.get_bootloader")
def test_cleanup_skips_empty_slot_placeholder_first_slot(mock_get_bootloader):
    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = ["", "SONiC-OS-2"]
    bootloader.get_current_image.return_value = "SONiC-OS-2"
    bootloader.get_next_image.return_value = "SONiC-OS-2"

    mock_get_bootloader.return_value = bootloader

    cleanup.callback()

    bootloader.remove_image.assert_not_called()


@patch("sonic_installer.main.get_bootloader")
def test_cleanup_skips_empty_slot_placeholder_second_slot(mock_get_bootloader):
    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = ["SONiC-OS-1", ""]
    bootloader.get_current_image.return_value = "SONiC-OS-1"
    bootloader.get_next_image.return_value = "SONiC-OS-1"

    mock_get_bootloader.return_value = bootloader

    cleanup.callback()

    bootloader.remove_image.assert_not_called()


@patch.object(UbootBootloader, "get_installed_images")
@patch("subprocess.Popen")
def test_get_next_image_slot1_preserves_mapping(mock_popen, mock_get_images):

    mock_get_images.return_value = ["SONiC-OS-1", ""]

    proc = MagicMock()
    proc.communicate.return_value = ("run sonic_image_1\n", None)
    mock_popen.return_value = proc

    bootloader = UbootBootloader()

    assert bootloader.get_next_image() == "SONiC-OS-1"


@patch.object(UbootBootloader, "get_installed_images")
@patch("subprocess.Popen")
def test_get_next_image_slot2_preserves_mapping(mock_popen, mock_get_images):

    mock_get_images.return_value = ["", "SONiC-OS-2"]

    proc = MagicMock()
    proc.communicate.return_value = ("run sonic_image_2\n", None)
    mock_popen.return_value = proc

    bootloader = UbootBootloader()

    assert bootloader.get_next_image() == "SONiC-OS-2"


@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
def test_list_preserves_slot_ordering_second_slot(mock_get_bootloader, _mock_geteuid):

    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = ["", "SONiC-OS-2"]

    bootloader.get_current_image.return_value = "SONiC-OS-2"
    bootloader.get_next_image.return_value = "SONiC-OS-2"

    mock_get_bootloader.return_value = bootloader

    runner = CliRunner()

    result = runner.invoke(sonic_installer, ["list"])

    assert result.exit_code == 0, result.output
    assert "SONiC-OS-2" in result.output
    bootloader.get_installed_images.assert_called_once()
    bootloader.get_current_image.assert_called_once()
    bootloader.get_next_image.assert_called_once()


@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
def test_remove_skip_empty_slot_placeholder(mock_get_bootloader, _mock_geteuid):

    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = ["", "SONiC-OS-2"]

    bootloader.get_current_image.return_value = "SONiC-OS-2"

    mock_get_bootloader.return_value = bootloader

    runner = CliRunner()

    result = runner.invoke(sonic_installer, ["remove", ""], input="y\n")

    assert result.exit_code == 0, result.output
    bootloader.remove_image.assert_not_called()


@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
def test_set_default_rejects_empty_slot(mock_get_bootloader, _mock_geteuid):

    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = ["", "SONiC-OS-2"]

    mock_get_bootloader.return_value = bootloader

    runner = CliRunner()

    result = runner.invoke(sonic_installer, ["set-default", ""])

    assert result.exit_code != 0, result.output
    bootloader.set_default_image.assert_not_called()


@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
def test_set_next_boot_rejects_empty_slot(mock_get_bootloader, _mock_geteuid):

    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = ["", "SONiC-OS-2"]

    mock_get_bootloader.return_value = bootloader

    runner = CliRunner()

    result = runner.invoke(sonic_installer, ["set-next-boot", ""])

    assert result.exit_code != 0, result.output
    bootloader.set_next_image.assert_not_called()


@patch.object(UbootBootloader, "get_installed_images")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_set_next_image_setproper_image(mock_run_command, mock_get_images):

    mock_get_images.return_value = ["SONiC-OS-10.22", "SONiC-OS-10.2"]

    bootloader = UbootBootloader()

    bootloader.set_next_image("SONiC-OS-10.2")

    mock_run_command.assert_called_once_with(
        ['/usr/bin/fw_setenv', 'boot_once', 'run sonic_image_2']
    )


@patch.object(UbootBootloader, "get_installed_images")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_set_default_image_setproper_image(mock_run_command, mock_get_images):

    mock_get_images.return_value = ["SONiC-OS-10.22", "SONiC-OS-10.2"]

    bootloader = UbootBootloader()

    bootloader.set_default_image("SONiC-OS-10.2")

    mock_run_command.assert_called_once_with(
        ['/usr/bin/fw_setenv', 'boot_next', 'run sonic_image_2'])


@patch.object(UbootBootloader, "get_installed_images")
@patch("sonic_installer.bootloader.uboot.subprocess.call")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image_removes_proper_image(
        mock_run_command,
        mock_subprocess_call,
        mock_get_images):

    mock_get_images.return_value = [
        "SONiC-OS-10.22",
        "SONiC-OS-10.2"
    ]

    bootloader = UbootBootloader()

    bootloader.remove_image("SONiC-OS-10.2")

    expected_calls = [
        call(['/usr/bin/fw_setenv', 'boot_next', 'run sonic_image_1']),
        call(['/usr/bin/fw_setenv', 'sonic_version_2', 'NONE']),
    ]

    assert mock_run_command.call_args_list == expected_calls

    mock_subprocess_call.assert_called_once_with(
        ['rm', '-rf', '/host/image-10.2']
    )
