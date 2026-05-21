import os
from unittest.mock import Mock, patch, call

# Import test module
import sonic_installer.bootloader.aboot as aboot
import tempfile
import shutil

# Constants
image_dir = f'{aboot.IMAGE_DIR_PREFIX}expeliarmus-{aboot.IMAGE_DIR_PREFIX}abcde'
image_chainloader = f'{image_dir}/.sonic-boot.swi'
exp_image = f'{aboot.IMAGE_PREFIX}expeliarmus-{aboot.IMAGE_DIR_PREFIX}abcde'
image_dirs = [image_dir]


@patch('sonic_installer.bootloader.aboot.is_secureboot',
       Mock(return_value=False))
def test_swi_image_path():
    # Constants
    image_id = f'{aboot.IMAGE_PREFIX}expeliarmus-{aboot.IMAGE_PREFIX}abcde'
    exp_image_path = f'flash:{aboot.IMAGE_DIR_PREFIX}expeliarmus-'\
                     f'{aboot.IMAGE_PREFIX}abcde/.sonic-boot.swi'

    bootloader = aboot.AbootBootloader()

    # Verify converted swi image path
    image_path = bootloader._swi_image_path(image_id)
    assert image_path == exp_image_path


@patch("sonic_installer.bootloader.aboot.re.search")
def test_get_current_image(re_search_patch):
    bootloader = aboot.AbootBootloader()

    # Test convertion image dir to image name
    re_search_patch().group = Mock(return_value=image_dir)
    assert bootloader.get_current_image() == exp_image


@patch('sonic_installer.bootloader.aboot.os.listdir',
       Mock(return_value=image_dirs))
def test_get_installed_images():
    bootloader = aboot.AbootBootloader()

    # Test convertion image dir to image name
    assert bootloader.get_installed_images() == [exp_image]


def test_get_next_image():
    bootloader = aboot.AbootBootloader()

    # Test missing boot-config
    bootloader._boot_config_read()

    # Test missing SWI value
    bootloader._boot_config_read = Mock(return_value={})
    assert bootloader.get_next_image() == ''

    # Test convertion image dir to image name
    swi = f'flash:{image_chainloader}'
    bootloader._boot_config_read = Mock(return_value={'SWI': swi})
    assert bootloader.get_next_image() == exp_image

    # Test some other image
    next_image = 'EOS.swi'
    bootloader._boot_config_read = Mock(return_value={'SWI': f'flash:{next_image}'})
    assert bootloader.get_next_image() == next_image


def test_install_image():
    image_path = 'sonic'
    env = os.environ.copy()
    env.update({
        'swipath': image_path,
        'target_path': '/host',
        'sonic_upgrade': '1'
    })

    expected_calls = [
        call(["/usr/bin/unzip", "-od", "/tmp", "%s" % image_path, "boot0"]),
        call(["/bin/sh", "/tmp/boot0"], env=env)
    ]
    with patch('sonic_installer.bootloader.aboot.run_command') as mock_cmd:
        bootloader = aboot.AbootBootloader()
        bootloader.install_image(image_path)
        mock_cmd.assert_has_calls(expected_calls)

def test_set_fips_aboot():
    image = 'test-image'
    dirpath = tempfile.mkdtemp()
    bootloader = aboot.AbootBootloader()
    bootloader.get_image_path = Mock(return_value=dirpath)

    # The the default setting
    bootloader._set_image_cmdline(image, 'test=1')
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

    # Cleanup
    shutil.rmtree(dirpath)

def test_verify_image_sign():
    bootloader = aboot.AbootBootloader()
    return_value = None
    is_supported = bootloader.is_secure_upgrade_image_verification_supported()
    try:
        return_value = bootloader.verify_image_sign(exp_image)
    except NotImplementedError:
        assert not is_supported
    else:
        assert False, "Wrong return value from verify_image_sign, returned" + str(return_value)
