import os

# Import test module
import sonic_installer.bootloader.bootloader as bl


def test_get_image_path():
    # Constants
    image = f'{bl.IMAGE_PREFIX}expeliarmus-{bl.IMAGE_PREFIX}abcde'
    path_prefix = os.path.join(bl.HOST_PATH, bl.IMAGE_DIR_PREFIX)
    exp_image_path = f'{path_prefix}expeliarmus-{bl.IMAGE_PREFIX}abcde'

    bootloader = bl.Bootloader()

    # Test replacement image id with image path
    assert bootloader.get_image_path(image) == exp_image_path
