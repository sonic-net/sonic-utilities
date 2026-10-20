from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from sonic_installer.main import cli, cleanup
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

    assert bootloader.get_installed_images() == [
        "SONiC-OS-1",
        ""
    ]

    # Case 2 First_slot no image and second_slot valid sonic image
    proc1 = MagicMock()
    proc1.communicate.return_value = ("NONE", None)

    proc2 = MagicMock()
    proc2.communicate.return_value = ("SONiC-OS-2\n", None)

    mock_popen.side_effect = [proc1, proc2]

    bootloader = UbootBootloader()

    assert bootloader.get_installed_images() == [
        "",
        "SONiC-OS-2"
    ]


@patch.object(UbootBootloader, "get_installed_images")
@patch("subprocess.run")
def test_set_next_image_preserves_slot_mapping(mock_run, mock_get_images):

    mock_get_images.return_value = [
        "",
        "SONiC-OS-2"
    ]

    bootloader = UbootBootloader()

    bootloader.set_next_image("SONiC-OS-2")

    mock_run.assert_called_once()


@patch.object(UbootBootloader, "get_installed_images")
def test_list_images_preserves_slot_ordering(mock_get_images):
    mock_get_images.return_value = [
        "",
        "SONiC-OS-2"
    ]
    runner = CliRunner()

    result = runner.invoke(cli, ["list"])

    assert "SONiC-OS-2" in result.output


@patch("sonic_installer.main.get_bootloader")
def test_cleanup_skips_empty_slot_placeholder(mock_get_bootloader):
    bootloader = MagicMock(spec=UbootBootloader)

    bootloader.get_installed_images.return_value = [
        "",
        "SONiC-OS-2"
    ]
    bootloader.get_current_image.return_value = "SONiC-OS-2"
    bootloader.get_next_image.return_value = "SONiC-OS-2"

    mock_get_bootloader.return_value = bootloader

    cleanup()

    bootloader.remove_image.assert_not_called()
