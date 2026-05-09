from unittest.mock import mock_open, patch

from sonic_installer.bootloader.null import NullBootloader


def test_get_current_image_success():
    bootloader = NullBootloader()
    mock_yaml_data = "build_version: '202311'\n"
    with patch("builtins.open", mock_open(read_data=mock_yaml_data)):
        assert bootloader.get_current_image() == "SONiC-OS-202311"


def test_get_current_image_fallback_to_unknown_if_missing_key():
    bootloader = NullBootloader()
    mock_yaml_data = "other_key: 'value'\n"
    with patch("builtins.open", mock_open(read_data=mock_yaml_data)):
        assert bootloader.get_current_image() == "SONiC-OS-Unknown"


def test_get_current_image_fallback_to_unknown_on_exception():
    bootloader = NullBootloader()
    with patch("builtins.open", side_effect=OSError("File not found")):
        assert bootloader.get_current_image() == "Unknown"


def test_install_image():
    bootloader = NullBootloader()
    with patch('sonic_installer.bootloader.null.run_command') as mock_run_command:
        bootloader.install_image('dummy_path.bin')
        mock_run_command.assert_called_once_with(['bash', 'dummy_path.bin'])


def test_get_binary_image_version():
    bootloader = NullBootloader()
    assert bootloader.get_binary_image_version('dummy_path.bin') is None


def test_detect():
    assert NullBootloader.detect() is False


def test_supports_package_migration():
    bootloader = NullBootloader()
    assert bootloader.supports_package_migration("image") is False


def test_get_next_image():
    bootloader = NullBootloader()
    assert bootloader.get_next_image() == "Unknown"


def test_get_installed_images():
    bootloader = NullBootloader()
    assert bootloader.get_installed_images() == []


def test_set_default_image():
    bootloader = NullBootloader()
    assert bootloader.set_default_image("image") is True


def test_set_next_image():
    bootloader = NullBootloader()
    assert bootloader.set_next_image("image") is True


def test_remove_image():
    bootloader = NullBootloader()
    bootloader.remove_image("image")  # Should be a no-op


def test_get_binary_image_version_success():
    bootloader = NullBootloader()
    with patch("os.path.isfile", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"image_version=\"202311\"\n")):
            assert bootloader.get_binary_image_version("dummy_path.bin") == "SONiC-OS-202311"


def test_get_binary_image_version_decode_error():
    bootloader = NullBootloader()
    with patch("os.path.isfile", return_value=True):
        # b'\xff' is invalid utf-8, will raise UnicodeDecodeError
        with patch("builtins.open", mock_open(read_data=b"image_version=\"\xff\"\n")):
            assert bootloader.get_binary_image_version("dummy_path.bin") is None


def test_get_binary_image_version_decode_error_success():
    bootloader = NullBootloader()
    with patch("os.path.isfile", return_value=True):
        # b'\xff' is invalid utf-8, will raise UnicodeDecodeError
        with patch("builtins.open", mock_open(read_data=b"image_version=\"202311\"\n\xff\n")):
            assert bootloader.get_binary_image_version("dummy_path.bin") == "SONiC-OS-202311"


def test_verify_image_platform():
    bootloader = NullBootloader()
    assert bootloader.verify_image_platform("dummy_path.bin") is True


def test_verify_secureboot_image():
    bootloader = NullBootloader()
    assert bootloader.verify_secureboot_image("dummy_path.bin") is True


def test_set_fips():
    bootloader = NullBootloader()
    assert bootloader.set_fips("image", True) is True


def test_get_fips():
    bootloader = NullBootloader()
    assert bootloader.get_fips("image") is False


def test_verify_image_sign():
    bootloader = NullBootloader()
    assert bootloader.verify_image_sign("dummy_path.bin") is True
