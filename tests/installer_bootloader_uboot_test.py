import os
from unittest.mock import Mock, patch, call

# Import test module
import sonic_installer.bootloader.uboot as uboot

# Constants
installed_images = [
    f'{uboot.IMAGE_PREFIX}expeliarmus-{uboot.IMAGE_PREFIX}abcde',
    f'{uboot.IMAGE_PREFIX}expeliarmus-abcde',
]

class MockProc():
    commandline = "linuxargs="
    def communicate():
        return commandline, None

def mock_run_command(cmd):
    MockProc.commandline = cmd

@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_default_image(mock_run_cmd):
    subcmd = ['/usr/bin/fw_setenv', 'boot_next']
    image0, image1 = ['run sonic_image_1'], ['run sonic_image_2']
    expected_call0, expected_call1 = [call(subcmd + image0)], [call(subcmd + image1)]

    bootloader = uboot.UbootBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)
    bootloader.set_default_image(installed_images[0])
    assert mock_run_cmd.call_args_list == expected_call0

    mock_run_cmd.call_args_list = []
    bootloader.set_default_image(installed_images[1])
    assert mock_run_cmd.call_args_list == expected_call1

@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_next_image(mock_run_cmd):
    subcmd = ['/usr/bin/fw_setenv', 'boot_once']
    image0, image1 = ['run sonic_image_1'], ['run sonic_image_2']
    expected_call0, expected_call1 = [call(subcmd + image0)], [call(subcmd + image1)]

    bootloader = uboot.UbootBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)
    bootloader.set_next_image(installed_images[0])
    assert mock_run_cmd.call_args_list == expected_call0

    mock_run_cmd.call_args_list = []
    bootloader.set_next_image(installed_images[1])
    assert mock_run_cmd.call_args_list == expected_call1

@patch("sonic_installer.bootloader.uboot.run_command")
def test_install_image(mock_run_cmd):
    image_path = ['sonic_image']
    expected_call = [call(['bash', image_path])]

    bootloader = uboot.UbootBootloader()
    bootloader.install_image(image_path)
    assert mock_run_cmd.call_args_list == expected_call

@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image(run_command_patch):
    # Constants
    image_path_prefix = os.path.join(uboot.HOST_PATH, uboot.IMAGE_DIR_PREFIX)
    exp_image_path = [
        f'{image_path_prefix}expeliarmus-{uboot.IMAGE_PREFIX}abcde',
        f'{image_path_prefix}expeliarmus-abcde'
    ]

    bootloader = uboot.UbootBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)

    # Verify rm command was executed with image path
    bootloader.remove_image(installed_images[0])
    args_list = uboot.subprocess.call.call_args_list
    assert len(args_list) > 0

    args, _ = args_list[0]
    assert exp_image_path[0] in args[0]

    uboot.subprocess.call.call_args_list = []
    bootloader.remove_image(installed_images[1])
    args_list = uboot.subprocess.call.call_args_list
    assert len(args_list) > 0

    args, _ = args_list[0]
    assert exp_image_path[1] in args[0]

@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_get_next_image(run_command_patch, popen_patch):
    class MockProc():
        commandline = "boot_next"
        def communicate(self):
            return MockProc.commandline, None

    def mock_run_command(cmd):
        # Remove leading string "/usr/bin/fw_setenv boot_next " -- the 29 characters
        cmd = ' '.join(cmd)
        MockProc.commandline = cmd[29:]

    run_command_patch.side_effect = mock_run_command
    popen_patch.return_value = MockProc()

    bootloader = uboot.UbootBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)

    bootloader.set_default_image(installed_images[1])
    
    # Verify get_next_image was executed with image path
    next_image=bootloader.get_next_image()

    assert next_image == installed_images[1]

@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_set_fips_uboot(run_command_patch, popen_patch):
    class MockProc():
        commandline = "linuxargs"
        def communicate(self):
            return MockProc.commandline, None

    def mock_run_command(cmd):
        # Remove leading string "/usr/bin/fw_setenv linuxargs " -- the 29 characters
        cmd = ' '.join(cmd)
        MockProc.commandline = 'linuxargs=' + cmd[29:]

    run_command_patch.side_effect = mock_run_command
    popen_patch.return_value = MockProc()

    image = 'test-image'
    bootloader = uboot.UbootBootloader()

    # The the default setting
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

def test_verify_image_sign():
    bootloader = uboot.UbootBootloader()
    image = 'test-image'
    return_value = None
    is_supported = bootloader.is_secure_upgrade_image_verification_supported()
    try:
        return_value = bootloader.verify_image_sign(image)
    except NotImplementedError:
        assert not is_supported
    else:
        assert False, "Wrong return value from verify_image_sign, returned" + str(return_value)
