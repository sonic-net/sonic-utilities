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


def test_get_next_image_preserves_slot_ordering_from_get_installed_images(mocker):
    """
    Order returned by get_installed_images() must be preserved.
    Case:1 boot_next=sonic_image_1 should select the first element.
    Case:2 boot_next=sonic_image_2 should select the second element.
    """

    # Case:1 boot_next=sonic_image_1 should select the first element.
    bootloader = UbootBootloader()

    mocker.patch.object(
        bootloader,
        "get_installed_images",
        return_value=[
            "SONiC-OS-1"
            "",
        ]
    )

    proc = mocker.Mock()
    proc.communicate.return_value = ("run sonic_image_1\n", None)

    mocker.patch(
        "subprocess.Popen",
        return_value=proc
    )

    assert (
        bootloader.get_next_image()
        == "SONiC-OS-1"
    )

    # Case:2 boot_next=sonic_image_2 should select the second element.
    mocker.patch.object(
        bootloader,
        "get_installed_images",
        return_value=[
            "",
            "SONiC-OS-2"
        ]
    )

    proc = mocker.Mock()
    proc.communicate.return_value = ("run sonic_image_2\n", None)

    mocker.patch(
        "subprocess.Popen",
        return_value=proc
    )

    assert (
        bootloader.get_next_image()
        == "SONiC-OS-2"
    )
