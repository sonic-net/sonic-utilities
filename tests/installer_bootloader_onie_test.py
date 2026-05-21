from unittest.mock import Mock, patch

# Import test module
import sonic_installer.bootloader.onie as onie


@patch("sonic_installer.bootloader.onie.re.search")
def test_get_current_image(re_search):
    # Constants
    image = f'{onie.IMAGE_DIR_PREFIX}expeliarmus-{onie.IMAGE_DIR_PREFIX}abcde'
    exp_image = f'{onie.IMAGE_PREFIX}expeliarmus-{onie.IMAGE_DIR_PREFIX}abcde'

    bootloader = onie.OnieInstallerBootloader()

    # Test image dir conversion
    onie.re.search().group = Mock(return_value=image)
    assert bootloader.get_current_image() == exp_image

def test_verify_image_sign():
    bootloader = onie.OnieInstallerBootloader()
    return_value = None
    is_supported = bootloader.is_secure_upgrade_image_verification_supported()
    try:
        return_value = bootloader.verify_image_sign('some_path.path')
    except NotImplementedError:
        assert not is_supported
    else:
        assert False, "Wrong return value from verify_image_sign, returned" + str(return_value)