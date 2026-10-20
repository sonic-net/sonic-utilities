from unittest.mock import MagicMock, patch
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

    installed_images = bootloader.get_installed_images()
    assert installed_images == [
        "SONiC-OS-1",
        ""
    ]
    bootloader.set_next_image(installed_images[0])

    next_image = bootloader.get_next_image()
    assert next_image == installed_images[0]

    # Case 2 First_slot no image and second_slot valid sonic image
    proc1 = MagicMock()
    proc1.communicate.return_value = ("NONE", None)

    proc2 = MagicMock()
    proc2.communicate.return_value = ("SONiC-OS-2\n", None)

    mock_popen.side_effect = [proc1, proc2]

    bootloader = UbootBootloader()

    installed_images = bootloader.get_installed_images()
    assert installed_images == [
        "",
        "SONiC-OS-2"
    ]

    bootloader.set_next_image(installed_images[1])

    next_image = bootloader.get_next_image()
    assert next_image == installed_images[1]
