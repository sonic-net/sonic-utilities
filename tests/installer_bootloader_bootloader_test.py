import os

# Import test module
import sonic_installer.bootloader.bootloader as bl


from unittest.mock import patch, mock_open


def test_get_image_path():
    # Constants
    image = f'{bl.IMAGE_PREFIX}expeliarmus-{bl.IMAGE_PREFIX}abcde'
    path_prefix = os.path.join(bl.HOST_PATH, bl.IMAGE_DIR_PREFIX)
    exp_image_path = f'{path_prefix}expeliarmus-{bl.IMAGE_PREFIX}abcde'

    bootloader = bl.Bootloader()

    # Test replacement image id with image path (direct match without ROOTFS check
    # should fail now if we follow the strict logic)
    # Actually, the base class now prefers A/B slots, then direct version with ROOTFS, then fallback.
    # So we need to mock these to test.

    with patch('sonic_installer.bootloader.bootloader.path.exists', return_value=False):
        # 1. No A/B slots, no direct match -> returns default path
        assert bootloader.get_image_path(image) == exp_image_path


@patch('sonic_installer.bootloader.bootloader.path.exists')
@patch('sonic_installer.bootloader.bootloader.path.isfile')
@patch('builtins.open', new_callable=mock_open, read_data='build_version: "abcde"')
def test_get_image_path_ab_slots(mock_file, mock_isfile, mock_exists):
    # Test A/B slot matching
    image = f'{bl.IMAGE_PREFIX}abcde'

    # Mock image-A exists and has correct config
    def exists_side_effect(p):
        return p in [os.path.join(bl.HOST_PATH, 'image-A')]

    mock_exists.side_effect = exists_side_effect
    mock_isfile.return_value = True

    bootloader = bl.Bootloader()
    assert bootloader.get_image_path(image) == os.path.join(bl.HOST_PATH, 'image-A')


@patch('sonic_installer.bootloader.bootloader.path.exists')
@patch('sonic_installer.bootloader.bootloader.path.isfile')
def test_get_image_path_direct_with_rootfs(mock_isfile, mock_exists):
    # Test direct version match with ROOTFS
    image = f'{bl.IMAGE_PREFIX}uvw'
    exp_path = os.path.join(bl.HOST_PATH, bl.IMAGE_DIR_PREFIX) + 'uvw'

    mock_exists.side_effect = lambda x: x == exp_path
    mock_isfile.side_effect = lambda x: x == os.path.join(exp_path, bl.ROOTFS_NAME)

    bootloader = bl.Bootloader()
    assert bootloader.get_image_path(image) == exp_path


@patch('sonic_installer.bootloader.bootloader.path.exists', return_value=False)
@patch('sonic_installer.bootloader.bootloader.path.isdir')
@patch('builtins.open', new_callable=mock_open, read_data='image-A')
def test_get_image_path_fallback_to_b(mock_file, mock_isdir, mock_exists):
    # Test fallback to B when running on A
    image = 'SONiC-OS-any'
    mock_isdir.side_effect = lambda x: x == os.path.join(bl.HOST_PATH, 'image-B')

    bootloader = bl.Bootloader()
    assert bootloader.get_image_path(image) == os.path.join(bl.HOST_PATH, 'image-B')


@patch('sonic_installer.bootloader.bootloader.path.exists', return_value=False)
@patch('sonic_installer.bootloader.bootloader.path.isdir')
@patch('builtins.open', new_callable=mock_open, read_data='image-B')
def test_get_image_path_fallback_to_a(mock_file, mock_isdir, mock_exists):
    # Test fallback to A when running on B
    image = 'SONiC-OS-any'
    mock_isdir.side_effect = lambda x: x == os.path.join(bl.HOST_PATH, 'image-A')

    bootloader = bl.Bootloader()
    assert bootloader.get_image_path(image) == os.path.join(bl.HOST_PATH, 'image-A')


@patch('sonic_installer.bootloader.bootloader.path.exists', return_value=False)
@patch('sonic_installer.bootloader.bootloader.path.isdir')
@patch('builtins.open', new_callable=mock_open, read_data='some other cmdline')
def test_get_image_path_fallback_default_a(mock_file, mock_isdir, mock_exists):
    # Case: unknown running slot, default to A
    image = 'SONiC-OS-any'
    mock_isdir.side_effect = lambda x: x == os.path.join(bl.HOST_PATH, 'image-A')

    bootloader = bl.Bootloader()
    assert bootloader.get_image_path(image) == os.path.join(bl.HOST_PATH, 'image-A')


@patch('sonic_installer.bootloader.bootloader.path.exists', return_value=False)
@patch('sonic_installer.bootloader.bootloader.path.isdir', return_value=False)
@patch('builtins.open', side_effect=OSError("File not found"))
def test_get_image_path_exception_handling(mock_file, mock_isdir, mock_exists):
    # Case: exception during proc reading, should return default path construction
    image = 'SONiC-OS-some_version'
    exp_path = os.path.join(bl.HOST_PATH, bl.IMAGE_DIR_PREFIX) + 'some_version'
    bootloader = bl.Bootloader()
    assert bootloader.get_image_path(image) == exp_path


@patch('sonic_installer.bootloader.bootloader.yaml.safe_load')
@patch('sonic_installer.bootloader.bootloader.path.exists')
@patch('sonic_installer.bootloader.bootloader.path.isfile')
@patch('builtins.open', new_callable=mock_open)
def test_get_image_path_attribute_error(mock_file, mock_isfile, mock_exists, mock_yaml_load):
    # Test A/B slot matching with malformed config (list instead of dict)
    # This triggers AttributeError on data.get("build_version")
    image = f'{bl.IMAGE_PREFIX}abcde'

    # Mock image-A exists, but ROOTFS doesn't (to avoid fallback_slot_path)
    mock_exists.side_effect = lambda x: x == os.path.join(bl.HOST_PATH, 'image-A')

    def isfile_side_effect(p):
        if p.endswith("sonic-config"):
            return True
        return False
    mock_isfile.side_effect = isfile_side_effect

    # Mock yaml.safe_load to return a list (triggers AttributeError on .get())
    mock_yaml_load.return_value = ['not_a_dict']

    # Mock file content: raise OSError for /proc/cmdline
    mock_file.side_effect = [mock_file.return_value, OSError("File not found")]

    bootloader = bl.Bootloader()
    # It should log error and continue to other slots or fallback
    # Since fallback_slot_path is NOT set and /proc/cmdline fails, it returns default path
    exp_path = os.path.join(bl.HOST_PATH, bl.IMAGE_DIR_PREFIX) + 'abcde'
    assert bootloader.get_image_path(image) == exp_path
